# Adversarial review — cutting-guide v1 (DB40)

**Verdict: FIX-FIRST**
**Scope reviewed:** `git diff 18b219a..HEAD` at committed HEAD `4de2841`
(cutting_guide.py, cutting-guide test file, and the shared renderer edits in
action_frames / consumer_manual_html / instruction_panels / instruction_render).
Findings: **1 Critical, 2 Important, 3 Minor.**

> **Concurrency note (read first).** During this review the worktree
> accumulated large uncommitted edits (a naive-reader round-1 fix pass is
> running in parallel: `.superpowers/sdd/naive-reader-cutting-guide-round1.md`,
> `git diff --stat` shows ~253 insertions/111 deletions in cutting_guide.py
> beyond HEAD). **All line numbers and quotes below are from committed HEAD
> `4de2841`** (verified via `git show HEAD:...`), which is what the brief
> pinned. The in-flight working tree already reworks at least the note-reserve
> math (M3 below is fixed there: `notes_h = 9.0 + 5.2*max(len(notes),1) + 2.0`
> and `max_h = 100 - top - notes_h`). Re-run this review against the working
> tree once the naive-reader loop settles — some findings may already be
> resolved there and others may have shifted.

Test state at HEAD-with-inflight-tree: `tests/test_cabinetry_cutting_guide.py`,
`test_cabinetry_consumer_manual.py`, `test_instruction_panels.py` →
92 passed / 1 skipped; `test_action_frames.py`, `test_instruction_render.py` →
56 passed. Budgets: 11 composed pages (≤12), 1227 counted instructional words
(≤1500).

---

## CRITICAL

### C1 — Diagram title/caption text bypasses the caption honesty contract and hard-codes stale-able number-words
`src/rendering/consumer_manual_html.py:65,73` renders **both**
`diagram.title` (figcaption) **and** `diagram.caption` (`op-caption`
figcaption) to the reader. Neither passes through `validate_caption`
(action_frames.py:176) — only `FrameSpec.caption`/tool/warning/hold do. The
module docstring claims "every caption number is interpolated from a typed
artifact/model fact and re-audited by the caption contract"
(cutting_guide.py:5-9); that claim is **false for the diagram text surface**,
which is equally reader-visible.

Several diagram captions/titles hard-code English number-words that are
logically coupled to model counts but are not interpolated and not guarded:

- `cutting_guide.py:322-323` (`_back_groove_diagram`): "the **other three**
  positions … **Cut all four** with one saw" — coupled to `len(rows)` (=4),
  hand-typed as words.
- `cutting_guide.py:392` (`_box_joinery_diagram`): "Step-drill **two** holes
  near the front end and **two** near the rear end" — coupled to the plotted
  bore rows, hand-typed.
- `cutting_guide.py:424-426` (`_rear_prep_diagram`): "**two** lower-corner
  notches … **two** runner hook holes … **All three** drawer backs" — coupled
  to notch/bore rows and drawer count, hand-typed.
- Reused `instruction_manual.py:811-813` (`_toe_attachment_diagram`, in scope
  because the arc newly makes it a reader surface): title "**Six**
  bottom-to-toe attachment centers", caption "Mark all **six** centers …
  directly over the **two** toe-rail centerlines".

**Concrete failure (demonstrated).** Applying the branch's own mutation
(drop one `toe_attachment_station` row, as `test_caption_counts_follow_mutated_machining`
does) and rebuilding: the validated frame caption correctly becomes "Mark all
**3** toe screw centers", while on the same page the diagram title still reads
"**Six** bottom-to-toe attachment centers" and its caption "Mark all **six**
centers" — with only 3 circles actually plotted. The frame surface is honest;
the diagram surface silently lies. Per Standing Rule 1 ("Any hand-typed count,
dimension, or claim that could go stale = CRITICAL"), this is Critical.

**Fix direction:** route every reader-visible `OperationDiagram.title` and
`.caption` through `validate_caption` (with an `allowed_numbers` set derived
from the same typed facts), or express these counts as interpolated integers,
or drop the English number-words in favor of the interpolated `{len(rows)}`
form already used elsewhere in the same captions.

---

## IMPORTANT

### I1 — "each of the N sides/fronts" uniformity is asserted from a single representative part with no machine guard
`cutting_guide.py:856-858` computes `box_holes_per_side` from
`drawer_top_side_left` only; `:886-887` computes `holes_per_box_front` from
`drawer_top_front` only. Those single-part counts drive captions that claim
uniformity across all parts: "Step-drill {box_holes_per_side} screw holes in
each of the {drawer_sides} drawer sides" (`:990-992`) and "Drill
{holes_per_box_front} clearance holes through each of the {box_fronts}
drawer-box fronts" (`:1078-1079`). The diagram caption "**All three** drawer
backs use the same values" (`:426`) is the same pattern.

The caption contract does **not** catch this: it only checks each number is
*some* typed fact, not that the fact is representative of the "each" it claims.
A model where one drawer's side/front carries a different hole count would keep
these captions passing while making them false. This defeats Standing Rule 4
("uniformity claims must be machine-verified with a loud failure when rows
diverge") for exactly these two operations — contrast the runner
(`_runner_stations_diagram` end-vs-end compare, `:448`), end-panel
(`_end_panel_joinery_diagram` per-end compare, `:553`), toe-rail
(`:588`), and groove/`_uniform` guards, which **do** fire (verified: the
existing `differ between ends` / `disagree` mutation tests pass). Add an
analogous per-part-count `_uniform` guard for box-side and box-front hole
counts before the caption claims "each".

### I2 — Word budget excludes reader-visible diagram titles
`consumer_pages.visible_instructional_words` (:121-138) counts frame
caption/warning/hold/tool plus the diagram **captions** passed as
`extra_texts` in the test (`test_cabinetry_cutting_guide.py:79-88`), but not
the diagram **titles**, which render as prose figcaptions to the reader
(≈102 words across the 10 diagrams). Including them yields ≈1329 words — still
under 1500, so the acceptance number is not actually breached, but the guard
under-measures the visible instructional text and would not notice a future
title-driven overflow. (The dense dimension **notes**, ≈364 words, are
defensibly excluded as "layout data" per the owner's dense-coordinate rule;
the titles are not data.) Count diagram titles in the budget, or state the
title exclusion explicitly.

---

## MINOR

### M1 — Notch branch hard-codes the bottom edge and diverges from its own `model_point_mm`
`cutting_guide.py:261`: `x0, y0 = row.location_mm[0], 0.0` — the notch rect is
forced to the bottom edge (`y=0`), ignoring `row.location_mm[1]`, while
`model_point_mm=tuple(row.location_mm)` (:268) stores the real coordinate and
`check_bounds` is run on the *drawn* coords, not the real Y. All current
`runner_rear_notch` rows have `location_mm[1]==0`, so it is correct today, but
a notch with nonzero Y would be silently drawn at the bottom, pass bounds, and
carry a `model_point_mm` that contradicts the drawing. Plot the notch at its
actual `location_mm[1]` (or assert `location_mm[1]==0` loudly).

### M2 — Bore loop fabricates a phantom station when `count == 0`
`cutting_guide.py:264`: `for index in range(max(row.count, 1))` draws one bore
even when `row.count == 0`, contradicting "diagrams may only draw
machining-schedule rows" — it would emit a `circle` citing that `feature_id`
with a `model_point_mm` for a hole the schedule says does not exist, while the
caption counters (`sum(row.count …)`) show 0. No `count==0` row exists today,
so latent. Use `range(row.count)` and reject `count < 1` explicitly.

### M3 — (HEAD only; already reworked in the working tree) Note-region reserve did not scale with note count
`cutting_guide.py:208` at HEAD: `max_h = 100.0 - top - 26.0` reserves a fixed
26 units for notes, but the note block needs `9 + 4.5·N + 2` units
(`:283,285`). `_box_joinery_diagram` emits 5 notes (needs ~33.5) and escapes
clipping only because that blank's plotted box is short (`box_h≈16`); a tall
blank (`box_h→max_h`) with ≥4 notes would push content past the
`min(view_height, 100)` clamp and silently crop the last note rows. **The
in-flight working tree already fixes this** (`notes_h` now scales with
`len(notes)` and `max_h` subtracts it, so `top+box_h+notes_h ≤ 100` always).
Listed for HEAD completeness; confirm the fix stays in the merged version.

---

## Checked and sound (so the owner knows these were attacked)

- **Datum corner label is model-backed.** "MEASURE FROM THE LOWER-LEFT
  CORNER" (:231) is correct for every coordinate system: the plot maps origin
  `(0,0)` to the box's lower-left in both axis orientations, including the
  `x_is_vertical=True` branch (verified against the `confirmat_step_drill`
  side system `+X=up/cut-list length; +Y=toward wall`, whose origin
  `bottom-front` lands lower-left). The Y-flip (`1.0 - v_mm/v_extent`, :228) is
  correct. The generic per-diagram physical-edge words ("REAR EDGE",
  "front lower corner", "…face up" outline labels) are hand-asserted rather
  than derived from a typed front/rear fact, but I confirmed they are
  physically correct for the current model (e.g. the end-panel captured-back
  groove at `y=9.52` mirrors to `y=574.17` on the right end and genuinely sits
  at each panel's rear); they fall under the same unguarded-prose class as C1.
- **`view_height=100` default keeps existing rendering byte-identical.** The
  viewBox change (`consumer_manual_html.py:66`) renders `0 0 100 100` for every
  pre-existing diagram (`{100:g}`→"100"); only the new plan diagrams set a
  smaller height.
- **Shared-renderer edits are backward compatible for the accepted docs.**
  The consumer manual (letters present, non-empty picture keys) renders
  byte-identically: the grouped-inventory branch is gated on `inventory_groups`
  (default `()` → old path), the Hardware `<h2>` moved inside the
  `if consumer.letters` string with identical bytes, and scene callouts default
  `callouts=True` = `show_picture_key` default. One latent behavioral change to
  note: a *letter-less* consumer manual now omits its previously-empty
  `<h2>Hardware>` and an empty-picture-key frame omits its empty `<ul>`; no
  accepted document hits either path. Consumer/instruction/action-frame suites
  pass.
- **Fabrication/technical surface untouched.** The `instruction_render.py`
  `callouts=frame.show_picture_key` edit is in `render_frame_images`
  (ActionFrame/consumer path); the build document renders `InstructionPanel`s
  directly and does not route through it.
- **Completeness + symmetry guards fire.** Every released `fab.*` step maps to
  exactly one frame's `source_step_ids` (test passes), and the end/toe/runner
  "identical on both …" claims raise loudly on mutated inputs.

---

## Fix-round verification — commit `77f438a`

**Verdict: CONFIRMED.** All 1 Critical / 2 Important / 2 blocking Minor
findings are resolved in the committed tree, each with a regression test.
`tests/test_cabinetry_cutting_guide.py`: **40 passed**. Guide re-verified:
11 composed pages, 1315 instructional words (titles now counted, ≤1500).

- **C1 (Critical) — resolved.** `_machining_plan_diagram`
  (cutting_guide.py:186-195) now runs `validate_caption` over the diagram
  `title` and `caption` with a per-diagram `allowed_numbers` and the consumer
  forbidden-token set — the same contract frames use. Every diagram count is
  interpolated (`{len(rows)}`, `{total}`, `{per_column}`, `{per_front}`,
  `{backs}`, `{holes}`); the hand-typed number-words are gone
  (`"all four"/"other three"` → `_back_groove_diagram`; the shared
  `_toe_attachment_diagram` "Six"/"all six" is retired and replaced by
  `_toe_centers_diagram` interpolating `{total}`). Regression:
  `test_diagram_titles_follow_mutated_machining` mutates a toe row and asserts
  the diagram **title** becomes "4 bottom-to-toe…". I re-ran my own
  demonstration mutation — frame and diagram now agree.
- **I1 (Important) — resolved.** Every "each of the N parts gets K" claim is
  backed by a uniformity guard: `_per_part_total` (…:1064-1071) at the frame
  level for box sides and box fronts, and `_uniform` over per-part counts
  inside `_box_joinery_diagram`, `_rear_prep_diagram` (`_per_back`),
  `_box_front_holes_diagram`, and `_pull_bore_diagram`. Regression:
  `test_per_part_uniformity_guard_fires_on_divergent_counts` drops one
  `pull_bore` row and asserts a loud "disagree" failure.
- **I2 (Important) — resolved.** `test_at_most_1500_visible_instructional_words`
  now feeds both diagram `title` and `caption` into the count (:90-92); the
  dense dimension **notes** stay excluded, documented in-code as layout data
  per the owner's dense-coordinate rule. 1315/1500.
- **M1 — resolved.** A notch row with `location_mm[1] != 0` raises
  (…:279-283). Regression: `test_floating_notch_fails_loudly`.
- **M2 — resolved.** `count < 1` raises instead of `max(count,1)` fabricating
  a phantom bore (…:299-302). Regression: `test_zero_count_machining_row_fails_loudly`.
- **M3 — retained.** Note-region reserve scales with note count
  (`notes_h = 9 + 5.2·max(len(notes),1) + 2`; `max_h = 100 - top - notes_h`),
  so `top + box_h + notes_h ≤ 100` and no note row clips.

### Residual observations (non-blocking, no action required)

- `validate_caption` matches digit tokens only, not English number-words, so
  the C1 guard is partial by construction — author discipline (interpolate,
  drop number-words) is what actually holds. I swept the rendered visible text:
  the only remaining number-words are the model's own name ("DB40 three-drawer
  …") and structural constants — "both cabinet ends / both columns / both ends
  / both rails" (each machine-guarded by an existing symmetry check) and "cut
  **both** lower-corner notches / drill **both** runner hook holes"
  (cutting_guide.py:1225-1226), where "both" = 2. That last "both" is the one
  count-word not forced to its value: `notches_per_back`/`holes_per_back` are
  guarded uniform but not guarded `== 2`, and the parallel diagram already
  interpolates them, so a (uniform) model change to ≠2 would leave this fref
  word stale while the diagram stays correct. Risk is negligible (a rectangle
  has two lower corners), but interpolating it would close the gap.
- `_STEP_TITLES["fab.shell_back_grooves"] = "Cut the four back grooves"` still
  hard-codes "four", but panel/step titles are **not** rendered to the reader
  (confirmed by rendering the guide and grepping the visible text — absent), so
  it is a dead internal string, not a reader-honesty risk.
- `_per_part_total` uses `max(row.count, 1)`, which would count a `count == 0`
  row as 1 — mildly inconsistent with M2's strict stance, but such rows are
  rejected upstream by the diagram builder's `count < 1` raise, so no live path
  reaches it.
