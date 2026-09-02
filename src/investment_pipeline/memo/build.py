"""Stage 4 orchestration: write one markdown memo per startup, plus an index.

Reads the analyses from Stage 3 and renders them to out/memos/<slug>.md. Also
writes out/memos/README.md — a ranked index so a partner can see the whole
funnel at a glance and click into any memo.
"""

from .. import config
from ..analysis.analyze import slug
from ..models import AnalyzedCandidate
from . import render

_CALL_MARK = {"Take a meeting": "🟢", "Watch": "🟡", "Pass": "🔴"}


def _index(analyzed: list[AnalyzedCandidate]) -> str:
    ranked = sorted(analyzed, key=lambda a: a.score.total, reverse=True)
    lines = [
        "# Investment Pipeline — Memo Index",
        "",
        f"_Thesis: {ranked[0].score.thesis}_" if ranked else "",
        "",
        f"{len(ranked)} candidates, ranked by rule-based thesis-fit score.",
        "",
        "| # | Company | Score | Call | One-liner |",
        "|---|---|---|---|---|",
    ]
    for i, ac in enumerate(ranked, 1):
        mark = _CALL_MARK.get(ac.recommendation, "")
        link = f"[{ac.candidate.name}]({slug(ac.candidate.name)}.md)"
        lines.append(
            f"| {i} | {link} | {ac.score.total} | {mark} {ac.recommendation} | "
            f"{ac.candidate.description} |"
        )
    lines.append("")
    return "\n".join(lines)


def run(analyzed: list[AnalyzedCandidate]) -> list[str]:
    """Render each analysis to a memo and write the index. Returns memo paths."""
    config.MEMO_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for ac in analyzed:
        path = config.MEMO_DIR / f"{slug(ac.candidate.name)}.md"
        path.write_text(render.render(ac))
        paths.append(str(path))
    (config.MEMO_DIR / "README.md").write_text(_index(analyzed))
    return paths
