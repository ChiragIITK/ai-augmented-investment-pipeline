"""Y Combinator discovery via the public Algolia index that powers
ycombinator.com/companies.

The companies directory is a client-side app backed by Algolia, so fetching the
HTML gives an empty shell. Instead we read the Algolia app id + search key that
the page ships in `window.AlgoliaOpts` and query the index directly. The key is
a restricted, search-only, public credential (the same one every visitor's
browser uses) and it rotates, so we extract it live rather than hard-coding it.
"""

import json
import re
from datetime import UTC, datetime
from urllib.parse import quote_plus

import httpx

from .. import cache
from ..models import Discovery, Signal, StartupCandidate

COMPANIES_PAGE = "https://www.ycombinator.com/companies"
INDEX = "YCCompany_production"
_HEADERS = {"User-Agent": "AI-Investment-Pipeline/0.1 (research; contact in README)"}


def _algolia_credentials() -> tuple[str, str]:
    """Extract the live Algolia app id and search key from the YC page."""

    def fetch() -> dict:
        resp = httpx.get(COMPANIES_PAGE, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        match = re.search(r'window\.AlgoliaOpts\s*=\s*(\{.*?\})', resp.text)
        if not match:
            raise RuntimeError(
                "Could not find window.AlgoliaOpts on the YC companies page; "
                "the page structure may have changed."
            )
        return json.loads(match.group(1))

    opts = cache.get_or_fetch("yc", "algolia-credentials", fetch)
    return opts["app"], opts["key"]


def search(topic: str, *, limit: int = 20) -> list[dict]:
    """Return raw Algolia hits for a topic query, cached under data/raw/yc/."""

    def fetch() -> dict:
        app_id, api_key = _algolia_credentials()
        url = f"https://{app_id.lower()}-dsn.algolia.net/1/indexes/*/queries"
        params = f"query={quote_plus(topic)}&hitsPerPage={limit}"
        resp = httpx.post(
            url,
            headers={
                "X-Algolia-Application-Id": app_id,
                "X-Algolia-API-Key": api_key,
                "Content-Type": "application/json",
            },
            json={"requests": [{"indexName": INDEX, "params": params}]},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    data = cache.get_or_fetch("yc", f"search-{topic}", fetch)
    return data["results"][0]["hits"]


def _to_candidate(hit: dict) -> StartupCandidate:
    slug = hit.get("slug", "")
    signals: list[Signal] = []

    if hit.get("batch"):
        signals.append(
            Signal(
                kind="yc_batch",
                description=f"Y Combinator {hit['batch']} batch",
                source="Y Combinator",
                url=f"https://www.ycombinator.com/companies/{slug}" if slug else None,
            )
        )

    company_url = f"https://www.ycombinator.com/companies/{slug}" if slug else None

    if hit.get("top_company"):
        signals.append(
            Signal(
                kind="yc_top_company",
                description="Flagged a YC Top Company",
                source="Y Combinator",
                url=company_url,
            )
        )

    if hit.get("isHiring"):
        signals.append(
            Signal(
                kind="yc_hiring",
                description="Actively hiring (YC listing) — a capital/momentum proxy",
                source="Y Combinator",
                url=company_url,
            )
        )

    launched = hit.get("launched_at")
    if launched:
        launched_dt = datetime.fromtimestamp(launched, tz=UTC)
        signals.append(
            Signal(
                kind="recent_launch",
                description=f"Launched {launched_dt.date().isoformat()}",
                source="Y Combinator",
                url=f"https://www.ycombinator.com/companies/{slug}" if slug else None,
                observed_at=launched_dt,
                metadata={"launched_at": launched},
            )
        )

    website = hit.get("website") or None
    return StartupCandidate(
        name=hit.get("name", "").strip(),
        website=website,
        description=(hit.get("one_liner") or "").strip(),
        long_description=(hit.get("long_description") or "").strip() or None,
        team_size=hit.get("team_size"),
        batch=hit.get("batch"),
        location=hit.get("all_locations") or None,
        industries=hit.get("industries", []),
        tags=hit.get("tags", []),
        signals=signals,
        discovery=Discovery(
            source="Y Combinator",
            source_url=f"https://www.ycombinator.com/companies/{slug}"
            if slug
            else COMPANIES_PAGE,
        ),
    )


def discover(topic: str, *, limit: int = 20) -> list[StartupCandidate]:
    """Discover YC startups for a topic, as StartupCandidate objects.

    We always fetch a full page (up to 20) into the cache, then apply `limit` on
    read, so changing --limit is honoured without needing to re-fetch.
    """
    candidates = [_to_candidate(h) for h in search(topic)]
    candidates = [c for c in candidates if c.name and c.description]
    return candidates[:limit]
