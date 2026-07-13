# Reader-Facing Part Names Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every builder-facing part surface one canonical human name while preserving the existing unique machine identity used by geometry, validation, exports, caches, and evidence.

**Architecture:** Add optional `reader_name` authoring to `ComponentSpec` and carry it only on `Placed`; never put it on `Component` and never use it as a dictionary/export key. A shared `part_labels()` projection computes the primary name and deterministic `index/count` once from assembly order. Viewer hover, cut plans, build-sequence placement lines, inspector headings, and the future instruction-panel renderer consume that projection; raw technical contract disclosures may retain machine names.

**Tech Stack:** Python 3 dataclasses, strict YAML loader/serializer, pytest, vanilla JavaScript/CSS, CadQuery/OCCT geometry-hash guards.

## Global Constraints

- `Placed.name` remains unique and remains the GLB/STEP node name, validation/evidence subject, explode/color-map key, and viewer payload dictionary key.
- `reader_name` is presentation-only; changing it must not change geometry hashes, component cache keys, findings, revision geometry classification, or GLB node keys.
- Duplicate `reader_name` values are valid and required for mirrored/repeated parts.
- Omitted `reader_name` falls back exactly to `Placed.name`; every existing spec remains valid and round-trips without churn.
- Never strip `+X`, `-X`, ordinals, or other suffixes heuristically. Human names are explicit authored content.
- Instance numbering is computed once, in assembly declaration order, and reused by every reader surface.
- Builder-facing caddy labels are title-cased semantic nouns: `Sofa arm`, `Top board`, `Side board`, `Registration rail`, and `Rail-to-side screw`.
- Raw install-contract and validation appendices may retain machine names because they are technical identity disclosures, not builder captions.
- Work test-first: every production behavior must first be observed failing for the intended reason.

## Test scaffolding (real repository APIs)

`tests/test_reader_names.py` owns its helpers instead of relying on invented
cross-test fixtures:

```python
from dataclasses import replace
from pathlib import Path

from detailgen.core.buildinfo import geometry_hash
from detailgen.spec import (
    compile_spec, compile_spec_file, dump_yaml, load_spec_file, load_spec_text,
)

ROOT = Path(__file__).resolve().parents[1]
CADDY = ROOT / "details" / "armchair_caddy.spec.yaml"

def build_text(text: str):
    detail = compile_spec(load_spec_text(text))
    detail.build()
    return detail

def compile_caddy():
    detail = compile_spec_file(CADDY)
    detail.validate()
    return detail

def finding_signature(detail):
    return tuple(
        (f.verdict, f.check, f.subject, f.detail)
        for f in detail.validate().findings
    )

def solid_hashes(detail):
    return tuple(
        (p.name, geometry_hash(p.world_solid()))
        for p in detail.assembly.parts
    )
```

Use literal minimal YAML strings with `load_spec_text()` for loader tests,
`dump_yaml()` followed by `load_spec_text()` for round trips, and
`dataclasses.replace()` on the loaded `DetailSpecDoc`/`ComponentSpec` values for
the presentation-only mutation test. Reuse the GLB parsing pattern already in
`tests/test_viewer_data.py`; do not import private helpers from another test
module.

**Execution dependency:** run Tasks 1 → 2 → 4 → 3 → 5. Task 2 proves the
generic projection with the two-rail fixture. Task 4 then authors the real
caddy vocabulary. Task 3 deliberately follows it because its cross-document
parity checks compile the caddy from disk.

---

### Task 1: Schema, loader, serializer, and placement plumbing

**Files:**
- Modify: `src/spec/schema.py`
- Modify: `src/spec/loader.py`
- Modify: `src/spec/serialize.py`
- Modify: `src/spec/compiler.py`
- Modify: `src/assemblies/assembly.py`
- Test: `tests/test_reader_names.py`
- Test: `tests/test_spec.py`

**Interfaces:**
- Produces: `ComponentSpec.reader_name: str = ""`.
- Produces: `Placed.reader_name: str = ""`, where `placed.reader_name or placed.name` is the compatibility fallback.
- Preserves: `Placed.name`, `Placed.id`, and every placement/export key.

- [x] **Step 1: Write failing schema and placement tests**

```python
def test_reader_name_loads_and_duplicate_values_are_allowed():
    doc = load_spec_text(TWO_RAILS_YAML)
    assert [c.reader_name for c in doc.components] == [
        "Registration rail", "Registration rail"]


@pytest.mark.parametrize("bad", ['""', '"   "', "3", "null"])
def test_reader_name_rejects_empty_or_non_string_values(bad):
    text = ONE_RAIL_YAML.replace("READER_VALUE", bad)
    with pytest.raises(SpecSchemaError, match="reader_name.*non-empty"):
        load_spec_text(text)


def test_compiler_interpolates_reader_name_without_changing_machine_name():
    detail = build_text(REPEATED_RAILS_YAML)
    rails = [p for p in detail.assembly.parts if p.name.startswith("rail ")]
    assert [p.name for p in rails] == ["rail +X", "rail -X"]
    assert [p.reader_name for p in rails] == [
        "Registration rail", "Registration rail"]
```

- [x] **Step 2: Run the tests and verify RED**

Run:
`PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_reader_names.py tests/test_spec.py`

Expected: FAIL because `reader_name` is rejected as an unknown key or absent from `ComponentSpec`/`Placed`.

- [x] **Step 3: Add the minimal typed plumbing**

Add `reader_name: str = ""` to `ComponentSpec` and `Placed`. Teach `_build_component` to accept only a non-empty string when authored; teach `_component_to_dict` to emit it only when non-empty. In `_place_component`, interpolate the field through repeats and assign it to the returned `Placed` without changing `Component.name`.

```python
reader_name = ""
if cspec.reader_name:
    reader_name = _interp(
        cspec.reader_name, bindings, f"component {cid!r} reader_name")
placed = self._apply_placement(...)
placed.reader_name = reader_name
```

- [x] **Step 4: Add round-trip and fallback assertions**

```python
def test_reader_name_round_trip_and_omission_fallback():
    authored = load_spec_text(ONE_RAIL_YAML.replace(
        "READER_VALUE", '"Registration rail"'))
    assert load_spec_text(dump_yaml(authored)) == authored
    legacy = build_text(LEGACY_RAIL_YAML)
    part = legacy.assembly.parts[0]
    assert part.reader_name == ""
    assert part.name == "legacy machine name"
```

- [x] **Step 5: Run GREEN tests and commit**

Run:
`PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_reader_names.py tests/test_spec.py tests/test_spec_repeat.py`

Expected: all selected tests pass.

Commit: `stepdoc: add reader-facing part names`

---

### Task 2: One shared part-label projection and viewer hover hierarchy

**Files:**
- Create: `src/rendering/part_labels.py`
- Modify: `src/rendering/web_viewer/__init__.py`
- Modify: `src/rendering/web_viewer/viewer.js`
- Modify: `src/rendering/web_viewer/viewer.css`
- Test: `tests/test_reader_names.py`
- Test: `tests/test_viewer_data.py`

**Interfaces:**
- Produces: `PartLabel(machine_name, reader_name, item, index, count)`.
- Produces: `part_labels(parts) -> dict[str, PartLabel]`, keyed by `Placed.id`.
- Viewer payload remains keyed by `Placed.name`; each row gains `reader_name`, `instance_index`, and `instance_count`.

- [x] **Step 1: Write failing projection and payload tests**

```python
def test_part_labels_number_duplicate_reader_names_once():
    detail = build_text(TWO_RAILS_YAML)
    labels = part_labels(detail.assembly.parts)
    rails = [labels[p.id] for p in detail.assembly.parts
             if p.reader_name == "Registration rail"]
    assert [(x.reader_name, x.index, x.count) for x in rails] == [
        ("Registration rail", 1, 2),
        ("Registration rail", 2, 2),
    ]


def test_viewer_keeps_machine_keys_and_adds_reader_fields():
    payload = build_viewer_payload(build_text(TWO_RAILS_YAML))
    assert "registration rail +X" in payload["parts"]
    row = payload["parts"]["registration rail +X"]
    assert row["reader_name"] == "Registration rail"
    assert (row["instance_index"], row["instance_count"]) == (1, 2)
```

- [x] **Step 2: Verify RED**

Run:
`PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_reader_names.py tests/test_viewer_data.py`

Expected: FAIL because `part_labels` and the new payload fields do not exist.

- [x] **Step 3: Implement the immutable shared projection**

```python
@dataclass(frozen=True)
class PartLabel:
    machine_name: str
    reader_name: str
    item: str
    index: int
    count: int


def part_labels(parts):
    parts = tuple(parts)
    names = tuple((p.reader_name or p.name) for p in parts)
    totals = Counter(names)
    seen = Counter()
    result = {}
    for placed, name in zip(parts, names):
        seen[name] += 1
        result[placed.id] = PartLabel(
            placed.name, name, placed.component.bom_label(),
            seen[name], totals[name])
    return result
```

- [x] **Step 4: Render the two-line hover contract**

Keep lookup by machine name. Change `fillTooltip` so the header is `p.reader_name || partName`, and the subheading is either `p.item` or `${p.instance_index} of ${p.instance_count} · ${p.item}`. Add CSS classes for the primary name and secondary stock line; do not concatenate them into one opaque string.

- [x] **Step 5: Add a JavaScript-source contract test**

```python
def test_tooltip_uses_reader_name_but_not_as_lookup_key():
    js = viewer_js()
    assert "p.reader_name || partName" in js
    assert "instance_index" in js and "instance_count" in js
    assert "payload.parts[partName]" in js
```

- [x] **Step 6: Run GREEN tests and commit**

Run:
`PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_reader_names.py tests/test_viewer_data.py tests/test_viewer_explode_and_fab.py`

Expected: all selected tests pass and GLB/payload key parity remains green.

Commit: `viewer: show canonical reader-facing part names`

---

### Task 3: Route model-driven reader surfaces through the shared projection

**Files:**
- Modify: `src/validation/build_sequence.py`
- Modify: `scripts/consolidated_report.py`
- Modify: `scripts/single_detail_report.py`
- Modify: `src/rendering/inspector.py`
- Modify: `src/rendering/inspector_assets/inspector.js`
- Test: `tests/test_reader_names.py`
- Test: `tests/test_cpg_core.py`
- Test: `tests/test_inspector_payload.py`

**Interfaces:**
- Consumes: `part_labels(detail.assembly.parts)` from Task 2.
- Preserves: raw connection labels and install-contract `describe()` lines in technical disclosures.
- Produces: canonical names in cut-plan part rows, build-sequence `place` and
  unordered-part lines, existing-context BOM/hover rows, and inspector headings.

- [x] **Step 1: Write failing cross-surface parity tests**

```python
def test_caddy_reader_surfaces_share_the_same_rail_label(tmp_path):
    detail = compile_caddy()
    sequence, _loose = build_sequence_model(detail)
    placed_names = [name for step in sequence for name, _bom, _fab in step["places"]]
    assert placed_names.count("Registration rail") == 2
    import single_detail_report as SDR
    out = tmp_path / "caddy.html"
    SDR.build_document(out, spec_path=CADDY, preview=False)
    html = out.read_text()
    cut_plan = html.split("Consolidated stock & cut plan", 1)[1]
    assert cut_plan.count("Registration rail") >= 2
    payload = build_inspector_payload(detail)
    assert [p["reader_name"] for p in payload["parts"]].count(
        "Registration rail") == 2
```

- [x] **Step 2: Verify RED**

Run:
`PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_reader_names.py tests/test_cpg_core.py tests/test_inspector_payload.py`

Expected: FAIL because these surfaces still read `Placed.name`.

- [x] **Step 3: Replace independent name reads with the shared projection**

Compute labels once per detail/assembly. In `build_sequence_model`, keep the
existing tuple shape but place `label.reader_name` in the first slot and map
`loose_names` through the same projection. In cut-plan maps and inspector
payloads, keep machine ids/keys unchanged and add/read the canonical display
field. `PartInspection.name`, the `parts` dictionary key, `part_order`,
`id_to_name`, graph queries, and neighbor references remain machine identity;
add `reader_name` for the inspector header and render
`part.reader_name || part.name`. In `single_detail_report.py`, use the same
projection when relabeling existing-context rows so hover/BOM says
`Sofa arm (existing)`, not the primitive or lowercase machine identity.

- [x] **Step 4: Pin the technical-appendix boundary**

```python
def test_machine_connection_labels_remain_in_raw_contract_appendix(tmp_path):
    import single_detail_report as SDR
    out = tmp_path / "caddy.html"
    SDR.build_document(out, spec_path=CADDY, preview=False)
    html = out.read_text()
    appendix = html.split("install-disclosure", 1)[1].split("</section>", 1)[0]
    assert "rail +X" in appendix
    sequence = html.split("build-sequence", 1)[1].split("</section>", 1)[0]
    assert "place Registration rail" in sequence
    assert "place registration rail +X" not in sequence
```

- [x] **Step 5: Run GREEN tests and commit**

Run:
`PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_reader_names.py tests/test_cpg_core.py tests/test_inspector_payload.py tests/test_armchair_caddy_e2e.py`

Expected: all selected tests pass.

Commit: `docs: unify model-driven part labels`

---

### Task 4: Author the caddy vocabulary and prove presentation-only behavior

**Files:**
- Modify: `details/armchair_caddy.spec.yaml`
- Modify: `scripts/render_caddy_views.py`
- Modify: `tests/test_armchair_caddy_e2e.py`
- Modify: `tests/test_reader_names.py`

**Interfaces:**
- Consumes: `reader_name` schema and shared labels from Tasks 1–2.
- Produces: semantic caddy names for context, wood parts, and screws.

- [x] **Step 1: Write failing caddy authoring and invariant tests**

```python
def test_caddy_authors_the_closed_reader_vocabulary():
    detail = compile_caddy()
    by_machine = {p.name: p.reader_name for p in detail.assembly.parts}
    assert by_machine["sofa arm"] == "Sofa arm"
    assert by_machine["top board"] == "Top board"
    assert {v for k, v in by_machine.items() if k.startswith("side board ")} == {
        "Side board"}
    assert {v for k, v in by_machine.items()
            if k.startswith("registration rail ")} == {"Registration rail"}
    assert {v for k, v in by_machine.items()
            if k.startswith("rail-side screw ")} == {"Rail-to-side screw"}


def test_reader_name_only_edit_is_geometry_and_truth_inert(tmp_path):
    original = compile_caddy()
    doc = load_spec_file(CADDY)
    components = tuple(
        replace(c, reader_name="Registration cleat")
        if getattr(c, "id", None) == "cleat_pos" else c
        for c in doc.components
    )
    renamed = compile_spec(replace(doc, components=components))
    assert solid_hashes(original) == solid_hashes(renamed)
    assert finding_signature(original) == finding_signature(renamed)
    assert [p.name for p in original.assembly.parts] == [
        p.name for p in renamed.assembly.parts]
```

- [x] **Step 2: Verify RED**

Run:
`PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_reader_names.py tests/test_armchair_caddy_e2e.py`

Expected: FAIL because the caddy has not authored `reader_name` values.

- [x] **Step 3: Add explicit caddy `reader_name` fields**

Author the exact vocabulary from Global Constraints on all 14 caddy components. Do not rename the existing `name` or `id` values.

- [x] **Step 4: Remove coordinate vocabulary from static builder captions**

Replace `+X/-X` only in manually authored raster titles/captions that builders see. Preserve coordinate-bearing variable names and geometry logic. Re-render only the caddy presentation PNGs whose text changed; record that geometry hash remains unchanged while presentation hashes move intentionally.

In this task, pin the source captions and leave ignored/generated PNG output to
Task 5. Task 5 must force `scripts/render_caddy_views.py` before composing the
HTML; `_ensure_views()` is existence-only and may otherwise retain stale
caption pixels from an earlier run.

- [x] **Step 5: Run GREEN tests and commit**

Run:
`PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_reader_names.py tests/test_armchair_caddy_e2e.py tests/test_viewer_data.py tests/test_inspector_payload.py`

Expected: all selected tests pass.

Commit: `caddy: author canonical builder-facing part names`

---

### Task 5: Adversarial review, document regeneration, and merge gate

**Files:**
- Create: `.superpowers/sdd/review-reader-names.md`
- Create: `.superpowers/sdd/task-reader-names-report.md`
- Modify: `.superpowers/sdd/progress.md`
- Regenerate: `outputs/armchair_caddy/armchair_caddy_build_document.html`

**Interfaces:**
- Consumes: the complete reader-name implementation.
- Produces: reviewed base-language naming substrate for the later cure and instruction-manual increments.

- [ ] **Step 1: Run the focused acceptance set**

Run:
`PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_reader_names.py tests/test_viewer_data.py tests/test_viewer_explode_and_fab.py tests/test_inspector_payload.py tests/test_cpg_core.py tests/test_armchair_caddy_e2e.py tests/test_spec.py tests/test_spec_repeat.py`

Expected: all selected tests pass.

- [ ] **Step 2: Run a fresh adversarial review**

The reviewer must attempt duplicate-reader-name payload collisions, GLB/payload key drift, geometry/cache fingerprint contamination, inconsistent instance numbering across surfaces, repeat interpolation failures, HTML escaping, and accidental stripping of coordinate suffixes from machine identities. Fix every Critical or Important finding and re-run its covering tests.

- [ ] **Step 3: Regenerate and inspect the caddy document**

Run:
`PYTHONPATH="$PWD/.shim" ../../.venv/bin/python scripts/single_detail_report.py details/armchair_caddy.spec.yaml`

Verify hover primary/secondary text, builder-facing cut-plan/build-sequence parity, static labels, no browser console error, print layout, and unchanged geometry hash.

- [ ] **Step 4: Run the binding full gate**

Run:
`PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -n auto -q`

Expected: zero failures; read and record the exact pass/skip/xfail counts before merge.

- [ ] **Step 5: Commit reports, merge separately, push, and redeliver**

Record the review and gate in the ledger. Verify `origin/main` immediately before the merge. Merge in a separate command, push `main`, regenerate from a clean merged tree, and deliver the updated caddy technical HTML to the vault and `~/Downloads/Build Documents/` without touching unrelated dirty files.
