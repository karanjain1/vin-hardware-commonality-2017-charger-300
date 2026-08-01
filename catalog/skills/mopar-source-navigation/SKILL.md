---
name: mopar-source-navigation
description: Use when traversing configured MoparAmerica catalogue routes.
version: 1.2.0
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
2. Fetch the configured route and require the expected `Select Parts Category` title plus an exact route-bound category set reconciled by two independent renderer URL schemes.
3. Preserve baseline category counts and, when the source changes, record a dated route-revalidation manifest instead of silently changing history.
4. Serialize Mopar page retrieval at the declared 10-second crawl delay. Treat short HTTP-200 interstitials as retryable transport blocks.
5. Prefer Jina's inner `http://` route for catalogue pages; for product details prefer inner `https://` and use `X-No-Cache: true` when a cached renderer omits the product structure/gallery.
6. If a catalogue response has the correct title but only route-navigation content, retry inner HTTPS with the exact header set `Accept: text/plain`, `X-No-Cache: true`, and `X-Engine: browser`. Record the engine and no-cache state in leaf evidence and mark the snapshot structure status `LEAF_STRUCTURE_VALIDATED_BROWSER_ENGINE`; do not silently treat this as an ordinary fetch.
7. Record selector state, source URL, renderer URL, final URL, HTTP status, access time and literal/canonical hashes.
8. Detect pagination, assembly selectors, source-displayed `no image N. Title` assembly links, tabs and single-diagram `#0` pages before classifying content. A no-image selector creates a diagram reference but never a thumbnail observation.
9. Never classify zero records as empty until route state and page structure pass.

## Tests
- Wrong year/model route must fail.
- A short interstitial must become `BLOCKED_RETRYABLE`, not `EMPTY`.
- Repeated traversal must produce the same normalized category set or a documented source-change defect.
- A route-navigation-only category response must remain incomplete until the explicit browser-engine fallback returns full structure.
- Source-displayed no-image selectors must reconcile the complete assembly-reference set without creating image observations.

## Completion Gate
Navigation passes only when the configured route identity and terminal retrieval state are machine-readable and reproducible.

## Common Pitfalls
- Treating parser success as completeness.
- Replacing source values with normalized values.
- Repairing defects inside an independent verification stage.
