---
name: mopar-source-navigation
description: Use when traversing configured MoparAmerica catalogue routes.
version: 1.0.0
author: Hermes Mopar Catalogue Project
license: Project-controlled
metadata:
  project: 2017-mopar-oem-catalogue
  status: validated-before-scale
---

# Mopar Source Navigation

## Scope
Navigate only evidence-supported configured routes in `catalog/manifests/variation_manifest.json`. Preserve the original Mopar URL when a read-only renderer is used.

## Procedure
1. Confirm year, make, model, trim and engine against the variation manifest.
2. Fetch the configured route and require the expected `Select Parts Category` title and at least 20 route-bound category links.
3. Serialize Mopar page retrieval at the declared 10-second crawl delay. Treat short HTTP-200 interstitials as retryable transport blocks.
4. Record selector state, source URL, renderer URL, final URL, HTTP status, access time and literal/canonical hashes.
5. Detect pagination, assembly selectors, tabs and single-diagram `#0` pages before classifying content.
6. Never classify zero records as empty until route state and page structure pass.

## Tests
- Wrong year/model route must fail.
- A short interstitial must become `BLOCKED_RETRYABLE`, not `EMPTY`.
- Repeated traversal must produce the same normalized category set or a documented source-change defect.

## Completion Gate
Navigation passes only when the configured route identity and terminal retrieval state are machine-readable and reproducible.

## Common Pitfalls
- Treating parser success as completeness.
- Replacing source values with normalized values.
- Repairing defects inside an independent verification stage.
