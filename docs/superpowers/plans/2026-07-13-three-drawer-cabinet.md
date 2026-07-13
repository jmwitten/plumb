# Three-Drawer Cabinet Implementation Plan

> **Execution contract:** Use `superpowers:executing-plans` to implement this
> plan task by task. Use `superpowers:test-driven-development` for every behavior
> change and `superpowers:verification-before-completion` before any completion
> claim.

**Goal:** Extend `cabinetry.frameless@1` with a real 40-inch three-drawer
clothing cabinet while building a reusable internal drawer-bank core for the
next split-bank vanity.

**Architecture:** Keep the public surface bounded to
`drawer_base_three@1`. Compact authoring expands into a strict drawer-base
declaration. A product-independent `DrawerBankModel` derives box geometry,
hardware, machining, load facts, validation inputs, and process fragments from
an enclosing opening. A drawer-base adapter combines that bank with the existing
floor-supported carcass contract and lowers only to existing DetailSpec
components and relationships. Existing door cabinets continue through their
current path with regression-pinned outputs.

**Tech stack:** Python 3.12, frozen dataclasses, PyYAML, CadQuery/OCCT,
DetailSpec lowering, pytest, deterministic JSON/HTML generation.

**Design source:**
`docs/superpowers/specs/2026-07-13-three-drawer-cabinet-design.md`

## Working rules

- Implement in an isolated git worktree created from committed master.
- In that worktree, create `.shim/detailgen` as a relative symlink to `../src`
  so tests exercise worktree code rather than the main checkout.
- Run each new test once while red and record the expected missing behavior.
- Implement only enough for the current red test, then refactor while green.
- Never stage unrelated `.superpowers` files from the main checkout.
- Do not add process-wide component vocabulary or mutate global registries.
- Preserve the exact existing door-base and vanity manifests, ids, artifacts,
  and findings unless this plan explicitly names an additive field.
- Keep product claims honest: runner compatibility can pass; complete-cabinet
  structural capacity remains unknown unless a real capacity checker runs.

## Task 1: Pin existing behavior and add the compact archetype contract

**Files:**

- Modify: `src/packs/cabinetry/presets.py`
- Modify: `src/packs/cabinetry/schema.py`
- Create: `tests/test_drawer_cabinet_schema.py`
- Modify: `tests/test_cabinetry_presets.py`

### Step 1: Write the red compact-expansion tests

Add a DB40 helper based on the checked-in B30 site/material context:

```python
def compact_db40() -> dict:
    raw = yaml.safe_load(BASE.read_text())
    raw["name"] = "DB40 three-drawer clothing cabinet"
    raw["cabinetry"]["cabinets"] = [{
        "archetype": "drawer_base_three@1",
        "id": "DB40",
        "width": 40,
        "placement": {
            "against": "north_wall",
            "from_left_datum": 24,
        },
        "conditions": {"left_end": "exposed", "right_end": "exposed"},
    }]
    return raw
```

Assert that expansion produces one drawer-base declaration with:

- `type: drawer_base`;
- sizing policy `progressive_clothing_3@1`;
- exactly `top`, `middle`, `bottom` cells;
- front heights 158.75, 254.0, 354.95 mm after parsing;
- box heights 101.6, 177.8, 254.0 mm;
- 40 lb contents per cell;
- fixed runner/locking-device/stabilizer/pull adapter ids; and
- `source_archetype == "drawer_base_three@1"`.

Also assert expanded-record replay produces the same parsed declaration and
that misspellings such as `drawer_base_tree@1`, extra cell keys, or an authored
drawer count fail with path-specific suggestions.

### Step 2: Run the focused tests and confirm red

Run:

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_drawer_cabinet_schema.py tests/test_cabinetry_presets.py -q
```

Expected: FAIL because `drawer_base_three@1` and drawer declarations do not
exist.

### Step 3: Implement strict expansion and declaration types

Add immutable `DrawerCellDecl`, `DrawerBankDecl`, and `DrawerBaseDecl` types.
Change `CabinetrySection.cabinets` to a union of existing `BaseCabinetDecl` and
new `DrawerBaseDecl` without weakening strict parsing.

In `presets.py`, add `drawer_base_three@1` as a cabinet-level archetype. Its
compact authoring accepts only:

```text
archetype, id, width, placement, conditions
```

The expander supplies the fixed DB40 product contract as a full semantic
record. It must not accept arbitrary drawer count, runner family, sizing policy,
or pull name in v1.

The strict expanded parser independently validates the normalized fields so a
hand-edited manifest cannot bypass archetype checks.

### Step 4: Run green and regression tests

Run the focused command above, then:

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_cabinetry_schema.py tests/test_cabinetry_presets.py \
  tests/test_floating_vanity.py -q
```

Expected: PASS; existing door/vanity authoring remains unchanged.

### Step 5: Commit

```bash
git add src/packs/cabinetry/presets.py src/packs/cabinetry/schema.py \
  tests/test_drawer_cabinet_schema.py tests/test_cabinetry_presets.py
git commit -m "feat: add three-drawer cabinet authoring contract"
```

## Task 2: Add pinned runner, stabilizer, locking-device, and pull catalogs

**Files:**

- Modify: `src/packs/cabinetry/catalogs.py`
- Create: `tests/test_drawer_hardware_catalogs.py`

### Step 1: Write failing product-adapter tests

Tests must assert exact, immutable catalog facts:

```python
runner = get_drawer_runner("blum_movento_763_5330s@2026.1")
assert runner.nominal_length_mm == pytest.approx(533)
assert runner.minimum_inside_depth_mm == pytest.approx(553)
assert runner.maximum_side_thickness_mm == pytest.approx(16)
assert runner.inside_width_deduction_mm == pytest.approx(42)
assert runner.static_rating_lb == pytest.approx(125)
assert runner.dynamic_rating_lb == pytest.approx(110)
assert runner.motion == "blumotion_soft_close"

stabilizer = get_lateral_stabilizer("blum_zs7m686mu@2026.1")
assert stabilizer.recommended_from_opening_mm == pytest.approx(610)
assert stabilizer.maximum_opening_mm == pytest.approx(1369)
assert stabilizer.capacity_increase_lb == 0
```

Also assert the T51.7601 handed pair, required runner fixing locations, rear
notch/hook-bore/bottom-recess facts, and Häfele 155.01.613 224 mm pull facts.
Unknown ids must fail loudly with near-miss suggestions.

### Step 2: Confirm red

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_drawer_hardware_catalogs.py -q
```

Expected: FAIL because drawer product dataclasses/getters are absent.

### Step 3: Implement closed catalog adapters

Add dedicated dataclasses and lookup tables; do not overload `HingeProduct` or
use free-form dictionaries. Every adapter carries product id, manufacturer,
source URL, adapter version, dimensional facts, load facts, and evidence level.

Include the manufacturer-required fixing stations for the 21-inch runner and
explicitly distinguish nominal drawer length (533 mm), physical runner length
(544 mm), and minimum inside cabinet depth (553 mm).

### Step 4: Run green and commit

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_drawer_hardware_catalogs.py tests/test_cabinetry_validation.py -q
git add src/packs/cabinetry/catalogs.py tests/test_drawer_hardware_catalogs.py
git commit -m "feat: pin drawer hardware product adapters"
```

## Task 3: Extract the common base shell without changing existing output

**Files:**

- Create: `src/packs/cabinetry/shell.py`
- Modify: `src/packs/cabinetry/model.py`
- Modify: `src/packs/cabinetry/lowering.py`
- Modify: `src/packs/cabinetry/artifacts.py`
- Create: `tests/test_cabinetry_shell_compat.py`

### Step 1: Add characterization tests before refactoring

For the existing B30 fixture, pin:

- ordered part ids/roles and component params;
- ordered machining rows;
- hardware systems and quantities;
- derived values;
- lowered document equality;
- report findings/evidence;
- artifact JSON; and
- manifest JSON before and after calling `require_release()`.

Store the expected payload in a small checked-in JSON fixture only if inline
assertions become unreadable. The fixture must be generated once from committed
`9974131`, reviewed, and thereafter treated as an oracle—not regenerated merely
to make a refactor pass.

### Step 2: Run characterization tests green before edits

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_cabinetry_shell_compat.py -q
```

Expected: PASS against the pre-refactor implementation.

### Step 3: Extract common shell construction

Move only genuinely common behavior into `shell.py`:

- carcass dimensions and coordinate frame;
- ends, bottom, captured back, stretchers, anchor strip;
- independent toe platform;
- surveyed studs and wall anchors;
- captured-back and Confirmat machining;
- wall-anchor, Confirmat, toe-attachment, and adhesive hardware; and
- common derived values and provenance.

The shell builder must accept the concrete cabinet declaration and return an
immutable result that product adapters can extend. Door-specific shelves,
fronts, hinges, shelf-pin rows, calculations, findings, and instructions stay
in the existing door model/artifact path.

Do not rename existing roles or reorder existing output. Preserve the current
`CabinetModel` public shape until all existing consumers pass.

### Step 4: Prove byte stability and commit

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_cabinetry_shell_compat.py tests/test_cabinetry_lowering.py \
  tests/test_cabinetry_artifacts.py tests/test_cabinetry_e2e.py -q
git add src/packs/cabinetry/shell.py src/packs/cabinetry/model.py \
  src/packs/cabinetry/lowering.py src/packs/cabinetry/artifacts.py \
  tests/test_cabinetry_shell_compat.py tests/fixtures/cabinetry
git commit -m "refactor: extract reusable base cabinet shell"
```

## Task 4: Build the reusable drawer-bank semantic model

**Files:**

- Create: `src/packs/cabinetry/drawers.py`
- Create: `tests/test_drawer_bank_model.py`

### Step 1: Write failing derivation tests

Build one bank from a 977.9 mm clear opening and assert:

```python
assert bank.opening_width_mm == pytest.approx(977.9)
assert bank.outside_box_width_mm == pytest.approx(967.9)
assert bank.inside_box_width_mm == pytest.approx(935.9)
assert [cell.cell_id for cell in bank.cells] == ["top", "middle", "bottom"]
assert [cell.front_height_mm for cell in bank.cells] == pytest.approx(
    [158.75, 254.0, 354.95]
)
assert all(cell.box_length_mm == pytest.approx(533) for cell in bank.cells)
```

Pin stable roles for five wood parts per cell:

```text
drawer_top_side_left, drawer_top_side_right, drawer_top_front,
drawer_top_back, drawer_top_bottom
```

and the equivalent middle/bottom roles. Assert the 12 mm bottom groove, 13 mm
recess, 50 mm rear notches, 6 × 10 mm hook bores, locking-device holes, applied
front, pull bores, runner fixing stations, and lateral-stabilizer cut facts.

Add a parent-independence test that builds the same bank under a synthetic
`vanity.V60.left_bank` namespace and proves dimensions/rules are unchanged while
ids are correctly namespaced. This is the key future-vanity seam.

### Step 2: Confirm red

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_drawer_bank_model.py -q
```

### Step 3: Implement immutable bank/cell models

`DrawerBankModel` must accept only opening geometry, cell declarations,
products, material evidence/profile, and namespace. It must not accept or query
toe kick, wall, floor support, plumbing absence, full-cabinet width, or a fixed
drawer count.

Derive moving wood mass per cell from actual part volumes and verified material
density. Add a pinned conservative moving-hardware allowance. Keep runner-system
mass outside the moving-load calculation where the manufacturer rating already
includes it.

Represent manufactured hardware as exact catalog systems plus honest simplified
geometry/clearance envelopes using existing DetailSpec component types; do not
register new global components. Visual proxies must be tagged as such in
provenance and must never be used as capacity evidence.

### Step 4: Run green, check abstraction, and commit

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_drawer_bank_model.py tests/test_drawer_hardware_catalogs.py -q
rg -n "toe|wall|floor|plumbing|three|DB40" src/packs/cabinetry/drawers.py
```

Expected: tests pass; any search matches are documentation/guard messages, not
parent-product assumptions.

```bash
git add src/packs/cabinetry/drawers.py tests/test_drawer_bank_model.py
git commit -m "feat: add reusable drawer bank semantic core"
```

## Task 5: Compile and lower the DB40 product

**Files:**

- Create: `src/packs/cabinetry/drawer_base.py`
- Modify: `src/packs/cabinetry/__init__.py`
- Modify: `src/packs/cabinetry/lowering.py`
- Create: `tests/test_drawer_cabinet_lowering.py`

### Step 1: Write failing physical-model tests

Compile compact DB40 and assert:

- the common carcass/toe/stud/anchor roles are present;
- door, hinge, adjustable-shelf, and shelf-pin roles are absent;
- three fronts and fifteen drawer-box panels are present;
- each runner pair, locking pair, stabilizer kit, pull, and front attachment is
  represented in the hardware schedule and source map;
- exact front/box placements agree with the vertical allocation;
- front closed gaps are 2 mm and side/top/bottom reveals are 1.5 mm;
- the bank's usable inside depth is at least 553 mm; and
- compiled base parts equal lowered components one-for-one.

Add geometry assertions after `project.build()` for actual front extents,
drawer-box extents, closed-position noninterference, and required fastener/
anchor overlaps.

### Step 2: Confirm red

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_drawer_cabinet_lowering.py -q
```

### Step 3: Implement product dispatch and lowering

Add `DrawerBaseModel` that combines `BaseShellModel` and `DrawerBankModel` while
exposing the common packed-project protocol (`mode`, `profile`, `section`,
`parts`, `machining`, `hardware`, `derived`, `source_map`, `anchor_stud_ids`).

In `FramelessCabinetryPack.compile`, dispatch one drawer-base declaration to
the new adapter. Mixed straight runs containing drawer bases remain an explicit
error in this increment; do not silently route them through the door-run path.

Lower:

- common shell bonds/contacts/anchor overlaps unchanged;
- box side/front/back/bottom joinery;
- applied-front attachment;
- represented runner/locking/stabilizer relations where the geometry supports
  an honest bond/contact/overlap; and
- closed-position clearance checks through existing validation vocabulary.

Do not add a `drawer` primitive to DetailSpec.

### Step 4: Run green and commit

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_drawer_cabinet_lowering.py tests/test_cabinetry_lowering.py \
  tests/test_cabinetry_e2e.py -q
git add src/packs/cabinetry/drawer_base.py src/packs/cabinetry/__init__.py \
  src/packs/cabinetry/lowering.py tests/test_drawer_cabinet_lowering.py
git commit -m "feat: compile and lower three-drawer cabinet"
```

## Task 6: Enforce runner, sizing, load, and interference rules adversarially

**Files:**

- Modify: `src/packs/cabinetry/drawer_base.py`
- Modify: `src/packs/cabinetry/validation.py`
- Create: `tests/test_drawer_cabinet_validation.py`

### Step 1: Add one-mutation red tests

Create mutation helpers that alter the normalized declaration or copied model
one fact at a time. Pin separate failure/unknown findings for:

- front heights no longer closing the reveal equation;
- opening-width/box-width formula mismatch;
- side thickness over 16 mm;
- usable depth below 553 mm;
- box height violating opening minus 23 mm;
- bottom recess/clearance mismatch;
- missing rear notch or hook bore;
- missing required runner fixing station;
- missing/wrong-handed locking device;
- missing lateral stabilizer at 977.9 mm opening;
- stabilizer falsely increasing capacity;
- moving mass plus 40 lb contents over 110 lb dynamic rating;
- pull/front screw emerging through the finished face;
- closed front gap outside the 2 mm target/adjustment envelope;
- extended envelope colliding with a declared obstruction; and
- sequencing removal/reinstallation before adjustment identity is recorded.

Every finding assertion must name the stable rule, verdict, severity, evidence
level, affected ids, and a teaching message with actual and required values.

### Step 2: Confirm red

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_drawer_cabinet_validation.py -q
```

### Step 3: Implement drawer-specific validation

Share the existing material, site, base support, stud, anchor embedment,
countertop support, physical-test UNKNOWN, and whole-cabinet capacity UNKNOWN
checks through common helpers. Do not run door/hinge/shelf checks on drawer
models.

Use catalog facts—not duplicated numeric literals—as the source of limits.
Keep geometric compatibility, load-rating fit, and whole-cabinet structural
capacity as separate findings.

### Step 4: Run green and commit

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_drawer_cabinet_validation.py \
  tests/test_cabinetry_validation.py tests/test_floating_vanity.py -q
git add src/packs/cabinetry/drawer_base.py src/packs/cabinetry/validation.py \
  tests/test_drawer_cabinet_validation.py
git commit -m "feat: validate wide soft-close drawer cabinet"
```

## Task 7: Generate fabrication, shipping, installation, and commissioning data

**Files:**

- Modify: `src/packs/cabinetry/artifacts.py`
- Create: `tests/test_drawer_cabinet_artifacts.py`

### Step 1: Write failing artifact tests

Assert the DB40 artifact payload includes:

- the common shell/toe cut list plus three fronts and fifteen box panels;
- exposed-edge banding for fronts and box tops as specified;
- exact runner, locking-device, stabilizer, pull, front-fastener, Confirmat,
  toe-attachment, adhesive, and wall-anchor quantities/URLs;
- bottom grooves, rear notches, hook bores, runner fixing stations,
  stabilizer preparation, front attachments, and 224 mm pull bores;
- stable fabrication/assembly stages from the design;
- conventional shipping: adjust, label/pair, remove drawers, ship empty carcass;
- installation: level/shim/anchor empty carcass, reinstall drawers by label;
- commissioning: cycle, full extension, BLUMOTION, 1.5/2 mm reveals, under-load
  operation, fastener inspection, and acceptance record; and
- no vague standalone phrase `adjust as needed`.

Assert every artifact part id resolves to the model/source map and every
machining row resolves to a real part.

### Step 2: Confirm red, implement, and run green

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_drawer_cabinet_artifacts.py -q
```

Add drawer-specific artifact composition while retaining the existing
`CabinetArtifacts` JSON shape. Prefer reusable step fragments returned by
`DrawerBankModel`; the parent product orders them with shell/site stages.

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_drawer_cabinet_artifacts.py tests/test_cabinetry_artifacts.py -q
git add src/packs/cabinetry/artifacts.py tests/test_drawer_cabinet_artifacts.py
git commit -m "feat: generate drawer shop and installation artifacts"
```

## Task 8: Add the real DB40 example, manifest protocol, and release gate

**Files:**

- Create: `details/frameless_three_drawer_40.project.yaml`
- Create: `tests/fixtures/cabinetry/frameless_three_drawer_40.project.yaml`
- Modify: `src/packs/project.py`
- Modify: `tests/test_cabinetry_e2e.py`
- Create: `tests/test_drawer_cabinet_e2e.py`

### Step 1: Write the checked-in compact project

Use the existing verified material/site structure, widen/position the wall and
stud survey so DB40 has at least two verified anchor targets, and author only
the compact `drawer_base_three@1` declaration. The detail and test fixture must
be byte-identical.

### Step 2: Write failing end-to-end tests

Assert:

- compact compile, build, base validation, and `require_release()` succeed;
- `release_ready` remains false until base validation runs;
- expanded-project replay is deterministic;
- manifest catalog entries include runner, locking device, stabilizer, pull,
  wall anchor, and product URLs while the existing B30 catalog object is
  byte-identical to its characterization oracle;
- manifest records the archetype and sizing-policy ids;
- all three drawers are physical boxes in the built assembly;
- no global component/material/connection registry changes after compile; and
- compilation is deterministic across two fresh processes, not only two objects
  in one process.

### Step 3: Generalize manifest catalogs additively

Give packed models a deterministic catalog-manifest protocol. Preserve the
existing B30 payload exactly:

```json
{"hinge":"...","wall_anchor":"..."}
```

Drawer models add their own closed entries. Do not add empty hinge or shelf
sentinels.

### Step 4: Run green and commit

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_drawer_cabinet_e2e.py tests/test_cabinetry_e2e.py \
  tests/test_pack_project.py -q
git add details/frameless_three_drawer_40.project.yaml \
  tests/fixtures/cabinetry/frameless_three_drawer_40.project.yaml \
  src/packs/project.py tests/test_cabinetry_e2e.py \
  tests/test_drawer_cabinet_e2e.py
git commit -m "feat: add releasable DB40 packed project"
```

## Task 9: Produce the self-contained HTML and drawings

**Files:**

- Create: `scripts/cabinetry_project_report.py`
- Create: `tests/test_cabinetry_project_report.py`
- Modify: `README.md`
- Generated, not committed unless repository convention says otherwise:
  `outputs/frameless_three_drawer_40/frameless_three_drawer_40_build_document.html`

### Step 1: Write failing report tests

The report generator must accept any supported packed cabinetry project and
derive all content from `PackedProject`, not a parallel geometry table. Test
that DB40 HTML contains:

- a release/unknown headline that distinguishes structural capacity;
- embedded interactive 3D viewer data from the built assembly;
- front, side, plan, isometric, exploded, and drawer-detail images;
- exact overall/front/box/reveal dimensions;
- cut list, edge bands, hardware, machining, findings/evidence, source map;
- fabrication, assembly, shipping, installation, and commissioning sections;
- manufacturer source links; and
- stable part ids for `top`, `middle`, and `bottom` drawers.

Assert the rendered dimensions equal model/artifact values and that a deliberate
mutation of the model changes both report text and validation rather than only
one surface.

### Step 2: Confirm red and implement

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_cabinetry_project_report.py -q
```

Reuse existing rendering/viewer utilities for static PNGs, GLB, viewer payload,
CSS, and JS. Add cabinetry-specific tables and dimension overlays, but do not
copy the single-detail base-spec compiler path. The report must call
`compile_project_file`, `require_release`, and then render the same built
assembly/artifacts it reports.

### Step 3: Generate and inspect the real deliverable

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  scripts/cabinetry_project_report.py \
  details/frameless_three_drawer_40.project.yaml \
  --out outputs/frameless_three_drawer_40/frameless_three_drawer_40_build_document.html
```

Open the HTML in the in-app browser and inspect at desktop and narrow viewport.
Verify:

- the cabinet visibly has three progressively taller fronts;
- pulls are present and centered;
- drawer boxes, runners/stabilizer representation, toe platform, carcass, and
  wall context are legible;
- dimensions do not overlap or contradict tables;
- interactive viewer loads and can isolate/explode parts; and
- no clipped tables, blank renders, horizontal page overflow, or unreadable
  text remains.

Fix report code and rerun tests/generation until the visual inspection passes.

### Step 4: Document and commit

Update the optional-packs README section with the DB40 compile/report commands,
the bounded archetype surface, the reusable vanity seam, and explicit non-goals.

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_cabinetry_project_report.py -q
git add scripts/cabinetry_project_report.py tests/test_cabinetry_project_report.py README.md
git commit -m "feat: add cabinetry build document"
```

## Task 10: Adversarial review and complete verification

**Files:**

- Modify only files justified by review findings.
- Update: `docs/superpowers/specs/2026-07-13-three-drawer-cabinet-design.md`
  only to mark implementation status or record an approved clarification; do
  not rewrite requirements to match bugs.

### Step 1: Run the complete focused pack gate

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_pack_project.py tests/test_cabinetry_schema.py \
  tests/test_cabinetry_presets.py tests/test_cabinetry_lowering.py \
  tests/test_cabinetry_validation.py tests/test_cabinetry_artifacts.py \
  tests/test_cabinetry_e2e.py tests/test_cabinetry_run.py \
  tests/test_floating_vanity.py tests/test_drawer_hardware_catalogs.py \
  tests/test_drawer_cabinet_schema.py tests/test_drawer_bank_model.py \
  tests/test_drawer_cabinet_lowering.py tests/test_drawer_cabinet_validation.py \
  tests/test_drawer_cabinet_artifacts.py tests/test_drawer_cabinet_e2e.py \
  tests/test_cabinetry_project_report.py -q
```

Expected: PASS with no unexpected skips/xfails.

### Step 2: Run the full suite and packaging gate

```bash
PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest -q
/Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m build
```

Expected baseline: all tests pass; only the repository's pre-existing expected
skips/xfail remain. Inspect wheel contents to confirm new Python modules are
included. The generated HTML is runtime output and need not ship in the wheel.

### Step 3: Perform an independent adversarial read

Review the implementation against every acceptance item in the design, with
special attention to:

- whether “three drawers” is real geometry rather than fronts only;
- any duplicated runner number outside the catalog adapter;
- any stabilizer capacity credit;
- missing fixing stations/locking devices;
- incorrect moving-load mass accounting;
- parent-product assumptions inside `drawers.py`;
- manifest/report facts that do not originate in the model;
- existing door/vanity drift; and
- structural/certification language that overclaims.

Turn each discovered issue into a failing regression test before fixing it.

### Step 4: Regenerate final deliverables and verify git state

Regenerate the HTML from the final commit, open it once more, and capture the
absolute path and file size for handoff.

```bash
git diff --check
git status --short
git log --oneline --decorate -12
```

Only intentional branch changes may remain. Do not stage generated caches,
temporary GLBs, `.shim`, or unrelated files.

### Step 5: Final commit if review produced changes

```bash
git add <reviewed-files-only>
git commit -m "fix: harden three-drawer cabinet release contract"
```

Then use `superpowers:finishing-a-development-branch` to present the verified
integration choices. Do not merge without the user's authorization.
