"""YC company-page enrichment: structured founder data.

The Algolia index (yc.py) has no founder information, but each company's detail
page at /companies/<slug> ships an Inertia.js `data-page` payload containing a
`founders` array with names, titles, bios, and LinkedIn URLs. This is our
reliable second source: 100% coverage (every candidate is a YC company), no
false-match risk (it is literally the company's own page), and it feeds both the
Team score and the Stage 3 analysis grounding.

See docs/decisions/005 for why this was chosen over more scraped social sources.
"""

import html
import json
import logging
import re

import httpx

from .. import cache
from ..models import Founder, StartupCandidate

log = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "AI-Investment-Pipeline/0.1 (research; contact in README)"}
_DATA_PAGE_RE = re.compile(r'data-page="(.*?)"', re.DOTALL)


def _fetch_company(slug: str) -> dict:
    """Return the parsed `company` payload from a YC company page (cached)."""

    def fetch() -> dict:
        url = f"https://www.ycombinator.com/companies/{slug}"
        resp = httpx.get(url, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        match = _DATA_PAGE_RE.search(resp.text)
        if not match:
            raise RuntimeError(f"No data-page payload on YC page for {slug}")
        payload = json.loads(html.unescape(match.group(1)))
        company = payload.get("props", {}).get("company", {})
        # Store only the fields we use, keeping the cached file small and readable.
        return {
            "name": company.get("name"),
            "year_founded": company.get("year_founded"),
            "founders": [
                {
                    "full_name": f.get("full_name"),
                    "title": f.get("title"),
                    "founder_bio": f.get("founder_bio"),
                    "linkedin_url": f.get("linkedin_url"),
                }
                for f in company.get("founders", [])
            ],
        }

    return cache.get_or_fetch("yc", f"company-{slug}", fetch)


def _slug_of(candidate: StartupCandidate) -> str | None:
    """Recover the YC slug from the candidate's discovery URL."""
    url = str(candidate.discovery.source_url)
    marker = "/companies/"
    if marker in url:
        return url.rsplit(marker, 1)[1].strip("/") or None
    return None


def founders_for(candidate: StartupCandidate) -> list[Founder]:
    """Fetch structured founders for a candidate (empty on any failure)."""
    slug = _slug_of(candidate)
    if not slug:
        return []
    try:
        company = _fetch_company(slug)
    except (httpx.HTTPError, RuntimeError, json.JSONDecodeError) as exc:
        log.warning("YC company lookup failed for %r: %s", slug, exc)
        return []

    founders: list[Founder] = []
    for f in company.get("founders", []):
        name = (f.get("full_name") or "").strip()
        if not name:
            continue
        linkedin = f.get("linkedin_url") or None
        # Some LinkedIn URLs on YC omit the scheme; normalise so the model accepts them.
        if linkedin and linkedin.startswith("linkedin.com"):
            linkedin = "https://" + linkedin
        founders.append(
            Founder(
                name=name,
                title=(f.get("title") or "").strip() or None,
                bio=(f.get("founder_bio") or "").strip() or None,
                linkedin_url=linkedin,
            )
        )
    return founders


def enrich(candidate: StartupCandidate) -> StartupCandidate:
    """Attach structured founders to a candidate in place."""
    candidate.founders = founders_for(candidate)
    return candidate
