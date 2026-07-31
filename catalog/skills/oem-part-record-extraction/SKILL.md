---
name: oem-part-record-extraction
description: Use when extracting every displayed Mopar part row/callout.
version: 1.0.0
author: Hermes Mopar Catalogue Project
license: Project-controlled
metadata:
  project: 2017-mopar-oem-catalogue
  status: validated-before-scale
---

# OEM Part Record Extraction

## Procedure
1. Parse diagram callout summaries and detailed product cards separately.
2. Preserve source part number, name, description, quantity, fitment, supersession and punctuation as strings.
3. Derive normalized fields separately; never infer an absent part number.
4. Associate every visible callout with all displayed alternatives by product URL.
5. Emit `PART_NUMBER_NOT_DISPLAYED` only when the source row lacks a displayed number and retain evidence.
6. Capture product-page URLs and prevent reruns from multiplying records.

## Tests
- Leading zero, suffix and hyphen fixtures round-trip unchanged.
- Wrong callout association fails.
- Missing number becomes the explicit exception, never a URL guess.
- Seeded missing visible row fails completeness.

## Completion Gate
Every visible row/callout has one exact record or a source-supported exception.

## Common Pitfalls
- Treating parser success as completeness.
- Replacing source values with normalized values.
- Repairing defects inside an independent verification stage.
