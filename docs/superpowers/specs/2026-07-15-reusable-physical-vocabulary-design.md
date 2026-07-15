# Reusable Physical Vocabulary and Fast Extension Loop

**Status:** implementation handoff for owner review

**Date:** 2026-07-15

**Pilot:** `family_birdhouse`

## Goal

Make ordinary small wood projects expressible with existing Plumb vocabulary so
that a new material, panel, ordinary screw, or operable service panel normally
requires DetailSpec data and focused tests rather than a new CadQuery component
or connection class.

The birdhouse remains the acceptance pilot. Existing public component and
connection names continue to compile, while reusable primitives become the
preferred authoring surface for future projects.

## Why the Birdhouse Became Compiler Work

The birdhouse geometry is simple. The delay came from semantic gaps around it:

- `HardwoodPanel` was tied to indoor-hardwood wording and allowed only one
  compiler-applied feature cut;
- Plumb had structural screws, but no ordinary exterior wood screw whose
  presence made no structural-capacity claim;
- connection hardware was accepted by exact Python class name, so a new screw
  required edits to every compatible connection;
- a pivoting or removable service panel could not truthfully use a fixed-joint
  connection;
- relevant extension tests still crossed the CadQuery boundary, and broader
  connection/full-suite gates took minutes even when only semantic behavior
  changed.

The birdhouse branch consequently added `CedarPanel`, `ExteriorWoodScrew`,
`PivotScrewed`, and `ServiceLatchScrewed`, plus registry, rendering, compiler,
and validation coverage. A clean relevant baseline currently takes 72.88
seconds for 19 tests. The broader connection run observed in the design task
took 7:17, and the first full platform gate took 17:12. Those durations are not
evidence that the birdhouse itself is CAD-heavy; they are evidence that the
extension and verification boundaries are too broad.

## Material Truth Today

`CedarPanel` does not encode engineering properties for cedar. It currently
encodes:

- panel dimensions and fabrication steps;
- `material_key="cedar"`;
- the BOM/display name `Untreated exterior cedar`;
- a render color and simple Blender shader;
- cedar-specific BOM, description, and assumption wording; and
- an explicit statement that species, grade, weathering, and structural
  capacity are not analyzed.

It does **not** encode density, stiffness, strength, shrinkage, moisture
movement, decay resistance, fastener withdrawal, or stock-size availability.
That is intentional. A material number belongs in Plumb only when a named rule
uses it and the value is scoped to a defensible species/grade/moisture/source.

A mahogany panel used non-structurally therefore needs material identity,
display color, a stock label, and honest service/finish assumptions. It does
not acquire invented engineering statistics merely because the species name is
more specific.

## Considered Approaches

### 1. Compatibility-first reusable core — selected

Extract generic panel, screw, hardware-capability, and service-panel behavior.
Keep all existing public types as compatibility wrappers. Migrate only the
birdhouse to the new primitives once equivalence and intentional representation
changes are proven.

This solves the recurring vocabulary problem without forcing every existing
detail through a high-risk migration.

### 2. Replace every panel, fastener, and connection at once

This would produce a cleaner-looking type graph immediately, but it would mix
the birdhouse problem with plywood sheet behavior, structural fasteners,
anchors, and every existing connection guard. The regression and artifact
review surface is disproportionate to the benefit.

### 3. Keep the birdhouse-specific classes and optimize only test selection

This would shorten the current loop but leave the next species, ordinary screw,
or service panel blocked on the same class additions. It treats the visible
duration without removing the vocabulary cause.

## Selected Architecture

### 1. A material-parameterized fabricated panel

Create `detailgen.components.panel.FabricatedPanel` and register it as
`fabricated_panel`.

Its public constructor is:

```python
FabricatedPanel(
    length: float,
    width: float,
    thickness: float,
    material_key: str,
    stock_label: str | None = None,
    material_assumptions: str | None = None,
    miter_ends=(),
    ease_radius: float = 0.0,
    name: str = "fabricated panel",
)
```

The component:

- rejects an unknown `material_key` through the existing material registry;
- uses `stock_label` for the fabrication profile and item label, defaulting to
  the material-key words only when the caller omits it;
- uses an explicit `material_assumptions` string when supplied, otherwise a
  generic disclaimer that grade, moisture condition, finish, and structural
  capacity are not analyzed;
- supports append-only bore/notch feature cuts, eased edges, and near/far
  miter crosscuts in one `ProcessRecord`;
- retains the existing panel datums and `WIDTH` compiler compatibility hook;
  and
- includes material, dimensions, edge treatment, miters, and every feature cut
  in its cache/BOM identity.

`HardwoodPanel` and `CedarPanel` become thin subclasses that supply their
current material keys, stock labels, default names, and exact assumption
language. Their registry keys and imports remain unchanged. Their dimensions,
datums, fabrication records, BOM rows, and single-feature geometry must remain
equivalent to the pre-refactor implementations.

The generic core adopts cedar's append-only feature behavior. Multiple feature
cuts on a hardwood wrapper become supported instead of silently overwriting the
previous cut. That is an intentional bug fix; the single-feature behavior used
by current projects remains unchanged.

`PlywoodPanel` stays separate in this increment. Its sheet-stock limits,
grooves, and fabrication semantics are materially different from linear solid
panels and should not be hidden behind optional branches in the new class.

### 2. Registered material identity with a truthful render fallback

The existing `Material` record remains the source of display name, RGB color,
and opacity. No strength or environmental-property fields are added in this
increment.

The Blender manifest gains each part's RGBA value. When Blender has a
purpose-built procedural shader for a material tag, it continues to use it.
When it does not, the renderer warns exactly as it does today but builds a flat
shader from the registered manifest color instead of unrelated gray.

Consequences:

- a new material such as mahogany requires one reviewed material-registry row
  with identity/color and honest project assumptions;
- it does not require a Blender-specific builder unless a procedural grain or
  finish is actually valuable; and
- an unknown/unregistered material remains a hard compiler error rather than a
  render-time guess.

### 3. Capability-based fastener compatibility

Add a small semantic capability surface to `Component`:

```python
CAPABILITIES: ClassVar[frozenset[str]] = frozenset()

def capability_tags(self) -> frozenset[str]:
    return self.CAPABILITIES
```

The initial closed vocabulary is:

- `installation_fastener` — this component owes an installation contract;
- `wood_screw` — it is appropriate for a connection that semantically asks
  for a screw biting wood;
- `ordinary_wood_screw` — it makes no structural-product-class claim; and
- `exterior_use` — the authored service selection says it is intended for an
  exterior application.

`_AxialFastener` and `ThreadedRod` receive `installation_fastener` as
appropriate so `is_fastener()` can stop matching Python class names.
`LagScrew`/`StructuralScrew` receive `wood_screw` but not
`ordinary_wood_screw`. The new ordinary screw receives all applicable tags,
with `exterior_use` derived from an explicit constructor value rather than its
color or coating name.

Connection unpacking gains `_require_hardware_capabilities()`. It retains the
current positional count/order diagnostics, but each slot names required
semantic tags and reports missing/actual tags. Exact class-name guards remain
for unrelated bolt/washer/nut/connector stacks until a real reuse case
justifies migrating them.

`CleatScrewed` and `ButtScrewed` require `wood_screw`. Service-panel retention
requires both `ordinary_wood_screw` and `exterior_use`, preserving the current
rule that a structural screw is not silently relabeled as an ordinary service
retainer.

### 4. A generic ordinary wood screw with lightweight geometry

Register `WoodScrew` as `wood_screw`:

```python
WoodScrew(
    diameter: float,
    length: float,
    material_key: str = "steel_galv",
    exposure: str = "exterior",  # closed: interior | exterior
    representation: str = "envelope",  # closed: envelope | represented_threads
    name: str | None = None,
)
```

The default geometry is a collision/render envelope: round head, smooth shank,
and conical tip. It deliberately omits represented threads and drive details.
The assumptions and generated documentation must say so. Dimensions, datums,
BOM identity, material, and installation semantics remain real model data.

`representation="represented_threads"` reuses the current thread geometry for
a view where that detail is worth its cost.

`ExteriorWoodScrew` remains registered and importable. It becomes a thin
compatibility wrapper fixed to exterior galvanized service and
`represented_threads`, preserving existing specs and geometry fingerprints.
The birdhouse deliberately migrates to `wood_screw` with the envelope
representation; its fastener geometry hashes therefore change by design and
must be reviewed, while older details do not change implicitly.

Structural screws retain their current represented-thread geometry and
structural-product-class identity. A representation option never promotes an
ordinary screw into a structural screw and never supplies capacity.

### 5. Parameterized service-panel semantics

Promote the private shared service-panel implementation to a public registered
`ServicePanelScrewed`, keyed as `service_panel_screwed`:

```python
ServicePanelScrewed(mode: str)  # closed: pivot | latch
```

The closed mode table maps:

- `pivot` to `pivoted_by` and install role `pivot_screw`;
- `latch` to `latched_by` and install role `latch_screw`.

Both modes:

- require exactly two parts and one ordinary exterior wood screw;
- allow/bond the screw to the frame and panel;
- order both members before screw installation;
- emit the operability edge for the selected mode;
- emit a straight-drive installation contract; and
- make no transfer claim, `bears_on`, or member-to-member `fastened_by` claim.

`PivotScrewed` and `ServiceLatchScrewed` remain registered thin subclasses with
their current zero-argument constructors and labels. Existing DetailSpecs
compile unchanged; future projects may use one parameterized type.

No DetailSpec schema change is needed. Component and connection `params` are
already resolved and passed as constructor keyword arguments by the compiler.

### 6. Separate semantic tests from CAD conformance

Component and connection semantics do not need to build solids. Tests for
registry selection, material truth, BOM wording, capability acceptance,
connection edges, transfer claims, and installation contracts must avoid
`Component.solid` entirely. At least one guard test monkeypatches `_build()` to
raise and proves the semantic connection suite still passes.

Geometry tests remain, but are narrow:

- one conformance test for the shared panel fabrication fold;
- wrapper equivalence tests for hardwood and cedar;
- one envelope screw bounds/volume test;
- one represented-thread compatibility test; and
- project-level adversarial geometry checks in the birdhouse detail gate.

Timing is reported by fresh-process benchmarks, not asserted with fragile
wall-clock thresholds inside ordinary pytest tests. A structural test proves
that envelope screws never call `threaded_shaft`; the benchmark then quantifies
the actual improvement.

The implementation consumes the semantic `--detail-gate` mechanism from the
active `codex/caddy-test-performance` work. It does not create a second
selection plugin. `family_birdhouse` receives a complete detail gate using the
contract vocabulary that lands on that branch. Shared compiler changes still
require one full repository gate before integration.

### 7. Measure and remove duplicate package rendering

The first complete birdhouse package contract took 403.22 seconds and produced
a 22 MB package, including a 14 MB GLB and 3.9 MB STEP file. Envelope screws
should remove most of the unnecessary fastener mesh complexity, but they do not
by themselves remove repeated work in the report pipeline.

Keep this increment narrow and project-proven:

- instrument cold package generation by phase before changing the pipeline;
- tessellate each placed part once for the five matplotlib still views, then
  reuse the immutable vertices/faces with view-specific camera and explode
  transforms;
- let the technical-document seam reuse an already-generated documentation
  directory instead of exporting the same model into a temporary directory;
- keep document-contract tests semantic and fast where renderer output is not
  the behavior under test; and
- retain one cold end-to-end package gate that proves HTML, images, STEP, GLB,
  manifests, hashes, and preview governance remain mutually consistent.

The benchmark report records phase timings, output sizes, and model/package
fingerprints before and after. Do not add a fragile wall-clock assertion to
ordinary pytest. The structural acceptance rule is that no placed part is
tessellated more than once for the five stills and the model documentation
export runs once per package build. A measured target of at least 2x faster
than the 403.22-second cold package baseline is a go/no-go objective; if it is
missed, profile the remaining dominant phase before expanding scope.

## Compatibility Contract

The implementation must preserve:

1. imports and registry keys for `HardwoodPanel`, `CedarPanel`,
   `ExteriorWoodScrew`, `PivotScrewed`, and `ServiceLatchScrewed`;
2. compilation of existing specs without parameter edits;
3. panel dimensions, datums, material/BOM output, fabrication steps, and
   single-feature installed geometry;
4. existing exterior-screw dimensions, datums, BOM output, and detailed
   geometry when accessed through `ExteriorWoodScrew`;
5. pivot/latch graph edges, absence of structural claims, and installation
   roles; and
6. ordinary pytest collection when `--detail-gate` is not supplied.

The only intentional pilot-output geometry change is the birdhouse's migration
from represented-thread exterior screws to generic envelope wood screws.

## Failure Behavior

- Unknown `material_key`, exposure, representation, or service-panel mode:
  fail at construction/compile time with the allowed values.
- Missing required hardware capabilities: fail before deriving graph or
  installation facts, naming the slot, required tags, actual tags, and part.
- Missing material-specific engineering property: remain unmodeled/UNKNOWN;
  never infer a value from a species label.
- Unknown Blender procedural tag with registered manifest color: warn and use
  the registered flat color.
- Unknown material with no registry/manifest identity: compiler failure; no
  silent gray success.

## Explicitly Deferred

- A sourced `MaterialProperties` model for density, movement, strength, or
  durability. Add it alongside the first validation/BOM rule that consumes a
  property and can define source, species, grade, and condition.
- Folding plywood, dimensional lumber, metal sheet, or arbitrary profiles into
  `FabricatedPanel`.
- Migrating every class-name connection role guard to capabilities.
- Separate collision and presentation solids on every `Component`. The smooth
  ordinary-screw envelope captures the measured pilot need with much less
  platform risk.
- Persisting test verdicts or weakening the full shared-platform release gate.
- A general rendering-engine, collision broad-phase, or persistent artifact
  cache rewrite. The pilot first removes measured duplicate work through
  explicit reuse seams; broader caching requires its own cross-project design.

## Acceptance

The increment is accepted when:

1. all compatibility tests above pass;
2. a synthetic mahogany-like registered material can compile through
   `fabricated_panel` without adding a panel class or Blender shader builder;
3. a synthetic new `WoodScrew` subtype/capability instance works in the chosen
   screw connections without editing accepted-class tuples;
4. semantic connection tests prove they do not build CAD;
5. the envelope screw path proves it never calls `threaded_shaft` and a
   fresh-process benchmark reports its improvement over represented threads;
6. the complete `family_birdhouse` detail gate passes in a fresh process and
   its timing is recorded alongside the 72.88-second extension baseline and
   the observed 17:12 full-suite run;
7. the full repository suite passes once after all shared changes; and
8. the birdhouse package is regenerated, its intentional screw-fingerprint
   delta is reviewed, and implementation returns to the exact blocked design
   step; and
9. a cold birdhouse package benchmark records phase/output deltas, proves one
   documentation export and one tessellation per placed part for all five
   stills, and either meets the 2x objective or identifies the remaining
   dominant phase without weakening the end-to-end package gate.
