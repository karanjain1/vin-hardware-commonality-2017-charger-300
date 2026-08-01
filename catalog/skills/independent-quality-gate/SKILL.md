---
name: independent-quality-gate
description: Use when independently accepting or rejecting catalogue batches.
version: 1.1.0
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
1. Run deterministic schema, source, image, fitment, completeness, repository and export-reproducibility tests without repairing or advancing producer audit states.
2. Treat every nonterminal leaf, product source and batch as blocking; never filter these failures before promotion.
3. Resample category, diagram and product source strata for every one of the six variations; missing sample coverage itself fails.
4. Create reproducible defect tickets with severity, owner, evidence, correction and retest.
5. Auto-resolve only `AUTOMATED` `OPEN` defects whose exact check and scope were rerun successfully; never auto-resolve manual or `IN_PROGRESS` defects.
6. Promote only rows already in `INTEGRITY_CHECKED`, guarded by exact eligible-versus-active counts.
7. Withhold QA_PASSED while any critical/major defect or nonterminal batch remains.

## Tests
Seed fixtures for a missing row, wrong image, wrong part number, broken path and false completion; all must fail and produce defects.

## Completion Gate
Only an independent run with zero unresolved critical/major defects may issue `FINAL STATUS: QA PASSED`.

## Common Pitfalls
- Treating parser success as completeness.
- Replacing source values with normalized values.
- Repairing defects inside an independent verification stage.
