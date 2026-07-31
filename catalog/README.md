# Searchable MoparAmerica catalogue — 2017 Charger and Chrysler 300

This directory is a resumable, provenance-controlled catalogue of the public MoparAmerica OEM parts pages for:

- 2017 Dodge Charger — every validated trim/engine catalogue route found in `config/variants_seed.json`.
- 2017 Chrysler 300/300C — every validated trim/engine catalogue route found in the same file.

## Current completeness

Read `exports/status.json` and `exports/coverage.csv`. A route or category is complete only when `crawl_state=complete`. The crawler is resumable; partial data is never labelled complete.

The earlier case evidence was **not** a complete all-variant catalogue. It covered selected VIN routes, ADR-relevant categories and braking/structure supplements. This new database is the canonical all-variant catalogue project.

## Search locally

```bash
# Show coverage and counts
python scripts/mopar_catalog.py status

# Full-text part/assembly search
python scripts/mopar_catalog.py search 'master cylinder'
python scripts/mopar_catalog.py search '68043494AT'
python scripts/mopar_catalog.py search 'front floor pan' --model Charger
python scripts/mopar_catalog.py search 'seat belt' --model Chrysler --trim C
```

The search backend is SQLite FTS5 in `mopar_catalog.sqlite3`. Search results retain model, trim, engine, category, assembly title, part number, description and original MoparAmerica evidence URL.

## Data products

- `mopar_catalog.sqlite3` — normalized SQLite database and FTS5 search index.
- `exports/variants.csv` — candidate and validated vehicle catalogue routes.
- `exports/coverage.csv` — category-by-variant crawl state and counts.
- `exports/parts.csv` — deduplicated part/product records.
- `exports/part_offerings.csv` — part availability by model/trim/engine/category.
- `exports/assemblies.csv` — exploded assembly image metadata, source URLs and SHA-256 hashes.
- `exports/status.json` — machine-readable completeness statement.
- `images/<hash-prefix>/<sha256>.<ext>` — hash-deduplicated original catalogue illustrations.
- `schema.sql` — normalized data model.
- `config/variants_seed.json` — auditable variant candidates and crawl policy.

Raw renderer responses are retained locally under `catalog/raw/` for recovery and audit, but are excluded from Git because they are large retrieval intermediates. Original MoparAmerica URLs, retrieval hashes and normalized outputs are preserved in the database/exports.

## Rebuild/update

```bash
python scripts/mopar_catalog.py init
python scripts/mopar_catalog.py discover
python scripts/mopar_catalog.py crawl
python scripts/mopar_catalog.py rebuild-search
python scripts/mopar_catalog.py export
```

`discover` validates candidate vehicle routes and enumerates every category link exposed by each route. `crawl` retrieves every pending category, captures all listed part numbers and product URLs, enumerates every exploded assembly image, downloads original illustrations and deduplicates them by SHA-256.

The crawler obeys the MoparAmerica public `robots.txt` 10-second crawl delay. When direct access is blocked, it uses the Jina text renderer as retrieval transport while retaining the original MoparAmerica URL as the evidence source.

## Evidence limits

- Records are **vehicle-family catalogue candidates**, not proof of factory installation on a particular VIN.
- Alternative parts, option codes, colours, production breaks and supersessions remain separate where the catalogue presents them separately.
- Exact part-number identity and shared diagram geometry do not establish engineering equivalence or ADR compliance.
- Complete callout-to-part enrichment is a separate slower phase; category-level part offerings and every assembly image are the first completeness target.

## GitHub storage

Catalogue images and the SQLite database are tracked through Git LFS. CSV/JSON metadata and the crawler remain ordinary Git objects, allowing review and search even when LFS objects are not downloaded.
