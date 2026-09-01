"""Hacker News enrichment via the public Algolia HN Search API (no key needed).

YC gives us structured company data; HN gives us community traction and
freshness. For each candidate we look for an HN story that links the company's
own website (a Show HN / Launch HN) and attach its points + comment count as a
traction signal.

Matching is by **website domain, not company name**. Names like "Locke", "Squid",
"Lance" or "Avent" collide with unrelated stories (a person, the squid proxy, a
French word), so name matching produces confident-looking garbage. Tying the
signal to a story that actually links the company's domain keeps it precise and
traceable. Candidates with no such story simply get no HN signal — the pipeline
must stay robust to missing data.
"""

import logging
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from .. import cache
from ..models import Signal, StartupCandidate

log = logging.getLogger(__name__)

SEARCH_URL = "https://hn.algolia.com/api/v1/search"
_HEADERS = {"User-Agent": "AI-Investment-Pipeline/0.1 (research; contact in README)"}


def _domain(url: str | None) -> str | None:
    """Registrable host for a URL, without a leading www. (best-effort)."""
    if not url:
        return None
    host = urlparse(url).netloc.lower()
    return host.removeprefix("www.") or None


def _story_links_domain(hit: dict, domain: str) -> bool:
    """True if an HN hit points at (or mentions) the company's own domain."""
    story_host = _domain(hit.get("url"))
    if story_host and (story_host == domain or story_host.endswith("." + domain)):
        return True
    # Launch HN posts are often text-only; fall back to the domain appearing in
    # the post body, which still ties the story to this specific company.
    return domain in (hit.get("story_text") or "").lower()


def _best_story(domain: str) -> dict | None:
    """Highest-scoring HN story linking `domain`, or None."""

    def fetch() -> dict:
        resp = httpx.get(
            SEARCH_URL,
            params={"query": domain, "tags": "story", "hitsPerPage": 20},
            headers=_HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    data = cache.get_or_fetch("hn", f"domain-{domain}", fetch)
    matches = [h for h in data.get("hits", []) if _story_links_domain(h, domain)]
    if not matches:
        return None
    return max(matches, key=lambda h: h.get("points") or 0)


def signals_for(candidate: StartupCandidate) -> list[Signal]:
    """HN traction + freshness signals for a candidate (possibly empty).

    HN is an enrichment source, not a required one: if the API is down or there
    is no matching story, we return no signals rather than failing sourcing.
    """
    domain = _domain(str(candidate.website)) if candidate.website else None
    if not domain:
        return []

    try:
        story = _best_story(domain)
    except httpx.HTTPError as exc:
        log.warning("HN lookup failed for %r, skipping HN signal: %s", domain, exc)
        return []
    if not story:
        return []

    object_id = story.get("objectID")
    hn_url = f"https://news.ycombinator.com/item?id={object_id}" if object_id else None
    points = story.get("points") or 0
    num_comments = story.get("num_comments") or 0
    created_at = story.get("created_at_i")
    created_dt = datetime.fromtimestamp(created_at, tz=UTC) if created_at else None

    return [
        Signal(
            kind="hn_traction",
            description=(
                f"Hacker News: {points} points, {num_comments} comments "
                f'on "{story.get("title", "").strip()}"'
            ),
            source="Hacker News",
            url=hn_url,
            observed_at=created_dt,
            metadata={"points": points, "num_comments": num_comments},
        )
    ]


def enrich(candidate: StartupCandidate) -> StartupCandidate:
    """Attach HN signals to a candidate in place, returning it for convenience."""
    candidate.signals.extend(signals_for(candidate))
    return candidate
