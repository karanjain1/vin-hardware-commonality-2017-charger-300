---
name: independent-quality-gate
description: Use when independently accepting or rejecting catalogue batches.
version: 1.0.0
author: Hermes Mopar Catalogue Project
license: Project-controlled
metadata:
  project: 2017-mopar-oem-catalogue
  status: validated-before-scale
---

# Independent Quality Gate

## Independence
Quality review does not perform primary extraction and cannot lower acceptance thresholds.

## Procedure
1. Run deterministic schema, source, image, fitment, completeness and repository tests.
2. Resample source records independently with risk-based selection.
3. Create reproducible defect tickets with severity, owner, evidence, correction and retest.
4. Return defects to the owning stage and rerun all affected downstream checks.
5. Withhold QA_PASSED while any critical/major defect or nonterminal batch remains.

## Tests
Seed fixtures for a missing row, wrong image, wrong part number, broken path and false completion; all must fail and produce defects.

## Completion Gate
Only an independent run with zero unresolved critical/major defects may issue `FINAL STATUS: QA PASSED`.

## Common Pitfalls
- Treating parser success as completeness.
- Replacing source values with normalized values.
- Repairing defects inside an independent verification stage.
