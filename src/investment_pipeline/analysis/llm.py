"""LLM analysis: turn a scored candidate + its sources into grounded prose.

This is the one place the pipeline calls a model. Design choices that map to the
rubric:

- **Grounded.** The prompt contains only the source text we actually fetched
  (YC one-liner, long description, founder bios). The model is instructed to use
  nothing else and to say so when data is missing — no invented market figures
  or competitor names.
- **Cited.** Every non-obvious claim must carry a Citation back to its source,
  so a reviewer can trust where a statement came from.
- **Cached + committed.** Each response is cached on disk keyed by a hash of the
  exact request. Committing data/llm_cache/ means the whole pipeline replays
  offline with no API key — only a changed input triggers a live call.
- **Auditable call.** The Pass/Watch/Take-a-meeting decision is derived from the
  rule-based score band elsewhere; here the model only writes the rationale.
"""

import hashlib
import json

import anthropic

from .. import config
from ..models import Analysis, ScoredCandidate

MAX_TOKENS = 4096

SYSTEM = """You are an analyst at a seed-stage VC firm triaging startups against \
a specific thesis. You write tight, skimmable memos a partner will actually read.

Hard rules:
- Ground every statement ONLY in the SOURCE MATERIAL provided. Do not use outside
  knowledge, and do not invent market sizes, customer names, competitors, or
  funding details that are not in the sources.
- When the sources do not support a section (e.g. no market data), say so plainly
  as an open question rather than guessing. Missing data is a finding, not a gap
  to paper over.
- Attach a citation to every non-obvious factual claim, naming the source it came
  from (e.g. "YC long description", "Founder bio: <name>").
- Be concise and concrete. No hype, no filler."""


def _sources_block(sc: ScoredCandidate) -> str:
    c = sc.candidate
    lines = [
        f"Name: {c.name}",
        f"One-liner: {c.description}",
        f"YC batch: {c.batch or 'unknown'}",
        f"Location: {c.location or 'unknown'}",
        f"Team size: {c.team_size if c.team_size is not None else 'unknown'}",
        f"Industries/tags: {', '.join(c.industries + c.tags) or 'unknown'}",
        f"YC profile URL: {c.discovery.source_url}",
    ]
    if c.long_description:
        lines.append(f"\nYC long description:\n{c.long_description}")
    if c.founders:
        lines.append("\nFounders:")
        for f in c.founders:
            title = f" ({f.title})" if f.title else ""
            bio = f"\n    bio: {f.bio}" if f.bio else ""
            link = f"\n    linkedin: {f.linkedin_url}" if f.linkedin_url else ""
            lines.append(f"  - {f.name}{title}{bio}{link}")
    for s in c.signals:
        lines.append(f"Signal: {s.description} (source: {s.source})")
    return "\n".join(lines)


def _score_block(sc: ScoredCandidate) -> str:
    band_call = config.RECOMMENDATION_BY_BAND[sc.score.band()]
    lines = [
        f"Thesis: {sc.score.thesis}",
        f"Rule-based score: {sc.score.total}/100 (band: {sc.score.band()})",
        f"Deterministic recommendation from score: {band_call}",
        "Score breakdown:",
    ]
    for comp in sc.score.components:
        lines.append(f"  - {comp.name}: {comp.points:.0f}/{comp.max_points:.0f}"
                     f" — {comp.reason}")
    return "\n".join(lines)


def _prompt(sc: ScoredCandidate) -> str:
    return f"""Analyse this startup against the thesis and write the memo body.

=== THESIS & SCORE (already computed by rule-based scoring) ===
{_score_block(sc)}

=== SOURCE MATERIAL (the only facts you may use) ===
{_sources_block(sc)}

=== YOUR TASK ===
Produce a structured analysis:
- team: founder backgrounds, technical depth, relevant prior experience.
- product: what they actually do, in plain language.
- market: size hint, competitive landscape, and why-now — grounded in the
  sources; flag explicitly what is unknown rather than guessing.
- risks: 2-4 concrete risks or open questions that would kill this.
- what_would_change_our_mind: 2-3 specific things that would move the call.
- recommendation_rationale: 2-4 sentences justifying the "{config.RECOMMENDATION_BY_BAND[sc.score.band()]}" \
call, consistent with the score above.
- citations: every non-obvious factual claim, tied to its source."""


def _cache_key(model: str, prompt: str) -> str:
    payload = json.dumps(
        {"model": model, "system": SYSTEM, "prompt": prompt,
         "schema": Analysis.model_json_schema()},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def analyze(sc: ScoredCandidate, *, model: str | None = None) -> Analysis:
    """Return a grounded Analysis for a scored candidate (cached)."""
    model = model or config.model()
    prompt = _prompt(sc)
    path = config.LLM_CACHE_DIR / f"{_cache_key(model, prompt)}.json"

    if path.exists():
        return Analysis.model_validate_json(path.read_text())

    if config.offline():
        raise FileNotFoundError(
            f"offline mode: no cached analysis for {sc.candidate.name} at {path}. "
            "Re-run without PIPELINE_OFFLINE (and with ANTHROPIC_API_KEY set)."
        )
    if not config.has_api_key():
        raise RuntimeError(
            f"No ANTHROPIC_API_KEY set and no cached analysis for {sc.candidate.name}. "
            "Add your key to .env to generate analyses, or run with committed cache."
        )

    client = anthropic.Anthropic()
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
            output_format=Analysis,
        )
    except anthropic.BadRequestError as exc:
        if "credit balance" in str(exc).lower():
            raise RuntimeError(
                "Anthropic API rejected the request: the account has no credits. "
                "Add credits at console.anthropic.com -> Plans & Billing, then re-run. "
                "The full run costs only a few cents."
            ) from exc
        raise
    analysis = response.parsed_output

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(analysis.model_dump_json(indent=2))
    return analysis
