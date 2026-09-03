"""Memo rendering and the fetch-through cache's offline behaviour."""

import pytest

from investment_pipeline import cache, config
from investment_pipeline.memo import render
from investment_pipeline.models import (
    Analysis,
    AnalyzedCandidate,
    Citation,
    Discovery,
    Score,
    ScoreComponent,
    StartupCandidate,
)


def _analyzed() -> AnalyzedCandidate:
    candidate = StartupCandidate(
        name="Acme",
        description="AI agents for banks",
        website="https://acme.com",
        discovery=Discovery(source="Y Combinator",
                            source_url="https://www.ycombinator.com/companies/acme"),
    )
    score = Score(
        total=78,
        components=[ScoreComponent(name="AI centrality", points=20, max_points=20,
                                   reason="AI-native")],
        thesis="AI-native autonomous agents",
    )
    analysis = Analysis(
        team="Strong team.",
        product="Automates underwriting.",
        market="Unknown market size.",
        risks=["Regulatory risk."],
        what_would_change_our_mind=["Revenue proof."],
        recommendation_rationale="Clears the bar.",
        citations=[Citation(claim="Automates underwriting",
                            source="YC long description",
                            url="https://www.ycombinator.com/companies/acme")],
    )
    return AnalyzedCandidate(candidate=candidate, score=score, analysis=analysis,
                             recommendation="Take a meeting")


def test_memo_has_call_score_sections_and_sources():
    md = render.render(_analyzed())
    assert md.startswith("# Acme — 🟢 Take a meeting")
    for section in ("## Team", "## Product", "## Market",
                    "## Risks & open questions", "## Score breakdown", "## Sources"):
        assert section in md
    assert "78/100" in md
    assert "YC long description" in md  # citation is traceable in the memo


def test_cache_offline_miss_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    monkeypatch.setenv("PIPELINE_OFFLINE", "1")
    with pytest.raises(FileNotFoundError):
        cache.get_or_fetch("ns", "missing-key", lambda: {"x": 1})


def test_cache_hit_returns_without_fetching(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    monkeypatch.delenv("PIPELINE_OFFLINE", raising=False)

    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return {"v": "fresh"}

    first = cache.get_or_fetch("ns", "k", fetch)
    second = cache.get_or_fetch("ns", "k", fetch)  # served from disk
    assert first == second == {"v": "fresh"}
    assert calls["n"] == 1  # fetched once, cached thereafter
