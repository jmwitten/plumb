# DV72 Cabinet Installation Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a fifth, illustrated DV72 guide that takes a field crew through mounting the empty cabinet and stops before countertop, sink, plumbing, drawer, loading, or commissioning work.

**Architecture:** Reuse the stable action-frame and Letter-page grammar from `fable/instruction-grammar-v1` without merging that divergent branch. A DV72 typed adapter will project the existing model, support layout, findings, and release states into eight print sheets with deterministic inline SVG. The current document-set composer will add reciprocal five-document navigation.

**Tech Stack:** Python 3.12+, frozen dataclasses, existing instruction types, deterministic inline SVG/HTML/CSS, pytest, Chromium print/render verification.

## Global Constraints

- End with an empty cabinet securely mounted; exclude countertop, sinks, plumbing, drawers, loading, and commissioning.
- Keep `INSTALLATION HOLD`; create no structural, field, product, or trade PASS.
- Leave wall fasteners and cabinet case/interface hardware as blank release fields.
- Give the rear rail zero gravity credit; it is positioning/lateral restraint only.
- Render dimensions, products, support positions, and authority from typed facts.
- Limit output to eight Letter pages and 1,500 visible instructional words.
- Put the STOP page before every action illustration; mark every later action conditional while held.
- Use self-contained assets, 390 px responsive behavior, and US Letter print CSS.
- Preserve the existing four reader scopes; only reciprocal navigation/footer count changes.

---

### Task 1: Add the reusable action-frame and Letter-page grammar

**Files:**
- Create: `src/rendering/action_frames.py`
- Create: `src/rendering/consumer_pages.py`
- Create: `tests/test_action_frames.py`
- Create: `tests/test_consumer_pages.py`
- Reference: `/Users/joelwitten/Code/construction-detail-generator/.worktrees/instruction-grammar-v1/src/rendering/action_frames.py`
- Reference: `/Users/joelwitten/Code/construction-detail-generator/.worktrees/instruction-grammar-v1/src/rendering/consumer_pages.py`

**Interfaces:**
- Consumes: `RecordField` and `RelatedDocumentLink` from `instruction_panels.py`.
- Produces: `ActionFrame`, `FrameIllustration`, `FrameContractError`, `ConsumerManualPage`, `ConsumerManual`, `compose_consumer_manual()`, and `visible_instructional_words()`.
- Copy only the current pure modules; do not import DB40 adapters, cutting-guide code, VTK, or viewer code.

- [ ] **Step 1: Port the shared tests first**

Copy the current generic tests from the reference worktree. Add this STOP-order contract if absent:

```python
def test_hold_page_is_unavoidable_and_precedes_actions():
    hold = ActionFrame(
        frame_id="release_hold",
        caption="Stop until the field and structural record is accepted.",
        source_step_ids=("release_hold",), owned_events=(),
        focus_part_ids=(), is_hold_gate=True,
    )
    action = ActionFrame(
        frame_id="layout_wall",
        caption="Lay out the accepted support axes.",
        source_step_ids=("layout_wall",), owned_events=(),
        focus_part_ids=(),
    )
    manual = compose_consumer_manual(
        frames=(hold, action), title="DV72 installation",
        basename="dv72_installation_guide.html", letters=(),
        kit_gate="Field release required",
        cover_caption="Empty cabinet only",
    )
    assert [page.kind for page in manual.pages] == [
        "cover", "inventory", "hold", "frames",
    ]
```

- [ ] **Step 2: Verify RED**

```bash
source .venv/bin/activate
pytest -q tests/test_action_frames.py tests/test_consumer_pages.py
```

Expected: collection fails because the two modules do not exist on this branch.

- [ ] **Step 3: Port the two pure modules**

Use their exact current contents. Preserve frozen dataclasses, numeric-caption validation, hardware lettering, event ownership, hold-page isolation, two-frame packing, and record composition. Change `instruction_panels.py` only if a copied test exposes a compatibility gap.

- [ ] **Step 4: Verify GREEN and commit**

```bash
pytest -q tests/test_action_frames.py tests/test_consumer_pages.py
git add src/rendering/action_frames.py src/rendering/consumer_pages.py   tests/test_action_frames.py tests/test_consumer_pages.py
git commit -m "feat: add reusable instruction page grammar"
```

Expected: all shared grammar tests pass.

---

### Task 2: Project DV72 into the conditional installation guide

**Files:**
- Create: `src/packs/cabinetry/double_vanity_installation_guide.py`
- Create: `tests/test_double_vanity_installation_guide.py`

**Interfaces:**
- Consumes: compiled `PackedProject`, assumed site, vanity geometry, `SupportLayout`, load case, plumbing/drawer service envelopes, release state, and findings.
- Produces: `project_double_vanity_installation_manual(project, *, related_documents) -> ConsumerManual` and `build_double_vanity_installation_guide(project, *, related_documents) -> str`.

- [ ] **Step 1: Write guide contract tests**

Create fixtures from `floating_double_sink_four_drawer.project.yaml` and these behavioral tests:

```python
def test_guide_is_bounded_and_stop_precedes_actions(project):
    manual = project_double_vanity_installation_manual(
        project, related_documents=(),
    )
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    assert len(manual.pages) <= 8
    assert html.count('class="sheet ') == len(manual.pages)
    assert html.index('data-page-kind="hold"') < html.index(
        'data-action-illustration="true"'
    )
    assert visible_instructional_words(
        manual, extra_texts=installation_visible_extras(project),
    ) <= 1500
    assert "INSTALLATION HOLD" in html


def test_guide_stops_at_empty_mounted_cabinet(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    assert "empty cabinet mounted" in html.lower()
    assert "STOP BEFORE COUNTERTOP" in html
    for forbidden in (
        "install the countertop", "install the sink", "connect the trap",
        "install the drawers", "load the vanity", "commission the vanity",
    ):
        assert forbidden not in html.lower()


def test_supports_and_rear_rail_are_typed(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    for support in project.model.support_layout.supports:
        assert f'data-support-id="{support.support_id}"' in html
        assert f'data-axis-mm="{support.x_axis_mm:.1f}"' in html
    assert "left end" in html
    assert "center divider" in html
    assert "right end" in html
    assert "zero gravity credit" in html


def test_guide_does_not_invent_connection_hardware(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    assert "Structural fastener schedule: __________________" in html
    assert "Cabinet case/interface detail: __________________" in html
    assert "connection capacity remains unproved" in html


def test_held_actions_are_conditional(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    actions = re.findall(
        r'<article class="frame action".*?</article>', html, re.S,
    )
    assert actions
    assert all(
        "CONDITIONAL — RELEASE RECORD REQUIRED" in row
        for row in actions
    )
```

Also assert: no visible machine identifiers, no `file://`, no external runtime assets, all approved record fields, and a support/model mutation either moves the output or fails coherence.
`installation_visible_extras(project)` must return every rendered `WHY`,
`VERIFY`, inventory, and boundary sentence not already stored on an
`ActionFrame`, so the word-budget assertion covers the actual guide rather
than only frame captions.

- [ ] **Step 2: Verify RED**

```bash
pytest -q tests/test_double_vanity_installation_guide.py
```

Expected: collection fails because the guide module does not exist.

- [ ] **Step 3: Implement the typed projection**

Define:

```python
def project_double_vanity_installation_manual(
    project,
    *,
    related_documents: tuple[RelatedDocumentLink, ...],
) -> ConsumerManual:
    if project.pack_id != "vanity.double_sink":
        raise ValueError(
            "DV72 installation guide requires vanity.double_sink"
        )
    _validate_installation_projection(project)
    return compose_consumer_manual(
        frames=_installation_frames(project),
        title="DV72 — Cabinet Installation Guide",
        basename="dv72_installation_guide.html",
        letters=(),
        kit_gate=(
            "INSTALLATION HOLD — FIELD/STRUCTURAL RELEASE REQUIRED"
        ),
        cover_caption=(
            "Outcome: the empty cabinet is mounted and restrained through the "
            "accepted cabinet case/interface detail, recorded, and held before "
            "countertop, fixtures, plumbing, drawers, loading, or use."
        ),
        related_documents=related_documents,
    )


def build_double_vanity_installation_guide(
    project,
    *,
    related_documents: tuple[RelatedDocumentLink, ...],
) -> str:
    manual = project_double_vanity_installation_manual(
        project, related_documents=related_documents,
    )
    return _render_installation_manual(project, manual)
```

Create one hold frame followed by wall-layout, support-installation, cabinet-placement, cabinet-restraint, and inspection frames. The inspection frame owns the signed record.

`_validate_installation_projection()` must reject: wrong pack; support count other than three; axes not matching left end/center divider/right end; nonzero rail gravity credit; unsupported Rakks identity/revision; false field-verification claims; or contradictory installation authority.

- [ ] **Step 4: Implement Letter sheets and inline SVG**

Render one `section.sheet` per composed page. Each post-gate frame must use:

```html
<article class="frame action" data-frame-id="...">
  <header><span class="step-number">...</span>
    <span class="conditional">CONDITIONAL — RELEASE RECORD REQUIRED</span>
  </header>
  <svg data-action-illustration="true">...</svg>
  <p class="caption">...</p>
  <aside class="why"><b>WHY</b>...</aside>
  <aside class="verify"><b>VERIFY</b>...</aside>
  <aside class="stop"><b>STOP</b>...</aside>
</article>
```

Required typed SVGs: empty mounted-cabinet cover; finished-floor/countertop-top/countertop-underside, x-origin, y-origin, wall-plane, and three support-axis datums; Rakks horizontal arm/diagonal/wall-leg load path with schedule-controlled fastener-location placeholder; accepted handling/support/restraint-plan placeholder with protection/clearance, arm alignment, and the empty case below/around the countertop-support arms; accepted cabinet case/interface-detail placeholder plus lateral-only rear rail; and final level/plumb/square/interface-restraint inspection.

Do not render a selected structural screw, cabinet case/interface screw, two-person lift, equipment, temporary restraint, three-plane cabinet bearing, countertop, sinks, installed plumbing, or installed drawers.

**Approved safety correction:** this supersedes the earlier two-person-placement and three-support-plane wording. The typed support arms bear at the countertop underside rather than the cabinet bottom, while actual case handling/support/restraint remains unselected. Placement must follow the accepted handling/support/restraint plan, and cabinet mounting/restraint must follow the accepted cabinet case/interface detail; no people, equipment, connection, temporary-restraint, or bottom-bearing claim may be invented.

- [ ] **Step 5: Verify GREEN and commit**

```bash
pytest -q tests/test_double_vanity_installation_guide.py
git add src/packs/cabinetry/double_vanity_installation_guide.py   tests/test_double_vanity_installation_guide.py
git commit -m "feat: add DV72 cabinet installation guide"
```

---

### Task 3: Publish and validate the five-document package

**Files:**
- Modify: `src/packs/cabinetry/double_vanity_documents.py`
- Modify: `scripts/double_vanity_documents.py`
- Modify: `tests/test_double_vanity_documents.py`
- Modify: `.superpowers/sdd/progress.md`
- Modify: `docs/projects/dv72/time-log.md`

**Interfaces:**
- Consumes: Task 2 guide builder.
- Produces: an ordered five-file mapping and generated `dv72_installation_guide.html`.

- [ ] **Step 1: Write five-document closure tests**

```python
assert tuple(documents) == (
    "dv72_review_installation.html",
    "dv72_assembly_service.html",
    "dv72_fabrication_coordination.html",
    "dv72_validation_sources.html",
    "dv72_installation_guide.html",
)
for name, html in documents.items():
    assert "file://" not in html
    for other in documents:
        assert f'href="{other}"' in html
```

Also require existing authority banners, `five reader projections` in technical footers, and `INSTALLATION HOLD` plus `STOP BEFORE COUNTERTOP` in the guide.

- [ ] **Step 2: Verify RED**

```bash
pytest -q tests/test_double_vanity_documents.py
```

Expected: current inventory contains only four documents.

- [ ] **Step 3: Integrate the guide**

Update:

```python
FILENAMES = (
    "dv72_review_installation.html",
    "dv72_assembly_service.html",
    "dv72_fabrication_coordination.html",
    "dv72_validation_sources.html",
    "dv72_installation_guide.html",
)
_LABELS[FILENAMES[4]] = "Cabinet installation guide"
```

Build typed `RelatedDocumentLink` values from `FILENAMES`, pass them to the guide, return it fifth, change the footer to `five reader projections`, and change the generator docstring to `Generate the linked five-file DV72 vanity package.`

- [ ] **Step 4: Verify relevant tests**

```bash
pytest -q   tests/test_double_vanity_installation_guide.py   tests/test_double_vanity_documents.py   tests/test_double_vanity_document.py
```

- [ ] **Step 5: Verify deterministic generation**

```bash
rm -rf /tmp/dv72-guide-one /tmp/dv72-guide-two
python scripts/double_vanity_documents.py   --project tests/fixtures/cabinetry/floating_double_sink_four_drawer.project.yaml   --out-dir /tmp/dv72-guide-one
python scripts/double_vanity_documents.py   --project tests/fixtures/cabinetry/floating_double_sink_four_drawer.project.yaml   --out-dir /tmp/dv72-guide-two
diff -ru /tmp/dv72-guide-one /tmp/dv72-guide-two
```

Expected: five files and no diff.

- [ ] **Step 6: Perform rendered QA**

Serve `/tmp/dv72-guide-one` over localhost and verify with browser control:

- 1280 × 900 and 390 × 844 viewports;
- no page-level overflow or clipped STOP/record fields;
- all five local links resolve;
- print-to-PDF page count equals composed sheets;
- each printed page is US Letter, action frames do not split, and page numbers are complete.

Record exact evidence in `docs/projects/dv72/time-log.md`.

- [ ] **Step 7: Obtain and apply independent reviews**

Dispatch an adversarial technical reviewer for load path/authority/model-source checks and a no-context installer reviewer who sees only the guide. Use receiving-code-review, systematic-debugging, and TDD for fixes. Repeat until no Critical or Important findings remain.

- [ ] **Step 8: Run final scoped verification**

```bash
pytest -q   tests/test_action_frames.py   tests/test_consumer_pages.py   tests/test_double_sink_vanity.py   tests/test_double_vanity_document.py   tests/test_double_vanity_documents.py   tests/test_double_vanity_installation_guide.py   tests/test_cabinetry_artifacts.py   tests/test_cabinetry_e2e.py   tests/test_drawer_cabinet_e2e.py
python scripts/double_vanity_documents.py   --project tests/fixtures/cabinetry/floating_double_sink_four_drawer.project.yaml   --out-dir outputs/floating_double_sink_four_drawer
git diff --check
git status --short --branch
```

Expected: scoped tests pass, five documents generate, and only intended files differ.

- [ ] **Step 9: Update accounting, commit, and push**

Update the progress/time logs with measured reuse and bespoke work. Preserve the incomplete repository-wide CAD-suite disclosure unless a fresh full run completes.

```bash
git add src/packs/cabinetry/double_vanity_documents.py   scripts/double_vanity_documents.py tests/test_double_vanity_documents.py   .superpowers/sdd/progress.md docs/projects/dv72/time-log.md
git commit -m "feat: publish linked DV72 installation guide"
git push origin codex/72-floating-double-vanity
git status --short --branch
```

Expected: local and remote feature branch heads match and the worktree is clean.
