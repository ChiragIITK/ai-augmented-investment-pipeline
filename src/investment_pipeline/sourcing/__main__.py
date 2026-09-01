"""Run the sourcing stage from the command line.

    python -m investment_pipeline.sourcing "AI agents"
    python -m investment_pipeline.sourcing "AI agents for SMBs" --limit 15

Writes data/candidates.json and prints a readable summary.
"""

import argparse
import logging

from . import pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Source startup candidates for a topic.")
    parser.add_argument("topic", help='e.g. "AI agents for SMBs"')
    parser.add_argument("--limit", type=int, default=20, help="max candidates (default 20)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    candidates = pipeline.run(args.topic, limit=args.limit)

    print(f'\nSourced {len(candidates)} candidates for "{args.topic}":\n')
    for i, c in enumerate(candidates, 1):
        print(f"{i:>2}. {c.name}  ({c.batch})  team={c.team_size}  {c.location}")
        print(f"    {c.description}")
        for s in c.signals:
            print(f"      - [{s.kind}] {s.description}")
    print(f"\nWritten to {pipeline.config.CANDIDATES_PATH}")


if __name__ == "__main__":
    main()
