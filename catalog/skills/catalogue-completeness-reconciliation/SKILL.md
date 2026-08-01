---
name: catalogue-completeness-reconciliation
description: Use when reconciling expected versus captured Mopar scope.
version: 1.1.0
author: Hermes Mopar Catalogue Project
license: Project-controlled
metadata:
  project: 2017-mopar-oem-catalogue
  status: validated-before-scale
---

# Catalogue Completeness Reconciliation

## Procedure
1. Reconcile project, vehicle, variation, category, subcategory, leaf, diagram, page, row occurrence, callout occurrence, part record and image occurrence levels.
2. Compute independent structural counters directly from immutable source snapshots; never reuse extraction counters as the expected denominator.
3. Compare expected/processed/passed/failed/blocked/unexplained counts and require source-row/record bijection.
4. Detect pagination, dynamic-content omissions, adjacent-card contamination and duplicate-row collapse.
5. Require every expected leaf to end QA_PASSED or BLOCKED_EXTERNAL with evidence.
6. Preserve shared applicability and repeated source occurrences; do not deduplicate them out of variation totals.

## Tests
- Removing a leaf, row, callout or image association makes reconciliation fail.
- A false-complete zero-row page with source links fails.

## Completion Gate
All unexplained and nonterminal counts equal zero.

## Common Pitfalls
- Treating parser success as completeness.
- Replacing source values with normalized values.
- Repairing defects inside an independent verification stage.
