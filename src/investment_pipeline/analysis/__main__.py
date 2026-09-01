"""Run the scoring stage from the command line.

    python -m investment_pipeline.analysis            # score data/candidates.json
    python -m investment_pipeline.analysis --explain   # also print rule breakdowns

Reads data/candidates.json (from stage 1), writes data/scored.json, and prints a
ranked table. Rule-based only — no API key needed.
"""

import argparse
import json

from .. import config
from ..models import ScoredCandidate
from ..sourcing import pipeline
from . import score as scoring


def run() -> list[ScoredCandidate]:
    candidates = pipeline.load()
    scored = [scoring.score_candidate(c) for c in candidates]
    scored.sort(key=lambda s: s.score.total, reverse=True)

    out = config.DATA_DIR / "scored.json"
    out.write_text(
        json.dumps(
            {"thesis": scoring.THESIS_LABEL,
             "scored": [json.loads(s.model_dump_json()) for s in scored]},
            indent=2, ensure_ascii=False,
        )
    )
    return scored


def main() -> None:
    parser = argparse.ArgumentParser(description="Score candidates against the thesis.")
    parser.add_argument("--explain", action="store_true", help="print rule breakdowns")
    args = parser.parse_args()

    scored = run()
    print(f"\nThesis: {scoring.THESIS_LABEL}\n")
    print(f"{'#':>2}  {'score':>5}  {'band':<7}  name")
    print("-" * 60)
    for i, s in enumerate(scored, 1):
        print(f"{i:>2}  {s.score.total:>5}  {s.score.band():<7}  {s.candidate.name}")
        if args.explain:
            for comp in s.score.components:
                print(f"        {comp.points:>4.0f}/{comp.max_points:<3.0f} "
                      f"{comp.name}: {comp.reason}")
            print()
    print(f"\nWritten to {config.DATA_DIR / 'scored.json'}")


if __name__ == "__main__":
    main()
