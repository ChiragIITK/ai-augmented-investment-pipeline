"""Sourcing orchestration: discover on YC, enrich on HN, write candidates.json.

This is stage 1 of the pipeline. Its only output is data/candidates.json, which
every later stage reads. Keeping the output a plain committed file is what makes
the downstream stages replayable without re-sourcing.
"""

import json

from .. import config
from ..models import StartupCandidate
from . import yc, yc_company


def source(topic: str, *, limit: int = 20) -> list[StartupCandidate]:
    """Discover candidates on YC, then enrich each with founder data.

    Two YC surfaces: the Algolia index (yc.py) for discovery + firmographics, and
    the company detail page (yc_company.py) for structured founders. Both are
    reliable and traceable. Scraped external traction sources (Hacker News,
    GitHub) were evaluated and dropped — empty or noisy for brand-new
    closed-source startups (see docs/decisions/004, and the retained but unwired
    sourcing/hn.py).
    """
    candidates = yc.discover(topic, limit=limit)
    for candidate in candidates:
        yc_company.enrich(candidate)
    return candidates


def run(topic: str, *, limit: int = 20) -> list[StartupCandidate]:
    """Source candidates for a topic and persist them to candidates.json."""
    candidates = source(topic, limit=limit)

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "topic": topic,
        "count": len(candidates),
        "candidates": [json.loads(c.model_dump_json()) for c in candidates],
    }
    config.CANDIDATES_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False)
    )
    return candidates


def load() -> list[StartupCandidate]:
    """Load previously sourced candidates from candidates.json."""
    payload = json.loads(config.CANDIDATES_PATH.read_text())
    return [StartupCandidate.model_validate(c) for c in payload["candidates"]]
