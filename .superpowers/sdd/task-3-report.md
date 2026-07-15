# Task 3 implementation report

Status: **DONE**

Commit: `38d9274` (`feat: publish linked DV72 installation guide`)

No push was performed. Independent adversarial technical and no-context installer reviews are intentionally delegated to the parent task.

## Delivered

- Extended the ordered DV72 package from four documents to five, with `dv72_installation_guide.html` fifth.
- Built typed `RelatedDocumentLink` values from the canonical `FILENAMES` tuple and passed the complete five-link set to the guide builder.
- Added the guide label, updated all technical footers to `five reader projections`, and updated the generator description.
- Preserved the existing fabrication, installation, and trade authority banners and pinned the guide's `INSTALLATION HOLD` and `STOP BEFORE COUNTERTOP` boundaries.
- Found and fixed a rendered print defect during required QA: the `max-width:850px` mobile rule also applied to print, collapsed the record grid to one column, and clipped reviewer/date/final-STOP/footer content. A print rule now restores the two-column record and fixed footer.
- Updated progress and measured reuse/bespoke accounting while preserving the existing disclosure that no repository-wide CAD-suite pass is claimed.

## TDD evidence

Five-document closure RED:

```text
2 failed, 30 passed in 5.86s
```

The failures were the expected four-file inventory and stale `four reader projections` footer. After minimal integration, the relevant suite passed:

```text
66 passed in 5.53s
```

Print regression RED:

```text
1 failed, 25 deselected in 2.42s
```

The failing assertion proved the print cascade lacked explicit two-column record/fixed-footer restoration. After the minimal CSS override:

```text
1 passed, 25 deselected in 3.01s
```

The shell's bare `pytest` is unavailable under its active Python 3.13 shim. All recorded Python verification used the repository interpreter:

```bash
PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest ...
```

## Deterministic generation

The corrected package was generated twice into `/tmp/dv72-guide-one` and `/tmp/dv72-guide-two`. `diff -ru` returned no output. Both generations contained exactly five files with matching hashes. The guide hash was:

```text
72838b655511c8d25c725c7eeabf48aec3ae8c975381abc9832f59798e4ecb2a
```

The final generator run wrote the same five-file inventory to `outputs/floating_double_sink_four_drawer`.

## Browser QA

The generated directory was served on `127.0.0.1`. Actual Chrome browser control navigated all five documents at exact CSS-pixel viewports:

- 1280 x 900
- 390 x 844

The browser's viewport capability maps its requested outer dimensions through an 80% CSS scale, so it was calibrated to 1600 x 1125 and 488 x 1055 outer pixels; browser-side readings confirmed the required exact inner viewports.

At both sizes:

- every document exposed all five local HTML links;
- every local document navigation resolved (HTTP 200/304);
- document-level horizontal overflow was false;
- critical HOLD, STOP, record-row, and action-frame elements reported no clipped content;
- the guide exposed seven sheets with complete `1 / 7` through `7 / 7` labels.

Screenshots were visually inspected for the desktop cover, mobile cover, and mobile final record/STOP region. No remaining clipping or overflow was observed.

## Print/PDF QA

Chrome produced a PDF from the served guide. Poppler reported:

```text
Pages: 7
Page size: 612 x 792 pts (letter)
```

All seven corrected pages were rendered to PNG and visually inspected individually/contact-sheet. Evidence:

- composed sheet count equals PDF page count (7);
- all pages are US Letter;
- action frames 1-5 remain whole and do not cross pages;
- footers are complete from `1 / 7` through `7 / 7`;
- sheet 7 contains every record field, final STOP box, and footer.

## Final verification

Post-commit scoped suite:

```text
228 passed in 16.12s
```

The intended diff and cached commit both passed `git diff --check`. Self-review found no remaining authority, link-closure, load-path, source-model, responsive, or print-layout issue in the Task 3 diff.

## Concerns / handoff

- The parent task obtained both independent reviews; the final disposition below records closure of all Critical and Important findings.
- The worktree is not globally clean because parent-owned Task 1-3 brief/report edits predated this task and remain unstaged. Three of those unrelated files contain trailing blank-line warnings, so an unscoped `git diff --check` reports them; Task 3's intended and committed files pass the check.
- `.superpowers/sdd/task-3-report.md` is included with the review-fix commit so the final evidence travels with the implementation.
- No push was performed, as requested.

## Final review disposition

All Critical and Important review findings were addressed. The guide and five-file package now project typed support bearing elevations, wall planes, and governing authority; preserve the safe countertop-underside load path without claiming cabinet-bottom bearing; retain all five release findings as unreleased; separate FIELD and STRUCTURAL releases; distinguish selected product revision `2022.1.0` from current-confirmation revision `2024.1.1`; avoid fixed hole patterns, unconditional handling instructions, and service-access approval; define datums and practical dual units; identify loads as comparison-only; name the exact package basenames; and require accepted tolerance/shim schedules.

Review-fix TDD evidence:

```text
14 failed, 58 passed in 4.52s
72 passed in 4.00s
219 passed in 5.82s
```

The corrected print-density regression first failed as intended:

```text
1 failed, 35 deselected in 2.30s
```

After the print-only action-frame adjustment:

```text
1 passed, 35 deselected in 2.29s
```

Fresh final scoped verification:

```text
242 passed in 15.82s
```

Fresh deterministic generation produced the same ordered five files twice with an empty recursive diff. The final installation-guide SHA-256 is:

```text
846d5f80c119437fa03ce6c6ab4378629c8b5e699dd8f9f8b3c6a73557d9a88e
```

Browser verification at an exact `390 x 844` CSS viewport confirmed no page-level horizontal overflow, all five deliberately scrollable SVG wrappers contained within the page, no clipped hold/release/record/final-STOP regions, complete `1 / 7` through `7 / 7` sheet labels, and all five release rows remaining `UNKNOWN`.

The final Chrome PDF contains seven `612 x 792 pt` US Letter pages. A Poppler-rendered seven-page contact sheet and the corrected detailed pages were visually inspected: action frames remain whole, sheets 4 and 6 no longer collide with their footers, release fields remain legible, and the final record sheet is complete.
