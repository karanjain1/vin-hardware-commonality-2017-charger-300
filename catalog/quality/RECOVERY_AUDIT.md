# Recovery Audit — 2017 Chrysler 300C / Dodge Challenger Mopar catalogue

**Audit time:** 2026-08-01T09:23:28+10:00  
**Starting commit:** `7272dc453d2fcc524ea8b77e524c57afe0259d4f`  
**Working branch:** `catalogue/2017-chrysler300c-challenger-master`

## Controlling finding

The repository contains valuable MoparAmerica source evidence and verified original image bytes, but its only searchable catalogue database is a partial, conflicting Charger/Chrysler-300 all-route experiment. It is not authoritative for the new exact-six-variation Chrysler 300C/Challenger mission.

The legacy database and images are preserved in place. They will not be deleted or silently promoted. Reuse requires record-level source reassociation and independent verification.

## Legacy snapshot

| Item | Count |
|---|---:|
| Valid legacy routes | 19 |
| Route/category combinations | 3,389 |
| Complete | 303 |
| Pending | 3,081 |
| Error | 5 |
| Unique parts | 1,549 |
| Offerings | 3,000 |
| Assembly rows | 513 |
| Unique stored images | 287 |
| Callout rows | 0 |
| FTS rows | 103 |

## Reusable evidence

- Existing selected-category Challenger source pages establish working configured routes for SXT 3.6L, R/T 5.7L and R/T Scat Pack 6.4L.
- Assembly-specific raw pages under `evidence/mopar/mvsa_44114_research/` are suitable parser fixtures.
- The 287 legacy image files have previously passed source-byte checks, but their scope associations require revalidation.
- Existing Git LFS configuration is reusable.

## Defects preventing promotion

1. Wrong/conflicting legacy vehicle scope.
2. False-complete zero-row category states.
3. Missing product and illustration-derived images.
4. No comprehensive callout capture.
5. Stale FTS projection.
6. Insufficient status, defect, batch and independent-QA controls.
7. Raw text hashes do not distinguish literal bytes from canonical LF text.
8. Published state and local partial state differ.

The machine-readable controlling audit is `catalog/quality/recovery_audit.json`.
