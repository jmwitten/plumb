# STEPDOC +instruction-grammar v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> (inline) or superpowers:subagent-driven-development to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A generic, model-backed ActionFrame instruction layer that projects
the validated instruction-panel model into a big-box-quality consumer assembly
manual, demonstrated with DB40 as
`frameless_three_drawer_40_consumer_manual.html`.

**Architecture:** Three new pure layers on top of the existing
`InstructionManual`/`InstructionPanel` model: (1) `action_frames` — pure
ActionFrame projection with deterministic hardware lettering, repetition
badges, caption honesty validation, and complete/unique source-event
ownership; (2) `consumer_pages` — a pure Letter-size print-sheet compositor;
(3) `consumer_manual_html` — the high-contrast reader rendering. One cabinetry
adapter (`packs/cabinetry/consumer_manual.py`) supplies DB40 frame content
keyed by typed step ids, with every count/name/quantity interpolated from
compiled artifacts. The accepted four-file DB40 set is untouched.

**Tech Stack:** Python 3.12, dataclasses (frozen), pytest; HTML/CSS print
composition (no JS dependencies for print correctness); existing VTK panel
renderer extended with a high-contrast style.

## Global Constraints (from the task spec, verbatim where exact)

- No caption, count, movement, or warning may be invented; missing facts stay
  absent or become an explicit modeling gap.
- No construction event may be dropped or duplicated (complete, unique
  source-event ownership across frames).
- DB40 consumer manual ≤ 12 printed Letter pages; ≤ 1,500 visible
  instructional words excluding inventory and signed installation record; no
  instruction paragraph > 50 words.
- Hardware letters A, B, C… deterministic from typed hardware identities.
- Repetition badges (2x/4x/6x…) derived from modeled parts/stations; mutation
  tests prove counts change automatically.
- Max two action frames per printed page; installation HOLD gets its own
  unavoidable page; no frame splits across pages.
- No raw machine IDs on reader-facing pages.
- No new CPG edges; no geometry or validation-verdict changes; existing
  technical/fabrication/review surfaces unchanged.
- Grayscale-legible; no clipping at Letter print size or 390 px viewport.
- Prepared-kit gate: assembly begins with all parts cut/edged/bored/labeled
  and released; no fabrication instructions inside assembly steps.
- New surface is a separate `frameless_three_drawer_40_consumer_manual.html`;
  the accepted assembly manual is not replaced.
- Do not implement the vanity in this branch.

## Key repo facts the implementer needs

- Worktree: `.worktrees/instruction-grammar-v1`, branch
  `fable/instruction-grammar-v1`, base `cbd6e6f` (GitHub main).
- Python: `source ../../.venv/bin/activate` then
  `PYTHONPATH=$PWD/.pypath` (`.pypath/detailgen` symlinks `./src`) so the
  worktree's source wins over the main checkout's editable install.
- Focused suites: `python -m pytest tests/test_instruction_panels.py
  tests/test_cabinetry_instruction_manual.py -q` (36 passed baseline).
- `InstructionPanel` (src/rendering/instruction_panels.py): carries
  `source_events: tuple[(kind, subject, group), ...]`, `instructions`,
  `hardware: tuple[DisplayRow,...]` (with `count`, `source_part_ids`),
  `tools`, `diagrams: tuple[OperationDiagram,...]`, `stop_notice`,
  `record_fields`, `focus/arrival/visible_part_ids`.
- DB40 adapter (src/packs/cabinetry/instruction_manual.py): 6 panels;
  `_PANEL_STEP_IDS` maps panels → artifact step ids;
  `project.artifacts.{fabrication,assembly,installation}_steps` are
  `WorkStep(phase, step_id, instruction, affected, evidence)`;
  `project.artifacts.hardware_schedule` is `HardwareItem(system_id, kind,
  product_id, quantity, quantity_unit, related_parts, procurement_note,
  procedure_url, procedure_label, source_url, evidence)` with per-drawer
  repeated rows (3 drawers ⇒ identical row triplets).
- `part_labels(parts)` gives reader names; machine ids must never render.
- Only `drawer_base_three@1` archetype exists ⇒ drawer/fastener mutation
  tests act on the typed inputs of the pure projection (mutated hardware
  schedule rows / drawer-bank-derived repetition groups / step `affected`
  lists), not on a recompiled different-geometry project.
- Panel PNGs come from `render_instruction_images(detail, manual, out_dir)`
  (src/rendering/instruction_render.py); frames reuse panel imagery plus
  OperationDiagram vector content.

## File Structure

- Create `src/rendering/action_frames.py` — pure ActionFrame layer (models,
  lettering, repetition, caption validation, panel→frame projection with
  ownership checks). No HTML/VTK/IO.
- Create `src/rendering/consumer_pages.py` — pure page compositor
  (ConsumerManualPage, pack_frames_into_pages, budgets). No HTML/VTK/IO.
- Create `src/rendering/consumer_manual_html.py` — HTML/CSS composition for
  the consumer manual (print-first, high-contrast, letters/badges/insets).
- Modify `src/rendering/instruction_render.py` — add
  `style="high_contrast"` (current work dark ink, prior light gray, future
  omitted, black outlines) without changing the default style.
- Create `src/packs/cabinetry/consumer_manual.py` — DB40 adapter: frame
  specs keyed by typed step ids; captions with interpolated typed counts;
  kit gate; HOLD frame; signed record passthrough.
- Create `scripts/cabinetry_consumer_manual.py` — generates
  `outputs/frameless_three_drawer_40/frameless_three_drawer_40_consumer_manual.html`
  (references, not regenerates, the four accepted documents).
- Tests: `tests/test_action_frames.py`, `tests/test_consumer_pages.py`,
  `tests/test_cabinetry_consumer_manual.py` (includes mutation +
  structural/print regression checks).

---

### Task 1: Pure ActionFrame model, hardware lettering, caption honesty

**Files:** Create `src/rendering/action_frames.py`,
`tests/test_action_frames.py`.

**Produces (exact interfaces):**

```python
@dataclass(frozen=True)
class HardwareLetter:
    letter: str                      # "A", "B", ...
    kind: str                        # typed hardware kind
    product_id: str                  # catalog identity (letter card only, reader-safe label required)
    reader_label: str                # e.g. "Confirmat screw 7 × 50 mm"
    size_text: str                   # dimensions/selection identity
    quantity_total: int
    quantity_unit: str
    icon: str                        # existing vetted icon key
    source_system_ids: tuple[str, ...]

@dataclass(frozen=True)
class FrameHardware:
    letter: str
    quantity: int                    # exact count used in THIS frame

@dataclass(frozen=True)
class FrameIllustration:
    intent: str                      # "assembly_scene" | "operation_diagram"
    panel_index: int                 # source panel image
    diagram_id: str = ""             # when intent == "operation_diagram"
    inset: str = ""                  # optional detail/inset target label

@dataclass(frozen=True)
class ActionFrame:
    frame_id: str
    caption: str                     # imperative, ≤50 words, validated
    source_step_ids: tuple[str, ...] # provenance (artifact step ids)
    owned_events: tuple[tuple[str, str, str], ...]
    focus_part_ids: tuple[str, ...]
    context_part_ids: tuple[str, ...]
    hardware: tuple[FrameHardware, ...]
    tool: str = ""                   # reader tool text, only when known
    repeat: int = 1                  # 1 = no badge; N>1 renders "Nx"
    repeat_subject: str = ""         # e.g. "per drawer" (typed origin)
    hold: str = ""                   # tightening/hold condition when modeled
    warning: str = ""                # action-changing warning only
    illustration: FrameIllustration | None = None
    is_hold_gate: bool = False       # installation HOLD frame
    record_title: str = ""
    record_fields: tuple[RecordField, ...] = ()

class FrameContractError(ValueError): ...

def assign_hardware_letters(items) -> tuple[HardwareLetter, ...]
    # items: iterable of HardwareItem-shaped objects (kind, product_id,
    # quantity, quantity_unit, related_parts, system_id). Groups by
    # (kind, product_id, quantity_unit); letters assigned in sorted
    # (kind, product_id) order — deterministic, input-order independent.
    # reader_label/size_text/icon come from a caller-supplied
    # labeler: Callable[[group], tuple[reader_label, size_text, icon]].

def validate_caption(caption: str, *, allowed_numbers: frozenset[str],
                     forbidden_tokens: tuple[str, ...]) -> None
    # raises FrameContractError when: > 50 words; contains any forbidden
    # token (machine ids, product ids); contains a numeric token not in
    # allowed_numbers (counts/dimensions must be typed-fact-fed).

def validate_frame_ownership(panels, frames) -> None
    # every event in union(panel.source_events) owned exactly once across
    # frames' owned_events; no frame owns an unknown event.
```

**Test cases (write first, watch fail, implement, pass, commit):**
- lettering: same letters regardless of input row order; triplicated
  per-drawer rows merge with quantity_total summed; adding a distinct
  product yields a new letter and shifts subsequent letters
  deterministically.
- caption validation: 51-word caption fails; "part_3" / product-id token
  fails; caption "drive 8 screws" fails when allowed_numbers lacks "8",
  passes when provided.
- ownership: dropping one panel event fails; duplicating across two frames
  fails; exact partition passes.

- [x] Steps: failing tests → minimal implementation → pass → commit
      `feat: pure action-frame model with lettering and caption honesty`.

### Task 2: Panel→frame projection engine

**Files:** Modify `src/rendering/action_frames.py`, extend
`tests/test_action_frames.py`.

**Produces:**

```python
@dataclass(frozen=True)
class FrameSpec:
    frame_id: str
    panel_index: int
    caption: str
    source_step_ids: tuple[str, ...] = ()
    owned_event_subjects: tuple[str, ...] = ()   # match by event subject+group
    hardware: tuple[FrameHardware, ...] = ()
    ... (mirrors ActionFrame authored fields)

def project_action_frames(manual: InstructionManual, specs: tuple[FrameSpec, ...],
                          *, letters: tuple[HardwareLetter, ...],
                          allowed_numbers_by_frame: Mapping[str, frozenset[str]],
                          forbidden_tokens: tuple[str, ...]) -> tuple[ActionFrame, ...]
    # resolves each spec against its panel: focus/context part ids from the
    # panel model, events matched by (subject, group) with unmatched-event
    # and double-claim errors, every FrameHardware letter must exist,
    # caption validated. Panels with no covering spec -> error.
```

Default ownership rule: a panel's events are claimed by exactly one of its
frames each; a spec may claim `owned_event_subjects=("*",)` only when it is
the sole frame of its panel.

- [x] Steps: failing tests (unmatched event, double claim, unknown letter,
      uncovered panel, happy path over the real caddy manual fixture) →
      implement → pass → commit `feat: project instruction panels into
      action frames`.

### Task 3: Print-sheet compositor

**Files:** Create `src/rendering/consumer_pages.py`,
`tests/test_consumer_pages.py`.

**Produces:**

```python
@dataclass(frozen=True)
class ConsumerManualPage:
    number: int
    kind: str        # "cover" | "inventory" | "frames" | "hold" | "record"
    frames: tuple[ActionFrame, ...] = ()   # ≤2; exactly 1 when kind=="hold"

@dataclass(frozen=True)
class ConsumerManual:
    title: str
    basename: str
    pages: tuple[ConsumerManualPage, ...]
    letters: tuple[HardwareLetter, ...]
    kit_gate: str                          # prepared-kit gate sentence(s)
    related_documents: tuple[RelatedDocumentLink, ...]

def compose_consumer_manual(...) -> ConsumerManual
    # cover page 1; inventory (parts + lettered hardware + tools) next;
    # frames packed 2-per-page in order; a frame with is_hold_gate=True
    # always starts its own page and shares it with nothing; record pages
    # after the frame that carries record_fields when that frame is last,
    # else appended; page numbers contiguous from 1.

def visible_instructional_words(manual: ConsumerManual) -> int
    # counts caption/warning/hold/tool words on cover+frames pages;
    # excludes inventory and record pages by definition.
```

Tests: packing order & 2-per-page; HOLD isolation (frame before and after a
hold frame never share its page); no frame split (structural: each frame
appears on exactly one page); word counter excludes inventory/record;
page-count property.

- [x] Commit `feat: letter-size consumer page compositor`.

### Task 4: High-contrast render style

**Files:** Modify `src/rendering/instruction_render.py`, extend
`tests/test_instruction_render.py` (new tests only).

Add `style` parameter ("technical" default, "high_contrast" new) to the
color assignment used for current/prior parts: high-contrast maps current
work to a dark near-black fill with black edges, prior assembly to light
gray with mid-gray edges, background white; future parts remain omitted
(already guaranteed by visible ids). Existing callers unchanged
(default style, byte-stable behavior for the accepted manual).

Tests: style="high_contrast" produces distinct configured colors; default
style unchanged (existing tests stay green).

- [x] Commit `feat: high-contrast instruction render style`.

### Task 5: DB40 consumer-manual adapter

**Files:** Create `src/packs/cabinetry/consumer_manual.py`, create
`tests/test_cabinetry_consumer_manual.py`.

**Produces:**

```python
def build_cabinetry_consumer_manual(project, *, basename: str,
        related_documents=()) -> tuple[ConsumerManual, InstructionManual]
    # 1) reuse build_cabinetry_instruction_manual(...) for panels
    # 2) letters = assign_hardware_letters(project.artifacts.hardware_schedule)
    #    with cabinetry labeler (reader names from catalog kinds; sizes from
    #    typed dims in product rows; never raw product ids in reader_label)
    # 3) frame specs keyed by _PANEL_STEP_IDS step ids; captions authored
    #    HERE as templates with EVERY count/name interpolated from typed
    #    facts (hardware quantities, drawer-bank size, station counts);
    #    allowed_numbers per frame = exactly the interpolated values
    # 4) repetition: repeat=len(project.model.drawer_bank.drawers) for
    #    per-drawer frames; fastener repeats from hardware quantities
    # 5) prepared-kit gate text built from the fabrication release contract
    #    (fab steps NOT rendered as frames; they gate the kit page)
    # 6) HOLD frame from the panel-6 stop notice + policy reader notice;
    #    signed record fields passed through
```

Mutation tests (the acceptance-critical ones):
- doubling every per-drawer hardware row triplet → letter quantities and
  per-frame counts change with no adapter edit (feed mutated schedule).
- changing carcass confirmat quantity in the schedule → frame caption count
  and letter total change (assert via regenerated frames, not string
  literals).
- removing a drawer from the repetition source → repeat badges drop to 2x.
Also: every frame's source_step_ids resolve to real artifact steps; event
ownership complete & unique against the six panels; no caption > 50 words;
forbidden-token scan uses all machine part ids + product ids.

- [x] Commit `feat: DB40 consumer manual adapter with typed-count captions`.

### Task 6: Consumer manual HTML renderer

**Files:** Create `src/rendering/consumer_manual_html.py`, extend
`tests/test_cabinetry_consumer_manual.py` (structural HTML checks).

Print-first composition: `@page { size: Letter; margin: … }`, each
`section.sheet` is one printed page (`break-after: page`,
`break-inside: avoid`), on-screen preview uses the same sheet blocks capped
at 8.5in width, responsive to 390 px (sheets scale, internal
`overflow-x:auto` never at page level). High-contrast palette (near-black
on white, single accent), hardware letter chips (`A ×8`) and repetition
badges (`3×`) adjacent to each frame caption, large illustration region
(panel PNG or typed OperationDiagram SVG re-styled high-contrast), detail
insets when the frame declares one, HOLD page full-bleed warning, record
table print-friendly. Reader names only; picture-key numbers reuse panel
callouts. No `<script>` required for print correctness (a small pager for
screen is allowed but the document must print correctly without JS).

Structural tests: page count ≤ 12; ≤2 `article.frame` per sheet; hold sheet
has exactly one frame and the alert precedes any imagery in DOM order; no
machine id/product id token in rendered text nodes (letter card may carry
product identity — spec requires "dimensions/selection identity" on the
inventory card; assert product ids appear ONLY inside the letter card);
every img is a data URI (self-contained); word budget via
`visible_instructional_words` ≤ 1500; every frame renders its letters and
badges; grayscale check = computed palette contains no color-only encoding
(assert the two work/prior fills differ in luminance ≥ threshold).

- [x] Commit `feat: high-contrast letter-size consumer manual renderer`.

### Task 7: Generator script + artifact

**Files:** Create `scripts/cabinetry_consumer_manual.py`.

Mirrors `cabinetry_documents.py` conventions: compile once, require
fabrication release, render high-contrast panel images to
`outputs/frameless_three_drawer_40/consumer_panels/`, write
`frameless_three_drawer_40_consumer_manual.html`, print JSON with sha256 +
page/word metrics. Does NOT rewrite the four accepted documents.

Test: e2e build in tmp dir (marked slow if needed); JSON keys stable;
regenerated file passes all Task 6 structural checks against real content.

- [x] Commit `feat: DB40 consumer manual generator script`.

### Task 8: Browser QA, comparison, reviews, report

- Playwright screenshots: every page at Letter print emulation
  (`page.emulate_media(media="print")` + PDF) and 390 px viewport; contact
  sheet vs the West Elm 2x2 bed manual (reference PDF) and one IKEA-class
  manual; check callout collisions visually.
- Fresh-context adversarial review subagent (correctness/honesty) and
  no-context builder review subagent answering the five acceptance
  questions vs West Elm + comparable manual.
- Fix loop until zero Critical/Important.
- Full focused suite + affected suites green; run broad suite.
- Write `.superpowers/sdd/task-instruction-grammar-v1-report.md` (metrics,
  acceptance table, honest gaps) and a SESSION UPDATE in progress.md.
- Commits pushed on `fable/instruction-grammar-v1` (no merge to main —
  spec: new surface ships separately until review passes).

## Self-review notes

- Spec coverage: models (1), projection+ownership (2), lettering (1),
  badges+mutation (1,5), compositor (3), high-contrast (4,6), separate DB40
  file (7), reviews+report (8). Word/page budgets tested in 6 and verified
  in 8. Non-goals respected: no CPG/geometry/validation edits anywhere.
- Risk: 12-page budget. Frame plan keeps ~14–18 frames; if honest packing
  exceeds 12 pages the report states the real count and the blocking facts
  rather than merging unlike actions. Target composition: cover 1,
  inventory+kit gate 1, assembly frames ≈ 6 pages, HOLD 1, install frames
  ≈ 2, record 1 ⇒ 12.
- Risk: caption honesty vs readability — resolved by numeric-token audit
  (allowed_numbers) rather than banning authored imperative templates,
  matching the repo's authored `sequence:` precedent.
