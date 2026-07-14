"""DV72 opt-in pack: analytic fixtures, service drawers, and honest gates."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from detailgen.core.registry import components, materials
from detailgen.packs import (
    ProjectReleaseError,
    ProjectSchemaError,
    compile_project_file,
)


FIXTURE = (
    Path(__file__).parent / "fixtures" / "cabinetry"
    / "floating_double_sink_four_drawer.project.yaml"
)


def _project():
    return compile_project_file(FIXTURE)


def test_registry_exposes_double_sink_pack_without_mutating_base_registries():
    from detailgen.packs.registry import default_pack_registry

    before_components = tuple(components.names())
    before_materials = tuple(materials.names())
    assert "vanity.double_sink@1" in default_pack_registry().available()
    _project()
    assert tuple(components.names()) == before_components
    assert tuple(materials.names()) == before_materials


def test_real_drain_trap_runner_and_mount_references_are_pinned_without_capacity_claim():
    project = _project()
    model = project.model
    catalog = model.catalog_manifest()
    sources = model.catalog_source_manifest()

    assert catalog["drain"] == "kohler_k7124_a@2018-09-28"
    assert model.drain.sku == "K-7124-A"
    assert model.drain.with_overflow
    assert model.drain.connection_od_mm == pytest.approx(1.25 * 25.4)
    assert model.drain.body_height_mm == pytest.approx(130.0)
    assert "K-7124-A_spec.pdf" in sources["drain"]

    assert catalog["trap"] == "kohler_k8998@2026-07-14"
    assert model.trap.sku == "K-8998"
    assert model.trap.inlet_od_mm == pytest.approx(1.25 * 25.4)
    assert model.trap.overall_length_mm == pytest.approx(298.0)
    assert model.trap.overall_height_mm == pytest.approx(111.0)
    assert model.trap.cleanout

    upper = model.drawer("left", "upper").runner
    assert upper.selected_sku == "763.4570S"
    assert upper.minimum_drawer_length_mm == pytest.approx(457.0)
    assert upper.minimum_inside_depth_mm == pytest.approx(477.0)

    assert catalog["comparative_mount"] == "rakks_eh_1818_lv@2022.1.0"
    assert model.mount_reference.static_capacity_lb == pytest.approx(450.0)
    assert model.mount_reference.capacity_basis == "evenly_distributed_static_load"
    assert project.report.by_rule("double_vanity.release.wall_mount").verdict == "UNKNOWN"


def test_catalog_asset_reference_is_metadata_only_and_authority_limited():
    from detailgen.packs.cabinetry.double_vanity import CatalogAssetRef

    asset = CatalogAssetRef(
        asset_id="kohler.caxton.k20000.visual",
        manufacturer="Kohler",
        sku="K-20000-0",
        variant="white",
        asset_role="visual_reference",
        authority="reference_only",
        source_url="https://example.invalid/k20000.rfa",
        source_page_url="https://example.invalid/k20000",
        specification_url="https://example.invalid/k20000.pdf",
        source_revision="2024-06-10",
        retrieved_at="2026-07-14T00:00:00Z",
        media_type="application/octet-stream",
        format="rfa",
        byte_length=123,
        sha256_raw="a" * 64,
        source_units="mm",
        source_frame=("right", "z", "negative_y", "manufacturer drain datum"),
        transform_to_project_mm=(
            1, 0, 0, 0,
            0, 1, 0, 0,
            0, 0, 1, 0,
            0, 0, 0, 1,
        ),
        calibration_anchors=("drain_center", "overall_left", "overall_front"),
        terms_url="https://example.invalid/terms",
        terms_checked_at="2026-07-14",
        license_class="local_project_use_only",
        redistribution="prohibited",
        analytic_adapter="kohler_k20000_v1",
    )

    assert asset.allows_consumer("local_preview_renderer")
    for forbidden in (
        "renderer", "publish_renderer", "self_contained_renderer",
        "cut_list", "machining", "plumbing", "structure", "code",
    ):
        assert not asset.allows_consumer(forbidden)
    assert not asset.may_embed
    with pytest.raises(ValueError, match="64-character"):
        replace(asset, sha256_raw="not-a-digest")
    with pytest.raises(ValueError, match="three calibration anchors"):
        replace(asset, calibration_anchors=("drain_center",))
    unknown_terms = replace(
        asset, license_class="unknown", redistribution="unknown",
    )
    assert not unknown_terms.allows_consumer("local_preview_renderer")
    unfetched_template = replace(
        unknown_terms,
        asset_role="cutout_template",
        authority="manufacturer_template",
        byte_length=0,
        sha256_raw=(
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ),
    )
    assert not unfetched_template.allows_consumer("cutout_template")
    pinned_template = replace(
        asset,
        asset_role="cutout_template",
        authority="manufacturer_template",
    )
    assert pinned_template.allows_consumer("cutout_template")


def test_dv72_expands_to_two_independent_service_bays_and_four_drawers():
    project = _project()
    model = project.model

    assert model.section.vanity.width_mm == pytest.approx(72 * 25.4)
    assert model.section.vanity.body_height_mm == pytest.approx(22 * 25.4)
    assert model.section.vanity.bottom_elevation_mm == pytest.approx(11 * 25.4)
    assert (
        model.section.vanity.bottom_elevation_mm
        + model.section.vanity.body_height_mm
        + model.section.vanity.countertop_thickness_mm
    ) == pytest.approx(34.5 * 25.4)
    assert model.section.vanity.body_depth_mm == pytest.approx(21 * 25.4)
    assert [bay.bay_id for bay in model.sink_bays] == ["left", "right"]
    assert [bay.sink_center_x_mm for bay in model.sink_bays] == pytest.approx(
        [18 * 25.4 + model.section.vanity.x0_mm,
         54 * 25.4 + model.section.vanity.x0_mm]
    )
    assert len(model.plumbing_paths) == 2
    assert len({path.path_id for path in model.plumbing_paths}) == 2
    assert all(path.trap_count == 1 for path in model.plumbing_paths)
    assert len(model.drawers) == 4
    assert {drawer.kind for drawer in model.drawers} == {
        "upper_u_service", "lower_short_service"
    }
    assert all(drawer.removable for drawer in model.drawers)
    assert all(drawer.runner.soft_close for drawer in model.drawers)
    assert all(drawer.runner.full_extension for drawer in model.drawers)
    for bay in ("left", "right"):
        upper = model.drawer(bay, "upper")
        lower = model.drawer(bay, "lower")
        assert upper.runner.family_id.startswith("blum_movento")
        assert upper.runner.minimum_drawer_length_mm == pytest.approx(457.0)
        assert upper.runner.minimum_inside_depth_mm == pytest.approx(477.0)
        assert upper.box_depth_mm >= upper.runner.minimum_drawer_length_mm
        assert lower.runner.family_id == "unselected_short_depth_runner@study"
        assert lower.runner.minimum_drawer_length_mm is None
        assert not lower.runner.selected_sku


def test_geometry_contains_four_physical_boxes_fronts_and_no_toe_kick():
    project = _project()
    roles = {part.role for part in project.model.parts}

    assert {
        "left_end", "center_divider", "right_end", "rear_mounting_rail",
        "drawer_front_left_upper", "drawer_front_left_lower",
        "drawer_front_right_upper", "drawer_front_right_lower",
    } <= roles
    assert not any(role.startswith("toe_") for role in roles)
    for bay in ("left", "right"):
        assert {
            f"drawer_{bay}_upper_side_left",
            f"drawer_{bay}_upper_side_right",
            f"drawer_{bay}_upper_front",
            f"drawer_{bay}_upper_back_left",
            f"drawer_{bay}_upper_back_right",
            f"drawer_{bay}_upper_bottom_left",
            f"drawer_{bay}_upper_bottom_right",
            f"drawer_{bay}_upper_bottom_bridge",
            f"drawer_{bay}_upper_inner_return_left",
            f"drawer_{bay}_upper_inner_return_right",
            f"drawer_{bay}_lower_side_left",
            f"drawer_{bay}_lower_side_right",
            f"drawer_{bay}_lower_front",
            f"drawer_{bay}_lower_back",
            f"drawer_{bay}_lower_bottom",
        } <= roles
    assert project.lowered_doc.type == "vanity_double_sink_floating_study"


def test_physical_upper_drawer_void_uses_declared_width_and_depth():
    model = _project().model

    for bay in ("left", "right"):
        drawer = model.drawer(bay, "upper")
        bridge = model.part(f"drawer_{bay}_upper_bottom_bridge")
        return_left = model.part(f"drawer_{bay}_upper_inner_return_left")
        return_right = model.part(f"drawer_{bay}_upper_inner_return_right")

        assert bridge.length_mm == pytest.approx(drawer.u_void_width_mm)
        assert bridge.width_mm == pytest.approx(
            drawer.box_depth_mm - drawer.u_void_depth_mm
        )
        assert return_left.length_mm == pytest.approx(drawer.u_void_depth_mm)
        assert return_right.length_mm == pytest.approx(drawer.u_void_depth_mm)
        assert return_right.at_mm[0] - (
            return_left.at_mm[0] + return_left.thickness_mm
        ) == pytest.approx(drawer.u_void_width_mm)


def test_unchanged_base_language_builds_and_has_no_unmodeled_geometry_failure():
    project = _project()
    assembly = project.build()
    base = project.validate()

    assert len(assembly.parts) == len(project.model.parts)
    assert base.ok, "\n".join(str(item) for item in base.blocking)
    assert not [
        finding for finding in project.report.findings
        if finding.verdict == "FAIL"
    ]
    assert not project.report.fabrication_ready
    assert not project.release_ready


def test_service_geometry_is_derived_from_fixture_and_plumbing_envelopes():
    model = _project().model

    for bay, path in zip(model.sink_bays, model.plumbing_paths):
        upper = model.drawer(bay.bay_id, "upper")
        lower = model.drawer(bay.bay_id, "lower")
        assert upper.u_void_width_mm == pytest.approx(
            path.service_envelope.width_mm
        )
        assert upper.u_void_depth_mm < path.service_envelope.depth_mm
        assert lower.box_depth_mm + model.service_chase_depth_mm \
            <= model.section.vanity.body_depth_mm
        assert bay.service_opening_smallest_mm == pytest.approx(
            min(bay.clear_opening_width_mm, bay.clear_opening_height_mm)
        )
        assert bay.service_opening_smallest_mm >= path.access_min_mm
        assert path.service_envelope.authority == "provisional_study_target"
        assert {element.kind for element in path.elements} >= {
            "fixture_body", "tailpiece", "p_trap", "trap_arm",
            "hot_supply", "cold_supply", "hot_shutoff", "cold_shutoff",
        }
        assert not upper.dynamic_verified
        assert not lower.dynamic_verified


def test_fixture_dimensions_drive_path_and_drawer_geometry(monkeypatch):
    import detailgen.packs.cabinetry.double_vanity as dv

    baseline = _project().model
    wider = replace(
        dv.K20000, overall_width_mm=650.0, overall_depth_mm=450.0,
    )
    monkeypatch.setattr(dv, "K20000", wider)
    changed = _project().model

    assert changed.plumbing_paths[0].fixture_envelope.width_mm == pytest.approx(650.0)
    assert changed.drawer("left", "upper").u_void_width_mm > (
        baseline.drawer("left", "upper").u_void_width_mm
    )
    assert changed.part("drawer_left_upper_bottom_bridge").width_mm != (
        baseline.part("drawer_left_upper_bottom_bridge").width_mm
    )
    assert changed.derived_fact_manifest() != baseline.derived_fact_manifest()


def test_impossible_fixture_fails_loudly_instead_of_emitting_fake_clearance(
    monkeypatch,
):
    import detailgen.packs.cabinetry.double_vanity as dv

    monkeypatch.setattr(
        dv, "K20000",
        replace(dv.K20000, overall_width_mm=1200.0, overall_depth_mm=900.0),
    )
    with pytest.raises(ProjectSchemaError, match="cannot form a positive U-drawer"):
        _project()


def test_duplicate_path_bay_ownership_and_missing_mount_parts_fail_validation():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    baseline_findings = {
        finding.rule: finding
        for finding in validate_double_vanity_model(model).findings
    }
    assert baseline_findings[
        "double_vanity.mount.representation"
    ].verdict == "PASS"
    duplicate = replace(
        model,
        plumbing_paths=(model.plumbing_paths[0], replace(
            model.plumbing_paths[1], bay_id="left",
        )),
    )
    duplicate_findings = {
        finding.rule: finding for finding in validate_double_vanity_model(duplicate).findings
    }
    assert duplicate_findings["double_vanity.plumbing.independent_traps"].verdict == "FAIL"

    mutations = (
        replace(
            model,
            parts=tuple(
                part for part in model.parts if part.role != "rear_mounting_rail"
            ),
        ),
        replace(
            model,
            parts=tuple(
                part for part in model.parts
                if part.role != f"wall_anchor_{model.anchor_stud_ids[0]}"
            ),
        ),
        replace(
            model,
            parts=tuple(
                part for part in model.parts
                if part.role != f"wall_stud_{model.anchor_stud_ids[0]}"
            ),
        ),
        replace(model, anchor_stud_ids=()),
    )
    for no_mount in mutations:
        mount_findings = {
            finding.rule: finding
            for finding in validate_double_vanity_model(no_mount).findings
        }
        assert mount_findings[
            "double_vanity.mount.representation"
        ].verdict == "FAIL"


def test_domain_geometry_checks_physical_u_void_and_named_bay_ownership():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model

    moved_returns = replace(
        model,
        parts=tuple(
            replace(part, at_mm=(
                part.at_mm[0] + (
                    100.0 if part.role.endswith("inner_return_left")
                    else -100.0
                ),
                part.at_mm[1], part.at_mm[2],
            ))
            if part.role in {
                "drawer_left_upper_inner_return_left",
                "drawer_left_upper_inner_return_right",
            }
            else part
            for part in model.parts
        ),
    )
    physical = {
        finding.rule: finding
        for finding in validate_double_vanity_model(moved_returns).findings
    }
    assert physical[
        "double_vanity.geometry.fixture_plumbing_drawer"
    ].verdict == "FAIL"

    right = model.plumbing_paths[1]

    def shift(envelope, dx):
        return replace(
            envelope,
            x0_mm=envelope.x0_mm + dx,
            x1_mm=envelope.x1_mm + dx,
        )

    dx = -model.section.vanity.width_mm / 2
    shifted = replace(
        right,
        fixture_envelope=shift(right.fixture_envelope, dx),
        elements=tuple(shift(element, dx) for element in right.elements),
        service_envelope=shift(right.service_envelope, dx),
    )
    wrong_bay = replace(
        model, plumbing_paths=(model.plumbing_paths[0], shifted),
    )
    wrong_bay_findings = {
        finding.rule: finding
        for finding in validate_double_vanity_model(wrong_bay).findings
    }
    assert wrong_bay_findings[
        "double_vanity.geometry.fixture_plumbing_drawer"
    ].verdict == "FAIL"
    assert wrong_bay_findings[
        "double_vanity.plumbing.independent_traps"
    ].verdict == "FAIL"


def test_plumbing_path_requires_every_element_and_connected_adjacencies():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    required = {
        "fixture_body", "tailpiece", "p_trap", "trap_arm",
        "hot_supply", "cold_supply", "hot_shutoff", "cold_shutoff",
    }
    left = model.plumbing_paths[0]
    assert {item.kind for item in left.elements} == required

    for omitted in sorted(required):
        path = replace(
            left,
            elements=tuple(
                item for item in left.elements if item.kind != omitted
            ),
        )
        broken = replace(
            model, plumbing_paths=(path, model.plumbing_paths[1]),
        )
        findings = {
            finding.rule: finding
            for finding in validate_double_vanity_model(broken).findings
        }
        assert findings[
            "double_vanity.plumbing.independent_traps"
        ].verdict == "FAIL", omitted

    displaced_elements = tuple(
        replace(item, y0_mm=item.y0_mm + 5000, y1_mm=item.y1_mm + 5000)
        if item.kind == "p_trap" else item
        for item in left.elements
    )
    disconnected = replace(
        model,
        plumbing_paths=(
            replace(left, elements=displaced_elements),
            model.plumbing_paths[1],
        ),
    )
    disconnected_findings = {
        finding.rule: finding
        for finding in validate_double_vanity_model(disconnected).findings
    }
    assert disconnected_findings[
        "double_vanity.plumbing.independent_traps"
    ].verdict == "FAIL"

    escaped_elements = tuple(
        replace(item, z0_mm=item.z0_mm - 500.0)
        if item.kind == "hot_supply" else item
        for item in left.elements
    )
    escaped = replace(
        model,
        plumbing_paths=(
            replace(left, elements=escaped_elements),
            model.plumbing_paths[1],
        ),
    )
    escaped_findings = {
        finding.rule: finding
        for finding in validate_double_vanity_model(escaped).findings
    }
    assert escaped_findings[
        "double_vanity.plumbing.independent_traps"
    ].verdict == "FAIL"


def test_lower_physical_box_checks_every_side_bottom_and_back():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    moved_right_side = replace(
        model,
        parts=tuple(
            replace(
                part,
                at_mm=(part.at_mm[0], part.at_mm[1] + 100.0, part.at_mm[2]),
            )
            if part.role == "drawer_left_lower_side_right" else part
            for part in model.parts
        ),
    )
    findings = {
        finding.rule: finding
        for finding in validate_double_vanity_model(moved_right_side).findings
    }
    assert findings[
        "double_vanity.geometry.fixture_plumbing_drawer"
    ].verdict == "FAIL"


def test_mount_expected_targets_come_from_the_survey_not_self_reported_ids():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    keep = model.anchor_stud_ids[0]
    reduced = replace(
        model,
        parts=tuple(
            part for part in model.parts
            if not part.role.startswith("wall_anchor_")
            or part.role == f"wall_anchor_{keep}"
        ),
        anchor_stud_ids=(keep,),
    )
    findings = {
        finding.rule: finding
        for finding in validate_double_vanity_model(reduced).findings
    }
    assert findings["double_vanity.mount.representation"].verdict == "FAIL"


def test_dynamic_verification_state_is_orthogonal_to_static_coordination():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    verified = replace(
        model,
        drawers=tuple(
            replace(drawer, dynamic_verified=True) for drawer in model.drawers
        ),
    )
    findings = {
        finding.rule: finding
        for finding in validate_double_vanity_model(verified).findings
    }
    assert findings[
        "double_vanity.geometry.fixture_plumbing_drawer"
    ].verdict == "PASS"


def test_unreleased_drawer_parts_are_not_emitted_as_cut_list_dimensions():
    project = _project()

    assert not any(
        item.role.startswith("drawer_") for item in project.artifacts.cut_list
    )


def test_nyc_and_ipc_profiles_pin_deliberate_vertical_trap_difference():
    from detailgen.packs.cabinetry.double_vanity import plumbing_code_profile

    nyc = plumbing_code_profile("nyc_2022")
    ipc = plumbing_code_profile("ipc_2024")
    assert nyc.lavatory_side_clearance_mm == pytest.approx(15 * 25.4)
    assert nyc.lavatory_center_spacing_mm == pytest.approx(30 * 25.4)
    assert nyc.front_clearance_mm == pytest.approx(21 * 25.4)
    assert nyc.outlet_to_trap_weir_vertical_max_mm == pytest.approx(48 * 25.4)
    assert ipc.outlet_to_trap_weir_vertical_max_mm == pytest.approx(24 * 25.4)


def test_all_nine_study_release_gates_are_required_unknown_and_block_release():
    project = _project()
    expected = {
        "double_vanity.release.fixture_template",
        "double_vanity.release.countertop_fabricator",
        "double_vanity.release.faucet",
        "double_vanity.release.site_survey",
        "double_vanity.release.plumbing_approval",
        "double_vanity.release.drawer_derivation",
        "double_vanity.release.dynamic_access",
        "double_vanity.release.wall_mount",
        "double_vanity.release.commissioning",
    }
    findings = {finding.rule: finding for finding in project.report.findings}

    assert expected <= findings.keys()
    assert all(findings[rule].severity == "required" for rule in expected)
    assert all(findings[rule].verdict == "UNKNOWN" for rule in expected)
    assert findings[
        "double_vanity.drawer.runner_applicability"
    ].verdict == "UNKNOWN"
    assert findings[
        "double_vanity.drawer.runner_applicability"
    ].severity == "advisory"
    assert len(project.report.blocking) == 9
    assert all(
        finding.rule.startswith("double_vanity.release.")
        for finding in project.report.blocking
    )
    assert not project.report.fabrication_ready
    with pytest.raises(ProjectReleaseError, match="fixture_template"):
        project.require_release()


def test_analytic_study_is_deterministic_with_no_external_asset_cache(monkeypatch):
    monkeypatch.delenv("DETAILGEN_CATALOG_ASSET_CACHE", raising=False)
    first = _project()
    second = _project()

    assert first.model == second.model
    assert first.lowered_doc == second.lowered_doc
    assert first.manifest_json() == second.manifest_json()
    assert all(not ref.may_embed for ref in first.model.catalog_assets)
    assert all(
        not ref.allows_consumer("local_preview_renderer")
        for ref in first.model.catalog_assets
    )
    assert "local_path" not in first.manifest_json()
