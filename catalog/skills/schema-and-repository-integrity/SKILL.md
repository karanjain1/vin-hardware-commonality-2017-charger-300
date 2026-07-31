---
name: schema-and-repository-integrity
description: Use when validating catalogue schema and repository state.
version: 1.0.0
author: Hermes Mopar Catalogue Project
license: Project-controlled
metadata:
  project: 2017-mopar-oem-catalogue
  status: validated-before-scale
---

# Schema and Repository Integrity

## Procedure
1. Enforce IDs, required fields, allowed statuses, UTF-8, paths, URLs and data types.
2. Run SQLite integrity and foreign-key checks.
3. Reject orphan images, missing files, duplicate active IDs and nonexistent references.
4. Verify reruns are idempotent and derived exports reproduce from the master database.
5. Verify Git LFS classification for binary images/database and scan controlled files for credentials.

## Tests
- Seeded orphan image, broken path and duplicate ID each fail.
- Two identical fixture runs produce identical active record counts.

## Completion Gate
All deterministic checks pass and no critical/major integrity defect remains.

## Common Pitfalls
- Treating parser success as completeness.
- Replacing source values with normalized values.
- Repairing defects inside an independent verification stage.
