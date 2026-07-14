# Task 1 Report — DB40 Surface Ownership Contracts

## Scope

Added RED-only contract tests for the approved DB40 reader-surface split. No
production code, model data, validation rule, release state, process order, or
generated artifact was changed.

## Files

- `tests/test_cabinetry_project_report.py`
  - added `_visible_text()`, which removes complete `script` and `style` blocks
    before stripping tags and counting reader-visible words;
  - added the DB40 primary-sheet budget, required-content, and heading-ownership
    contract;
  - added the compatibility contract for
    `build_cabinetry_review_html()`;
  - added fabrication and audit composer ownership contracts using the complete
    output of the existing canonical detailed renderers.
- `tests/test_cabinetry_instruction_manual.py`
  - extended the real generated-document test from two outputs to four paths and
    four verified SHA-256 values;
  - pinned the approved stable basenames and relative companion-link graph;
  - retained the existing six panel-asset, instruction-panel payload, diagram,
    coordinate-key, procedure-link, accessibility, and self-containment pins.
- `.superpowers/sdd/task-1-brief.md`
  - task brief supplied by the controller; included in the task commit as
    requested.
- `.superpowers/sdd/task-1-report.md`
  - this report.

## Baseline

Before editing, the exact focused command passed:

```bash
PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest -q tests/test_cabinetry_project_report.py tests/test_cabinetry_instruction_manual.py
```

Result: `20 passed in 22.21s`.

## Verified RED

After the final test edits, the same exact command produced:

```text
5 failed, 19 passed in 24.17s
```

The five failures are the intended unmet contracts:

1. The current primary sheet is over every budget: 13,825 visible words versus
   2,500; 454 table rows versus 80; and 18 tables versus eight. It still owns
   the `Cut list`, `Machining schedule`, `Fabrication`, `Validation findings`,
   `Evidence register`, and `Source map` headings. It also lacks the approved
   `Model/shop-data gate: PASS` and `Purchasing/cutting preflight: OPEN` status
   labels. The active UNKNOWN rule ids, key dimensions, field checks, and all
   installation step ids are already present and did not appear as accidental
   missing-content failures.
2. `build_cabinetry_review_html()` is absent (`AttributeError`).
3. `build_cabinetry_fabrication_html()` is absent (`AttributeError`).
4. `build_cabinetry_audit_html()` is absent (`AttributeError`).
5. The real pair generator lacks `fabrication_path`, `fabrication_sha256`,
   `audit_path`, and `audit_sha256`.

There were no collection, syntax, import, fixture, rendering, or unexpected
existing-test failures. The 19 unaffected tests passed.

## Self-review

- `git diff --check` is clean.
- Only the two authorized test modules were modified; no production file was
  touched.
- Existing exact truth pins were retained. The real document test was extended
  after its existing generation call rather than replacing its panel/viewer and
  accessibility assertions.
- Fabrication completeness is asserted by requiring the exact complete outputs
  of `_render_cut_list`, `_render_edge_banding`, `_render_hardware`,
  `_render_machining`, and both owned step renderers. Audit completeness uses
  the exact `_render_findings` and `_render_source_map` outputs. This makes the
  tests sensitive to omitted records without copying a second hand-maintained
  ledger into the test.
- The link contract uses relative HTML basenames only and verifies returned
  hashes against file bytes.
- The RED result is intentionally not repaired in this task; focused composers
  and document-set production belong to later implementation tasks.

## Concerns

None. The failures match the approved plan and are isolated to the missing
reader-surface implementation.
