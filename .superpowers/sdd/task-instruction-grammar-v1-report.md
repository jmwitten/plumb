# STEPDOC +instruction-grammar v1 — task report

Branch: `fable/instruction-grammar-v1` (base: GitHub main `cbd6e6f`)
Date: 2026-07-14

## What was built

A generic, model-backed **ActionFrame** instruction layer that projects the
validated instruction-panel model into a big-box-quality consumer assembly
manual, demonstrated with DB40 as a separate review surface
(`frameless_three_drawer_40_consumer_manual.html`). The accepted four-document
DB40 set is untouched.

### Platform capabilities (reusable, pure)

- `src/rendering/action_frames.py` — `ActionFrame`, `FrameSpec`,
  `HardwareLetter`, `FrameHardware`, `FrameIllustration`;
  `assign_hardware_letters` (deterministic A/B/C… from typed hardware
  identities, input-order independent, per-drawer identity rows merged with
  summed totals); `validate_caption` (≤50 words, no machine identifiers, and
  **every numeric token must be backed by a typed fact** the caller
  interpolated — a stale hand-written count fails the build);
  `project_action_frames` (panel→frame decomposition with complete, unique
  source-event ownership: no CPG event dropped or duplicated, wildcard
  ownership only when no sibling frame claims events);
  `validate_frame_ownership`.
- `src/rendering/consumer_pages.py` — pure Letter print-sheet compositor:
  cover → prepared-kit inventory → frame pages (≤2 frames each, no splits) →
  installation HOLD alone on an unavoidable page → signed record page(s);
  `visible_instructional_words` (excludes inventory + record by the
  acceptance definition).
- `src/rendering/consumer_manual_html.py` — print-first, high-contrast,
  grayscale-legible HTML: `@page` Letter pagination, one `section.sheet` per
  composed page, hardware letter chips (`B ×8`), repetition badges (`3×
  per drawer`), warning/hold boxes marked with a glyph + border (never
  color-only), reader names only. Machine ids appear solely in `data-*`
  attributes for traceability.
- `src/rendering/instruction_render.py` — named `InstructionStyle` registry:
  `technical` (byte-stable with the pre-style renderer — content keys and
  cached PNGs unchanged) and `high_contrast` (dark current work on light-gray
  prior assembly, white background, **feature-edge** black outlines — real
  boundaries/creases only, no tessellation-triangle false joints);
  `render_frame_images` (one scene per frame with the frame's own focus set,
  panel-accurate visibility) and `render_cover_image` (finished-product view,
  no callout overlay).
- `scripts/cabinetry_consumer_manual.py` — one-command generation with JSON
  metrics (sha256, page/frame/word counts, letter roster).

### DB40 adapter (typed-fact captions)

`src/packs/cabinetry/consumer_manual.py` decomposes the six accepted panels
into **15 action frames** (14 numbered steps + the HOLD gate). Every count in
a caption/tool/warning is interpolated from a typed source and re-audited by
the caption contract:

- carcass Confirmat split (8/5/13) from `_carcass_confirmat_panel_quantities`;
- per-drawer quantities (8 box screws, 10 runner screws, 4 locking screws,
  4 front screws, 2 pull screws) from the released hardware schedule with a
  uniformity check;
- runner stations (5) and screws-per-runner (5) from the typed Blum product;
- reveals/gaps (1.5 mm / 2 mm) from the compiled drawer bank;
- repetition badges (`3× per drawer`) from the drawer-bank cell count;
- the HOLD warning verbatim from the typed panel stop notice; the signed
  installation/fit record passed through unchanged (8 fields).

Hardware lettering merges schedule roles by physical identity
`(product_id, quantity_unit)` — e.g. one Confirmat letter across carcass and
drawer-box roles (50 screws), one 606N letter across runner and
locking-device roles (42) — labeled from typed catalog products
(manufacturer name + dimensions/selection identity on the kit card only).

## Acceptance status

| Criterion | Status |
|---|---|
| ≤ 12 printed Letter pages | **11 composed sheets = 11 printed PDF pages** (Chrome print, verified) |
| ≤ 1,500 visible instructional words | **640** (excl. inventory + signed record) |
| No instruction paragraph > 50 words | enforced at build time (`validate_caption`) |
| Every frame has traceable sources | every frame carries owned events and/or resolvable artifact step ids (tested) |
| Every source event owned exactly once | `validate_frame_ownership` on all six panels (tested) |
| Deterministic hardware letters/quantities | input-order-independence + merge tests |
| Counts update under drawer/fastener mutation | 5 mutation tests: drawer count → badges + caption; box-screw ×2 → 16 in caption+chips; anchor ×2 → letter total 4; confirmat split change → toe frame; stale hand-written count → loud FrameContractError |
| No raw machine IDs on reader pages | forbidden-token scan (part ids, machine names, product ids, stud ids) over frame text and over rendered visible text |
| No new CPG edges; no geometry/verdict changes | no edits under assemblies/validation/details; panels manual consumed read-only |
| Existing surfaces retain evidence | four-document set untouched; `technical` style content keys byte-stable (tested) |
| Grayscale legible | ink-on-white palette; work/prior fills ≥ 0.5 luminance apart (tested); warnings use borders + glyphs, not color |
| No clipping at Letter print / 390 px | print: 11 = 11 pages, no spill; 390 px: `scrollWidth == clientWidth == 386`, zero elements past the right edge (live Chrome check) |
| Screenshot/structural regression tests | structural suite (sheets/frame counts, hold-alert DOM order, data URIs, chips/badges, print CSS) + opt-in `DETAILGEN_PRINT_QA=1` Chrome print-break test |
| Prepared-kit gate | kit card + gate text; no `fab.*` step renders as an assembly frame (tested) |
| Separate surface, accepted manual unreplaced | script writes only the consumer manual (tested) |

Full gate at final HEAD: **1826 passed / 4 skipped / 1 xfailed in
1063s**, plus 2 subprocess-determinism tests that fail in any fresh
worktree because they expect the untracked repo-root `.shim/` symlink
(`detailgen -> src`); after recreating `.shim` in the worktree — the same
state the main checkout carries — both pass (1828 total green). Not
related to this branch's changes.

Verification: 151 tests green across the affected instruction suites
(`test_instruction_panels`, `test_instruction_render`,
`test_caddy_instruction_manual`, `test_viewer_instruction_panels`,
`test_cabinetry_instruction_manual`, `test_action_frames`,
`test_consumer_pages`, `test_cabinetry_consumer_manual`), plus the
end-to-end generator test.

## Comparison vs West Elm / cabinet-hardware manuals

The West Elm 2x2 bed frame manual (reference PDF) idioms all present:
lettered hardware card with quantities and silhouettes → our typed letter
card; per-step hardware callouts (`F`, `G` bubbles) → letter chips beside
each step number; `2x`/`6x` repetition bubbles → derived repetition badges;
one-sentence imperative captions → validated ≤50-word captions;
line-art with current work emphasized → high-contrast feature-edge scenes.
Where we exceed that bar deliberately: the unavoidable installation HOLD
page, the signed installation/fit record, and per-frame provenance
(machine-checkable, hidden from the reader).

## Review outcomes

- **Adversarial review (fresh context): zero Critical, zero Important,
  four Minor** — see `review-instruction-grammar-v1.md`. Two minors fixed
  post-review (panel-multiset event ownership; `repeat_subject` audited),
  one retained deliberately (`_test_caption_override` seam — it is the
  loud-failure proof), one accepted as intended altitude (kit-register
  captions drop dimensions the fabrication packet retains; reviewer
  confirmed nothing action-changing was lost).
- **No-context builder review: conditional PASS** — see
  `review-instruction-grammar-v1-builder.md`. "A careful builder can
  finish it: captions are accurate, sequence is disciplined, hardware
  accounting is exact" and the hardware-letter bookkeeping reconciled to
  the piece ("better than most big-box manuals"); the illustration
  grammar (exploded views, motion arrows, adjustment diagrams) does not
  yet meet the West Elm/Blum bar. Fixed from this round: drywall-anchor
  line promoted to a ⚠ warning box, label-dependency stated at the kit
  gate, stabilizer components attributed to their letter, page numbers
  added. Remaining illustration findings are documented v1 scope limits —
  motion/exploded states are not modeled facts, and this branch may not
  invent them or change geometry.

After both fix rounds: 11 pages / **640** visible instructional words;
consumer sha256
`2ae10ec3efb9ba9d1442500845ac6605b97b193cde2b5a6c97aff99a3cf3c522`.

## Honest gaps and notes

- **Frame illustrations reuse panel visibility with frame-level focus.**
  Sibling frames of one panel share the same camera; three late frames
  (adjust / label-remove / reinstall) show similar scenes distinguished
  mainly by focus emphasis. Real per-frame camera/motion arrows are future
  work (motion is not modeled; the spec forbids inventing it, so no arrows
  are drawn anywhere).
- **Hardware silhouettes are icon-register, not 1:1 scale drawings.** The
  kit card uses the vetted icon set plus typed dimension text; true scaled
  silhouettes from component geometry are a natural +presentation follow-up.
- **`DETAILGEN_PRINT_QA=1` print test depends on headless Chrome**, which is
  intermittently flaky on this machine (hangs unrelated to the document);
  the check passed when run manually (11 = 11). Kept opt-in, not in the
  default gate.
- **Word/page budgets have head-room** (623/1500 words, 11/12 pages), so the
  DB40 numbers are not tuned-to-fit.
