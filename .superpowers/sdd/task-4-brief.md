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

  Include typed release summary, shared procurement-preflight holds, active non-PASS gates, concise dimensions, installation drawings, field/signed-clearance checklist, installation-only hardware/source, installation/commissioning steps, optional isometric/3D viewer, and companion links. Call the passing gate `Model/shop-data gate`, never the broader `Fabrication ready`. Exclude shop and audit ledgers.

- [ ] **Step 3: Compose S1+ fabrication packet**

  Include fabrication readiness/tools, shop drawings, part key, detailed dimensions, cut/edge/hardware/machining schedules, and fabrication/assembly/shipping steps. Include the shared release banner and companion links, but no installation sequence or audit ledger.

- [ ] **Step 4: Compose R1 review trace**

  Include verdict counts, shared release boundary, full findings/evidence/source-map tables, source links, and a landing-page link. Exclude product GLB/JS and shop tables.

- [ ] **Step 5: Make `build_cabinetry_html()` a compatibility wrapper**

  Preserve its existing call signature and route it to the review composer with default basenames. Keep `generate_released_build_document()` working for single-document callers.

- [ ] **Step 6: Run ownership/budget tests and verify GREEN**

  Run `tests/test_cabinetry_project_report.py`; expected: all exact fact, source, release mutation, vocabulary, surface ownership, and budget tests pass.
