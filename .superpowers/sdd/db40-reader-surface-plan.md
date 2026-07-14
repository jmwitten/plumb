# DB40 Reader-Surface Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the DB40 monolithic technical document with a concise review/install landing sheet plus model-linked fabrication and audit companions, without changing geometry, validation, release state, or construction order.

**Architecture:** Compile one `PackedProject`, build one instruction manual, and render shared assets once. Three focused pure HTML composers consume that same project, and one typed basename object closes all reciprocal links. Installation drawings consume one tested `installation_drawing_facts(project)` projection rather than owning numeric literals.

**Tech Stack:** Python 3.12, pytest, dataclasses, Matplotlib, existing OCCT/VTK export and self-contained HTML renderer.

## Global Constraints

- Preserve `frameless_three_drawer_40_build_document.html` as the landing-page basename.
- DB40 installation/use remains HOLD; no UNKNOWN may become PASS.
- No cabinetry geometry, pack validation, or CPG order change is authorized.
- Every displayed installation dimension comes from the compiled model or selected catalog record.
- The document set compiles once and renders product views once.
- Existing non-cabinetry instruction manuals retain their current behavior by default.
- Use `PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python` for every Python command.

---

### Task 1: Pin surface ownership and content budgets

**Files:**
- Modify: `tests/test_cabinetry_project_report.py`
- Modify: `tests/test_cabinetry_instruction_manual.py`

**Interfaces:**
- Consumes: current `compile_project_file()`, `CPR.build_cabinetry_html()` and detailed renderer functions.
- Produces: failing contracts for `build_cabinetry_review_html()`, `build_cabinetry_fabrication_html()`, `build_cabinetry_audit_html()`, and the four-file output set.

- [ ] **Step 1: Add a visible-text helper and failing primary-sheet test**

  Strip `<script>` and `<style>` blocks before counting words. Assert the DB40 primary sheet has no more than 2,500 visible words, 80 `<tr>` rows, or eight tables; includes release state, active UNKNOWN rules, key dimensions, field checks, and installation steps; and excludes `Cut list`, `Machining schedule`, `Fabrication`, `Validation findings`, `Evidence register`, and `Source map` headings.

- [ ] **Step 2: Add failing fabrication and audit ownership tests**

  Assert the fabrication composer contains every cut/edge/hardware/machining record and every fabrication/assembly step id, but no installation or audit ledgers. Assert the audit composer contains every finding rule, evidence id, and source-map target, but no cut or machining tables.

- [ ] **Step 3: Add failing link-closure test**

  Extend the real document generation test to require four output paths/hashes and relative links among the landing sheet, manual, fabrication packet, and review trace. Preserve the existing six panel assets and viewer metadata assertions.

- [ ] **Step 4: Run the tests and verify RED**

  Run:

  ```bash
  PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest -q tests/test_cabinetry_project_report.py tests/test_cabinetry_instruction_manual.py
  ```

  Expected: failures for missing focused composers, missing output files/keys, and current primary-sheet budget/ownership violations.

### Task 2: Add typed document links and correct manual ownership

**Files:**
- Modify: `src/rendering/instruction_panels.py`
- Modify: `src/rendering/instruction_manual.py`
- Modify: `src/packs/cabinetry/instruction_manual.py`
- Test: `tests/test_cabinetry_instruction_manual.py`

**Interfaces:**
- Consumes: `InstructionManual`, `_relative_html_basename()`, and the DB40 manual adapter.
- Produces: `RelatedDocumentLink(label: str, href: str)` and `InstructionManual.related_documents: tuple[RelatedDocumentLink, ...] = ()`.

- [ ] **Step 1: Add failing validation/render tests for related document links**

  Require relative `.html` basenames, reject paths and non-HTML hrefs, and assert the rendered DB40 manual labels the landing link `Review & installation sheet` while showing direct Fabrication packet and Review trace links. Assert caddy/default manuals remain unchanged when the tuple is empty.

- [ ] **Step 2: Run focused tests and verify RED**

  Run the named related-link tests and confirm failures are caused by the absent type/fields.

- [ ] **Step 3: Implement the additive typed link model and renderer**

  Add the frozen dataclass and defaulted field; validate links through the existing basename validator during manual construction/rendering; render a small related-document navigation list in header/footer.

- [ ] **Step 4: Correct DB40 prose ownership**

  Change only DB40 adapter copy from “technical build document” to “fabrication packet” where it refers to cut, edge-band, machining, or material signoff. Keep release/install references pointed at the landing sheet.

- [ ] **Step 5: Run focused tests and verify GREEN**

  Run `tests/test_cabinetry_instruction_manual.py`; expected: all tests pass except later document-set tests that still depend on missing composers.

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

### Task 4: Implement the three focused HTML composers

**Files:**
- Modify: `scripts/cabinetry_project_report.py`
- Test: `tests/test_cabinetry_project_report.py`

**Interfaces:**
- Consumes: existing table/step renderers, shared views, viewer payload/GLB, typed link basenames, `InstallationUsePolicy`, and `installation_drawing_facts()`.
- Produces: `CabinetryDocumentLinks`, `build_cabinetry_review_html()`, `build_cabinetry_fabrication_html()`, `build_cabinetry_audit_html()`, and compatibility wrapper `build_cabinetry_html()`.

- [ ] **Step 1: Add the frozen link/basename type and shared shell helpers**

  Validate all hrefs as relative HTML basenames. Extract one release-banner helper, one document-nav helper, and one responsive/print CSS base; do not add a generic page framework or `surface=` branch.

- [ ] **Step 2: Compose A0/I1 review/install sheet**

  Include typed release summary, active non-PASS gates, concise dimensions, installation drawings, field/signed-clearance checklist, installation-only hardware/source, installation/commissioning steps, optional isometric/3D viewer, and companion links. Exclude shop and audit ledgers.

- [ ] **Step 3: Compose S1+ fabrication packet**

  Include fabrication readiness/tools, shop drawings, part key, detailed dimensions, cut/edge/hardware/machining schedules, and fabrication/assembly/shipping steps. Include the shared release banner and companion links, but no installation sequence or audit ledger.

- [ ] **Step 4: Compose R1 review trace**

  Include verdict counts, shared release boundary, full findings/evidence/source-map tables, source links, and a landing-page link. Exclude product GLB/JS and shop tables.

- [ ] **Step 5: Make `build_cabinetry_html()` a compatibility wrapper**

  Preserve its existing call signature and route it to the review composer with default basenames. Keep `generate_released_build_document()` working for single-document callers.

- [ ] **Step 6: Run ownership/budget tests and verify GREEN**

  Run `tests/test_cabinetry_project_report.py`; expected: all exact fact, source, release mutation, vocabulary, surface ownership, and budget tests pass.

### Task 5: Generate the linked document set once

**Files:**
- Modify: `scripts/cabinetry_documents.py`
- Modify: `scripts/cabinetry_project_report.py`
- Test: `tests/test_cabinetry_instruction_manual.py`

**Interfaces:**
- Consumes: the three composers, one compiled `PackedProject`, one manual, one panel-render pass, one view-render pass, and one GLB export.
- Produces: `build_cabinetry_document_set()` plus compatibility alias `build_cabinetry_document_pair()`; old return keys plus fabrication/audit paths and SHA-256 values.

- [ ] **Step 1: Add a single shared-asset render helper**

  Return product assembly, six view data URIs, viewer payload, and GLB bytes without writing a document. Reuse it from both the set generator and standalone build generator.

- [ ] **Step 2: Implement the document-set orchestrator**

  Add `FABRICATION_BASENAME` and `AUDIT_BASENAME`; compile/release once; build the manual once with typed related links; render panel images and product assets once; write review, manual, fabrication, and audit HTML; return paths/hashes while preserving `technical_*`, `manual_*`, `panel_count`, `asset_keys`, and `panel_images`.

- [ ] **Step 3: Keep the old pair function as an alias**

  Route `build_cabinetry_document_pair()` to the set function so existing automation receives the additional files without breaking old keys.

- [ ] **Step 4: Run the real bundle test and verify GREEN**

  Run the real document test at 480 × 360. Assert four files exist, every reciprocal href resolves, only the review sheet embeds the GLB/viewer, and panel/diagram counts remain six/nine.

### Task 6: Verify, review, regenerate, and deliver

**Files:**
- Regenerate: `outputs/frameless_three_drawer_40/*.html`
- Add: `.superpowers/sdd/review-db40-reader-surfaces.md`
- Update delivery copies under `~/Downloads/Build Documents/` and the organized JoelBrain attachment folder.

**Interfaces:**
- Consumes: the final clean committed tree.
- Produces: reviewed, hash-identical delivered HTML documents.

- [ ] **Step 1: Run focused and platform regression tests**

  Run the two cabinetry document test files, instruction-panel/viewer tests, and all pack cabinetry tests. Read every failure; do not weaken a check.

- [ ] **Step 2: Generate into a scratch directory and audit visible metrics**

  Measure words/tables/rows after removing scripts/styles. Verify primary content budget and exact surface ownership before touching accepted outputs.

- [ ] **Step 3: Perform desktop/mobile/print visual QA**

  Inspect 1440 px and 390 px widths. Verify no horizontal page overflow; release/HOLD appears before install steps; setout drawings remain legible; companion links resolve; print groups do not split critical drawing/checklist blocks.

- [ ] **Step 4: Request fresh adversarial and naive-reader reviews**

  Give reviewers only the generated set and requirements. Fix all Critical/Important findings and obtain confirmation. The naive reviewer must identify the hold, size, field checks, anchor setout, and correct document for fabrication within two minutes.

- [ ] **Step 5: Run the final suite gate**

  From the clean frozen commit run:

  ```bash
  PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest -n auto -q
  ```

  Read the exit code and complete counts before any completion claim.

- [ ] **Step 6: Regenerate and deliver from the accepted commit**

  Generate the four DB40 files, verify SHA-256 hashes, copy byte-identically to Downloads and the vault, then commit/push only the intended project and vault paths.
