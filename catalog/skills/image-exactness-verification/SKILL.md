---
name: image-exactness-verification
description: Use when independently verifying stored Mopar image exactness.
version: 1.1.0
author: Hermes Mopar Catalogue Project
license: Project-controlled
metadata:
  project: 2017-mopar-oem-catalogue
  status: validated-before-scale
---

# Image Exactness Verification

## Procedure
1. Verify record-to-source-page and record-to-image association independently of acquisition, using the immutable source-page hash and exact occurrence locator.
2. Keep byte verification and association verification separate: a byte-identical wrong association still fails.
3. Re-fetch final image URL and compare literal SHA-256 where stable; independently reread the local file before accepting it.
4. Fully decode local bytes; record MIME, format, size, dimensions and decoded pixel hash.
5. Recognize legitimately shared diagrams through explicit many-to-many occurrence associations.
6. Accept `NO_OEM_IMAGE_AVAILABLE` only from a structurally complete product page. Partial renderer output is `IMAGE_ENUMERATION_INCOMPLETE`, never no-image evidence.
7. Create a defect for changed, broken, wrong, placeholder or invalid images; never silently repair.

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
