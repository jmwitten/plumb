# Armchair Caddy +presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a five-panel, model-backed armchair-caddy assembly manual as a separate offline HTML document, reciprocally linked to the existing technical build document.

**Architecture:** A pure panel-model layer projects the validated Construction Process Graph, typed process facts, resolved installation contracts, shared part labels, and compiled geometry into deterministic `InstructionPanel` values. A VTK/PIL layer renders content-keyed ghost/arrival images and geometry-derived station overlays. A document layer embeds those images into a self-contained manual and an optional viewer-payload extension adds a panel-snapping assembly slider without changing legacy payloads.

**Tech Stack:** Python 3.13, dataclasses, CadQuery/OCCT geometry, VTK offscreen rendering, Pillow overlays, existing HTML/CSS/vanilla JavaScript viewer, pytest/xdist.

## Global Constraints

- The binding source is `docs/superpowers/specs/2026-07-13-caddy-presentation-design.md` plus `.superpowers/sdd/stepdoc-cpg-design.md`'s approved +presentation section.
- The illustrated manual is `armchair_caddy_assembly_manual.html`; the technical document remains `armchair_caddy_build_document.html`; links are reciprocal relative basenames.
- Presentation consumes the existing event graph and resolved facts. It never adds an order edge, recompiles a connection, parses rendered prose, or changes a verdict.
- A panel caption may not invent a product, timer, clamp count, pilot size, torque, finish, load capacity, code claim, or hot-drink safety claim.
- Stage and reader-step vocabulary remain distinct.
- Process and join cohorts are hard panel boundaries.
- Every placement-critical caddy panel is station-complete; missing/inconsistent station data blocks generation.
- Content keys change for relevant order/geometry/station changes and remain stable for unrelated prose/review changes.
- Existing payloads/doc generation remain backward compatible when companion/panel metadata is omitted.
- Use the verified worktree shim: `PYTHONPATH="$PWD/.shim"` and `../../.venv/bin/python`; verify imports resolve to this worktree before trusting tests.
- TDD is mandatory: each production behavior follows a test observed failing for the intended reason.
- Before merge: fresh adversarial review, fix/confirmation rounds, one full `pytest -n auto -q` on the frozen final tree, read the result, and merge as a separate command.

---

### Task 1: Pure instruction-panel model and five caddy cohorts

**Files:**
- Create: `src/rendering/instruction_panels.py`
- Create: `tests/test_instruction_panels.py`
- Modify: `src/rendering/__init__.py`

**Interfaces:**
- Consumes: `derive_reader_steps(graph)`, `build_sequence_model(detail)`, `ConnectionChecks.event_graph`, `ConnectionChecks.installs`, `part_labels(parts)`, `Placed.id/name/component`, `EventGraph.edges/event_of/members_of/process_facts/staging`.
- Produces: `PlacementStation`, `HardwareRow`, `InstructionPanel`, `InstructionManual`, `build_instruction_manual(detail, technical_href: str) -> InstructionManual`, and `panel_part_schedule(manual) -> dict[str, int]`.

- [ ] **Step 1: Write RED tests for the pure dataclass contract and fail-closed companion basename**

```python
def test_caddy_manual_is_a_separate_relative_companion(caddy):
    with pytest.raises(ValueError, match="relative basename"):
        build_instruction_manual(caddy, "../technical.html")
    manual = build_instruction_manual(
        caddy, "armchair_caddy_build_document.html")
    assert manual.technical_href == "armchair_caddy_build_document.html"
    assert manual.basename == "armchair_caddy_assembly_manual.html"
```

- [ ] **Step 2: Run the RED selection**

Run:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_instruction_panels.py -k separate_relative
```

Expected: import failure for the missing production module.

- [ ] **Step 3: Add frozen presentation dataclasses and strict basename validation**

Implement frozen dataclasses whose fields are JSON-serializable except for a retained typed `ProcessFact`/`ResolvedInstallation` reference where the renderer needs it. Validate `Path(href).name == href`, no slash/backslash, and `.html` suffix.

- [ ] **Step 4: Write RED tests for event-to-step lifting and cohort coverage**

```python
def test_caddy_panels_cover_each_reader_step_once(caddy):
    manual = build_instruction_manual(caddy, "armchair_caddy_build_document.html")
    covered = tuple(i for p in manual.panels for i in p.reader_step_indexes)
    assert sorted(covered) == list(range(len(derive_reader_steps(
        caddy._connection_checks.event_graph))))
    assert len(covered) == len(set(covered))

def test_caddy_has_five_semantic_cohorts(caddy):
    manual = build_instruction_manual(caddy, "armchair_caddy_build_document.html")
    assert [p.action for p in manual.panels] == [
        "prepare", "bond", "cure", "fasten", "join"]
    assert [len(p.reader_step_indexes) for p in manual.panels] == [1, 2, 2, 2, 1]
```

- [ ] **Step 5: Run RED and verify the failure is missing grouping behavior**

Run the two tests above with `-vv`; expected failures show zero/missing panels, not fixture errors.

- [ ] **Step 6: Implement consecutive-run grouping over the canonical reader order**

Map every event to its owning reader-step index, lift graph edges only to verify the existing order, then scan `derive_reader_steps()` without re-linearizing it. Group only adjacent steps with the same `(unit, authored stage, action family)`. Classify process as its kind, joins as join, contract-bearing connections as fasten, contract-less connections as bond/set, and pure placements as prepare. Assert every panel's indexes are a contiguous range, panel order is by first index, and every lifted edge points forward. Author the caddy's two cross-cure `after:` terms (each screw connection waits on both cures) with the declared batch-workflow why; pin deletion reverting to seven canonical panels. Do not use stages as the remedy: the executed proof shows they do not order process events.

- [ ] **Step 7: Write RED tests for typed human register and banned machine vocabulary**

```python
def test_caddy_panel_text_uses_reader_vocabulary_and_typed_facts(caddy):
    manual = build_instruction_manual(caddy, "armchair_caddy_build_document.html")
    rendered = "\n".join(
        [p.title, *p.instructions, *(p.rationales or ())]
        for p in manual.panels)
    assert "Registration rail (1 of 2)" in rendered
    assert "Side board (2 of 2)" in rendered
    assert "8" in next(p for p in manual.panels if p.action == "fasten").hardware[0].label
    assert "No generic duration is represented" in next(
        p for p in manual.panels if p.action == "cure").instructions[-1]
    for banned in ("+X", "-X", "lumber-", "install contract", "connectiontype_default"):
        assert banned not in rendered
```

- [ ] **Step 8: Implement compositional captions, inventories, tools, and trust markers**

Use `part_labels()` ordinals, actual fastener components/counts, `ResolvedInstallation.contract`, `ProcessFact.instructions/completion/why`, and staging facts. The final join panel carries `DECLARED TRUST` and named analysis gaps. Technique vocabulary maps only typed method/kind to verbs/icons. Product-selection gaps become explicit gates.

- [ ] **Step 9: Run Task 1 tests and existing reader-name/process tests**

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q \
  tests/test_instruction_panels.py tests/test_stepdoc_process.py \
  tests/test_reader_names.py tests/test_viewer_data.py
```

Expected: all pass.

- [ ] **Step 10: Commit Task 1**

```bash
git add src/rendering/instruction_panels.py src/rendering/__init__.py tests/test_instruction_panels.py
git commit -m "feat: derive grouped instruction panels"
```

---

### Task 2: Geometry-derived CAT-M stations and content-keyed panel renderer

**Files:**
- Create: `src/rendering/instruction_render.py`
- Create: `src/rendering/caddy_stations.py`
- Create: `tests/test_instruction_render.py`
- Modify: `src/rendering/instruction_panels.py`
- Modify: `tests/test_instruction_panels.py`

**Interfaces:**
- Consumes: Task 1 `InstructionPanel`/`InstructionManual`, `build_manifest(assembly)["geometry_hash"]`, `assembly.isolated_world_solids()`, compiled part world bounding boxes, `ProcessRecord.fab_note()`.
- Produces: `derive_caddy_stations(detail, panels) -> tuple[InstructionPanel, ...]`, `panel_content_key(detail, panel, renderer_version) -> str`, `render_instruction_panel(detail, panel, out_dir) -> Path`, and `render_instruction_images(detail, manual, out_dir) -> dict[str, Path]`.

- [ ] **Step 1: Write CAT-M RED tests for text-complete stations**

Assert the prepare panel carries the centered bore from both top-board ends; the bond panel carries each rail's top-end/front-back/underside datums; and the fasten panel carries four geometry-derived symmetric screw-pair stations (two rails × two drops), each locating one center from either interchangeable rail end plus the top-underside drop. A one-screw asymmetric mutation without a modeled distinguishing end feature must fail closed rather than inventing front/back.

- [ ] **Step 2: Verify CAT-M fails because no station adapter exists**

Run the CAT-M tests only and read the missing/empty station assertion.

- [ ] **Step 3: Implement bbox/anchor measurement helpers and caddy station adapter**

The adapter selects top/rail/side/screw ids by graph membership plus reader labels, not raw machine-name string parsing. All numbers come from world bbox faces or fastener datum/world center. Format with the existing fractional-inch formatter. Each `PlacementStation` stores the raw millimeter measurements and projected world anchors used later by the image overlay.

- [ ] **Step 4: Add fail-closed reconciliation**

For both-ends point stations require `near + far == reference_length` within 0.5 mm; for feature stations include feature extent in the equation. Raise `InstructionPresentationError` naming panel, feature, reference part, raw values, and missing/inconsistent datum.

- [ ] **Step 5: Write and observe the moved-station RED mutation**

Compile a temporary caddy spec variant with `screw_dy_h` changed. Assert the fasten panel's raw stations and formatted labels change while panel text contains no old literal. Also assert the station image inputs change.

- [ ] **Step 6: Implement the mutation path and re-run CAT-M**

Expected: CAT-M selection passes and `git grep` finds no caddy station literal in the renderer.

- [ ] **Step 7: Write CAT-J RED tests for content-key guard directions**

```python
def test_relevant_geometry_or_order_rekeys_panel(...): ...
def test_unrelated_review_or_caption_metadata_does_not_rekey_panel(...): ...
```

The first changes a part placement or source event identities; the second changes only a copied rationale/display wrapper outside the key contract.

- [ ] **Step 8: Implement canonical key serialization**

Hash a sorted, compact JSON object containing renderer version, per-part world-geometry hashes restricted to visible/arrival/focus ids, ordered source event tuples, camera spec, callouts, and raw stations. Do not hash the whole assembly, rendered prose, review stores, generated timestamps, or HTML styles. The moved-screw CAT-M variant must re-key fasten/join while leaving prepare/bond/cure keys unchanged.

- [ ] **Step 8a: Implement binding CAT-L on the verdict-independent step stool**

Build a temporary step-stool variant with authored stages, then remove the stages and rebuild. Assert the reader grouping changes (per-stage versus per-connection), affected step/panel keys move, and every validation finding tuple—verdict, check, subject, detail, declared-order, declared-trust—remains byte-identical. First resolve any existing reader-bucket collapse honestly; do not weaken CAT-L into downstream panel regrouping, which would be vacuous because verdicts do not consume panels.

Implementation result: reader projection now condenses compatible SCCs of the
bucket quotient, preserves valid split stages by evicting only an unclaimed
default-folded placement when sufficient, and fails closed across remaining
process/join/stage/unit hard boundaries. Platform is pinned at 18 steps with
five merges; stool is pinned at three unstaged/two staged steps; mapping and
emission coverage are loud; the Build Sequence consumer rejects zero steps.
CAT-L pins four added authored edges, 137 byte-identical finding tuples,
geometry identity, affected-key movement, comment-only key stability, and
exact reversion.

- [ ] **Step 9: Write renderer RED tests**

Pin a PNG for every panel, keyed basename, nonzero dimensions, stable bytes on a second call, current-part color pixels, ghost-gray prior pixels, numbered callouts, and station-label pixels. Pin process panels with no arrivals but nonempty focus parts, and final join context visibility.

- [ ] **Step 10: Implement VTK/PIL rendering from the checked-in prototype**

Move only the general rendering mechanics: per-part tessellation, material versus 0.16 ghost actors, final-camera world projection, callout circles, dimension arrows/labels, PNG writing, and exact-key reuse. Close VTK windows explicitly after capture.

- [ ] **Step 11: Run renderer/model gates and commit Task 2**

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q \
  tests/test_instruction_panels.py tests/test_instruction_render.py
git add src/rendering/instruction_panels.py src/rendering/instruction_render.py \
  src/rendering/caddy_stations.py tests/test_instruction_panels.py \
  tests/test_instruction_render.py
git commit -m "feat: render content-keyed instruction panels"
```

---

### Task 3: Separate self-contained manual and reciprocal document links

**Files:**
- Create: `src/rendering/instruction_manual.py`
- Create: `scripts/caddy_documents.py`
- Create: `tests/test_caddy_instruction_manual.py`
- Modify: `scripts/single_detail_report.py`
- Modify: `tests/test_armchair_caddy_e2e.py`

**Interfaces:**
- Consumes: Tasks 1–2 manual/panels/PNGs, existing `build_document()` technical generator and coverage report.
- Produces: `render_instruction_manual_html(detail, manual, image_paths) -> str`, `build_caddy_document_pair(out_dir: Path) -> dict`, optional `companion_href` on `build_document()`/header rendering.

- [ ] **Step 1: Write RED tests for two distinct files and reciprocal links**

Generate into `tmp_path`; assert both exact basenames exist, manual link appears only when `companion_href` is supplied, both links are relative, and ordinary `build_document()` without a companion stays byte-compatible with the old link behavior.

- [ ] **Step 2: Observe the missing pair generator failure**

Run `tests/test_caddy_instruction_manual.py -k reciprocal -vv`.

- [ ] **Step 3: Add optional technical companion link without changing default output**

Thread `companion_href: str | None = None` through `_title_block`, `build_single_detail_html`, and `build_document`. Render one prominent “Open illustrated assembly manual” link in the header only when non-`None`, after strict relative-basename validation.

- [ ] **Step 4: Write RED tests for manual content and honesty**

Assert five panels; embedded `data:image/png;base64`; parts inventory; per-panel tool/hardware strips; why boxes only where rationales exist; full-cure/no-duration wording; `DECLARED TRUST`; insertion/stability/sliding/capacity/hot-drink gaps; technical link; and absence of raw machine vocabulary.

- [ ] **Step 5: Implement semantic HTML/CSS and panel navigation**

Use a visible `<article data-panel-index>` per panel, Prev/Next buttons, a range input with integer panel values, progress text, arrow-key handling, URL hash persistence, and `@media print` rules that reveal every panel and hide controls. Add no external resources.

- [ ] **Step 6: Implement the pair CLI**

`scripts/caddy_documents.py --out-dir outputs/armchair_caddy` compiles and validates once, builds panel model, renders/reuses keyed PNGs in `manual_assets/`, writes the manual, then writes the technical document with the manual link. Return/print both SHA-256 values, panel count, and asset keys.

- [ ] **Step 7: Pin deterministic regeneration and portable copies**

Run the pair generator twice in separate directories; assert identical HTML bytes after normalizing only the repository's existing generated stamp policy (or make the manual stamp source-stable). Delete the asset directory and confirm the embedded manual still loads all panel images.

- [ ] **Step 8: Run document tests and commit Task 3**

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q \
  tests/test_caddy_instruction_manual.py tests/test_armchair_caddy_e2e.py
git add src/rendering/instruction_manual.py scripts/caddy_documents.py \
  scripts/single_detail_report.py tests/test_caddy_instruction_manual.py \
  tests/test_armchair_caddy_e2e.py
git commit -m "feat: generate linked caddy assembly manual"
```

---

### Task 4: Panel-snapping 3D assembly slider

**Files:**
- Modify: `src/rendering/web_viewer/__init__.py`
- Modify: `src/rendering/web_viewer/viewer.js`
- Modify: `src/rendering/web_viewer/viewer.css`
- Modify: `scripts/single_detail_report.py`
- Create: `tests/test_viewer_instruction_panels.py`
- Modify: `tests/test_viewer_data.py`

**Interfaces:**
- Consumes: `panel_part_schedule(manual)` and existing viewer payload/GLB node contract.
- Produces: optional payload top-level `instruction_panels` and per-part `first_panel`; unchanged legacy payload when no manual metadata is passed.

- [ ] **Step 1: Write payload RED tests**

Pin structural wood first-visible at prepare, screw hardware at fasten, sofa-arm context at join, all ids resolved exactly once, and legacy `build_viewer_payload(detail)` without the optional schedule unchanged.

- [ ] **Step 2: Add optional panel schedule to payload builder**

Accept `instruction_manual=None`; when supplied, serialize panel number/title/action/arrival machine names and each part's first panel. Reject unknown/omitted built part ids. The technical pair generator passes the same manual value used for the static document.

- [ ] **Step 3: Write JS source/DOM RED tests**

Pin creation only when metadata exists; integer `min=1`, `max=panel_count`, `step=1`; part visibility uses `first_panel <= current`; current arrivals receive a highlight class/emissive state; existing explode listener remains and does not change the panel input.

- [ ] **Step 4: Implement panel slider and explode composition**

Add “Assembly” range control and current panel label. Cache every top node's panel visibility. On panel input, hide later nodes, show prior/current nodes, and highlight current arrivals without losing hover/pin state. Explode continues to translate only currently visible nodes and does not alter the panel number.

- [ ] **Step 5: Run viewer syntax and regression gates**

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q \
  tests/test_viewer_instruction_panels.py tests/test_viewer_data.py \
  tests/test_viewer_explode_and_fab.py tests/test_reader_names.py
node --check src/rendering/web_viewer/viewer.js
```

- [ ] **Step 6: Commit Task 4**

```bash
git add src/rendering/web_viewer/__init__.py \
  src/rendering/web_viewer/viewer.js src/rendering/web_viewer/viewer.css \
  scripts/single_detail_report.py tests/test_viewer_instruction_panels.py \
  tests/test_viewer_data.py
git commit -m "feat: add panel-snapping assembly viewer"
```

---

### Task 5: Adversarial review, final gate, merge, and paired delivery

**Files:**
- Create: `.superpowers/sdd/task-stepdoc-presentation-report.md`
- Create: `.superpowers/sdd/review-stepdoc-presentation.md`
- Create: `.superpowers/sdd/review-stepdoc-presentation-builder.md`
- Modify: `.superpowers/sdd/progress.md`

**Interfaces:**
- Consumes: complete branch and generated pair.
- Produces: reviewed/gated GitHub `main`, delivered byte-identical document pair, review/report/ledger trail.

- [ ] **Step 1: Run focused acceptance gates**

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q \
  tests/test_instruction_panels.py tests/test_instruction_render.py \
  tests/test_caddy_instruction_manual.py tests/test_viewer_instruction_panels.py \
  tests/test_stepdoc_process.py tests/test_armchair_caddy_e2e.py
```

- [ ] **Step 2: Verify geometry/verdict/event-graph non-change**

Compare assembly geometry hash, validation finding signatures, event identities/edges, the canonical linearization, and all existing ten caddy view PNG hashes against `origin/main`. The two new cross-cure authored edges and canonical order are deliberate; geometry and validation findings must remain unchanged. Panel grouping may change only presentation artifacts and optional payload metadata.

- [ ] **Step 3: Request fresh adversarial review**

Attack: hidden invented order, process/join boundary crossing, missing/duplicated step coverage, raw-name leakage, hardware under/overcount, product/timer invention, station-literal drift, key guard directions, context appearing before join, slider/explode interference, broken offline links, legacy payload changes, and presentation moving a verdict.

- [ ] **Step 4: Fix findings test-first and obtain confirmation**

Record initial findings, failing probes, fixes, and fresh confirmation in `.superpowers/sdd/review-stepdoc-presentation.md`.

- [ ] **Step 5: Freeze and run one full suite**

Verify shim and clean status, then:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -n auto -q
```

Read and record the exact result. Do not modify code after this gate.

- [ ] **Step 6: Merge and push as separate commands**

Fetch and verify remote `main`; create an integration branch from it; merge `codex/stepdoc-presentation` with `--no-ff` in its own command; verify merge tree equals the gated feature tree; push `HEAD:main`.

- [ ] **Step 7: Generate and browser-QA the pair**

Run the pair CLI from the clean merged tree. Verify keyed assets, reciprocal links, desktop/narrow layout, all five panels, Prev/Next/range/keyboard navigation, print expansion, 3D panel slider, hover reader names, and zero console errors.

- [ ] **Step 8: Run the required fresh naive-builder review**

Give a no-context reviewer only `armchair_caddy_assembly_manual.html` and ask:

> Imagine you were a handyman without official contracting/engineering training and were asked to build this caddy. Would you understand how to build it? Separately, do you see all the parts included? Compare to official manufacturer manuals you find online. Could I place every part using only this page?

Classify safety-analysis blockers separately from instruction-comprehension defects. Fix release-blocking instruction defects test-first; repeat review if the document changes.

- [ ] **Step 9: Deliver byte-identical paired copies**

Copy both HTML files side by side to:

- `05_Attachments/Organized/Armchair Caddy Drawings/`
- `~/Downloads/Build Documents/`
- the repo's ignored `outputs/armchair_caddy/`

Verify hashes and relative links after copy. Commit/push only the exact vault attachments in JoelBrain; preserve unrelated dirty files.

- [ ] **Step 10: Record final report and ledger**

Record commits, review, exact tests, geometry/view non-change, panel asset keys, document hashes, builder verdict, paths, and deferrals. Commit/push documentation without changing the already gated code tree.
