---
name: resumable-batch-checkpointing
description: Use when running bounded resumable catalogue batches.
version: 1.0.0
author: Hermes Mopar Catalogue Project
license: Project-controlled
metadata:
  project: 2017-mopar-oem-catalogue
  status: validated-before-scale
---

# Resumable Batch Checkpointing

## Procedure
1. Assign stable batch ID, exact scope, owner, input, output paths and completion test.
2. Write staging results transactionally; merge only after handoff validation.
3. Checkpoint after each verified leaf and preserve failure/retry history.
4. Resume from the last terminal checkpoint without duplicating active records.
5. Record source scope and extractor/skill/schema versions.

## Tests
- Kill a fixture run mid-batch; resume must match an uninterrupted run.
- Retry must not increase active record counts.

## Completion Gate
No partial output is promoted and every batch has an auditable terminal or resumable state.

## Common Pitfalls
- Treating parser success as completeness.
- Replacing source values with normalized values.
- Repairing defects inside an independent verification stage.
