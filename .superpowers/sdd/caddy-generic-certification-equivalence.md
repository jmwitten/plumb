# Caddy generic-certification equivalence ledger

Date: 2026-07-15

Baseline: the 53 nodes selected by `--detail-gate armchair_caddy` at commit
`5e1498e`.

Disposition vocabulary:

- **RULE** — replaced by a named generic certification rule;
- **CONTRACT** — replaced by a typed fact in
  `details/armchair_caddy.cert.yaml`;
- **SHARED** — duplicate of a named surviving framework test;
- **RETAIN** — remains a physical caddy invariant because v1 generic evidence
  cannot express it honestly;
- **POLICY** — retired under the owner-approved rule that documentation and
  presentation are optional unless declared in `deliverables`.

| # | Baseline node | Disposition |
| ---: | --- | --- |
| 1 | `tests/test_armchair_caddy_e2e.py::test_compiles_and_validates_with_declared_bench_staging` | **RULE** `compile.success`, `validation.clean`, `connections.resolved` |
| 2 | `tests/test_armchair_caddy_e2e.py::test_reinforced_miters_have_no_metal_install_contract` | **CONTRACT** `intent.forbidden[0:2]`, `intent.connections[0:3]`, `intent.validation[3:5]` |
| 3 | `tests/test_armchair_caddy_e2e.py::test_every_board_has_expected_fabrication_record` | **CONTRACT** `intent.fabrication[0:2]`; **RULE** `fabrication.fold` |
| 4 | `tests/test_armchair_caddy_e2e.py::test_fabrication_fold_invariant_holds` | **RULE** `fabrication.fold` delegates to `verify_assembly_fabrication` |
| 5 | `tests/test_armchair_caddy_e2e.py::test_bom_rows_and_cut_lengths` | **RULE** `bom.source_ids`; **CONTRACT** `intent.bom[0:3]`, `intent.forbidden[0:2]` |
| 6 | `tests/test_armchair_caddy_e2e.py::test_bearing_on_arm_is_represented_capacity_absent` | **CONTRACT** `intent.validation[0:3]` requires one sofa-arm bearing PASS and zero support/capacity findings |
| 7 | `tests/test_armchair_caddy_e2e.py::test_full_flow_is_fast` | **SHARED** clean-process gate benchmark recorded in `.superpowers/sdd/caddy-test-performance-report.md` |
| 8 | `tests/test_armchair_caddy_e2e.py::test_raster_builder_captions_avoid_x_coordinate_part_names` | **POLICY** presentation is absent from `deliverables`; shared reader-name behavior remains in `tests/test_reader_names.py::test_part_labels_number_duplicate_reader_names_once` |
| 9 | `tests/test_armchair_caddy_e2e.py::test_progression_harness_matches_the_tree_it_runs_on` | **SHARED** `tests/test_scripts_spec_rewire.py::test_no_detail_py_is_loaded_by_script` owns script-to-spec wiring |
| 10 | `tests/test_armchair_caddy_e2e.py::test_certifying_render_accepts_declared_staging` | **RULE** `validation.clean`, `governance.ready`; shared export gating remains in `tests/test_design_review_integration.py::test_current_delivery_confirmation_allows_certified_render` |
| 11 | `tests/test_armchair_caddy_e2e.py::test_doc_renders_through_render_documentation` | **POLICY** documentation is absent from `deliverables` |
| 12 | `tests/test_armchair_caddy_e2e.py::test_build_sequence_derives_each_miter_cure_before_final_join` | **CONTRACT** `intent.connections[2]` requires eight `installed_before` edges; **RULE** `connections.resolved`, `validation.clean` |
| 13 | `tests/test_armchair_caddy_e2e.py::test_miter_process_order_has_one_authoritative_owner` | **CONTRACT** `intent.connections[0:3]`, `intent.fabrication[0:2]`; **RULE** `determinism.evidence` |
| 14 | `tests/test_armchair_caddy_e2e.py::test_cat_k_sequence_prose_exists_only_in_typed_authoring_surfaces` | **POLICY** prose is not a certification deliverable |
| 15 | `tests/test_armchair_caddy_e2e.py::test_reader_configuration_formats_values_from_the_compiled_namespace` | **SHARED** `tests/test_reader_names.py::test_compiler_interpolates_reader_name_without_changing_machine_name` |
| 16 | `tests/test_armchair_caddy_e2e.py::test_visual_review_store_is_valid_and_grounded` | **SHARED** `tests/test_review_stores.py::test_load_detail_stores_loads_the_real_caddy_stores` and review-store schema tests |
| 17 | `tests/test_armchair_caddy_e2e.py::test_view_coverage_table_audited_both_directions` | **POLICY** view presentation is absent from `deliverables`; shared payload validation remains in `tests/test_viewer_instruction_panels.py::test_viewer_payload_rejects_incomplete_unknown_or_duplicate_schedule_ids` |
| 18 | `tests/test_armchair_caddy_e2e.py::test_single_detail_html_build_document` | **POLICY** documentation is absent from `deliverables` |
| 19 | `tests/test_armchair_caddy_e2e.py::test_caddy_doc_carries_no_zipline_content` | **POLICY** documentation is absent from `deliverables` |
| 20 | `tests/test_armchair_caddy_e2e.py::test_caddy_doc_prose_describes_the_current_reinforced_miter` | **POLICY** documentation is absent from `deliverables` |
| 21 | `tests/test_armchair_caddy_e2e.py::test_design_findings_store_statuses_per_ruling` | **SHARED** `tests/test_review_store.py::test_round_trip_load_dump_load` and `tests/test_review_stores.py::test_load_detail_stores_loads_the_real_caddy_stores` |
| 22 | `tests/test_armchair_caddy_e2e.py::test_design_review_block_disclosed_in_caddy_doc` | **POLICY** documentation is absent from `deliverables`; lifecycle accuracy remains **RULE** `governance.ready` |
| 23 | `tests/test_armchair_caddy_e2e.py::test_reinforced_miter_revision_uses_three_panels_and_four_keys` | **CONTRACT** `intent.counts[1:3]`, `intent.forbidden[0:2]` |
| 24 | `tests/test_caddy_design_review.py::test_caddy_review_is_complete_and_compares_four_required_architectures` | **RULE** `governance.ready` delegates to the validated review; shared closed-schema/completeness cases remain in `tests/test_design_review_validation.py` |
| 25 | `tests/test_caddy_design_review.py::test_caddy_reinforced_miter_is_implemented_and_modeling_approved` | **CONTRACT** `intent.governance`; **RULE** `governance.ready` |
| 26 | `tests/test_caddy_design_review.py::test_caddy_spec_opts_in_and_delivery_is_confirmed` | **CONTRACT** `intent.governance`; **RULE** `governance.ready` |
| 27 | `tests/test_caddy_design_review.py::test_customer_document_pair_writes_nothing_while_review_is_pending` | **SHARED** `tests/test_design_review_integration.py::test_governed_render_writes_nothing_without_delivery_confirmation`; **POLICY** document-pair projection is not a deliverable |
| 28 | `tests/test_caddy_design_review.py::test_confirmed_customer_document_pair_is_unmarked` | **POLICY** document-pair presentation is absent from `deliverables` |
| 29 | `tests/test_caddy_design_review.py::test_explicit_preview_pair_is_reviewable_but_cannot_masquerade_as_delivery` | **POLICY** document-pair presentation is absent from `deliverables`; shared lifecycle gates remain in `tests/test_design_review_gate.py` |
| 30 | `tests/test_caddy_design_review.py::test_governance_binding_does_not_change_caddy_geometry` | **SHARED** `tests/test_design_review_integration.py::test_binding_round_trips_without_source_path` and **RULE** `determinism.evidence` own metadata inertness/stability |
| 31 | `tests/test_caddy_design_review.py::test_generated_caddy_report_is_developer_facing_and_retains_provenance` | **SHARED** `tests/test_design_review_report.py::test_report_is_deterministic_and_contains_provenance_and_decision`; **POLICY** generated report is not a deliverable |
| 32 | `tests/test_caddy_instruction_manual.py::test_pair_has_exact_distinct_basenames_and_reciprocal_relative_links` | **POLICY** documentation is absent from `deliverables` |
| 33 | `tests/test_caddy_instruction_manual.py::test_technical_companion_uses_the_same_four_panel_schedule` | **POLICY** documentation is absent from `deliverables`; shared panel scheduling remains in `tests/test_viewer_instruction_panels.py` |
| 34 | `tests/test_caddy_instruction_manual.py::test_pair_compiles_the_detail_only_once` | **POLICY** documentation is absent from `deliverables` |
| 35 | `tests/test_caddy_instruction_manual.py::test_pair_compiles_once_when_ignored_legacy_views_are_missing` | **POLICY** documentation is absent from `deliverables` |
| 36 | `tests/test_caddy_instruction_manual.py::test_ordinary_technical_header_has_no_broken_companion_link` | **POLICY** documentation is absent from `deliverables` |
| 37 | `tests/test_caddy_instruction_manual.py::test_manual_is_self_contained_and_has_one_model_backed_panel_per_cohort` | **POLICY** documentation is absent from `deliverables`; shared renderer semantics remain in `tests/test_instruction_render.py` |
| 38 | `tests/test_caddy_instruction_manual.py::test_manual_renders_typed_resource_icons_and_release_boundary` | **POLICY** documentation is absent from `deliverables` |
| 39 | `tests/test_caddy_instruction_manual.py::test_manual_carries_typed_gates_stations_rationales_and_declared_trust` | **POLICY** documentation is absent from `deliverables`; physical validation remains **RULE** `validation.clean` |
| 40 | `tests/test_caddy_instruction_manual.py::test_manual_explains_callout_numbers_with_shared_reader_names` | **POLICY** documentation is absent from `deliverables`; shared naming remains in `tests/test_reader_names.py` |
| 41 | `tests/test_caddy_instruction_manual.py::test_pair_reports_content_hashes_and_four_keyed_panel_images` | **POLICY** documentation is absent from `deliverables`; shared content-key behavior remains in `tests/test_instruction_render.py::test_content_key_covers_source_event_identity` |
| 42 | `tests/test_caddy_instruction_manual.py::test_pair_regeneration_is_deterministic_after_generated_stamp_normalization` | **POLICY** document determinism is not required; build-evidence stability remains **RULE** `determinism.evidence` |
| 43 | `tests/test_caddy_reinforced_miter.py::test_caddy_uses_three_hardwood_panels_and_four_keys_only` | **RETAIN** explicit physical topology/orientation inspection beyond v1 selectors |
| 44 | `tests/test_caddy_reinforced_miter.py::test_three_panel_shell_has_uniform_stock_fit_and_closed_miter_geometry` | **RETAIN** closed 45-degree miter fit and stock-envelope geometry |
| 45 | `tests/test_caddy_reinforced_miter.py::test_four_dowels_match_precedent_size_stations_and_diagonal_axes` | **RETAIN** diagonal axes, stations, and flush physical key geometry |
| 46 | `tests/test_caddy_reinforced_miter.py::test_top_retains_centered_three_and_half_inch_cup_bore` | **RETAIN** actual bore placement and diameter in produced solid |
| 47 | `tests/test_caddy_reinforced_miter.py::test_bom_contains_three_panels_four_dowels_and_no_legacy_hardware` | **RETAIN** cross-checks physical component geometry with reader-facing BOM at the product boundary |
| 48 | `tests/test_caddy_reinforced_miter.py::test_implemented_selection_and_model_are_owner_confirmed` | **RETAIN** binds the physical-model fingerprint to the approved selected architecture |
| 49 | `tests/test_install_sweep.py::test_caddy_glued_top_joints_carry_no_install_verdicts` | **CONTRACT** `intent.connections[0:2]`, `intent.validation[3:5]`, `intent.forbidden[0:2]`; **RULE** `validation.clean` |
| 50 | `tests/test_install_sweep.py::test_cat_g_caddy_bench_frame_clears_arm_with_declared_trust` | **RULE** `validation.clean`; **CONTRACT** `intent.validation[3]` requires zero access findings |
| 51 | `tests/test_install_sweep.py::test_caddy_has_no_install_blocker_after_declared_staging` | **RULE** `validation.clean` |
| 52 | `tests/test_install_sweep.py::test_caddy_keyed_miter_rejects_extra_hardware` | **RETAIN** physical negative probe for the caddy's keyed-miter joint semantics; move to `tests/test_caddy_reinforced_miter.py` |
| 53 | `tests/test_install_sweep.py::test_caddy_synthetic_oversized_corner_keys_fail_interference` | **RETAIN** physical negative probe for real caddy interference; move to `tests/test_caddy_reinforced_miter.py` |

## Totals

- Baseline rows: 53
- Retained caddy physical nodes: 8
- Rows no longer requiring a bespoke caddy gate test: 45 (84.91%)
- Generic certification nodes added to the caddy gate: 1
- Expected final caddy gate nodes: 9
