"""Rule-based scoring of candidates against the thesis (docs/decisions/001,003).

Deliberately NOT an LLM. A score a partner will trust has to be auditable: they
should be able to see exactly which rule contributed which points and why. So
each rule returns points plus a plain-language reason, and the total is just
their sum. The rules encode the thesis: AI-native autonomous agents that own a
high-value business workflow end-to-end.

The keyword heuristics are intentionally simple and transparent. They are a
first-pass triage signal, not ground truth — the LLM analysis stage adds the
nuance. Where a heuristic is weak we say so in the reason rather than hiding it.
"""

import json
from datetime import UTC, datetime

from .. import config
from ..models import Score, ScoreComponent, ScoredCandidate, StartupCandidate
from ..sourcing import pipeline as sourcing

THESIS_LABEL = "AI-native autonomous agents owning high-value business workflows"

# Language that suggests the product *executes* a workflow (thesis-positive).
_EXECUTION_TERMS = {
    "automate", "automates", "automating", "automated", "autonomous", "autonomously",
    "run", "runs", "handle", "handles", "resolve", "resolves", "execute", "executes",
    "manage", "manages", "operations", "back-office", "back office", "end-to-end",
    "workflow", "workflows", "pipeline", "process", "processes",
}
# Language that suggests a human still does the work (thesis-negative / copilot).
_ASSISTIVE_TERMS = {
    "copilot", "co-pilot", "assistant", "assist", "assists", "helps you",
    "suggestions", "insights", "recommend", "recommends", "chatbot", "chat with",
    "generate content", "content generation", "writing assistant",
}
# Explicit autonomy cues.
_AUTONOMY_TERMS = {
    "autonomous", "autonomously", "without human", "no human", "fully automated",
    "end-to-end", "24/7", "on its own", "agents that run", "agents that handle",
}


def _text(c: StartupCandidate) -> str:
    parts = [c.name, c.description, c.long_description or "", " ".join(c.tags)]
    return " ".join(parts).lower()


def _count_hits(text: str, terms: set[str]) -> list[str]:
    return sorted({t for t in terms if t in text})


def _ai_centrality(c: StartupCandidate) -> ScoreComponent:
    text = _text(c)
    ai_tag = any(t.lower() == "ai" for t in c.tags)
    central = ("agent" in text) or ("ai" in text and ai_tag)
    if central and ai_tag:
        return ScoreComponent(
            name="AI centrality", points=20, max_points=20,
            reason="Positions as AI/agent-native (AI tag + agent language).",
        )
    if central:
        return ScoreComponent(
            name="AI centrality", points=14, max_points=20,
            reason="Agent/AI language present but not tagged AI on YC.",
        )
    return ScoreComponent(
        name="AI centrality", points=4, max_points=20,
        reason="No strong signal that AI is central to the product.",
    )


def _workflow_execution(c: StartupCandidate) -> ScoreComponent:
    text = _text(c)
    exec_hits = _count_hits(text, _EXECUTION_TERMS)
    assist_hits = _count_hits(text, _ASSISTIVE_TERMS)
    # Reward execution language, subtract assistive/copilot framing.
    points = min(30, len(exec_hits) * 8) - min(14, len(assist_hits) * 7)
    points = max(0, points)
    if exec_hits and not assist_hits:
        reason = f"Owns a workflow: {', '.join(exec_hits[:4])}."
    elif exec_hits and assist_hits:
        reason = (
            f"Mixed framing — execution ({', '.join(exec_hits[:3])}) but also "
            f"assistive ({', '.join(assist_hits[:3])})."
        )
    elif assist_hits:
        reason = f"Reads as assistive/copilot ({', '.join(assist_hits[:3])}), not owner."
    else:
        reason = "No clear workflow-ownership language in the description."
    return ScoreComponent(
        name="Workflow ownership", points=float(points), max_points=30, reason=reason
    )


def _autonomy(c: StartupCandidate) -> ScoreComponent:
    hits = _count_hits(_text(c), _AUTONOMY_TERMS)
    points = min(15, len(hits) * 8)
    reason = (
        f"Explicit autonomy cues: {', '.join(hits[:3])}."
        if hits
        else "No explicit autonomy language (may still be autonomous — see analysis)."
    )
    return ScoreComponent(
        name="Autonomy", points=float(points), max_points=15, reason=reason
    )


def _freshness(c: StartupCandidate) -> ScoreComponent:
    """More recent launch = more worth a partner's attention right now."""
    launch = next(
        (s for s in c.signals if s.kind == "recent_launch" and s.observed_at), None
    )
    if not launch or not launch.observed_at:
        return ScoreComponent(
            name="Freshness", points=5, max_points=15,
            reason="No dated launch signal; using YC batch presence only.",
        )
    days = (datetime.now(UTC) - launch.observed_at).days
    if days <= 120:
        points, note = 15, "launched within ~4 months"
    elif days <= 270:
        points, note = 11, "launched within ~9 months"
    elif days <= 450:
        points, note = 7, "launched within ~15 months"
    else:
        points, note = 4, "launched over 15 months ago"
    return ScoreComponent(
        name="Freshness", points=float(points), max_points=15,
        reason=f"Recent launch ({note}, {launch.observed_at.date().isoformat()}).",
    )


def _momentum(c: StartupCandidate) -> ScoreComponent:
    """Momentum from YC structured signals.

    We deliberately do NOT scrape external traction (HN, GitHub): both are empty
    or noisy for brand-new closed-source startups (see docs/decisions/004). YC's
    own `top_company` and `isHiring` flags are reliable and fully traceable.
    """
    kinds = {s.kind for s in c.signals}
    if "yc_top_company" in kinds:
        return ScoreComponent(
            name="Momentum", points=10, max_points=10,
            reason="Designated a YC Top Company (strong external validation).",
        )
    if "yc_hiring" in kinds:
        return ScoreComponent(
            name="Momentum", points=6, max_points=10,
            reason="Actively hiring per YC listing (has capital and is scaling).",
        )
    return ScoreComponent(
        name="Momentum", points=0, max_points=10,
        reason="No momentum signal (not hiring / not YC-flagged in available data).",
    )


# Prior employers / credentials that signal pedigree, matched in founder bios.
_PEDIGREE_TERMS = {
    "google", "meta", "facebook", "openai", "anthropic", "amazon", "apple",
    "microsoft", "stripe", "uber", "airbnb", "palantir", "nvidia", "tesla",
    "mckinsey", "bcg", "boston consulting", "bain", "goldman", "jpmorgan",
    "rocket internet", "stanford", "mit", "harvard", "berkeley", "cmu", "oxford",
    "cambridge", "phd", "ex-", "y combinator", "forbes 30",
}
# Cues that the team has real technical depth.
_TECHNICAL_TERMS = {
    "cto", "engineer", "engineering", "built", "phd", "ml", "machine learning",
    "research", "developer", "architect", "led engineering",
}
# Cues of prior founder experience / exits.
_SERIAL_TERMS = {
    "co-founder", "founded", "previously founded", "exit", "acquired",
    "second-time", "serial",
}


def _team(c: StartupCandidate) -> ScoreComponent:
    """Team strength from structured founder bios (yc_company.py)."""
    if not c.founders:
        size_ok = c.team_size is not None and 2 <= c.team_size <= 15
        return ScoreComponent(
            name="Team", points=2.0 if size_ok else 0.0, max_points=10,
            reason=(
                f"No founder bios available; team size {c.team_size}."
                if size_ok
                else "No founder data available."
            ),
        )

    bios = " ".join(f.bio.lower() for f in c.founders if f.bio)
    pedigree = sorted({t for t in _PEDIGREE_TERMS if t in bios})
    technical = bool(_TECHNICAL_TERMS & set(bios.split())) or any(
        t in bios for t in _TECHNICAL_TERMS
    )
    serial = any(t in bios for t in _SERIAL_TERMS)

    points = 2.0  # having real, named founders with bios
    if pedigree:
        points += 4
    if technical:
        points += 2
    if serial:
        points += 2
    points = min(10.0, points)

    names = ", ".join(f.name for f in c.founders[:3])
    bits = []
    if pedigree:
        bits.append(f"pedigree ({', '.join(pedigree[:3])})")
    if technical:
        bits.append("technical depth")
    if serial:
        bits.append("prior founder experience")
    detail = "; ".join(bits) if bits else "bios available, no standout markers"
    return ScoreComponent(
        name="Team", points=points, max_points=10,
        reason=f"{len(c.founders)} founder(s) — {names}. {detail}.",
    )


_RULES = (
    _ai_centrality,
    _workflow_execution,
    _autonomy,
    _freshness,
    _momentum,
    _team,
)


def score(candidate: StartupCandidate) -> Score:
    components = [rule(candidate) for rule in _RULES]
    total = round(sum(comp.points for comp in components))
    return Score(total=total, components=components, thesis=THESIS_LABEL)


def score_candidate(candidate: StartupCandidate) -> ScoredCandidate:
    return ScoredCandidate(candidate=candidate, score=score(candidate))


# --- Stage 2 orchestration (reads candidates.json, writes scored.json) ---

SCORED_PATH = config.DATA_DIR / "scored.json"


def run() -> list[ScoredCandidate]:
    """Score all sourced candidates, highest first, and persist to scored.json."""
    scored = [score_candidate(c) for c in sourcing.load()]
    scored.sort(key=lambda s: s.score.total, reverse=True)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCORED_PATH.write_text(
        json.dumps(
            {"thesis": THESIS_LABEL,
             "scored": [json.loads(s.model_dump_json()) for s in scored]},
            indent=2, ensure_ascii=False,
        )
    )
    return scored


def load_scored() -> list[ScoredCandidate]:
    payload = json.loads(SCORED_PATH.read_text())
    return [ScoredCandidate.model_validate(s) for s in payload["scored"]]
