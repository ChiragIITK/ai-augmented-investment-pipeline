"""Sourcing orchestration: turn a seed into candidates.json.

This is stage 1. It accepts any of the three seed types from the brief — a topic
query, a YC batch feed, or a list of YC company URLs — and produces the same
data/candidates.json that every later stage reads. Keeping the output a plain
committed file is what makes the downstream stages replayable without re-sourcing.

All three seeds resolve through Y Combinator, the one source we went deep on:
- topic  -> YC Algolia index, text query
- batch  -> YC Algolia index, batch facet filter (a whole-batch feed)
- urls   -> YC company pages, one per URL
The URL path is intentionally limited to YC company URLs; scraping arbitrary
company websites would be the shallow multi-source anti-pattern the brief warns
against. See docs/decisions/006.
"""

import json

from .. import config
from ..models import StartupCandidate
from . import yc, yc_company


def source(
    topic: str = "",
    *,
    batch: str | None = None,
    urls: list[str] | None = None,
    limit: int = 20,
) -> list[StartupCandidate]:
    """Discover candidates from a seed, enriched with founder data."""
    if urls:
        candidates = []
        for url in urls:
            slug = yc_company.slug_from_url(url)
            if not slug:
                continue
            candidate = yc_company.candidate_from_slug(slug)
            if candidate:
                candidates.append(candidate)
        return candidates[:limit]

    # topic and/or batch both go through the Algolia index; founders come from
    # the company pages.
    candidates = yc.discover(topic, batch=batch, limit=limit)
    for candidate in candidates:
        yc_company.enrich(candidate)
    return candidates


def _seed_label(topic: str, batch: str | None, urls: list[str] | None) -> dict:
    if urls:
        return {"type": "urls", "value": urls}
    if batch:
        return {"type": "batch", "value": batch, "topic": topic or None}
    return {"type": "topic", "value": topic}


def run(
    topic: str = "",
    *,
    batch: str | None = None,
    urls: list[str] | None = None,
    limit: int = 20,
) -> list[StartupCandidate]:
    """Source candidates from a seed and persist them to candidates.json."""
    candidates = source(topic, batch=batch, urls=urls, limit=limit)

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "seed": _seed_label(topic, batch, urls),
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
