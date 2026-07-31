# Image-Only ADR Similarity Screen — Mixed 2017 Challenger, Charger and Chrysler 300 Catalog Drawings

**Date:** 2026-07-31

## Decision rule

This pass uses visible image geometry only. Part numbers, descriptions, catalog applicability, dimensions, materials, fitment, supersession and compliance evidence were excluded from the similarity decision. Models, categories and ADR labels were applied only after pixel-only comparison so that the visible result could be routed to a component class.

**Result:** 9 of 19 screened ADR rows receive a user-defined image-similarity pass. This is not an ADR compliance pass.

## Image-similarity pass list

| ADR | Subject | Image-only result | Visible basis |
|---|---|---|---|
| 3/03 | Seats and Seat Anchorages | IMAGE-SIMILARITY PASS | Direct seat frame, track/adjuster and seat-back structures are highly similar or similar with visible differences. |
| 4/05 | Seatbelts | IMAGE-SIMILARITY PASS | Direct restraint assemblies are near-identical in the strongest mixed-model pair. |
| 10/02 | Steering Column | IMAGE-SIMILARITY PASS | Steering column geometry is highly similar and steering-wheel/airbag interfaces are visibly similar. |
| 11/00 | Internal Sun Visors | IMAGE-SIMILARITY PASS | The roof-liner/visor attachment architecture is similar with visible differences. |
| 21/00 | Instrument Panel | IMAGE-SIMILARITY PASS | Full dashboard shells show similar visible architecture with substantial local differences. |
| 22/00 | Head Restraints | IMAGE-SIMILARITY PASS | Head restraints, guides and seat-back families are visibly similar with configuration differences. |
| 42/04 | General Safety Requirements | IMAGE-SIMILARITY PASS | Several directly depicted interior assemblies show similar visible geometry across mixed models. |
| 69/00 | Full Frontal Impact Occupant Protection | IMAGE-SIMILARITY PASS — DEPICTED HARDWARE ONLY | Multiple frontal-restraint hardware classes are highly similar or visibly similar; no crash-performance inference is made. |
| 73/00 | Offset Frontal Impact Occupant Protection | IMAGE-SIMILARITY PASS — DEPICTED HARDWARE ONLY | Multiple frontal-restraint hardware classes are highly similar or visibly similar; occupant-cell/crash performance is not addressed. |

## Full 19-row image-only matrix

| ADR | Subject | Outcome | Visual classes | Image-only basis |
|---|---|---|---|---|
| 2/01 | Side Door Latches and Hinges | INSUFFICIENT / NO IMAGE-ONLY PASS | front-door | Direct latch/hinge geometry is not comparably shown; only a small lock-cylinder component family looks similar. |
| 3/03 | Seats and Seat Anchorages | IMAGE-SIMILARITY PASS | front-seat-adjusters | rear-seat-adjusters | Direct seat frame, track/adjuster and seat-back structures are highly similar or similar with visible differences. |
| 4/05 | Seatbelts | IMAGE-SIMILARITY PASS | seat-belts | Direct restraint assemblies are near-identical in the strongest mixed-model pair. |
| 5/05 | Anchorages for Seatbelts | PARTIAL / NO IMAGE-ONLY PASS | seat-belts | front-seat-adjusters | Belts and seat frames look similar, but the vehicle structural anchorage points are not comparably exposed. |
| 8/01 | Safety Glazing Material | INSUFFICIENT COMPARABLE IMAGE | none | No comparable glazing image pair was captured. |
| 10/02 | Steering Column | IMAGE-SIMILARITY PASS | steering-column | steering-wheel | air-bags | Steering column geometry is highly similar and steering-wheel/airbag interfaces are visibly similar. |
| 11/00 | Internal Sun Visors | IMAGE-SIMILARITY PASS | headliners-visors | The roof-liner/visor attachment architecture is similar with visible differences. |
| 14/02 | Rear Vision Mirrors | INSUFFICIENT COMPARABLE IMAGE | none | No comparable mirror assembly pair was captured. |
| 18/03 | Instrumentation | INSUFFICIENT / NO IMAGE-ONLY PASS | instrument-panel | Dashboard shells are comparable, but direct cluster/tell-tale geometry is not comparably depicted. |
| 21/00 | Instrument Panel | IMAGE-SIMILARITY PASS | instrument-panel | Full dashboard shells show similar visible architecture with substantial local differences. |
| 22/00 | Head Restraints | IMAGE-SIMILARITY PASS | rear-seats-second-row | front-seat-adjusters | Head restraints, guides and seat-back families are visibly similar with configuration differences. |
| 25/02 | Anti-Theft Lock | INSUFFICIENT / NO IMAGE-ONLY PASS | steering-column | instrument-panel | The direct steering/ignition lock or immobilizer mechanism is not visibly isolated for comparison. |
| 29/00 | Side Door Strength | VISUALLY DIFFERENT / NO IMAGE-ONLY PASS | front-door | aperture-pillars | floor-pans | Door/body structural views show major two-door/four-door geometry and segmentation differences. |
| 34/02 | Child Restraint Anchorages and Child Restraint Anchor Fittings | INSUFFICIENT / NO IMAGE-ONLY PASS | rear-seats-second-row | rear-seat-adjusters | Rear-seat architecture looks similar, but child-restraint anchors are not visibly isolated or comparable. |
| 42/04 | General Safety Requirements | IMAGE-SIMILARITY PASS | instrument-panel | steering-wheel | seats | headliners-visors | Several directly depicted interior assemblies show similar visible geometry across mixed models. |
| 69/00 | Full Frontal Impact Occupant Protection | IMAGE-SIMILARITY PASS — DEPICTED HARDWARE ONLY | air-bags | seat-belts | front-seat-adjusters | steering-column | steering-wheel | Multiple frontal-restraint hardware classes are highly similar or visibly similar; no crash-performance inference is made. |
| 72/00 | Dynamic Side Impact Occupant Protection | PARTIAL / NO IMAGE-ONLY PASS | air-bags | seat-belts | front-door | aperture-pillars | Belts look similar, but direct side-airbag and side-structure coverage is insufficient and body structures visibly differ. |
| 73/00 | Offset Frontal Impact Occupant Protection | IMAGE-SIMILARITY PASS — DEPICTED HARDWARE ONLY | air-bags | seat-belts | front-seat-adjusters | steering-column | steering-wheel | Multiple frontal-restraint hardware classes are highly similar or visibly similar; occupant-cell/crash performance is not addressed. |
| 85/00 | Pole Side Impact Performance | INSUFFICIENT / NO IMAGE-ONLY PASS | air-bags | front-door | aperture-pillars | Direct pole-side restraint/structure coverage is insufficient; body-side structures visibly differ. Probably not mandatory for these 2017 vehicles, but applicability is separate from this image screen. |

## Category-level visual review

### air-bags
- **Visual grade:** HIGHLY SIMILAR (High confidence)
- **Compared images:** `evidence/mopar/illustrations/2C3CCAEG4HH586472/air-bags__assembly-03.png` versus `evidence/mopar/illustrations/2C3CDXGJ2HH530684/air-bags__assembly-03.png`
- **Pixel metrics:** score 0.853304; foreground Dice 0.699183; pHash distance 6
- **Visible commonalities:** Passenger-airbag module, steering-wheel airbag family and lower bolster occupy the same three-part exploded layout.
- **Visible differences/limits:** Steering-wheel hub/spoke detail differs; the drawing does not show calibration, sensors or deployment behaviour.

### front-seat-adjusters
- **Visual grade:** SIMILAR WITH VISIBLE DIFFERENCES (High confidence)
- **Compared images:** `evidence/mopar/illustrations/2C3CCAEG4HH586472/front-seat-adjusters__assembly-03.png` versus `evidence/mopar/illustrations/2C3CDXGJ2HH530684/front-seat-adjusters__assembly-02.png`
- **Pixel metrics:** score 0.758966; foreground Dice 0.581176; pHash distance 10
- **Visible commonalities:** Both drawings show matching seat-back frame, cushion/track frame, side shield and floor-foot arrangement.
- **Visible differences/limits:** Spring field, side hardware and small attachment layout differ.

### rear-seat-adjusters
- **Visual grade:** HIGHLY SIMILAR (High confidence)
- **Compared images:** `evidence/mopar/illustrations/2C3CCAEG4HH586472/rear-seat-adjusters__assembly-01.png` versus `evidence/mopar/illustrations/2C3CDXGJ2HH530684/rear-seat-adjusters__assembly-01.png`
- **Pixel metrics:** score 0.664822; foreground Dice 0.42093; pHash distance 16
- **Visible commonalities:** Twin seat-back frames, perforated panels, central latch/bracket cluster and peripheral hardware have closely corresponding geometry.
- **Visible differences/limits:** Callout numbering and several small peripheral pieces differ.

### rear-seats-second-row
- **Visual grade:** SIMILAR WITH VISIBLE DIFFERENCES (Medium confidence)
- **Compared images:** `evidence/mopar/illustrations/2C3CCAEG4HH586472/rear-seats-second-row__assembly-07.png` versus `evidence/mopar/illustrations/2C3CDXGJ2HH530684/rear-seats-second-row__assembly-01.png`
- **Pixel metrics:** score 0.627052; foreground Dice 0.350828; pHash distance 18
- **Visible commonalities:** Both show split rear seat-backs, head restraints, side bolsters, cushions and lower trim in a comparable exploded arrangement.
- **Visible differences/limits:** Backrest split/configuration, cushion segmentation and accessory layout differ; child anchors are not visibly isolated.

### seat-belts
- **Visual grade:** HIGHLY SIMILAR (Very high confidence)
- **Compared images:** `evidence/mopar/expanded_adrs/illustrations/Challenger/seat-belts/assembly-02.png` versus `evidence/mopar/illustrations/2C3CDXGJ2HH530684/seat-belts__assembly-02.png`
- **Pixel metrics:** score 1.0; foreground Dice 1.0; pHash distance 0
- **Visible commonalities:** The best pair is visually indistinguishable after pixel normalization; webbing paths, retractors, buckles and callout placement coincide.
- **Visible differences/limits:** Image identity does not prove fitted identity, webbing specification, pretensioner behaviour or anchorage strength.

### steering-column
- **Visual grade:** HIGHLY SIMILAR (High confidence)
- **Compared images:** `evidence/mopar/illustrations/2C3CCAEG4HH586472/steering-column__assembly-01.png` versus `evidence/mopar/illustrations/2C3CDXGJ2HH530684/steering-column__assembly-01.png`
- **Pixel metrics:** score 0.58138; foreground Dice 0.326957; pHash distance 22
- **Visible commonalities:** Angled column shaft, upper housing, mounting bracket, coupling and fastener locations closely correspond.
- **Visible differences/limits:** One drawing includes an additional large shroud/module and callout layout differs.

### steering-wheel
- **Visual grade:** SIMILAR WITH VISIBLE DIFFERENCES (High confidence)
- **Compared images:** `evidence/mopar/expanded_adrs/illustrations/Challenger/steering-wheel/assembly-01.png` versus `evidence/mopar/illustrations/2C3CCAEG4HH586472/steering-wheel__assembly-01.png`
- **Pixel metrics:** score 0.641131; foreground Dice 0.37144; pHash distance 16
- **Visible commonalities:** Both show a round three-spoke wheel, central airbag/hub interface, side switch/trim modules and lower spoke trim.
- **Visible differences/limits:** Spoke trim, hub detail and peripheral module shapes differ.

### headliners-visors
- **Visual grade:** SIMILAR WITH VISIBLE DIFFERENCES (Medium confidence)
- **Compared images:** `evidence/mopar/expanded_adrs/illustrations/Challenger/headliners-visors/assembly-01.png` versus `evidence/mopar/expanded_adrs/illustrations/Charger/headliners-visors/assembly-01.png`
- **Pixel metrics:** score 0.568377; foreground Dice 0.41511; pHash distance 28
- **Visible commonalities:** Both show a large roof-liner panel with front visor/console attachment groups and perimeter fasteners.
- **Visible differences/limits:** Roof openings, panel contour and quantity/location of smaller attachments differ; visor geometry is small in the source view.

### instrument-panel
- **Visual grade:** SIMILAR WITH VISIBLE DIFFERENCES (Medium confidence)
- **Compared images:** `evidence/mopar/illustrations/2C3CCAEG4HH586472/instrument-panel__assembly-01.png` versus `evidence/mopar/illustrations/2C3CDXGJ2HH530684/instrument-panel__assembly-01.png`
- **Pixel metrics:** score 0.554849; foreground Dice 0.33003; pHash distance 26
- **Visible commonalities:** Both show a full-width dashboard shell with instrument binnacle, centre stack, vent groups, glove-box region and lower trim.
- **Visible differences/limits:** Main shell contour, centre-stack shape, component count and callout arrangement visibly differ.

### front-door
- **Visual grade:** GENERIC ONLY (Medium confidence)
- **Compared images:** `evidence/mopar/door_variants/illustrations/Challenger_R-T_5.7L/assembly-03.png` versus `evidence/mopar/door_variants/illustrations/Charger_R-T_5.7L/assembly-03.png`
- **Pixel metrics:** score 0.703398; foreground Dice 0.389942; pHash distance 10
- **Visible commonalities:** The strongest pair shows a similar small lock-cylinder/escutcheon component family and callout layout.
- **Visible differences/limits:** The direct latch and hinge assemblies are not comparably depicted; other paired drawings use different views and visibly different door structures.

### aperture-pillars
- **Visual grade:** GENERIC ONLY (High confidence)
- **Compared images:** `evidence/mopar/expanded_adrs/illustrations/Challenger/aperture-pillars/assembly-02.png` versus `evidence/mopar/expanded_adrs/illustrations/Charger/aperture-pillars/assembly-02.png`
- **Pixel metrics:** score 0.557634; foreground Dice 0.300373; pHash distance 28
- **Visible commonalities:** Both contain body aperture/pillar members and sill pieces.
- **Visible differences/limits:** Two-door and four-door aperture structures, pillar count, opening geometry and assembly segmentation visibly differ.

### floor-pans
- **Visual grade:** GENERIC ONLY (High confidence)
- **Compared images:** `evidence/mopar/expanded_adrs/illustrations/Challenger/floor-pans/assembly-01.png` versus `evidence/mopar/expanded_adrs/illustrations/Charger/floor-pans/assembly-02.png`
- **Pixel metrics:** score 0.552351; foreground Dice 0.308346; pHash distance 26
- **Visible commonalities:** Both depict underbody/floor structural panels.
- **Visible differences/limits:** Panel boundaries, tunnel/floor segmentation, crossmembers and layout visibly differ.

## Non-negotiable limitation

A similar exploded drawing may be reused across a service family and does not prove identical parts, dimensions, materials, attachment strength, software, calibration, installed configuration, interchangeability, crash performance or legal ADR compliance. ADR 69/00 and ADR 73/00 are listed only as image-similar depicted restraint-hardware screens; dynamic performance remains wholly unproven.

## Reproducibility

- 89 catalog images inventoried.
- 2,628 cross-model pairs scored from pixels only.
- 12 same-category component classes manually reviewed from the strongest pixel-ranked pairs.
- Automated metrics: whitespace-trimmed grayscale structure, foreground-mask Dice, perceptual hash and difference hash.
- Structured outputs: `extracted/image_similarity/`.