# Case ledger — VIN hardware commonality review

## Case
- Case ID: VIN-HARDWARE-2017-CHARGER-300
- Purpose: compare catalogued ADR-critical interior/occupant-protection hardware between two vehicles.
- Status: evidence collection and comparison; not a compliance approval or certification conclusion.

## Vehicle identities
| VIN | Decoded identity | Identity source | Catalog route |
|---|---|---|---|
| 2C3CDXGJ2HH530684 | 2017 Dodge Charger R/T 392; 6.4 L V8; RWD; Brampton, Canada | NHTSA vPIC DecodeVinValuesExtended; clean decode | MoparAmerica VIN search accepted and routed to `2017 Dodge Charger R/T Scat Pack 6.4L V8 Gas` |
| 2C3CCAEG4HH586472 | 2017 Chrysler 300C; 3.6 L V6; RWD; Brampton, Canada | NHTSA vPIC DecodeVinValuesExtended; clean decode | MoparAmerica VIN search returned a vehicle-selection error; catalog trim route inferred as `2017 Chrysler 300 C 3.6L V6 Flex` from vPIC identity and MoparAmerica trim catalog |

## Supplied source
- Original filename: `Aries_Aero_Mail_Fw_STARPARTS_Parts_List2023_LD_050_Interior_Trim.pdf`
- Controlled copy: `source/STARPARTS_LD_050_Interior_Trim.pdf`
- SHA-256: `db26573eb7d1b671eb41eeefe0bd1c6db30903c754033f0c3baa532f525bea1d`
- Size: 1,316,980 bytes
- Pages: 13
- Title/scope: STARPARTS 2023 LD, 050 Interior Trim / 900 Front Seats / 910.01 Adjusters, Recliners, Shields and Risers — Passenger Seat, power.
- Exploded drawing: pages 3–4; visible callouts 1–10. Remaining pages contain the parts list and option/sales-code qualifiers.

## Evidence limitations
1. The supplied STARPARTS extract is for **2023 LD** and is not itself VIN-specific evidence for either 2017 vehicle.
2. MoparAmerica category pages can list several option-, colour-, trim-, and supersession-dependent alternatives. A part appearing on a trim page is a **catalog candidate**, not proof that it is installed on the individual VIN.
3. MoparAmerica accepted the Charger VIN but failed to select the Chrysler VIN. The Chrysler catalog route is therefore identity/trim-inferred and must be confirmed against an OEM build sheet or dealer VIN query before any installed-part assertion.
4. Identical catalog part numbers can support commonality, but parts-catalog evidence alone does not prove ADR compliance, physical installation, test equivalence, or production configuration.
5. Any exact-installed-part or compliance conclusion not resolved by OEM option/build data is marked `[TBC — needs: OEM build sheet/sales-code/VIN-specific dealer confirmation]`.
