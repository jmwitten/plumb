# Plumb Test Scope and Timing Audit

**Status:** complete inventory; implementation planning input

**Date:** 2026-07-15

**Audited branch:** `codex/plumb-reusable-vocabulary` at `90f346b`

**Node-level evidence:**
[`2026-07-15-test-scope-timing-audit.csv`](2026-07-15-test-scope-timing-audit.csv)

## Question answered

Classify every collected pytest node as one of:

1. **Platform** — proves reusable compiler, geometry, validation, renderer,
   cache, test-harness, mutation, invalidation, or exhaustive-oracle behavior.
   A real product may be used as the stress fixture, but the result is not
   evidence about the accepted document being delivered.
2. **Document/build accuracy** — proves a fact about the accepted current model
   or delivery package for one named owner.

“Generic” is orthogonal to this distinction. A reusable test template that is
instantiated against the accepted birdhouse and runs its normal collision
validation is a birdhouse build-accuracy test. A test that deliberately moves a
beam, corrupts a baseline, or disables the bbox prefilter to exercise an
exhaustive oracle is a platform test.

## Evidence and accounting

- Fresh `pytest --collect-only -q`: **2,298 nodes** in 29.11 seconds.
- Prior JUnit timing artifact: **2,298 unique nodes**.
- Exact node-id intersection: **2,298**; no current-only or timing-only nodes.
- Prior parallel-suite wall time: **1,099.366 seconds**.
- Sum of per-node durations across parallel workers: **3,892.683 seconds**.
  This sum is useful for ownership attribution but is not wall time.
- Pytest charges module-fixture setup to the first test that consumes it. A
  slow first node may therefore mean “one shared model build for this module,”
  not that the assertion body itself took that long.

| Category | Nodes | Share of nodes | Cumulative worker time | Nodes over 10 s |
|---|---:|---:|---:|---:|
| Platform | 1,881 | 81.9% | 3,406.363 s | 96 |
| Document/build accuracy | 417 | 18.1% | 486.320 s | 15 |
| Total | 2,298 | 100% | 3,892.683 s | 111 |

The main performance problem is scope, not the ordinary accepted-model
collision check. Platform tests account for 87.5% of cumulative test time and
96 of the 111 nodes over ten seconds.

## Concrete boundary checks

| Test | Prior time | Classification | Why |
|---|---:|---|---|
| `test_family_birdhouse_e2e.py::test_model_has_six_primary_cedar_parts_plus_the_mounting_cleat` | 1.124 s | Document/build accuracy | Its module fixture compiles and normally validates the accepted birdhouse, including its collision sweep. |
| `test_certified_builds.py::test_certified_build[armchair_caddy]` | 1.779 s | Document/build accuracy | A generic certification template instantiated for one accepted build. |
| `test_bbox_prefilter.py::test_platform_prefilter_agrees_with_unfiltered` | 94.812 s | Platform | Deliberately disables the optimization and exact-checks all 7,626 pairs to certify the shared algorithm. |
| `test_affected_region.py::test_region_is_sound_against_whole_world[overrides0]` | 24.357 s | Platform | Deliberately changes beam length and compares incremental invalidation with a whole-world rebuild. |
| `test_baselines.py::test_tampered_baseline_is_caught_and_named[detail_counts.json]` | 85.079 s | Platform | Deliberately corrupts test infrastructure; it says nothing about a delivered document. |
| `test_baselines.py::test_tampered_baseline_is_caught_and_named[site_divergence.json]` | 130.735 s | Platform | Same platform self-test through the annotated-baseline path. |

## Document/build-accuracy nodes over ten seconds

### 1. Zipline site-overview PNG size — 58.863 s

`tests/test_site_overview.py::test_site_overview_pngs_are_small_relative_to_the_html_ceiling`

**Finding:** owner-correct but execution-mis-scoped. It performs a new full
two-PNG render only to sum the output bytes. The preceding hash-gate test also
renders the same two views, but to a different function-scoped scratch path.

**Change:** create one module-scoped rendered-overview fixture. Use it for the
image-content, cache-reuse, and size assertions. Keep the real render in the
zipline package release gate only.

### 2. Consolidated document text-layer golden — 43.957 s

`tests/test_spec_presentation_equiv.py::test_consolidated_document_text_layer_matches_golden`

**Finding:** evidence is valid, cadence is too broad. It assembles all four
accepted zipline details to certify the current consolidated package.

**Change:** retain unchanged in the zipline package release gate. Exclude it
from every unrelated build and from the inner document-edit loop.

### 3. Consolidated verdict headline — 38.539 s

`tests/test_consolidated_coverage.py::test_verdict_headline_leads_with_the_per_family_breakdown`

**Finding:** execution-mis-scoped. It independently reloads and validates four
details plus the site instead of consuming the accepted reports already built
by the module fixture for the coverage section.

**Change:** expose one module-scoped `{details, detail_reports, site,
site_report}` fixture and project both the coverage table and headline from it.

### 4. Accepted zipline platform validates — 26.911 s

`tests/test_platform_detail.py::test_platform_default_validates_clean`

**Finding:** required build-accuracy evidence, but the module recompiles the
same default platform separately in many tests. This is the current-model
collision/validation check that belongs in build accuracy.

**Change:** one module-scoped accepted-platform fixture builds and validates
once. All read-only current-platform assertions consume it.

### 5. DV72 mobile and printed document — 24.590 s

`tests/test_double_vanity_installation_guide.py::test_local_chrome_mobile_metrics_and_letter_pdf`

**Finding:** correct DV72 document evidence, wrong cadence for an inner loop.
It launches real headless Chrome twice and inspects a PDF.

**Change:** retain in the DV72 document release/visual gate. Keep the fast
HTML/CSS and typed-projection checks in the DV72 inner build gate.

### 6. Consolidated prose truthfulness — 23.899 s

`tests/test_consolidated_doc_prose.py::test_document_prose_has_no_lag_or_slot_tokens[\blags?\b]`

**Finding:** properly scoped inside its module. One module fixture assembles the
accepted zipline document once; pytest charges that setup to the first of six
small prose assertions.

**Change:** keep in the zipline package gate and exclude from unrelated builds.
No additional model rebuild should be introduced.

### 7. Accepted platform presentation surfaces — 23.722 s

`tests/test_spec_presentation_equiv.py::test_presentation_surfaces_render_and_are_consistent[platform]`

**Finding:** valid generic template instantiated for the accepted platform, but
it exercises the presentation/export surface and belongs to release cadence.

**Change:** retain in the zipline-platform release gate only.

### 8–10. Three accepted platform construction facts — 23.544, 22.902, 22.378 s

- `test_joist_and_rung_hangers_declare_fasteners`
- `test_rail_fastening_declares_all_four_joints`
- `test_end_joist_clears_leg_bolts`

**Finding:** all three are legitimate current-build facts. Each independently
compiles and validates the default platform.

**Change:** consume the same module-scoped accepted-platform detail/report used
by the default validation test. Do not weaken the assertions.

### 11. DB40 cold consumer-manual build — 15.210 s

`tests/test_cabinetry_consumer_manual.py::TestGeneratorScript::test_end_to_end_build_writes_a_contained_consumer_manual`

**Finding:** properly owner-scoped; it is one real end-to-end document build.

**Change:** retain once in the DB40 document release gate. The DB40 inner gate
uses the existing pure model/projection assertions.

### 12. Consolidated coverage section — 13.749 s

`tests/test_consolidated_coverage.py::test_section_names_every_family_for_every_detail`

**Finding:** properly module-scoped. Its shared fixture performs the accepted
four-detail validation once, and pytest charges setup to this first assertion.

**Change:** keep in the zipline package gate; share its reports with the slow
headline test described above.

### 13. Platform frozen-geometry oracle — 12.784 s

`tests/test_platform_spec.py::test_spec_matches_frozen_transforms_to_1e_6`

**Finding:** properly module-scoped. One accepted platform build feeds all four
oracle assertions; setup is charged to the first.

**Change:** keep in the zipline-platform build gate only.

### 14. Platform spatial declarations — 12.571 s

`tests/test_platform_spatial.py::test_platform_declares_symmetric_about_for_every_mirror_pair`

**Finding:** properly module-scoped. One accepted platform validation feeds
three spatial assertions; setup is charged to the first.

**Change:** keep in the zipline-platform build gate only.

### 15. Birdhouse preview package — 12.149 s

`tests/test_family_birdhouse_report.py::test_package_contains_model_documents_data_and_model_exports`

**Finding:** properly scoped. One module fixture generates the birdhouse preview
package once, and all 11 package assertions reuse it.

**Change:** keep once for birdhouse document/package changes. It is the only
birdhouse document/build node above ten seconds and must never run for another
build.

## Resulting policy

The normal gate for a named build should apply generic accuracy templates to
that accepted model and run its owner-specific facts. It includes normal
collision validation. It excludes:

- artificial geometry edits used to test invalidation;
- fake baseline corruption;
- exhaustive all-pairs equivalence oracles;
- cross-product platform/cache audits;
- another product's geometry, browser, PDF, or package generation.

Real browser/PDF checks, cold package builds, and whole-document goldens remain
document/build accuracy but run at the named build's release cadence. Platform
integration and platform audit checks run when their shared subsystem changes
and on the scheduled/full-platform cadence.
