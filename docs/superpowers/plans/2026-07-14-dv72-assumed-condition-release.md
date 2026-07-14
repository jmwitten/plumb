# DV72 Assumed-Condition Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert DV72 into a conditional cabinet-fabrication package driven by explicit assumed site conditions and selected manufacturer products, while retaining field-installation and trade-controlled holds.

**Architecture:** Extend `vanity.double_sink@1`; do not add another geometry engine. Typed assumption, installed-plumbing, runner, countertop, and support records feed the existing model, findings, artifacts, and four HTML projections. Assumptions enable analysis but never masquerade as field verification.

**Tech Stack:** Python 3.12, frozen dataclasses, existing cabinetry pack/compiler, pytest, deterministic HTML/SVG generation.

## Global Constraints

- Preserve 72 in width, 11 in cabinet-bottom datum, 34.5 in finished counter height, two equal sink bays, and four physical drawers.
- Mark the synthetic wall and rough-ins `owner_assumed`, never `field_verified`.
- Drive geometry with Kohler K-20000, K-7124-A, and K-8998.
- Use Blum MOVENTO `763.4570S` above and `763.3050S` below.
- Use a 30 mm quartz slab with a 38 mm visual edge; the fabricator's accepted template controls stone cutting.
- Use Rakks EH vanity supports as the primary gravity path and the rear rail only for positioning/lateral restraint.
- Preserve licensed-plumbing, actual field-verification, stone-cutting, and structural-authority holds.
- Use test-first red/green cycles for every behavior change.

## File Structure

- `tests/fixtures/cabinetry/floating_double_sink_four_drawer.project.yaml`: assumed conditions and non-verified synthetic site.
- `src/packs/cabinetry/double_vanity.py`: typed inputs, geometry, findings, and artifact authority.
- `src/packs/cabinetry/double_vanity_documents.py`: scoped statuses and four reader projections.
- `src/packs/cabinetry/double_vanity_document.py`: legacy projection consistency only.
- `tests/test_double_sink_vanity.py`: model, mutation, provenance, release, and mount tests.
- `tests/test_double_vanity_documents.py`: status, assumption, responsibility, and routing tests.
- `tests/test_double_vanity_document.py`: changed model facts.
- `docs/projects/dv72/time-log.md`: implementation/review timing and reuse accounting.

---

### Task 1: Assumed Site Basis and Provenance

**Files:**
- Modify: `tests/fixtures/cabinetry/floating_double_sink_four_drawer.project.yaml`
- Modify: `src/packs/cabinetry/double_vanity.py`
- Test: `tests/test_double_sink_vanity.py`

**Interfaces:**
- Produces: `AssumedSiteBasis`, `RoughInPoint`, `DoubleVanitySection.assumed_site`, `DoubleVanityModel.assumed_site`.
- Consumes: existing section/site declarations and project units.

- [ ] **Step 1: Write failing tests**

```python
def test_owner_assumptions_are_explicit_and_never_field_verified():
    model = _project().model
    assert model.assumed_site.provenance == "owner_assumed"
    assert not model.assumed_site.field_verified
    assert model.assumed_site.wall_length_mm == pytest.approx(144 * 25.4)
    assert all(not stud.verified for stud in model.section.site.wall.studs)

def test_assumed_rough_ins_match_the_approved_schedule():
    basis = _project().model.assumed_site
    assert [p.x_mm for p in basis.wastes] == pytest.approx([42 * 25.4, 78 * 25.4])
    assert [p.z_mm for p in basis.wastes] == pytest.approx([19 * 25.4] * 2)
    assert [p.x_mm for p in basis.supplies] == pytest.approx(
        [38 * 25.4, 46 * 25.4, 74 * 25.4, 82 * 25.4]
    )
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q tests/test_double_sink_vanity.py -k 'owner_assumptions or assumed_rough_ins'`

Expected: FAIL because `assumed_site` is absent.

- [ ] **Step 3: Implement typed assumptions**

```python
@dataclass(frozen=True)
class RoughInPoint:
    point_id: str
    kind: str
    x_mm: float
    y_mm: float
    z_mm: float
    provenance: str

@dataclass(frozen=True)
class AssumedSiteBasis:
    provenance: str
    field_verified: bool
    wall_length_mm: float
    wall_height_mm: float
    vanity_left_mm: float
    floor_elevation_mm: float
    finish_thickness_mm: float
    backing: str
    wastes: tuple[RoughInPoint, ...]
    supplies: tuple[RoughInPoint, ...]
```

Parse `double_vanity.assumed_conditions`. Reject any provenance other than `owner_assumed` and reject `field_verified: true`. Mark synthetic studs and floor unverified in the fixture.

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q tests/test_double_sink_vanity.py -k 'owner_assumptions or assumed_rough_ins'`

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/cabinetry/floating_double_sink_four_drawer.project.yaml src/packs/cabinetry/double_vanity.py tests/test_double_sink_vanity.py
git commit -m "feat: model DV72 assumed site basis"
```

---

### Task 2: Manufacturer-Driven Plumbing and Drawer Geometry

**Files:**
- Modify: `src/packs/cabinetry/double_vanity.py`
- Test: `tests/test_double_sink_vanity.py`

**Interfaces:**
- Consumes: `AssumedSiteBasis`, `K20000`, `K7124_A`, `K8998`, `AnalyticEnvelope`, `PlumbingPath`.
- Produces: product-authoritative path envelopes and lower runner `763.3050S`.

- [ ] **Step 1: Write failing mutation and runner tests**

```python
def test_drain_and_trap_dimensions_drive_geometry(monkeypatch):
    import detailgen.packs.cabinetry.double_vanity as dv
    baseline = _project().model
    monkeypatch.setattr(dv, "K7124_A", replace(dv.K7124_A, body_height_mm=160.0))
    monkeypatch.setattr(dv, "K8998", replace(dv.K8998, overall_length_mm=330.0))
    changed = _project().model
    assert changed.plumbing_paths[0].element("tailpiece").height_mm != pytest.approx(
        baseline.plumbing_paths[0].element("tailpiece").height_mm
    )
    assert changed.plumbing_paths[0].element("p_trap").depth_mm != pytest.approx(
        baseline.plumbing_paths[0].element("p_trap").depth_mm
    )

def test_lower_drawers_use_selected_12_in_movento():
    model = _project().model
    for bay in ("left", "right"):
        runner = model.drawer(bay, "lower").runner
        assert runner.selected_sku == "763.3050S"
        assert runner.minimum_drawer_length_mm == pytest.approx(305.0)
        assert runner.minimum_inside_depth_mm == pytest.approx(325.0)
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q tests/test_double_sink_vanity.py -k 'drain_and_trap_dimensions or lower_drawers_use'`

Expected: FAIL because plumbing is hard-coded and the lower runner is unselected.

- [ ] **Step 3: Implement product-driven geometry**

Add `PlumbingPath.element(kind: str)`. Locate the undermount sink at the 30 mm slab underside. Extend K-7124-A by `body_height_mm` and `connection_od_mm`. Orient K-8998 from that outlet toward the matching assumed 19 in AFF waste using its length, height, diameters, cleanout, and service allowance. Derive supplies from the assumed points and recompute both drawer boxes without reducing the 1/2 in clearance.

Use this lower runner:

```python
StudyRunner(
    family_id="blum_movento_763_3050s@2026.1",
    soft_close=True,
    full_extension=True,
    selected_sku="763.3050S",
    source_url="https://d2.blum.com/services/BEC003/movento_ep_dok_bus_%24sen-us_%24aof_%24v7.pdf",
    minimum_drawer_length_mm=305.0,
    minimum_inside_depth_mm=325.0,
)
```

- [ ] **Step 4: Scope the coordination finding**

PASS `double_vanity.geometry.fixture_plumbing_drawer` only when product IDs control the envelopes, connection diameters agree, each trap reaches its assumed waste, drawers clear all product envelopes, and both runners fit. Use FAIL for contradictions and UNKNOWN for missing authority.

- [ ] **Step 5: Verify GREEN**

Run: `pytest -q tests/test_double_sink_vanity.py -k 'plumbing or drawer or fixture or runner'`

Expected: all selected tests pass; impossible mutations fail compilation or validation.

- [ ] **Step 6: Commit**

```bash
git add src/packs/cabinetry/double_vanity.py tests/test_double_sink_vanity.py
git commit -m "feat: drive DV72 service geometry from products"
```

---

### Task 3: Countertop and Conditional Cut Authority

**Files:**
- Modify: `src/packs/cabinetry/double_vanity.py`
- Test: `tests/test_double_sink_vanity.py`

**Interfaces:**
- Consumes: product-driven geometry and `PackedProject.artifacts`.
- Produces: `CountertopStudy`, `ConditionalRelease`, conditional cabinet/drawer cut inventory.

- [ ] **Step 1: Write failing release tests**

```python
def test_30_mm_countertop_keeps_finished_height():
    model = _project().model
    assert model.countertop.structural_thickness_mm == pytest.approx(30.0)
    assert model.countertop.visual_edge_height_mm == pytest.approx(38.0)
    total = model.section.vanity.bottom_elevation_mm + model.section.vanity.body_height_mm + 30.0
    assert total == pytest.approx(34.5 * 25.4)

def test_conditional_release_emits_drawers_but_withholds_stone():
    project = _project()
    roles = {item.role for item in project.artifacts.cut_list}
    assert "drawer_left_upper_bottom_bridge" in roles
    assert "drawer_right_lower_bottom" in roles
    assert "countertop" not in roles
    assert project.model.release.fabrication_status == "CONDITIONAL_FABRICATION_RELEASE"
    assert project.model.release.installation_status == "HOLD_FIELD_VERIFY"
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q tests/test_double_sink_vanity.py -k '30_mm_countertop or conditional_release'`

Expected: FAIL because the current slab is 38.1 mm and drawers are withheld.

- [ ] **Step 3: Implement countertop and release records**

```python
@dataclass(frozen=True)
class CountertopStudy:
    material: str
    structural_thickness_mm: float
    visual_edge_height_mm: float
    cutout_template_id: str
    stone_cut_authority: str

@dataclass(frozen=True)
class ConditionalRelease:
    fabrication_status: str
    installation_status: str
    trade_status: str
    commissioning_status: str
```

Set body height to `34.5 in - 11 in - 30 mm`. Emit drawer parts only when product geometry and runner applicability pass. Keep stone out of the cut list and name the fabricator-accepted K-20000 template as controlling.

- [ ] **Step 4: Test authority withdrawal**

Mutate the trap beyond case depth and assert compilation fails or drawer roles disappear. Empty the sink template ID and assert stone remains withheld without invalidating safe cabinet panels.

- [ ] **Step 5: Verify GREEN**

Run: `pytest -q tests/test_double_sink_vanity.py`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/packs/cabinetry/double_vanity.py tests/test_double_sink_vanity.py
git commit -m "feat: issue conditional DV72 cut authority"
```

---

### Task 4: Primary Mounting System and Load Accounting

**Files:**
- Modify: `src/packs/cabinetry/double_vanity.py`
- Test: `tests/test_double_sink_vanity.py`

**Interfaces:**
- Consumes: vanity/countertop geometry, assumed backing, modeled inventory, Rakks guide.
- Produces: `SupportLayout`, `LoadCase`, three support envelopes, scoped mount findings.

- [ ] **Step 1: Write failing support tests**

```python
def test_three_supports_carry_gravity_without_rail_credit():
    model = _project().model
    assert len(model.support_layout.supports) == 3
    assert model.support_layout.max_spacing_mm <= 36 * 25.4
    assert model.support_layout.gravity_path == "rakks_eh_primary"
    assert model.support_layout.rear_rail_role == "positioning_and_lateral_only"
    assert model.load_case.factored_total_lb / 3 <= model.mount_reference.static_capacity_lb

def test_mount_layout_passes_but_installation_waits_for_real_backing():
    findings = {f.rule: f for f in _project().report.findings}
    assert findings["double_vanity.mount.layout"].verdict == "PASS"
    assert findings["double_vanity.release.wall_mount"].verdict == "UNKNOWN"
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q tests/test_double_sink_vanity.py -k 'three_supports or mount_layout_passes'`

Expected: FAIL because support/load records are absent.

- [ ] **Step 3: Implement conservative support analysis**

Model quartz, plywood, sinks, hardware/plumbing, contents, and service/live load separately; apply a 1.5 factor. Place three EH supports below the left end, divider, and right end at no more than 36 in spacing. Compare per-support demand to the published 450 lb evenly distributed static capacity only under the manufacturer's acceptable blocking/stud application and four secured screws per support. Assign zero gravity capacity to the rear rail.

Keep `double_vanity.release.wall_mount` UNKNOWN pending actual backing, product revision, fastener installation, and required structural review.

- [ ] **Step 4: Test conservative failures**

Increase factored load beyond three capacities and assert layout FAIL. Remove one support and assert spacing or demand FAIL. Change backing to `none` and assert installation remains blocked.

- [ ] **Step 5: Verify GREEN**

Run: `pytest -q tests/test_double_sink_vanity.py -k 'mount or support or load'`

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/packs/cabinetry/double_vanity.py tests/test_double_sink_vanity.py
git commit -m "feat: model DV72 primary support load path"
```

---

### Task 5: Conditional Four-Document Package

**Files:**
- Modify: `src/packs/cabinetry/double_vanity_documents.py`
- Modify: `src/packs/cabinetry/double_vanity_document.py`
- Test: `tests/test_double_vanity_documents.py`
- Test: `tests/test_double_vanity_document.py`

**Interfaces:**
- Consumes: assumptions, product-driven paths, countertop/release/support/load objects, findings.
- Produces: the same four deterministic HTML filenames with scoped statuses.

- [ ] **Step 1: Write failing status tests**

```python
def test_documents_distinguish_all_authorities():
    docs = _documents()
    assert "CONDITIONAL FABRICATION RELEASE" in docs["dv72_fabrication_coordination.html"]
    assert "INSTALLATION HOLD — FIELD VERIFY" in docs["dv72_review_installation.html"]
    assert "owner_assumed" in docs["dv72_review_installation.html"]
    assert "not field verified" in docs["dv72_review_installation.html"]
    assert "TRADE HOLD" in docs["dv72_validation_sources.html"]

def test_fabrication_names_both_runners_and_withholds_stone():
    html = _documents()["dv72_fabrication_coordination.html"]
    assert "763.4570S" in html
    assert "763.3050S" in html
    assert "Released cabinet and drawer inventory" in html
    assert "Stone cutting remains fabricator-controlled" in html
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q tests/test_double_vanity_documents.py -k 'distinguish_all or names_both'`

Expected: FAIL because every page still has the blanket design hold.

- [ ] **Step 3: Project model-derived statuses**

Make `_shell` accept status content. Add the assumption schedule and field-comparison checklist to review/install. Show exact rough-ins and both runner SKUs in assembly. Show released inventory, tolerances, joinery/finish assumptions, and stone hold in fabrication. Show responsible party and blocking phase for every validation finding.

- [ ] **Step 4: Preserve routing and determinism**

Keep four filenames and reciprocal navigation; do not expand the omnibus document. Update legacy assertions only for changed facts.

- [ ] **Step 5: Verify GREEN**

Run: `pytest -q tests/test_double_vanity_document.py tests/test_double_vanity_documents.py`

Expected: all tests pass and repeated generation hashes match.

- [ ] **Step 6: Commit**

```bash
git add src/packs/cabinetry/double_vanity_documents.py src/packs/cabinetry/double_vanity_document.py tests/test_double_vanity_document.py tests/test_double_vanity_documents.py
git commit -m "feat: publish conditional DV72 fabrication package"
```

---

### Task 6: Render, Review, Verify, and Push

**Files:**
- Modify: `docs/projects/dv72/time-log.md`
- Modify implementation/tests only for review findings corrected test-first.

**Interfaces:**
- Consumes: completed conditional package.
- Produces: regenerated HTML, two reviews, clean verification, commits, pushed branch.

- [ ] **Step 1: Generate and inspect**

```bash
source .venv/bin/activate
python scripts/double_vanity_documents.py --project tests/fixtures/cabinetry/floating_double_sink_four_drawer.project.yaml --out-dir outputs/floating_double_sink_four_drawer
```

Inspect the key section and statuses at desktop and 390 px. Confirm no overflow, clipped labels, contradictory authority, or imperative installation language under a hold.

- [ ] **Step 2: Obtain independent reviews**

Ask an adversarial reviewer to mutate product/load/assumption inputs and audit release authority. Ask a fresh no-context installer what they would fabricate/install and what blocks them. Classify findings.

- [ ] **Step 3: Correct Critical and Important findings test-first**

For each accepted finding: add one failing regression, verify RED, implement the smallest correction, and rerun to GREEN. Never close a trade/field gate with prose.

- [ ] **Step 4: Update time accounting**

Append exact checkpoints, reused platform functions, bespoke work, and excluded unmeasured research time.

- [ ] **Step 5: Run fresh verification**

```bash
source .venv/bin/activate
pytest -q tests/test_double_sink_vanity.py tests/test_double_vanity_document.py tests/test_double_vanity_documents.py
python scripts/double_vanity_documents.py --project tests/fixtures/cabinetry/floating_double_sink_four_drawer.project.yaml --out-dir outputs/floating_double_sink_four_drawer
git diff --check
```

Expected: zero failures, deterministic inventory/hashes, no whitespace errors. Report complete-suite status separately if CAD-heavy tests are not completed.

- [ ] **Step 6: Commit and push**

```bash
git add docs/projects/dv72/time-log.md src tests docs/superpowers
git commit -m "fix: close DV72 conditional release review"
git push origin codex/72-floating-double-vanity
```

Verify `HEAD` equals the remote branch and the worktree is clean.
