"""Core data models shared across pipeline stages.

Every stage reads and writes these via JSON on disk, so the models double as the
contract between stages. Keeping them small and explicit is what makes the
pipeline replayable: candidates.json is enough to re-run analysis without the
network.
"""

from datetime import datetime

from pydantic import BaseModel, HttpUrl


class Founder(BaseModel):
    name: str
    title: str | None = None
    bio: str | None = None
    linkedin_url: HttpUrl | None = None


class Discovery(BaseModel):
    """Where a candidate first entered the pipeline."""

    source: str
    source_url: HttpUrl


class Signal(BaseModel):
    """A single freshness or traction data point, always traceable to a URL.

    The task requires at least one freshness/traction signal per candidate, and
    the rubric penalises claims with no source, so every signal carries the URL
    it came from and the time we observed it.
    """

    kind: str  # e.g. "yc_batch", "hn_launch", "hn_traction", "recent_launch"
    description: str  # human-readable, memo-ready
    source: str  # "Y Combinator", "Hacker News"
    url: HttpUrl | None = None
    observed_at: datetime | None = None
    metadata: dict = {}


class StartupCandidate(BaseModel):
    name: str
    website: HttpUrl | None = None
    description: str  # the one-liner
    long_description: str | None = None  # grounding text for later analysis
    founders: list[Founder] = []
    team_size: int | None = None
    batch: str | None = None
    location: str | None = None
    industries: list[str] = []
    tags: list[str] = []
    signals: list[Signal] = []
    discovery: Discovery

    def primary_signal(self) -> Signal | None:
        """Best single signal for a memo header, freshest first."""
        if not self.signals:
            return None
        dated = [s for s in self.signals if s.observed_at]
        if dated:
            return max(dated, key=lambda s: s.observed_at)
        return self.signals[0]


class ScoreComponent(BaseModel):
    """One line of the score breakdown. Every point is traceable to a reason.

    We keep scoring rule-based (not an LLM) precisely so a partner can audit why
    a company got the number it got; this is the unit that makes that possible.
    """

    name: str
    points: float
    max_points: float
    reason: str


class Score(BaseModel):
    total: int  # 0-100
    components: list[ScoreComponent]
    thesis: str  # short label of the thesis scored against

    def band(self) -> str:
        """Coarse bucket used to seed the memo recommendation."""
        if self.total >= 70:
            return "strong"
        if self.total >= 45:
            return "watch"
        return "weak"


class ScoredCandidate(BaseModel):
    candidate: StartupCandidate
    score: Score


class Citation(BaseModel):
    """A single claim tied back to the source it came from.

    The rubric penalises memo claims with no traceable source, so the LLM is
    required to attach one of these to any non-obvious factual statement.
    """

    claim: str
    source: str  # e.g. "YC long description", "Founder bio: Ahmed Gaber"
    url: HttpUrl | None = None


class Analysis(BaseModel):
    """LLM-produced narrative, grounded only in the provided source material.

    The score (Stage 2) is rule-based and lives on ScoredCandidate; this stage
    adds the qualitative prose a partner reads. The recommendation *call* is
    derived deterministically from the score band, not written by the LLM — the
    LLM only writes the rationale that supports it.
    """

    team: str
    product: str
    market: str
    risks: list[str]
    what_would_change_our_mind: list[str]
    recommendation_rationale: str
    citations: list[Citation]


class AnalyzedCandidate(BaseModel):
    candidate: StartupCandidate
    score: Score
    analysis: Analysis
    recommendation: str  # "Pass" | "Watch" | "Take a meeting" (from score band)
