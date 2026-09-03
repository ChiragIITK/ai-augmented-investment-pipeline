"""One command to run the whole pipeline — or any single stage on its own.

    pipeline run --topic "AI agents for Fintech"      # all four stages
    pipeline source --topic "AI agents for Fintech"   # stage 1 only
    pipeline score                                     # stage 2 only
    pipeline analyze                                   # stage 3 only (needs API key)
    pipeline memo                                      # stage 4 only

Each stage reads the previous stage's committed file, so they compose but also
run independently. Offline replay (no key) works via PIPELINE_OFFLINE=1 once the
caches are present.
"""

import argparse

from . import config
from .analysis import analyze
from .analysis import score as scoring
from .memo import build
from .sourcing import pipeline as sourcing

_CALL_MARK = {"Take a meeting": "🟢", "Watch": "🟡", "Pass": "🔴"}


def _print_candidates(candidates) -> None:
    print(f"\nSourced {len(candidates)} candidates:")
    for i, c in enumerate(candidates, 1):
        founders = ", ".join(f.name for f in c.founders) or "—"
        print(f"  {i:>2}. {c.name} ({c.batch}) — {c.description}")
        print(f"      founders: {founders} | signals: {len(c.signals)}")


def _print_scored(scored) -> None:
    print(f"\nThesis: {scoring.THESIS_LABEL}\n")
    print(f"{'#':>2}  {'score':>5}  {'band':<7}  name")
    print("-" * 56)
    for i, s in enumerate(scored, 1):
        print(f"{i:>2}  {s.score.total:>5}  {s.score.band():<7}  {s.candidate.name}")


def _print_analyzed(analyzed) -> None:
    ranked = sorted(analyzed, key=lambda a: a.score.total, reverse=True)
    print(f"\n{'#':>2}  {'score':>5}  call            company")
    print("-" * 56)
    for i, a in enumerate(ranked, 1):
        mark = _CALL_MARK.get(a.recommendation, "")
        print(f"{i:>2}  {a.score.total:>5}  {mark} {a.recommendation:<13} {a.candidate.name}")


# --- individual stages ---

def cmd_source(args) -> None:
    candidates = sourcing.run(args.topic, limit=args.limit)
    _print_candidates(candidates)
    print(f"\n-> {config.CANDIDATES_PATH}")


def cmd_score(args) -> None:
    scored = scoring.run()
    _print_scored(scored)
    print(f"\n-> {scoring.SCORED_PATH}")


def cmd_analyze(args) -> None:
    analyzed = analyze.run(scoring.load_scored(), model=args.model)
    _print_analyzed(analyzed)
    print(f"\n-> {config.ANALYSIS_DIR}/")


def cmd_memo(args) -> None:
    paths = build.run(analyze.load())
    print(f"\nWrote {len(paths)} memos + index -> {config.MEMO_DIR}/")


def cmd_run(args) -> None:
    print(f"[1/4] Sourcing '{args.topic}' ...")
    sourcing.run(args.topic, limit=args.limit)
    print("[2/4] Scoring ...")
    scoring.run()
    print("[3/4] Analyzing (LLM) ...")
    analyze.run(scoring.load_scored(), model=args.model)
    print("[4/4] Rendering memos ...")
    analyzed = analyze.load()
    build.run(analyzed)
    _print_analyzed(analyzed)
    print(f"\nDone. Memos in {config.MEMO_DIR}/ — open README.md for the ranked index.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline", description="AI-augmented investment pipeline."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_topic(p):
        p.add_argument("--topic", required=True, help='e.g. "AI agents for Fintech"')
        p.add_argument("--limit", type=int, default=20, help="max candidates (default 20)")

    def add_model(p):
        p.add_argument("--model", default=None,
                       help=f"LLM model id (default: {config.DEFAULT_MODEL})")

    p_run = sub.add_parser("run", help="run all four stages")
    add_topic(p_run)
    add_model(p_run)
    p_run.set_defaults(func=cmd_run)

    p_source = sub.add_parser("source", help="stage 1: source candidates")
    add_topic(p_source)
    p_source.set_defaults(func=cmd_source)

    p_score = sub.add_parser("score", help="stage 2: rule-based scoring")
    p_score.set_defaults(func=cmd_score)

    p_analyze = sub.add_parser("analyze", help="stage 3: LLM analysis (needs API key)")
    add_model(p_analyze)
    p_analyze.set_defaults(func=cmd_analyze)

    p_memo = sub.add_parser("memo", help="stage 4: render memos")
    p_memo.set_defaults(func=cmd_memo)

    return parser


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
