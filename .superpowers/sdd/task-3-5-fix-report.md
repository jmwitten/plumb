# DB40 reader-surface consolidated review fix

Date: 2026-07-14  
Review addressed: `task-3-5-review.md`

## Initial closure

The single Critical and four Important findings are fixed in one round. The
three small correctness/readability findings that were adjacent to the fix are
also closed; the review's module-extraction recommendation remains a separate
follow-up rather than being mixed into this correctness change.

## RED evidence

The added regressions failed against `2b8626c` for the reproduced reasons:

- the release banner contained the complete 110-word policy notice and the
  notice was duplicated into fabrication/audit output;
- toe facts exposed only a bounding box and accepted a collapsed sleeper;
- moved cabinet sides and moved/shortened anchor strips were accepted;
- duplicate anchor roles and screw-parameter/catalog disagreement were not
  rejected;
- hostile image data could enter `src` markup;
- standalone B30/DB40 output advertised DB40 companion files it did not write;
- installation figures lacked full-resolution/mobile/print affordances;
- front-view ink touched both raster edges because the side labels were clipped.

## Implementation

- Projected all four toe-member rectangles and the material intervals actually
  intersected by the anchor section. The plan now draws the four rectangles;
  the section draws the front and rear rails with the modeled void between.
- Removed the invented shim triangle. The section now asks the field team to
  record shims only at actual toe members without inventing a location.
- Added one wall/floor-local cabinet frame and exact frame, strip, anchor-role,
  screw-parameter, strip-containment, toe-corner, and adjacency invariants.
- Kept the release cards short. The full typed warning remains in the canonical
  `install.release_gate` reader step; the review sheet retains compact CPSC
  source links without copying the long notice into shop/audit documents.
- Made review navigation explicit. The four-file orchestrator passes the full
  link set; standalone generation renders no local link unless its companion
  was explicitly supplied.
- Allocated distinct countertop/anchor annotation lanes, widened the front
  drawing margins, drew installation figures one-per-row, added full-resolution
  links and mobile horizontal pan, and made print put each installation figure
  on its own page.
- Validated and escaped PNG/JPEG/WebP base64 data URIs at the composer boundary.
- Corrected fabrication ownership wording: only installation plan and anchor
  section geometry are owned by the review sheet.

## GREEN evidence

```text
35 passed in 16.60s
```

for `tests/test_cabinetry_project_report.py`.

```text
310 passed, 3 skipped in 74.03s
```

for the affected cabinetry, drawer, instruction, and viewer suites.

Real four-file regeneration completed in 6.7 seconds. Final accepted metrics:

| Surface | Visible words | Tables | Rows |
|---|---:|---:|---:|
| Review/install landing | 1,224 | 7 | 35 |
| Illustrated manual | 7,989 | 1 | 9 |
| Fabrication packet | 10,535 | 14 | 340 |
| Review trace | 3,268 | 3 | 133 |

Desktop browser QA at 1440 × 1000 found no horizontal overflow; the cover is
512 px tall rather than 1,238 px. Mobile QA at 390 × 844 found no page-level
overflow, while the 900 px installation drawing canvas remains intentionally
pannable and all three full-resolution links are present.

## Final completion state

Fresh adversarial and no-context-builder confirmations both returned PASS with
zero remaining Critical and zero Important findings. The 1,900-line report
module remains a deliberately deferred, separately reviewed refactor rather
than correctness work mixed into this release.

## Confirmation and naive-reader closure

The first adversarial confirmation found one remaining Important projection
hole: toe members could move together in Z, the strip and anchors could move
together in Y/Z, and a stud could move or resize while the drawing silently
recreated its expected geometry. Three RED mutations now pin those cases. The
projection checks every toe against the floor high point, the strip against its
absolute cabinet/wall frame, and each stud against the surveyed wall origin,
rotation, height, width, and depth.

The no-context builder review then failed the package on two Critical and four
Important reader problems. The consolidated fix:

- replaces the contradictory `fabrication ready` wording with the unavoidable
  `MODEL DATA PASS — DO NOT BUY OR CUT` boundary;
- adds a per-part purchasing/cutting release record for product/lot, finish
  face, grain direction, nesting orientation, and approval;
- prevents the manual from auto-jumping past its cover and inventory;
- changes held Panel 6 to `Installation HOLD`, places a full-width
  `DO NOT ANCHOR / INSTALL / LOAD` alert before hardware or imagery, and adds a
  printable signed installation/fit record;
- expands the selected MOVENTO/ZS7M686MU work into ten executable substeps plus
  a nine-operation stabilizer sequence diagram derived from the selected Blum
  procedure and model cut lengths; and
- redraws the front, anchor-section, and exploded views with separated
  annotation lanes and non-overlapping drawer groups.

Focused and broad verification after that round:

```text
52 passed in 28.98s
```

for the complete cabinetry report and manual suites, and:

```text
318 passed, 3 skipped in 74.06s
```

for affected cabinetry, drawer, instruction, presentation, and viewer suites.
Direct browser QA confirmed that an unfragmented manual opens at the cover with
an empty hash and zero scroll, while direct `#panel-6` navigation reaches the
stop-first held installation panel.

## Final gate and accepted artifacts

The frozen final tree passed the full suite:

```text
1742 passed, 3 skipped, 1 xfailed in 888.22s (0:14:48)
```

Final accepted generation produced these SHA-256 values:

- review/installation: `633a0617f3a90d36a3789a42c7cb7a2f906840fc7ec3c734c722e4acc6ff7288`
- assembly manual: `8510c4aca6a6ae5608160f853424969e46da09420cbab2d184c08c9f5113bb36`
- fabrication packet: `bb68cecfbe3575e9fdf776afdf5f77e0a3361d61f55a082b5595a5e2e404c3e0`
- review trace: `b845254ddc83b149be073113270113a3311f9ebf06f18db789bd705c303f1ebc`
