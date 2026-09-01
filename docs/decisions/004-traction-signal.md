# Decision 004 — Traction / Momentum Signal

## Context

The thesis (001) and scoring (Stage 2) want a signal for external validation or
traction. ADR-002 proposed Hacker News as the enrichment source. Building it
against real data changed the decision, so this record supersedes the HN part of
ADR-002.

## What we tried, and what the data showed

1. **Hacker News, matched by company name.**
   Produced confident false positives: "Locke" matched "account gets locked",
   "Squid" matched the squid proxy, "Lance" matched Ian Lance Taylor. Unusable.

2. **Hacker News, matched by company website domain.**
   Correct and precise (verified: posthog.com → its real Show HN, 684 points).
   But it returned nothing for our cohort: brand-new YC companies (many Summer
   2026) have not posted a Show HN. Correct, but empty.

3. **GitHub repository activity.**
   Probed before building. Same name-collision problem, worse: "Prodigal" →
   a bioinformatics tool (553★), "Concourse" → the CI/CD system (7,894★).
   Homepages are mostly empty, so precise domain-matching would leave near-zero
   coverage. Seed-stage fintech companies are closed-source, so GitHub has no
   reliable traction signal for them.

## Conclusion

For seed-stage, closed-source B2B/fintech startups there is **no reliable public
traction signal** (HN, GitHub, etc.). Continuing to add scraped sources would be
the "12-source layer where each returns 2 garbage results" anti-pattern.

## Decision

- **Drop scraped external traction** from the default pipeline.
- Use YC's own structured, traceable fields as a **momentum** signal instead:
  - `top_company` — YC's curated designation (strong; rare for new companies).
  - `isHiring` — actively hiring, a capital/momentum proxy (varies across the
    cohort, so it differentiates).
- Rebalance the score: the 15 traction points become 10 momentum points, and
  Workflow ownership rises from 25 to 30 (the core thesis lever).

## Status of the HN module

`src/investment_pipeline/sourcing/hn.py` is retained but not wired into the
default pipeline. It is kept as a working, correct implementation of the
domain-matched approach and as the record of why HN was set aside. It will fire
correctly for cohorts that do have HN presence (e.g. older, launch-driven
developer tools).

## What would change this decision

- Sourcing a cohort with real public traction (dev tools, open-source) — then
  re-enable `hn.py` / add GitHub.
- Access to a private data source (funding, headcount growth) would give a
  stronger momentum signal than `isHiring`.
