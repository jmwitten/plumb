# Test Scope and Gate Layering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make document/build verification run only the generic and owner-specific checks that certify the accepted model being delivered, while moving artificial mutations, baseline self-tests, exhaustive geometry oracles, and whole-platform soundness checks to explicit platform integration/audit cadence.

**Architecture:** The audited 2,298-node inventory becomes a fail-closed scope manifest with exactly one category per collected node. The existing strict `detail_gate` remains the build-accuracy selector and gains an inner/release cadence so current-model validation—including normal collision detection—stays in the build gate while cold package/browser/document checks run only for that owner’s release. Separate platform integration and platform audit markers select expensive shared-system checks. Baseline-corruption tests are reduced to pure JSON/directory comparisons; one real live regeneration remains as platform integration evidence.

**Tech Stack:** Python 3.12, pytest 9, pytest-xdist 3.8, CadQuery 2.8/OCCT, stdlib `csv`, `json`, `pathlib`, existing Plumb compiler/validation/report APIs.

## Global Constraints

- The accepted model’s normal validation, including its collision sweep, is document/build accuracy even when invoked by generic certification code.
- A real product used as a counterfactual stress fixture does not make the test build accuracy. Fake corruption, geometry mutation, cache equivalence, invalidation, and exhaustive-oracle tests are platform tests.
- `test_bbox_prefilter.py::test_platform_prefilter_agrees_with_unfiltered` remains intact as a platform audit; it must never enter a named document/build gate.
- Beam-length and other affected-region mutations remain intact as platform audits; they must never enter a named document/build gate.
- The two baseline-tamper behaviors remain tested, but no tamper unit test may compile or validate CadQuery geometry.
- Keep one real, fresh, byte-for-byte baseline regeneration round trip as platform integration evidence.
- Ordinary unfiltered `pytest` must continue to collect and run every test. Scope options filter only when explicitly supplied.
- Unknown build owners, unknown platform tiers, incomplete detail contracts, missing release-document coverage, duplicate manifest rows, and unclassified collected nodes fail closed.
- Do not use wall-clock thresholds as correctness assertions. Record timings with `--durations`; assert call counts and ownership instead.
- Preserve the fresh per-test `DETAILGEN_CACHE_DIR` default. Any broader fixture that reuses an immutable accepted model must own an isolated cache root for its complete lifetime.
- Generated documents never invoke pytest internally. The caller chooses the appropriate build gate before release.
- Missing compiler vocabulary invokes `plumb-extend`, then regeneration and review; no test-scope workaround may conceal a compiler capability gap.

---

## File map

- `tests/test_scope_manifest.csv` — runtime scope truth: every collected node, category, owner, cadence, and rationale; timings excluded.
- `tests/scope_manifest.py` — strict loader, exact collection reconciliation, owner/tier queries, and source-module prefilter support.
- `tests/test_scope_manifest.py` — pure manifest schema, reconciliation, selection, and default-safety tests.
- `tests/conftest.py` — build cadence and platform-tier options, fast source prefiltering, strict selection, and manifest reconciliation.
- `pyproject.toml` — marker declarations for build release, platform integration, and platform audit.
- `tests/test_detail_gate_selection.py` — cadence, mutual-exclusion, and release-document completeness tests.
- `tests/test_baseline_integrity_unit.py` — no-CAD directory comparison, annotated-note merge, tamper, and `--check` CLI tests.
- `tests/test_baselines.py` — committed-surface policy plus the one real live round trip.
- `scripts/regen_baselines.py` — pure comparison and annotated-note merge seams used by both CLI and tests.
- `tests/test_affected_region.py` — platform-audit ownership; consolidate duplicate variant recompilations only where assertions remain equivalent.
- `tests/test_bbox_prefilter.py` — small threshold/multi-solid checks stay ordinary platform tests; two full-detail equivalence oracles become platform audit.
- `tests/test_revision_identity.py` — whole-world scoped-regeneration proofs become platform audit.
- `tests/test_site_overview.py` — one owner-scoped rendered-overview fixture instead of two duplicate PNG renders.
- `tests/test_consolidated_coverage.py` — one accepted details/reports/site context shared by table and headline checks.
- `tests/test_platform_detail.py` — one immutable accepted default platform/report shared by current-build assertions; variants remain separate platform tests.
- `tests/test_family_birdhouse_report.py` — birdhouse release-document marker on the existing one-package module fixture.
- `README.md` — test decision table and exact commands.
- `CLAUDE.md` — replace the blanket full-suite document workflow with the scoped gate policy.
- `docs/superpowers/specs/2026-07-15-test-scope-timing-audit.md` — update final counts/timings after implementation.
- `.superpowers/sdd/test-scope-gate-verification.md` — command, count, and timing evidence captured during execution.

---

### Task 1: Turn the 2,298-node audit into a fail-closed runtime manifest

**Files:**
- Create: `tests/test_scope_manifest.csv`
- Create: `tests/scope_manifest.py`
- Create: `tests/test_scope_manifest.py`
- Modify: `tests/conftest.py`
- Source: `docs/superpowers/specs/2026-07-15-test-scope-timing-audit.csv`

**Interfaces:**
- Produces: `ScopeRecord`, `load_scope_manifest(path)`, `reconcile_scope_manifest(records, collected_nodeids)`, `build_nodes(records, owner, include_release=False)`, and `platform_nodes(records, tier)`.
- Manifest columns: `nodeid`, `category`, `owner`, `cadence`, `rationale`.
- Categories: `platform`, `document_build_accuracy`.
- Build cadences: `inner`, `release`.
- Platform cadences: `unit`, `integration`, `audit`.

- [ ] **Step 1: Write RED manifest-loader and reconciliation tests**

```python
def test_every_record_has_one_closed_category(tmp_path):
    path = write_manifest(
        tmp_path,
        [("tests/test_x.py::test_x", "mystery", "plumb-platform", "unit")],
    )
    with pytest.raises(ScopeManifestError, match="unknown category 'mystery'"):
        load_scope_manifest(path)


def test_reconciliation_fails_for_unclassified_and_retired_nodes():
    records = (
        ScopeRecord(
            nodeid="tests/test_x.py::test_old",
            category="platform",
            owner="plumb-platform",
            cadence="unit",
            rationale="pure shared rule",
        ),
    )
    with pytest.raises(ScopeManifestError, match="unclassified.*test_new"):
        reconcile_scope_manifest(
            records,
            {"tests/test_x.py::test_new"},
        )


def test_generic_parameterized_node_can_belong_to_one_build():
    rows = load_scope_manifest(_fixture_manifest(
        nodeid="tests/test_certified_builds.py::test_certified_build[birdhouse]",
        category="document_build_accuracy",
        owner="family_birdhouse",
        cadence="inner",
    ))
    assert [row.nodeid for row in build_nodes(rows, "family_birdhouse")] == [
        "tests/test_certified_builds.py::test_certified_build[birdhouse]"
    ]
```

- [ ] **Step 2: Run RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_scope_manifest.py -q
```

Expected: import failure because `tests.scope_manifest` does not exist.

- [ ] **Step 3: Implement the immutable manifest model and strict loader**

```python
@dataclass(frozen=True)
class ScopeRecord:
    nodeid: str
    category: Literal["platform", "document_build_accuracy"]
    owner: str
    cadence: Literal["unit", "integration", "audit", "inner", "release"]
    rationale: str


def reconcile_scope_manifest(records, collected_nodeids):
    by_id = {row.nodeid: row for row in records}
    if len(by_id) != len(records):
        raise ScopeManifestError("duplicate nodeid in test scope manifest")
    missing = sorted(set(collected_nodeids) - set(by_id))
    retired = sorted(set(by_id) - set(collected_nodeids))
    if missing or retired:
        raise ScopeManifestError(
            f"scope manifest drift: unclassified={missing}; retired={retired}"
        )
```

Enforce owner `plumb-platform` for platform rows, a non-platform owner for build rows, non-empty rationale, category-compatible cadence, and normalized `tests/...::test...` node ids.

- [ ] **Step 4: Generate the timing-free runtime manifest from the audited CSV**

Translate all 2,298 rows. Map `recommended_cadence` as follows:

- `build_inner` → `inner`
- `build_release` → `release`
- audited platform bbox/affected-region/revision whole-world oracles → `audit`
- other real multi-model/cache/baseline subprocess checks → `integration`
- remaining platform rows → `unit`

Do not copy durations into the runtime manifest. Reconcile the result with:

```bash
.venv/bin/python -m pytest --collect-only -q > /tmp/plumb-scope-collection.txt
```

Expected: 2,298 collected node ids before new manifest tests; every id appears exactly once in the manifest.

- [ ] **Step 5: Reconcile on ordinary full collection**

In `pytest_collection_modifyitems`, run manifest reconciliation only when pytest is performing an ordinary full collection. Focused path/node invocations and explicit gate/tier selections validate only the relevant subset, so `pytest tests/test_x.py` remains usable.

- [ ] **Step 6: Run GREEN**

```bash
.venv/bin/python -m pytest tests/test_scope_manifest.py tests/test_detail_gate_selection.py -q
.venv/bin/python -m pytest --collect-only -q
```

Expected: scope tests pass; collection increases only by the new manifest test nodes and reconciliation reports no drift after the manifest is refreshed for them.

- [ ] **Step 7: Commit**

```bash
git add tests/scope_manifest.py tests/test_scope_manifest.py \
  tests/test_scope_manifest.csv tests/conftest.py
git commit -m "test: classify platform and build accuracy scopes"
```

---

### Task 2: Add inner/release build cadence without weakening current-model validation

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_detail_gate_selection.py`
- Modify: `tests/test_family_birdhouse_report.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Extends: `pytest.mark.detail_gate(slug, contracts=..., cadence="inner"|"release")`.
- Extends: `pytest --detail-gate SLUG --detail-cadence inner|release`.
- `inner` selects only inner nodes and requires the existing nine build contracts.
- `release` selects both inner and release nodes and additionally requires `documents`.

- [ ] **Step 1: Write RED selection and completeness tests**

```python
def test_inner_gate_excludes_release_documents():
    inner = item("family_birdhouse", contracts=("compile",), cadence="inner")
    release = item("family_birdhouse", contracts=("documents",), cadence="release")
    selected, _deselected, contracts = _detail_gate_selection(
        [inner, release], "family_birdhouse", cadence="inner"
    )
    assert selected == [inner]
    assert contracts == {"compile"}


def test_release_gate_includes_inner_and_requires_documents():
    selected, _deselected, contracts = _detail_gate_selection(
        complete_inner_items() + [
            item("family_birdhouse", contracts=("documents",), cadence="release")
        ],
        "family_birdhouse",
        cadence="release",
    )
    _require_complete_detail_gate(
        "family_birdhouse", selected, contracts, cadence="release"
    )
    assert "documents" in contracts
```

Also test invalid cadence, `--detail-gate` combined with a platform tier, and a release gate missing documents.

- [ ] **Step 2: Run RED**

```bash
.venv/bin/python -m pytest tests/test_detail_gate_selection.py -q
```

Expected: cadence argument/marker validation is not implemented.

- [ ] **Step 3: Extend the pure marker parser**

Accept only `contracts` and optional `cadence`; default existing markers to `inner` for compatibility. `release` selection includes both cadence values. Preserve the existing required-contract vocabulary and fail messages.

- [ ] **Step 4: Mark the existing birdhouse package fixture as release evidence**

```python
pytestmark = pytest.mark.detail_gate(
    "family_birdhouse",
    contracts=("documents",),
    cadence="release",
)
```

The existing module-scoped `package` fixture remains the single package generation. Do not create a second package test.

- [ ] **Step 5: Verify the generic current-model collision check stays in the inner gate**

Run:

```bash
.venv/bin/python -m pytest --detail-gate family_birdhouse \
  --detail-cadence inner --collect-only -q
```

Expected: includes the birdhouse E2E module whose fixture calls `detail.validate()`; excludes `test_family_birdhouse_report.py`.

Run:

```bash
.venv/bin/python -m pytest --detail-gate family_birdhouse \
  --detail-cadence release --collect-only -q
```

Expected: inner nodes plus all 11 package assertions.

- [ ] **Step 6: Run the two real gates**

```bash
.venv/bin/python -m pytest --detail-gate family_birdhouse \
  --detail-cadence inner -q --durations=20
.venv/bin/python -m pytest --detail-gate family_birdhouse \
  --detail-cadence release -q --durations=20
```

Expected: both pass; release generates the preview package once.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml tests/conftest.py tests/test_detail_gate_selection.py \
  tests/test_family_birdhouse_report.py
git commit -m "test: separate build inner and release cadence"
```

---

### Task 3: Make baseline self-tests pure and retain one live integration round trip

**Files:**
- Modify: `scripts/regen_baselines.py`
- Create: `tests/test_baseline_integrity_unit.py`
- Modify: `tests/test_baselines.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `stale_baseline_names(generated_dir, source_dir) -> tuple[str, ...]`.
- Produces: `merge_site_divergence(pairs, source_dir) -> tuple[dict, list, list]`.
- Keeps: `_compute_site_divergence(source_dir)` as the live wrapper around `bl.site_divergence_pairs()`.

- [ ] **Step 1: Write RED pure directory-comparison tests**

```python
def test_tampered_plain_baseline_is_named_without_regeneration(tmp_path):
    committed = tmp_path / "committed"
    generated = tmp_path / "generated"
    committed.mkdir(); generated.mkdir()
    (committed / "detail_counts.json").write_text('{"count": 4}\n')
    (generated / "detail_counts.json").write_text('{"count": 5}\n')
    assert stale_baseline_names(generated, committed) == (
        "detail_counts.json",
    )


def test_annotated_merge_preserves_notes_and_flags_new_and_removed(tmp_path):
    (tmp_path / "site_divergence.json").write_text(json.dumps({
        "findings": [
            {"check": "old", "subject": "gone", "note": "retired note"},
            {"check": "keep", "subject": "same", "note": "real reason"},
        ]
    }))
    data, new, removed = merge_site_divergence(
        [
            {"check": "keep", "subject": "same"},
            {"check": "new", "subject": "appeared"},
        ],
        tmp_path,
    )
    assert data["findings"][0]["note"] == "real reason"
    assert data["findings"][1]["note"] == TODO_NOTE
    assert new == [("new", "appeared")]
    assert removed == [("old", "gone")]
```

- [ ] **Step 2: Run RED**

```bash
.venv/bin/python -m pytest tests/test_baseline_integrity_unit.py -q
```

Expected: missing pure helper imports.

- [ ] **Step 3: Extract the pure helpers and use them in `--check`**

`stale_baseline_names` compares the union of JSON basenames in both directories, so missing and extra surfaces are named. `merge_site_divergence` never imports, compiles, or validates a model. `_compute_site_divergence` becomes:

```python
def _compute_site_divergence(source_dir):
    return merge_site_divergence(bl.site_divergence_pairs(), source_dir)
```

- [ ] **Step 4: Replace the two heavy tamper tests with pure unit tests**

Delete the parametrized live-regeneration tamper path from `tests/test_baselines.py`. Keep committed surface/note policy there. Move `--check` behavior to a unit test that monkeypatches `regenerate` to write tiny JSON fixtures; assert both current exit `0` and stale exit `1` without CadQuery.

- [ ] **Step 5: Mark the one live round trip as platform integration**

```python
@pytest.mark.platform_integration
def test_regen_round_trip_reproduces_committed_baselines():
    ...
```

Use `stale_baseline_names` after one actual `regenerate` call. Do not retain a second live `regen.main(["--check"])` test.

- [ ] **Step 6: Verify unit and live behavior separately**

```bash
.venv/bin/python -m pytest tests/test_baseline_integrity_unit.py -q --durations=20
.venv/bin/python -m pytest tests/test_baselines.py -q --durations=20
```

Expected: all unit nodes complete without model compilation; exactly one node performs full regeneration.

- [ ] **Step 7: Commit**

```bash
git add scripts/regen_baselines.py tests/test_baseline_integrity_unit.py \
  tests/test_baselines.py pyproject.toml
git commit -m "test: isolate baseline integrity from live CAD regeneration"
```

---

### Task 4: Add explicit platform integration and audit tiers

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_scope_manifest.py`
- Modify: `tests/test_affected_region.py`
- Modify: `tests/test_bbox_prefilter.py`
- Modify: `tests/test_revision_identity.py`
- Modify: `pyproject.toml`
- Update: `tests/test_scope_manifest.csv`

**Interfaces:**
- Produces: `pytest --platform-tier integration|audit`.
- Registers: `platform_integration`, `platform_audit`.

- [ ] **Step 1: Write RED tier-selection tests**

```python
def test_platform_audit_selection_excludes_build_and_integration_nodes():
    rows = fixture_records(
        platform_unit="tests/test_a.py::test_unit",
        platform_integration="tests/test_b.py::test_integration",
        platform_audit="tests/test_c.py::test_audit",
        build_inner="tests/test_d.py::test_build",
    )
    assert [r.nodeid for r in platform_nodes(rows, "audit")] == [
        "tests/test_c.py::test_audit"
    ]
```

Test unknown tier, zero selected nodes, and mutual exclusion with `--detail-gate`.

- [ ] **Step 2: Implement fast source prefiltering from manifest module paths**

When a platform tier is selected, `pytest_ignore_collect` should admit only Python test modules containing selected manifest node ids. This avoids importing `test_affected_region.py` during unrelated build gates and avoids its module-level platform compilation cost.

- [ ] **Step 3: Mark exhaustive bbox oracles as audit**

Mark only:

- `test_rock_anchor_prefilter_agrees_with_unfiltered`
- `test_platform_prefilter_agrees_with_unfiltered`

Keep the five tiny threshold, accounting, and multi-solid regression tests as ordinary platform unit tests.

- [ ] **Step 4: Mark whole-world invalidation suites as audit**

Use module-level `pytestmark = pytest.mark.platform_audit` in:

- `tests/test_affected_region.py`
- `tests/test_revision_identity.py`

These tests intentionally rebuild alternate worlds; no named build gate may select them.

- [ ] **Step 5: Consolidate only duplicate affected-region variants**

Preserve the six distinct edit classes in the soundness matrix. Fold duplicate assertions for the already-built `beam_len`, `bolt_dia`, and `n_steps=1` variants into their corresponding parametrized case result rather than compiling those exact variants again in separate tests. Keep distinct assertions for:

- unattributed-finding floor (`beam_len`);
- broader-region size (`bolt_dia`);
- vanished member from old graph (`n_steps=1`).

Do not remove the one-sided symmetry regression or replace whole-world truth with a mocked diff.

- [ ] **Step 6: Verify candidate selection**

```bash
.venv/bin/python -m pytest --platform-tier audit --collect-only -q
.venv/bin/python -m pytest --platform-tier integration --collect-only -q
.venv/bin/python -m pytest --detail-gate family_birdhouse \
  --detail-cadence release --collect-only -q
```

Expected: exhaustive bbox and affected/revision nodes appear only in audit; live baseline roundtrip appears only in integration; neither appears in birdhouse release.

- [ ] **Step 7: Run focused platform evidence**

```bash
.venv/bin/python -m pytest tests/test_bbox_prefilter.py -q --durations=20
.venv/bin/python -m pytest tests/test_affected_region.py -q --durations=30
.venv/bin/python -m pytest tests/test_revision_identity.py -q --durations=30
```

Expected: all existing correctness assertions pass. Record counts and timings; no timing threshold assertion.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml tests/conftest.py tests/test_scope_manifest.py \
  tests/test_scope_manifest.csv tests/test_affected_region.py \
  tests/test_bbox_prefilter.py tests/test_revision_identity.py
git commit -m "test: separate platform integration and exhaustive audits"
```

---

### Task 5: Remove duplicate work from slow current-build tests

**Files:**
- Modify: `tests/test_site_overview.py`
- Modify: `tests/test_consolidated_coverage.py`
- Modify: `tests/test_platform_detail.py`
- Update: `tests/test_scope_manifest.csv`

- [ ] **Step 1: Pin current duplicate call counts with focused RED tests**

Add pure fixture-helper tests or monkeypatched wrappers that demonstrate:

- site-overview release evidence invokes the real render path once and the reuse path once, while both output-size and content assertions consume the same images;
- consolidated coverage builds each accepted detail once and the site once per module context;
- current default platform validation is computed once for all read-only default-platform assertions.

Use counters, not wall time.

- [ ] **Step 2: Run RED**

```bash
.venv/bin/python -m pytest \
  tests/test_site_overview.py \
  tests/test_consolidated_coverage.py \
  tests/test_platform_detail.py -q --durations=30
```

Expected: newly added call-count assertions expose the duplicate paths before refactoring.

- [ ] **Step 3: Create one module-scoped rendered-overview fixture**

The fixture owns a module scratch directory, temporarily redirects `report_mod.RENDERS`, calls `process_site_overview(details)` twice to prove miss then hit, and returns both results. The size test only sums the already-returned image URIs.

- [ ] **Step 4: Share one consolidated coverage context**

```python
@pytest.fixture(scope="module")
def coverage_context(report_mod):
    details = report_mod.load_details()
    detail_reports = {name: detail.validate() for name, detail in details.items()}
    site = report_mod.load_site()
    return details, detail_reports, site, site.validate()
```

Project `coverage_html` and the verdict headline from this same context.

- [ ] **Step 5: Share one immutable accepted default platform**

```python
@pytest.fixture(scope="module")
def accepted_platform():
    detail = _platform()
    report = detail.validate()
    _assert_no_fail_only_honest_unknowns(report)
    return detail, report
```

Only read-only default-model assertions consume it. Parameter-family tests keep their own explicit variants and remain platform-scoped where the audited manifest classifies them as counterfactual.

- [ ] **Step 6: Run GREEN and compare call counts/timings**

```bash
.venv/bin/python -m pytest \
  tests/test_site_overview.py \
  tests/test_consolidated_coverage.py \
  tests/test_platform_detail.py -q --durations=30
```

Expected: all assertions pass; duplicate call counters are one per intended accepted model/render context. Record before/after duration observations in `.superpowers/sdd/test-scope-gate-verification.md`.

- [ ] **Step 7: Commit**

```bash
git add tests/test_site_overview.py tests/test_consolidated_coverage.py \
  tests/test_platform_detail.py tests/test_scope_manifest.csv \
  .superpowers/sdd/test-scope-gate-verification.md
git commit -m "test: reuse accepted build evidence within owner gates"
```

---

### Task 6: Document the decision table and verify the complete policy

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `docs/superpowers/specs/2026-07-15-test-scope-timing-audit.md`
- Modify: `.superpowers/sdd/test-scope-gate-verification.md`
- Update: `tests/test_scope_manifest.csv`

- [ ] **Step 1: Replace blanket test advice with exact commands**

Document:

```bash
# Accepted model, normal validation/collisions, fabrication/BOM/governance
pytest --detail-gate family_birdhouse --detail-cadence inner -q

# Same build plus its cold package/document release checks
pytest --detail-gate family_birdhouse --detail-cadence release -q

# Real shared-system integrations, including one live baseline regeneration
pytest --platform-tier integration -q

# Exhaustive/whole-world oracles; never part of document production
pytest --platform-tier audit -q

# Everything; shared-platform integration/release only
pytest -q -n 4
```

Add the explicit rule: a current-model collision check is build accuracy; an exhaustive collision-algorithm equivalence test is platform audit.

- [ ] **Step 2: Run scope-manifest and collection verification**

```bash
.venv/bin/python -m pytest tests/test_scope_manifest.py \
  tests/test_detail_gate_selection.py -q
.venv/bin/python -m pytest --collect-only -q
```

Expected: every collected node classified exactly once; no retired manifest ids.

- [ ] **Step 3: Run the birdhouse gates**

```bash
.venv/bin/python -m pytest --detail-gate family_birdhouse \
  --detail-cadence inner -q --durations=30
.venv/bin/python -m pytest --detail-gate family_birdhouse \
  --detail-cadence release -q --durations=30
```

Expected: both pass; no bbox exhaustive oracle, affected-region mutation, revision whole-world test, or live baseline regeneration is collected.

- [ ] **Step 4: Run platform integration and audit gates**

```bash
.venv/bin/python -m pytest --platform-tier integration -q -n 4 --durations=50
.venv/bin/python -m pytest --platform-tier audit -q -n 4 --durations=50
```

Expected: both pass. Record the exhaustive platform-pair oracle and affected-region mutations here, not in any build gate.

- [ ] **Step 5: Run the unfiltered full suite**

```bash
.venv/bin/python -m pytest -q -n 4 --durations=100 \
  --junitxml=/tmp/plumb-test-scope-final.xml
```

Expected: all tests pass with only the existing intentional skips/xfail. Refresh the audit CSV/report from this JUnit artifact, reconcile every current node, and list any remaining build-accuracy node over ten seconds with its owner/cadence.

- [ ] **Step 6: Self-review**

Verify:

- every requirement in the global constraints has direct test evidence;
- no `TODO`, `pass`, placeholder owner, or unclassified node remains;
- every build node’s cadence is `inner` or `release`;
- every platform node over ten seconds is `integration` or `audit`, not `unit`;
- the birdhouse normal validation/collision evidence remains selected;
- the 7,626-pair oracle and beam mutations are absent from both birdhouse gates;
- no generated product document imports or invokes pytest.

- [ ] **Step 7: Commit**

```bash
git add README.md CLAUDE.md tests/test_scope_manifest.csv \
  docs/superpowers/specs/2026-07-15-test-scope-timing-audit.md \
  .superpowers/sdd/test-scope-gate-verification.md
git commit -m "docs: define Plumb build and platform test cadence"
```

---

## Completion criteria

- Every collected test node has one explicit runtime classification matching the refreshed audit.
- A generic accepted-model validation node, including normal collision checking, is selected by the named build gate.
- Artificial mutations, fake corruptions, the 7,626-pair exact oracle, and whole-world invalidation proofs are absent from every named build gate.
- Fake baseline-corruption unit tests perform zero live model compilations; exactly one platform-integration node performs a full live baseline regeneration.
- The birdhouse inner and release gates both pass; its release package is generated once.
- Platform integration, platform audit, and the unfiltered full suite all pass.
- The updated audit records every remaining document/build node over ten seconds with an owner and justified cadence.
