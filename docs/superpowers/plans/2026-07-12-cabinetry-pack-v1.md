# Frameless Cabinetry Pack v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an opt-in, versioned frameless cabinetry pack that lowers one real two-door base cabinet and its stud-wall installation into the existing construction language with structured validation, provenance, and shop/install artifacts.

**Architecture:** A new `detailgen.packs` front end owns project loading and a compilation-local pack registry. The cabinetry implementation uses focused schema, profile/catalog, model, lowering, validation, and artifact modules; its lowerer produces an ordinary `DetailSpecDoc` consumed by the unchanged base compiler. `PackedProject` delegates existing geometry/render/BOM behavior and adds pack findings, evidence, and deterministic cabinetry artifacts.

**Tech Stack:** Python 3.12, frozen dataclasses, PyYAML, existing DetailSpec compiler, CadQuery 2.8, pytest.

## Global Constraints

- Existing `load_spec_file`, `compile_spec`, and `compile_spec_file` behavior must remain unchanged.
- Pack activation must be explicit and exact-version checked.
- No pack import may mutate process-wide component/material/connection/check registries.
- Use only existing registered base components in lowered specs.
- KCMA certification may never be inferred; physical-test evidence remains explicit.
- V1 scope is one frameless, two-door base cabinet with one adjustable shelf and installation against a stud wall.
- Do not edit STEPDOC-owned `src/spec/schema.py`, `src/spec/loader.py`, `src/spec/semantics.py`, `src/assemblies/connection.py`, `src/validation/install.py`, `details/platform.spec.yaml`, or report-script sequence surfaces.

---

### Task 1: Project front end and scoped pack registry

**Files:**
- Create: `src/packs/__init__.py`
- Create: `src/packs/project.py`
- Create: `src/packs/registry.py`
- Modify: `pyproject.toml`
- Test: `tests/test_pack_project.py`

**Interfaces:**
- Produces: `PackRef`, `ProjectDoc`, `PackRegistry`, `load_project_text(text, fmt="yaml")`, `load_project_file(path)`, `compile_project(doc)`, and `compile_project_file(path)`.
- Consumes later: a pack object exposing `pack_id`, `major_version`, `parse_project_section(raw, project)`, and `compile(parsed, project)`.

- [ ] **Step 1: Write failing strict-loader and isolation tests**

```python
def test_project_requires_explicit_known_pack():
    with pytest.raises(ProjectSchemaError, match="unknown pack"):
        compile_project(load_project_text("name: x\nunits: in\npacks: [missing@1]\n"))

def test_importing_packs_does_not_change_base_registry_names():
    before = tuple(components.names())
    import detailgen.packs
    assert tuple(components.names()) == before
```

- [ ] **Step 2: Run tests and verify feature-missing failures**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_pack_project.py -q`
Expected: import/collection failure because `detailgen.packs` does not exist.

- [ ] **Step 3: Implement the strict document shell and local registry**

`PackRegistry.resolve(PackRef("cabinetry.frameless", 1))` must either return the
exact registered implementation or raise a diagnostic listing available ids and
versions. Reject unknown top-level keys and duplicate pack ids. Do not call or
modify `detailgen.core.registry`.

- [ ] **Step 4: Run focused tests**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_pack_project.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/packs tests/test_pack_project.py
git commit -m "feat: add scoped packed-project front end"
```

### Task 2: Cabinet schema, profiles, and manufacturer catalog

**Files:**
- Create: `src/packs/cabinetry/__init__.py`
- Create: `src/packs/cabinetry/schema.py`
- Create: `src/packs/cabinetry/profiles.py`
- Create: `src/packs/cabinetry/catalogs.py`
- Test: `tests/test_cabinetry_schema.py`

**Interfaces:**
- Produces: `CabinetrySection`, `BaseCabinetDecl`, `StudWallSurvey`, `ConstructionProfile`, `HingeProduct`, `MaterialProduct`, and `FramelessCabinetryPack`.
- Profile key: `frameless_plywood_shop_v1@1.0.0`.
- Hinge key: `blum_clip_top_blumotion_110_screw_on@2025.1`.

- [ ] **Step 1: Write failing tests for the approved declaration and teaching errors**

```python
def test_parse_approved_base_cabinet():
    doc = load_project_file(FIXTURE)
    parsed = default_pack_registry().resolve(doc.packs[0]).parse(doc)
    assert parsed.cabinets[0].cabinet_id == "B30"
    assert parsed.cabinets[0].width_mm == pytest.approx(30 * IN)

@pytest.mark.parametrize("mutation, phrase", [
    ({"front": {"doors": 3}}, "v1 requires exactly two"),
    ({"interior": {"adjustable_shelves": 2}}, "v1 requires exactly one"),
    ({"profile": "not-real"}, "known profiles"),
])
def test_v1_rejects_unsupported_variants(mutation, phrase): ...
```

- [ ] **Step 2: Run and verify missing-schema failures**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_cabinetry_schema.py -q`
Expected: FAIL because cabinetry parser/types are missing.

- [ ] **Step 3: Implement frozen schema types and catalogs**

Accept bare numbers in project units and explicit `mm`, `in`, and `ft` quantities.
Reject booleans as dimensions. Store every resolved dimension in millimeters.
Encode the approved plywood/back/toe-kick/joinery defaults and Blum cup diameter,
cup depth, door-thickness range, overlay range, 37-mm plate line, System-32 plate
spacing, opening angle, adjustment envelope, and two-hinge v1 door limit.

- [ ] **Step 4: Run focused tests**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_cabinetry_schema.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/packs/cabinetry tests/test_cabinetry_schema.py
git commit -m "feat: define frameless cabinet profile and catalogs"
```

### Task 3: Semantic cabinet model and deterministic lowering

**Files:**
- Create: `src/packs/cabinetry/model.py`
- Create: `src/packs/cabinetry/lowering.py`
- Test: `tests/test_cabinetry_lowering.py`

**Interfaces:**
- Produces: `CabinetModel`, `PartModel`, `MachiningFeature`, `SurfaceClass`, `DerivedValue`, `build_model(section, profile, catalogs)`, and `lower_model(model) -> DetailSpecDoc`.
- Stable ids use `cabinetry.<cabinet_id>.<role>` and provenance records source declaration, rule, pack/profile/catalog versions.

- [ ] **Step 1: Write failing model/lowering tests**

```python
def test_b30_expands_to_named_real_parts():
    model = build_fixture_model()
    assert {p.role for p in model.parts} >= {
        "left_end", "right_end", "bottom", "captured_back",
        "front_stretcher", "rear_stretcher", "adjustable_shelf",
        "door_left", "door_right", "anchor_strip",
    }

def test_lowered_doc_uses_only_base_component_vocabulary():
    doc = lower_model(build_fixture_model())
    assert {c.type for c in doc.components} <= {
        "plywood_panel", "lumber", "structural_screw"
    }
```

- [ ] **Step 2: Run and verify feature-missing failures**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_cabinetry_lowering.py -q`
Expected: FAIL because model/lowering modules do not exist.

- [ ] **Step 3: Implement dimensional derivation and stable provenance**

Derive clear opening, captured-back position, stretcher sizes, shelf clearance,
paired-door widths/reveals, independent toe-kick members, anchor strip, hinge cup
and plate locations, System-32 shelf-pin rows, wall-screw locations, and all raw
placements from the one resolved declaration/profile. Surface exposure derives
edge-band obligations; no author repeats edge lists.

- [ ] **Step 4: Implement ordinary `DetailSpecDoc` lowering**

Construct schema dataclasses directly; do not route the generated document back
through YAML. Include explicit bonds/contacts and physically expected overlaps,
modeled surveyed studs as existing site lumber, and installation screws aligned
to measured studs. Preserve a source map from each generated component id to its
pack declaration/rule.

- [ ] **Step 5: Run focused tests**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_cabinetry_lowering.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/packs/cabinetry/model.py src/packs/cabinetry/lowering.py tests/test_cabinetry_lowering.py
git commit -m "feat: lower frameless cabinets into DetailSpec"
```

### Task 4: Evidence-aware draft and release validation

**Files:**
- Create: `src/packs/cabinetry/validation.py`
- Create: `src/packs/cabinetry/evidence.py`
- Test: `tests/test_cabinetry_validation.py`

**Interfaces:**
- Produces: `EvidenceLevel`, `EvidenceRecord`, `CabinetFinding`, `CabinetReport`, and `validate_model(model, mode) -> CabinetReport`.
- `CabinetReport.release_ready` is true only when no required finding is FAIL or UNKNOWN.

- [ ] **Step 1: Write failing validation tests**

```python
def test_draft_retains_unknown_field_studs_without_certification_claim():
    report = validate_model(model_with_unverified_studs(), "draft")
    assert any(f.rule == "cabinetry.install.studs" and f.verdict == "UNKNOWN"
               for f in report.findings)
    assert "certified" not in report.summary.lower()

def test_release_blocks_unknown_studs_but_accepts_verified_fixture():
    assert not validate_model(model_with_unverified_studs(), "release").release_ready
    assert validate_model(build_fixture_model(), "release").release_ready
```

- [ ] **Step 2: Run and verify missing-validator failures**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_cabinetry_validation.py -q`
Expected: FAIL because validation/evidence modules do not exist.

- [ ] **Step 3: Implement the validation ladder**

Rules must cover dimensions/stock, door/reveal geometry, Blum compatibility and
quantity, shelf deflection under the declared KCMA-reference load, toe-base
support, anchor/stud resolution, countertop-support declaration, TSCA material
record, site readiness/acclimation, and commissioning. Record physical KCMA tests
as `not_performed`/UNKNOWN evidence rather than blocking a truthfully labeled
custom design unless the project requests a certification claim.

- [ ] **Step 4: Run focused tests**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_cabinetry_validation.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/packs/cabinetry/validation.py src/packs/cabinetry/evidence.py tests/test_cabinetry_validation.py
git commit -m "feat: validate cabinet release evidence"
```

### Task 5: Shop, assembly, and installation artifacts

**Files:**
- Create: `src/packs/cabinetry/artifacts.py`
- Test: `tests/test_cabinetry_artifacts.py`

**Interfaces:**
- Produces: `CabinetArtifacts`, `CutListItem`, `EdgeBandItem`, `HardwareItem`, `WorkStep`, and `build_artifacts(model, report)`.

- [ ] **Step 1: Write failing deterministic-artifact tests**

```python
def test_fixture_artifacts_cover_shop_and_field_work():
    a = build_fixture_artifacts()
    assert any(x.part_id.endswith("left_end") for x in a.cut_list)
    assert any(x.operation == "band" for x in a.edge_banding)
    assert [s.phase for s in a.installation_steps] == sorted(
        [s.phase for s in a.installation_steps])
    assert "field-verify stud" in " ".join(s.instruction.lower()
                                            for s in a.installation_steps)

def test_manifest_is_byte_deterministic():
    assert artifact_json(build_fixture_artifacts()) == artifact_json(build_fixture_artifacts())
```

- [ ] **Step 2: Run and verify missing-artifact failures**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_cabinetry_artifacts.py -q`
Expected: FAIL because artifacts module does not exist.

- [ ] **Step 3: Implement derived artifacts**

Generate cut list, edge-band map, Blum/shelf-pin/fastener schedule, fabrication
steps, carcass/door assembly steps, delivery state, wall survey, leveling,
shimming, cabinet-to-wall anchorage, filler/scribe, countertop, hinge adjustment,
and final commissioning instructions. Every row references stable ids and
provenance; ordering and JSON serialization are canonical.

- [ ] **Step 4: Run focused tests**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_cabinetry_artifacts.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/packs/cabinetry/artifacts.py tests/test_cabinetry_artifacts.py
git commit -m "feat: derive cabinet shop and installation artifacts"
```

### Task 6: Packed-project compilation and real vertical slice

**Files:**
- Modify: `src/packs/project.py`
- Modify: `src/packs/cabinetry/__init__.py`
- Create: `details/frameless_base_cabinet.project.yaml`
- Create: `tests/fixtures/cabinetry/frameless_base_cabinet.project.yaml`
- Create: `tests/test_cabinetry_e2e.py`

**Interfaces:**
- Produces: `PackedProject` with `.detail`, `.model`, `.lowered_doc`, `.report`, `.artifacts`, `.release_ready`, `.manifest()`, and delegation to the base detail.

- [ ] **Step 1: Write failing end-to-end and compatibility tests**

```python
def test_real_project_compiles_builds_and_releases():
    project = compile_project_file(FIXTURE)
    assembly = project.build()
    assert project.release_ready
    assert len(assembly.parts) == len(project.lowered_doc.components)
    assert project.manifest()["packs"] == {"cabinetry.frameless": "1.0.0"}

def test_ordinary_spec_is_identical_before_and_after_pack_compile():
    before = content_lines(compile_spec_file(PLATFORM))
    compile_project_file(FIXTURE)
    after = content_lines(compile_spec_file(PLATFORM))
    assert after == before
```

- [ ] **Step 2: Run and verify integration failures**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_cabinetry_e2e.py -q`
Expected: FAIL because packed compilation/wrapper/fixture are incomplete.

- [ ] **Step 3: Wire the pack pipeline and checked-in example**

The pack parser resolves the profile/catalogs, builds the model, validates it,
lowers to `DetailSpecDoc`, calls existing `compile_spec`, builds artifacts, and
returns `PackedProject`. `release` mode raises a `ProjectReleaseError` only when
the caller invokes `require_release()`; compilation itself preserves diagnostics.

- [ ] **Step 4: Run focused end-to-end tests**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_cabinetry_e2e.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/packs details/frameless_base_cabinet.project.yaml tests/fixtures/cabinetry tests/test_cabinetry_e2e.py
git commit -m "feat: compile real frameless cabinet project"
```

### Task 7: Documentation, packaging, STEPDOC integration, and full gate

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `pyproject.toml`
- Test: `tests/test_packaging.py`
- Test: `tests/test_cabinetry_e2e.py`

**Interfaces:**
- Final public API: `from detailgen.packs import compile_project_file`.

- [ ] **Step 1: Write failing packaging/API documentation tests**

```python
def test_wheel_configuration_lists_pack_packages():
    text = Path("pyproject.toml").read_text()
    assert '"detailgen.packs"' in text
    assert '"detailgen.packs.cabinetry"' in text
```

- [ ] **Step 2: Run the focused packaging test and verify failure**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_packaging.py -q`
Expected: FAIL until packaging/docs are complete.

- [ ] **Step 3: Document the packed project and explicit limits**

Add one concise README example and architecture notes to CLAUDE.md. State that
the profile is KCMA-informed, not certified; only the v1 vertical slice is
supported; release readiness does not substitute for engineering approval or
physical certification.

- [ ] **Step 4: Integrate completed STEPDOC master changes**

Run: `git merge master` after STEPDOC/CPG is merged there. Resolve no semantic
conflicts by changing STEPDOC-owned behavior; cabinetry remains additive.
Expected: clean merge or conflicts limited to independent documentation/package
lists.

- [ ] **Step 5: Run focused cabinetry tests**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_pack_project.py tests/test_cabinetry_schema.py tests/test_cabinetry_lowering.py tests/test_cabinetry_validation.py tests/test_cabinetry_artifacts.py tests/test_cabinetry_e2e.py -q`
Expected: PASS.

- [ ] **Step 6: Run the complete suite**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest -q -n auto`
Expected: all tests pass with only the repository's documented skips/xfail.

- [ ] **Step 7: Build the checked-in example and inspect its manifest**

Run: `PYTHONPATH=.shim /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -c 'from detailgen.packs import compile_project_file; p=compile_project_file("details/frameless_base_cabinet.project.yaml"); p.require_release(); print(p.manifest_json())'`
Expected: exit 0; manifest names `cabinetry.frameless` 1.0.0, profile/catalog
versions, `release_ready: true`, and no certification claim.

- [ ] **Step 8: Commit**

```bash
git add README.md CLAUDE.md pyproject.toml tests/test_packaging.py
git commit -m "docs: document cabinetry pack vertical slice"
```

## Self-review

- Spec coverage: explicit activation, scoped registry, base lowering, profiles,
  real hardware data, evidence ladder, draft/release, installation, artifacts,
  compatibility, and STEPDOC integration each have an owning task.
- Placeholder scan: no task contains deferred implementation markers; explicitly
  unsupported future cabinet variants are stated as scope, not implementation gaps.
- Type consistency: `ProjectDoc` flows through the registry into
  `FramelessCabinetryPack`; it produces `CabinetModel`, `DetailSpecDoc`,
  `CabinetReport`, and `CabinetArtifacts`; `PackedProject` owns those exact values.
