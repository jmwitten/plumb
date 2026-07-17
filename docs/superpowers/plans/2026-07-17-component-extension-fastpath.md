# Component Extension Fast Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public, risk-classified component-extension contract and verifier that keeps ordinary component-addition checks below 60 seconds and escalates genuinely cross-layer work honestly.

**Architecture:** A new `detailgen.authoring.component_extension` module owns the closed physical-family/change-class vocabulary, YAML schema validation, public-surface component probe, optional bounded focused-test execution, and JSON result. The existing authoring CLI and manifest expose this capability; example contracts exercise catalog and semantic lanes without introducing a second geometry or test framework.

**Tech Stack:** Python 3.12, PyYAML, CadQuery through the existing `Component`/DetailSpec compiler, argparse, pytest.

## Global Constraints

- `catalog_variant`, `new_primitive`, and `semantic_component` verification has a hard 60-second budget.
- `cross_layer_complex` returns `ESCALATE`, never `PASS`.
- Semantic focused tests are bounded to at most eight explicit pytest node IDs and run without a shell.
- Component construction is exercised through the live registry and DetailSpec compiler.
- No repository-wide suite is run; affected focused tests and fresh-process example benchmarks are sufficient.
- Existing component, registry, authoring, and product behavior remains backward compatible.

---

### Task 1: Closed extension vocabulary and guide

**Files:**
- Create: `src/authoring/component_extension.py`
- Test: `tests/test_component_extension.py`
- Modify: `tests/test_scope_manifest.csv`

**Interfaces:**
- Produces: `COMPONENT_FAMILIES`, `CHANGE_CLASSES`, `ComponentExtensionError`, and `build_component_extension_guide() -> dict[str, object]`.
- Consumes: no new production interface.

- [ ] **Step 1: Write failing guide tests**

```python
def test_component_extension_guide_separates_family_from_change_risk():
    guide = build_component_extension_guide()
    assert guide["schema"] == "detailgen/component-extension-guide/v1"
    assert set(guide["families"]) == set(COMPONENT_FAMILIES)
    assert guide["change_classes"]["catalog_variant"]["lane"] == "micro"
    assert guide["change_classes"]["semantic_component"]["budget_seconds"] == 60
    assert guide["change_classes"]["cross_layer_complex"]["result"] == "ESCALATE"


def test_component_family_does_not_select_verification_lane():
    guide = build_component_extension_guide()
    assert "fastener" in guide["families"]
    assert "change_class" in guide["contract_required"]
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
pytest tests/test_component_extension.py -q
```

Expected: collection fails because `detailgen.authoring.component_extension` does not exist.

- [ ] **Step 3: Implement the guide**

Define the seven physical families from the design and four change classes with lanes, required evidence, a 60-second budget for the three fast lanes, and `None` for complex work. Return deep-copied JSON-compatible data so callers cannot mutate module constants.

- [ ] **Step 4: Classify the new tests**

Add each new node to `tests/test_scope_manifest.csv` as `platform,plumb-platform,unit` because guide/schema checks do not compile a real component.

- [ ] **Step 5: Run tests and confirm GREEN**

Expected: guide tests pass in less than five seconds wall-clock.

### Task 2: Fail-closed contract loading and risk requirements

**Files:**
- Modify: `src/authoring/component_extension.py`
- Modify: `tests/test_component_extension.py`
- Modify: `tests/test_scope_manifest.csv`

**Interfaces:**
- Produces: frozen `ComponentExtensionContract` and `load_component_extension_contract(path: Path) -> ComponentExtensionContract`.
- Consumes: `COMPONENT_FAMILIES`, `CHANGE_CLASSES`.

- [ ] **Step 1: Write failing schema tests**

Cover a valid catalog contract and failures for unknown schema/family/change class, unknown expectation fields, missing dimensions, missing reject cases on `new_primitive`, missing semantic evidence/focused tests, more than eight test IDs, and shell-like/non-node-ID test strings.

- [ ] **Step 2: Run the schema tests and confirm RED**

Expected: failures because the loader does not exist.

- [ ] **Step 3: Implement the frozen contract and loader**

The loader accepts only:

```python
{
    "schema", "id", "family", "change_class", "component",
    "expect", "reject", "focused_tests",
}
```

`component` accepts only `type` and `params`. `expect` accepts only
`dimensions`, `datums`, `capabilities`, and `material_key`. Dimension keys are
closed to `xlen`, `ylen`, and `zlen`. Fast lanes require all three dimensions.
Primitive and semantic lanes require one rejected params mapping. Semantic
lanes require capabilities or a non-origin datum plus one focused pytest node
ID. Focused IDs must begin with `tests/`, contain `::`, contain no whitespace,
and number at most eight.

- [ ] **Step 4: Run schema tests and confirm GREEN**

Expected: all contract-validation tests pass without building CAD.

### Task 3: Generic public-surface component verification

**Files:**
- Modify: `src/authoring/component_extension.py`
- Modify: `tests/test_component_extension.py`
- Modify: `tests/test_scope_manifest.csv`

**Interfaces:**
- Produces: `verify_component_extension(contract, *, repo_root=Path.cwd(), clock=time.perf_counter) -> dict[str, object]`.
- Consumes: DetailSpec `load_spec_text`/`compile_spec`, component registry, `Resolver`, and `Component` public methods.

- [ ] **Step 1: Write failing verifier tests**

Tests must prove:

- nominal 2x2 compiles through DetailSpec and passes exact dimensions, datums,
  empty capabilities, material, positive finite volume, `check()`, and BOM text;
- a wrong dimension fails with the expected axis/value;
- a primitive reject case must actually reject through exception or `check()`;
- semantic focused tests are invoked as an argv list without a shell;
- focused-test failure fails the contract;
- an injected clock over 60 seconds fails the fast lane; and
- complex contracts return `ESCALATE` without invoking CAD or focused tests.

- [ ] **Step 2: Run verifier tests and confirm RED**

Expected: failures because verification is not implemented.

- [ ] **Step 3: Implement the narrow verifier**

Build one in-memory DetailSpec with one identity-placed component. Compile and
build it through public APIs. Require no `component.check()` problems, at least
one solid, positive finite total volume, exact declared dimensions within
`1e-6` mm, declared datums/capabilities, material identity, and non-empty BOM
label/description.

Resolve unit-suffixed expected dimensions and reject params with the existing
`Resolver({}, 1.0)`. Reject cases merge over the valid params and succeed only
if construction raises or `check()` returns a problem, without forcing solid
geometry.

Run semantic `focused_tests` as:

```python
subprocess.run(
    [sys.executable, "-m", "pytest", *contract.focused_tests, "-q"],
    cwd=repo_root,
    env=source_bound_environment,
    text=True,
    capture_output=True,
    timeout=remaining_budget,
    check=False,
)
```

Prepend `repo_root / "src"` to `PYTHONPATH`, retain the existing environment,
and never use `shell=True`. The result includes schema, id, family, change
class, lane, status, elapsed/budget seconds, and ordered check IDs.

- [ ] **Step 4: Run verifier tests and confirm GREEN**

Expected: all verifier tests pass and the test module remains below 10 seconds.

### Task 4: CLI, authoring manifest, examples, and user guidance

**Files:**
- Modify: `src/authoring/__init__.py`
- Modify: `src/authoring/__main__.py`
- Modify: `src/authoring/manifest.py`
- Modify: `tests/test_authoring_manifest.py`
- Modify: `tests/test_authoring_scaffold.py`
- Create: `examples/component_extensions/nominal_2x2_lumber.yaml`
- Create: `examples/component_extensions/exterior_wood_screw.yaml`
- Modify: `README.md`
- Modify: `tests/test_scope_manifest.csv`

**Interfaces:**
- Produces: `python -m detailgen.authoring component-guide` and `python -m detailgen.authoring component-check CONTRACT`.
- Consumes: guide/loader/verifier from Tasks 1–3.

- [ ] **Step 1: Write failing CLI and manifest tests**

Assert that `component-guide` emits the exact guide, `component-check` emits a
PASS result for a temporary catalog contract, invalid contracts return code 2
with structured JSON on stderr, and `build_authoring_manifest()` publishes the
component-extension guide and command vectors.

- [ ] **Step 2: Run tests and confirm RED**

Expected: unknown CLI commands and absent manifest key.

- [ ] **Step 3: Implement CLI/export/manifest wiring**

Add the two subcommands, catch only `ComponentExtensionError`, and print sorted,
indented JSON. Export the public functions from `detailgen.authoring`. Add
`component_extensions` to the authoring manifest with `guide_argv` and
`check_argv` alongside the guide payload.

- [ ] **Step 4: Add representative contracts and README workflow**

The catalog example verifies nominal 2x2 lumber at 24 × 1.5 × 1.5 inches. The
semantic example verifies a 0.16-inch × 2-inch exterior envelope `wood_screw`,
its 0.368 × 0.368 × 2.072-inch envelope, head/tip/axis datums, four capability
tags, invalid exposure rejection, and the focused capability test.

Document family vs. change class, the two commands, test minimums, the
60-second rule, and explicit complex escalation in `README.md`.

- [ ] **Step 5: Run affected tests and confirm GREEN**

Run the component extension, authoring manifest, authoring scaffold, registry,
and component-capability test modules. Expected: all pass.

### Task 5: Fresh-process timing, scoped verification, and integration

**Files:**
- Create: `docs/superpowers/specs/2026-07-17-component-extension-fastpath-benchmark.md`

**Interfaces:**
- Consumes: the two public example contracts and affected pytest modules.
- Produces: measured acceptance evidence and merged main branch.

- [ ] **Step 1: Benchmark both public contracts**

Run each through the source-bound launcher in a fresh process under
`/usr/bin/time -p`. Record command, result, internal elapsed time, and external
wall time. Both must be below 60 seconds.

- [ ] **Step 2: Run scoped verification**

Run:

```bash
pytest tests/test_component_extension.py tests/test_authoring_manifest.py \
  tests/test_authoring_scaffold.py tests/test_registry.py \
  tests/test_component_capabilities.py -q
```

Run `git diff --check`. Do not run repository verification.

- [ ] **Step 3: Self-review against the design**

Confirm all families/classes are exposed, fast lanes enforce 60 seconds,
complex work cannot return PASS, focused test execution has no shell, examples
exercise catalog and semantic lanes, and public guidance contains no stale
full-suite requirement.

- [ ] **Step 4: Commit, merge, and push**

Commit implementation/evidence on `codex/component-extension-fastpath`, merge
it into `main` without touching unrelated untracked files, and push
`origin/main`.
