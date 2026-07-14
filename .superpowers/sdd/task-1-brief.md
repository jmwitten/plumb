### Task 1: Pin surface ownership and content budgets

**Files:**
- Modify: `tests/test_cabinetry_project_report.py`
- Modify: `tests/test_cabinetry_instruction_manual.py`

**Interfaces:**
- Consumes: current `compile_project_file()`, `CPR.build_cabinetry_html()` and detailed renderer functions.
- Produces: failing contracts for `build_cabinetry_review_html()`, `build_cabinetry_fabrication_html()`, `build_cabinetry_audit_html()`, and the four-file output set.

- [ ] **Step 1: Add a visible-text helper and failing primary-sheet test**

  Strip `<script>` and `<style>` blocks before counting words. Assert the DB40 primary sheet has no more than 2,500 visible words, 80 `<tr>` rows, or eight tables; includes the four-part model/procurement/structure/install status matrix, active UNKNOWN rules, key dimensions, field checks, and installation steps; and excludes `Cut list`, `Machining schedule`, `Fabrication`, `Validation findings`, `Evidence register`, and `Source map` headings.

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
