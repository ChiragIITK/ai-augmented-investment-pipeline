# Decision 006 — Seed Inputs (topic / batch / URLs)

## Context

The brief says the seed input can be "a topic query, a list of URLs, or a feed
like the YC W25 batch." The first version supported only a topic query.

## Decision

Support all three seed types, all resolving through Y Combinator — the one
source we went deep on (ADR-002). Only the discovery step differs; every seed
produces the same `data/candidates.json`, so stages 2–4 are unchanged.

| Seed | Flag | How it's discovered |
|---|---|---|
| Topic | `--topic "AI agents for Fintech"` | YC Algolia index, text query |
| Batch feed | `--batch "Winter 2025"` | YC Algolia index, `facetFilters=["batch:<batch>"]` — a whole-batch feed |
| URL list | `--urls <a,b>` / `--urls-file f` | YC company pages, one per URL |

## Why the URL path is limited to YC company URLs

A "list of URLs" could mean arbitrary company websites. Scraping those would
mean a generic HTML/heuristic extractor per unknown site layout — low quality,
high maintenance, and exactly the "12-source layer where each returns 2 garbage
results" anti-pattern the brief warns against. Instead the URL seed accepts YC
company URLs and reuses the structured `data-page` payload we already parse, so
a single URL yields firmographics *and* founders with the same fidelity as the
other two paths. Non-YC URLs are skipped rather than half-scraped.

## Notes

- Batch and topic can be combined in the library (`discover(topic, batch=...)`),
  e.g. a topic within a batch; the CLI keeps them mutually exclusive for
  simplicity.
- URL-seeded candidates carry a YC batch signal but not the Algolia-only
  `launched_at` / `isHiring` fields, so their freshness/momentum scores fall back
  gracefully — the scoring rules already handle missing signals.

## What would change this decision

- A need to source outside YC (Product Hunt, a press feed) would add a new
  discovery module behind the same `source()` seam, still writing candidates.json.
