# detailgen — Framework Improvement Roadmap

## Context

`~/Code/construction-detail-generator` (`detailgen`) ships one real detail (rock anchor) on a
clean geometry core. Reviewed **as a reusable framework**, two independent audits
(extensibility+determinism, semantics+maintainability) converge: it is a *parametric-geometry
+ interference/contact validator wearing construction vocabulary*. Placement is hand-authored
global-axis rotate+translate every detail must re-derive (the dominant authoring-bug source,
`details/rock_anchor.py:96-105`); "connections" exist only as scattered string-keyed lists
(`rock_anchor.py:126-173`); materials/fasteners are color-only with no engineering properties
(`core/materials.py:11-33`); validation thresholds are uncentralized magic numbers
(`validation/checks.py:36-42`); every extension point is a hardcoded import; and the
engineering/rendering/solver layers are essentially untested.

**Filter for every item (platform-first):** does it make *every future detail* more
deterministic, more semantic, more reusable, or easier to validate? If it only makes the rock
anchor prettier, it's not here. *(Superseded as the primary filter by the north star below,
2026-07-06 — it remains a useful secondary lens.)*

## North star & design principles (adopted 2026-07-06, binds all waves)

**Every framework improvement should reduce the construction knowledge authors must
explicitly encode.** Optimize expressiveness: a small declarative expression of intent from
which the platform infers geometry, placement, mating, validation, BOM, installation
sequence, exploded views, dimensions, rendering defaults, and documentation. DetailSpec is
the platform's *language*, not an input format; the architecture is a **compiler**, not a
CAD framework:

```
Intent → DetailSpec → Construction Graph → Derived facts (with provenance)
       → low-level assembly/geometry → Validation → Rendering → Documentation
```

Below the Construction Graph, everything is deterministic compilation. The spec contains
ONLY author-intended facts (components, relationships, required dimensions, high-level
constraints); everything derivable is derived. Schema test per field: *could the compiler
infer this?* → then it's out of the spec.

**P1 — Inference must be auditable.** Infer aggressively, never silently. Every derived fact
carries provenance: what was inferred, which authored declaration caused it, which rule
produced it, what assumptions were used, a confidence tag (official | inferred |
placeholder), and whether the author can override it. Failed or ambiguous inference is a
hard diagnostic, never a guess. Minimal spec; verbose, inspectable Construction Graph.

**P2 — Extensible dictionary.** Connection types encode reusable construction knowledge
(exemplar: `Simpson ABA66Z` → geometry source, valid mating parts, required fasteners, hole
pattern, bearing faces, installation order, validation rules, assumptions,
code/manufacturer references). The dictionary grows one type at a time — never blocked on
completeness.

**P3 — Imperative code is the escape hatch.** DetailSpec is the high-level language; the
Python assembly system remains the "assembly language" for what the DSL cannot yet express.

**P4 — Compiler diagnostics are a first-class output.** Every build emits a
derivation/diagnostic report alongside the validation report: what the author specified,
what the framework inferred, what assumptions were made, what was overridden, what could
not be inferred, and what warnings/ambiguity were found.

**Metrics per new detail:** Specification Compression (derived facts : authored facts, from
the derivation log — should rise every wave); spec LOC and explicit placement/constraint/
validation/dimension counts; secondary: imperative LOC (baseline: rock_anchor ~845,
platform 625, trolley 454, tree_attachment 369).

**Generation speed (user directive 2026-07-06, top priority for the next work phase):**
target **4× faster** generate+validate for a moderately complex design. Baselines:
rock_anchor (26 parts) build+validate ~60–90s; platform (46 parts) ~2–5 min; cold
full-document regen ~25–30 min (warm regen already hash-gated). Benchmark first (per-phase
timing harness), then attack the biggest costs — candidate levers: component-solid cache
keyed by (type, params), persistent BREP cache across runs, bbox/spatial prefilter before
pairwise BRepExtrema checks, per-pair verdict cache keyed by geometry hashes + relative
transform, measured parallelism. Speed work must never weaken validation honesty — a check
may be skipped only with a hash-proof of equivalence. This outranks Wave 2 feature work in
sequencing.

This roadmap incorporates review feedback that strengthens the **core abstractions first**.
The target is a framework where the pipeline is:

```
Prompt → DetailSpec → Construction Graph (Connections) → Assembly → Validation → Rendering → Documentation
```

The **Construction Graph** carries semantic edges (`bears_on`, `fastened_by`,
`transfers_load_to`, `installed_before`, `supported_by`), so the system becomes a construction
*reasoning* engine, not a CAD generator. `DetailSpec` (serializable) is the stable interface
between AI authoring and the framework: Claude emits a spec; the platform consumes it to
produce geometry, validation, rendering, docs, BOM, and installation steps.

Effort: S≈½d, M≈1–2d, L≈3–5d, XL≈1wk+. Items ordered into 5 waves; earlier waves are
foundations later ones build on.

---

## Orientation for a fresh agent (cold start — read this first)

This plan was produced in a long prior session; you do **not** need that history. Everything
to execute it is here plus the repo.

**Repo & env**
- Project: `~/Code/construction-detail-generator`, importable as package `detailgen`
  (editable install; `src/` maps to `detailgen` via `pyproject.toml`).
- Python venv: `~/Code/construction-detail-generator/.venv` (Python 3.12, CadQuery 2.8).
  Run things as `.venv/bin/python ...` or `source .venv/bin/activate`.
- Read `CLAUDE.md` in the repo — it states the coherence rules (mm-internal units, the
  Component contract, "validate before export"). Honor them.

**Commands that must keep working (regression oracle)**
- `.venv/bin/python -m pytest -q` → 8 tests green (grow, don't break).
- `.venv/bin/python details/rock_anchor.py` → prints "Validation: rock anchor — CLEAN" + BOM.
- `.venv/bin/python details/rock_anchor.py --render outputs/rock_anchor` → GLB/STEP/manifest/report.
- Blender (optional, macOS `/Applications/Blender.app`): 4-view render via
  `detailgen.rendering.render_blender` / `src/rendering/_blender_render.py`.

**File map (what to touch)**
- `src/core/` — `base.py` (Component ABC + BOM hooks), `units.py` (IN/FT = mm multipliers),
  `materials.py` (render-only Material dict).
- `src/components/` — `lumber.py` (reference impl of the contract), `concrete.py`,
  `fasteners.py`, `connectors.py`, `_geometry.py` (shared bend/thread/hex/ease recipes).
- `src/assemblies/assembly.py` — `DetailAssembly`, `Placed` (placement = rotate+translate),
  `bom_table()`, `load_step()`.
- `src/validation/checks.py` — interference/contact/bearing/through-hole/floating/dimension.
- `src/rendering/` — `export.py` (STEP/STL/PNG/GLB/manifest), `blender.py` +
  `_blender_render.py` (headless Cycles), `overlay.py` (PIL dimensions).
- `details/rock_anchor.py` (full real detail), `details/deck_ledger_example.py` (simple).

**Contracts to preserve while refactoring**
- Deterministic **computed placement is canonical**; the cq.Assembly solver is
  verification-only and never trusted unless it reproduces computed placement.
- Never export without a clean validation report (`report.require_clean()`).
- Components build geometry in a documented local frame; placement belongs to the assembly.
- The shipped rock-anchor detail is the behavior-preserving oracle: after items 1/3/6, its
  placed-part transforms must match the current model within 1e-6, and it must still validate
  CLEAN and render 4 views.

**How to work**: execute one wave at a time, keep `pytest` + rock_anchor green after each
item, commit per item with a clear message. Start with Wave 1 item 1 (datum/mate) — it
unblocks the most. Do not optimize for the rock-anchor example; optimize the framework.

---

## WAVE 1 — Framework Foundation
*Every detail must share one lifecycle before richer semantics land.*

### 1. Datum / Mate placement system — *Extensibility, Determinism* · L · **Very High**
Replace `add(at=, rotate=[...])` global-origin rotate-then-translate
(`assemblies/assembly.py:27-75`) with **named datum frames on components** and a mate API
(`place(part,"base").on(other,"top_face")`). Promote the prose datums (`core/base.py:8-10`,
per-class docstrings) to machine `datums: dict[str,Frame]`. Removes the dominant class of
authoring bugs — a sign error becomes inexpressible rather than a silent valid-but-wrong solid.
New `core/frame.py`; touch `core/base.py`, `assemblies/assembly.py`.

### 2. Stable part identity + typed references — *Maintainability, Extensibility* · M · **High**
Stable `id` per placed part, independent of display name; validation specs and BOM key on IDs,
not `by_name[str]` (`checks.py:230-232,285`; `rock_anchor.py:225`). `add()` returns handles
specs reference directly. Kills silent allowlist breakage / raw `KeyError` on rename
(`checks.py:291-298`) and fixes the `load_step` source-mislabel bug (`assembly.py:133-146`
never sets `source`).

### 3. Parameterizable `Detail` base class — *Extensibility, Maintainability* · M · **High**
*(moved up from later per feedback — Detail is the unit everything else builds on).*
Promote a detail from "module with a `build()` closing over ~20 globals"
(`rock_anchor.py:31-52`) to a `Detail` ABC over a params dataclass, enforcing the shared
lifecycle **params → components → assembly → validation → rendering → documentation**. Same
detail instantiable at any size; auto-derive dimension callouts from params (kills the
`'8" EMBED'`-vs-`ROD_EMBED=8.0` label drift, `rock_anchor.py:265-274`); unify the two BOM
paths (`assembly.py:99-130`). New `details/base.py`.

### 4. Centralized tolerance & config — *Determinism, Maintainability* · M · **High**
One `Config`/`Tolerances` object derived from a base precision, overridable per detail,
replacing scattered globals (`NOISE_VOLUME/CONTACT_EPS/NEAR_MISS/PUSH`, `checks.py:36-42`; the
`max(min_area*0.5,1.0)` bearing fudge `checks.py:174`; stray `tolerance=0.5`). New
`core/config.py`.

### 5. Reproducible builds — *Determinism* · M · **High**
Pin CadQuery + lockfile (`pyproject.toml:8` pins only `>=2.4`; OCCT boolean/tessellation is
version-sensitive); single-source the mesh tolerance (per-call 0.1/0.15/0.2 today,
`export.py:56,73,145`); seed Blender procedural textures (`_blender_render.py:81,91,103,135`
are seedless); emit a build manifest with **geometry content-hashes** for automatic
geometric-regression detection. `pyproject.toml`, new `constraints.txt`, `rendering/*`, new
`core/buildinfo.py`.

## WAVE 2 — Semantic Core
*Give the framework its missing central abstraction and a stable AI interface.*

### 6. First-class Connection object (the central abstraction) — *Semantic awareness* · L · **Very High**
Elevate `Connection` to the object the platform revolves around:
`Post —connected_to→ Bracket —connected_to→ Concrete, using Anchor-Bolt-Assembly`. A
Connection **owns** mating faces, the hardware stack, expected bearing surfaces, allowed
intersections, installation order, validation rules, load path, and assumptions. Geometry
becomes *one representation of the connection* rather than the connection being implied by
scattered arithmetic + string-pair lists (`rock_anchor.py:52-173`). Validation specs are
**generated from** the Connection, so they can't drift from geometry. This realizes the
Construction-Graph edges. Depends on 1+2. New `assemblies/connection.py`.

### 7. Serializable `DetailSpec` schema — *Extensibility, Semantic awareness* · L · **Very High**
A declarative spec (`type / components / connections / views / dimensions / validation / bom`)
that the platform consumes to produce geometry → validation → rendering → docs → BOM →
install steps. Becomes the stable contract between AI authoring and the framework: Claude
generates a spec, not imperative Python, so authoring is validated, diffable, and replayable.
Depends on 3+6. New `spec/` (schema + loader).

### 8. Registry / plugin architecture — *Extensibility* · M · **High**
Registries (decorator/entry-point) for components, materials, exporters, and checks, replacing
hardcoded lists (`components/__init__.py:1-13`; materials dict `core/materials.py:24-33`;
exporter free-functions `rendering/export.py`; fixed check pipeline `checks.py:263-308`;
`if/elif` Blender material chain that silently grays unknown tags `_blender_render.py:74-113`).
Lets DetailSpec resolve types by name and enables third-party detail libraries. New
`core/registry.py`.

## WAVE 3 — Engineering Metadata
*Attach real properties and deterministic engineering rules.*

> **RESHAPED 2026-07-06 (user-adopted, binding — full text in
> `.superpowers/sdd/progress.md` "WAVE 3 SHAPE"):** Wave 3 is built as a
> small construction ONTOLOGY (Role / LoadClass / TransferCapability /
> Support / LoadPath) rather than per-assembly rule packages; items 9-10
> below are subsumed as compositions over it. Sequencing: (1) UNKNOWN/NOT
> ANALYZED verdicts + a per-report coverage matrix over seven invariant
> families (Physical, Spatial, Construction, Functional, Load-path,
> Capacity, Code) — first, so "clean" cannot be overread; (2) semantic
> model; (3) provenance-tagged transfer claims on ConnectionTypes;
> (4) load-path reachability as representation proof only; (5) first
> cited rule pack (guards/rails, AWC DCA6 / Simpson). Wording rule: "a
> lateral-load path is represented," never "safe," unless capacity/code
> checks actually ran.

### 9. Engineering material & grade model (with provenance) — *Semantic awareness* · M · **High**
Extend `Material` (name/color/alpha only today) with density, allowable stresses, species/grade;
add grade/class to fasteners (ASTM/Grade, hot-dip-vs-zinc as *capacity* not color). Every
property and asset carries **provenance**: `source` ∈ official/generated/placeholder,
`confidence`, `reference_url`, `revision`, `units`, and for parts `manufacturer`/`part_number`.
Revives the dead `volume()`→weight promise and the dead BOM `source` column; makes
`StructuralScrew` a real distinction. `core/materials.py`, `components/fasteners.py`,
`components/lumber.py`; provenance ties into `load_step` (`assembly.py:133-146`).

### 10. Rule-based engineering validation (6A) — *Semantic awareness* · L · **High**
Deterministic, no-load-calc rules that improve every detail immediately: minimum edge/end
distance, fastener spacing, required washers/nuts present, bearing-surface adequacy, embedment
length, required-hardware presence, and installation-sequence validity. Built on the Connection
(rules attach to connection types) and current geometric checks (`checks.py`). New
`validation/rules/`.

## WAVE 4 — Structural Engineering (6B)
*The geometry engine becomes an engineering engine.*

### 11. Capacity, load path & code citations — *Semantic awareness* · XL · **Very High**
Demand-vs-capacity: allowable stresses, withdrawal/shear, bearing capacity, safety factors,
with machine-readable NDS/IRC/ACI citations attached to results. Connections declare demand;
checks compare against member/fastener capacity from item 9. Today no force/allowable/safety
factor exists anywhere and `check_no_floaters` proves *touching*, not load transfer
(`checks.py:230-260`). Depends on 6+9+10. New `validation/structural.py`, `validation/codes/`.

## WAVE 5 — Quality & Reliability

### 12. Full-stack test, CI & regression harness — *Maintainability* · M · **High**
Positive+negative test per validation check (today `check_through_hole`/`check_no_floaters`/
`check_contact` have no failure test); assert every `check()` domain rule fires (only lumber's
is tested); headless-VTK `export_png` smoke test; Blender-optional render gate; golden
geometry-hash regression (from item 5). Close the silent-except bug-hiding surfaces
(`lumber.py:128`, `_geometry.py:115`, and especially `rock_anchor.py:211`, where a real
solver-setup bug is laundered into the by-design "solver disagrees" narrative). CI runs the
whole matrix per detail. `tests/`, `pyproject.toml`, CI config.

---

## Dependencies
1→2→3 foundational; 4,5 parallel. 6 needs 1+2; 7 needs 3+6; 8 anytime after 1. 9 before 10;
11 needs 6+9+10. 12 needs 5 (+ everything, ongoing). Highest single-item leverage: **6**
(Connection) and **1** (datum/mate) — they supply the missing central abstraction and remove
the dominant authoring-bug class. **7** (DetailSpec) is the key AI-interface unlock; **11** is
the biggest capability jump but the largest and most dependent.

## Verification (per executed item)
- `pytest` stays green and grows (12); `python details/rock_anchor.py` still validates CLEAN
  and renders 4 views — the shipped detail is the regression oracle for 1–9.
- 1/3/6: re-author rock_anchor via datums/Detail/Connection; diff placed-part transforms
  against the current computed model (≤1e-6) to prove behavior-preserving.
- 4/5: identical mesh vertex counts + identical geometry hashes across repeated runs; verdicts
  unchanged. 7: round-trip a DetailSpec → same assembly the Python detail produces.

## Execution model — use Claude's team abilities (required)

Build this as an **orchestrator + subagents**, not a solo effort. You (the agent reading this
file) are the lead: you own the wave sequence, the git history, and the behavior-preserving
oracle; you delegate implementation and verification to teammates.

**Parallelism (dispatch independent items to subagents in isolated git worktrees):**
- Wave 1: the `1 → 2 → 3` chain is sequential (each builds on the prior), but **items 4
  (config) and 5 (reproducible builds) are independent** and run in parallel worktrees
  alongside the chain. Merge in dependency order.
- Wave 2: `8 (registry)` is independent of the `6 → 7` chain — parallelize it.
- Wave 3: `9` before `10`. Wave 4: `11` is mostly sequential. Wave 5: `12` is continuous.
- Use the `git-worktrees` / `dispatching-parallel-agents` skills so parallel edits don't
  collide; each subagent works one item to completion (code + tests) in its own worktree.

**Adversarial verification (a fresh subagent per item, no shared context):**
After each item lands, spawn a **fresh reviewer subagent** that (a) re-runs `pytest` and
`details/rock_anchor.py`, (b) diffs the item's public API against this plan's intent, and
(c) confirms behavior preservation against the rock-anchor oracle (placed-part transforms
≤1e-6, still CLEAN, still 4 renders). This is the same solo-review discipline that caught real
defects in the prior session — reviewers must have no stake in the implementation.

**Loop:** implement (subagent, worktree) → review (fresh subagent) → fix → commit per item →
next item. Keep the lead's context lean by delegating reading-heavy work and relaying only
conclusions.

## Scope note
Analysis/roadmap deliverable — approving it accepts the direction and sequencing; executing
any item or wave is a follow-up. Recommended first increment: **Wave 1** (items 1–5), which
every later capability depends on. Build it with the team, one item at a time, green after each.
