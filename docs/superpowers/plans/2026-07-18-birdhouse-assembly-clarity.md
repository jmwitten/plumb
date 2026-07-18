# Birdhouse Assembly Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an eight-panel birdhouse guide with model-derived screw placement arrows and correctly scaled exploded views.

**Architecture:** Author birdhouse-specific stage boundaries in the DetailSpec, add a reusable fastener-marker projection beside structural callouts, and make `SpecDetail.explode_vectors()` return canonical millimeters. Generated HTML remains non-authoritative and is regenerated only after source tests pass.

**Tech Stack:** Python 3.12, DetailSpec YAML, CadQuery/VTK, Pillow overlays, pytest, self-contained HTML.

## Global Constraints

- No hard cap on total instruction panels.
- One physical goal per birdhouse panel.
- Number structural parts only; identical screws use one quantity/length chip and unnumbered placement markers.
- Preserve distinct 1 1/2-inch and 2 1/4-inch screw families.
- Preserve UNKNOWN product, pilot, coating, torque, capacity, and field-installation facts.
- Write failing regressions before production changes.

---

### Task 1: Canonical explode units

**Files:**
- Modify: `tests/test_spec_presentation_loading.py`
- Modify: `tests/test_spec_presentation_equiv.py`
- Modify: `src/spec/compiler.py`

**Interfaces:**
- Consumes: `SpecDetail.doc.export.explode_authoring_units`, `SpecDetail.unit_factor`.
- Produces: `SpecDetail.explode_vectors() -> dict[str, tuple[float, float, float]]` in millimeters.

- [ ] Add a failing test compiling a `units: in` spec with `vector: [0, 4, 0]`; assert `explode_vectors()` returns `(0, 101.6, 0)` and the rendered manifest contains the same values.
- [ ] Run the focused test and confirm it fails because the public vector is `(0, 4, 0)`.
- [ ] Scale resolved vector coordinates once inside `explode_vectors()` when `explode_authoring_units` is true; remove scaling from `_inject_explode()`.
- [ ] Run the focused tests and confirm both the public surface and manifest pass.
- [ ] Commit the explode repair.

### Task 2: Reusable screw placement markers

**Files:**
- Modify: `tests/test_instruction_render.py`
- Modify: `tests/test_family_birdhouse_report.py`
- Modify: `src/rendering/instruction_render.py`
- Modify: `src/rendering/instruction_manual.py`
- Modify: `src/rendering/instruction_panels.py`

**Interfaces:**
- Produces: `panel_fastener_ids(detail, panel) -> tuple[str, ...]` from `DisplayRow.source_part_ids`.
- Produces: structural-only `panel_callout_ids(detail, panel)`.
- Produces: PNG metadata `detailgen_fastener_marker_count` and orange entry rings/axis arrows.

- [ ] Add failing tests asserting installation fasteners are absent from numbered callouts, every current screw has one marker, no screw instance name appears in the HTML picture key, and the hardware chip retains quantity and length.
- [ ] Run the focused tests and confirm the current 23-callout behavior fails.
- [ ] Filter installation fasteners from `panel_callout_ids()` and add `panel_fastener_ids()`.
- [ ] Project each fastener's `head_bearing` and `axis` datums, draw one target and arrow, and include marker identity in the content key and PNG metadata.
- [ ] Render the picture-key legend with structural callouts plus `orange targets = screw locations`; simplify each panel hardware row to `Screw ×N` while retaining size/head facts.
- [ ] Run focused renderer/manual tests and inspect one generated image.
- [ ] Commit the shared instruction-rendering repair.

### Task 3: Eight birdhouse stages

**Files:**
- Modify: `details/family_birdhouse.spec.yaml`
- Modify: `scripts/family_birdhouse_report.py`
- Modify: `tests/test_family_birdhouse_report.py`
- Modify: `tests/test_scope_manifest.csv` only if new test node IDs require classification.

**Interfaces:**
- Consumes: authored `sequence.stages` and existing `JoinPresentation`.
- Produces: eight panels with connection counts `[1, 1, 3, 2, 1, 3, 0, 1]`.

- [ ] Add a failing product test asserting eight panels, exact connection grouping, no panel over three connections, panel 1 has only two structural callouts/two screw markers, and the completion panel checks drains, vents, swing, and latch.
- [ ] Run the product test and confirm the four-panel schedule fails.
- [ ] Author six enclosure stages plus the cleat stage, assigning each incoming board to its first stage so the scene builds progressively.
- [ ] Update the join presentation to be an explicit enclosure acceptance check without claiming field readiness.
- [ ] Run the focused family tests and inspect all eight panel images.
- [ ] Commit the product sequence.

### Task 4: Regenerate, review, and release

**Files:**
- Regenerate: `build/family_birdhouse/`
- Replace: the compiled package under the JoelBrain birdhouse attachment folder.
- Update: `01_Projects/03_Dacha/Traditional Small Birdhouse.md` with the new package fingerprint, review result, and timing.

**Interfaces:**
- Consumes: source-bound Plumb launcher and package builder.
- Produces: reconciled preview package, review evidence, and vault delivery.

- [ ] Run focused tests, family-birdhouse inner gate, family-birdhouse release gate, and platform integration.
- [ ] Regenerate the preview package from the worktree source and compare all eight panels, static exploded view, and viewer payload offsets.
- [ ] Verify responsive and print HTML structure and package-manifest hashes.
- [ ] Copy the regenerated authoritative package and evidence into JoelBrain; update the project note.
- [ ] Commit and push the Plumb branch and the scoped JoelBrain changes.

