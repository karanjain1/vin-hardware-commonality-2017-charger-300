---
name: catalogue-taxonomy-inventory
description: Use when enumerating the full Mopar catalogue hierarchy.
version: 1.0.0
author: Hermes Mopar Catalogue Project
license: Project-controlled
metadata:
  project: 2017-mopar-oem-catalogue
  status: validated-before-scale
---

# Catalogue Taxonomy Inventory

## Procedure
1. Preserve exact source labels and derive normalized IDs separately.
2. Split route links into category and subcategory source labels without rewriting them.
3. Create stable IDs from variation plus source URL.
4. Enumerate category index leaves, each assembly selector and any single unnumbered diagram.
5. Retain empty, unavailable, shared and variation-specific branches with explicit dispositions.
6. Reconcile repeated discovery and create a source-change defect for unexplained differences.

## Tests
- Every leaf has parent, source URL, variation and status.
- Parent-child cycles and duplicate active IDs fail.
- Removing one seeded leaf makes completeness reconciliation fail.

## Completion Gate
All six route taxonomies reconcile against the Master Expected Scope Manifest with zero unexplained leaves.

## Common Pitfalls
- Treating parser success as completeness.
- Replacing source values with normalized values.
- Repairing defects inside an independent verification stage.
