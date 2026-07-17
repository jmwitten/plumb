# plumb

A semantic compiler for real-world carpentry: declarative specs become 3D
models, checked joinery, derived build order, and human-readable build
documents — cut plans, dimensioned drawings, step-by-step assembly. Every
claim is machine-verified against the model; what can't be proven is
reported honestly, never papered over.

Parametric 3D construction details built on [CadQuery](https://cadquery.readthedocs.io/):
lumber, concrete, fasteners, and connectors composed into validated assemblies,
exported as STEP / STL / GLB / PNG and rendered engineering sheets.

More than a modeller, it is a **semantic construction compiler**: an author
declares intent (a `DetailSpec`, or the imperative `Detail` API), the platform
DERIVES the rest — joints from `Connection` types, an [Evidence
Graph](#evidence-graph) of *why every conclusion holds*, a [coverage
matrix](#coverage-matrix--the-unknown-rule) that reports `UNKNOWN` for what it
did NOT check rather than implying a clean bill of health. The reusable
architecture is the product; the four shipped dacha-zipline details
(`details/rock_anchor.py`, `tree_attachment.py`, `trolley_launch.py`,
`platform.py`) are its first consumers.

## Setup

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]" -c constraints.txt
```

`constraints.txt` pins the exact dependency versions (notably
`cadquery`/OCCT) that the checked-in reference outputs were built against —
OCCT's boolean/tessellation results are version-sensitive, so install with
it for bit-reproducible builds. Omit `-c constraints.txt` to pick up newer
compatible versions instead.

## Quick start

```bash
python details/deck_ledger_example.py
```

That builds the reference detail (deck ledger + rim + joist hanger + lags),
runs the validation sweep, and writes `outputs/deck_ledger_example.{step,stl}`
plus iso/front PNG previews. It's a walkthrough of the low-level
`DetailAssembly` + exporter-function API.

For an ordinary new project, query the compact live authoring vocabulary,
author a `DetailSpec`, and invoke the generic full-package compiler:

```bash
.venv/bin/python -m detailgen.authoring
.venv/bin/python -m detailgen.package details/example.spec.yaml \
  --out outputs/example --preview
```

For a fresh product, the registry-backed scaffolder removes the need to invent
the nested DetailSpec shape. Give it only explicit component values and
placements:

```bash
.venv/bin/python -m detailgen.authoring scaffold \
  --slug example_detail \
  --out details \
  --component base:slab \
  --set 'base.width=12 in' \
  --set 'base.length=18 in' \
  --place 'base={raw: {at: [0, 0, 0]}}'
```

It writes `details/example_detail.spec.yaml` and the discoverable
`details/example_detail.cert.yaml`, after loading and compiling the spec and
resolving the certification contract. It never guesses dimensions, datums,
placements, or validation claims. An omitted placement is DetailSpec's identity
placement at the origin; with multiple components that is structurally valid
but physically unresolved until the author supplies relationships or explicit
placements.

Bare numeric component and placement lengths are millimeters, and generated
scaffolds declare `units: mm` to make that contract explicit. To author another
unit, pass a unit-suffixed YAML string such as `--set 'member.length=42 in'`.
The top-level `units` field controls `$`/`=` authoring expressions; it does not
reinterpret bare constructor or raw-placement numbers.

Filesystem/output slugs may begin with a lowercase letter or digit, so a name
such as `2x4_frame` is preserved exactly in the generated spec, certification
sidecar, and package path. Component IDs still begin with a letter because they
are internal reference identifiers.

Dimension checks use the placed solid's **world-axis bounding-box** measures.
`xlen`, `ylen`, and `zlen` are projections on those world axes, so they change
when a member rotates. No rotation-invariant member-length measure currently
exists; omit that claim or extend the platform instead of calling a rotated
member's `xlen` its length.

For lumber `end_cuts`, `miter_angle_degrees` means **degrees off square**, not
the acute angle between joined members. Every cut mapping must contain `end`,
`miter_angle_degrees`, and `long_face`, and cut members must also author
`length_semantics: long_point_to_long_point`.

Use `.venv/bin/python -m detailgen.authoring grammar` when only the nested field
shapes and conventions are needed. Its bounded output omits the full component
and connection registries. For a connection that requires hardware, declare
each hardware item as a component and attach its id with
`--connection-hardware INDEX=ID[,ID...]`; scaffold verification executes the
validation pipeline and rejects declarations that would make package generation
crash. A definite validation failure also stops publication and reports every
blocker with datum mate guidance for parts seated on neighbors. Honest `UNKNOWN`
findings remain allowed in a preview scaffold; unresolved evidence is not
relabeled as passing.

The compiler generates the model, standard views, technical/fabrication/
assembly documents, review evidence, CSVs, hashes, and final package manifest
from one compiled detail. The installation audit renderer remains available as
an explicit internal surface but is not emitted in the default package.
Ordinary projects require no source-code registration or project-specific
renderer dispatch. Read framework source or extend a registry only when the
compact manifest proves that a required capability is absent.

Orchestrators must consume `workflow.schema` and `workflow.tests` from this
live manifest rather than copying test policy into their own instructions. An
unsupported workflow schema is a fail-closed compatibility error.

## Architecture

```
details/            One runnable script per construction detail (the "drawings")
assets/
  manufacturer/     Vendor STEP files (Simpson etc.) — load via assemblies.load_step
  textures/         Image assets for future rendered output
src/                Importable as the `detailgen` package
  core/             Component base class, units (IN/FT -> mm), materials,
                    registry, ontology (Role/LoadClass/TransferCapability),
                    persistent solid caches
  components/       Primitive parts: lumber, concrete, fasteners, connectors
  assemblies/       DetailAssembly (placement, colors, BOM) + the Connection
                    library (FaceMountHanger / ToeScrewed / … + registry)
  details/          The `Detail` lifecycle base class
  spec/             DetailSpec: a declarative YAML/JSON language + compiler
  design_review/    Precedent-first design selection, reports, and lifecycle gates
  packs/            Opt-in domain front ends that lower into DetailSpec
  validation/       The sweep -> ValidationReport, plus the coverage matrix,
                    the Evidence Graph, spatial invariants, load-path proof
  rendering/        export_step / _stl / _glb / _png, the consolidated report,
                    Blender path, and the interactive web viewer
outputs/            Generated artifacts (gitignored)
```

### The Component contract

Every part inherits `detailgen.core.Component`:

1. **Parameters in `__init__`**, stored in mm (`from detailgen.core import IN, FT`).
2. **`_build()`** returns a `cq.Workplane` in the part's *local frame*, with the
   datum documented in the class docstring. Parts never bake in an installed
   orientation — placement belongs to the assembly.
3. **`check()`** returns human-readable parameter problems (empty = OK).
4. Geometry is lazy and cached via `.solid`; don't mutate parameters after
   first build.

`src/components/lumber.py` is the annotated reference implementation — read it
before writing a new component.

### Assemblies

`DetailAssembly.add(component, at=..., rotate=[("Z", 90), ...])` places parts:
rotations about local axes applied in order, then translation. From an
assembly you get `to_cq_assembly()` (colored, for STEP/PNG), `compound()`
(fused, for STL), `check()`, and `bom()`.

### Validation

`validate_assembly(assembly, expected_overlaps=..., contacts=..., bearings=...,
bonds=..., through_holes=..., ground=..., spatial=...)` runs the whole-assembly
sweep: a pairwise interference check (fastener-into-wood pairs allowlisted via
`expected_overlaps`), rigorous min-distance + bearing-area proofs (`bearings`,
preferred over the coarse bbox `contacts`), floating-part connectivity
(`bonds` + `ground`), fastener through-hole probes, and every part's parameter
problems — collected into a `ValidationReport`. Every part reference accepts a
`Placed` handle (rename-proof) or a display name; a bad reference raises loudly,
never resolves silently. `report.require_clean()` raises on any failure, and the
`Detail.render()` verb is gated on it, so broken geometry cannot reach
`outputs/`.

### Rendering

```python
detail.render("outputs/rock_anchor")        # GLB + STEP + manifest + report,
                                            # gated on a clean validation report
python scripts/consolidated_report.py       # all four details -> ONE self-
                                            # contained HTML build document
```

Low-level exporter functions (`export_step` / `export_stl` / `export_glb` /
`export_png`, VTK camera names in `rendering/export.py`) remain available for
the `DetailAssembly` API. STEP carries per-part names + material colors; STL is
a single fused mesh; GLB feeds the interactive web viewer
(`rendering/web_viewer/`, vendored three.js) whose node names join to per-part
spec payloads for hover tooltips. Presentation-quality output uses the optional
Blender path (`render_blender`, needs a Blender install).

## The semantic compiler layer

The north star: reduce the construction knowledge an author must explicitly
encode while increasing what the platform can DERIVE, PROVE, EXPLAIN, and AUDIT.
The pipeline is `Intent → DetailSpec → Construction Graph → Evidence Graph →
Proven Invariants → Generated Artifacts`.

### Connections (the joint library)

A `Connection` declares a joint by intent — "these parts are face-mounted by
this hanger" — and a registered `ConnectionType` DERIVES the checks: required
hardware, bearing pairs, allowed fastener intersections, bonded pairs, and
Construction-Graph edges (`bears_on` / `fastened_by` / `installed_before`).
The library ships `FaceMountHanger`, `ToeScrewed`, `RailCapScrewed`,
`BoltedClamp`, and a threaded-rod epoxy anchor, resolved through the
`connection_types` registry (`from detailgen.assemblies import
FaceMountHanger, …`). Declaring a joint replaces hand-writing its whole
validation spec — the derivation is logged with provenance, never hidden.

### DetailSpec (the declarative language)

A detail can be authored as data instead of code — a YAML/JSON `DetailSpec`
compiled to the same validated `Detail`:

```bash
python -m detailgen.spec details/platform.spec.yaml            # compile + report
python -m detailgen.spec details/platform.spec.yaml --render outputs/platform
```

The language expresses `params` + derived dimensions (`= expr`), component
placement (a `mate` onto a neighbour's datum, or a `raw` transform escape
hatch), `repeat` blocks over a derived count (`repeat: {var: j, count: '=
n_joists'}` — the author declares a family and a spacing rule, the compiler
derives how many, threading `{var}={index}` into each instance's provenance),
`connections`, a `validation` block (bearings / bonds / through-holes /
dimensions / ground / `spatial`), and load-system `roles`. `platform.spec.yaml`
reproduces the imperative `platform.py` byte-for-byte; `detailgen.spec.metrics`
reports the compression it buys — genuine derived : authored facts, escape
hatches excluded from the honest headline.

Dimensional lumber supports semantic miter end cuts without raw geometry. A
cut's `miter_angle_degrees` is the conventional saw setting off square; the
authored member length must explicitly be long-point to long-point. The
physical cut faces are available as `cut_near` and `cut_far` mating datums,
while `end_near` and `end_far` remain the X=0/X=length reference planes:

```yaml
params:
  nominal: 2x4
  length: 48 in
  length_semantics: long_point_to_long_point
  end_cuts:
    - {end: near, miter_angle_degrees: 30, long_face: top}
    - {end: far, miter_angle_degrees: 30, long_face: top}
```

### Precedent-first design selection

New details can opt into a structured design review before production modeling.
The sidecar record captures the design brief, source provenance, materially
different concepts, a ten-criterion comparison, novelty and part-purpose
reviews, and an evidence-linked decision. Validation rejects missing evidence,
near-duplicate concepts, unsupported novelty, incomplete matrices, empty or
placeholder prose, and copied comparison boilerplate.

```bash
python -m detailgen.design_review validate details/armchair_caddy.design-review.yaml
python -m detailgen.design_review report \
  details/armchair_caddy.design-review.yaml \
  --output outputs/design-reviews/armchair_caddy.html
python -m detailgen.design_review gate \
  details/armchair_caddy.spec.yaml --stage modeling
python -m detailgen.design_review gate \
  details/armchair_caddy.spec.yaml --stage delivery
```

A DetailSpec opts in explicitly with a relative sidecar path and selected
concept:

```yaml
design_review:
  record: armchair_caddy.design-review.yaml
  selected_concept: reinforced_miter
```

Drafts still compile so concepts can be investigated. Production promotion
requires a named approval of the current selection fingerprint. Delivery then
requires the selected concept to be marked `implemented` and a second named
confirmation of both the selection and exact model fingerprints. Specs without
the binding retain the legacy lifecycle. The generated design-selection HTML is
a developer artifact and is not inserted into the customer build manual.

### Optional domain packs

A domain pack compresses repeated trade knowledge into a small authoring
surface, then lowers it into the ordinary DetailSpec language. Packs are
explicit and versioned; merely installing or importing one changes nothing in
an existing spec.

The first vertical slice is `cabinetry.frameless@1`: conventional-shop
frameless base cabinets with an independent toe base, a modeled surveyed stud
wall, shop artifacts, and field installation instructions. Its bounded
archetypes are `base_two_door@1` (adjustable shelf and Blum hinge machining)
and `drawer_base_three@1` (three wood drawers on pinned Blum MOVENTO soft-close
runners, locking devices, lateral stabilizers, applied fronts, and pulls). The
two-door archetype also supports a touching straight run. `vanity.frameless@1`
adds one wall-hung two-door vanity with verified 2x8 backing, structural
anchors, a plumbing keepout, and its own installation sequence. Compile the
checked-in 40-inch three-drawer clothing cabinet with:

```python
from detailgen.packs import compile_project_file

project = compile_project_file("details/frameless_three_drawer_40.project.yaml")
project.require_release()               # pack rules + existing geometry sweep
print(project.manifest_json())          # versions, evidence, shop/install data
```

Generate its self-contained build document (six drawings, interactive model,
cut/edge/hardware/machining schedules, evidence, and exact shop-to-install
sequence) with:

```bash
python scripts/cabinetry_project_report.py \
  details/frameless_three_drawer_40.project.yaml \
  --out outputs/frameless_three_drawer_40/build_document.html
```

The drawer implementation has a parent-independent `DrawerBankModel` seam so a
future split-bank vanity can reuse the same sizing, machining, hardware, load,
and validation rules. That seam is internal: the public v1 archetype remains
the narrow, replayable three-drawer base rather than accepting arbitrary
layouts.

Versioned archetypes remove repetitive declarations while expanding into the
same strict schemas. These examples demonstrate derived run placement and a
floating vanity draft:

```python
run = compile_project_file("details/frameless_base_run.compact.project.yaml")
run.require_release()

vanity = compile_project_file("details/floating_vanity.compact.project.yaml")
assert not vanity.release_ready  # project-specific mount review still required
```

The profile uses ANSI/KCMA A161.1-2022 as a performance reference and carries
calculated, manufacturer, field, and unknown evidence separately. It **does not claim KCMA certification**: cyclic, impact, sustained-load, and finish tests
remain explicitly `not_performed` unless real evidence is supplied. A floating
vanity likewise does not become structurally adequate merely because a listed
screw and manufacturer installation precedent exist: release requires a
referenced, project-specific review of the complete custom wall-mount load path.
Arbitrary drawer counts, mixed door/drawer public layouts, sink-base cutout
systems, wall cabinets, tall cabinets, appliances, fillers, and corner units
remain future profile/pack work rather than parse-and-ignore vocabulary.

### Coverage matrix — the UNKNOWN rule

`report.coverage_matrix()` reports a verdict per invariant family (Physical
geometry, Spatial intent, Construction completeness, Functional use, Load-path
representation, Structural capacity, Code compliance). The load-bearing rule:
a family no check touched reads **`UNKNOWN — NOT ANALYZED`**, never `PASS`; and
a single failing or unresolvable check flips a family `PASS → UNKNOWN`, never
silently staying green. The framework's job is to be honest about what it has
NOT proven, so a clean report can never be mistaken for a completeness claim.

### Evidence Graph

Validation is treated as PROOF GENERATION. `detail.evidence_graph` (an
`EvidenceGraph`, built lazily from lifecycle outputs — building it changes no
validation outcome) is one queryable graph linking authored declarations →
derived facts → generated checks/findings → family verdicts, each node tagged
with its knowledge source (`authoritative` / `verified_heuristic` /
`llm_hypothesis`, the last non-build-blocking by construction). Four queries
answer, for any part: `what_is`, `why_here` (authored vs derived provenance),
`how_verified` (findings + verdicts + a readable chain — never a bare "PASS"),
and `what_depends_on` (construction neighbours + change impact). Serialization
is canonical (deterministic across processes); queries are O(degree) via an
adjacency index.

### Ontology & load-path representation

`detailgen.core.ontology` seeds `Role` / `LoadClass` / `TransferCapability`:
a `ConnectionType` carries provenance-tagged claims about which load classes it
transfers, and `validation/loadpath.py` proves a support→ground path is
REPRESENTED (capacity-free reachability gated by those claims — e.g. "downward
load path REPRESENTED: leg → angle → rod → boulder"). This REPRESENTS a load
path; it never claims the structure is adequate — Structural capacity stays
`UNKNOWN`.

### Spatial invariants

Declared redundancies about *where* and *which-way* parts sit, checked against
the compiled geometry (validation-only — they never move a part). `SymmetricAbout`
(with an explicit-pairs or a mirror-by-name selector) proves part pairs are
AABB mirror images about a coordinate plane; `FacesToward` / `FacesAway` prove
the sign of a facing's projection toward a target. A declared invariant that
resolves to zero pairs FAILS loudly rather than silently proving nothing.

### Persistent caches

Built local solids are cached in-run (keyed on `Component.cache_key()`) and in
a persistent on-disk tier (`core/diskcache.py`), so N identical placed parts
pay the CAD-kernel cost once and unchanged geometry survives across runs; the
consolidated report additionally hash-gates render reuse.

## Units

Internal geometry is always **millimeters**. Write inputs with the helpers so
scripts read like a cut list: `Lumber("2x8", length=8 * FT)`,
`LagScrew(0.5 * IN, 4 * IN)`. Convert back for labels with
`inches()` / `feet()` / `fmt_in()` (the last snaps to 1e-6" before display
rounding, so the inch↔mm float-ordering residual can't tip a boundary value to
a different string — display only, geometry untouched).

## Adding a new detail

1. Copy `details/rock_anchor.py` and subclass `detailgen.details.Detail`.
2. Build components; add any missing part types under `src/components/`
   following the Component contract.
3. Place parts in `assemble()`, declare checks in `validation_spec()`, then
   `render()` — gated on a clean report, so there's no way to export a dirty
   detail.

## Tests

```bash
pytest --detail-gate family_birdhouse --detail-cadence inner -q
pytest --detail-gate family_birdhouse --detail-cadence release -q
pytest --platform-tier integration -q
pytest --platform-tier audit -q
pytest -q -n 4      # unfiltered verification across every scope
python -m detailgen.certification details/my_build.cert.yaml
```

Every collected test has an explicit owner and cadence in
`tests/test_scope_manifest.csv`. A named detail gate applies the reusable
accuracy contracts to that accepted model plus its owner-specific facts. The
inner cadence includes compile, geometry, normal collision/validation,
connections, fabrication, BOM, governance, intent, and determinism. Release
adds that build's document/package checks.

Platform integration tests exercise shared subsystems using real data. Platform
audit tests are intentionally exhaustive or adversarial: for example, they
alter geometry to verify invalidation, corrupt baselines to prove the guard
detects it, or compare the bbox shortcut with exact intersection checks across
every pair. Those checks certify the platform, not an accepted document, so
they do not run in a named build gate.

The unfiltered suite spans all of those scopes: geometry primitives, the
Connection library, the DetailSpec compiler and equivalence oracles,
coverage/UNKNOWN honesty rules, Evidence Graph invariants, and every shipped
detail.

`-n auto` isn't the default (no `addopts` entry) so a single debugging
invocation — `pytest --pdb tests/test_foo.py::test_x` or `-s` for prints —
stays simple; xdist doesn't support interactive `--pdb`/live `-s` output
under `-n`.

Every standalone build can opt into the generic certification engine by adding
`details/<slug>.cert.yaml` beside its spec. Contracts are discovered from the
filesystem, so a new build needs no Python test module or central registry edit.
Pytest derives the generic node's inner-cadence scope from that discovered
contract at runtime; only bespoke product tests need explicit rows in
`tests/test_scope_manifest.csv`.
The YAML records the build's declarative intent: expected parts and
connections, validation findings, fabrication folds, BOM bounds, governance,
and any explicit decisions. The shared engine supplies the tests. V1 standalone
contracts leave `deliverables: []`; a requested deliverable fails closed until
an adapter supplies typed evidence for it.

A named gate with a canonical standalone subject also receives automatic
integrity evidence independent of every bespoke test marker. The binding comes
first from `details/<slug>.cert.yaml`; otherwise Plumb accepts
`details/<slug>.spec.yaml` or the hyphen-to-underscore filename equivalent. The
inner cadence freshly compiles that spec and requires authoritative validation
with `ok: true` and zero blocking findings.

The release cadence additionally requires a current package at
`build/<slug>/package-manifest.json`. Its spec identity, validation status,
current assembly and governance fingerprints, exact declared artifact set, and
every artifact SHA-256 must reconcile. A preview manifest remains a preview and
a delivery manifest must still satisfy delivery readiness; the gate never
rewrites `not-run` or skipped tests as passed. Package-manifest v1 has no
spec-content hash, so current source identity is limited to its exact spec
filename while model freshness uses the persisted assembly hash.

Legacy or composite owners without a one-to-one certification subject or
normalized spec filename keep their existing owner-specific gates until they
are explicitly migrated. That compatibility path does not claim automatic
package integrity.

Use the detail gate as the inner loop when a change is owned entirely by one
build. Documents are release-cadence evidence, not inner-cadence model
accuracy. Each gate starts with fresh temporary caches, compiles twice, and
never reads a result from an earlier run.

Certification fails closed on inaccurate evidence. A declared, non-safety
uncertainty can produce a visible warning; unresolved high-severity decisions
produce exit code 2 and block release without prompting, which keeps automated
runs autonomous and auditable.

Run the platform integration tier for shared compiler, validation, geometry,
rendering, pack, or cache changes. Run the audit tier when changing bbox
prefiltering, affected-region invalidation, revision identity, or their test
oracles. The unfiltered suite remains the final repository-wide verification.
A detail gate answers whether one product still builds correctly; it does not
claim the platform is unchanged.
