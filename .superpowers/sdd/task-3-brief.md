### Task 3: Build one model-bound installation drawing projection

**Files:**
- Modify: `scripts/cabinetry_project_report.py`
- Test: `tests/test_cabinetry_project_report.py`

**Interfaces:**
- Consumes: `PackedProject.model`, cabinet declaration, support parts, surveyed studs, structural-screw parts, selected wall-anchor product, and installation-use policy.
- Produces: `installation_drawing_facts(project) -> dict[str, object]`, `_render_installation_plan_drawing()`, and `_render_anchor_section_drawing()`.

- [ ] **Step 1: Add failing exact-fact tests**

  For DB40 assert cabinet local bounds, global left datum, toe footprint, two stud centers, two local anchor X values, common anchor Z, selected screw length, modeled stack, and stud embedment. Assert a released width/site variant moves the appropriate facts and contains no stale DB40 literal.

- [ ] **Step 2: Run the exact tests and verify RED**

  Expected: `AttributeError` for missing `installation_drawing_facts`.

- [ ] **Step 3: Implement the fact projection with loud invariants**

  Select parts by semantic role/part id, require a one-to-one stud/anchor relationship, derive local X from anchor global X minus cabinet x0, derive toe bounds from compiled toe parts, and derive stack/embedment from the selected screw and modeled wall/strip geometry. Raise a teaching `ValueError` when required geometry is absent or incoherent.

- [ ] **Step 4: Replace raw primary plan/right renders**

  Draw a dedicated wall/cabinet/toe/stud plan and anchor/toe section from the facts. Enhance the front elevation with anchor-strip/stud centerlines, anchor X/Z callouts, high-floor datum, and held countertop boundary. Stamp held drawings `COORDINATION ONLY — DO NOT ANCHOR OR ATTACH COUNTERTOP UNTIL HOLD CLEARED` from typed release state.

- [ ] **Step 5: Run exact drawing tests and verify GREEN**

  Run the drawing-fact, front-label, and report-scene tests.
