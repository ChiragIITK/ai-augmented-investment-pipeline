# Decision 005 — Founder Data Source (reliable second source)

## Context

Scoring wants a real Team signal, and the Stage 3 analysis needs grounded
founder backgrounds. The Algolia index (ADR-002 / yc.py) has firmographics but
**no founders**. HN and GitHub were evaluated as enrichment sources and dropped
(ADR-004): empty or noisy for brand-new closed-source startups. We wanted one
*more* source, but a reliable one — not another scraped social feed.

## Decision

Use the **YC company detail page** (`/companies/<slug>`) as the second source.

Each page ships an Inertia.js `data-page` payload (HTML-entity-escaped JSON)
containing a `founders` array with `full_name`, `title`, `founder_bio`, and
`linkedin_url`. We fetch the page, unescape and parse that payload, and attach
structured `Founder` records to each candidate.

## Why this source

- **100% coverage** — every candidate is, by construction, a YC company.
- **No false-match risk** — it is the company's own page, keyed by slug, unlike
  name-searching HN/GitHub.
- **Traceable** — bios and LinkedIn URLs are real, citable claims for the memo.
- **Dual use** — upgrades the Team score *and* grounds the Stage 3 LLM analysis.

## Impact on scoring

The Team rule now reads founder bios for pedigree (prior employers, PhD),
technical depth (CTO/engineer/ML), and prior founder experience, instead of
keyword-matching the company blurb. Example: Accend and Tesora reach 10/10 Team
with reasons that name the founders and their backgrounds.

## Cost / limits

One extra HTTP GET per candidate (~20 per run), cached under data/raw/yc/ so
subsequent runs and offline replay need no network. Full run to fetch 20 pages
is ~11s.

## What would change this decision

- If YC changes the page structure (the `data-page` payload), the parser needs
  updating; failures degrade gracefully to "no founder data" rather than
  crashing sourcing.
- A structured founder API (if one existed) would remove the HTML parsing.
