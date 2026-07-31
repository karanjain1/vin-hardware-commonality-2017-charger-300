---
name: catalogue-completeness-reconciliation
description: Use when reconciling expected versus captured Mopar scope.
version: 1.0.0
author: Hermes Mopar Catalogue Project
license: Project-controlled
metadata:
  project: 2017-mopar-oem-catalogue
  status: validated-before-scale
---

# Catalogue Completeness Reconciliation

## Procedure
1. Reconcile project, vehicle, variation, category, subcategory, leaf, diagram, page, row, callout, part and image levels.
2. Compare expected/processed/passed/failed/blocked/unexplained counts.
3. Detect pagination and dynamic-content omissions.
4. Require every expected leaf to end QA_PASSED or BLOCKED_EXTERNAL with evidence.
5. Preserve shared applicability; do not remove it from variation totals.

## Tests
- Removing a leaf, row, callout or image association makes reconciliation fail.
- A false-complete zero-row page with source links fails.

## Completion Gate
All unexplained and nonterminal counts equal zero.

## Common Pitfalls
- Treating parser success as completeness.
- Replacing source values with normalized values.
- Repairing defects inside an independent verification stage.
