---
name: oem-part-record-extraction
description: Use when extracting every displayed Mopar part row/callout.
version: 1.2.0
author: Hermes Mopar Catalogue Project
license: Project-controlled
metadata:
  project: 2017-mopar-oem-catalogue
  status: validated-before-scale
---

# OEM Part Record Extraction

## Procedure
1. Parse numbered parts tables, diagram callout summaries, accessory result grids, bounded markerless product-card lists and `Related Parts` sections separately.
2. Preserve source part number, name, description, quantity, fitment, supersession and punctuation as strings.
3. Derive normalized fields separately; never infer an absent part number.
4. Associate every visible callout with all displayed alternatives by product URL.
5. Materialize one immutable `visible_source_rows` occurrence per displayed table row and per displayed callout occurrence; repeated identical callouts remain separate through an occurrence ordinal.
6. Bound each detailed-card parse at the next card marker. Never let an adjacent product supply a name or part number.
7. Emit `PART_NUMBER_NOT_DISPLAYED` only when the exact bounded source row lacks a displayed number and retain the snippet hash.
8. Capture product-page URLs and make the source-row key the idempotent logical key.

## Tests
- Leading zero, suffix and hyphen fixtures round-trip unchanged.
- Wrong callout association fails.
- Missing number becomes the explicit exception, never a URL guess.
- Seeded missing visible row fails completeness.
- Accessory grids, markerless bounded cards and Related Parts fixtures independently reconcile their displayed row denominators.
- `http://www.moparamerica.com` source links remain literal observations while product-source identity is canonical HTTPS.

## Completion Gate
Every visible row/callout has one exact record or a source-supported exception.

## Common Pitfalls
- Treating parser success as completeness.
- Replacing source values with normalized values.
- Repairing defects inside an independent verification stage.
