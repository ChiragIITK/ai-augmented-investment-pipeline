"""Stage 4: render an AnalyzedCandidate into a one-page markdown memo.

Deterministic — no LLM. It stitches together the rule-based score (auditable),
the grounded LLM narrative, and the score-derived recommendation into something
a partner can skim in 60 seconds and a reviewer can spot-check against sources.
"""

from ..models import AnalyzedCandidate

# Emoji marker so the call is scannable at the top of the file.
_CALL_MARK = {"Take a meeting": "🟢", "Watch": "🟡", "Pass": "🔴"}


def render(ac: AnalyzedCandidate) -> str:
    c = ac.candidate
    a = ac.analysis
    mark = _CALL_MARK.get(ac.recommendation, "")

    meta = " · ".join(
        p for p in [
            str(c.website) if c.website else None,
            f"YC {c.batch}" if c.batch else None,
            c.location,
            f"team {c.team_size}" if c.team_size is not None else None,
        ] if p
    )

    lines = [
        f"# {c.name} — {mark} {ac.recommendation}",
        "",
        f"**{c.description}**",
        "",
        meta,
        "",
        (f"**Score: {ac.score.total}/100** ({ac.score.band()}) · "
         f"_Thesis: {ac.score.thesis}_"),
        "",
        f"## Recommendation: {ac.recommendation}",
        "",
        a.recommendation_rationale,
        "",
        "## Team",
        "",
        a.team,
        "",
        "## Product",
        "",
        a.product,
        "",
        "## Market",
        "",
        a.market,
        "",
        "## Risks & open questions",
        "",
        *[f"- {r}" for r in a.risks],
        "",
        "## What would change our mind",
        "",
        *[f"- {w}" for w in a.what_would_change_our_mind],
        "",
        "## Score breakdown",
        "",
        "| Dimension | Score | Rationale |",
        "|---|---|---|",
        *[
            f"| {comp.name} | {comp.points:.0f}/{comp.max_points:.0f} | "
            f"{comp.reason} |"
            for comp in ac.score.components
        ],
        "",
        "## Sources",
        "",
        "_Every claim above is grounded in these sources:_",
        "",
        *[
            f"- **{cit.source}** — {cit.claim}"
            + (f" ([link]({cit.url}))" if cit.url else "")
            for cit in a.citations
        ],
        "",
        "---",
        "",
        (f"_Sourced from Y Combinator · scored by rule-based thesis fit · "
         f"analysis grounded in the sources above. "
         f"Discovery: {c.discovery.source_url}_"),
        "",
    ]
    return "\n".join(lines)
