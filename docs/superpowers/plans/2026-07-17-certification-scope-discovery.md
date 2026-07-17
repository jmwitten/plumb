# Certification Scope Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every discovered generic certification contract immediately selectable by its product gate without a central scope-manifest edit.

**Architecture:** Keep certification discovery in pytest's runtime boundary and keep scope-record construction pure. `tests/scope_manifest.py` will augment explicit records with missing generic certification nodes; `tests/conftest.py` will discover contract slugs once per pytest configuration and use the augmented records for both scoped selection and full reconciliation.

**Tech Stack:** Python 3.11+, pytest, existing `detailgen.certification` contract discovery, CSV runtime scope manifest.

## Global Constraints

- Explicit scope-manifest rows take precedence and must never be duplicated or replaced.
- Only `tests/test_certified_builds.py::test_certified_build[<slug>]` may be derived.
- Named selection and ordinary full-collection reconciliation must consume the same records.
- Arbitrary tests, release/document tests, platform tiers, and certification rules remain unchanged.
- Invalid or duplicate certification contracts continue to fail through strict existing discovery.

---

### Task 1: Pure certification-scope augmentation

**Files:**
- Modify: `tests/scope_manifest.py`
- Modify: `tests/test_scope_manifest.py`
- Modify: `tests/test_scope_manifest.csv`

**Interfaces:**
- Consumes: `ScopeRecord` and an iterable of validated certification slugs.
- Produces: `augment_certification_nodes(records: Iterable[ScopeRecord], contract_slugs: Iterable[str]) -> tuple[ScopeRecord, ...]`.

- [ ] **Step 1: Write failing augmentation tests**

Add tests that construct explicit records, call `augment_certification_nodes`, and assert that a missing slug produces exactly one inner `document_build_accuracy` node while an explicit generic node remains the original object. Reconcile the augmented records against the expected node IDs to prove the derived node participates in drift checking.

```python
def test_certification_contracts_fill_only_missing_generic_scope_records():
    explicit = ScopeRecord(
        nodeid="tests/test_certified_builds.py::test_certified_build[existing]",
        category="document_build_accuracy",
        owner="existing",
        cadence="inner",
        rationale="explicit rationale",
    )

    records = augment_certification_nodes(
        (explicit,), ("future_build", "existing", "future_build")
    )

    assert records[0] is explicit
    assert records[1] == ScopeRecord(
        nodeid="tests/test_certified_builds.py::test_certified_build[future_build]",
        category="document_build_accuracy",
        owner="future_build",
        cadence="inner",
        rationale="Generic certification node discovered from details/future_build.cert.yaml.",
    )
    reconcile_scope_manifest(records, {row.nodeid for row in records})
```

- [ ] **Step 2: Run the test to verify RED**

Run the focused `test_scope_manifest.py` node with the worktree-bound Python invocation. Expected: import failure because `augment_certification_nodes` does not exist.

- [ ] **Step 3: Implement minimal pure augmentation**

Add a constant node template and a function that materializes explicit records once, tracks existing node IDs, iterates sorted unique slugs, and appends only missing generic nodes using the slug as owner and inner cadence.

```python
CERTIFIED_BUILD_NODE = "tests/test_certified_builds.py::test_certified_build[{slug}]"


def augment_certification_nodes(records, contract_slugs):
    augmented = list(records)
    existing = {record.nodeid for record in augmented}
    for slug in sorted(set(contract_slugs)):
        nodeid = CERTIFIED_BUILD_NODE.format(slug=slug)
        if nodeid in existing:
            continue
        augmented.append(ScopeRecord(
            nodeid=nodeid,
            category="document_build_accuracy",
            owner=slug,
            cadence="inner",
            rationale=(
                "Generic certification node discovered from "
                f"details/{slug}.cert.yaml."
            ),
        ))
        existing.add(nodeid)
    return tuple(augmented)
```

- [ ] **Step 4: Classify and run focused tests GREEN**

Add the new test node to `tests/test_scope_manifest.csv` as a `platform,plumb-platform,unit` self-test, then run `tests/test_scope_manifest.py`. Expected: all tests pass.

- [ ] **Step 5: Commit the pure behavior**

```bash
git add tests/scope_manifest.py tests/test_scope_manifest.py tests/test_scope_manifest.csv
git commit -m "test: derive generic certification scope records"
```

### Task 2: Runtime discovery and shared reconciliation

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_detail_gate_selection.py`
- Modify: `tests/test_scope_manifest.csv`
- Modify: `README.md`

**Interfaces:**
- Consumes: `discover_contracts(details_dir, repo_root=...)` and `augment_certification_nodes` from Task 1.
- Produces: `_load_runtime_scope_records(manifest_path, details_dir, repo_root)` and cached `_scope_records(config)` behavior.

- [ ] **Step 1: Write failing runtime-discovery test**

Create a temporary minimal manifest, detail spec, and certification contract. Call `_load_runtime_scope_records` and assert that the generic certification node exists despite no matching CSV row.

```python
def test_runtime_scope_discovers_generic_contract_without_manifest_row(tmp_path):
    manifest = tmp_path / "test_scope_manifest.csv"
    manifest.write_text("nodeid,category,owner,cadence,rationale\n")
    details = tmp_path / "details"
    details.mkdir()
    (details / "garden_shelf.spec.yaml").write_text("name: garden shelf\n")
    (details / "garden_shelf.cert.yaml").write_text(
        "schema_version: 1\n"
        "subject:\n"
        "  kind: standalone_detail\n"
        "  source: garden_shelf.spec.yaml\n"
    )

    records = _load_runtime_scope_records(manifest, details, tmp_path)

    assert [row.nodeid for row in records] == [
        "tests/test_certified_builds.py::test_certified_build[garden_shelf]"
    ]
```

- [ ] **Step 2: Run the test to verify RED**

Run the focused `test_detail_gate_selection.py` node with the worktree-bound Python invocation. Expected: import failure because `_load_runtime_scope_records` does not exist.

- [ ] **Step 3: Implement runtime discovery**

In `tests/conftest.py`, import `discover_contracts` and `augment_certification_nodes`; define repository/details paths; load explicit rows and discovered slugs through `_load_runtime_scope_records`; cache that result in `_scope_records(config)`.

```python
def _load_runtime_scope_records(manifest_path, details_dir, repo_root):
    explicit = load_scope_manifest(manifest_path)
    contracts = discover_contracts(details_dir, repo_root=repo_root)
    return augment_certification_nodes(explicit, (row.slug for row in contracts))
```

Replace ordinary full-collection reconciliation's fresh `load_scope_manifest` call with `_scope_records(config)` so selection and drift checks share the same classification set.

- [ ] **Step 4: Classify the self-test and document behavior**

Add the runtime-discovery test node to `tests/test_scope_manifest.csv` as a platform unit self-test. Update README certification guidance to say generic certification scope is derived from discovered contracts at runtime and only bespoke product tests require explicit rows.

- [ ] **Step 5: Run compatibility tests GREEN**

Run `tests/test_detail_gate_selection.py`, `tests/test_scope_manifest.py`, `tests/test_certification_contract.py`, `tests/test_certification_engine.py`, `tests/test_certified_builds.py`, and `tests/test_authoring_manifest.py`. Expected: all selected tests pass.

- [ ] **Step 6: Commit runtime integration**

```bash
git add tests/conftest.py tests/test_detail_gate_selection.py tests/test_scope_manifest.csv README.md
git commit -m "feat: discover certification product gates"
```

### Task 3: End-to-end no-registry proof

**Files:**
- Modify: `tests/test_detail_gate_selection.py`
- Modify: `tests/test_scope_manifest.csv`

**Interfaces:**
- Consumes: runtime records, module-path filtering, marker selection, and completeness checks.
- Produces: a regression proof that a discovered slug supplies a complete inner gate without an explicit product row.

- [ ] **Step 1: Add a focused integration-style selection test**

Using the temporary contract from Task 2, assert that `build_nodes(records, "garden_shelf")` selects the derived node and that `module_paths` returns only `tests/test_certified_builds.py`. This proves the existing early collection filter will import the generic parametrized test for the new slug.

```python
selected = build_nodes(records, "garden_shelf")
assert [row.nodeid for row in selected] == [
    "tests/test_certified_builds.py::test_certified_build[garden_shelf]"
]
assert module_paths(selected) == ("tests/test_certified_builds.py",)
```

- [ ] **Step 2: Run the test to verify RED if not already covered**

Run the exact node before completing its assertions. Expected before Task 2 implementation: failure because runtime records are not augmented. If Task 2 made it GREEN, retain the assertion as the end-to-end boundary and do not introduce unrelated production behavior solely to force another failure.

- [ ] **Step 3: Run the complete focused verification set**

Run the compatibility set from Task 2 plus a named existing generic gate:

```bash
pytest --detail-gate armchair_caddy --detail-cadence inner -q
```

Expected: all focused tests and the existing generic product gate pass.

- [ ] **Step 4: Commit proof if it changed after Task 2**

```bash
git add tests/test_detail_gate_selection.py tests/test_scope_manifest.csv
git commit -m "test: prove registry-free product gate selection"
```

- [ ] **Step 5: Push the branch**

```bash
git push -u origin codex/product-gate-fastpath
```
