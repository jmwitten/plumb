# Blind caddy certification comparison

## Frozen inputs

The challenge design and frozen predictions are
`docs/superpowers/specs/2026-07-15-blind-caddy-certification-challenge-design.md`
at commit `cb5e495b144dd2eb02447249df30eec9a262426c`. The legacy equivalence
ledger is `.superpowers/sdd/caddy-generic-certification-equivalence.md` at
commit `b71629404c41b59abba1fec1e30d0095cb73f0b7`. The alternative fixture
and execution plan were frozen at
`333c41187ff2b2fd0b049891da49fea027091582`; the independently reviewed
dual-oracle harness was committed at
`b27a5a777827583644b2b1b5ba5a3db504d8378b` before the first real run.

The preflight commands were:

```text
git pull
git status --short
git log --oneline -3
shasum -a 256 tests/fixtures/certification/blind_cleated_caddy.spec.yaml
git rev-parse HEAD
```

`git pull` reported `Already up to date.` `HEAD` was exactly
`b27a5a777827583644b2b1b5ba5a3db504d8378b`; the log showed the harness
commit `b27a5a7` immediately above fixture commit `333c411`. The only status
entry was the controller-owned ` M .superpowers/sdd/progress.md`, which was
neither an experiment input nor staged or committed by this task. The fixture,
harness, contract, predictions, and equivalence ledger all started from
committed bytes.

## Fixture and oracle identity

| Item | Identity |
| --- | --- |
| Frozen fixture | `tests/fixtures/certification/blind_cleated_caddy.spec.yaml` |
| Fixture SHA-256 | `ea945074ddcc1f4f501ea69062423079dc28c5a5e85d77e9a1b31a362c3628dd` |
| Legacy ref and resolved commit | `5e1498e` -> `5e1498ebed9f40aaf3d955897332e3c1c7d0775f` |
| Generic ref and resolved commit | `HEAD` -> `b27a5a777827583644b2b1b5ba5a3db504d8378b` |
| Legacy collection | 53 nodes |
| Generic collection | eight retained probes plus one generic certification node (9 total) |
| Legacy gate | return code 1; 31 failed, 12 passed, 10 errors in 103.17s |
| Generic gate | return code 1; 9 failed in 46.07s |
| Harness | return code 0 after both expected-rejection gates executed |

Both oracle records printed the same fixture digest. The harness read the
fixture bytes once, copied those bytes into two detached disposable worktrees,
verified each copied digest, and used each worktree's own `src` first on
`PYTHONPATH`. Collection succeeded in both trees, so neither fixture
compilation vocabulary nor import isolation blocked the experiment.

After collection and execution, both disposable worktrees and everything
generated inside them were removed. `git worktree list --porcelain` contained
no `blind-caddy-certification-*` path, and the harness process had exited. No
certification result object or generated output was persisted or reused across
oracles; this report records only identities, command/output facts, outcomes,
and category mapping.

The untouched shipped-file hashes after the experiment were:

| Shipped file | SHA-256 |
| --- | --- |
| `details/armchair_caddy.spec.yaml` | `71b7fa7bddf85617cfc320c361ef77ece310217bceb692056b513bd0650cdf76` |
| `details/armchair_caddy.cert.yaml` | `c2f62ab445d0bc38423f9ae7165290a8a20f1e90bd5107dcc07e94ebc93e2066` |
| `details/armchair_caddy.design-review.yaml` | `9baf097d5718684dcacb4e7c4bc07d74dbe71791153345aa2162ac7165bd0dab` |

`git diff --exit-code 333c411^ --` for those three paths returned zero, proving
they remain byte-identical to the Task 1 pre-fixture baseline.

## Exact commands

The only real blind harness invocation was:

```text
.venv/bin/python scripts/blind_caddy_certification.py
```

For each detached worktree the harness collected with:

```text
/Users/joelwitten/Code/construction-detail-generator/.worktrees/caddy-test-performance/.venv/bin/python -m pytest --detail-gate armchair_caddy --collect-only -q
```

and executed with:

```text
/Users/joelwitten/Code/construction-detail-generator/.worktrees/caddy-test-performance/.venv/bin/python -m pytest --detail-gate armchair_caddy -q -n 4
```

The ordinary shipped-caddy regression command was:

```text
.venv/bin/python -m pytest --detail-gate armchair_caddy -q -n 4
```

The focused permanent-evidence command is recorded with its fresh result under
`Ordinary approved-caddy regression` below.

## Frozen predictions versus observed passes

| Frozen prediction | Observed result | Assessment |
| --- | --- | --- |
| The alternative differs in architecture and governance. | Legacy nodes 26, 30, and 48 rejected the absent subject binding; generic `intent.matches` failed with `declared governance intent but governance is absent`, and retained probe 48 failed. | Confirmed. `governance.ready` correctly passed the narrower fact that the subject itself declares no governance; the unchanged contract's declared intent made that absence a rejection. |
| Cleats and screws change part/BOM topology. | Legacy nodes 5, 23, 43, and 47 failed. Generic `intent.matches` observed five panels instead of three, zero dowels instead of four, eight forbidden screws, and BOM length/quantity differences; retained probes 43 and 47 failed. | Confirmed. |
| Forbidden screw hardware is present. | Legacy nodes 2 and 49 failed. Generic `intent.matches` named all eight `structural_screw-*` part IDs under `forbidden[0]`. | Confirmed. |
| Screwed cleat connections replace bonded/keyed/cure-order topology. | Legacy nodes 2, 12, 13, 49, 50, and 52 failed. Generic `intent.matches` observed zero expected bonded/keyed connections and 16 rather than 8 `installed_before` edges; retained probe 52 failed. | Confirmed. |
| Fabrication differs from approved miter sequences. | Legacy node 3 failed, while node 4's generic fold invariant passed. Generic `intent.matches` reported missing miter-crosscut operations on the top and side panels. | Confirmed: selected-design fabrication intent failed while the alternative's own structural fabrication fold remained coherent. |
| Closed miters, diagonal keys/stations, and four flush keys are absent. | Retained legacy/current probes 43-46, 52, and 53 all failed. | Confirmed by direct physical probes, not inferred from assertion-count parity. |
| Compilation succeeds. | The fixture compiled under both commits. Generic `compile.success` passed; legacy node 1 reached validation and failed there rather than at compilation. | Confirmed. |
| Parts have valid non-empty solids. | Generic `geometry.parts_valid` passed for all 14 modeled parts. | Confirmed. Selected-design geometry still failed retained probes, which is not contradictory. |
| Connection endpoints resolve. | Generic `connections.resolved` passed for 20 edges. | Confirmed. Approved connection *topology* still failed `intent.matches`, which is a separate question. |
| Production validation is clean. | Generic `validation.clean` failed on eight screw-embedment termination findings. Legacy output also reported unresolved access/order evidence; `intent.matches` observed eight disallowed termination findings and eight disallowed access findings. | **Frozen-prediction discrepancy.** The plausible alternative compiled but its represented screw installation was not clean. Both systems rejected the discrepancy, so it is not a generic coverage gap. |
| BOM source IDs partition the modeled parts. | Generic `bom.source_ids` passed for all 14 modeled part IDs. | Confirmed. Approved BOM topology separately failed `intent.matches` and retained probe 47. |
| Evidence is deterministic. | Generic `determinism.evidence` passed after two fresh normalized collections. | Confirmed. Legacy document-determinism node 42 errored in optional-document setup and is policy, not contradictory build-evidence evidence. |

## Legacy node outcomes

`ERROR` is retained below when pytest failed in setup; it is a non-pass but is
not relabeled as an assertion failure. Classifications use exactly the frozen
comparison vocabulary. A dash means the node passed and produced no rejection
to classify.

| # | Baseline node | Outcome | Rejection classification and observed evidence |
| ---: | --- | --- | --- |
| 1 | `tests/test_armchair_caddy_e2e.py::test_compiles_and_validates_with_declared_bench_staging` | FAIL | meaningful accuracy: **validation** — compilation succeeded, then eight `install_termination` failures made the report non-clean. |
| 2 | `tests/test_armchair_caddy_e2e.py::test_reinforced_miters_have_no_metal_install_contract` | FAIL | meaningful accuracy: **connections, declared intent** — four resolved screw-install contracts were present instead of hardware-free keyed miters. |
| 3 | `tests/test_armchair_caddy_e2e.py::test_every_board_has_expected_fabrication_record` | FAIL | meaningful accuracy: **fabrication, declared intent** — the top/sides lacked required miter crosscuts and two cleats added different made-part records. |
| 4 | `tests/test_armchair_caddy_e2e.py::test_fabrication_fold_invariant_holds` | PASS | — |
| 5 | `tests/test_armchair_caddy_e2e.py::test_bom_rows_and_cut_lengths` | FAIL | meaningful accuracy: **BOM, declared intent** — expected keyed-miter rows were absent (`StopIteration`). |
| 6 | `tests/test_armchair_caddy_e2e.py::test_bearing_on_arm_is_represented_capacity_absent` | PASS | — |
| 7 | `tests/test_armchair_caddy_e2e.py::test_full_flow_is_fast` | FAIL | meaningful accuracy: **validation**; shared framework duplicate — the assertion failed because `ValidationReport.ok` was false, before the shared clean-process benchmark could establish an approved flow. |
| 8 | `tests/test_armchair_caddy_e2e.py::test_raster_builder_captions_avoid_x_coordinate_part_names` | PASS | — |
| 9 | `tests/test_armchair_caddy_e2e.py::test_progression_harness_matches_the_tree_it_runs_on` | FAIL | meaningful accuracy: **validation**; shared framework duplicate — the independent progression output did not contain `failures: 0`; script-to-spec ownership remains shared-test coverage. |
| 10 | `tests/test_armchair_caddy_e2e.py::test_certifying_render_accepts_declared_staging` | FAIL | meaningful accuracy: **governance** — the legacy helper expected a `design_review` binding to remove and raised `KeyError` because the alternative is ungoverned. |
| 11 | `tests/test_armchair_caddy_e2e.py::test_doc_renders_through_render_documentation` | FAIL | approved policy: optional documentation — no `validation_report.md` was emitted. |
| 12 | `tests/test_armchair_caddy_e2e.py::test_build_sequence_derives_each_miter_cure_before_final_join` | FAIL | meaningful accuracy: **connections, declared intent** — the authored cleat sequence replaced the approved off-sofa miter-cure rationale/order. |
| 13 | `tests/test_armchair_caddy_e2e.py::test_miter_process_order_has_one_authoritative_owner` | FAIL | meaningful accuracy: **connections, fabrication, declared intent** — zero required miter process edges were present instead of two. |
| 14 | `tests/test_armchair_caddy_e2e.py::test_cat_k_sequence_prose_exists_only_in_typed_authoring_surfaces` | PASS | — |
| 15 | `tests/test_armchair_caddy_e2e.py::test_reader_configuration_formats_values_from_the_compiled_namespace` | PASS | — |
| 16 | `tests/test_armchair_caddy_e2e.py::test_visual_review_store_is_valid_and_grounded` | PASS | — |
| 17 | `tests/test_armchair_caddy_e2e.py::test_view_coverage_table_audited_both_directions` | PASS | — |
| 18 | `tests/test_armchair_caddy_e2e.py::test_single_detail_html_build_document` | FAIL | approved policy: optional documentation — legacy caddy prose/rendering expected absent `top_long_len`. |
| 19 | `tests/test_armchair_caddy_e2e.py::test_caddy_doc_carries_no_zipline_content` | FAIL | approved policy: optional documentation — legacy caddy prose/rendering expected absent `top_long_len`. |
| 20 | `tests/test_armchair_caddy_e2e.py::test_caddy_doc_prose_describes_the_current_reinforced_miter` | FAIL | approved policy: optional documentation — legacy caddy prose/rendering expected absent `top_long_len`. |
| 21 | `tests/test_armchair_caddy_e2e.py::test_design_findings_store_statuses_per_ruling` | PASS | — |
| 22 | `tests/test_armchair_caddy_e2e.py::test_design_review_block_disclosed_in_caddy_doc` | FAIL | approved policy: optional documentation — legacy caddy prose/rendering expected absent `top_long_len`; this node is not used as generic governance evidence. |
| 23 | `tests/test_armchair_caddy_e2e.py::test_reinforced_miter_revision_uses_three_panels_and_four_keys` | FAIL | meaningful accuracy: **geometry, declared intent** — three primary panels existed but zero of the four required keys. |
| 24 | `tests/test_caddy_design_review.py::test_caddy_review_is_complete_and_compares_four_required_architectures` | PASS | — |
| 25 | `tests/test_caddy_design_review.py::test_caddy_reinforced_miter_is_implemented_and_modeling_approved` | PASS | — |
| 26 | `tests/test_caddy_design_review.py::test_caddy_spec_opts_in_and_delivery_is_confirmed` | FAIL | meaningful accuracy: **governance, declared intent** — the compiled alternative's `design_governance` was `None`. |
| 27 | `tests/test_caddy_design_review.py::test_customer_document_pair_writes_nothing_while_review_is_pending` | FAIL | meaningful accuracy: **validation**; shared framework duplicate; approved policy — rendering stopped on eight validation failures plus unresolved access before the optional document-pair assertion. |
| 28 | `tests/test_caddy_design_review.py::test_confirmed_customer_document_pair_is_unmarked` | FAIL | meaningful accuracy: **validation**; approved policy — rendering stopped on the same validation evidence before optional presentation marking was examined. |
| 29 | `tests/test_caddy_design_review.py::test_explicit_preview_pair_is_reviewable_but_cannot_masquerade_as_delivery` | FAIL | approved policy: optional presentation; shared framework duplicate — the old presentation raised `InstructionPresentationError` for an incomplete prepare panel. |
| 30 | `tests/test_caddy_design_review.py::test_governance_binding_does_not_change_caddy_geometry` | FAIL | meaningful accuracy: **governance**; shared framework duplicate — the helper raised `KeyError: design_review` before metadata-inertness comparison. |
| 31 | `tests/test_caddy_design_review.py::test_generated_caddy_report_is_developer_facing_and_retains_provenance` | PASS | — |
| 32 | `tests/test_caddy_instruction_manual.py::test_pair_has_exact_distinct_basenames_and_reciprocal_relative_links` | ERROR | approved policy: optional documentation — shared module setup called `raw.pop("design_review")` on the intentionally ungoverned fixture. |
| 33 | `tests/test_caddy_instruction_manual.py::test_technical_companion_uses_the_same_four_panel_schedule` | ERROR | approved policy: optional documentation — same setup `KeyError`. |
| 34 | `tests/test_caddy_instruction_manual.py::test_pair_compiles_the_detail_only_once` | ERROR | approved policy: optional documentation — same setup `KeyError`. |
| 35 | `tests/test_caddy_instruction_manual.py::test_pair_compiles_once_when_ignored_legacy_views_are_missing` | ERROR | approved policy: optional documentation — same setup `KeyError`. |
| 36 | `tests/test_caddy_instruction_manual.py::test_ordinary_technical_header_has_no_broken_companion_link` | PASS | — |
| 37 | `tests/test_caddy_instruction_manual.py::test_manual_is_self_contained_and_has_one_model_backed_panel_per_cohort` | ERROR | approved policy: optional documentation/presentation — same setup `KeyError`. |
| 38 | `tests/test_caddy_instruction_manual.py::test_manual_renders_typed_resource_icons_and_release_boundary` | ERROR | approved policy: optional documentation/presentation — same setup `KeyError`. |
| 39 | `tests/test_caddy_instruction_manual.py::test_manual_carries_typed_gates_stations_rationales_and_declared_trust` | ERROR | approved policy: optional documentation/presentation — same setup `KeyError`; meaningful validation is counted only from independent validation nodes. |
| 40 | `tests/test_caddy_instruction_manual.py::test_manual_explains_callout_numbers_with_shared_reader_names` | ERROR | approved policy: optional documentation/presentation — same setup `KeyError`. |
| 41 | `tests/test_caddy_instruction_manual.py::test_pair_reports_content_hashes_and_four_keyed_panel_images` | ERROR | approved policy: optional documentation/presentation — same setup `KeyError`. |
| 42 | `tests/test_caddy_instruction_manual.py::test_pair_regeneration_is_deterministic_after_generated_stamp_normalization` | ERROR | approved policy: optional document determinism — same setup `KeyError`; it is not a build-evidence determinism rejection. |
| 43 | `tests/test_caddy_reinforced_miter.py::test_caddy_uses_three_hardwood_panels_and_four_keys_only` | FAIL | retained spatial invariant: selected physical topology/orientation — five hardwood panels were present instead of three. |
| 44 | `tests/test_caddy_reinforced_miter.py::test_three_panel_shell_has_uniform_stock_fit_and_closed_miter_geometry` | FAIL | retained spatial invariant: selected closed-miter stock geometry — top length was 241.3 mm instead of 203.2 mm before later miter checks. |
| 45 | `tests/test_caddy_reinforced_miter.py::test_four_dowels_match_precedent_size_stations_and_diagonal_axes` | FAIL | retained spatial invariant: key axes/stations/flush geometry — the observed dowel station list was empty. |
| 46 | `tests/test_caddy_reinforced_miter.py::test_top_retains_centered_three_and_half_inch_cup_bore` | FAIL | retained spatial invariant: produced-solid bore placement — `cx` was 120.65 mm instead of 101.6 mm. |
| 47 | `tests/test_caddy_reinforced_miter.py::test_bom_contains_three_panels_four_dowels_and_no_legacy_hardware` | FAIL | retained spatial invariant: physical/BOM product-boundary cross-check — BOM contained zero required dowels. |
| 48 | `tests/test_caddy_reinforced_miter.py::test_implemented_selection_and_model_are_owner_confirmed` | FAIL | retained spatial invariant: approved selected-model fingerprint binding — absent subject governance produced `None.model_digest`. |
| 49 | `tests/test_install_sweep.py::test_caddy_glued_top_joints_carry_no_install_verdicts` | FAIL | meaningful accuracy: **connections, validation, declared intent** — 16 screw-install findings existed for joints that should have no install verdicts. |
| 50 | `tests/test_install_sweep.py::test_cat_g_caddy_bench_frame_clears_arm_with_declared_trust` | FAIL | meaningful accuracy: **connections, validation** — eight install-access findings existed, including unresolved obstructed tool corridors. |
| 51 | `tests/test_install_sweep.py::test_caddy_has_no_install_blocker_after_declared_staging` | FAIL | meaningful accuracy: **validation** — termination failures remained blocking after staging. |
| 52 | `tests/test_install_sweep.py::test_caddy_keyed_miter_rejects_extra_hardware` | FAIL | retained spatial invariant: physical negative probe for keyed-miter semantics — the alternative had no keyed connection/dowel, so mutation failed as an unknown part rather than the expected third-key cardinality rejection. |
| 53 | `tests/test_install_sweep.py::test_caddy_synthetic_oversized_corner_keys_fail_interference` | FAIL | retained spatial invariant: physical negative interference probe — no corner keys existed, so zero of four expected key interferences were found. |

The 10 `ERROR` outcomes were all optional instruction-manual module setup
effects from the same `raw.pop("design_review")` call. They were not compiler,
fixture-vocabulary, harness, worktree, or collection failures.

## Generic rule and retained-probe outcomes

The generic certification assertion expanded to the required nine named rule
findings:

| Generic rule | Outcome | Observed detail |
| --- | --- | --- |
| `compile.success` | PASS | Subject compiled and evidence collection completed. |
| `geometry.parts_valid` | PASS | 14 parts had unique IDs and valid non-empty solids. |
| `validation.clean` | FAIL | Eight `install_termination` findings reported 0.50-inch embedment below the declared 1.00-inch top or 0.62-inch side minimum. |
| `connections.resolved` | PASS | 20 connection edges resolved. |
| `fabrication.fold` | PASS | Fabrication fold verified for five made parts. |
| `bom.source_ids` | PASS | 14 modeled part IDs partitioned the BOM. |
| `governance.ready` | PASS | The subject does not declare design governance. This narrower pass is paired with the unchanged contract's failing governance intent below. |
| `intent.matches` | FAIL | Observed five vs three approved panels, zero vs four dowels, all eight forbidden screws, zero expected bonded/keyed connections, 16 vs 8 order edges, disallowed validation findings, missing miter operations, panel length outliers, zero dowel BOM quantity, and declared governance intent with governance absent. |
| `determinism.evidence` | PASS | Two fresh collections produced identical normalized evidence. |

All eight retained physical probes also rejected the alternative:

| Retained probe | Outcome | Rule/probe role |
| --- | --- | --- |
| `tests/test_caddy_reinforced_miter.py::test_caddy_uses_three_hardwood_panels_and_four_keys_only` | FAIL | Physical selected-design topology/orientation beyond v1 selectors. |
| `tests/test_caddy_reinforced_miter.py::test_three_panel_shell_has_uniform_stock_fit_and_closed_miter_geometry` | FAIL | Closed 45-degree miter fit and stock envelope. |
| `tests/test_caddy_reinforced_miter.py::test_four_dowels_match_precedent_size_stations_and_diagonal_axes` | FAIL | Key axes, stations, dimensions, and flush trim. |
| `tests/test_caddy_reinforced_miter.py::test_top_retains_centered_three_and_half_inch_cup_bore` | FAIL | Actual bore placement/diameter in produced geometry. |
| `tests/test_caddy_reinforced_miter.py::test_bom_contains_three_panels_four_dowels_and_no_legacy_hardware` | FAIL | Physical component/BOM product-boundary cross-check. |
| `tests/test_caddy_reinforced_miter.py::test_implemented_selection_and_model_are_owner_confirmed` | FAIL | Physical model fingerprint bound to owner-approved selection. |
| `tests/test_caddy_reinforced_miter.py::test_caddy_keyed_miter_rejects_extra_hardware` | FAIL | Negative keyed-joint semantic probe. |
| `tests/test_caddy_reinforced_miter.py::test_caddy_synthetic_oversized_corner_keys_fail_interference` | FAIL | Negative real-geometry interference probe. |

## Category equivalence mapping

The comparison unit is rejection-category coverage, not 53-versus-9 assertion
count parity.

| Meaningful accuracy category | Observed legacy rejection evidence | Generic failing evidence | Equivalent? |
| --- | --- | --- | --- |
| compilation | No legacy compilation rejection; node 1 compiled and failed only during validation. | `compile.success` PASS. | Yes; no contradictory compilation rejection existed to cover. |
| geometry | Node 23 rejected key topology; retained nodes 43-47 and 53 rejected selected physical geometry/product-boundary facts. | `intent.matches` FAIL for selected counts/BOM plus retained probes 43-47 and 53 FAIL. | Yes. |
| validation | Nodes 1, 7, 9, 27, 28, and 49-51 rejected non-clean termination/access evidence. | `validation.clean` FAIL for eight termination failures; `intent.matches` FAIL for disallowed termination/access finding counts. | Yes. |
| connections | Nodes 2, 12, 13, 49, and 50 rejected screw installs and missing approved process topology; node 52 rejected absent keyed semantics. | `intent.matches` FAIL for bonded/keyed/order topology and validation counts; retained probe 52 FAIL. | Yes. |
| fabrication | Nodes 3 and 13 rejected missing miter operations/process edges; node 4 passed the structural fold. | `intent.matches` FAIL for exact top/side fabrication sequences; `fabrication.fold` PASS confirms no contradiction at the generic structural-fold layer. | Yes. |
| BOM | Nodes 5 and 47 rejected selected BOM topology/geometry. | `intent.matches` FAIL for panel lengths and zero required dowels; retained probe 47 FAIL. `bom.source_ids` PASS confirms the separate source-ID partition prediction. | Yes. |
| governance | Nodes 10, 26, 30, and 48 rejected absent subject governance/fingerprint binding. | `intent.matches` FAIL because unchanged contract intent declares governance while subject governance is absent; retained probe 48 FAIL. | Yes. |
| declared intent | Nodes 2, 3, 5, 12, 13, 23, 26, and 49 rejected approved topology, fabrication, governance, or forbidden-hardware expectations. | `intent.matches` FAIL with direct counts, forbidden IDs, connections, validation, fabrication, BOM, and governance evidence. | Yes. |
| determinism | No meaningful legacy build-evidence determinism rejection. Node 42 was optional-document setup policy, and node 30 failed for absent governance before stability comparison. | `determinism.evidence` PASS after two fresh collections. | Yes; no contradictory meaningful rejection was hidden. |

The retained spatial-invariant category is independently satisfied because all
eight deliberately retained probes failed in the generic oracle. Shared
framework duplicate rows remain owned by the exact named shared tests in the
equivalence ledger, including the script rewiring, reader-name, review-store,
design-review integration/gate/report, renderer, and content-key tests. No
shared duplicate or approved-policy failure is counted as generic accuracy
coverage.

## Approved policy-only differences

The caddy certification contract declares no documentation or presentation
deliverables. Accordingly, legacy failures in nodes 11, 18-20, 22, 29, and
32-35/37-42 are approved policy/setup effects, not missed certification
accuracy. Nodes 27 and 28 concern optional document-pair presentation but
stopped earlier on independently meaningful validation evidence; their
validation category is counted from `validation.clean`/`intent.matches`, not
from the optional output requirement. Policy nodes 8, 14, 17, and 36 passed,
and shared/report node 31 also passed.

Most importantly, the 10 instruction-manual errors are a single legacy setup
assumption (`raw.pop("design_review")`) repeated across optional-document tests.
The fixture itself compiled under both commits and both collections completed,
so those errors do not justify a representation edit or an infrastructure
block.

## Gaps and corrections

No meaningful legacy rejection category was missed by the generic gate or the
retained physical probes. Therefore no certification source, contract,
fixture, shipped caddy file, or regression test was changed, and no TDD
correction task was required.

The empirical discrepancy from the frozen pass predictions is production
validation: the fixture's represented screw installation produced eight
termination failures and access/order evidence instead of a clean report. This
was reported as observed rather than edited away. Both oracles rejected it,
and generic coverage is explicit in `validation.clean` and `intent.matches`.

The Task 2 review's minor note that collection-failure propagation lacks a
direct regression assertion remains out of scope. Collection succeeded for
both real oracles, so that note did not block or alter this experiment.

## Ordinary approved-caddy regression

After the disposable challenge worktrees were removed, the untouched ordinary
approved caddy gate ran with the exact command shown above and returned:

```text
.........                                                                [100%]
9 passed in 37.72s
```

This proves the shipped approved caddy still clears the final nine-node gate
after the blind experiment.

The focused permanent-evidence command then ran fresh:

```text
.venv/bin/python -m pytest tests/test_blind_caddy_certification.py tests/test_certification_migrations.py -q
```

and returned:

```text
....                                                                     [100%]
4 passed in 0.30s
```

These tests verify the disposable harness behavior and the permanent generic
certification migration evidence used by the ordinary gate.

## Conclusion

The blind rejection-equivalence experiment succeeds. The fixture and
predictions predated both oracle executions, both worktrees used the same
SHA-256-identical fixture bytes with isolated source imports, every meaningful
legacy rejection category was rejected by a named generic rule or retained
physical probe, optional documentation/presentation failures were kept in the
approved-policy bucket, and the ordinary approved caddy still passed 9/9.

The result is category equivalence, not assertion-count equivalence: the
generic gate rejected through `validation.clean` and `intent.matches`, while
the eight retained probes preserved physical selected-design scrutiny. Its
passing compilation, part-solid validity, resolved endpoints, fabrication
fold, BOM source-ID partition, governance opt-in rule, and deterministic
evidence are compatible with those targeted rejections and with the frozen
predictions except for the explicitly recorded validation discrepancy.
