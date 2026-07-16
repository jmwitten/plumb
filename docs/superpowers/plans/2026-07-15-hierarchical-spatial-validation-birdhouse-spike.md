# Hierarchical Spatial Validation Birdhouse Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure whether a conservative one-level birdhouse hierarchy can preserve exactly the same collision candidates as Plumb's flat bounding-box sweep while replacing tens of thousands of remote leaf-pair PASS records with compact group-separation certificates.

**Architecture:** Compile the real 28-part family birdhouse once per geometry variant, extract immutable leaf records from production geometry, and create translated synthetic instances without rebuilding their solids. A flat leaf-pair traversal remains the independent candidate oracle. A one-level hierarchy either certifies two birdhouse envelopes as separated or descends to the unchanged leaf bounding-box rule. Internal certificates are keyed by geometry, relative transforms, tolerances, and an algorithm version so unchanged instances can reuse them after one roof edit. This is a measurement-only platform-audit spike: it does not modify production validation, evidence, caches, or document gates.

**Tech Stack:** Python 3.12, pytest 9, CadQuery 2.8/OCCT, existing `detailgen` compiler and validation primitives, stdlib `argparse`, `dataclasses`, `hashlib`, `json`, `math`, `pathlib`, and `time.perf_counter`.

## Global Constraints

- Complete Tasks 1–4 of `2026-07-15-test-scope-and-gate-layering.md` first, so this test is registered as `platform_audit` and cannot enter any document/build gate.
- Use the real `details/family_birdhouse.spec.yaml`; do not create a simplified proxy model.
- Compile the base birdhouse once and the edited variant once. Rigid repetitions must translate extracted records and lazily translated `Placed` handles, not rebuild CadQuery solids.
- Use conservative BREP-derived axis-aligned bounding boxes. A separated box is proof of disjointness; an overlapping box only causes descent.
- Treat the flat bounding-candidate set as the soundness oracle. The hierarchical candidate set must equal it exactly in every scenario.
- Keep OpenCascade's existing exact interference operation unchanged and invoke it only for the bounded deliberate-overlap candidate set.
- A connection graph may explain an allowed contact but may never eliminate a spatial pair.
- Do not modify `validate_assembly`, `ValidationReport`, `EvidenceGraph`, persistent caches, generated documents, or product specs.
- Do not add wall-clock assertions. Timings are informational output separated from deterministic results.
- Write generated JSON only below a caller-supplied output directory, default `/tmp`; never write to `details/`, `tests/baselines/`, `outputs/`, or the JoelBrain vault.
- Stop after publishing the spike results. A passing experiment requires a separate production-design decision before integration.

---

## File map

- `scripts/spatial_hierarchy_spike.py` — read-only birdhouse extraction, translated layouts, flat oracle, hierarchical traversal, certificate projection, bounded exact checks, and CLI.
- `tests/test_spatial_hierarchy_spike.py` — deterministic extraction, scaling, soundness, compact accounting, invalidation, overlap, and serialization tests.
- `.superpowers/sdd/spatial-hierarchy-spike-results.md` — measured work counts, timings, exact-check scope, deterministic-output verification, and go/no-go result.
- `tests/test_scope_manifest.csv` — add all new nodes as `platform`, owner `plumb-platform`, cadence `audit` after the tests have their final collected nodeids.

---

### Task 1: Extract deterministic leaf records from the real birdhouse

**Files:**
- Create: `scripts/spatial_hierarchy_spike.py`
- Create: `tests/test_spatial_hierarchy_spike.py`

**Production APIs used read-only:**
- `detailgen.spec.compiler.compile_spec_file(path, overrides=...)`
- `detailgen.validation.checks._AABB`, `_part_bbox`, `_aabb_gap`
- `detailgen.core.buildinfo.local_geometry_digest`, `relative_transform_digest`
- `detailgen.core.frame.Frame`
- `detailgen.assemblies.assembly.Placed`

**Interfaces introduced in the spike:**
- `LeafBound(instance_id, authored_id, qualified_id, box, geometry_digest, relative_transform_digest, placed_factory)`
- `GroupNode(instance_id, leaves, box, content_key)`
- `compile_birdhouse_variant(spec_path, overrides=None) -> BirdhouseVariant`
- `translate_variant(variant, instance_id, offset) -> GroupNode`
- `union_boxes(boxes) -> _AABB`

- [ ] **Step 1: Write RED extraction and box tests**

```python
pytestmark = pytest.mark.platform_audit


@pytest.fixture(scope="module")
def base_variant():
    return compile_birdhouse_variant(BIRDHOUSE_SPEC)


def test_real_birdhouse_extracts_28_unique_deterministic_leaves(base_variant):
    assert len(base_variant.leaves) == 28
    assert len({leaf.authored_id for leaf in base_variant.leaves}) == 28
    assert [leaf.authored_id for leaf in base_variant.leaves] == sorted(
        leaf.authored_id for leaf in base_variant.leaves
    )
    assert all(leaf.geometry_digest for leaf in base_variant.leaves)


def test_group_box_conservatively_contains_every_leaf(base_variant):
    group = translate_variant(base_variant, "birdhouse_00", (0.0, 0.0, 0.0))
    assert all(box_contains(group.box, leaf.box) for leaf in group.leaves)


def test_translation_preserves_content_key_and_moves_every_bound(base_variant):
    origin = translate_variant(base_variant, "birdhouse_00", (0.0, 0.0, 0.0))
    moved = translate_variant(base_variant, "birdhouse_01", (1000.0, 0.0, 0.0))
    assert moved.content_key == origin.content_key
    assert moved.box.xmin == pytest.approx(origin.box.xmin + 1000.0)
```

- [ ] **Step 2: Run the focused tests and confirm the missing-module failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_spatial_hierarchy_spike.py -q
```

Expected: collection fails because `scripts.spatial_hierarchy_spike` does not yet exist.

- [ ] **Step 3: Implement immutable records, conservative box helpers, and one-time compilation**

```python
ALGORITHM_VERSION = "birdhouse-hierarchy-spike-v1"


def union_boxes(boxes: Sequence[_AABB]) -> _AABB:
    if not boxes:
        raise ValueError("cannot union an empty box collection")
    return _AABB(
        xmin=min(box.xmin for box in boxes),
        xmax=max(box.xmax for box in boxes),
        ymin=min(box.ymin for box in boxes),
        ymax=max(box.ymax for box in boxes),
        zmin=min(box.zmin for box in boxes),
        zmax=max(box.zmax for box in boxes),
    )


def translate_box(box: _AABB, offset: tuple[float, float, float]) -> _AABB:
    dx, dy, dz = offset
    return _AABB(
        box.xmin + dx, box.xmax + dx,
        box.ymin + dy, box.ymax + dy,
        box.zmin + dz, box.zmax + dz,
    )
```

Build the content key from sorted `(authored_id, local_geometry_digest, relative_transform_digest)` rows plus the tolerance fingerprint and `ALGORITHM_VERSION`. Exclude absolute translation and instance id. Store enough immutable source data to construct a translated `Placed` only when the bounded exact-check scenario requests it.

- [ ] **Step 4: Run focused tests and commit the extraction seam**

Run:

```bash
.venv/bin/python -m pytest tests/test_spatial_hierarchy_spike.py -q
git add scripts/spatial_hierarchy_spike.py tests/test_spatial_hierarchy_spike.py
git commit -m "test: extract birdhouse hierarchy records"
```

Expected: extraction tests pass; no product or production-validation files are changed.

---

### Task 2: Build the independent flat oracle and separated hierarchy

**Files:**
- Modify: `scripts/spatial_hierarchy_spike.py`
- Modify: `tests/test_spatial_hierarchy_spike.py`

**Interfaces:**
- `build_separated_layout(variant, count, threshold) -> tuple[GroupNode, ...]`
- `flat_candidate_oracle(groups, threshold) -> frozenset[PairId]`
- `traverse_hierarchy(groups, threshold, certificate_cache=None) -> TraversalResult`
- `GroupSeparationCertificate(left_group, right_group, left_box, right_box, threshold, covered_pairs)`

- [ ] **Step 1: Write RED scaling and exact-candidate-equivalence tests**

```python
@pytest.mark.parametrize(
    ("count", "parts", "all_pairs", "internal_pairs", "remote_pairs"),
    [
        (1, 28, 378, 378, 0),
        (4, 112, 6_216, 1_512, 4_704),
        (16, 448, 100_128, 6_048, 94_080),
    ],
)
def test_separated_scaling_matrix_has_complete_sound_accounting(
    base_variant, count, parts, all_pairs, internal_pairs, remote_pairs
):
    groups = build_separated_layout(base_variant, count, DEFAULT.bbox_prefilter_gap)
    flat = flat_candidate_oracle(groups, DEFAULT.bbox_prefilter_gap)
    result = traverse_hierarchy(groups, DEFAULT.bbox_prefilter_gap)

    assert sum(len(group.leaves) for group in groups) == parts
    assert result.total_pair_universe == all_pairs
    assert result.internal_pair_universe == internal_pairs
    assert result.remote_pair_universe == remote_pairs
    assert result.candidate_pairs == flat
    assert result.accounted_pairs == all_pairs


def test_sixteen_separated_groups_certify_all_remote_pairs_without_descent(base_variant):
    groups = build_separated_layout(base_variant, 16, DEFAULT.bbox_prefilter_gap)
    result = traverse_hierarchy(groups, DEFAULT.bbox_prefilter_gap)
    assert result.group_comparisons == 120
    assert result.group_certified_remote_pairs == 94_080
    assert result.descended_remote_pairs == 0
    assert len(result.separation_certificates) == 120
```

- [ ] **Step 2: Confirm the new assertions fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_spatial_hierarchy_spike.py -q
```

Expected: failures name the missing layout/oracle/traversal interfaces.

- [ ] **Step 3: Implement envelope-derived spacing and the flat oracle**

Derive grid stride from the live envelope, configured threshold, and a fixed 1 mm proof margin:

```python
stride_x = envelope_width + threshold + 1.0
stride_y = envelope_depth + threshold + 1.0
columns = math.ceil(math.sqrt(count))
offset = ((index % columns) * stride_x, (index // columns) * stride_y, 0.0)
```

The oracle enumerates every unique qualified leaf pair and includes the canonical pair id exactly when `_aabb_gap(left.box, right.box) <= threshold`. It returns candidate ids only, not individual PASS findings.

- [ ] **Step 4: Implement one-level group separation and descent**

For each group pair:

```python
remote_count = len(left.leaves) * len(right.leaves)
if _aabb_gap(left.box, right.box) > threshold:
    separation_certificates.append(
        GroupSeparationCertificate(..., covered_pairs=remote_count)
    )
else:
    descended_remote_pairs += remote_count
    candidates.update(leaf_candidates(left.leaves, right.leaves, threshold))
```

Internal candidate sets come from the same leaf bounding rule and are eligible for certificate reuse in Task 3. Sort every externally visible group, certificate, and candidate collection before projection.

- [ ] **Step 5: Verify the exact scaling laws and commit**

Run:

```bash
.venv/bin/python -m pytest tests/test_spatial_hierarchy_spike.py -q
git add scripts/spatial_hierarchy_spike.py tests/test_spatial_hierarchy_spike.py
git commit -m "test: compare flat and hierarchical birdhouse candidates"
```

Expected: 1/4/16 candidate sets match the flat oracle exactly; 120 certificates cover all 94,080 remote pairs in the 16-instance separated layout.

---

### Task 3: Prove compact accounting and one-roof-edit certificate reuse

**Files:**
- Modify: `scripts/spatial_hierarchy_spike.py`
- Modify: `tests/test_spatial_hierarchy_spike.py`

**Interfaces:**
- `InternalCertificate(key, leaf_count, covered_pairs, candidate_pairs)`
- `InternalCertificateCache`
- `TraversalResult.accounted_pairs`
- `build_roof_edit_layout(base_variant, edited_variant, count=16, edited_index=...)`

- [ ] **Step 1: Write RED accounting and invalidation tests**

```python
def test_compact_coverage_identity_equals_pair_universe(base_variant):
    result = traverse_hierarchy(
        build_separated_layout(base_variant, 16, DEFAULT.bbox_prefilter_gap),
        DEFAULT.bbox_prefilter_gap,
    )
    assert (
        result.reused_internal_pairs
        + result.recomputed_internal_pairs
        + result.group_certified_remote_pairs
        + result.descended_remote_pairs
    ) == 100_128
    assert result.individual_remote_pass_records == 0


def test_one_roof_edit_reuses_15_internal_certificates_and_recomputes_one(
    base_variant, edited_variant
):
    cache = InternalCertificateCache()
    traverse_hierarchy(
        build_separated_layout(base_variant, 16, DEFAULT.bbox_prefilter_gap),
        DEFAULT.bbox_prefilter_gap,
        cache,
    )
    edited_groups = build_roof_edit_layout(base_variant, edited_variant)
    result = traverse_hierarchy(edited_groups, DEFAULT.bbox_prefilter_gap, cache)

    assert edited_variant.content_key != base_variant.content_key
    assert result.reused_internal_group_count == 15
    assert result.recomputed_internal_group_count == 1
    assert result.reconsidered_group_relationships == 120
    assert result.candidate_pairs == flat_candidate_oracle(
        edited_groups, DEFAULT.bbox_prefilter_gap
    )
```

The `edited_variant` module fixture calls `compile_birdhouse_variant` exactly once with `overrides={"roof_len": 9.5}`; the spec's declared inch unit interprets that numeric override as 9.5 inches. The base fixture uses the authored 7.5-inch value.

- [ ] **Step 2: Run focused tests and inspect the intended reuse failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_spatial_hierarchy_spike.py -q
```

Expected: the new cache/reuse assertions fail until certificate storage exists.

- [ ] **Step 3: Implement content-addressed internal certificates**

An internal certificate key must include:

```text
algorithm version
+ bbox-prefilter threshold/tolerance fingerprint
+ sorted authored ids
+ each local geometry digest
+ each relative transform digest
```

It must not include absolute group translation or synthetic instance id. Cache candidate ids in authored-id space and qualify them for the requesting instance on reuse. The first base group computes the certificate; equivalent translated groups reuse it. The edited roof produces a new key and exactly one new certificate.

- [ ] **Step 4: Reconsider every edited group relationship without discarding valid internal certificates**

Rebuild the edited group's union box and execute all 120 group relationships fresh for the edited layout. Reuse applies only to group-internal evidence; it must not imply that remote separation relationships touching the edit remain valid.

- [ ] **Step 5: Verify accounting, invalidation, and commit**

Run:

```bash
.venv/bin/python -m pytest tests/test_spatial_hierarchy_spike.py -q
git add scripts/spatial_hierarchy_spike.py tests/test_spatial_hierarchy_spike.py
git commit -m "test: prove birdhouse certificate reuse and accounting"
```

Expected: every traversal satisfies the accounting identity, the roof edit reuses 15 internal group certificates, recomputes one, and still equals the fresh flat oracle.

---

### Task 4: Force descent and run only bounded exact collision checks

**Files:**
- Modify: `scripts/spatial_hierarchy_spike.py`
- Modify: `tests/test_spatial_hierarchy_spike.py`

**Production API used unchanged:**
- `detailgen.validation.checks.check_interference`

**Interfaces:**
- `build_overlapping_layout(variant, threshold) -> tuple[GroupNode, ...]`
- `materialize_translated_placed(leaf) -> Placed`
- `run_exact_candidates(candidate_pairs, leaf_index) -> ExactCheckResult`

- [ ] **Step 1: Write RED descent and exact-check-bound tests**

```python
def test_overlapping_groups_descend_without_losing_flat_candidates(base_variant):
    groups = build_overlapping_layout(base_variant, DEFAULT.bbox_prefilter_gap)
    flat = flat_candidate_oracle(groups, DEFAULT.bbox_prefilter_gap)
    result = traverse_hierarchy(groups, DEFAULT.bbox_prefilter_gap)
    assert result.descended_group_pairs == 1
    assert result.descended_remote_pairs == 28 * 28
    assert result.candidate_pairs == flat
    assert result.candidate_pairs


def test_exact_interference_is_called_only_for_hierarchy_candidates(
    base_variant, monkeypatch
):
    groups = build_overlapping_layout(base_variant, DEFAULT.bbox_prefilter_gap)
    result = traverse_hierarchy(groups, DEFAULT.bbox_prefilter_gap)
    calls = []
    monkeypatch.setattr(spike, "check_interference", recording_check(calls))
    exact = run_exact_candidates(result.candidate_pairs, index_leaves(groups))
    assert len(calls) == len(result.candidate_pairs)
    assert set(exact.checked_pairs) == set(result.candidate_pairs)
    assert len(calls) < 28 * 28
```

- [ ] **Step 2: Confirm descent tests fail before overlap support exists**

Run:

```bash
.venv/bin/python -m pytest tests/test_spatial_hierarchy_spike.py -q
```

Expected: missing overlap-layout/materialization functions or zero descended pairs.

- [ ] **Step 3: Implement an envelope-derived overlap, not a magic coordinate**

Start from two separated groups and translate the second toward the first so their group envelopes overlap by `max(threshold + 1.0, 0.05 * envelope_width)`. Assert the resulting group gap is at most the threshold before running either traversal.

- [ ] **Step 4: Lazily construct translated `Placed` handles and invoke the existing narrow phase**

Compose the instance translation with each source part's original world frame and preserve its component, authored placement metadata, and qualified id. Materialize only leaves participating in candidate pairs. Pass every candidate to the existing `check_interference` function with production tolerance/expected-overlap semantics; record checked pair ids and unexpected-overlap signatures without changing the function.

- [ ] **Step 5: Verify the bounded negative case and commit**

Run:

```bash
.venv/bin/python -m pytest tests/test_spatial_hierarchy_spike.py -q
git add scripts/spatial_hierarchy_spike.py tests/test_spatial_hierarchy_spike.py
git commit -m "test: bound exact checks after hierarchy descent"
```

Expected: hierarchy and flat oracle candidates are identical, only one 784-pair remote cross-product is descended, and exact calls equal the much smaller candidate count.

---

### Task 5: Add deterministic JSON evidence, register audit scope, and publish measurements

**Files:**
- Modify: `scripts/spatial_hierarchy_spike.py`
- Modify: `tests/test_spatial_hierarchy_spike.py`
- Modify: `tests/test_scope_manifest.csv`
- Create: `.superpowers/sdd/spatial-hierarchy-spike-results.md`

**CLI:**

```bash
.venv/bin/python scripts/spatial_hierarchy_spike.py --out /tmp/plumb-spatial-hierarchy-spike
```

- [ ] **Step 1: Write RED serialization and deterministic-projection tests**

```python
def test_json_projection_separates_deterministic_evidence_from_timings(result):
    payload = project_result(result)
    assert set(payload) == {"evidence", "timings_seconds"}
    assert payload["evidence"]["accounting"]["total_pair_universe"] == 100_128
    assert payload["evidence"]["candidate_pairs"] == sorted(
        payload["evidence"]["candidate_pairs"]
    )


def test_deterministic_evidence_is_byte_identical_across_runs(tmp_path, base_variant):
    first = write_scenario_json(run_all_scenarios(base_variant), tmp_path / "one")
    second = write_scenario_json(run_all_scenarios(base_variant), tmp_path / "two")
    assert deterministic_bytes(first) == deterministic_bytes(second)
```

- [ ] **Step 2: Implement the CLI and compact JSON projection**

Project assembly/algorithm fingerprints, coverage counts, certificate counts and estimated serialized size, sorted candidate pairs, unexpected overlaps, and accounting anomalies under `evidence`. Put compile, flat traversal, hierarchy traversal, exact checking, and projection timings only under `timings_seconds`.

Use `json.dumps(..., sort_keys=True, indent=2)` plus a final newline. The deterministic comparison must remove only the top-level timing object; it may not normalize or discard evidence fields.

- [ ] **Step 3: Collect final nodeids and register every one as platform audit**

Run:

```bash
.venv/bin/python -m pytest tests/test_spatial_hierarchy_spike.py --collect-only -q
```

Add each exact collected nodeid to `tests/test_scope_manifest.csv` with:

```text
category=platform
owner=plumb-platform
cadence=audit
rationale=measurement-only hierarchy soundness oracle; never a document build gate
```

Then run the manifest reconciliation tests from the test-scope plan.

- [ ] **Step 4: Generate two independent outputs and verify deterministic evidence**

Run:

```bash
rm -rf /tmp/plumb-spatial-hierarchy-spike-a /tmp/plumb-spatial-hierarchy-spike-b
.venv/bin/python scripts/spatial_hierarchy_spike.py --out /tmp/plumb-spatial-hierarchy-spike-a
.venv/bin/python scripts/spatial_hierarchy_spike.py --out /tmp/plumb-spatial-hierarchy-spike-b
jq -S 'del(.timings_seconds)' /tmp/plumb-spatial-hierarchy-spike-a/results.json > /tmp/plumb-spatial-a-deterministic.json
jq -S 'del(.timings_seconds)' /tmp/plumb-spatial-hierarchy-spike-b/results.json > /tmp/plumb-spatial-b-deterministic.json
diff -u /tmp/plumb-spatial-a-deterministic.json /tmp/plumb-spatial-b-deterministic.json
```

Expected: `diff` is empty.

- [ ] **Step 5: Run focused and scope-boundary verification**

Run:

```bash
.venv/bin/python -m pytest tests/test_spatial_hierarchy_spike.py -q --durations=0
.venv/bin/python -m pytest tests/test_scope_manifest.py tests/test_detail_gate_selection.py -q
.venv/bin/python -m pytest --detail-build family_birdhouse --detail-cadence inner --collect-only -q | tee /tmp/birdhouse-inner-nodes.txt
! grep -q 'test_spatial_hierarchy_spike' /tmp/birdhouse-inner-nodes.txt
.venv/bin/python -m pytest --platform-tier audit --collect-only -q | grep 'test_spatial_hierarchy_spike'
```

Expected: spike tests pass, the manifest is complete, no spike node enters the birdhouse build gate, and every spike node is available through the platform-audit selector.

- [ ] **Step 6: Record measurements and an explicit decision**

Create `.superpowers/sdd/spatial-hierarchy-spike-results.md` with:

- base and edited compile time, reported separately;
- flat and hierarchical traversal time for 1/4/16 instances;
- exact candidate count and exact-check time for the overlap case;
- 100,128 total pairs, 94,080 group-certified remote pairs, 120 separation certificates, and zero remote descent for the separated 16-instance case;
- base/edit certificate keys, exactly 15 reused internal group certificates, and one recomputed certificate for the roof edit;
- compact JSON size versus an explicitly calculated one-record-per-remote-pair estimate;
- deterministic diff result;
- any unexpected-overlap signatures;
- pass/fail against every decision rule in the approved design spec;
- one of: `proceed to production-design brainstorm` or `do not proceed`, with the failed rule(s).

- [ ] **Step 7: Run final verification and commit the completed spike**

Run:

```bash
git diff --check
.venv/bin/python -m pytest tests/test_spatial_hierarchy_spike.py tests/test_scope_manifest.py tests/test_detail_gate_selection.py -q
git status --short
git add scripts/spatial_hierarchy_spike.py tests/test_spatial_hierarchy_spike.py tests/test_scope_manifest.csv .superpowers/sdd/spatial-hierarchy-spike-results.md
git commit -m "test: measure hierarchical birdhouse collision coverage"
```

Expected: all focused verification passes; only the approved spike, its platform-audit registration, and its result record are committed.

## Completion criteria

- The 1/4/16 hierarchical candidate sets exactly equal the flat oracle.
- The 16-instance separated case covers 94,080 remote pairs with exactly 120 group certificates and no remote leaf descent.
- Every scenario satisfies complete pair accounting with no individual remote PASS-record expansion.
- The deliberate overlap descends and invokes exact geometry only for the candidate set.
- The roof edit reuses exactly 15 internal group certificates and recomputes exactly one while reconsidering all group relationships.
- Deterministic evidence is byte-identical across independent runs after removing only timing fields.
- Every spike test is classified as platform audit and absent from all document/build gates.
- No production validator, product spec, generated document, cache, or evidence contract changes.
- The measurements support an explicit go/no-go decision; no production integration is implied by a passing spike.
