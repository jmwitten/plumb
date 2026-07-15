# Reusable Physical Vocabulary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Use
> superpowers:test-driven-development for every behavior change and
> superpowers:verification-before-completion before claiming success. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a new solid-wood material, ordinary wood screw, or pivot/latch
service panel a parameterized DetailSpec choice instead of a new CadQuery and
class-name-plumbing project, while preserving every existing public type.

**Architecture:** Extract a registered `FabricatedPanel` core beneath cedar and
hardwood compatibility wrappers; carry registered RGBA through the render
manifest; add a closed component-capability protocol and an envelope-first
`WoodScrew`; generalize service-panel screw semantics behind a closed mode
parameter; and verify the birdhouse through the existing semantic detail-gate
work. Existing types and specs remain valid. Only the birdhouse's deliberate
migration to envelope screws changes its geometry.

**Tech Stack:** Python 3.12, pytest 9, pytest-xdist 3.8, CadQuery 2.8, OCCT,
PyYAML, Blender's standalone Python render script.

**Design reference:**
`docs/superpowers/specs/2026-07-15-reusable-physical-vocabulary-design.md`

## Global Constraints

- Work in a new isolated worktree. Do not edit or merge an active dirty
  birdhouse or caddy-performance worktree.
- Preserve imports and registry keys for `HardwoodPanel`, `CedarPanel`,
  `ExteriorWoodScrew`, `PivotScrewed`, and `ServiceLatchScrewed`.
- Do not add material strength, density, movement, or durability numbers. This
  increment models identity/color/service assumptions only.
- Do not change the DetailSpec schema. Existing component/connection `params`
  already lower to constructor keyword arguments.
- Do not fold `PlywoodPanel` into the new panel type.
- Do not replace every class-name hardware guard. Migrate only installation
  fastener detection, `CleatScrewed`, `ButtScrewed`, and service-panel
  retention.
- Do not persist pytest verdicts or weaken required semantic contracts.
- Reuse the `--detail-gate` plugin from `codex/caddy-test-performance` after
  that branch is clean and accepted. Do not implement a competing selector.
- Use fresh cache roots for performance measurements. Do not report a warm
  persistent-cache hit as a faster cold authoring loop.
- Every behavior task begins with a failing or characterization test and ends
  with a focused commit.
- Run the full repository suite once, after all shared changes are integrated.

---

### Task 0: Create a clean integration worktree and capture baselines

**Files:**
- Read:
  `docs/superpowers/specs/2026-07-15-reusable-physical-vocabulary-design.md`
- Read:
  `docs/superpowers/plans/2026-07-15-reusable-physical-vocabulary.md`
- No source changes.

**Integration inputs:**
- Plan branch: `codex/plumb-reusable-vocabulary-plan` at `bc41e33` or later.
- Birdhouse branch: `codex/birdhouse-plumb` at `a769f2a` or later, after its
  report/component edits are committed and its worktree is clean.
- Detail-gate branch: `codex/caddy-test-performance` at `b27a5a7` or later,
  after its progress-ledger edit is resolved and its worktree is clean.

- [ ] **Step 1: Verify the three inputs without changing them**

Run from the main repository:

~~~bash
git status --short --branch
git log -1 --oneline codex/plumb-reusable-vocabulary-plan
git log -1 --oneline codex/birdhouse-plumb
git log -1 --oneline codex/caddy-test-performance
git -C .worktrees/birdhouse-plumb status --short --branch
git -C .worktrees/caddy-test-performance status --short --branch
~~~

Expected: the plan branch contains this plan. Do not merge the other two
branches while their worktrees show modifications. Tasks 1–5 may start from the
plan branch before those branches finish; Task 6 may not.

- [ ] **Step 2: Create the implementation worktree**

~~~bash
git worktree add \
  .worktrees/plumb-reusable-vocabulary \
  -b codex/plumb-reusable-vocabulary \
  codex/plumb-reusable-vocabulary-plan
cd .worktrees/plumb-reusable-vocabulary
~~~

Expected: `git status --short --branch` shows a clean
`codex/plumb-reusable-vocabulary` branch.

- [ ] **Step 3: Install the pinned development environment**

~~~bash
uv venv --python 3.12
uv pip install -e '.[dev]' -c constraints.txt
~~~

Expected: installation exits zero and `.venv/bin/python -V` reports Python
3.12.

- [ ] **Step 4: Reproduce the focused extension baseline**

~~~bash
.venv/bin/python -m pytest \
  tests/test_cedar_components.py \
  tests/test_blender_materials.py \
  tests/test_exterior_wood_screw.py \
  tests/test_service_panel_connections.py \
  -q --durations=20
~~~

Expected on the plan base: `19 passed`. The recorded clean reference was 72.88
seconds. Save the new machine-local time; do not replace the reference with a
warm rerun.

- [ ] **Step 5: Reproduce the compatibility geometry fingerprints**

Run with the persistent cache disabled:

~~~bash
DETAILGEN_NO_CACHE=1 .venv/bin/python -c '
from detailgen.components import CedarPanel, HardwoodPanel, ExteriorWoodScrew
from detailgen.core.buildinfo import geometry_hash
from detailgen.core.units import IN
c = CedarPanel(8*IN, 5.5*IN, .75*IN, ease_radius=1/16*IN)
c.apply_feature_cut(4*IN, 2.75*IN, .5*IN, noun="probe", step_kind="bore", provenance="probe")
h = HardwoodPanel(8*IN, 5.5*IN, .75*IN, miter_ends=("near", "far"))
h.apply_feature_cut(4*IN, 2.75*IN, .5*IN, noun="probe", step_kind="bore", provenance="probe")
s = ExteriorWoodScrew(.164*IN, 1.5*IN)
print("cedar", geometry_hash(c.solid))
print("hardwood", geometry_hash(h.solid))
print("screw", geometry_hash(s.solid))
'
~~~

Expected:

~~~text
cedar 0cf648eaa0442878c6ceb3b13de6eb26f4eb72d7092c9561473ce1bc3747b1f2
hardwood cd42ca17af15e6cd8618f119faf31deef61836ec583580f977cda32106d7ced4
screw 9fea70e8c0facd592ff729f0e443d54dde64257d8bfe80f229ba3d9b6856db22
~~~

If a hash differs before source changes, stop and identify the toolchain/base
difference rather than blessing a new compatibility value.

---

### Task 1: Carry registered material color through Blender fallback

**Files:**
- Modify: `src/rendering/export.py`
- Modify: `src/rendering/_blender_materials.py`
- Modify: `src/rendering/_blender_render.py`
- Modify: `tests/test_blender_materials.py`
- Modify: `tests/test_reproducible_builds.py`

**Interfaces:**
- Manifest part row adds `rgba: [r, g, b, a]`.
- Add `apply_material(nt, tag, rgba)` to the Blender-safe material module.
- Change `default_material(nt, base=...)` to accept a fallback RGB value.

- [ ] **Step 1: Write RED manifest and fallback tests**

In `tests/test_reproducible_builds.py` add
`test_export_manifest_carries_registered_rgba`. Build a one-part
`DetailAssembly`, export its manifest, and assert:

~~~python
part = data["parts"][0]
assert part["material"] == placed.component.material_key
assert part["rgba"] == list(placed.component.material.rgba)
~~~

In `tests/test_blender_materials.py` add
`test_unknown_procedural_tag_uses_registered_manifest_color`:

~~~python
def test_unknown_procedural_tag_uses_registered_manifest_color(
    monkeypatch, capsys
):
    from detailgen.rendering import _blender_materials as bm

    calls = []
    monkeypatch.setattr(
        bm,
        "_principled",
        lambda nt, base, rough, metal=0.0: calls.append(
            (nt, base, rough, metal)
        ),
    )
    nt = object()
    bm.apply_material(nt, "mahogany_probe", (0.31, 0.12, 0.07, 1.0))

    assert calls == [(nt, (0.31, 0.12, 0.07), 0.6, 0.0)]
    assert "unknown material tag" in capsys.readouterr().err
~~~

Also add a known-tag test proving `apply_material` calls the registered builder
instead of the fallback.

- [ ] **Step 2: Run RED**

~~~bash
.venv/bin/python -m pytest \
  tests/test_blender_materials.py \
  tests/test_reproducible_builds.py::test_export_manifest_carries_registered_rgba \
  -q
~~~

Expected: failures because `rgba` and `apply_material` do not exist.

- [ ] **Step 3: Implement the Blender-safe fallback**

In `_blender_materials.py`:

~~~python
def default_material(nt, base=(0.7, 0.7, 0.7)) -> None:
    _principled(nt, tuple(base[:3]), 0.6)


def apply_material(nt, tag, rgba) -> None:
    builder = resolve_material_builder(tag)
    if builder is None:
        default_material(nt, base=tuple(rgba[:3]))
    else:
        builder(nt)
~~~

In `export_manifest` add `rgba` from the already-resolved
`pl.component.material.rgba`.

In `_blender_render.py` import `apply_material`, change
`make_material(tag, rgba)` to call it, and have `assign_materials` pass the
manifest RGBA. Cache materials by `(tag, tuple(rgba))` so two inconsistent
manifest rows cannot accidentally share a shader.

- [ ] **Step 4: Run GREEN and rendering regressions**

~~~bash
.venv/bin/python -m pytest \
  tests/test_blender_materials.py \
  tests/test_reproducible_builds.py \
  tests/test_spec_presentation_equiv.py \
  -q
~~~

Expected: all pass. Existing known material builders remain selected and
unknown tags still warn.

- [ ] **Step 5: Commit Task 1**

~~~bash
git add \
  src/rendering/export.py \
  src/rendering/_blender_materials.py \
  src/rendering/_blender_render.py \
  tests/test_blender_materials.py \
  tests/test_reproducible_builds.py
git commit -m "feat: render registered material fallback colors"
~~~

---

### Task 2: Extract the reusable fabricated-panel core

**Files:**
- Create: `src/components/panel.py`
- Modify: `src/components/hardwood.py`
- Modify: `src/components/cedar.py`
- Modify: `src/components/__init__.py`
- Create: `tests/test_fabricated_panel.py`
- Modify: `tests/test_hardwood_components.py`
- Modify: `tests/test_cedar_components.py`

**Interfaces:**
- Register `FabricatedPanel` as `fabricated_panel`.
- Preserve `hardwood_panel` and `cedar_panel` registrations.
- Preserve `apply_feature_cut(...)` and `fabrication_record(part_id="")`.
- Make all feature cuts append-only.

- [ ] **Step 1: Add GREEN characterization assertions before refactoring**

Add representative `geometry_hash` assertions to the existing cedar and
hardwood tests using the Task 0 literals. Also pin:

- datum names and origins;
- exact process-step kind order;
- stock `material_key` and profile;
- BOM item/material/length;
- current assumption language; and
- current single-feature volume.

Run:

~~~bash
.venv/bin/python -m pytest \
  tests/test_hardwood_components.py \
  tests/test_cedar_components.py \
  -q
~~~

Expected: all pass before implementation. Commit these characterization tests:

~~~bash
git add tests/test_hardwood_components.py tests/test_cedar_components.py
git commit -m "test: lock solid panel compatibility"
~~~

- [ ] **Step 2: Write RED generic-panel tests**

In `tests/test_fabricated_panel.py` cover:

1. registry/import:

~~~python
assert components.get("fabricated_panel") is FabricatedPanel
~~~

2. a synthetic mahogany-like material:

~~~python
monkeypatch.setitem(
    MATERIALS,
    "mahogany_probe",
    Material("Select mahogany", (0.31, 0.12, 0.07)),
)
~~~

Compile a DetailSpec component with:

~~~yaml
type: fabricated_panel
params:
  length: 8 in
  width: 5.5 in
  thickness: 0.75 in
  material_key: mahogany_probe
  stock_label: mahogany
  material_assumptions: >-
    Select mahogany panel for interior use; species, grade, moisture
    condition, finish, and structural capacity are not analyzed.
~~~

Assert material, BOM, stock profile, assumptions, and manifest RGBA. Do not add
a `MahoganyPanel` or Blender shader.

3. an unknown material fails loudly and lists known keys;
4. non-positive dimensions fail `check()`;
5. invalid miter end fails at construction;
6. three appended bores/notches all remain in the fabrication record/cache key;
7. omitted stock label derives `material_key.replace("_", " ")`; and
8. omitted assumptions explicitly say grade, moisture, finish, and capacity are
   not analyzed.

- [ ] **Step 3: Run RED**

~~~bash
.venv/bin/python -m pytest tests/test_fabricated_panel.py -q
~~~

Expected: import/registry failure because `FabricatedPanel` does not exist.

- [ ] **Step 4: Implement `FabricatedPanel`**

Move the duplicated inch-fraction helper and common panel behavior into
`src/components/panel.py`. The constructor must:

~~~python
if material_key not in MATERIALS:
    raise ValueError(
        f"unknown panel material {material_key!r}; "
        f"known materials: {sorted(MATERIALS)}"
    )
if set(miter_ends) - {"near", "far"}:
    raise ValueError(...)
~~~

Represent a feature as one immutable tuple containing `cx`, `cy`, `radius`,
`noun`, `step_kind`, and `provenance`. Reject `step_kind` outside
`{"bore", "notch"}`. `apply_feature_cut` always appends.

Build geometry only through
`self.fabrication_record().installed_geometry()`. Do not create a second
hand-written CadQuery path.

Use the material registry display name in default assumptions, but do not infer
any physical property from the name.

- [ ] **Step 5: Convert cedar and hardwood to thin wrappers**

`CedarPanel(FabricatedPanel)` supplies:

- `material_key="cedar"`;
- `stock_label="cedar"`;
- current untreated-exterior assumption text; and
- current default name.

`HardwoodPanel(FabricatedPanel)` supplies the corresponding hardwood values and
continues to accept `miter_ends`. Keep `WoodDowel` in `hardwood.py` unchanged.

Export `FabricatedPanel` from `detailgen.components`. Keep wrapper module paths,
names, decorators, and constructor compatibility.

- [ ] **Step 6: Run GREEN and compatibility hashes**

~~~bash
.venv/bin/python -m pytest \
  tests/test_fabricated_panel.py \
  tests/test_hardwood_components.py \
  tests/test_cedar_components.py \
  tests/test_process_graph.py \
  -q
~~~

Expected: all pass, including the three pre-refactor geometry hashes for cedar
and hardwood. If a wrapper hash changes, compare fabrication records before
changing any expected value.

- [ ] **Step 7: Commit Task 2**

~~~bash
git add \
  src/components/panel.py \
  src/components/hardwood.py \
  src/components/cedar.py \
  src/components/__init__.py \
  tests/test_fabricated_panel.py \
  tests/test_hardwood_components.py \
  tests/test_cedar_components.py
git commit -m "refactor: extract material-parameterized panels"
~~~

---

### Task 3: Replace installation fastener class lists with capabilities

**Files:**
- Modify: `src/core/base.py`
- Modify: `src/components/fasteners.py`
- Modify: `src/assemblies/installation.py`
- Create: `tests/test_component_capabilities.py`
- Modify: `tests/test_install_contract.py`

**Interfaces:**
- Add `COMPONENT_CAPABILITIES` and `Component.capability_tags()`.
- Replace `FASTENER_COMPONENT_CLASSES` in `is_fastener()`.

- [ ] **Step 1: Write RED capability protocol tests**

In `tests/test_component_capabilities.py` define a minimal test component with
`CAPABILITIES = frozenset({"installation_fastener"})` and an `_build()` that
raises. Add it to a `DetailAssembly` and assert `is_fastener(placed)` is true
without adding its class name anywhere.

Also assert:

- ordinary components return an empty set;
- an unknown capability raises a teaching `ValueError` naming the valid tags;
- `LagScrew`, `StructuralScrew`, and `ExteriorWoodScrew` are installation
  fasteners and wood screws;
- `ThreadedRod` and `HexBolt` remain installation fasteners; and
- washers/nuts/connectors remain false.

- [ ] **Step 2: Run RED**

~~~bash
.venv/bin/python -m pytest tests/test_component_capabilities.py -q
~~~

Expected: failure because `capability_tags` and the closed vocabulary do not
exist.

- [ ] **Step 3: Implement the closed protocol**

In `core/base.py` add:

~~~python
COMPONENT_CAPABILITIES = frozenset({
    "installation_fastener",
    "wood_screw",
    "ordinary_wood_screw",
    "exterior_use",
})

class Component(ABC):
    CAPABILITIES: ClassVar[frozenset[str]] = frozenset()

    def capability_tags(self) -> frozenset[str]:
        tags = frozenset(self.CAPABILITIES)
        unknown = tags - COMPONENT_CAPABILITIES
        if unknown:
            raise ValueError(...)
        return tags
~~~

Use class attributes so capabilities do not enter `params()` or geometry cache
keys.

Set:

- `_AxialFastener.CAPABILITIES = {"installation_fastener"}`;
- `LagScrew.CAPABILITIES` to the inherited set plus `wood_screw`;
- `StructuralScrew` to inherit `LagScrew`;
- current `ExteriorWoodScrew` to add `wood_screw`,
  `ordinary_wood_screw`, and `exterior_use`; and
- `ThreadedRod.CAPABILITIES = {"installation_fastener"}`.

Change `is_fastener` to:

~~~python
return "installation_fastener" in placed.component.capability_tags()
~~~

Delete `FASTENER_COMPONENT_CLASSES` only after its repository references are
zero.

- [ ] **Step 4: Run GREEN and install-contract regressions**

~~~bash
.venv/bin/python -m pytest \
  tests/test_component_capabilities.py \
  tests/test_install_contract.py \
  tests/test_exterior_wood_screw.py \
  tests/test_install_axes.py \
  -q
~~~

Expected: all pass without building the test component's solid.

- [ ] **Step 5: Commit Task 3**

~~~bash
git add \
  src/core/base.py \
  src/components/fasteners.py \
  src/assemblies/installation.py \
  tests/test_component_capabilities.py \
  tests/test_install_contract.py
git commit -m "refactor: classify fasteners by capability"
~~~

---

### Task 4: Add envelope-first `WoodScrew` and capability-based wood joints

**Files:**
- Modify: `src/components/fasteners.py`
- Modify: `src/components/__init__.py`
- Modify: `src/assemblies/connection.py`
- Create: `tests/test_wood_screw.py`
- Modify: `tests/test_service_panel_connections.py`
- Modify: `tests/test_install_contract.py`

**Interfaces:**
- Register `WoodScrew` as `wood_screw`.
- Add `_require_hardware_capabilities(conn, requirements)`.
- Migrate `CleatScrewed` and `ButtScrewed` to require `wood_screw`.

- [ ] **Step 1: Write RED `WoodScrew` semantic tests**

In `tests/test_wood_screw.py` assert:

- import/registry key;
- default `material_key="steel_galv"` and `exposure="exterior"`;
- closed exposure and representation values;
- `ordinary_wood_screw`, `wood_screw`, `installation_fastener`, and
  `exterior_use` capabilities;
- interior exposure omits only `exterior_use`;
- BOM/description never says structural;
- assumptions say envelope threads/drive are omitted and capacity is not
  analyzed; and
- the current `ExteriorWoodScrew` description/BOM remain unchanged.

- [ ] **Step 2: Write RED geometry tests**

Add:

~~~python
def test_envelope_geometry_never_calls_threaded_shaft(monkeypatch):
    monkeypatch.setattr(
        fasteners,
        "threaded_shaft",
        lambda *a, **k: pytest.fail("envelope screw built represented threads"),
    )
    screw = WoodScrew(0.164 * IN, 1.5 * IN)
    bb = screw.solid.val().BoundingBox()
    assert bb.zmin == pytest.approx(-screw.length)
    assert bb.zmax == pytest.approx(screw.head_height)
    assert bb.xlen == pytest.approx(screw.head_diameter)
~~~

Also pin the detailed compatibility wrapper to:

~~~python
assert geometry_hash(
    ExteriorWoodScrew(0.164 * IN, 1.5 * IN).solid
) == "9fea70e8c0facd592ff729f0e443d54dde64257d8bfe80f229ba3d9b6856db22"
~~~

- [ ] **Step 3: Write RED connection-capability tests**

Add tests proving:

- `WoodScrew` works in one-screw `CleatScrewed` and `ButtScrewed` joints;
- a test-only component carrying `wood_screw` is accepted without editing a
  class tuple;
- a `HexBolt` or washer fails with a message containing the slot, required
  `wood_screw` tag, actual tags, and part name; and
- wrong hardware count retains the existing positional diagnostic.

The test-only capable screw's `_build()` must raise; generating connection checks
must still pass, proving this path is semantic-only.

- [ ] **Step 4: Run RED**

~~~bash
.venv/bin/python -m pytest \
  tests/test_wood_screw.py \
  tests/test_service_panel_connections.py \
  -q
~~~

Expected: import and capability-helper failures.

- [ ] **Step 5: Implement `WoodScrew`**

Place `WoodScrew` beside the current exterior screw. Preserve the common
fastener frame and use:

~~~python
EXPOSURES = ("interior", "exterior")
SCREW_REPRESENTATIONS = ("envelope", "represented_threads")
~~~

For `envelope`:

- build the same round head as the current exterior screw;
- use `axis_cylinder(..., base=(0, 0, 0), direction=(0, 0, -1))` for the smooth
  shank;
- reuse the current conical-tip operation; and
- never call `threaded_shaft`.

For `represented_threads`, preserve the current
`ExteriorWoodScrew._build()` operation order exactly.

Override `capability_tags()` only to add `exterior_use` when
`self.exposure == "exterior"`, then validate the result through the base closed
vocabulary.

Make `ExteriorWoodScrew(WoodScrew)` a wrapper fixed to:

~~~python
material_key="steel_galv"
exposure="exterior"
representation="represented_threads"
~~~

Keep its constructor signature, class name, registry key, default name,
description, assumptions, BOM label, datums, and detailed geometry.

- [ ] **Step 6: Implement capability-based positional unpacking**

Add:

~~~python
def _require_hardware_capabilities(
    conn: Connection,
    requirements: list[frozenset[str]],
) -> list[Placed]:
    ...
~~~

It must validate count first, then each positional slot with
`required <= actual`. Error text must be as diagnostic as
`_require_hardware_roles`.

Change only `CleatScrewed._unpack` and `ButtScrewed._unpack` to require
`frozenset({"wood_screw"})` per screw. Remove `_BOX_SCREW` when no reference
remains. Leave `_SCREW` and unrelated connection types unchanged.

- [ ] **Step 7: Run GREEN**

~~~bash
.venv/bin/python -m pytest \
  tests/test_wood_screw.py \
  tests/test_component_capabilities.py \
  tests/test_exterior_wood_screw.py \
  tests/test_service_panel_connections.py \
  tests/test_install_contract.py \
  -q
~~~

Expected: all pass; the compatibility screw hash remains unchanged.

- [ ] **Step 8: Commit Task 4**

~~~bash
git add \
  src/components/fasteners.py \
  src/components/__init__.py \
  src/assemblies/connection.py \
  tests/test_wood_screw.py \
  tests/test_service_panel_connections.py \
  tests/test_install_contract.py
git commit -m "feat: add reusable envelope wood screws"
~~~

---

### Task 5: Generalize pivot/latch service-panel connections

**Files:**
- Modify: `src/assemblies/connection.py`
- Modify: `src/assemblies/__init__.py`
- Modify: `tests/test_service_panel_connections.py`

**Interfaces:**
- Register `ServicePanelScrewed` as `service_panel_screwed`.
- Constructor: `ServicePanelScrewed(mode: str)` where mode is `pivot` or
  `latch`.
- Keep the two old zero-argument wrappers.

- [ ] **Step 1: Write RED parameterized semantic tests**

Extend `tests/test_service_panel_connections.py` so each mode asserts:

- registry lookup and constructor;
- edge kind and install role;
- exactly the two screw/member overlap and bond pairs;
- no `fastened_by`, `bears_on`, or transfer claims;
- structural screw rejection because it lacks `ordinary_wood_screw`;
- interior ordinary screw rejection because it lacks `exterior_use`; and
- unknown mode failure listing `pivot` and `latch`.

Add a compiler test using:

~~~yaml
connections:
  - type: service_panel_screwed
    params: {mode: pivot}
    parts: [frame, panel]
    hardware: [retainer]
~~~

Assert the compiled edge is `pivoted_by`.

- [ ] **Step 2: Add the no-CAD guard**

Monkeypatch the three participating components' `_build()` methods to raise,
then call `Connection.generate_checks` for both modes. The test must pass.

- [ ] **Step 3: Run RED**

~~~bash
.venv/bin/python -m pytest tests/test_service_panel_connections.py -q
~~~

Expected: missing `service_panel_screwed` registry entry and old class-name
guard failures.

- [ ] **Step 4: Promote the shared implementation**

Replace private `_ServicePanelScrewed` with registered public
`ServicePanelScrewed`. Use one closed lookup table:

~~~python
SERVICE_PANEL_MODES = {
    "pivot": ("pivoted_by", "pivot_screw"),
    "latch": ("latched_by", "latch_screw"),
}
~~~

Require one hardware slot with:

~~~python
frozenset({"ordinary_wood_screw", "exterior_use"})
~~~

Keep all current edge, bond, overlap, and installation behavior.

Implement `PivotScrewed` and `ServiceLatchScrewed` as registered wrappers that
call `super().__init__("pivot")` and `super().__init__("latch")`. Export the new
public class.

- [ ] **Step 5: Run GREEN and prove semantic speed**

~~~bash
.venv/bin/python -m pytest \
  tests/test_service_panel_connections.py \
  tests/test_install_contract.py \
  -q --durations=20
~~~

Expected: all pass, no no-CAD guard failure, and no component solid is built by
the semantic service-panel tests.

- [ ] **Step 6: Commit Task 5**

~~~bash
git add \
  src/assemblies/connection.py \
  src/assemblies/__init__.py \
  tests/test_service_panel_connections.py
git commit -m "refactor: parameterize service panel retainers"
~~~

---

### Task 6: Integrate accepted branch work and migrate the birdhouse pilot

**Files:**
- Merge/rebase from accepted clean branch tips.
- Modify: `details/family_birdhouse.spec.yaml`
- Modify: `tests/test_family_birdhouse_e2e.py`
- Modify: `tests/test_family_birdhouse_design_review.py`
- Modify: `tests/test_family_birdhouse_report.py`
- Modify: `scripts/family_birdhouse_report.py`
- Modify: `tests/conftest.py` and `pyproject.toml` only through integration of
  the existing detail-gate work, not a new implementation.

**Precondition:** the birdhouse and caddy-performance branch worktrees are
clean, and their branch owners have identified accepted tips.

- [ ] **Step 1: Integrate the finalized birdhouse branch**

~~~bash
git merge --no-ff codex/birdhouse-plumb
~~~

Resolve overlaps by preserving both:

- the birdhouse's latest spec/report truth and fastener formatting fixes; and
- the new generic panel/screw/capability implementation.

Do not copy files from the active worktree or discard uncommitted work. Run:

~~~bash
.venv/bin/python -m pytest \
  tests/test_family_birdhouse_e2e.py \
  tests/test_family_birdhouse_design_review.py \
  tests/test_family_birdhouse_report.py \
  -q
~~~

Expected before migration: all accepted birdhouse tests pass.

- [ ] **Step 2: Integrate only the accepted semantic-gate implementation**

Prefer merging the branch after its owner marks it complete:

~~~bash
git merge --no-ff codex/caddy-test-performance
~~~

If that branch still contains unrelated unfinished certification work, stop and
ask its owner for the accepted gate commit range; cherry-pick only that range.
Do not recreate `--detail-gate` locally.

Run:

~~~bash
.venv/bin/python -m pytest tests/test_detail_gate_selection.py -q
.venv/bin/python -m pytest --collect-only -q > /tmp/all-nodeids.txt
~~~

Expected: strict selector tests pass and ordinary collection succeeds.

- [ ] **Step 3: Write RED birdhouse migration assertions**

Update the birdhouse tests first to expect:

- all seven cedar boards are `FabricatedPanel` instances with
  `material_key == "cedar"`;
- all 21 screws are `WoodScrew` instances with
  `representation == "envelope"` and the ordinary/exterior capabilities;
- no structural screw occurs;
- pivot/latch connections use `service_panel_screwed` modes and still emit two
  `pivoted_by` plus one `latched_by` edges;
- BOM item/material wording and seven cut records/nine bores remain unchanged;
- model validation remains clean; and
- two fresh compiles produce the same assembly hash.

Update report tests to identify panels by `material_key` and screws by
capability instead of concrete compatibility-wrapper type.

Run the three birdhouse modules and confirm they fail against the old spec.

- [ ] **Step 4: Migrate the DetailSpec**

For each cedar board, change:

~~~yaml
type: cedar_panel
~~~

to:

~~~yaml
type: fabricated_panel
params:
  # existing dimensions...
  material_key: cedar
~~~

The generic defaults derive stock label `cedar` and assumptions from the
registered display identity without inventing properties.

Change each `exterior_wood_screw` component to `wood_screw`. The defaults are
already exterior galvanized envelope representation; keep them explicit only
where the spec needs reader clarity.

Change service connections to:

~~~yaml
type: service_panel_screwed
params: {mode: pivot}
~~~

or:

~~~yaml
type: service_panel_screwed
params: {mode: latch}
~~~

Keep every placement, dimension, feature, part reference, assumption, sequence,
and validation claim unchanged.

- [ ] **Step 5: Remove report concrete-type coupling**

In `family_birdhouse_report.py`:

- use `component.material_key == "cedar"` for cedar coloring/counts; and
- use `"ordinary_wood_screw" in component.capability_tags()` for screw
  coloring/counts.

Do not make the report import a new project-specific screw or panel class.

- [ ] **Step 6: Bind existing real tests to the semantic detail gate**

Use the contract vocabulary from the integrated `tests/conftest.py`, currently:

~~~text
compile, geometry, validation, connections, fabrication,
bom, governance, intent, determinism
~~~

Apply:

- birdhouse E2E module: `compile`, `geometry`, `validation`,
  `connections`, `fabrication`, `bom`, `intent`, `determinism`;
- design-review module: `governance`;
- report module: optional `documents` only if it remains inside the desired
  authoring loop.

Do not claim `determinism` unless the new two-compile assembly-hash test is in
the selected set.

- [ ] **Step 7: Run the complete pilot gate**

~~~bash
DETAILGEN_CACHE_DIR="$(mktemp -d)" \
  .venv/bin/python -m pytest \
  --detail-gate family_birdhouse \
  -q --durations=30
~~~

Expected: complete-contract collection succeeds and every selected test passes.

- [ ] **Step 8: Commit Task 6**

~~~bash
git add \
  details/family_birdhouse.spec.yaml \
  scripts/family_birdhouse_report.py \
  tests/test_family_birdhouse_e2e.py \
  tests/test_family_birdhouse_design_review.py \
  tests/test_family_birdhouse_report.py
git commit -m "refactor: express birdhouse with reusable vocabulary"
~~~

Merge commits remain separate history; do not squash away their provenance.

---

### Task 7: Measure the new authoring loop and screw representation

**Files:**
- Modify: `scripts/benchmark.py`
- Modify: `tests/test_benchmark_harness.py`
- Create:
  `docs/superpowers/specs/2026-07-15-reusable-physical-vocabulary-benchmark.md`

**Interfaces:**
- Add `family_birdhouse` to `DETAIL_SPECS`.
- Record cold, fresh-process measurements; do not add wall-clock assertions to
  pytest.

- [ ] **Step 1: Write RED benchmark-harness coverage**

Add a test that `DETAIL_SPECS["family_birdhouse"]` points to
`family_birdhouse.spec.yaml` and that `load_detail("family_birdhouse")` returns
the normal compiled-spec factory.

- [ ] **Step 2: Run RED**

~~~bash
.venv/bin/python -m pytest tests/test_benchmark_harness.py -q
~~~

Expected: missing detail-map entry.

- [ ] **Step 3: Add the birdhouse benchmark entry and run GREEN**

~~~python
DETAIL_SPECS = {
    # existing details...
    "family_birdhouse": "family_birdhouse.spec.yaml",
}
~~~

Run:

~~~bash
.venv/bin/python -m pytest tests/test_benchmark_harness.py -q
~~~

Expected: all pass.

- [ ] **Step 4: Measure envelope versus represented threads**

Use at least seven new Python processes for each representation, with
`DETAILGEN_NO_CACHE=1`. Each process constructs one screw and forces
`.solid.val()`. Record every elapsed time and the median. A small helper command
or scratch script is acceptable, but do not commit generated cache/output data.

Go/no-go rule:

- envelope median must be at least 2× faster than represented threads; and
- if it is not, profile the two `_build` paths and revise the implementation
  before calling the performance objective achieved.

The unit test proving `threaded_shaft` is never called remains the deterministic
correctness guard; timing is supporting evidence.

- [ ] **Step 5: Measure the full birdhouse compile/validation phases**

~~~bash
DETAILGEN_NO_CACHE=1 \
  .venv/bin/python scripts/benchmark.py \
  --details family_birdhouse \
  --runs 2 \
  --no-doc \
  --out /tmp/plumb-birdhouse-bench
~~~

Expected: `bench.json` contains two successful runs, a `build:WoodScrew` phase,
and `validation_ok: true`.

- [ ] **Step 6: Measure the semantic gate twice from fresh processes**

~~~bash
for run in 1 2; do
  DETAILGEN_CACHE_DIR="$(mktemp -d)" \
    /usr/bin/time -p \
    .venv/bin/python -m pytest \
    --detail-gate family_birdhouse -q
done
~~~

Target: each run is at most 36.44 seconds, half of the 72.88-second focused
extension baseline. If the target is missed:

1. inspect `--durations=30`;
2. consolidate immutable module fixtures or remove unrelated gate annotations;
3. keep every required contract and negative probe; and
4. rerun both fresh-process measurements.

Do not meet the target by reading a prior run's cache.

- [ ] **Step 7: Write the benchmark report**

Record:

- repository commit and tool versions;
- machine/load caveat;
- old 72.88-second focused extension baseline;
- observed 7:17 connection and 17:12 full-suite runs;
- all screw microbenchmark samples/medians;
- two `benchmark.py` detail runs and phase medians;
- two fresh semantic-gate wall times;
- cache environment for every measurement; and
- whether both go/no-go rules passed.

- [ ] **Step 8: Commit Task 7**

~~~bash
git add \
  scripts/benchmark.py \
  tests/test_benchmark_harness.py \
  docs/superpowers/specs/2026-07-15-reusable-physical-vocabulary-benchmark.md
git commit -m "perf: verify reusable vocabulary authoring loop"
~~~

---

### Task 8: Full regression, artifact review, and handoff

**Files:**
- Regenerate under: `outputs/family_birdhouse/`
- Update only source-controlled fingerprints/records whose changes are
  intentional and reviewed.
- Modify roadmap/progress documentation only if required by the integrated
  detail-gate workflow.

- [ ] **Step 1: Run the focused subsystem matrix**

~~~bash
.venv/bin/python -m pytest \
  tests/test_blender_materials.py \
  tests/test_reproducible_builds.py \
  tests/test_fabricated_panel.py \
  tests/test_hardwood_components.py \
  tests/test_cedar_components.py \
  tests/test_component_capabilities.py \
  tests/test_wood_screw.py \
  tests/test_exterior_wood_screw.py \
  tests/test_service_panel_connections.py \
  tests/test_install_contract.py \
  tests/test_benchmark_harness.py \
  -q
~~~

Expected: all pass.

- [ ] **Step 2: Run the complete birdhouse gate one final time**

~~~bash
DETAILGEN_CACHE_DIR="$(mktemp -d)" \
  .venv/bin/python -m pytest \
  --detail-gate family_birdhouse \
  -q
~~~

Expected: all required contracts present and all tests pass.

- [ ] **Step 3: Run the official full repository suite once**

~~~bash
DETAILGEN_CACHE_DIR="$(mktemp -d)" \
  .venv/bin/python -m pytest -q
~~~

Expected: zero failures. If a failure passes alone, reproduce it three times
before classifying it as order/parallel sensitive; do not waive it from one
rerun.

- [ ] **Step 4: Regenerate the birdhouse preview package**

Use the accepted report CLI/help contract, for example:

~~~bash
.venv/bin/python scripts/family_birdhouse_report.py \
  --preview \
  --out outputs/family_birdhouse
~~~

Expected: technical, family, fabrication, installation, design-review, CSV,
STEP, GLB, manifest, and view artifacts are produced with no delivery
confirmation.

- [ ] **Step 5: Review the artifact delta**

Compare the prior and new model/package manifests.

Expected intentional changes:

- component identity for generic panels/screws where exposed;
- screw-local geometry hashes and the assembly hash due to envelope screws;
- any derived file hashes downstream of that geometry.

Expected unchanged facts:

- seven cedar boards;
- 21 ordinary exterior screws;
- nine bores;
- all dimensions and placements;
- BOM item/material wording and cut lengths;
- two pivot plus one latch semantics;
- zero blocking validation findings; and
- delivery remains gated.

Any panel geometry, placement, cut-list, bore, connection-edge, or validation
change is a regression until explained.

- [ ] **Step 6: Run static repository checks**

~~~bash
git diff --check
git status --short
rg -n "_BOX_SCREW|FASTENER_COMPONENT_CLASSES|class _ServicePanelScrewed" src tests
rg -n "isinstance\\(.*(CedarPanel|ExteriorWoodScrew)" \
  scripts/family_birdhouse_report.py \
  tests/test_family_birdhouse_*.py
~~~

Expected: `git diff --check` is silent; the legacy implementation symbols have
no live references; birdhouse project code no longer couples to compatibility
wrapper classes.

- [ ] **Step 7: Request review and address findings**

Review specifically for:

- material truth versus invented properties;
- compatibility-wrapper hashes and signatures;
- capability-tag honesty;
- absence of structural claims on ordinary screws/service panels;
- no-CAD semantic test boundary;
- gate completeness and fresh-cache timing; and
- regenerated artifact authority.

Rerun the smallest affected test set after each fix, then repeat Steps 1–3
before completion.

- [ ] **Step 8: Commit final reviewed source changes**

~~~bash
git add <reviewed-source-files-only>
git commit -m "docs: finalize reusable vocabulary verification"
~~~

Do not commit ignored benchmark caches or generated preview artifacts unless the
repository's existing release policy explicitly tracks them.

- [ ] **Step 9: Push the implementation branch**

~~~bash
git push -u origin codex/plumb-reusable-vocabulary
~~~

Expected: push succeeds and `git status --short --branch` is clean.

- [ ] **Step 10: Resume the birdhouse workflow**

Return to the exact birdhouse step that was paused for compiler extension. Do
not restart concept selection or remodel accepted geometry. Regenerate/review
with the integrated reusable vocabulary, then continue the existing release and
JoelBrain handoff plan.

## Completion Evidence

The implementation handoff is complete only with:

1. focused and full-suite command outputs;
2. three unchanged compatibility geometry hashes;
3. no-CAD semantic guard tests;
4. component and gate benchmark reports meeting the go/no-go rules;
5. reviewed birdhouse manifest/artifact deltas;
6. a clean pushed branch; and
7. an explicit pointer to the resumed birdhouse plan step.
