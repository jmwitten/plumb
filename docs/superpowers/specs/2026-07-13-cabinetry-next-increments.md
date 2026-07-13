# Cabinetry Next Increments: Runs, Floating Vanities, Archetypes, and Fast Authoring

Date: 2026-07-13

Status: Implemented and adversarially hardened. This document narrows each
increment so the optional packs continue to lower to the unchanged DetailSpec
base language.

## Outcome

The next increments turn the first frameless base cabinet into a useful family
without pretending that all casework shares one structural or installation
contract:

1. straight, touching base-cabinet runs;
2. wall-hung two-door vanities with a modeled wall load path;
3. named, versioned archetype presets; and
4. compact authoring that expands to the same strict semantic records.

All four increments are implemented. The floating-vanity increment deliberately
has a stronger release gate than a floor-supported base cabinet.

## Research-derived rules

| Concept | Primary source | Pack rule |
| --- | --- | --- |
| Vanity wall support | [Kohler 1533268-2-A](https://techcomm.kohler.com/techcomm/pdf/1533268-2.pdf) | The conservative custom-v1 profile requires surveyed studs plus continuous flush 2x8 blocking; modeled anchors engage the blocking near both rail ends and every intervening stud. A future tested proprietary system may define a different profile. |
| Temporary support and anchor sequence | [Kohler 1533268-2-A](https://techcomm.kohler.com/techcomm/pdf/1533268-2.pdf) | Installation instructions set a temporary full-width support, verify level/plumb, drill end pilots and every intervening stud, fasten, then remove support. |
| Fastener stack | [Kohler 1533268-2-A](https://techcomm.kohler.com/techcomm/pdf/1533268-2.pdf) | Model rail, finish, and backing thickness. A generic nominal length is not sufficient evidence. |
| Bracing and plumbing rough-in | [Kohler 1106935-2](https://resources.kohler.com/onlinecatalog/pdf/1106935_2.pdf) | Represent wall backing and a plumbing keepout before fabrication; do not allow anchors or rail segments to occupy the keepout. |
| Multi-cabinet alignment | [IKEA ENHET bathroom installation guide](https://www.ikea.com/us/en/files/pdf/7a/d5/7ad5f5f4/enhet_bathroom_installation_guide_july_2022.pdf) | Establish one level datum, clamp/align adjoining boxes, connect them, and seal service penetrations where required. |
| Structural screw evidence | [ICC-ES ESR-2442](https://www.grkfasteners.com/getmedia/5f4f72a8-8d1f-479b-8ae0-5fc043e2943d/ESR-2442.pdf?ext=.pdf) | A listed screw can supply fastener properties, but it does not prove the custom rail-to-case assembly or the whole vanity. |

The source documents are installation precedents, not a claim that a custom
cabinet is a tested Kohler or IKEA product. Source-derived geometry and process
rules retain their source URLs and use the closed evidence vocabulary; a custom
wall-hung assembly still needs project-specific engineering evidence to cross
release.

## Increment 1: straight cabinet runs

Implemented scope:

- two or more touching base cabinets on one surveyed wall plane;
- deterministic left-to-right ordering;
- reciprocal `adjacent_cabinet` end conditions;
- no overlap and no undeclared gaps;
- one site model, namespaced per-box parts and evidence;
- cabinet-to-cabinet connection hardware and installation step; and
- ordinary base-language components, bonds, contacts, and overlaps.

The four case-connector screws at each joint are modeled components with
expected intersections into both adjacent end panels. The authored construction
process graph puts those join fasteners before the wall anchors, matching the
reader-facing instruction to align and join the run before final anchoring.

Deferred from the run increment:

- scribed fillers;
- corners and blind corners;
- changes in depth or height;
- integrated appliance openings; and
- shared countertops.

## Increment 2: floating vanity v1

### Authoring boundary

Activate `vanity.frameless@1`. V1 accepts exactly one wall-hung, two-door
frameless vanity with a field-installed top and sink. It reuses pinned cabinetry
material, hinge, joinery, evidence, and artifact types, but owns its structural
and plumbing semantics.

Required declarations:

- vanity id, width, height, depth, bottom elevation, and wall datum;
- two overlay doors and one open plumbing bay;
- field-installed top/sink design dead load and an explicit service load;
- supply/drain keepout rectangle in wall-run/elevation coordinates;
- a full-width rear structural rail;
- surveyed studs and flush 2x8 blocking records;
- selected 5/16-inch structural lag/screw, modeled length and pilot diameter;
- mounting evidence status and reference; and
- material evidence used by the cabinetry pack.

### Geometry and load path

The generated assembly contains:

- two carcass ends, bottom, front top stretcher, structural rear rail, split
  lower back rails around the plumbing bay, two doors, studs, backing, and
  structural fasteners;
- no toe-kick and no floor bearing;
- structural fasteners through the rear rail and finished wall into verified
  backing/studs; and
- bonds/contacts from loaded panels to the rear rail plus expected fastener
  overlaps through the complete wall stack.

V1 uses a rectangular open back/plumbing bay rather than inventing arbitrary
cutout operations in the base panel component. Sink bowl, faucet, trap, supplies,
top, and sealant remain field-installed interfaces rather than fake solids.

### Required validation

- positive, buildable carcass dimensions;
- every panel fits selected stock;
- pinned material properties and TSCA record;
- hinge fit and hinge quantity;
- rear rail spans the cabinet and has an anchor near each end;
- at least two verified supporting stud/backing targets;
- 2x8 blocking is flush, verified, and spans the rear rail when declared;
- each fastener clears the plumbing keepout;
- the rail-to-finish-to-backing stack leaves the specified embedment;
- the vanity bottom/top elevations agree with the project datum;
- dead and service loads are positive and recorded;
- project-specific mount engineering is verified and referenced; and
- base-language geometry validation passes.

The pack also runs a deterministic representation check from the loaded carcass
members through the rear rail and modeled anchors to the surveyed existing-wall
boundary. That finding activates the base report's **Load-path representation**
family. **Structural capacity** remains `UNKNOWN — NOT ANALYZED`; the external
review is a separate required evidence gate and is never relabeled as an engine
capacity calculation or certification. Both states are retained in the packed
manifest.

`mount_engineering.status: required` produces a required `UNKNOWN`, not a
best-guess pass. This is the intentional release boundary. Manufacturer
precedent and fastener tables do not establish capacity of a custom rail, its
joinery into the carcass, eccentric cabinet loading, substrate condition, or
the complete assembly.

### Installation output

The installation artifact must instruct the installer to:

1. verify release, wall plane, studs/backing, services, and local requirements;
2. verify the plumbing rough-in stays inside the declared keepout;
3. establish the top and bottom datums;
4. construct a temporary full-width support and use two installers;
5. set, level, plumb, and shim without twisting the case;
6. drill the specified pilots near both rail ends and at intervening targets;
7. install washers and structural fasteners through the modeled stack;
8. inspect the rail/case connection before removing temporary support;
9. install top, sink, faucet, drain, and supplies to their product instructions;
10. seal penetrations as required and perform a leak test; and
11. commission door operation, reveals, fasteners, wall contact, and deflection.

## Increment 3: reusable archetypes

Archetypes are named declaration templates, not new geometric primitives. Each
one expands to the same strict authoring schema and records the preset id in
provenance.

Initial presets:

- `base_two_door_30@1`: the proven B30 configuration;
- `base_two_door@1`: width is the only required cabinet dimension;
- `floating_vanity_two_door@1`: the v1 vanity carcass/front arrangement;
- `straight_base_run@1`: ordered cabinets with touching placement derived from
  a run origin and declared widths.

Not yet implemented as geometry merely because a name exists:

- drawer base;
- sink base with arbitrary plumbing cutouts;
- wall cabinet/suspension rail;
- tall pantry; and
- corner/blind-corner cabinets.

Those need separate product adapters, clearances, installation rules, and tests.

### Researched contracts for the deferred archetypes

These are design inputs for later increments, not silently active defaults.

#### Drawer base

The first drawer base should pin one complete runner family and nominal length,
not expose a generic `drawer_slide` label. Blum's MOVENTO material derives a
wood drawer's internal width as cabinet clear width minus 42 mm, drawer length
as nominal runner length minus 10 mm, limits drawer-side thickness to 16 mm,
requires a 12 mm minimum/15 mm maximum underside recess, a fixing-hook hole,
locking devices, and final height/side/tilt/depth adjustment. Sources:
[Blum wooden MOVENTO drawer guidance](https://ea.blum.com/en/building-a-movento-drawer/)
and [Blum MOVENTO downloads and installer guide](https://www.blum.com/us/en/products/runnersystems/movento/downloads-videos/).

Therefore its semantic model needs drawer box parts, bottom groove/recess,
runner drilling, locking devices, nominal-length/depth fit, load-class evidence,
front attachment/adjustment, pull clearance, removal/reinstallation, and cycle
commissioning. Drawer count cannot be a cosmetic front split.

#### Sink base

The sink base must own a coordinated service zone. IKEA's 2026 installation
guide requires plumbing layout verification before installation, warns that
service openings affect drawer arrangements, and directs openings to be cut
before fitting. It also calls for aligning the correct base cabinet with the
plumbing. Source: [IKEA 2026 kitchen installation guide](https://www.ikea.com/us/en/files/pdf/49/6f/496ff2f6/kitchen_installation_guide_mar_2026.pdf).

Its contract therefore needs selected sink/top envelope, drain/supply/disposal
and electrical keepouts, reinforced top rails or subtop, cutout machining with
edge-sealing operations, door/drawer collision checks, trap/service access,
countertop/sink attachment instructions, and leak commissioning. A generic
rectangle cut from the back is insufficient.

#### Wall cabinet

Two legitimate installation families should remain separate profiles:

- A proprietary rail profile must pin the rail and cabinet hanger as a tested
  system. IKEA's rail may be cut/combined, has holes intended to align with
  studs, permits horizontal adjustment before locking, requires a strong wall,
  a straight/level rail, suitable wall fasteners, and 1/2-inch lift clearance
  above a wall cabinet. Sources: [SEKTION suspension rail](https://www.ikea.com/us/en/p/sektion-suspension-rail-galvanized-60261527/)
  and [IKEA 2026 kitchen installation guide](https://www.ikea.com/us/en/files/pdf/49/6f/496ff2f6/kitchen_installation_guide_mar_2026.pdf).
- A direct-fastened custom case needs top and bottom hardwood hanging rails.
  American Woodmark calls for at least four installation screws on wall
  cabinets wider than 15 inches, at least one inch into studs, pilots through
  both hanging rails, temporary support/T-bracing, shimming crooked walls
  without stressing cabinet joints, and two-person lifting. Source:
  [American Woodmark Cabinet Installation Guide](https://americanwoodmark.com/content/dam/install-guides/mto/Cabinet-Install-Guide.pdf).

Both profiles need cabinet/contents design loads, rail/hanger or hanging-rail
joinery, wall substrate and fastener evidence, lifting envelope, temporary
support, top clearance, neighboring-case connections, and the same honest
whole-assembly capacity boundary used for the floating vanity.

#### Tall cabinet

Tall cabinets are installation-order and stability problems, not taller base
boxes. IKEA recommends installing a high cabinet first when it terminates a
single-line kitchen and fitting its cover panel before placement. American
Woodmark stages tall cabinets for spacing, installs them after the wall run,
shims them to align plumb with adjacent wall cabinets, connects the frames, and
defers specialty units to their product instructions. Sources:
[IKEA 2026 kitchen installation guide](https://www.ikea.com/us/en/files/pdf/49/6f/496ff2f6/kitchen_installation_guide_mar_2026.pdf)
and [American Woodmark Cabinet Installation Guide](https://americanwoodmark.com/content/dam/install-guides/mto/Cabinet-Install-Guide.pdf).

The future contract needs tip-over restraint/load path, ceiling and lift/tilt
clearance, floor bearing and shims, multiple wall attachment zones, door and
pull-out load cases, appliance ventilation/clearance when applicable, cover
panel sequence, and explicit order relative to wall/base cabinets.

#### Fillers and corner clearances

Fillers must be physical, fabricated parts tied to a measured site gap, not a
permission to leave space between cabinet bounding boxes. American Woodmark
uses fillers to establish blind-corner pullout and hinge clearance, requires
them to be measured, cut, predrilled, and screwed in place, and aligns them with
the cabinet run. Source: [American Woodmark Cabinet Installation Guide](https://americanwoodmark.com/content/dam/install-guides/mto/Cabinet-Install-Guide.pdf).

A filler increment needs nominal blank width, minimum retained width, scribe
allowance, finished/exposed edges, wall profile survey, door/handle clearance,
attachment hardware, field-trim provenance, and a post-scribe measured record.
It should not be modeled as a generic gap.

## Increment 4: faster authoring

The compact surface adds an `archetype` plus `overrides`. Expansion occurs
before strict pack parsing, and the expanded record is retained in the manifest.
Unknown overrides fail with suggestions. No default may silently select:

- a wall or stud location;
- material procurement evidence;
- plumbing rough-in;
- structural mounting evidence;
- site verification status; or
- a product whose instructions govern installation.

For runs, a compact declaration may provide `origin` and cabinet widths/ids;
placement and reciprocal adjacency are derived. For a floating vanity, the
archetype supplies shop-construction defaults but not wall, plumbing, load, or
engineering evidence.

The manifest retains the full expanded strict project record, not only the
archetype id. Recompiling that retained record produces the same lowered
DetailSpec as compiling the compact declaration.

## Compatibility

All additions are opt-in. Existing `cabinetry.frameless@1` documents and the
base DetailSpec compiler remain unchanged. Packs continue to emit ordinary
base-language components and validations. A new pack may import reusable Python
adapters from cabinetry, but it cannot add process-wide component vocabulary or
change base registries as a side effect.
