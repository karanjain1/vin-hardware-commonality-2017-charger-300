# Authoritative 2017 Mopar OEM Catalogue — Chrysler 300C / Dodge Challenger

This directory contains the controlled schema-v3 authoritative catalogue required by the Mopar master instruction. It is separate from, and supersedes for this mission, the partial legacy Charger/300 experiment in `catalog/mopar_catalog.sqlite3`. The `v2/` path is retained for repository continuity; its authoritative database declares `schema_version=3`.

## Exact scope

The authoritative variation definitions are in [`manifests/variation_manifest.json`](manifests/variation_manifest.json):

### 2017 Chrysler 300C

MoparAmerica source model label: **Chrysler 300**; source trim: **C**.

1. C / 3.6L V6 Gas
2. C / 3.6L V6 Flex
3. C / 5.7L V8 Gas

### 2017 Dodge Challenger

1. SXT / 3.6L V6 Gas
2. R/T / 5.7L V8 Gas
3. R/T Scat Pack / 6.4L V8 Gas

These are configured vehicle-family catalogue routes, not VIN-confirmed installed equipment.

## Authoritative and derived artifacts

- **Authoritative database:** `authoritative_catalogue.sqlite3`
- **Schema:** `schema_v2.sql`
- **Variation manifest:** `manifests/variation_manifest.json`
- **Master expected scope:** `manifests/master_expected_scope.json`
- **Original source evidence:** `v2/evidence/source/`
- **Byte-preserved images:** `v2/images/`
- **Derived CSV/JSON exports:** `v2/exports/`
- **Project-local skills:** `skills/`
- **Defect register:** database table `defects` plus `v2/exports/defects.csv`
- **QA reports:** `quality/reports/`
- **Recovery audit:** `quality/RECOVERY_AUDIT.md`

CSV files are reproducible projections. They are not competing master datasets.

## Safe resumable workflow

```bash
python scripts/catalogue_v2.py init
python scripts/catalogue_v2.py discover
python scripts/catalogue_v2.py crawl-categories
python scripts/catalogue_v2.py crawl-diagrams
python scripts/catalogue_v2.py crawl-products
python scripts/catalogue_v2.py acquire-images
python scripts/catalogue_v2.py verify-images
python scripts/catalogue_v2.py export
python scripts/catalogue_auditors.py source
python scripts/catalogue_auditors.py image
python scripts/catalogue_auditors.py fitment
python scripts/catalogue_auditors.py completeness
python scripts/catalogue_v2.py export
python scripts/catalogue_auditors.py integrity
python scripts/catalogue_v2.py export
python scripts/catalogue_reports.py
# Commit and push the clean extraction/integrity checkpoint before Agent 9:
python scripts/catalogue_qa.py final
```

Each source leaf is committed to SQLite transactionally. Existing raw evidence is reused unless `--refresh` is explicitly supplied. `--retry-failed` is for diagnosed and corrected failures; it is not a substitute for root-cause analysis.

Mopar page retrieval is serialized at the source's ten-second crawl delay. CDN image acquisition and independent re-verification may run concurrently.

## Validation

```bash
python -m unittest discover -s tests -p 'test_catalogue_v2.py' -v
python scripts/catalogue_auditors.py all
python scripts/catalogue_qa.py check
```

The tests include parser fixtures and seeded failures for missing rows, false completion, wrong part numbers, broken image paths and wrong image associations.

## Status meaning

The extraction agent can set only extraction-stage states. Downstream verification advances source, image, fitment, completeness and integrity status. Only `AGENT_9_INDEPENDENT_QUALITY_RED_TEAM` may set `QA_PASSED`.

The project is complete only when every expected leaf and batch is `QA_PASSED` or a fully evidenced `BLOCKED_EXTERNAL`, all counts reconcile, all content images have terminal exactness states, all critical/major defects are resolved, derived outputs reproduce, and the final quality report states:

`FINAL STATUS: QA PASSED`

## Source and safety controls

- MoparAmerica is the primary catalogue source.
- Original source strings are preserved; normalized fields are separate.
- Part numbers remain strings and are never inferred from URL slugs.
- Missing displayed numbers use `PART_NUMBER_NOT_DISPLAYED` with source evidence.
- Missing OEM images use `NO_OEM_IMAGE_AVAILABLE` only when source-supported.
- Images are stored as downloaded; no conversion, cropping or recompression occurs.
- Access controls, CAPTCHAs, authentication and rate limits are not bypassed.
- Static site logos and placeholders are not promoted as OEM part images.
