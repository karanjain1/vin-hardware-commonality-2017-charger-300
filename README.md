# 2017 Charger / Chrysler 300 — ADR-critical interior hardware catalog comparison

This repository/branch contains the public, AI-readable evidence packet for comparing catalogued interior and occupant-protection hardware for:

- `2C3CDXGJ2HH530684` — 2017 Dodge Charger R/T 392 / MoparAmerica R/T Scat Pack 6.4L V8 Gas
- `2C3CCAEG4HH586472` — 2017 Chrysler 300C 3.6L V6 RWD / MoparAmerica C 3.6L V6 Gas

## Start here

- `report/hardware_commonality_report.pdf` — human-readable report with 46 exploded drawings and tables
- `report/hardware_commonality_report.docx` — editable Word version
- `report/hardware_commonality_report.md` — AI-readable narrative and image register
- `extracted/comparison/direct_safety_hardware_common_candidates.csv` — 51 conservative direct-safety common candidates
- `extracted/comparison/adr_relevance_keyword_candidates.csv` — 76 broad ADR-relevance keyword candidates
- `extracted/comparison/common_catalog_parts.csv` — all 106 common catalog candidates
- `extracted/comparison/catalog_parts_deduplicated.csv` — 635 VIN/category candidate rows
- `extracted/mopar/parts.csv` — 1,485 raw diagram-page part rows
- `extracted/mopar/assemblies.csv` — diagram register and source URLs
- `extracted/adr/adr_scope_matrix.csv` — ADR relevance/applicability matrix
- `evidence/mopar/illustrations/` — downloaded public catalog illustrations

## Determination

**CONDITIONAL:** the catalog routes show substantial commonality, including seat tracks/adjusters, frames, brackets/fasteners, belt components, airbag-related hardware and steering components. This is useful architecture/commonality evidence.

It is **not proof** that the exact option-dependent parts are installed on either VIN, and it is not a substitute for ADR test/approval evidence. MoparAmerica accepted the Charger VIN; the Chrysler VIN failed to resolve and its route was inferred from decoded model/trim. Obtain both OEM build sheets/sales codes and VIN-specific dealer/OEM part confirmations before making an installed-configuration claim.

## Source and provenance

MoparAmerica pages are cited by URL in the report and CSV tables. Public catalog pages were read through a read-only rendering proxy because the site presented a Cloudflare challenge to the automated research browser. Images retain their source URLs and SHA-256 metadata.

The user-supplied original email PDF is intentionally excluded from the public repository. Only the requested derived tables and report content are included.

Australian regulatory references use public Federal Register URLs and the verified `Dogeshdawg/vehicle-regulations-corpus` snapshot at commit `b2903c330bdd5ef38248709aed9a77dc64d71bf5`. Exact legal applicability remains conditional on the approval pathway and date basis.

## Third-party material

Vehicle catalog illustrations and part information remain the property of their respective owners and are reproduced here for identification, technical comparison and evidentiary reference. No ownership or endorsement is claimed. Do not assume third-party material is covered by any repository code/data licence.
