---
name: fitment-and-variation-resolution
description: Use when mapping Mopar records to vehicle variations.
version: 1.0.0
author: Hermes Mopar Catalogue Project
license: Project-controlled
metadata:
  project: 2017-mopar-oem-catalogue
  status: validated-before-scale
---

# Fitment and Variation Resolution

## Procedure
1. Preserve source fitment wording and normalized applicability separately.
2. Map through explicit variation/category/leaf relationships, not visual similarity.
3. Represent shared parts with one part identity plus per-variation applicability.
4. Flag ambiguous or contradictory fitment and supersession chains.
5. Keep vehicle-family catalogue candidates distinct from VIN-installed parts.

## Tests
- Source strings survive normalization unchanged.
- Contradictory fitment produces a defect.
- Shared part retains all variation associations.

## Completion Gate
Every record is audited as applicable, ambiguous, not applicable or source-exception with evidence.

## Common Pitfalls
- Treating parser success as completeness.
- Replacing source values with normalized values.
- Repairing defects inside an independent verification stage.
