"""Sourcing: YC hit mapping and the HN domain-match precision fix (ADR-004)."""

from investment_pipeline.sourcing import hn, yc


def test_yc_hit_maps_to_candidate_with_signals():
    hit = {
        "name": "Acme",
        "slug": "acme",
        "website": "https://acme.com",
        "one_liner": "AI agents for banks",
        "long_description": "We automate underwriting.",
        "team_size": 3,
        "batch": "Winter 2026",
        "all_locations": "San Francisco, CA, USA",
        "industries": ["B2B"],
        "tags": ["AI", "Fintech"],
        "launched_at": 1_700_000_000,
        "isHiring": True,
        "top_company": False,
    }
    c = yc._to_candidate(hit)
    assert c.name == "Acme"
    assert c.description == "AI agents for banks"
    assert c.batch == "Winter 2026"
    kinds = {s.kind for s in c.signals}
    assert {"yc_batch", "recent_launch", "yc_hiring"} <= kinds


def test_hn_domain_match_accepts_own_domain():
    hit = {"url": "https://acme.com/launch", "title": "Show HN: Acme"}
    assert hn._story_links_domain(hit, "acme.com")


def test_hn_domain_match_rejects_unrelated_story():
    # The bug ADR-004 fixed: "Locke" must NOT match "account gets locked".
    hit = {"url": "https://stadia.google.com/x", "title": "account gets locked"}
    assert not hn._story_links_domain(hit, "locke.inc")


def test_hn_domain_helper_strips_www():
    assert hn._domain("https://www.acme.com/path") == "acme.com"
    assert hn._domain(None) is None


def test_slug_from_url_extracts_yc_slug():
    from investment_pipeline.sourcing import yc_company
    assert yc_company.slug_from_url(
        "https://www.ycombinator.com/companies/accend") == "accend"
    assert yc_company.slug_from_url(
        "https://www.ycombinator.com/companies/tesora?foo=1") == "tesora"
    # Non-YC URLs are rejected (we don't scrape arbitrary sites).
    assert yc_company.slug_from_url("https://acme.com") is None
