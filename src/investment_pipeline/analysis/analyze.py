"""Stage 3 orchestration: scored candidates -> grounded analyses on disk.

Reads the scored candidates, runs the (cached) LLM analysis for each, attaches
the deterministic recommendation from the score band, and writes one
AnalyzedCandidate per startup to data/analysis/<slug>.json.
"""

import re

from .. import config
from ..models import AnalyzedCandidate, ScoredCandidate
from . import llm


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "startup"


def analyze_one(sc: ScoredCandidate, *, model: str | None = None) -> AnalyzedCandidate:
    analysis = llm.analyze(sc, model=model)
    recommendation = config.RECOMMENDATION_BY_BAND[sc.score.band()]
    return AnalyzedCandidate(
        candidate=sc.candidate,
        score=sc.score,
        analysis=analysis,
        recommendation=recommendation,
    )


def run(
    scored: list[ScoredCandidate], *, model: str | None = None
) -> list[AnalyzedCandidate]:
    """Analyse each scored candidate and persist to data/analysis/<slug>.json."""
    config.ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    results: list[AnalyzedCandidate] = []
    for sc in scored:
        analyzed = analyze_one(sc, model=model)
        out = config.ANALYSIS_DIR / f"{slug(sc.candidate.name)}.json"
        out.write_text(analyzed.model_dump_json(indent=2))
        results.append(analyzed)
    return results


def load() -> list[AnalyzedCandidate]:
    """Load previously written analyses from data/analysis/."""
    results = []
    for path in sorted(config.ANALYSIS_DIR.glob("*.json")):
        results.append(AnalyzedCandidate.model_validate_json(path.read_text()))
    return results
