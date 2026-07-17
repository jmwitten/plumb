# construction-detail-generator

Parametric 3D construction details on CadQuery. Components (lumber, concrete,
fasteners, connectors) compose into validated assemblies, exported as
STEP/STL/PNG/GLB and rendered engineering sheets. Built 2026-07 as reusable
architecture. Four shipped details, all dacha-zipline elements:
`details/rock_anchor.py`, `details/tree_attachment.py`,
`details/trolley_launch.py`, `details/platform.py` — see the zipline drawings
in the JoelBrain vault, `01_Projects/03_Dacha/`.

**Roadmap execution state lives in `.superpowers/sdd/progress.md`** (untracked
ledger): completed waves, user directives (north star, doc voice, generation-
speed target), and the resume brief for the next work phase. Read it before
starting roadmap work. The roadmap itself: `docs/FRAMEWORK_ROADMAP.md`.

**Ordinary-project context boundary:** first run
`.venv/bin/python -m detailgen.authoring`, author the smallest sufficient
`DetailSpec`, then run `.venv/bin/python -m detailgen.package <spec> --out
<dir> --preview`. Do not read `docs/FRAMEWORK_ROADMAP.md`, the progress ledger,
implementation source, unrelated specs, or prior project manuals for an
ordinary project. Load roadmap/progress state only for actual framework work;
load implementation source only after the manifest or compiler reports a
concrete capability gap. No source registration is required for an ordinary
new spec.

**Area of opportunity — reading initial context:** keep preflight bounded to
the authoring manifest, the accepted brief, and the spec being authored. The
simple-project timing experiment showed that broad initial reading can cost
more than compilation and full document generation combined.

Components are **engineering-grade**, not envelopes: bent steel angles have a
real inner bend radius + punched holes (`_geometry.angle_profile`), fasteners
carry a thread *representation* (`_geometry.threaded_shaft`) and hex washer-face
chamfers (`_geometry.hex_prism`), lumber has eased edges. Threads are a
revolved V-groove (never a helix — that's the OCC fragility hotspot), pitch
exaggerated for legibility.

## Environment

```bash
source .venv/bin/activate        # Python 3.12, cadquery 2.8 already installed
python details/deck_ledger_example.py       # simple example: build, validate, export
python details/rock_anchor.py               # any detail: validate + BOM
python details/rock_anchor.py --render outputs/rock_anchor   # + GLB/STEP/manifest/report
python scripts/consolidated_report.py       # the full model-backed build document
                                            # (all 4 details -> ONE self-contained HTML,
                                            # copied to the vault; hash-gated fast reuse
                                            # of unchanged renders)
pytest --detail-gate family_birdhouse --detail-cadence inner -q
pytest --detail-gate family_birdhouse --detail-cadence release -q
pytest --platform-tier integration -q
pytest --platform-tier audit -q
pytest -q -n 4                  # unfiltered repository-wide verification
python -m detailgen.spec details/platform.spec.yaml   # compile a DetailSpec + print
                                            # its derivation report + compression
.venv/bin/python -m detailgen.authoring      # compact live authoring vocabulary
.venv/bin/python -m detailgen.package details/example.spec.yaml \
  --out outputs/example --preview            # complete generic package
```

## Test scope

`tests/test_scope_manifest.csv` classifies every collected node and is checked
fail-closed during ordinary collection. A detail's inner gate runs accepted
model/build facts, including normal collision validation; release adds only
that detail's document/package evidence. Platform integration covers shared
subsystems with real data. Platform audit contains exhaustive or adversarial
oracles such as all-pairs intersection equivalence, artificial geometry edits,
and deliberate baseline corruption. Never put those platform self-tests in a
document gate merely because they use a real detail as their fixture.

**Component-extension scope:** before adding physical vocabulary, run
`.venv/bin/python -m detailgen.authoring component-guide` and author a
`detailgen/component-extension/v1` contract. `catalog_variant`,
`new_primitive`, and `semantic_component` use `component-check` with a hard
60-second combined budget; a registry/catalog addition alone does not select
`platform_integration`. `cross_layer_complex` returns `ESCALATE` and then uses
the owning-layer regression plus only the applicable platform/product gates.

**stdlib-shadow gotcha**: `details/platform.py` shadows the stdlib `platform`
module that numpy imports transitively. Run detail files as scripts (they
carry a sys.path guard) or import them by explicit file path under a distinct
module name — never put `details/` at the front of `sys.path`.

Blender renders (optional, needs a Blender install; path via `BLENDER` env or
`/Applications/Blender.app`): `detailgen.rendering.render_blender(detail, out)`
produces presentation / exploded / hidden-line / dimensioned views. The Blender
script `src/rendering/_blender_render.py` runs *inside* Blender (not imported);
dimension labels are a PIL overlay (`rendering/overlay.py`) driven by
`camera_map.json` the render writes.

`src/` is importable as the **`detailgen`** package (mapped in pyproject) —
`from detailgen.components import Lumber`. Editable install, so source edits
apply immediately.

## Rules that keep this codebase coherent

- **Units**: geometry is always mm internally; public APIs take `n * IN` /
  `n * FT` from `detailgen.core`. Never hardcode raw mm for real-world sizes.
- **Component contract** (documented in `src/core/base.py`, reference
  implementation `src/components/lumber.py`): params in `__init__`, geometry
  in `_build()` in a *local frame with the datum documented in the class
  docstring*, parameter problems from `check()`. Components never bake in an
  installed orientation — placement belongs to `DetailAssembly.add()`.
- **Placement**: `place(part, "datum").on(handle, "datum", offset=..., rotate=...,
  flip=...)` is the preferred way a part seats on a neighbor — a datum encodes
  a real surface (origin *and* orientation), so mating two datums makes a
  positional sign error unrepresentable rather than a silently valid-but-wrong
  solid. `add(component, at=..., rotate=...)` remains the low-level escape
  hatch, for parts positioned off a global measurement or a genuine free DOF
  (a leveling nut's hand-set height, a driven bolt's tightened depth) rather
  than off a neighbor. Decision rule: seated on a neighbor → mate; positioned
  by global measurement or a genuine free DOF → add.
- **Placement is computed (deterministic), not solver-driven.** cq.Assembly
  constraints may cross-check a chain, but solver output is never canonical and
  is trusted only if it reproduces the computed placement (see
  `RockAnchor.cross_check`). Some joints have legitimate free DOF (a leveling
  nut's height) the solver can't resolve — that's why.
- **New details** subclass `detailgen.details.Detail`: a frozen `Params`
  dataclass, then the lifecycle params → `assemble()` → `validate()` →
  `render()`. `render()` is the only public export verb and is gated on a
  clean validation report — there's no way to export a dirty detail through
  the `Detail` API. Placed parts are retrievable via `self["name"]` (no
  threading a handles dict back out); dimension callouts (`callouts()`)
  derive their label text from the live param value so they can't drift from
  the geometry they annotate. `details/rock_anchor.py` (class `RockAnchor`)
  is the reference to copy; `details/deck_ledger_example.py` demonstrates the
  low-level `DetailAssembly` + exporter-function API directly.
- **Validation thresholds** live in `detailgen.core.config.Tolerances`
  (`DEFAULT` reproduces the legacy hardcoded constants exactly); a detail
  overrides them by returning a `replace(DEFAULT, ...)` instance from
  `validation_spec()["tol"]`. Mesh/tessellation tolerances
  (`MESH_TOL_LINEAR`/`MESH_TOL_ANGULAR` in `core/buildinfo.py`) are
  deliberately kept as separate, fixed constants, not `Tolerances` fields —
  see that module's docstring for why.
- **Validation depth**: `validate_assembly` takes `bearings` (rigorous
  min-distance + bearing-area proof via `check_bearing`), `bonds` +
  `ground` (floating-part connectivity), and `through_holes` (fastener probes),
  in addition to `expected_overlaps` / `contacts`. Prefer `bearings` over the
  coarse bbox `contacts` for real details.
- **Fastener-into-wood/nut overlaps are expected** — allowlist those pairs via
  `expected_overlaps`; anything else intersecting is a bug in the detail.
- **BOM**: `detail.bom_table()` aggregates identical parts into qty rows
  (item/material/dimensions/source/assumptions). Give parts a `bom_label()`,
  `describe()`, `assumptions()` for readable rows.
- Vendor STEP files go in `assets/manufacturer/`, loaded with
  `detailgen.assemblies.load_step()` — don't hand-model specific SKUs.
- Renders: quick VTK PNG cameras are named in `rendering/export.py` `VIEWS`.
  For presentation-quality output use the Blender path (above). Check which side
  of the detail the hardware faces before picking views.
- **Generated documents are contractor-facing and standalone** (user
  directive): no references to prior versions or corrections; field-fit items
  phrased as site-verification instructions. The voice is encoded in
  `scripts/consolidated_report.py` — keep it that way.
- **Interactive viewer**: `src/rendering/web_viewer/` (vendored three.js r147
  + `build_viewer_payload()`); GLB node names == `Placed.name`, joined to
  per-part spec payloads for hover tooltips — `tests/test_viewer_data.py`
  enforces the join. The payload contract is the reuse surface for future 2D
  drawing sheets.
- `outputs/` is gitignored; artifacts are regenerated, never committed. Final
  deliverables for a detail are copied into the JoelBrain vault
  (`05_Attachments/Organized/Zipline Platform Drawings/`) when it ships.

## The semantic compiler layer (Waves 2–3)

The platform is a **semantic construction compiler**, not just a modeller: an
author declares intent and the compiler derives, proves, explains and audits
the rest. The layer sits on top of the Component/Assembly primitives above.

- **Connections** (`src/assemblies/connection.py`): a `Connection` declares a
  joint by intent; a registered `ConnectionType` (`connection_types` registry:
  `face_mount_hanger` / `toe_screwed` / `rail_cap_screwed` / `bolted_clamp` /
  `threaded_rod_epoxy_anchor`) DERIVES its checks — required hardware, bearing
  pairs, allowed intersections, bonded pairs, Construction-Graph edges — as
  `DerivedFact`s with provenance (`compile_connections`). Declaring a joint
  replaces hand-writing its validation spec. Prefer a Connection over a raw
  `validation_spec()` block when a joint type fits.
- **DetailSpec** (`src/spec/`): a declarative YAML/JSON detail compiled to the
  same validated `Detail` (`compile_spec(load_spec_file(path))`, or `python -m
  detailgen.spec …`). Expresses `params` + `= expr` derived dimensions,
  `mate`/`raw` placement, `repeat` over a derived count (index threaded into
  each instance's provenance), `connections`, a `validation` block, and load
  `roles`. `details/*.spec.yaml` compile oracle-equal to the imperative
  `details/*.py`; `spec/metrics.py` reports compression (genuine derived :
  authored, escape hatches excluded from the honest headline). The imperative
  `Detail` API stays the P3 escape hatch for geometry the language can't yet say.
  A DetailSpec doubles as a **fragment**: `details/site.spec.yaml` composes the
  same specs into one site model (below), and the direction of travel is that a
  "detail" becomes a *view* of that model rather than a separately-authored doc.
- **Optional domain packs** (`src/packs/`): an explicitly activated, versioned
  front end compiles domain vocabulary into an ordinary `DetailSpecDoc`; the
  public entry point is `compile_project_file`. A pack is a knowledge-compression
  layer, never a second geometry engine. Pack discovery and catalogs are scoped
  to one packed-project compilation and must not mutate the global base registries;
  importing or installing a pack cannot change an existing spec.
  `cabinetry.frameless@1` compiles one two-door base cabinet or a touching
  straight run; `vanity.frameless@1` compiles one wall-hung two-door vanity with
  backing, anchors, plumbing keepout, and a required project-specific mount
  review. Versioned archetypes expand compact authoring into those same strict
  schemas. Their release gates distinguish derived/calculated/manufacturer/
  field/certified evidence from UNKNOWN and infer neither KCMA certification nor
  custom wall-mount capacity from geometry or generic fastener data.
- **Site model + views** (`src/spec/site.py`, `spec/views.py`): ONE compiled
  model of the whole assembly. `details/site.spec.yaml` (`kind: site`) lists
  DetailSpec *fragments* (each still compiles standalone) at declared placements
  with EXACT/ASSUMED provenance; a member two subsystems SHARE becomes ONE node
  via `bind:` (a `stub_of` stub resolves onto the real member) or `dedup:` (a
  context body onto its real copy). That single-node move makes cross-subsystem
  disagreement UNREPRESENTABLE: it surfaces as a SYSTEM finding, not a
  hand-written caveat — the tree beam-Y divergence and the trolley post/leg
  registration are honest FAILs the per-detail structure hid. `SiteDetail` runs
  ONE validation sweep / coverage matrix / evidence graph over the composed
  model; `require_clean()` raising IS the gate working (the site can't render
  while a contradiction is open). A **view** (`views:`) is a scope selector over
  that one model + camera + view-local callouts; it NEVER re-validates —
  verdicts are site-level, a view PRESENTS the findings/BOM/coverage slice
  touching its scope and renders only when the WHOLE site is clean. A member in
  two views is the same node in both (`views_including` answers "where else?").
  Drawing sheets, later, are just views with a projection.
- **Coverage matrix + the UNKNOWN rule** (`src/validation/coverage.py`):
  `report.coverage_matrix()` gives a verdict per invariant family. A family no
  check touched is `UNKNOWN — NOT ANALYZED`, never `PASS`; any failing/
  unresolvable check flips a family `PASS → UNKNOWN`. Honesty about what is NOT
  proven is a hard rule — never phrase an UNKNOWN as safe. `PROVENANCE_ONLY_KINDS`
  are excluded from family attribution.
- **Evidence Graph** (`src/validation/evidence.py`): `detail.evidence_graph`
  links declarations → derived facts → findings → family verdicts, each node
  tagged `authoritative`/`verified_heuristic`/`llm_hypothesis` (the last
  non-build-blocking by construction). Built from lifecycle outputs only —
  building it changes no outcome (`test_evidence_equiv`). Serialization is
  canonical/deterministic across processes (fact ids assigned in content
  order); queries (`what_is`/`why_here`/`how_verified`/`what_depends_on`) are
  O(degree) via an adjacency index. This is the data layer the HTML consumes.
- **Ontology + load-path** (`src/core/ontology.py`, `validation/loadpath.py`):
  `Role`/`LoadClass`/`TransferCapability`; a detail that declares `roles` opts
  into a capacity-free reachability proof that a support→ground path is
  REPRESENTED. It never claims adequacy — Structural capacity stays UNKNOWN.
- **Spatial invariants** (`src/validation/spatial.py`): validation-only
  `SymmetricAbout` (explicit pairs or a mirror-by-name selector) + `FacesToward`/
  `FacesAway`, passed via `validate_assembly(spatial=[…])`. A selector that
  resolves to zero pairs FAILS loudly — a declared invariant must not read as
  proven if it proved nothing. `Parallel`/`Perpendicular`/`AlignedWith` are
  reserved names with a teaching error, not silent noops.
- **Inspector Mode** (`src/rendering/inspector.py`, prototype): the compiler
  emits an `inspector/v1` JSON payload (per-part descriptor / provenance /
  verification / dependencies IRs projected from the Evidence Graph's four
  queries); a self-contained clickable HTML consumes ONLY that payload — no
  detail knowledge lives in the UI, and UNKNOWN families render against every
  part (the wording rule binds the UI too). Build:
  `python scripts/build_inspector.py` → `outputs/inspector/…html`,
  byte-reproducible (gzip `mtime=0`; two-builds-equal is test-enforced). The
  direction of travel: the HTML is the primary interface to the semantic
  model, not generated documentation.
- **Persistent caches** (`src/core/base.py`, `core/diskcache.py`): built local
  solids are cached in-run and on disk keyed on `Component.cache_key()`, so
  identical parts pay the CAD cost once and unchanged geometry survives runs.
  Never key a cache on a display name (renames must not split geometry).
