---
name: image-exactness-verification
description: Use when independently verifying stored Mopar image exactness.
version: 1.0.0
author: Hermes Mopar Catalogue Project
license: Project-controlled
metadata:
  project: 2017-mopar-oem-catalogue
  status: validated-before-scale
---

# Image Exactness Verification

## Procedure
1. Verify record-to-source-page and record-to-image association independently of acquisition.
2. Re-fetch final image URL and compare literal SHA-256 where stable.
3. Fully decode local bytes; record MIME, size and dimensions.
4. Recognize legitimately shared diagrams by source association.
5. Create a defect for changed, broken, wrong, placeholder or invalid images; never silently repair.

## Tests
- One-byte corruption fails.
- Wrong record/image pairing fails despite a valid hash.
- Shared source image passes only with explicit multiple associations.

## Completion Gate
Terminal states are byte/content exact or source-supported no-image; all others block QA.

## Common Pitfalls
- Treating parser success as completeness.
- Replacing source values with normalized values.
- Repairing defects inside an independent verification stage.
