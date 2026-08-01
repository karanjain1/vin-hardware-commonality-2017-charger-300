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

## Controlled preproduction correction

The first v2 validation crawl was halted after independent Agents 5, 7 and 9 found false-pass paths: duplicate visible callouts could collapse, adjacent product fields could contaminate a row, image byte verification could overclaim association, and final QA could promote nonterminal scopes. Its physical database was preserved as `catalog/v2/checkpoints/pre_red_team_rebuild.sqlite3`; it is historical, not authoritative.

The active database was rebuilt as schema v3 from preserved immutable source evidence after root-cause correction and regression tests. The complete defect history is `catalog/quality/defects/preproduction_red_team_defects.json`.

Repeated current route traversal through two independent renderer URL schemes also established a controlled source change: every one of the six routes exposes exactly two fewer category leaves than at initial resolution (baseline total 1,081; current total 1,069). Baselines remain in the Variation Manifest; `catalog/v2/manifests/route_revalidation.json` controls the active expected scope.
