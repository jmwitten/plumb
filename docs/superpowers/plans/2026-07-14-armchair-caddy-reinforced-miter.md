# Armchair Caddy Reinforced-Miter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the governed armchair caddy's five-piece rail construction with the selected three-panel, four-dowel reinforced-miter production design while preserving truthful fabrication, validation, reporting, and delivery gates.

**Architecture:** Add reusable `miter_crosscut`, `hardwood_panel`, `wood_dowel`, and `dowel_reinforced_miter` vocabulary, then consume it declaratively in the caddy DetailSpec. Geometry remains derived from fabrication records, connection semantics feed the existing evidence/load-path graph, and customer delivery remains blocked until model-bound owner confirmation.

**Tech Stack:** Python 3.12, CadQuery, dataclasses, YAML DetailSpec, pytest, and the existing DetailGen review/rendering pipeline.

## Global Constraints

- Work only in the isolated `precedent-first-design-selection` worktree and do not merge to `MAIN`.
- Use three matching 3/4-inch hardwood panels and retain the centered 3-1/2-inch cup opening.
- Preserve a 6-1/2-inch clear opening around the modeled 6-inch arm.
- Use two 3/8-inch diagonal dowels per joint at 1-3/16 inches from the front and back edges.
- Do not claim adhesive, dowel, panel, cup-fit, or hot-drink capacity as analyzed.
- Do not author delivery confirmation for the owner.
- Implement test-first and commit each independently reviewable task.

---

### Task 1: Add the reusable miter fabrication operation

**Files:**
- Modify: `src/core/process_graph.py`
- Create: `tests/test_miter_fabrication.py`

**Interfaces:**
- Produces: `ProcessStep.miter_crosscut(end, angle_degrees=45.0, long_face="top", provenance="")`
- Produces: `fold()` support for a full-width triangular miter wedge
- Consumed by: `HardwoodPanel.fabrication_record()`

- [ ] **Step 1: Write failing constructor and identity tests**

~~~python
def test_miter_steps_are_keyed_by_end():
    near = ProcessStep.miter_crosscut("near", 45, "top", "near-miter")
    far = ProcessStep.miter_crosscut("far", 45, "top", "far-miter")
    assert near.identity == ("miter_crosscut", "near")
    assert far.identity == ("miter_crosscut", "far")
    ProcessRecord(STOCK, (ProcessStep.crosscut(203.2), near, far), "panel")

@pytest.mark.parametrize("end,face,angle", [
    ("middle", "top", 45), ("near", "side", 45),
    ("near", "top", 0), ("near", "top", 90),
])
def test_miter_rejects_invalid_parameters(end, face, angle):
    with pytest.raises(ValueError):
        ProcessStep.miter_crosscut(end, angle, face)
~~~

- [ ] **Step 2: Verify the red test**

Run: `.venv/bin/python -m pytest tests/test_miter_fabrication.py -q`  
Expected: FAIL because `miter_crosscut` does not exist.

- [ ] **Step 3: Implement the constructor, identity, cut note, and fold**

Validate `end in {"near", "far"}`, `long_face in {"top", "bottom"}`, and `0 < angle_degrees < 90`. Key identity as `("miter_crosscut", end)`. In `_apply_step`, compute setback as `thickness / tan(radians(angle_degrees))` and cut the mirrored full-width triangular prism.

- [ ] **Step 4: Add geometry and invariant assertions**

For a 203.2 x 139.7 x 19.05 mm panel with two top-long 45-degree miters, assert an 8-inch top long point and 7-1/4-inch bottom short point. Assert cut notes name both ends, 45 degrees, and the top long face. Run `assert_fabrication_fold_invariant` on the folded solid.

- [ ] **Step 5: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_miter_fabrication.py tests/test_process_graph.py -q`  
Expected: PASS.

- [ ] **Step 6: Commit**

~~~bash
git add src/core/process_graph.py tests/test_miter_fabrication.py
git commit -m "feat: model miter crosscut fabrication"
~~~

### Task 2: Add hardwood panel and dowel components

**Files:**
- Create: `src/components/hardwood.py`
- Modify: `src/components/__init__.py`
- Modify: `src/core/materials.py`
- Modify: `src/rendering/_blender_materials.py`
- Create: `tests/test_hardwood_components.py`

**Interfaces:**
- Produces: registered `HardwoodPanel` as `hardwood_panel`
- Produces: registered `WoodDowel` as `wood_dowel`
- Produces: registered `hardwood` material
- Consumes: `ProcessStep.miter_crosscut` and compiler feature cuts

- [ ] **Step 1: Write failing component tests**

~~~python
def test_hardwood_panel_folds_miters_and_bore_from_one_record():
    panel = HardwoodPanel(8*IN, 5.5*IN, 0.75*IN,
                          miter_ends=("near", "far"), ease_radius=0)
    panel.apply_feature_cut(4*IN, 2.75*IN, 1.75*IN,
                            noun="cup opening", step_kind="bore",
                            provenance="feature:cup")
    assert [s.kind for s in panel.fabrication_record().steps] == [
        "crosscut", "miter_crosscut", "miter_crosscut", "bore"]
    assert panel.material_key == "hardwood"

def test_wood_dowel_is_a_finished_hardwood_cylinder():
    pin = WoodDowel(3/8*IN, math.sqrt(2)*0.75*IN)
    bb = pin.solid.val().BoundingBox()
    assert bb.xlen == pytest.approx(math.sqrt(2)*0.75*IN)
    assert bb.ylen == pytest.approx(3/8*IN)
~~~

- [ ] **Step 2: Verify the red test**

Run: `.venv/bin/python -m pytest tests/test_hardwood_components.py -q`  
Expected: FAIL because the registry entries do not exist.

- [ ] **Step 3: Implement `HardwoodPanel`**

Use local `X=length`, `Y=width`, `Z=thickness`. Its ordered process record is crosscut, optional ease, authored miters, then optional compiler-applied bore. `_build()` delegates to the record fold. Cache identity includes miters and feature data. BOM and assumptions say hardwood panel, never SPF or pressure-treated lumber.

- [ ] **Step 4: Implement `WoodDowel` and material registration**

Build the finished pin with `axis_cylinder(diameter/2, length, origin, +X)`. Report 3/8-inch hardwood dowel stock. Add the `hardwood` material to core and Blender registries and export both component classes from `components.__init__`.

- [ ] **Step 5: Add compiler/BOM integration tests**

Compile a temporary spec with a `hardwood_panel` and `bore` feature. Assert the bore reaches the process record, lowers solid volume, and surfaces as hardwood in BOM/material output.

- [ ] **Step 6: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_hardwood_components.py tests/test_registry.py tests/test_blender_materials.py tests/test_cl2_feature.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

~~~bash
git add src/components/hardwood.py src/components/__init__.py src/core/materials.py src/rendering/_blender_materials.py tests/test_hardwood_components.py
git commit -m "feat: add hardwood panels and dowels"
~~~

### Task 3: Add reinforced-miter connection semantics

**Files:**
- Modify: `src/assemblies/connection.py`
- Modify: `src/validation/loadpath.py`
- Modify: `src/validation/evidence.py`
- Create: `tests/test_dowel_reinforced_miter.py`

**Interfaces:**
- Produces: registered `dowel_reinforced_miter` connection
- Produces: `keyed_by` construction/load-path edge
- Consumes: exactly two panels and exactly two `WoodDowel` hardware members

- [ ] **Step 1: Write failing connection tests**

Build a synthetic two-panel corner with two dowels. Assert registry resolution, exact role guards, one panel bond, four allowed dowel/panel intersections, `bonded_to` and `keyed_by` edges, a typed cure fact, placeholder pull-out/shear claims, and `install_contract() == ()`. Substituting a screw for a dowel must raise a teaching error.

- [ ] **Step 2: Verify the red test**

Run: `.venv/bin/python -m pytest tests/test_dowel_reinforced_miter.py -q`  
Expected: FAIL because the connection type is unknown.

- [ ] **Step 3: Implement `DowelReinforcedMiter`**

Subclass `ConnectionType`. Validate exactly two member panels and two dowels. Derive member bonding/connectivity, dowel/member allowed intersections, `bonded_to` and `keyed_by` edges, label-governed cure, and explicitly unanalyzed transfer claims. Return `()` instead of a screw/bolt installation contract.

- [ ] **Step 4: Register `keyed_by` in graph consumers**

Add it to `LOAD_BEARING_EDGE_KINDS`, `EDGE_KINDS`, and `_CONSTRUCTION_EDGE_KINDS`. Test evidence traversal and incremental affected-region traversal so the new edge cannot be silently dropped.

- [ ] **Step 5: Run focused graph tests**

Run the new test plus the connection, evidence, load-path, and affected-region suites:

~~~bash
.venv/bin/python -m pytest tests/test_dowel_reinforced_miter.py \
  tests/test_connection.py tests/test_evidence_graph.py tests/test_loadpath.py \
  tests/test_affected_region.py -q
~~~

Expected: PASS.

- [ ] **Step 6: Commit**

~~~bash
git add src/assemblies/connection.py src/validation/loadpath.py src/validation/evidence.py tests/test_dowel_reinforced_miter.py
git commit -m "feat: model dowel reinforced miter joints"
~~~

### Task 4: Replace the caddy geometry and record modeling approval

**Files:**
- Modify: `details/armchair_caddy.spec.yaml`
- Modify: `details/armchair_caddy.design-review.yaml`
- Modify: `tests/test_armchair_caddy_e2e.py`
- Modify: `tests/test_caddy_design_review.py`

**Interfaces:**
- Produces: caddy with three panels, four dowels, and no rails/screws
- Preserves selection fingerprint: `24a277ee5e2a67e1022428ca20cb0c09cca8be946a147619528cee160e891b25`

- [ ] **Step 1: Rewrite caddy assertions first**

Require three `HardwoodPanel` parts, four `WoodDowel` parts, no rail/screw parts, 6-1/2-inch clear opening, 8-inch top long point, 7-3/4-inch side long points, 3/4-inch thickness, retained 3-1/2-inch bore, two reinforced-miter connections, diagonal pin axes, and front/back pin stations at +/-1.5625 inches.

- [ ] **Step 2: Verify the red tests**

Run: `.venv/bin/python -m pytest tests/test_armchair_caddy_e2e.py tests/test_caddy_design_review.py -q`  
Expected: FAIL against the legacy five-piece spec.

- [ ] **Step 3: Rewrite the DetailSpec**

Use:

~~~yaml
panel_thk: 0.75
panel_width: 5.5
arm_gap: 0.25
dowel_dia: 0.375
dowel_edge_station: 1.1875
inner_span: "= arm_w + 2*arm_gap"
top_long_len: "= inner_span + 2*panel_thk"
side_long_len: "= side_drop + panel_thk"
dowel_finish_len: "= sqrt(2) * panel_thk"
~~~

Declare the top with near/far miters, sides with far miters, four flush diagonal dowels, two reinforced-miter connections, arm bearing, and bench staging. Remove rail/screw parameters, parts, connections, ordering, and prose.

- [ ] **Step 4: Record the already-granted modeling approval**

~~~yaml
decision:
  selected_concept: reinforced_miter
  application: implemented
modeling_approval:
  approved_by: Joel Witten
  approved_on: 2026-07-14
  selection_fingerprint: 24a277ee5e2a67e1022428ca20cb0c09cca8be946a147619528cee160e891b25
delivery_confirmation: null
~~~

Update governance tests so production promotion passes while delivery still fails for missing confirmation.

- [ ] **Step 5: Run caddy/governance tests**

Run:

~~~bash
.venv/bin/python -m pytest tests/test_armchair_caddy_e2e.py \
  tests/test_caddy_design_review.py tests/test_design_review_integration.py \
  tests/test_design_review_gate.py -q
~~~

Expected: PASS.

- [ ] **Step 6: Commit**

~~~bash
git add details/armchair_caddy.spec.yaml details/armchair_caddy.design-review.yaml tests/test_armchair_caddy_e2e.py tests/test_caddy_design_review.py
git commit -m "feat: implement reinforced miter caddy"
~~~

### Task 5: Regenerate truthful instructions and reports

**Files:**
- Modify: `src/rendering/caddy_stations.py`
- Modify: `scripts/single_detail_report.py`
- Modify: `scripts/caddy_documents.py`
- Modify: `scripts/render_caddy_views.py`
- Modify: `reviews/visual/caddy-findings.yaml`
- Modify: `reviews/visual/caddy-design-findings.yaml`
- Modify: `reviews/visual/caddy-view-coverage.json`
- Modify: `tests/test_caddy_instruction_manual.py`
- Modify: `tests/test_instruction_render.py`
- Regenerate: `outputs/design-reviews/armchair_caddy.html`
- Regenerate preview artifacts under `outputs/armchair_caddy/`

**Interfaces:**
- Produces geometry-measured miter/dowel stations and customer instructions with no legacy rail language

- [ ] **Step 1: Write new visible-output assertions**

Require `3/4 in hardwood`, `45-degree miter`, `3/8 in dowel`, `1-3/16 in from each edge`, `6.5 in clear opening`, cup-fit check, clamp/cure, flush trim, and four dowels. Reject `registration rail`, `cleat_screwed`, `structural screw`, `5/4x6`, and old screw-station copy.

- [ ] **Step 2: Verify the red document tests**

Run: `.venv/bin/python -m pytest tests/test_armchair_caddy_e2e.py -q -k 'doc or station or visual or design_review'`  
Expected: FAIL on rail-oriented adapters/copy.

- [ ] **Step 3: Replace station extraction**

Derive the inner opening, panel long/short points, each dowel's station/diameter/axis, and cup center/diameter from compiled geometry. Every reader step gets a measurable datum and verification. Delete rail/screw selection paths.

- [ ] **Step 4: Rewrite report/manual copy and review resolutions**

Describe waterfall layout, 45-degree cutting, dry-fit closure, cup bore, jig-guided through drilling, glue/dowel insertion, two-direction clamping, label-governed cure, flush trimming, sanding, and final fit verification. Preserve historical findings where useful but ensure every current resolution says the reinforced-miter geometry is implemented.

- [ ] **Step 5: Generate developer and preview artifacts**

Run the repository's actual report and preview interfaces:

~~~bash
.venv/bin/python -m detailgen.design_review report details/armchair_caddy.design-review.yaml --output outputs/design-reviews/armchair_caddy.html
.venv/bin/python scripts/single_detail_report.py details/armchair_caddy.spec.yaml --out outputs/armchair_caddy/armchair_caddy_build_document.html
.venv/bin/python scripts/render_caddy_views.py outputs/armchair_caddy/views
~~~

Use only the explicit preview/documentation path for customer files; certified delivery remains blocked.

- [ ] **Step 6: Inspect rendered output**

Confirm visually that the model has three panels, four visible corner keys, and the cup bore; no rails/screws remain; promotion reads PASS; delivery reads BLOCKED.

- [ ] **Step 7: Run document/visual tests**

Run: `.venv/bin/python -m pytest tests/test_armchair_caddy_e2e.py tests/test_caddy_instruction_manual.py tests/test_instruction_render.py -q`  
Expected: PASS.

- [ ] **Step 8: Commit**

Stage only changed source, tests, review stores, and tracked outputs, then:

~~~bash
git commit -m "docs: publish reinforced miter caddy preview"
~~~

### Task 6: Adversarial verification, full gate, and push

**Files:**
- Modify only files required by demonstrated failures

- [ ] **Step 1: Run adversarial probes**

Prove that deleting one dowel, replacing it with a screw, changing a miter to square, shrinking the opening, removing the cup bore, or restoring `application: recommendation_only` is caught. Do not weaken expected findings.

- [ ] **Step 2: Run the targeted feature gate**

~~~bash
.venv/bin/python -m pytest tests/test_miter_fabrication.py \
  tests/test_hardwood_components.py tests/test_dowel_reinforced_miter.py \
  tests/test_caddy_design_review.py tests/test_armchair_caddy_e2e.py -q
~~~

Expected: PASS.

- [ ] **Step 3: Check baselines and cleanliness**

~~~bash
.venv/bin/python scripts/regen_baselines.py --check
git diff --check
git status --short
~~~

Expected: baselines current and only intentional changes present.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`  
Expected: full suite passes with only established skips/xfail.

- [ ] **Step 5: Commit verification-driven corrections**

Stage only fixes required by demonstrated failures and commit as `test: verify reinforced miter delivery flow`.

- [ ] **Step 6: Push without merging**

Run: `git push origin codex/precedent-first-design-selection`  
Expected: remote branch advances.

- [ ] **Step 7: Stop at owner delivery confirmation**

Report commits, targeted/full-suite evidence, exact report/manual paths, and that delivery remains blocked. Do not populate `delivery_confirmation` or merge until Joel inspects and explicitly confirms the implemented result.
