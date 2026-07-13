# Frameless Cabinetry Pack v1 Design

## Objective

Add an opt-in `cabinetry.frameless@1` project front end that compiles a conventional
shop-built, two-door frameless base cabinet with one adjustable shelf and its
installation against a stud wall into the existing `DetailSpecDoc` base language.
Existing `load_spec_file`, `compile_spec`, and `compile_spec_file` behavior remains
unchanged when the pack is absent or inactive.

## Approved baseline

- 3/4-inch prefinished plywood carcass and door slabs.
- 1/4-inch captured back.
- Applied edge banding.
- Independent toe-kick base.
- Glue-and-cabinet-screw carcass joinery.
- Blum CLIP top BLUMOTION 110-degree hinge adapter with manufacturer drilling
  dimensions and adjustment envelope.
- One adjustable shelf on a System-32-compatible pin pattern.
- Conventional small-shop workflow; CNC is not required.
- Installation covers site survey, floor datum, leveling/shimming, fillers,
  wall fastening at verified studs, countertop support, and final adjustment.

## Standards and evidence

`KCMA A161.1-2022` is the primary performance reference for residential kitchen
and vanity cabinets. AWI vocabulary and workmanship guidance inform surface
classification, installation, care, storage, and acclimation. Manufacturer data
controls hardware geometry. TSCA Title VI status is material provenance.

The engine must never infer certification. Evidence is classified as `derived`,
`calculated`, `manufacturer_rated`, `field_verified`, `physically_tested`,
`certified`, `assumed`, or `unknown`. A generated design may state that a
calculation passed or that catalog limits were respected; it may not state KCMA
compliance or certification without supplied evidence.

## Boundary

The new public entry point is `detailgen.packs.compile_project_file`. It loads a
strict project document, activates explicitly requested packs in a compilation-
local registry, asks the cabinetry pack to resolve profiles/catalogs and build a
cabinet semantic model, then lowers that model to an ordinary `DetailSpecDoc`.
The existing compiler builds the resulting geometry. Pack-aware validation and
artifacts wrap, but do not replace, the compiled `SpecDetail`.

No pack imports register component, material, connection, or check vocabulary in
the process-wide base registries. Installing or importing the pack therefore has
no effect on ordinary specs.

## Authoring surface

The project declares:

- project name and units;
- exact pack id/version;
- one named cabinetry construction profile;
- a stud-wall survey with wall plane, finish thickness, floor-high-point datum,
  and measured or explicitly field-unverified stud positions;
- one or more cabinet declarations; v1 accepts exactly one `base` cabinet with
  two overlay doors and one adjustable shelf;
- `draft` or `release` compilation mode.

The profile supplies routine construction choices. Typed per-cabinet overrides
cover width, height, depth, toe-kick, door gaps, surface exposure, placement, and
countertop condition. Arbitrary custom geometry is not added to the pack grammar;
future work can attach base-language fragments through a separately designed
augmentation seam.

## Semantic output

The cabinet model carries stable ids for sides, bottom, captured back, front and
rear stretchers, shelf, doors, toe-kick members, anchor strip, hinge systems,
shelf-support systems, wall anchors, shims, and installation obligations. Each
derived value records its declared source, generating rule, profile version, and
catalog version.

The lowerer emits only existing base vocabulary (`plywood_panel`, `lumber`, and
`structural_screw`) with raw placements, explicit validation bonds/contacts and
expected overlaps where they are physically meaningful, plus derived facts in
the pack result. Studs are modeled as existing site members; the wall finish and
field survey remain semantic installation layers rather than being mislabeled as
plywood geometry.

## Validation modes

Both modes run the same rules. `draft` permits unresolved field and evidence
obligations while labeling them. `release` blocks fabrication/installation release
when a required finding is failed or unknown.

V1 rules cover strict schema/profile/catalog resolution, positive and coherent
dimensions, panel stock limits, door/reveal geometry, manufacturer hinge fit and
quantity, shelf load/deflection, wall-stud attachment resolution, toe-kick support,
countertop support declaration, environmental/site readiness, material provenance,
and final commissioning. Physical KCMA cyclic, impact, and finish tests remain
`not_performed` unless evidence is supplied and never become simulated passes.

## Outputs

`PackedProject` exposes the compiled base detail, cabinet semantic model, lowered
spec, structured findings, release readiness, evidence records, cut list, edge-band
map, hardware schedule, assembly steps, installation steps, and a deterministic
JSON-serializable manifest. Existing detail rendering and BOM facilities remain
available through delegation to the compiled `SpecDetail`.

## Compatibility contract

- Existing spec APIs and output are byte-identical with the pack installed but
  inactive.
- Pack activation is explicit and version-pinned.
- Registry state is compilation-local.
- Generated ids and manifests are deterministic.
- Profile and catalog versions are recorded.
- Unsupported pack versions or v1 cabinet variants fail with teaching errors.
- The STEPDOC/CPG implementation owns base sequence and installability internals;
  this increment does not edit those files and will re-verify after its merge.

