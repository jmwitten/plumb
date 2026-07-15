# Naive-Builder Read — DB40 Cutting Guide (Round 3)

**Reader persona:** homeowner, normal DIY skills, no prior knowledge of the project, holding only the 11-page `cutting_guide_print.pdf`.
**Verdict:** CONDITIONAL PASS. One contradictory dimension can produce a wrong part unless the reader resolves it using the document's own ≈-rule. Everything else is buildable.

---

## 1. What I would buy and machine, in order

### Buy
The document tells me clearly that hardware buying is not my job here — the "BEFORE YOU START" box says to buy the hardware kit from the **assembly manual's kit card FIRST**, because the drilling/cutting steps below use that kit's makers' templates, matching stepped bit, and stabilizer rack/rod stock. I do not have the assembly manual, so I cannot buy hardware from this PDF alone — but the boundary is stated up front, so this is expected, not a gap.

Sheet goods I buy myself, in four thickness groups (page 2 wood list):
- Garnica Duraply 3/4 in — 13 parts
- 16 mm plywood — 12 parts
- 12 mm plywood — 3 parts
- 6.35 mm plywood — 1 part

Sheet count and nesting are explicitly my own job ("plan your own nesting from the wood list before buying"). Every part has a size, so I can lay out a nest. Fine.

### Cut all 29 parts (steps 1–2)
Mark show face and grain on every part (my call, recorded on the release record — stated boundary), start the release record, then cut all 29 blanks to the page-2 wood list. Sizes with `≈` are cut to the exact mm printed; sizes without `≈` are cut to the tape-mark fraction. Label every part; left and right are not interchangeable.

For each blank I have both a face dimension and a length/height, so I can cut every one — **except** the bottom drawer front, where the two printed values disagree (see risk 1).

### Machining, in the document's order
- **Step 3 — captured-back groove:** on left side, right side, cabinet bottom, rear stretcher. ≈1/4" (6.85 mm) wide × 3/8" deep, one blade/depth setting for all 4, each at its own printed up-from-lower-left position (bottom 574.175, left side 9.525, rear stretcher 94.75, right side 574.175 mm). Dry-fit the 6.35 mm back before glue.
- **Step 4 — 6 toe-screw centers** on the cabinet bottom, marked only (driven during assembly), from front-left corner: columns 244.475 / 488.95 / 733.425 mm, front row 85.725 up, rear row 564.65 up. No screw path may enter the rear groove band.
- **Step 5 — drawer-bottom groove** on all 12 drawer-box parts, inside face: ≈1/2" (12 mm) wide × 1/4" deep, starting 1/2" up from the bottom edge, one fence setting for all 12.
- **Step 6 — drawer-side screw holes:** 2 near each end (4 total) on each of the 6 drawer sides, from the outside face, columns 5/16" from each end, first hole 1-1/2" up, second hole 9"/6"/3" up for bottom/middle/top. Stepped bit matched to the drawer screws; test on a clamped offcut first.
- **Step 7 — drawer-back notches + hook holes** on the 3 backs only: 50 × 13 mm notches at both lower corners, two 6 mm-dia × 10 mm-deep hook holes, 7 mm in from each side, 24 mm up, from the lower-left rear corner.
- **Step 8 — drawer-front pilot holes:** template on each of the 3 drawer-box front corners, 2 pilots per side, 2.5 mm × 10 mm, 75° set by the template.
- **Step 9 — 15 runner screw stations** per end panel, inside face, from the front-lower corner: columns 10 / 32 / 37 / 261 / 357 mm from the front edge, rows 57.05 / 386.45 / 652.45 mm up, 2.5 mm pilots with a depth stop so the bit cannot break through the outside face.
- **Step 10 — cut 3 gear racks to 560.0 mm and 3 linkage rods to 659.9 mm** from kit stock, deburr, keep each drawer's set together.
- **Step 11 — 4 applied-front clearance holes** through each of the 3 drawer-box fronts, from the inside face, 5 mm dia through, columns 233.975 mm in from each end, heights per box (bottom 63.5/190.5, middle 44.45/133.35, top 25.4/76.2 up).
- **Step 12 — 2 pull holes** through each of the 3 decorative fronts, 5 mm dia, 224 mm apart, left hole 394.5 mm from the left edge, height per front (bottom 177.475, middle 127, top 79.375 up), backer board behind the show face, check against the purchased pull.
- **Step 13 — 9 cabinet-end step-drilled holes** per end panel, outside face, from bottom-front corner, at the printed up/from-front values (both ends identical).
- **Step 14 — 4 toe-rail holes** per rail (front + rear), from left-bottom corner, pairs 9.525 mm in from each end, heights 30.48 / 71.12 mm up.
- **Step 15 — edge-band the 19 banded parts** (each part's banded edges named on its wood-list row), trim, inspect, never band a grooved edge, finish the release record.

Part counts all reconcile: 13 + 12 + 3 + 1 = 29 cut parts; 7 Garnica + 12 plywood = 19 banded parts, matching step 15's numbered list.

---

## 2. Wrong-build risks (most important)

**RISK 1 — Bottom drawer front height: the fraction and the printed mm contradict each other. (Major.)**
Wood list row: `Bottom drawer front — ≈39-13/16" (1012 mm) × 13-15/16" (253 mm)`.
- 13-15/16" = **354.0 mm**, not 253 mm. 253 mm = 9-15/16", which is the *middle* drawer front's height. The mm value has been copied from the middle row.
- Cross-check confirms 354 mm is correct: step 12 puts the bottom front's pull hole at 177.475 mm up, and 177.475 × 2 = 354.95 mm — i.e. centered on a ~354 mm-tall front. The other two fronts pass the same test (middle 127×2=254 ≈ 253; top 79.375×2=158.75 ≈ 158). Only the bottom row is broken.
- **How a careful reader still goes wrong:** the height `13-15/16"` carries no `≈`, so by the document's own rule ("a size written *without* ≈ is on a tape mark — cut to the fraction") the reader should cut 13-15/16" and be correct. But the entire document trains the reader to treat the printed millimeter as the precise ground truth, and here a millimeter is printed on a non-≈ row (which normally has no mm at all). A reader who resolves the conflict in favor of the mm cuts the bottom front **100 mm too short** — shorter than its own drawer box (253.5 mm tall), so it cannot cover the box. Nothing at the cut step flags the disagreement; it is only caught much later at pull-drilling or assembly. This is the single reason the document is not a clean PASS.

**RISK 2 — Cabinet-side groove can land on the wrong edge if the show-face/rear-edge call is inconsistent. (Medium, mitigated.)**
Left and right sides are cut from identical blanks (30-1/2" × 590.05 mm). The only thing that makes one a left and one a right is the show-face/grain mark I place in step 1, and the captured-back groove position differs enormously between them (9.525 mm vs 574.175 mm up from lower-left). If I mark the two sides' show faces inconsistently, I can groove both the same way and get two identical panels instead of a mirror pair. Mitigation is real: the step-3 note gives a self-check ("every groove hugs its part's cabinet-rear edge; if yours lands near the opposite edge, the blank is flipped"), and the front edge is the banded edge, so the rear edge is identifiable. A careful reader recovers, but the error is plausible.

**RISK 3 — The "front edge" datum for the 15 runner stations is never tied to a physical feature. (Medium.)**
Step 9 measures the 15 runner pilots from the panel's front edge, and the column values are clustered near the front (10/32/37 mm) and asymmetric front-to-back. If I pick the wrong end as "front," the whole runner pattern mirrors and won't line up with the drawer runners. The document says "measured from the front edge, never from the runner's set-back" but never states that the front edge is the banded/finished edge. It's a reasonable inference (a cabinet's front is the banded open face), but it is left to the reader.

**RISK 4 — Inside/outside-face assignment on symmetric drawer-box parts is the reader's to get right.** Step 5 grooves the *inside* face, steps 6 and 11 drill from *outside* / *inside* respectively, and the plywood parts are face-symmetric until I assign a face. Getting groove-on-inside and holes-from-correct-face right depends on my step-1 face marking being consistent per part. The drawer-side hole pattern is symmetric front-to-back (both columns share heights), so left/right mirroring there is harmless — but a swapped face on a grooved part would put the groove on the show side. Low-to-medium; recoverable by care.

---

## 3. Smaller frictions

- **"Cut all 29 parts to the wood list on the kit page" (step 2)** — the wood list is on page 2 of *this* guide, not on a separate "kit page." A reader may hunt for a kit page that isn't here, or wonder if the page-2 list is superseded.
- **Inconsistent mm parentheticals.** Non-≈ dimensions normally carry no millimeter value (e.g. cabinet bottom's 38-1/2"), but the bottom-drawer-front row anomalously carries one — and it's the wrong one. The inconsistency is itself what makes Risk 1 easy to trip on.
- **Tiny callout text.** The dense mm lists in the diagram boxes (especially step 13's nine holes and step 9's station table) are small and hard to read on a printed Letter page; a misread digit becomes a mis-drilled hole.
- **Dark, low-contrast isometric renders.** Steps 1/2/10/15 are near-black gray on gray; the step-15 render crowds 19 tiny numbered circles onto a dark box, making it hard to match a number to a location.
- **"2 pilot holes per side" (step 8)** is ambiguous wording (per corner? per edge?), though the physical template resolves it.
- **Step-3 self-check wording** ("groove hugs its part's cabinet-rear edge") maps awkwardly to the rear stretcher, whose groove sits along a top edge rather than a rear edge; a literal reader may second-guess a correctly-placed groove.

---

## 4. Grade — CONDITIONAL PASS

A careful homeowner who applies the document's own stated rule — *no ≈ means cut to the fraction* — cuts the bottom drawer front to 13-15/16" (354 mm) and produces a correct kit; every other dimension, groove, hole, notch, and band is fully specified and internally consistent, and the stated boundaries (hardware on the kit card, nesting and show-face choices on the reader) are all flagged before work starts. The reason it is not a clean PASS is Risk 1: the same row prints a contradictory 253 mm, and the document elsewhere primes the reader to trust the millimeter as ground truth. Resolving that contradiction the right way is an assumption the reader must make; a reader who trusts the mm cuts a part 100 mm short and doesn't find out until assembly. One contradictory value, with the document's own convention pointing to the correct answer, is a conditional pass rather than a fail — but it must be fixed (print 354.0 mm, or drop the erroneous parenthetical) to reach PASS.
