# Connector-Aware Explode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the shared interactive viewer open on the completed assembly and visibly withdraw embedded connectors along their declared axes whenever Explode is used.

**Architecture:** Preserve the existing authored-vector and contact-normal precedence, then add the component's existing `axis` datum as the next automatic direction source before radial fallback. In the browser state machine, initialize instruction-aware viewers to their final panel and treat nonzero Explode as a temporary all-parts visibility override that restores the selected Assembly panel at zero.

**Tech Stack:** Python 3, CadQuery component frames/datums, pytest, vanilla JavaScript, three.js viewer payloads, deterministic self-contained HTML generation.

## Global Constraints

- No caddy-specific explode vectors, component-type checks, or part-name rules.
- Existing authored explode vectors remain byte-for-byte authoritative.
- Contact-derived bearing and through-hole directions retain precedence over datum axes.
- Existing/context bodies remain pinned at zero.
- Explode greater than zero reveals every scheduled part without mutating the selected Assembly panel.
- Explode zero restores the selected Assembly panel's visibility.
- Instruction-aware viewers initialize to the final panel; viewers without instruction metadata remain unchanged.
- The caddy geometry, design selection, model fingerprint, instructions, and delivery confirmation do not change.
- No camera animation, color override, collision-free disassembly solver, or new component API.
- Use the existing named `axis` datum; malformed directions fall back without blocking delivery.
- Run targeted tests and the complete repository suite before push.
- Do not merge to `main` in this increment.

## File Map

- `src/rendering/web_viewer/explode.py` — choose deterministic semantic explode directions.
- `src/rendering/web_viewer/viewer.js` — coordinate Assembly visibility with Explode state.
- `tests/test_viewer_explode_and_fab.py` — prove connector-axis behavior and retained precedence.
- `tests/test_viewer_instruction_panels.py` — pin completed-default and temporary reveal semantics.
- `outputs/armchair_caddy/armchair_caddy_build_document.html` — regenerated certified technical document; ignored generated artifact, not committed.
- `outputs/armchair_caddy/armchair_caddy_assembly_manual.html` — regenerated certified manual; ignored generated artifact, not committed.

---

### Task 1: Derive connector explode vectors from existing axis datums

**Files:**
- Modify: `src/rendering/web_viewer/explode.py:1-166`
- Test: `tests/test_viewer_explode_and_fab.py:88-168`

**Interfaces:**
- Consumes: `Placed.component.datums["axis"] -> Frame`, `Frame.z_axis -> tuple[float, float, float]`, and `Placed.world_frame.transform_direction(direction)`.
- Produces: `_datum_axis_direction(placed, radial) -> tuple[float, float, float] | None`, consumed only by `derive_explode_vectors()` between contact-normal and radial fallback.
- Preserves: `derive_explode_vectors(assembly, contacts=None) -> dict[str, tuple[float, float, float]]`.

- [ ] **Step 1: Write the failing caddy axis-alignment regression**

Add `import math` with the standard-library imports, then add this test beside the existing caddy context-pin test in `tests/test_viewer_explode_and_fab.py`:

```python
def test_caddy_corner_keys_explode_along_their_declared_axes():
    caddy = compile_spec_file(DETAILS / "armchair_caddy.spec.yaml")
    caddy.validate()
    payload = build_viewer_payload(caddy)

    keys = [
        part for part in caddy.assembly.parts
        if part.reader_name == "Corner key"
    ]
    assert len(keys) == 4
    for part in keys:
        vector = payload["parts"][part.name]["explode"]
        local_axis = part.component.datum("axis").z_axis
        world_axis = part.world_frame.transform_direction(local_axis)
        cross = (
            vector[1] * world_axis[2] - vector[2] * world_axis[1],
            vector[2] * world_axis[0] - vector[0] * world_axis[2],
            vector[0] * world_axis[1] - vector[1] * world_axis[0],
        )

        assert math.sqrt(sum(value * value for value in cross)) < 1e-6
        assert sum(vector[index] * world_axis[index] for index in range(3)) > 0
```

- [ ] **Step 2: Run the regression to prove the radial fallback fails**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_viewer_explode_and_fab.py::test_caddy_corner_keys_explode_along_their_declared_axes \
  -q
```

Expected: FAIL at the cross-product assertion because current key vectors are only about 37 percent aligned with the declared axes.

- [ ] **Step 3: Add a non-finite direction guard test**

Import `_unit` from `detailgen.rendering.web_viewer.explode` and add:

```python
def test_explode_unit_rejects_nonfinite_directions():
    assert _unit((math.nan, 0.0, 0.0)) is None
    assert _unit((math.inf, 0.0, 0.0)) is None
```

- [ ] **Step 4: Run the guard test to prove malformed directions currently leak**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_viewer_explode_and_fab.py::test_explode_unit_rejects_nonfinite_directions \
  -q
```

Expected: FAIL because `_unit()` currently returns non-finite components.

- [ ] **Step 5: Implement finite-vector validation and datum-axis resolution**

Update `_unit()` and add `_datum_axis_direction()` in `src/rendering/web_viewer/explode.py`:

```python
def _unit(v):
    if not all(math.isfinite(c) for c in v):
        return None
    n = math.sqrt(sum(c * c for c in v))
    if n < _EPS:
        return None
    return tuple(c / n for c in v)


def _datum_axis_direction(placed, radial):
    datum = placed.component.datums.get("axis")
    if datum is None:
        return None
    direction = _unit(
        placed.world_frame.transform_direction(datum.z_axis)
    )
    if direction is None:
        return None
    projection = sum(
        radial[index] * direction[index] for index in range(3)
    )
    if projection < -_EPS:
        direction = tuple(-value for value in direction)
    return direction
```

Change the per-part precedence in `derive_explode_vectors()`:

```python
contact_direction = _sum_unit(normals[name])
direction = (
    contact_direction
    or _datum_axis_direction(p, radial)
    or _unit(radial)
    or (0.0, 0.0, 1.0)
)
```

Update the module docstring so the deterministic rule explicitly states `contact normal -> named axis datum -> radial -> +Z`, with authored detail vectors still bypassing the derivation in `_explode_for()`.

- [ ] **Step 6: Run connector and existing explode tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_viewer_explode_and_fab.py \
  tests/test_viewer_data.py \
  -q
```

Expected: PASS, including authored-vector precedence, pinned context, platform contact directions, deterministic output, and the new caddy key alignment.

- [ ] **Step 7: Commit the semantic direction change**

```bash
git add src/rendering/web_viewer/explode.py tests/test_viewer_explode_and_fab.py
git diff --cached --check
git commit -m "fix: explode connectors along declared axes"
```

---

### Task 2: Make Explode reveal all parts while preserving Assembly state

**Files:**
- Modify: `src/rendering/web_viewer/viewer.js:360-625`
- Test: `tests/test_viewer_instruction_panels.py:60-105`

**Interfaces:**
- Consumes: existing per-part `first_panel`, the current Assembly slider value, and the Explode slider value.
- Produces: `applyPartVisibility()` as the single visibility writer for instruction-aware viewer nodes.
- Preserves: viewers without `instruction_panels`, existing hover/pin visibility checks, and the current explode translation formula.

- [ ] **Step 1: Write failing source-contract tests for the new state machine**

Add the following tests to `tests/test_viewer_instruction_panels.py`:

```python
def test_instruction_viewer_opens_on_completed_assembly():
    js = viewer_js()

    assert (
        'assembly.value = String(payload.instruction_panels.length);'
        in js
    )
    assert "applyAssemblyPanel(assembly.value);" in js
    assert "applyAssemblyPanel(1);" not in js


def test_explode_temporarily_reveals_future_parts():
    js = viewer_js()

    assert "var explodeAmount = 0;" in js
    assert "function applyPartVisibility()" in js
    assert "var revealAll = explodeAmount > 0;" in js
    assert "var visible = revealAll || first_panel <= currentPanel;" in js
    assert "explodeAmount = parseFloat(explode.value) || 0;" in js
    assert "applyPartVisibility();" in js
```

Extend the existing panel-input test to retain its assertion that changing Assembly never changes `explode.value`.

- [ ] **Step 2: Run the new tests to verify current behavior fails**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_viewer_instruction_panels.py::test_instruction_viewer_opens_on_completed_assembly \
  tests/test_viewer_instruction_panels.py::test_explode_temporarily_reveals_future_parts \
  -q
```

Expected: both FAIL because the viewer initializes to Panel 1 and has no shared visibility override.

- [ ] **Step 3: Implement one shared visibility state**

In `src/rendering/web_viewer/viewer.js`, add `explodeAmount` beside the current panel state:

```javascript
var currentPanel = 1;
var explodeAmount = 0;
var arrivalNames = {};
```

Remove the redundant `first_panel > currentPanel` rejection from `isPartVisible()` so actual scene-node visibility remains authoritative:

```javascript
function isPartVisible(partName) {
  var row = payload.parts[partName];
  var entry = partNodes[partName];
  if (!row || !entry) return false;
  return entry.tops.some(objectIsVisible);
}
```

Initialize the Assembly control to the final panel:

```javascript
assembly.value = String(payload.instruction_panels.length);
```

Add the single visibility writer before `applyExplode()`:

```javascript
function applyPartVisibility() {
  if (!assembly) return;
  var revealAll = explodeAmount > 0;
  Object.keys(partNodes).forEach(function (name) {
    var entry = partNodes[name];
    var first_panel = payload.parts[name].first_panel;
    var visible = revealAll || first_panel <= currentPanel;
    entry.tops.forEach(function (node) { node.visible = visible; });
  });
}
```

At the start of `applyExplode()`, set the shared state and apply visibility before translating nodes:

```javascript
explodeAmount = parseFloat(explode.value) || 0;
applyPartVisibility();
var t = explodeAmount;
```

Replace the visibility-setting loop inside `applyAssemblyPanel()` with:

```javascript
applyPartVisibility();
Object.keys(partNodes).forEach(function (name) {
  refreshPartEmissive(name);
});
```

Initialize using the authored control value:

```javascript
applyAssemblyPanel(assembly.value);
```

Update the toolbar hint to:

```javascript
hint.textContent = "Drag to orbit · Explode reveals all parts · hover a part";
```

- [ ] **Step 4: Run viewer state and interaction-source tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_viewer_instruction_panels.py \
  tests/test_viewer_data.py \
  -q
```

Expected: PASS. The no-instruction payload still omits panel metadata, Assembly changes leave Explode untouched, and hidden nodes cannot be picked when Explode is zero.

- [ ] **Step 5: Commit the viewer interaction change**

```bash
git add src/rendering/web_viewer/viewer.js tests/test_viewer_instruction_panels.py
git diff --cached --check
git commit -m "fix: reveal embedded parts in exploded views"
```

---

### Task 3: Regenerate the caddy and verify the platform end to end

**Files:**
- Regenerate: `outputs/armchair_caddy/armchair_caddy_build_document.html`
- Regenerate: `outputs/armchair_caddy/armchair_caddy_assembly_manual.html`
- Regenerate: `outputs/armchair_caddy/instruction_panels/*.png`
- Verify tracked files from Tasks 1-2; no new production file is expected.

**Interfaces:**
- Consumes: the approved and delivery-confirmed caddy DetailSpec plus the shared viewer platform changes.
- Produces: certified local review documents whose embedded payload and viewer source exhibit the new behavior.

- [ ] **Step 1: Run focused platform and caddy verification**

```bash
.venv/bin/python -m pytest \
  tests/test_viewer_explode_and_fab.py \
  tests/test_viewer_instruction_panels.py \
  tests/test_viewer_data.py \
  tests/test_caddy_design_review.py \
  tests/test_caddy_reinforced_miter.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Regenerate the certified document pair**

```bash
.venv/bin/python scripts/caddy_documents.py
```

Expected JSON:

- `"preview": false`;
- `"panel_count": 4`;
- technical and manual paths under `outputs/armchair_caddy/`;
- four instruction-panel asset keys.

- [ ] **Step 3: Audit the generated viewer payload and markings**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("outputs/armchair_caddy/armchair_caddy_build_document.html")
html = path.read_text()
assert "PREVIEW — NOT APPROVED FOR DELIVERY" not in html
payload_text = html.split(
    '<script type="application/json" id="detail-data-armchair_caddy">', 1
)[1].split("</script>", 1)[0]
payload = json.loads(payload_text)
keys = [
    row for row in payload["parts"].values()
    if row["reader_name"] == "Corner key"
]
assert len(keys) == 4
assert all(any(abs(value) > 1e-6 for value in row["explode"]) for row in keys)
assert 'assembly.value = String(payload.instruction_panels.length);' in html
assert "var revealAll = explodeAmount > 0;" in html
print("certified viewer audit: PASS")
PY
```

Expected: `certified viewer audit: PASS`.

- [ ] **Step 4: Run the complete repository suite**

```bash
.venv/bin/python -m pytest -q -n 4
```

Expected: all tests pass, with only the repository's documented skips and expected failure.

- [ ] **Step 5: Run final diff and gate checks**

```bash
.venv/bin/python -m detailgen.design_review gate \
  details/armchair_caddy.spec.yaml --stage delivery
git diff --check
git status --short
```

Expected: the delivery gate exits zero, `git diff --check` is silent, and the worktree contains only intended tracked changes or is clean after the task commits.

- [ ] **Step 6: Push the verified feature branch without merging**

```bash
git push
git rev-parse HEAD
git rev-parse @{upstream}
```

Expected: local and upstream SHAs match on `codex/precedent-first-design-selection`.
