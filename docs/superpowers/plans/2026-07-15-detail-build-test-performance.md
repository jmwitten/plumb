# Detail Build Test Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a strict semantic per-detail pytest gate and prove the fresh-run
armchair-caddy verification wall time is at most 645.17 seconds.

**Architecture:** Pytest collection remains unchanged by default. Supplying
`--detail-gate SLUG` selects tests carrying a typed `detail_gate` marker, fails
collection if the slug is unknown or any universal build contract is missing,
and runs only the selected product tests. Existing caddy tests provide the
coverage; the implementation adds metadata and selection, not duplicate mocks.

**Tech Stack:** Python 3.12, pytest 9, pytest-xdist 3.8, CadQuery 2.8.

## Global Constraints

- Historical acceptance baseline: 1,290.34 seconds; ceiling: 645.17 seconds.
- Every measured run starts a new Python process with fresh temporary cache
  directories; no previous-run output/cache may be used.
- Ordinary pytest collection must retain all 1,833 pre-existing node IDs; new
  detail-gate contract tests may increase the total.
- Universal contracts are exactly `compile`, `geometry`, `validation`,
  `fabrication`, `governance`, and `documents`.
- Unknown slugs and incomplete gates fail before executing tests.
- The full repository suite remains mandatory for shared platform changes.
- No existing test is deleted in this increment.

---

### Task 1: Strict detail-gate collection contract

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/test_detail_gate_selection.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: pytest `Item.iter_markers`, `Config.getoption`, and collection hooks.
- Produces: `pytest --detail-gate SLUG`, `_detail_gate_selection(items, slug)`,
  and `_require_complete_detail_gate(slug, selected, contracts)`.

- [ ] **Step 1: Write RED tests for selection and completeness**

Create lightweight fake items in `tests/test_detail_gate_selection.py` whose
`iter_markers("detail_gate")` returns real `pytest.Mark` objects. Pin selection,
unknown-slug failure, missing-contract failure, and complete-gate acceptance:

```python
def test_selection_keeps_only_requested_slug():
    selected, deselected, contracts = _detail_gate_selection(
        [
            item("armchair_caddy", contracts=("compile", "geometry")),
            item("platform", contracts=("compile",)),
            item(None),
        ],
        "armchair_caddy",
    )
    assert [row.name for row in selected] == ["armchair_caddy"]
    assert len(deselected) == 2
    assert contracts == {"compile", "geometry"}


def test_unknown_slug_fails_collection():
    with pytest.raises(pytest.UsageError, match="unknown detail gate"):
        _require_complete_detail_gate("missing", [], set())


def test_missing_contract_fails_collection():
    selected = [item("armchair_caddy", contracts=("compile",))]
    with pytest.raises(pytest.UsageError, match="missing contracts.*documents"):
        _require_complete_detail_gate(
            "armchair_caddy", selected, {"compile"}
        )


def test_complete_contract_is_accepted():
    _require_complete_detail_gate(
        "armchair_caddy",
        [item("armchair_caddy", contracts=tuple(REQUIRED_DETAIL_CONTRACTS))],
        set(REQUIRED_DETAIL_CONTRACTS),
    )
```

Also pin malformed markers: missing slug, unknown keyword, empty contract list,
and an unrecognized contract must raise `pytest.UsageError` with the item id.

- [ ] **Step 2: Run RED and verify the missing API is the failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_detail_gate_selection.py -q
```

Expected: collection/import failure because the helper APIs do not exist.

- [ ] **Step 3: Implement pure selection helpers**

In `tests/conftest.py`, define:

```python
REQUIRED_DETAIL_CONTRACTS = frozenset({
    "compile", "geometry", "validation", "fabrication",
    "governance", "documents",
})


def _detail_gate_selection(items, slug):
    selected, deselected, contracts = [], [], set()
    for item in items:
        matched = False
        for marker in item.iter_markers(name="detail_gate"):
            if len(marker.args) != 1 or not isinstance(marker.args[0], str):
                raise pytest.UsageError(
                    f"{item.nodeid}: detail_gate requires one string slug"
                )
            if set(marker.kwargs) != {"contracts"}:
                raise pytest.UsageError(
                    f"{item.nodeid}: detail_gate accepts only contracts="
                )
            declared = marker.kwargs["contracts"]
            if not isinstance(declared, (tuple, list)) or not declared:
                raise pytest.UsageError(
                    f"{item.nodeid}: detail_gate contracts must be non-empty"
                )
            unknown = set(declared) - REQUIRED_DETAIL_CONTRACTS
            if unknown:
                raise pytest.UsageError(
                    f"{item.nodeid}: unknown detail-gate contracts "
                    f"{sorted(unknown)}"
                )
            if marker.args[0] == slug:
                matched = True
                contracts.update(declared)
        (selected if matched else deselected).append(item)
    return selected, deselected, contracts


def _require_complete_detail_gate(slug, selected, contracts):
    if not selected:
        raise pytest.UsageError(f"unknown detail gate {slug!r}")
    missing = REQUIRED_DETAIL_CONTRACTS - contracts
    if missing:
        raise pytest.UsageError(
            f"detail gate {slug!r} is missing contracts: "
            f"{', '.join(sorted(missing))}"
        )
```

- [ ] **Step 4: Add the opt-in pytest hook**

Add `--detail-gate` in `pytest_addoption`, register the marker in
`pytest_configure`, and delegate from `pytest_collection_modifyitems`:

```python
def pytest_collection_modifyitems(config, items):
    slug = config.getoption("--detail-gate")
    if not slug:
        return
    selected, deselected, contracts = _detail_gate_selection(items, slug)
    _require_complete_detail_gate(slug, selected, contracts)
    config.hook.pytest_deselected(items=deselected)
    items[:] = selected
```

Register the marker text under `[tool.pytest.ini_options]` in `pyproject.toml`
so ordinary collection emits no unknown-marker warning.

- [ ] **Step 5: Run GREEN and ordinary collection checks**

Run:

```bash
.venv/bin/python -m pytest tests/test_detail_gate_selection.py -q
.venv/bin/python -m pytest --collect-only -q \
  | rg '^tests/' | sort > /tmp/detailgen-after-nodeids.txt
comm -23 /tmp/detailgen-before-nodeids.txt /tmp/detailgen-after-nodeids.txt
```

Expected: helper tests pass and `comm` prints nothing, proving all 1,833
pre-existing node IDs remain collected.

- [ ] **Step 6: Commit Task 1**

```bash
git add tests/conftest.py tests/test_detail_gate_selection.py pyproject.toml
git commit -m "test: add strict semantic detail gates"
```

---

### Task 2: Bind existing caddy tests to the six contracts

**Files:**
- Modify: `tests/test_armchair_caddy_e2e.py`
- Modify: `tests/test_caddy_reinforced_miter.py`
- Modify: `tests/test_caddy_design_review.py`
- Modify: `tests/test_caddy_instruction_manual.py`
- Modify: `tests/test_install_sweep.py`

**Interfaces:**
- Consumes: the `detail_gate` marker contract from Task 1.
- Produces: a complete `armchair_caddy` gate using existing real tests.

- [ ] **Step 1: Add module-level markers to dedicated caddy modules**

After imports, add exactly these declarations:

```python
# test_armchair_caddy_e2e.py
pytestmark = pytest.mark.detail_gate(
    "armchair_caddy",
    contracts=("compile", "validation", "fabrication"),
)

# test_caddy_reinforced_miter.py
pytestmark = pytest.mark.detail_gate(
    "armchair_caddy", contracts=("geometry",),
)

# test_caddy_design_review.py
pytestmark = pytest.mark.detail_gate(
    "armchair_caddy", contracts=("governance",),
)

# test_caddy_instruction_manual.py
pytestmark = pytest.mark.detail_gate(
    "armchair_caddy", contracts=("documents",),
)
```

- [ ] **Step 2: Mark the caddy installability/interference negative probes**

Apply this decorator to the five caddy-specific tests at the top of
`tests/test_install_sweep.py`, including
`test_caddy_synthetic_oversized_corner_keys_fail_interference`:

```python
@pytest.mark.detail_gate(
    "armchair_caddy", contracts=("geometry", "validation"),
)
```

Do not mark site, platform, stool, rock-anchor, trebuchet, or whole-corpus
tests from the same module.

- [ ] **Step 3: Verify collection inventory before timing**

Run:

```bash
.venv/bin/python -m pytest --detail-gate armchair_caddy --collect-only -q \
  > /tmp/caddy-gate-collect.txt
rg 'oversized_corner_keys|writes_nothing_while_review_is_pending|three_panel_shell' \
  /tmp/caddy-gate-collect.txt
tail -1 /tmp/caddy-gate-collect.txt
```

Expected: all three negative/geometry probes are present and the selected node
count is nonzero with no contract error.

- [ ] **Step 4: Run the first fresh-process gate**

Run:

```bash
/usr/bin/time -p .venv/bin/python -m pytest \
  --detail-gate armchair_caddy -q -n 4 --durations=30
```

Expected: all selected tests pass in at most 645.17 seconds. If it misses the
ceiling, use the duration table to form one new hypothesis before changing
code.

- [ ] **Step 5: Commit Task 2**

```bash
git add tests/test_armchair_caddy_e2e.py \
  tests/test_caddy_reinforced_miter.py tests/test_caddy_design_review.py \
  tests/test_caddy_instruction_manual.py tests/test_install_sweep.py
git commit -m "test: define the armchair caddy build gate"
```

---

### Task 3: Document policy and measured performance

**Files:**
- Modify: `README.md`
- Create: `.superpowers/sdd/caddy-test-performance-report.md`
- Modify: `.superpowers/sdd/progress.md`

**Interfaces:**
- Consumes: final gate command and timing from Task 2.
- Produces: an auditable inner-loop/full-suite policy and benchmark record.

- [ ] **Step 1: Add the one-command workflow to README**

In the Tests section, document:

```bash
pytest --detail-gate armchair_caddy -q -n 4
```

State that detail-owned changes run this gate during iteration, shared
compiler/validation/rendering/pack changes require the full suite, every gate
must cover all six contracts, and the gate never reads results from an earlier
run.

- [ ] **Step 2: Write the benchmark report**

Record exact command, pass/fail count, wall time, and environment for:

- historical full suite: 1,290.34s;
- clean reproduced full suite: 1,351.06s under concurrent load;
- broad 12-file source-reference selection: 78.36s;
- rejected `loadscope` experiment: 85.06s;
- semantic gate run 1 and run 2.

Compute reduction as `1 - final_worst_case / 1290.34` and name every selected
contract plus the representative negative probes.

- [ ] **Step 3: Update the progress ledger**

Add a dated session update describing the root cause, selected gate, strict
freshness rule, measured reduction, and the unchanged full-suite boundary.

- [ ] **Step 4: Verify docs and commit**

```bash
git diff --check
rg -n '645.17|detail-gate|full suite|fresh' \
  README.md .superpowers/sdd/caddy-test-performance-report.md \
  .superpowers/sdd/progress.md
git add README.md .superpowers/sdd/caddy-test-performance-report.md \
  .superpowers/sdd/progress.md
git commit -m "docs: record caddy gate performance policy"
```

---

### Task 4: Fresh verification and branch review

**Files:**
- Modify only if verification exposes a defect in Task 1–3 files.

**Interfaces:**
- Consumes: the frozen branch from Tasks 1–3.
- Produces: two fresh timing proofs, ordinary-collection proof, focused tests,
  full regression evidence, and review disposition.

- [ ] **Step 1: Run the gate twice from fresh Python processes**

```bash
for run in 1 2; do
  /usr/bin/time -p .venv/bin/python -m pytest \
    --detail-gate armchair_caddy -q -n 4 --durations=10
done
```

Both runs must pass; use the slower wall time for acceptance.

- [ ] **Step 2: Verify unknown and incomplete gates fail closed**

```bash
.venv/bin/python -m pytest --detail-gate missing --collect-only -q
.venv/bin/python -m pytest tests/test_detail_gate_selection.py -q
```

Expected: the first command exits nonzero naming `unknown detail gate`; the
second passes all synthetic incomplete-gate tests.

- [ ] **Step 3: Verify ordinary collection is unchanged**

```bash
.venv/bin/python -m pytest --collect-only -q \
  | rg '^tests/' | sort > /tmp/detailgen-final-nodeids.txt
comm -23 /tmp/detailgen-before-nodeids.txt /tmp/detailgen-final-nodeids.txt
```

Expected: no output; every pre-existing node ID remains present.

- [ ] **Step 4: Run the full repository suite once**

Wait until no other detailgen pytest process is consuming the machine, then:

```bash
.venv/bin/python -m pytest -q -n 4
```

Read the complete summary. Marker metadata must not alter default behavior.

- [ ] **Step 5: Review the branch diff against the design**

Check every design requirement against the diff, inspect marker scope for
unrelated tests, verify no production/cache behavior changed, and run:

```bash
git diff --check origin/codex/precedent-first-design-selection...HEAD
git status --short
```

Fix any Critical or Important finding test-first and repeat the affected gate.

- [ ] **Step 6: Final commit and push**

If verification produced report-only changes:

```bash
git add .superpowers/sdd/caddy-test-performance-report.md \
  .superpowers/sdd/progress.md
git commit -m "test: verify caddy gate cuts runtime by half"
git push -u origin codex/caddy-test-performance
```
