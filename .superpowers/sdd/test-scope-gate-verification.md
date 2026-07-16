# Test Scope and Gate Verification

**Branch:** `codex/plumb-reusable-vocabulary`

**Baseline commit:** `808c8fd`

## Before

```text
pytest -q -n 4 --maxfail=1 --durations=30
2293 passed, 4 skipped, 1 xfailed in 968.54s
```

The pre-change JUnit artifact is `/tmp/plumb-test-scope-before.xml`.

| Module or behavior | Before cumulative worker time |
|---|---:|
| `test_baselines.py` | 310.691 s |
| `test_affected_region.py` | 445.435 s |
| `test_revision_identity.py` | 492.741 s |
| `test_site_overview.py` | 115.192 s |
| `test_consolidated_coverage.py` | 52.589 s |
| `test_platform_detail.py` | 110.066 s |

The exhaustive platform bbox oracle took 105.84 seconds in the baseline run.

## Scope manifest and selectors

After Task 5, ordinary collection reconciles exactly to 2,324 node ids. The
manifest has no duplicates, unclassified nodes, or retired ids.

Task 4 collection boundaries before Task 5's two pure fixture tests:

| Selector | Nodes | Required boundary evidence |
|---|---:|---|
| `--detail-gate family_birdhouse --detail-cadence inner` | 10 | Includes accepted birdhouse validation/collision fixture; excludes package tests. |
| `--detail-gate family_birdhouse --detail-cadence release` | 21 | Inner 10 plus all 11 birdhouse package assertions. |
| `--platform-tier integration` | 235 | Includes one real baseline regeneration; excludes bbox/affected/revision audits. |
| `--platform-tier audit` | 46 | Includes both exhaustive bbox oracles plus every affected-region and revision-identity node. |

The birdhouse gates passed in 5.31 seconds inner and 18.07 seconds release.
The release package fixture was generated once.

## Baseline integrity refactor

The two deliberate corruption paths, annotation merge, union-of-files
comparison, and `--check` current/stale behavior now run as six pure tests:

```text
6 passed in 0.03s
```

They perform no live compile or validation. The sole real round trip remains:

```text
4 passed in 59.23s
test_regen_round_trip_reproduces_committed_baselines: 59.20s
```

This replaces 310.691 seconds of prior cumulative baseline-module work with
approximately 59.26 seconds while retaining one fresh byte-for-byte truth run.

## Platform audit refactor

```text
test_bbox_prefilter.py:     7 passed in 94.30s
test_affected_region.py:   21 passed in 233.05s
test_revision_identity.py: 23 passed in 417.59s
```

The 7,626-pair oracle remains unchanged and took 85.90 seconds in this focused
run. Affected-region now compiles the six distinct seeded edit worlds once;
the shared setup took 80.39 seconds and the beam-length, bolt-diameter, and
dropped-step follow-up assertions reused those worlds. This reduced the module
from 445.435 seconds in the pre-change artifact to 233.05 seconds in the focused
run without removing any edit class, negative control, or whole-world oracle.

## Accepted-build evidence reuse

The combined focused run passed 42 tests in 225.00 seconds:

| Context | Observed work after refactor | Call-count contract |
|---|---:|---|
| Site overview | 103.61 s shared setup; 5.69 s composed bbox | One real render; one cache-hit call only when the platform integration test is selected; the size assertion consumes the first render. |
| Consolidated coverage | 53.80 s shared setup; 0.01 s headline | `load_details()` once, each detail validation once, `load_site()` once, site validation once. |
| Accepted platform | 31.09 s shared setup; default read-only assertions sub-second | Default platform build once, validation once, report check once. |
| 16-inch O.C. variant | 26.01 s | Remains a separate platform integration variant. |

The fixture reuse assertions use call counts, not wall-clock thresholds. Every
module-scoped CAD context owns a private `DETAILGEN_CACHE_DIR` for its complete
lifetime.

## Final verification

Pending Task 6. Record final integration, audit, birdhouse, and unfiltered-suite
results here after the refreshed JUnit run.
