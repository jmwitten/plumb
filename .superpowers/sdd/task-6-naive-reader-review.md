# DB40 naive-reader review

**Overall: FAIL.** The package contains a complete-looking parts inventory and a plausible six-stage build sequence, but I would not release it to a capable handyman as written. The stop/release boundary is internally contradictory, and the drawer-hardware and field-installation instructions still require expert interpretation or external material.

## Critical

1. **The release language simultaneously authorizes and forbids purchasing/cutting.** The project sheet says `Model/shop-data gate: PASS` and “fabrication ready,” while the adjacent status says `Purchasing/cutting preflight: OPEN`; the preflight text then says nesting, finish/grain, edge-band SKU, waste, yield, and sheet count must be approved “before purchase or cutting.” As a fresh builder I cannot tell whether PASS means I may start making parts. “Fabrication ready” must not appear while the purchasing/cutting gate is open; the leading status should instead say, in plain language, `MODEL DATA PASS — DO NOT BUY OR CUT` until those items are closed.

2. **The installation HOLD is not stop-first in the standalone assembly path.** Opening the manual automatically lands at `#panel-1`, bypassing the front safety banner, master inventory, and panel index. Panel 6 then opens with the action title “Install and commission the empty cabinet,” a list of two anchor screws, and installation tools; the `Installation planning HOLD` appears only after a large assembly image. A reader following the panel navigation could reasonably stage or drive the anchors before reaching the lower warning. Because this is the tip-over/load-path gate, panel 6 must begin with an unavoidable full-width `DO NOT ANCHOR / INSTALL / LOAD` stop banner and signed-clearance prerequisite; its title must not say “Install and commission” while release is HOLD.

## Important

1. **The drawer/runner/stabilizer installation is not self-contained enough to build correctly.** Panel 4 compresses pinion housings, two racks, linkage rod, adapters, locking clips, runner pairs, handed T51.7601 locks, and 42 Blum 606N screws into one prose operation. Its model image identifies 15 wood parts but shows none of that hardware; the three small schematics show station dots and proxy blocks, not component handedness, orientation, clipping order, runner insertion, or the four MOVENTO adjustments. Completion depends on several live Blum links and page references. By comparison, Blum's own MOVENTO material separates drawer preparation, runner mounting, locking-device installation, insertion/removal, adjustment, and lateral-stabilizer assembly into diagrammed steps. Those substeps and essential orientation diagrams need to be embedded or the exact manufacturer PDFs need to ship with the package.

2. **Required finish-face and grain orientation is never converted into an executable per-part instruction.** The cutting preflight requires approval of grain direction, and thirteen 19.05 mm parts say “finish face/grain to verify,” but the cut list has no face/grain column and the shop drawings have no grain arrows or inside/outside face marks. After selecting a veneered/appearance panel, a builder still cannot determine the intended grain direction for the three fronts, cabinet sides, stretchers, or toe pieces. Add per-part face and grain targets, or explicitly mark them non-directional.

3. **The field drawings contain label collisions at the places most likely to be used for setout.** In `views/front.png`, the countertop-boundary note, top cabinet line, stud labels, and anchor leaders crowd/overlap at the cabinet top. In `views/anchor_section.png`, the vertical `MODEL FINISH` and `NO ANCHORAGE CREDIT` labels overlap. In `views/exploded.png`, the staggered drawer fronts and their labels overlap one another and the cabinet outline, making diagrammatic offsets look like part interference. These should be redrawn with non-overlapping leaders and readable text at the inline document scale before relying on them in the shop or field.

4. **The required signed installation/fit record does not exist in the package.** The installation instructions say to record high-floor/wall deviations and shim locations and to “enter measurements and corrections in the signed fit record,” but neither the project sheet nor manual provides fields for the clearance document identifier, actual stud centers, datum measurement, shim/bearing locations, anchor product/count, final level/plumb/diagonals, drawer reveals, corrections, installer, or date. Without that record there is no defined way to prove the HOLD was cleared or the unloaded commissioning checks were completed.

## Concise disposition

- HOLD clarity: **FAIL**
- Parts quantity coverage: **PASS**, subject to the explicitly open material/edge-band/nesting selections
- Carcass and drawer-box sequence: **PASS** at a high level
- Drawer/runner/stabilizer/pull execution: **FAIL** as a self-contained manual
- Field setout and installation closeout: **FAIL**

