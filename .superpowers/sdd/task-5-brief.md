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
