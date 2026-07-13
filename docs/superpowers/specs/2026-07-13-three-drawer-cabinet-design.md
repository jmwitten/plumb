# Three-Drawer Cabinet and Reusable Drawer-Bank Core

Date: 2026-07-13

Status: Approved concept; written contract awaiting owner review.

## Outcome

Extend the existing optional `cabinetry.frameless@1` pack with one bounded,
real product archetype:

```yaml
cabinetry:
  mode: release
  profile: frameless_plywood_shop_v1@1.0.0
  material_evidence: ...
  cabinets:
    - archetype: drawer_base_three@1
      id: DB40
      width: 40
      placement:
        against: north_wall
        from_left_datum: 24
      conditions:
        left_end: exposed
        right_end: exposed
```

That compact declaration must generate a fabrication- and installation-ready
40-inch frameless base cabinet with three progressively taller clothing
drawers, conventional pulls, and soft-close undermount runners. It must also
prove that the pack is doing useful work: the declaration expands into the
carcass, drawer boxes, fronts, hardware, machining, relationships, validation,
instructions, BOM, and viewable documents rather than relying on a bespoke
project script.

The implementation introduces an internal reusable drawer-bank core. The
archetype is the only new compact public product surface in this increment. A
future vanity can reuse the same core twice—two drawers on the left and two on
the right—without inheriting a completely generic cabinet-layout language.

This remains a pack extension. It does not change the frozen base DetailSpec
language or the behavior of existing door-base, cabinet-run, or floating-vanity
projects.

## Decisions

| Decision | Contract |
| --- | --- |
| Product | Floor-supported, 40-inch-wide, three-drawer frameless base cabinet for clothing |
| Public archetype | `drawer_base_three@1` inside `cabinetry.frameless@1` |
| Reuse seam | Internal `DrawerBankModel` independent of the enclosing product archetype |
| Overall geometry | 40 in W × 34.5 in H × 23.25 in D, including a separate 4 in toe-kick platform with 3 in setback |
| Front arrangement | Three applied slab fronts with 1.5 mm top/bottom reveals, 2 mm inter-front gaps, and progressive heights |
| Drawer boxes | 16 mm prefinished plywood sides/front/back with a captured 12 mm plywood bottom |
| Runner | Blum MOVENTO 763.5330S, 21 in, standard-duty, full-extension, integrated BLUMOTION soft-close |
| Locking devices | Blum T51.7601 left/right pair per drawer |
| Wide-drawer control | Blum ZS7M686MU lateral-stabilizer set per drawer |
| Opening | One centered Häfele Vogue matte-black 224 mm pull (`155.01.613`) per front; no TIP-ON, SERVO-DRIVE, or touch latch |
| Intended contents | Clothing; 40 lb declared contents load per drawer |
| Countertop | Field installed and supported by cabinet stretchers, matching the existing base-cabinet contract |
| Release boundary | Pack validates geometry, compatibility, load-rating fit, represented connections, and process; it does not certify whole-cabinet structural capacity |

## Why this shape

Three implementation shapes were considered:

1. a project-specific assembly built directly from base-language primitives;
2. a completely generic public drawer-stack authoring language; and
3. a bounded product archetype implemented over a reusable internal drawer-bank
   mechanism.

The third is selected. A one-off assembly would not exercise the cabinet pack.
A fully generic public language would require resolving arbitrary drawer counts,
mixed hardware, partitioning, sizing policies, service conflicts, and invalid
combinations before they are needed. The selected design captures the reusable
engineering now while exposing only the product that has actually been designed
and tested.

## Research-derived hardware contract

The runner adapter is a product-system adapter, not a generic `drawer_slide`
label.

Blum's current MOVENTO program lists the standard runner at 125 lb static load
and 12–21 inch nominal lengths; MOVENTO includes integrated BLUMOTION soft-close.
The selected 21-inch standard-duty part is `763.5330S`. The manufacturer data
requires a minimum 553 mm inside cabinet depth, a 533 mm drawer length, and
specific fixing locations to achieve the stated rating. One right and one left
`T51.7601` locking device are required per drawer.

The same manufacturer data derives the drawer's inside width as cabinet opening
width minus 42 mm for 16 mm drawer sides, requires 13 mm bottom recess, 16 mm
bottom clearance, a 50 mm minimum rear notch, and a 6 × 10 mm rear hook bore.
Maximum drawer height is opening height minus 23 mm, including at least 7 mm top
clearance.

Blum recommends its lateral stabilizer at opening widths of 610 mm (24 inches)
and wider. The `ZS7M686MU` set synchronizes the runners and prevents racking but
does not increase their load capacity. It supports opening widths through 1369
mm (53-29/32 inches), so the derived 977.9 mm opening in DB40 is within its
range. Each of the three drawers gets its own set.

Primary sources:

- [MOVENTO current program](https://www.blum.com/us/en/products/runnersystems/movento/programme/)
- [MOVENTO assembly and adjustment](https://www.blum.com/us/en/products/runnersystems/movento/assembly/)
- [MOVENTO product and application data](https://d2.blum.com/services/BEC003/movento_ep_dok_bus_%24sen-us_%24aof_%24v6.pdf)
- [MOVENTO 2026 product and dynamic-rating data](https://d2.blum.com/services/BEC003/movento_ep_dok_bus_%24sen-us_%24aof_%24v7.pdf)
- [MOVENTO current downloads](https://www.blum.com/us/en/products/runnersystems/movento/downloads-videos/)
- [MOVENTO 763/769 lateral-stabilizer instructions](https://d2.blum.com/services/BEC003/moventolatstab_ma_dok_bus_%24sen-us_%24aof_%24v3.pdf)
- [Häfele Vogue pull product family](https://www.hafele.com/us/en/product/handle-zinc/15501623/)

The implementation must retain source URLs, adapter version, and evidence level
in the catalog, manifest, hardware schedule, and source map. Manufacturer load
ratings apply to the selected runner system under its installation conditions;
they are not relabeled as proof of the carcass, drawer joinery, material, wall
attachment, or complete cabinet.

## Normalized semantic model

Compact archetype expansion produces a strict, replayable semantic declaration.
The existing `BaseCabinetDecl` contract remains valid for door cabinets. Drawer
bases receive their own declaration instead of populating door-only fields with
sentinel values.

The normalized model contains:

- the common shell fields: id, type, width, height, depth, toe dimensions,
  placement, end conditions, countertop contract, and source archetype;
- exactly one `DrawerBankDecl` for this archetype;
- three ordered `DrawerCellDecl` records with stable ids `top`, `middle`, and
  `bottom`;
- the front and box height allocation for each cell;
- declared contents load per cell;
- selected runner, locking-device, stabilizer, pull, and front-fastener product
  adapters; and
- a stable sizing-policy id, `progressive_clothing_3@1`, rather than a hidden
  positional convention.

`DrawerBankModel` accepts an enclosing clear opening, vertical allocation,
runner product, box construction profile, front policy, and stable namespace.
It returns drawer parts, hardware systems, machining, derived facts,
relationships, validation inputs, and process fragments. It must not know
whether its parent is a floor-supported base or a future wall-hung vanity.

The DB40 product adapter owns the carcass and passes one full-width opening to
the drawer-bank builder. The future vanity adapter can pass two narrower
openings separated from a plumbing keepout without copying drawer math or
installation logic.

## Derived DB40 geometry

All values are derived from the declaration, construction profile, and pinned
hardware adapter; no output script carries an independent dimension table.

### Carcass and fronts

- Overall width: 1016.0 mm (40 in)
- Carcass thickness: 19.05 mm (3/4 in)
- Clear opening width: 977.9 mm (38.5 in)
- Overall height: 876.3 mm (34.5 in)
- Toe-kick height: 101.6 mm (4 in)
- Frontable body height: 774.7 mm (30.5 in)
- Top and bottom reveal: 1.5 mm each
- Two inter-front gaps: 2.0 mm each
- Total front material height: 767.7 mm

The `progressive_clothing_3@1` policy resolves:

| Cell | Applied-front height | Drawer-side height | Intended use |
| --- | ---: | ---: | --- |
| top | 158.75 mm (6.25 in) | 101.6 mm (4 in) | socks, underwear, small folded items |
| middle | 254.0 mm (10 in) | 177.8 mm (7 in) | shirts and medium folded items |
| bottom | 354.95 mm (13.974 in) | 254.0 mm (10 in) | sweaters, pants, and bulky folded items |

The slightly sub-14-inch bottom front closes the exact metric reveal equation;
the reader-facing dimension may display as approximately 14 inches, but the cut
list and machining use 354.95 mm. All fronts are 1013.0 mm wide after the
existing 1.5 mm side-reveal policy. The word “progressive” refers to front and
box height, not runner depth: all three boxes are 533 mm nominal depth.

### Drawer boxes

For each cell:

- maximum side/front/back thickness is 16 mm;
- outside box width is 967.9 mm, giving 5 mm runner clearance per side;
- inside box width is 935.9 mm, exactly opening width minus 42 mm;
- nominal box length is 533 mm;
- the front and back fit between the two sides;
- a 12 mm bottom is captured in a profile-defined groove with its underside at
  the required 13 mm recess;
- the rear receives the required notches and hook bores; and
- the front receives generated applied-front attachment and pull bores.

The chosen 23.25-inch carcass profile must derive at least 553 mm usable inside
depth after back inset and back thickness. Any depth override that violates this
condition fails before geometry generation.

### Loads

Each cell declares 40 lb of clothing contents. The compiler derives the moving
wood assembly's self-weight from part volumes and the verified material
density, adds a pinned or conservatively measured allowance for the pull and
other moving hardware, and compares the resulting total with the current
runner's dynamic rating. Runner-system parts already included in the
manufacturer's test assembly are not double-counted. A required unknown mass is
an explicit evidence gap; it is not silently treated as zero for release.

The selected 125 lb static/110 lb dynamic runner is expected to have ample
margin for clothing, but release depends on the calculation and pinned current
catalog data. The lateral stabilizer is never counted as additional capacity.

## Parts, machining, and hardware

The expanded product includes the existing base shell and toe platform, with
door, hinge, shelf, and shelf-pin parts omitted. The drawer-bank core adds:

- three applied fronts;
- left side, right side, front, back, and captured bottom for each drawer;
- three left/right runner pairs represented as hardware components;
- three left/right locking-device pairs;
- three lateral-stabilizer kits, including cut rod/rack facts;
- one centered conventional pull and two mounting screws per front; and
- front-attachment fasteners sufficient to hold and adjust each applied front.

Generated machining includes:

- bottom grooves and their setup orientation;
- rear notches and 6 × 10 mm hook bores;
- locking-device fixing holes;
- all manufacturer-required runner screw positions on both cabinet ends;
- lateral-stabilizer rack/housing/rod preparation;
- applied-front attachment holes with adjustment allowance; and
- centered pull holes from the selected product's exact center-to-center
  dimension.

The reference pull for DB40 is one centered matte-black 224 mm pull per front,
using an exact catalog adapter and screws sized through the actual applied-front
thickness. Decorative finish may become an archetype version or supported
override later; v1 does not accept an arbitrary pull name.

## Validation and failure behavior

Schema and semantic failures must identify the authoring path, offending value,
derived limit, and repair direction where one exists. The increment adds at
least these checks:

1. archetype is known and width is finite and positive;
2. DB40 resolves to the exact three ordered cells and stable role ids;
3. body height equals front heights plus specified gaps and reveals;
4. every front and box part is positive and fits selected sheet stock;
5. clear opening, box width, and side thickness satisfy the runner formula;
6. inside cabinet depth satisfies the selected nominal runner length;
7. each box height stays at least 23 mm below its allocated opening height;
8. bottom recess, bottom clearance, rear notches, and hook bores match the
   product adapter;
9. every required runner fixing location exists and remains within its cabinet
   side;
10. left/right locking devices and runner handedness are complete per drawer;
11. the 977.9 mm opening activates and fits a lateral-stabilizer set per drawer;
12. stabilizer presence never alters the load rating;
13. declared contents plus derived self-weight do not exceed dynamic rating;
14. applied-front attachment and pull screws fit the material stack without
   emerging through the finished face;
15. adjacent fronts retain the 2 mm closed gap through the allowed adjustment
   envelope;
16. fully extended drawer envelopes do not collide with another closed front,
   countertop, toe platform, wall, or declared neighboring condition;
17. carcass joinery, captured back, toe support, wall anchorage, and material
   evidence retain all existing base-cabinet release checks; and
18. the lowered base-language assembly passes ordinary geometry and connection
   validation.

Negative tests must mutate one fact at a time—runner length, width formula,
stabilizer, locking device, fixing hole, depth, box height, front sum, load, or
sequence—and prove that compilation fails or the expected release finding opens.
The tests must not merely assert that the checked-in DB40 example passes.

## Lowering and base-language compatibility

The pack lowers every generated panel and hardware solid to existing
base-language components and every known physical relation to existing bonds,
contacts, overlaps, clearances, and authored construction-process stages. It
does not add drawer primitives to DetailSpec.

Existing projects must remain byte-for-byte deterministic at their current pack
surface. The implementation may split internal carcass and artifact helpers so
door bases and drawer bases share them, but existing ids, manifests, artifacts,
validation text, and checked-in example results are regression-pinned.

The packed manifest records:

- `cabinetry.frameless@1` and its implementation version;
- `drawer_base_three@1`;
- `progressive_clothing_3@1`;
- all selected product-adapter ids and source URLs;
- compact and expanded authoring provenance;
- derived dimensions and loads; and
- release findings without replacing unknown structural capacity with a pass.

## Process and instructions

The construction process graph and reader-facing instructions share the same
stable stages:

1. verify material/evidence, hardware part numbers, site, and release status;
2. break down and label carcass, toe, fronts, and drawer-box parts;
3. machine carcass joinery, back grooves, runner fixing holes, and wall anchors;
4. machine drawer-bottom grooves, rear notches, hook bores, locking devices,
   front attachments, and pull bores;
5. edge-band and finish all scheduled exposed edges, including drawer fronts;
6. dry-fit each drawer box and verify diagonals, bottom capture, and width;
7. assemble the toe platform and carcass square around the captured back;
8. attach and secure runners at every required fixing location;
9. assemble each drawer box, fit locking devices and stabilizer components, and
   install the applied front and pull;
10. insert drawers, cycle them, and perform side/height/tilt/depth adjustment to
    the generated reveal targets;
11. remove and label drawers for conventional shipping while retaining their
    paired runners and adjustment identity;
12. install, level, shim, and anchor the empty carcass using the existing
    base-cabinet installation contract;
13. reinstall each labeled drawer in order, commission soft-close and full
    extension, verify gaps under load, and record final acceptance; and
14. field-install the countertop under its separate product instructions.

No instruction may tell the installer to “adjust as needed” without naming the
target reveal, hardware adjustment, fastener state, and commissioning check.

## Deliverables and acceptance

The checked-in example is `details/frameless_three_drawer_40.project.yaml`. Its
normal build must produce the same deliverable families as the current cabinet
pack, extended for drawers:

- compiled 3D cabinet and exploded views;
- dimensioned front, side, plan, and drawer-box/detail views;
- cut list and edge-band map;
- runner, locking-device, stabilizer, pull, and fastener schedule;
- part-level machining schedule;
- fabrication, assembly, shipping, installation, and commissioning steps;
- evidence/release report and packed manifest; and
- a self-contained HTML report that Joel can open directly.

Acceptance requires:

- compact archetype expansion and expanded-record replay are deterministic;
- the compiled cabinet has three actual drawer boxes, not three decorative
  front rectangles;
- all product formulas and required hardware are represented and validated;
- the example passes the pack's fabrication and installation release gates
  without suppressing honest structural-capacity limitations;
- existing cabinetry and base-language tests remain unchanged and green;
- adversarial tests pin every listed safety/compatibility rule; and
- the HTML and drawings visibly show the progressive 40-inch cabinet and can be
  traced back to the same compiled model used by validation and BOM generation.

## Future vanity seam

The next vanity is expected to have four drawers: two on the left and two on the
right, normally around a sink and plumbing zone. This increment does not build
that vanity. It must, however, make the later implementation additive:

- instantiate `DrawerBankModel` twice with distinct namespaces and narrower
  clear openings;
- let the vanity product adapter own the center sink/plumbing keepout,
  partitions, countertop/sink envelope, moisture rules, and wall load path;
- check runner, drawer, and pull envelopes against the plumbing keepout; and
- reuse box sizing, runner machining, hardware, load checks, artifacts, removal,
  reinstallation, adjustment, and commissioning unchanged.

The reusable core must not assume full-cabinet width, a toe kick, floor support,
three drawers, or absence of plumbing. If any of those assumptions appears in
drawer-bank code or tests, the abstraction has been drawn at the wrong boundary.

## Explicit non-goals

- arbitrary drawer counts or user-authored sizing formulas;
- mixed runner families or nominal depths in one bank;
- inset fronts, face-frame cases, metal drawer boxes, file drawers, or pull-out
  shelves;
- TIP-ON, SERVO-DRIVE, locks, internal organizers, dividers, or electrical
  accessories;
- sink, plumbing, floating support, or moisture-zone logic in this increment;
- structural certification of the whole cabinet; and
- changes to the base DetailSpec language.
