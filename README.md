# AI-Augmented Investment Pipeline

A triage pipeline for a seed-stage VC: point it at a topic, and it sources
startups, scores them against a specific thesis, writes a grounded one-page memo
for each, and ends every memo with a clear call — **Pass / Watch / Take a
meeting**.

```
topic ──▶ 1. Source ──▶ 2. Score ──▶ 3. Analyse ──▶ 4. Memo
          (YC)          (rules)       (LLM)          (markdown)
```

## The thesis

> **AI-native autonomous agents that own a high-value business workflow
> end-to-end.**

Specific and held consistently across the whole pipeline — the score rewards
workflow *ownership* over copilots and assistants, and the memos are written
against it. Full reasoning in [`docs/decisions/001-thesis.md`](docs/decisions/001-thesis.md).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .          # registers the `pipeline` command

# Read the committed memos — no setup needed:
open out/memos/README.md

# Re-run the whole thing offline from committed caches (no API key, no network):
PIPELINE_OFFLINE=1 pipeline run --topic "AI agents for Fintech"
```

To generate **fresh** analyses you need an Anthropic API key:

```bash
cp .env.example .env        # then paste your key into .env
pipeline run --topic "AI agents for SMBs"
```

A full 20-startup run costs a few cents to ~$0.50 of API usage.

## One command, or one stage at a time

Each stage reads the previous stage's file on disk, so they chain **and** run
independently:

```bash
pipeline run     --topic "AI agents for Fintech"   # all four stages
pipeline source  --topic "AI agents for Fintech"   # 1: → data/candidates.json
pipeline score                                      # 2: → data/scored.json
pipeline analyze                                     # 3: → data/analysis/*.json  (needs key)
pipeline memo                                        # 4: → out/memos/*.md
```

Options: `--limit N` (how many candidates), `--model <id>` (defaults to
`claude-opus-4-8`; set `PIPELINE_MODEL=claude-sonnet-5` for lower cost).

## How it works

| Stage | What it does | Deterministic? |
|---|---|---|
| **1. Source** | YC's Algolia index for discovery + firmographics; the YC company page for structured founders (name, title, bio, LinkedIn). | ✅ |
| **2. Score** | Six transparent rules vs. the thesis (AI centrality, workflow ownership, autonomy, freshness, momentum, team). Every point carries a reason. **No LLM — so scores are auditable.** | ✅ |
| **3. Analyse** | One grounded LLM call per startup. It sees *only* the fetched sources, must cite every claim, and flags missing data instead of inventing it. | LLM |
| **4. Memo** | Renders score + analysis + score-derived call into a one-page markdown memo. | ✅ |

**The recommendation call is deterministic**, derived from the score band
(strong → Take a meeting, watch → Watch, weak → Pass) — the LLM only writes the
supporting prose, never the number or the call.

## Replayable by design

- Every HTTP response (YC, company pages) is cached under `data/raw/`.
- Every LLM response is cached under `data/llm_cache/`, keyed by a hash of the
  exact request.
- With `PIPELINE_OFFLINE=1`, the pipeline serves everything from cache and never
  touches the network — a reviewer can reproduce the full run, memos and all,
  **with no API key**. A cache miss (changed input) fails loudly rather than
  silently going live.

Secrets never leave your machine: `.env` is gitignored; only `.env.example`
(a placeholder) is committed.

## Traceability

The rubric asks that a reviewer can spot-check one analysis and trust where its
claims came from. Every memo carries:

- a **Score breakdown** table — why it got the number it got, rule by rule;
- a **Sources** section — every factual claim tied back to the exact source
  (YC long description, a named founder bio, the YC profile) with links.

## Project layout

```
src/investment_pipeline/
  sourcing/     yc.py, yc_company.py, hn.py (retained, see ADR-004), pipeline.py
  analysis/     score.py (rules), llm.py (grounded call), analyze.py
  memo/         render.py, build.py
  cli.py        the `pipeline` command
  models.py     the contracts between stages (Pydantic)
docs/decisions/ ADRs 001–005 — the decision trail
tests/          deterministic-core tests
data/           candidates.json, scored.json, analysis/, raw/, llm_cache/  (caches)
out/memos/      the deliverable memos + ranked index
```

## How this was built (with AI)

The decision trail lives in [`docs/decisions/`](docs/decisions/) — including
**ADR-004**, which records a hypothesis that the *data disproved*: Hacker News
(and then GitHub) were evaluated as traction sources and dropped because they're
empty or noisy for brand-new closed-source startups. `sourcing/hn.py` is kept,
unwired, as evidence of that pivot. Read the ADRs alongside the git history to
see how the scoping decisions were actually made.

## Tests

```bash
pytest -q
```

Covers the deterministic core: scoring rules and bands, YC hit mapping, the HN
domain-match fix, memo rendering, and the cache's offline behaviour.
