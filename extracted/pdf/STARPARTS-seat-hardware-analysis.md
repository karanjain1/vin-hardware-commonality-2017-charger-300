# STARPARTS seat-hardware extraction

## Source and scope

- Source: `STARPARTS_LD_050_Interior_Trim.pdf`
- Printed/exported title: **Parts List (2023 - LD), 050 Interior Trim / 900 Front Seats — Adjusters, Recliners, Shields and Risers / 910.01 Passenger Seat, power**.
- PDF length: 13 landscape pages.
- STARPARTS email was generated 30 July 2026 and printed/forwarded 31 July 2026.
- The source is a broad, sales-code-conditioned parts list. It is not a VIN-filtered build record.

## Distinct callout inventory

| Callout | Catalog description | Distinct service part number(s) | Catalog qty | Parts-list PDF page(s) | Shown in exploded drawing? | Potential ADR relevance |
|---:|---|---|---:|---|---|---|
| 1 | PANEL, Front Seat Back | `1UY02DX9AC` | 1 | 4–5 | Yes | Low/secondary trim item |
| 2 | FRAME, Front Seat Back | `68159139AA`; `68593541AA`; `68593544AA` | 1 | 5 | Yes | **High** — structural seat-back frame |
| 3 | ADJUSTER, Power Seat | `68193460AC`; `68193462AC` | 1 | 5–6 | Yes | **High** — seat track/adjuster load path to floor |
| 4 | COVER, Track, Rear | `1UV50DX9AA` | 4 typical; 1 on some C8/X5 rows | 6–7 | Yes | Low/secondary cover |
| 5 | COVER, Track, Front | `1UV51DX9AA` | 4 typical; 1 on some C8/X5 rows | 7–8 | Yes | Low/secondary cover |
| 6 | SCREW, Hex Head, M14x1.5x109.0, Adjuster To Floor | `06507594AA` | 8 | 8 | Yes | **High** — direct seat-to-floor anchorage fastener |
| 7 | BRACKET, Seat, Side Shield Attaching | `68157098AA` | 1 | 8 | Yes | Low–medium; shield attachment, not established here as primary load path |
| 8 | SHIELD, Seat Adjuster | `1UZ62DX9AC` | 1 | 8–9 | Yes | Low/secondary cover/shield |
| 9 | COVER, Front Seat Anchor Bolt | `1UV75DX9AA`; `1UV75DX9AB` | 1 | 9–11 | Yes | Low/secondary cover over a critical joint |
| 10 | CHUTE, Airbag | `68102980AA`; `68103691AA` | 2 | 11 | Yes | **High/medium** — airbag deployment-path component |
| -11 | BLOWER, Seat Back | `55057389AD` | 2 | 11–12 | No | Low; comfort/ventilation |
| -12 | BLOWER, Seat Cushion | `68306763AA` | 2 | 12 | No | Low; comfort/ventilation |
| -13 | BRACKET, Module, Heated Seat Module, (NOT SERVICED) | None listed | Not listed | 12 | No | Low; explicitly not serviced |
| -14 | BOLT, Seat, Seat Back to Cushion | `68104960AA` | 8 typical; 1 on some C8/X5 rows | 12–13 | No | **High** — structural seat-back/cushion joint fastener |
| -15 | NUT, M6x1.00, Air Bag Attaching | `68104961AA` | 6 typical; 1 on some C8/X5 rows | 13 | No | **High/medium** — airbag attachment fastener |

There are **15 distinct catalog callouts and 19 distinct listed service part numbers**. Callout `-13` has no service part number. The leading hyphen on callouts `-11` through `-15` is preserved exactly from the parts list; none of those callouts appears in the exploded graphic.

## Drawing/graphic pages

- **PDF page 2:** blank apart from printed email header/footer.
- **PDF page 3:** upper/major portion of exploded passenger power-seat illustration; visible callouts 1–4 and 6–10.
- **PDF page 4:** lower continuation of the same oversized illustration, showing callout 5, followed by the beginning of the parts table for callout 1.
- The underlying embedded STARPARTS graphic is a single 1400 × 1700 JPEG and shows callouts **1 through 10 only**.
- No exploded graphic is present for table-only callouts `-11` through `-15`.

Extracted artifacts:

- `starparts_pages/drawing-pages-03-04.pdf` — exact two printed pages carrying the split/continued drawing.
- `starparts_pages/starparts-exploded-drawing.jpeg` — complete underlying exploded drawing, without the email print split.
- `starparts_pages/page-01.png` through `page-13.png` — rendered page images.
- `starparts_pages/page-metadata.json` — page dimensions, text character counts and embedded-image inventory.

## Evidence and applicability caveats

1. **Not 2017 VIN-specific evidence.** The catalog scope is explicitly **2023 LD**, while the case scope concerns a VIN-specific 2017 Charger/300. This document cannot prove the as-built part number, hardware count or applicability for the 2017 vehicle.
2. **No VIN/build-date filtering is visible.** The many sales-code and trim-code rows produce alternative part numbers. A VIN build sheet/STARPARTS VIN query, 2017 model-year catalog, OEM engineering drawing, or physical part marking is required to select the applicable number.
3. **Potential vehicle mismatch in the forwarding text.** The email body says “this is a challenger,” whereas the STARPARTS title says LD. That inconsistency further weakens vehicle-specific provenance.
4. **Quantities are catalog-row quantities, not an installation audit.** Do not infer torque, material grade, fastener property class, geometry, or confirmed per-seat count from this list alone.
5. **ADR relevance is triage only.** Structural frame/adjuster/seat anchorage and airbag-associated items are flagged as potentially ADR-critical, but the PDF contains no ADR claim, test result, torque specification, drawing dimensions, or compliance determination.
