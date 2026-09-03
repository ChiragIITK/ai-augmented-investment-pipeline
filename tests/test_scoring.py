"""Scoring is rule-based precisely so it's testable and auditable."""

from investment_pipeline.analysis import score as scoring
from investment_pipeline.models import Discovery, Founder, Signal, StartupCandidate


def _candidate(**kw) -> StartupCandidate:
    base = {
        "name": "Acme",
        "description": "AI agents that automate underwriting end-to-end",
        "discovery": Discovery(
            source="Y Combinator",
            source_url="https://www.ycombinator.com/companies/acme",
        ),
    }
    base.update(kw)
    return StartupCandidate(**base)


def test_workflow_ownership_rewards_execution_language():
    c = _candidate(description="AI that automates and runs the whole billing workflow",
                   tags=["AI"])
    s = scoring.score(c)
    workflow = next(x for x in s.components if x.name == "Workflow ownership")
    assert workflow.points >= 16


def test_assistive_language_is_penalised():
    owner = scoring.score(_candidate(description="automates the entire claims process",
                                     tags=["AI"]))
    copilot = scoring.score(_candidate(description="a copilot and assistant that helps you",
                                       tags=["AI"]))
    ow = next(x for x in owner.components if x.name == "Workflow ownership").points
    co = next(x for x in copilot.components if x.name == "Workflow ownership").points
    assert ow > co


def test_momentum_uses_yc_hiring_signal():
    hiring = _candidate(signals=[Signal(kind="yc_hiring", description="hiring",
                                        source="Y Combinator")])
    quiet = _candidate()
    hp = next(x for x in scoring.score(hiring).components if x.name == "Momentum").points
    qp = next(x for x in scoring.score(quiet).components if x.name == "Momentum").points
    assert hp > qp == 0


def test_team_reads_founder_bios_for_pedigree():
    c = _candidate(founders=[
        Founder(name="Jane", bio="Previously an engineer at Google; PhD from MIT."),
    ])
    team = next(x for x in scoring.score(c).components if x.name == "Team")
    assert team.points >= 6
    assert "Jane" in team.reason


def test_bands_are_monotonic():
    from investment_pipeline.models import Score
    assert Score(total=75, components=[], thesis="t").band() == "strong"
    assert Score(total=50, components=[], thesis="t").band() == "watch"
    assert Score(total=20, components=[], thesis="t").band() == "weak"


def test_total_is_sum_of_components_and_bounded():
    s = scoring.score(_candidate(tags=["AI"]))
    assert s.total == round(sum(c.points for c in s.components))
    assert 0 <= s.total <= 100
