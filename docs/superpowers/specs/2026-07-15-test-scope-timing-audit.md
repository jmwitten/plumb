# Plumb Test Scope and Timing Audit

**Status:** implemented and verified

**Date:** 2026-07-15

**Audited branch:** `codex/plumb-reusable-vocabulary`

**Node-level evidence:**
[`2026-07-15-test-scope-timing-audit.csv`](2026-07-15-test-scope-timing-audit.csv)

## Decision rule

Every collected pytest node is classified exactly once as either:

1. **Platform** — proves reusable compiler, geometry, validation, renderer,
   cache, test-harness, mutation, invalidation, or exhaustive-oracle behavior.
   A real product may be the stress fixture, but the result is not evidence
   about the accepted document being delivered.
2. **Document/build accuracy** — proves a fact about the accepted current model
   or delivery package for one named owner.

“Generic” is orthogonal to this distinction. A reusable collision test applied
to the accepted birdhouse is birdhouse build accuracy. A test that deliberately
moves a beam, corrupts a baseline, or disables the bbox prefilter to compare all
7,626 pairs is a platform self-test.

## Final evidence and accounting

- Ordinary collection: **2,325 nodes**, reconciled exactly to **2,325 manifest
  rows**; no duplicates, missing rows, or retired ids.
- Final unfiltered run: **2,320 passed, 4 skipped, 1 xfailed** in **1,203.91
  seconds**.
- Sum of per-node durations across four workers: **4,142.810 seconds**. This is
  useful for ownership attribution but is not wall time.
- Pytest charges fixture setup to the first consumer in each worker. A slow
  first node can therefore represent one shared model build, not a slow
  assertion body.

| Category | Nodes | Share | Worker time | Nodes over 10 s |
|---|---:|---:|---:|---:|
| Platform | 1,907 | 82.0% | 3,758.633 s | 82 |
| Document/build accuracy | 418 | 18.0% | 384.177 s | 10 |
| Total | 2,325 | 100% | 4,142.810 s | 92 |

| Runtime cadence | Nodes |
|---|---:|
| Platform unit | 1,607 |
| Platform integration | 254 |
| Platform audit | 46 |
| Build inner | 374 |
| Build release | 44 |

No platform-unit node exceeded ten seconds in the final artifact. Every slow
platform node is explicitly integration or audit.

## Verified selectors

| Selector | Result | Boundary proved |
|---|---|---|
| `--detail-gate family_birdhouse --detail-cadence inner` | 10 passed in 7.05 s | Includes accepted birdhouse compile and normal validation/collision evidence; excludes documents and every platform integration/audit. |
| `--detail-gate family_birdhouse --detail-cadence release` | 22 passed in 26.47 s | Inner evidence plus the single cold birdhouse package and its cache-isolation regression. |
| `--platform-tier integration` | 254 passed in 477.46 s | Real shared-system models, caches, renderers, accepted site views, and one live baseline round trip. |
| `--platform-tier audit` | 46 passed in 636.43 s | Exhaustive bbox equivalence, affected-region mutations, and revision whole-world oracles only. |

The exhaustive 7,626-pair platform oracle took **504.590 seconds** in the final
unfiltered run. The one live baseline regeneration took **263.616 seconds**.
Those timings vary substantially with machine load and concurrent CAD work;
their scope and cadence do not.

## Concrete boundary checks

| Test | Final time | Classification | Why |
|---|---:|---|---|
| `test_family_birdhouse_e2e.py::test_model_has_six_primary_cedar_parts_plus_the_mounting_cleat` | 0.997 s | Birdhouse inner build | Its shared fixture compiles and normally validates the accepted model, including the normal collision sweep. |
| `test_baseline_integrity_unit.py::test_tampered_plain_baseline_is_named_without_regeneration` | 0.002 s | Platform unit | Deliberate corruption now tests pure bytes/names and performs no live model compile. |
| `test_baselines.py::test_regen_round_trip_reproduces_committed_baselines` | 263.616 s | Platform integration | The sole live byte-for-byte regeneration proves the pure baseline guard against real outputs. |
| `test_bbox_prefilter.py::test_platform_prefilter_agrees_with_unfiltered` | 504.590 s | Platform audit | Deliberately disables the optimization and exact-checks all 7,626 pairs. |
| `test_affected_region.py::test_region_is_sound_against_whole_world[beam_len]` | 99.221 s | Platform audit | Artificially changes beam length and compares scoped invalidation with a whole-world rebuild. |

## Remaining build-accuracy nodes over ten seconds

All ten are owner-correct. Seven are release-only document/presentation work;
three are inner accepted-platform model facts whose module setup is charged to
the first consumer.

| Time | Owner / cadence | Test | Scope assessment |
|---:|---|---|---|
| 61.819 s | zipline-package / release | `test_consolidated_document_text_layer_matches_golden` | Correct whole-package golden; exclude from inner and unrelated gates. |
| 40.206 s | zipline-package / release | `test_section_names_every_family_for_every_detail` | Correct release evidence; the coverage module now shares one accepted detail/site context. |
| 35.941 s | zipline-platform / release | `test_presentation_surfaces_render_and_are_consistent[platform]` | Correct accepted-platform presentation/export evidence. |
| 34.295 s | zipline-platform / inner | `test_platform_default_validates_clean` | Essential current-model validation/collision evidence; one accepted-platform fixture feeds the read-only facts. |
| 26.441 s | zipline-package / release | `test_document_prose_has_no_lag_or_slot_tokens[\blags?\b]` | One package fixture is charged to the first parameterized prose assertion. |
| 24.639 s | dv72-documents / release | `test_local_chrome_mobile_metrics_and_letter_pdf` | Correct visual release check using real Chrome and PDF inspection. |
| 14.543 s | cabinetry-db40-documents / release | `test_end_to_end_build_writes_a_contained_consumer_manual` | One justified cold DB40 manual build. |
| 13.978 s | zipline-platform / inner | `test_spec_matches_frozen_transforms_to_1e_6` | Accepted platform geometry oracle; shared module setup is charged here. |
| 11.925 s | zipline-platform / inner | `test_platform_declares_symmetric_about_for_every_mirror_pair` | Accepted platform spatial fact; shared module setup is charged here. |
| 11.697 s | family_birdhouse / release | `test_package_contains_model_documents_data_and_model_exports` | The single cold birdhouse package build; never selected for another build. |

## Implemented performance changes

- Baseline corruption, merge, and stale-file behavior are six pure unit tests;
  only one real baseline regeneration remains.
- Affected-region tests compile six seeded alternate worlds once per module and
  reuse them without dropping any edit class, negative control, or whole-world
  oracle.
- Site overview rendering, consolidated coverage reports, and accepted platform
  validation reuse one owner-scoped context instead of independently rebuilding
  it for adjacent assertions.
- All accepted-live-site view assertions are integration; pure loaders,
  parsers, and toy checks remain unit.
- Birdhouse still rendering tessellates isolated topology copies, preventing a
  generated document from mutating the shared exact-geometry cache.

## Policy

The normal gate for a named build applies generic accuracy contracts to that
accepted model and runs its owner-specific facts. It includes normal collision
validation. It excludes:

- artificial geometry edits used to test invalidation;
- fake baseline corruption through live model recomputation;
- exhaustive all-pairs equivalence oracles;
- cross-product platform/cache audits;
- another product’s geometry, browser, PDF, or package generation.

Real browser/PDF checks, cold package builds, and whole-document goldens remain
document/build accuracy at the named build’s release cadence. Platform
integration and audit checks run when their shared subsystem changes and in the
unfiltered repository-wide verification.
