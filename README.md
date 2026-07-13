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
`DetailAssembly` + exporter-function API. **For a new detail, read
`details/rock_anchor.py` first instead** — it's the annotated `Detail`
subclass every new detail should copy (frozen params, `assemble()`,
`validation_spec()`, `render()`).

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

### Optional domain packs

A domain pack compresses repeated trade knowledge into a small authoring
surface, then lowers it into the ordinary DetailSpec language. Packs are
explicit and versioned; merely installing or importing one changes nothing in
an existing spec.

The first vertical slice is `cabinetry.frameless@1`: conventional-shop,
two-door frameless base cabinets with an adjustable shelf, independent toe
base, Blum hinge machining, a modeled surveyed stud wall, shop artifacts, and
field installation instructions. It supports either one cabinet or a touching
straight run. `vanity.frameless@1` adds one wall-hung two-door vanity with
verified 2x8 backing, structural anchors, a plumbing keepout, and its own
installation sequence. Compile a checked-in example with:

```python
from detailgen.packs import compile_project_file

project = compile_project_file("details/frameless_base_cabinet.project.yaml")
project.require_release()               # pack rules + existing geometry sweep
print(project.manifest_json())          # versions, evidence, shop/install data
```

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
Drawer bases, sink-base cutout systems, wall cabinets, tall cabinets,
appliances, fillers, and corner units remain future profile/pack work rather
than parse-and-ignore vocabulary.

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
pytest              # ~400 tests: smoke + framework + spec + per-detail
pytest -n auto      # same suite, parallel across CPU cores (pytest-xdist)
```

The suite spans the geometry primitives, the Connection library, the DetailSpec
compiler + its equivalence oracle (the compiled `platform.spec.yaml` reproduces
the imperative detail exactly), the coverage/UNKNOWN honesty rules, the Evidence
Graph (completeness invariants + cross-process determinism), and each shipped
detail. Many guards are written mutation-style — they assert both that clean
data passes AND that corrupted data is REJECTED, so a guard can't rot into a
tautology.

`-n auto` isn't the default (no `addopts` entry) so a single debugging
invocation — `pytest --pdb tests/test_foo.py::test_x` or `-s` for prints —
stays simple; xdist doesn't support interactive `--pdb`/live `-s` output
under `-n`.
