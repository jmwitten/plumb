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
