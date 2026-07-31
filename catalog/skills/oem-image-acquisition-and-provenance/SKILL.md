---
name: oem-image-acquisition-and-provenance
description: Use when acquiring Mopar OEM images and diagrams.
version: 1.0.0
author: Hermes Mopar Catalogue Project
license: Project-controlled
metadata:
  project: 2017-mopar-oem-catalogue
  status: validated-before-scale
---

# OEM Image Acquisition and Provenance

## Procedure
1. Enumerate full diagrams, illustration-derived thumbnails and product images from each source record.
2. Reject static logos, loaders, HTML, JSON, zero-byte files and unavailable placeholders as images.
3. Download original bytes without conversion or recompression.
4. Store by SHA-256 under deterministic hash paths and record source/final URL, MIME, bytes, width and height.
5. Associate shared files to every applicable record without duplicating bytes.
6. Emit `NO_OEM_IMAGE_AVAILABLE` only with source evidence.

## Tests
- HTML disguised as PNG fails.
- Placeholder logo is classified, not promoted.
- Same bytes from two records produce one file and two associations.

## Completion Gate
Every image-bearing source item has a valid file/provenance row or supported no-image disposition.

## Common Pitfalls
- Treating parser success as completeness.
- Replacing source values with normalized values.
- Repairing defects inside an independent verification stage.
