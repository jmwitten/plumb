# Family Birdhouse Plumb Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a governed, model-backed fabrication, kid-participation, assembly, installation, and review package for the approved cedar chickadee/wren birdhouse with a pivoting cleanout side.

**Architecture:** Extend the semantic compiler only where the approved concept cannot be represented honestly: exterior cedar panels with multiple bores, ordinary exterior wood screws, and non-structural pivot/latch connection semantics. Author the birdhouse as one declarative DetailSpec, derive every geometry-dependent output from the compiled model and fabrication records, and promote only through Plumb's validation and design-review gates. Copy the reviewed release into JoelBrain and update the existing project note.

**Tech Stack:** Python 3.12, CadQuery, YAML DetailSpec/design-review sidecar, pytest, existing Plumb validation/report/viewer/document pipelines, Blender/Chromium visual verification, and Obsidian Markdown.

## Global Constraints

- Work only on `codex/birdhouse-plumb` in the isolated worktree; preserve the divergent local main checkout.
- Keep the approved `pivot_side_classic` concept and bind modeling to selection fingerprint `8119fc4fa46b962e5653c25c8cdb54130a3bc5b6cfe30646afc104ba8cb8beea`.
- Use untreated 3/4-inch cedar, a 1-1/8-inch entrance, no perch, recessed/drained floor, side ventilation, oversized sloped roof, extended mounting back, and a metal-pole/predator-baffle installation boundary.
- Adult-only: all sawing, boring, exterior installation, lifting, and sharp-tool work. Children may measure, mark, sand already-prepared edges, decorate exterior faces only, sort parts, and drive supervised pre-started screws.
- Do not claim bird occupancy, predator resistance, fastener capacity, pole/foundation adequacy, paint safety, or site suitability as analyzed.
- Unknown pole, baffle, foundation, mounting-hardware, coating, and site facts remain explicit field holds.
- Implement compiler behavior test-first and commit each independently reviewable task.

---

### Task 1: Add exterior cedar panel fabrication vocabulary

**Files:**
- Create: `src/components/cedar.py`
- Modify: `src/components/__init__.py`
- Modify: `src/core/materials.py`
- Modify: `src/rendering/_blender_materials.py`
- Create: `tests/test_cedar_components.py`
- Modify: `tests/test_blender_materials.py`

**Interfaces:**
- Produces: registered `CedarPanel` as `cedar_panel`
- Produces: registered `cedar` material and Blender material tag
- Consumes: every authored `features[].bore` and lowers each into one ordered process-record bore

- [x] Write failing tests for cedar registry/material/BOM language, rectangular geometry, multiple distinct bores, fabrication-fold equality, and compiler lowering of entrance/vent/drain features.
- [x] Run `.venv/bin/python -m pytest tests/test_cedar_components.py tests/test_blender_materials.py -q` and confirm RED due to missing cedar vocabulary.
- [x] Implement the smallest `CedarPanel` using the established panel local frame (`X=length`, `Y=width`, `Z=thickness`), a crosscut/ease/bore fabrication record, an append-only feature list, and geometry derived from that record.
- [x] Register cedar core/Blender materials and export the component.
- [x] Run the focused component, compiler-feature, process-graph, registry, and Blender-material suites; confirm GREEN.
- [x] Commit as `feat: add exterior cedar panel vocabulary`.

### Task 2: Add exterior screw and service-panel connection semantics

**Files:**
- Modify: `src/components/fasteners.py`
- Modify: `src/assemblies/installation.py`
- Modify: `src/assemblies/connection.py`
- Create: `tests/test_exterior_wood_screw.py`
- Create: `tests/test_service_panel_connections.py`

**Interfaces:**
- Produces: registered galvanized `ExteriorWoodScrew` as `exterior_wood_screw`
- Produces: registered `pivot_screwed` and `service_latch_screwed` connection types
- Consumes: exactly two wood members and one exterior screw per service connection

- [ ] Write failing tests for component registration/BOM/material, fastener classification, strict role guards, allowed intersections, screw/member bonds, install contracts, and `pivoted_by` versus `latched_by` construction edges.
- [ ] Run the two new test modules and confirm RED because the registry entries/edge kinds do not exist.
- [ ] Implement the exterior screw as a pointed galvanized axial fastener without structural-screw naming or capacity claims.
- [ ] Implement the two service connection types with no gravity seat and no member-to-member fixed-joint claim; register the new semantic edge kinds in all graph/evidence consumers required by failing tests.
- [ ] Run connection, installation-contract/sweep, evidence/load-path, registry, and new focused suites; confirm GREEN.
- [ ] Commit as `feat: model birdhouse service panel hardware`.

### Task 3: Author and validate the governed birdhouse DetailSpec

**Files:**
- Create: `details/family_birdhouse.spec.yaml`
- Modify: `details/family_birdhouse.design-review.yaml`
- Create: `tests/test_family_birdhouse_e2e.py`
- Create: `tests/test_family_birdhouse_design_review.py`

**Interfaces:**
- Produces: one compiled birdhouse model whose parts, holes, connections, sequences, BOM, and cut plan match the approved concept
- Binds: implemented modeling approval to concept fingerprint `8119fc4fa46b962e5653c25c8cdb54130a3bc5b6cfe30646afc104ba8cb8beea`

- [ ] Write failing end-to-end assertions for six cedar pieces, one 1-1/8-inch entrance, four side vents, four floor drains, recessed floor, oversized sloped roof, extended back, pivot/latch hardware, no perch, no fixed joint across the cleanout side, coherent BOM/cut list, kid/adult boundaries, and unresolved site/pole holds.
- [ ] Write failing governance assertions that the selected concept is implemented and promotion is model-bound while delivery confirmation remains unclaimed.
- [ ] Run the two new tests and confirm RED against the missing spec.
- [ ] Author the DetailSpec with named parameters, raw placements, `butt_screwed` fixed joints, `pivot_screwed` cleanout pivots, `service_latch_screwed` latch, typed stages, assembly sequence, installation holds, and source-backed notes.
- [ ] Record the autonomous owner modeling approval in the sidecar using the selected concept fingerprint; do not forge a post-review delivery confirmation.
- [ ] Run spec lint/compile/build plus model, fabrication, construction, installability, load-path/evidence, BOM, and design-review gates; confirm GREEN.
- [ ] Commit as `design: model family cedar birdhouse`.

### Task 4: Generate the complete model-backed release package

**Files:**
- Create: `scripts/family_birdhouse_report.py`
- Create: `tests/test_family_birdhouse_report.py`
- Generate under: `outputs/family_birdhouse/`

**Interfaces:**
- Consumes only the compiled DetailSpec, fabrication records, validation findings, and governed sidecar
- Produces model/report/viewer files, fabrication and assembly/install documents, BOM/cut data, rendered views, and a manifest carrying fingerprints and release state

- [ ] Write failing report-contract tests requiring reciprocal links, model-derived dimensions/part counts/hole counts, explicit adult/kid task ownership, cleanout operation, install holds, validation status, model/selection fingerprints, no external runtime dependency, and no static drawing presented as geometry evidence.
- [ ] Run the new report tests and confirm RED because the generator does not exist.
- [ ] Implement the narrow birdhouse adapter over the existing report/viewer/instruction/document composers; add only project-specific prose and view/station definitions.
- [ ] Generate STEP/GLB/model manifest, governed HTML report and interactive viewer, fabrication/cut guide, kid-friendly build guide, adult installation/service guide, BOM/cut CSV, orthographic/exploded renders, and review evidence.
- [ ] Render HTML/PDF/image outputs with the repository's Chromium/Blender tooling and inspect every page/view for clipping, overlap, legibility, correct geometry, and truthful release/hold labeling.
- [ ] Run focused generator/document/viewer tests and commit source as `feat: generate family birdhouse package` (generated ignored outputs remain release evidence, not source history).

### Task 5: Review, verify, and deliver

**Files:**
- Review: complete Plumb source/model/package
- Replace/update: `05_Attachments/Organized/Birdhouse Drawings/2026-07-15/`
- Modify: `01_Projects/03_Dacha/Family Birdhouse Build.md`

- [ ] Read and apply `plumb-review` immediately before review; audit concept binding, geometry, construction semantics, fabrication records, instruction coverage, visuals, fingerprints, and hold/pass boundaries.
- [ ] Resolve every source-backed review finding test-first; regenerate from source after any change and repeat visual inspection.
- [ ] Run the official full serial Plumb suite to distinguish the observed xdist-only baseline flake from a real regression, plus all family-birdhouse tests, spec/design-review gates, `git diff --check`, report link/asset checks, and deterministic regeneration/fingerprint comparison.
- [ ] Copy only the approved model-backed release into the existing JoelBrain attachment folder; replace the earlier static substitute files and preserve unrelated vault content.
- [ ] Update the Obsidian project note with YAML, wikilinks/embeds, package inventory, safe participation boundaries, fingerprints, validation state, sources, and remaining field holds.
- [ ] Commit and push `codex/birdhouse-plumb`; commit and push the scoped JoelBrain files. Leave both repositories clean except for pre-existing unrelated user changes.
