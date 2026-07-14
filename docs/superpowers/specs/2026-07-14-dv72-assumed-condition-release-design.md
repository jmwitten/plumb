# DV72 Assumed-Condition Release Design

Date: 2026-07-14

Status: Owner-approved design basis awaiting written-spec review

## Outcome

Convert the DV72 coordination study into a conditional fabrication package that is useful without a completed field survey. The package will state one explicit assumed site condition, resolve every product and geometry decision that can be resolved analytically, and distinguish three authorities:

1. **Released for fabrication under assumed conditions:** cabinet parts and joinery, drawer boxes and hardware preparation, service voids, and countertop coordination dimensions.
2. **Released for installation only after field verification:** wall location, finished-floor datum, framing/backing, rough-ins, clearances, and agreement between the installed site and the assumed-condition schedule.
3. **Trade-controlled:** plumbing code approval, countertop fabricator templates and procedures, and any project-specific structural approval required by the authority having jurisdiction.

The documents must never imply that an assumed wall was surveyed or that a model-generated calculation is a professional seal.

## Assumed site basis

The conditional package will use the existing project coordinate system and mark every item below as `owner_assumed`, not `field_verified`:

| Item | Assumed condition |
|---|---|
| Wall | 144 in long × 96 in high; straight, flat, plumb, and capable of receiving backing |
| Vanity placement | 72 in wide; left edge 24 in from the wall's left datum |
| Floor | Level finished floor at 0 in AFF |
| Framing | Wood studs at 16 in on center plus new continuous solid 2×6 backing at the rear rail and solid blocking at each selected support location |
| Wall finish | 1/2 in gypsum or equivalent nonstructural finish over the assumed framing |
| Vanity elevation | Cabinet bottom 11 in AFF; finished counter top 34.5 in AFF |
| Sink centers | 18 in and 54 in from the vanity's left edge |
| Waste | One independent wall outlet per sink, centered on its sink at 19 in AFF; final size, slope, venting, fittings, and connection remain plumber-controlled |
| Supplies | Hot and cold shutoffs at 21 in AFF, 4 in left/right of each sink center; final valve and escutcheon geometry remains plumber-controlled |
| Wall faucet | Spout centerline targeted 4.5 in above finished counter; valve body and wall build-up follow the accepted Kohler installation data |
| Room clearance | At least the selected NYC profile's required clear floor space in front and at the sides |

Any field variance invalidates installation release until the model is rerun. It does not retroactively invalidate shop fabrication when the variance can be accommodated entirely by serviceable field connections without cutting the case.

## Product-driven geometry

The current fixture, drain, trap, and runner records must become geometry authorities through typed adapters:

- Kohler K-20000 sink dimensions locate the undermount rim at the countertop underside and control the sink/body envelope.
- Kohler K-7124-A controls the drain connection diameter and nominal body length below the fixture outlet.
- Kohler K-8998 controls the trap's gross length, gross height, inlet/outlet size, cleanout side, and an explicit installed orientation to the assumed wall outlet.
- Each sink retains an independent P-trap. No shared trap, S-trap, or unvented topology is inferred.
- Blum MOVENTO 763.4570S controls upper-drawer nominal length, minimum inside depth, locking-device zones, and removal direction.
- A current manufacturer-documented short-depth, full-extension, soft-close runner will be selected for the lower drawers. If no reliable product fits, the lower drawers remain withheld rather than receiving invented hardware.

Drawer boxes and service envelopes will be re-derived from those selected products plus explicit assembly, hand, and tool allowances. Product mutation tests must prove that changing drain or trap dimensions changes geometry or fails loudly.

## Countertop and cabinet fabrication

Use a 30 mm engineered-quartz structural slab with a 38 mm visual front edge to retain the reference image's substantial pale top. The cabinet height will be adjusted so the finished top remains 34.5 in AFF above the 11 in cabinet-bottom datum.

The package will issue cabinet and drawer dimensions only after the product-driven plumbing and runner checks pass. It will include:

- case panels, rear rail, stretchers, drawer fronts, and drawer-box components;
- grain and front-sequencing identifiers for the four figured-wood slabs;
- joinery, fastener, edge-band, and finish assumptions;
- current sink-template identifiers, cutout ownership, minimum stone webs, support zones, and sealant/attachment notes;
- explicit tolerances and a statement that the countertop fabricator's accepted template controls final stone cutting.

The reference photograph controls aesthetic intent only.

## Mounting system and load path

The design will select one primary vertical load path rather than summing unrelated capacities. The intended arrangement is manufacturer-documented concealed vanity supports aligned with the left end, center divider, and right end, bearing directly beneath the countertop/case structure. A continuous rear rail provides cabinet positioning and lateral restraint but receives no assumed share of gravity load unless the connection calculation explicitly assigns one.

The calculation will enumerate dead load, fixtures, water, drawers, contents, countertop, and a service/live-load allowance; apply a stated safety factor; and check bracket count/spacing, blocking, fasteners, embedment, edge distances, and cabinet-to-support attachment. Manufacturer capacity remains bounded by the manufacturer's substrate and installation conditions. If no public documentation supports a complete connection path, mounting remains a conditional installation hold even if cabinet fabrication is released.

Temporary support stays in place until the cabinet is level, plumb, fully connected, and independently inspected. The heavy top is installed only after the empty cabinet has passed mounting inspection.

## Release-state changes

Replace the blanket `DESIGN HOLD` with a model-derived status banner:

- `CONDITIONAL FABRICATION RELEASE` when all fabrication-controlled findings pass and every assumption is displayed;
- `INSTALLATION HOLD — FIELD VERIFY` until the site matches the assumed-condition schedule;
- `TRADE HOLD` for licensed plumbing, fabricator-controlled stone work, or required structural review;
- `COMMISSIONED` only after installed leak, drawer, anchor, loading, and service-access checks are recorded.

The validation document will show which evidence closes each finding, who owns it, and whether it blocks fabrication, installation, use, or closeout. PASS remains scoped; no trade-controlled question is converted to PASS merely because an assumption exists.

## Document changes

Retain the four linked reader surfaces:

1. **Review and installation:** assumed-condition schedule, dimensioned sink/plumbing/drawer/mount section, load path, field-verification checklist, and conditional status.
2. **Assembly and service:** released case/drawer sequence, selected hardware, validated removal states, plumbing access, and conditional service procedure.
3. **Fabrication:** released cut inventory, joinery and finish assumptions, countertop coordination, tolerances, and withheld items if any.
4. **Validation and sources:** product authorities, calculations, mutation evidence, phased findings, owner/responsible party, and commissioning record.

## Failure behavior

- Missing or contradictory product dimensions fail compilation.
- A trap, drain, or runner that does not fit fails rather than shrinking a service allowance.
- A site variance changes installation status back to HOLD.
- Missing manufacturer or connection evidence preserves UNKNOWN.
- No output may claim field verification from an owner assumption.
- Fabrication dimensions disappear when their controlling product or validation fails.

## Verification

- Test assumption provenance and invalidation behavior.
- Test product mutations for sink, drain, trap, upper runner, and lower runner.
- Test fixture, drain, trap, assumed wall outlet, drawers, and service clearances in the same coordinate frame.
- Test released cut inventory disappears on controlling failures.
- Test mounting load accounting and conservative failure cases without overstating manufacturer capacity.
- Test all four documents' statuses, reciprocal links, responsible parties, and deterministic bytes.
- Render and inspect the key section at desktop and mobile widths.
- Repeat adversarial technical and no-context installer reviews, fix Critical and Important findings, run the relevant suite, commit, and push the branch.

## Explicit non-authorities

This package is not a permit, professional engineering seal, licensed-plumber approval, countertop shop drawing, or evidence that the real wall matches the assumed wall. It is a conditional fabrication design whose installation authority depends on field confirmation and the named trade-controlled evidence.
