"""DV72 opt-in pack: analytic fixtures, service drawers, and honest gates."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
import yaml

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


def _project_with_assumption(tmp_path, key, value):
    raw = yaml.safe_load(FIXTURE.read_text())
    raw["double_vanity"]["assumed_conditions"][key] = value
    path = tmp_path / f"dv72-{key}.project.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    return compile_project_file(path)


def test_owner_assumptions_are_explicit_and_never_field_verified():
    model = _project().model
    assert model.assumed_site.provenance == "owner_assumed"
    assert not model.assumed_site.field_verified
    assert model.assumed_site.wall_length_mm == pytest.approx(144 * 25.4)
    assert all(not stud.verified for stud in model.section.site.wall.studs)
    assert not model.section.site.floor.verified


def test_assumed_rough_ins_match_the_approved_schedule():
    basis = _project().model.assumed_site
    assert [p.x_mm for p in basis.wastes] == pytest.approx([42 * 25.4, 78 * 25.4])
    assert [p.z_mm for p in basis.wastes] == pytest.approx([19 * 25.4] * 2)
    assert [p.x_mm for p in basis.supplies] == pytest.approx(
        [38 * 25.4, 46 * 25.4, 74 * 25.4, 82 * 25.4]
    )


@pytest.mark.parametrize(
    ("key", "value", "match"),
    (
        ("wall_length", 145, "wall_length"),
        ("wall_height", 95, "wall_height"),
        ("finish_thickness", 0.625, "finish_thickness"),
        ("floor_elevation", 1, "floor_elevation"),
        ("vanity_left", 25, "vanity_left"),
    ),
)
def test_assumed_site_contradictions_fail_loudly(tmp_path, key, value, match):
    with pytest.raises(ProjectSchemaError, match=match):
        _project_with_assumption(tmp_path, key, value)


@pytest.mark.parametrize(
    ("key", "value", "match"),
    (
        ("provenance", "field_verified", "provenance"),
        ("field_verified", True, "field_verified"),
    ),
)
def test_assumptions_reject_false_authority(tmp_path, key, value, match):
    with pytest.raises(ProjectSchemaError, match=match):
        _project_with_assumption(tmp_path, key, value)


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
    assert upper.drawer_length_mm == pytest.approx(457.0)
    assert upper.minimum_inside_depth_mm == pytest.approx(477.0)

    assert catalog["comparative_mount"] == "rakks_eh_1818_lv@2022.1.0"
    assert model.mount_reference.static_capacity_lb == pytest.approx(450.0)
    assert model.mount_reference.capacity_basis == "evenly_distributed_static_load"
    assert project.report.by_rule("double_vanity.release.wall_mount").verdict == "UNKNOWN"


def test_three_supports_carry_gravity_without_rail_credit():
    model = _project().model

    assert len(model.support_layout.supports) == 3
    assert model.support_layout.max_spacing_mm <= 36 * 25.4
    assert model.support_layout.gravity_path == "rakks_eh_primary"
    assert model.support_layout.rear_rail_role == "positioning_and_lateral_only"
    assert model.support_layout.rear_rail_gravity_credit_lb == 0.0
    assert model.support_layout.backing_verification == "UNKNOWN"
    assert model.support_layout.product_revision_approval == "UNKNOWN"
    assert model.support_layout.fastener_installation == "UNKNOWN"
    assert model.support_layout.structural_approval == "UNKNOWN"
    assert model.support_layout.fastener_connection_capacity_lb is None
    assert model.load_case.load_factor == pytest.approx(1.5)
    assert model.load_case.factored_total_lb / 3 <= (
        model.mount_reference.static_capacity_lb
    )


def test_mount_layout_never_passes_unproved_reaction_distribution():
    project = _project()
    findings = {finding.rule: finding for finding in project.report.findings}

    assert findings["double_vanity.mount.layout"].verdict == "UNKNOWN"
    assert "reaction distribution" in findings["double_vanity.mount.layout"].message
    assert "equal-share" not in findings["double_vanity.mount.layout"].message
    assert findings["double_vanity.release.wall_mount"].verdict == "UNKNOWN"
    assert not project.model.assumed_site.field_verified


def test_mount_layout_fails_when_factored_load_exceeds_three_ratings():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    overloaded = replace(
        model,
        load_case=replace(model.load_case, service_live_lb=1000.0),
    )

    assert validate_double_vanity_model(overloaded).by_rule(
        "double_vanity.mount.layout"
    ).verdict == "FAIL"


def test_mount_layout_fails_when_a_primary_support_is_removed():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    two_supports = replace(
        model,
        support_layout=replace(
            model.support_layout,
            supports=(
                model.support_layout.supports[0],
                model.support_layout.supports[2],
            ),
        ),
    )

    assert two_supports.support_layout.max_spacing_mm > 36 * 25.4
    assert validate_double_vanity_model(two_supports).by_rule(
        "double_vanity.mount.layout"
    ).verdict == "FAIL"


def test_mount_layout_fails_when_support_misses_case_top_bearing():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    moved = replace(
        model.support_layout.supports[0],
        bearing_z_mm=model.support_layout.supports[0].bearing_z_mm - 25.4,
    )
    no_bearing = replace(
        model,
        support_layout=replace(
            model.support_layout,
            supports=(moved,) + model.support_layout.supports[1:],
        ),
    )

    assert validate_double_vanity_model(no_bearing).by_rule(
        "double_vanity.mount.layout"
    ).verdict == "FAIL"


def test_mount_layout_rejects_no_backing_and_keeps_installation_blocked(tmp_path):
    project = _project_with_assumption(tmp_path, "backing", "none")
    findings = {finding.rule: finding for finding in project.report.findings}

    assert findings["double_vanity.mount.layout"].verdict == "FAIL"
    assert findings["double_vanity.release.wall_mount"].verdict == "UNKNOWN"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("adapter_id", "rakks_eh_1818_lv@2099.9.9"),
        ("manufacturer", "Not Rakks"),
        ("sku", "EH-FAKE"),
        ("width_mm", 19 * 25.4),
        ("depth_mm", 22 * 25.4),
        ("static_capacity_lb", 451.0),
        ("capacity_basis", "unpublished_ultimate_load"),
        ("required_screws_per_bracket", 3),
        ("maximum_spacing_mm", 49 * 25.4),
        ("authority", "STRUCTURAL_ENGINEER_APPROVED"),
        ("specification_url", "https://example.invalid/pinned.pdf"),
        ("current_specification_url", "https://example.invalid/current.pdf"),
        ("acceptable_applications", ("drywall",)),
    ),
)
def test_mount_layout_rejects_mutated_rakks_contract(field, value):
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    mutated = replace(
        model,
        mount_reference=replace(model.mount_reference, **{field: value}),
    )

    assert validate_double_vanity_model(mutated).by_rule(
        "double_vanity.mount.layout"
    ).verdict == "FAIL"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("quartz_countertop_lb", 0.0),
        ("plywood_casework_lb", 0.0),
        ("sinks_lb", 0.0),
        ("hardware_plumbing_lb", 0.0),
        ("water_lb", 0.0),
        ("contents_lb", 0.0),
        ("service_live_lb", 0.0),
        ("load_factor", 1.49),
        ("quartz_density_pcf", 164.0),
        ("plywood_density_pcf", 44.0),
    ),
)
def test_mount_layout_rejects_mutated_load_case(field, value):
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    mutated = replace(
        model,
        load_case=replace(model.load_case, **{field: value}),
    )

    assert validate_double_vanity_model(mutated).by_rule(
        "double_vanity.mount.layout"
    ).verdict == "FAIL"


def test_mount_layout_rederives_quartz_and_plywood_dead_loads():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    thicker_slab = replace(
        model,
        section=replace(
            model.section,
            vanity=replace(
                model.section.vanity,
                countertop_thickness_mm=31.0,
            ),
        ),
    )
    first_panel = next(
        part for part in model.parts if part.component_type == "plywood_panel"
    )
    thicker_plywood = replace(
        model,
        parts=tuple(
            replace(part, thickness_mm=part.thickness_mm + 1.0)
            if part.part_id == first_panel.part_id else part
            for part in model.parts
        ),
    )

    for mutated in (thicker_slab, thicker_plywood):
        assert validate_double_vanity_model(mutated).by_rule(
            "double_vanity.mount.layout"
        ).verdict == "FAIL"


def test_mount_layout_rejects_fake_support_envelope_authority():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    fake_approval = replace(
        model.support_layout.supports[0],
        authority="STRUCTURAL_ENGINEER_APPROVED",
    )
    mutated = replace(
        model,
        support_layout=replace(
            model.support_layout,
            supports=(fake_approval,) + model.support_layout.supports[1:],
        ),
    )

    assert validate_double_vanity_model(mutated).by_rule(
        "double_vanity.mount.layout"
    ).verdict == "FAIL"


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
    assert model.section.vanity.body_height_mm == pytest.approx(
        34.5 * 25.4 - 11 * 25.4 - 30.0
    )
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
        assert upper.runner.drawer_length_mm == pytest.approx(457.0)
        assert upper.runner.minimum_inside_depth_mm == pytest.approx(477.0)
        assert upper.box_depth_mm == pytest.approx(
            upper.runner.drawer_length_mm
        )
        assert lower.runner.family_id.startswith("blum_movento")
        assert lower.runner.drawer_length_mm == pytest.approx(305.0)
        assert lower.runner.minimum_inside_depth_mm == pytest.approx(325.0)
        assert lower.box_depth_mm == pytest.approx(
            lower.runner.drawer_length_mm
        )


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
    countertop_underside = (
        model.section.vanity.bottom_elevation_mm
        + model.section.vanity.body_height_mm
    )

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
        assert path.fixture_envelope.z1_mm == pytest.approx(countertop_underside)


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


def test_drain_and_trap_dimensions_drive_geometry(monkeypatch):
    import detailgen.packs.cabinetry.double_vanity as dv

    baseline = _project().model
    monkeypatch.setattr(dv, "K7124_A", replace(dv.K7124_A, body_height_mm=160.0))
    monkeypatch.setattr(dv, "K8998", replace(dv.K8998, overall_length_mm=330.0))
    changed = _project().model

    assert changed.plumbing_paths[0].element("tailpiece").height_mm != pytest.approx(
        baseline.plumbing_paths[0].element("tailpiece").height_mm
    )
    assert changed.plumbing_paths[0].element("p_trap").depth_mm != pytest.approx(
        baseline.plumbing_paths[0].element("p_trap").depth_mm
    )


def test_lower_drawers_use_selected_12_in_movento():
    model = _project().model

    for bay in ("left", "right"):
        runner = model.drawer(bay, "lower").runner
        assert runner.selected_sku == "763.3050S"
        assert runner.drawer_length_mm == pytest.approx(305.0)
        assert runner.minimum_inside_depth_mm == pytest.approx(325.0)


def test_movento_contract_drives_box_width_stock_and_length_by_role():
    model = _project().model
    cabinet_opening_width = model.sink_bays[0].clear_opening_width_mm

    for bay in ("left", "right"):
        for level, nominal in (("upper", 457.0), ("lower", 305.0)):
            drawer = model.drawer(bay, level)
            runner = drawer.runner
            left = model.part(f"drawer_{bay}_{level}_side_left")
            right = model.part(f"drawer_{bay}_{level}_side_right")

            assert runner.inside_drawer_width_deduction_mm == pytest.approx(42.0)
            assert runner.maximum_drawer_side_thickness_mm == pytest.approx(16.0)
            assert runner.drawer_length_mm == pytest.approx(nominal)
            assert drawer.box_depth_mm == pytest.approx(nominal)
            assert drawer.box_width_mm == pytest.approx(
                cabinet_opening_width - 12.0
            )
            assert drawer.box_width_mm - 2 * left.thickness_mm == pytest.approx(
                cabinet_opening_width - 42.0
            )
            assert right.at_mm[0] + right.thickness_mm - left.at_mm[0] \
                == pytest.approx(drawer.box_width_mm)
            assert max(left.thickness_mm, right.thickness_mm) <= (
                runner.maximum_drawer_side_thickness_mm
            )
            assert runner.mounting_authority == (
                "WITHHELD_MANUFACTURER_TEMPLATE_CONTROLLED"
            )
            assert runner.machining_authority == (
                "WITHHELD_MANUFACTURER_TEMPLATE_CONTROLLED"
            )
    assert model.machining == ()
    assert _project().artifacts.machining_schedule == ()


def _cut_roles_for_mutated_model(model):
    from detailgen.packs.cabinetry.double_vanity import (
        build_double_vanity_artifacts,
        validate_double_vanity_model,
    )

    report = validate_double_vanity_model(model)
    artifacts = build_double_vanity_artifacts(model, report)
    return report, {item.role for item in artifacts.cut_list}


def test_wrong_runner_lateral_clearance_withdraws_drawer_cut_authority():
    model = _project().model
    mutated = replace(
        model,
        drawers=tuple(
            replace(
                drawer,
                runner=replace(
                    drawer.runner,
                    inside_drawer_width_deduction_mm=50.0,
                ),
            )
            for drawer in model.drawers
        ),
    )

    report, roles = _cut_roles_for_mutated_model(mutated)
    assert report.by_rule(
        "double_vanity.drawer.runner_applicability"
    ).verdict == "FAIL"
    assert not any(role.startswith("drawer_") for role in roles)


def test_oversize_modeled_drawer_side_withdraws_drawer_cut_authority():
    model = _project().model
    mutated = replace(
        model,
        parts=tuple(
            replace(part, thickness_mm=17.0)
            if part.role == "drawer_left_upper_side_left" else part
            for part in model.parts
        ),
    )

    report, roles = _cut_roles_for_mutated_model(mutated)
    assert report.by_rule(
        "double_vanity.drawer.runner_applicability"
    ).verdict == "FAIL"
    assert not any(role.startswith("drawer_") for role in roles)


def test_wrong_modeled_drawer_length_withdraws_drawer_cut_authority():
    model = _project().model
    mutated = replace(
        model,
        parts=tuple(
            replace(part, length_mm=part.length_mm + 1.0)
            if part.role == "drawer_right_lower_side_right" else part
            for part in model.parts
        ),
    )

    report, roles = _cut_roles_for_mutated_model(mutated)
    assert report.by_rule(
        "double_vanity.drawer.runner_applicability"
    ).verdict == "FAIL"
    assert not any(role.startswith("drawer_") for role in roles)


def test_product_and_assumed_rough_in_dimensions_drive_path_envelopes():
    model = _project().model

    for bay, path in zip(model.sink_bays, model.plumbing_paths):
        waste = min(
            model.assumed_site.wastes,
            key=lambda point: abs(point.x_mm - bay.sink_center_x_mm),
        )
        tailpiece = path.element("tailpiece")
        p_trap = path.element("p_trap")
        trap_arm = path.element("trap_arm")
        assert tailpiece.width_mm == pytest.approx(model.drain.connection_od_mm)
        assert tailpiece.height_mm == pytest.approx(model.drain.body_height_mm)
        assert p_trap.depth_mm == pytest.approx(model.trap.overall_length_mm)
        assert p_trap.height_mm == pytest.approx(model.trap.overall_height_mm)
        assert "gross_bounding_envelope" in p_trap.authority
        assert trap_arm.x0_mm <= waste.x_mm <= trap_arm.x1_mm
        assert trap_arm.y1_mm == pytest.approx(waste.y_mm)
        assert trap_arm.z0_mm <= waste.z_mm <= trap_arm.z1_mm
        for kind in ("hot_supply", "cold_supply"):
            point = min(
                (item for item in model.assumed_site.supplies if item.kind == kind),
                key=lambda item: abs(item.x_mm - bay.sink_center_x_mm),
            )
            supply = path.element(kind)
            assert (supply.x0_mm + supply.x1_mm) / 2 == pytest.approx(point.x_mm)
            assert supply.y1_mm == pytest.approx(point.y_mm)
            assert (supply.z0_mm + supply.z1_mm) / 2 == pytest.approx(point.z_mm)


def test_selected_products_and_runner_geometry_pass_static_coordination():
    findings = {finding.rule: finding for finding in _project().report.findings}

    assert findings[
        "double_vanity.geometry.fixture_plumbing_drawer"
    ].verdict == "PASS"
    assert findings["double_vanity.drawer.runner_applicability"].verdict == "PASS"


def test_selected_drain_and_trap_contradictions_fail_geometry():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    impossible = replace(
        model,
        drain=replace(
            model.drain, body_height_mm=800.0, connection_od_mm=70.0,
        ),
        trap=replace(
            model.trap,
            inlet_od_mm=70.0,
            outlet_od_mm=70.0,
            overall_length_mm=800.0,
            overall_height_mm=500.0,
        ),
    )
    findings = {
        finding.rule: finding
        for finding in validate_double_vanity_model(impossible).findings
    }
    coordination = findings[
        "double_vanity.geometry.fixture_plumbing_drawer"
    ]
    assert coordination.verdict == "FAIL"


def test_missing_product_authority_keeps_static_coordination_unknown():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    missing = replace(model, drain=replace(model.drain, adapter_id=""))
    finding = validate_double_vanity_model(missing).by_rule(
        "double_vanity.geometry.fixture_plumbing_drawer"
    )

    assert finding.verdict == "UNKNOWN"


def test_drain_outlet_must_reach_oriented_trap_not_merely_overlap():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    left = model.plumbing_paths[0]
    tailpiece = left.element("tailpiece")
    shifted_tailpiece = replace(
        tailpiece,
        x0_mm=tailpiece.x0_mm + 40.0,
        x1_mm=tailpiece.x1_mm + 40.0,
    )
    shifted = replace(
        left,
        elements=tuple(
            shifted_tailpiece if item.kind == "tailpiece" else item
            for item in left.elements
        ),
    )
    finding = validate_double_vanity_model(replace(
        model, plumbing_paths=(shifted, model.plumbing_paths[1]),
    )).by_rule("double_vanity.geometry.fixture_plumbing_drawer")

    assert shifted_tailpiece.touches_or_intersects(left.element("p_trap"))
    assert finding.verdict == "FAIL"

    short_height = 50.0
    short_tailpiece = replace(
        tailpiece,
        z0_mm=left.fixture_envelope.z0_mm - short_height,
    )
    short_path = replace(
        left,
        elements=tuple(
            short_tailpiece if item.kind == "tailpiece" else item
            for item in left.elements
        ),
    )
    short_model = replace(
        model,
        drain=replace(model.drain, body_height_mm=short_height),
        plumbing_paths=(short_path, model.plumbing_paths[1]),
    )
    assert not short_tailpiece.touches_or_intersects(left.element("p_trap"))
    assert validate_double_vanity_model(short_model).by_rule(
        "double_vanity.geometry.fixture_plumbing_drawer"
    ).verdict == "FAIL"


def test_wrong_nonempty_product_and_runner_identities_do_not_pass():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    product_mutations = (
        replace(model, sink=replace(model.sink, adapter_id="other_sink@1")),
        replace(model, drain=replace(model.drain, adapter_id="other_drain@1")),
        replace(model, trap=replace(model.trap, adapter_id="other_trap@1")),
    )
    for mutation in product_mutations:
        finding = validate_double_vanity_model(mutation).by_rule(
            "double_vanity.geometry.fixture_plumbing_drawer"
        )
        assert finding.verdict != "PASS"

    for level in ("upper", "lower"):
        wrong_runner = replace(
            model,
            drawers=tuple(
                replace(drawer, runner=replace(
                    drawer.runner, selected_sku="999.9999X",
                ))
                if drawer.level == level else drawer
                for drawer in model.drawers
            ),
        )
        report = validate_double_vanity_model(wrong_runner)
        assert report.by_rule(
            "double_vanity.geometry.fixture_plumbing_drawer"
        ).verdict != "PASS"
        assert report.by_rule(
            "double_vanity.drawer.runner_applicability"
        ).verdict != "PASS"


def test_runner_inside_depth_uses_modeled_installation_span_not_gross_depth():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    gross_depth = model.section.vanity.body_depth_mm
    usable_depth = gross_depth - 22.0
    required_depth = (gross_depth + usable_depth) / 2
    too_deep = replace(
        model,
        drawers=tuple(
            replace(drawer, runner=replace(
                drawer.runner, minimum_inside_depth_mm=required_depth,
            ))
            for drawer in model.drawers
        ),
    )
    report = validate_double_vanity_model(too_deep)

    assert usable_depth < required_depth < gross_depth
    assert report.by_rule(
        "double_vanity.geometry.fixture_plumbing_drawer"
    ).verdict == "FAIL"
    assert report.by_rule(
        "double_vanity.drawer.runner_applicability"
    ).verdict == "FAIL"


def test_each_rough_in_point_has_exactly_one_bay_owner():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    duplicate_waste = replace(
        model.assumed_site.wastes[0],
        point_id="left_waste_duplicate",
    )
    duplicated = replace(
        model,
        assumed_site=replace(
            model.assumed_site,
            wastes=model.assumed_site.wastes + (duplicate_waste,),
        ),
    )
    finding = validate_double_vanity_model(duplicated).by_rule(
        "double_vanity.geometry.fixture_plumbing_drawer"
    )

    assert finding.verdict == "FAIL"


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


def test_30_mm_countertop_keeps_finished_height():
    model = _project().model

    assert model.countertop.structural_thickness_mm == pytest.approx(30.0)
    assert model.countertop.visual_edge_height_mm == pytest.approx(38.0)
    assert model.section.vanity.countertop_thickness_mm == pytest.approx(
        model.countertop.structural_thickness_mm
    )
    total = (
        model.section.vanity.bottom_elevation_mm
        + model.section.vanity.body_height_mm
        + model.section.vanity.countertop_thickness_mm
    )
    assert total == pytest.approx(34.5 * 25.4)


def test_pending_acceptance_emits_prepared_drawers_but_withholds_production_and_stone():
    project = _project()
    roles = {item.role for item in project.artifacts.cut_list}

    assert "drawer_left_upper_bottom_bridge" in roles
    assert "drawer_right_lower_bottom" in roles
    assert "countertop" not in roles
    assert project.model.release.fabrication_status == (
        "HOLD_FABRICATOR_ACCEPTANCE"
    )
    assert project.model.fabrication_acceptance.status == "PENDING"
    assert not project.artifacts.fabrication_ready
    assert project.model.release.installation_status == "HOLD_FIELD_VERIFY"
    assert project.model.countertop.stone_cut_authority == (
        "WITHHELD_UNTIL_FABRICATOR_ACCEPTS_K-20000_TEMPLATE"
    )


def test_trap_beyond_case_depth_withdraws_drawer_dimensions_or_fails_loudly(
    monkeypatch,
):
    import detailgen.packs.cabinetry.double_vanity as dv

    monkeypatch.setattr(
        dv,
        "K8998",
        replace(dv.K8998, overall_length_mm=1000.0),
    )
    with pytest.raises(
        ProjectSchemaError,
        match="left K-8998 trap depth exceeds the vanity case depth",
    ):
        _project()


def test_missing_sink_template_withholds_stone_without_invalidating_cabinet(
    monkeypatch,
):
    import detailgen.packs.cabinetry.double_vanity as dv

    monkeypatch.setattr(
        dv,
        "K20000",
        replace(dv.K20000, cutout_template_id=""),
    )
    project = _project()
    roles = {item.role for item in project.artifacts.cut_list}

    assert project.model.countertop.cutout_template_id == ""
    assert "countertop" not in roles
    assert "left_end" in roles
    assert "drawer_left_upper_bottom_bridge" in roles


def test_pending_fabrication_instruction_is_prepared_nonproduction_and_scoped():
    project = _project()
    instruction = " ".join(
        step.instruction for step in project.artifacts.fabrication_steps
    )

    assert "PREPARED CABINET/DRAWER CUT SCHEDULE" in instruction
    assert "NON-PRODUCTION" in instruction
    assert "fabrication remains held" in instruction
    assert "stone" in instruction.lower()
    assert "wall drilling" in instruction.lower()
    assert "installation" in instruction.lower()
    assert "do not purchase, cut, drill, fabricate, or install" not in instruction


def test_physical_drawer_boxes_have_exact_six_mm_clearance_at_case_faces():
    project = _project()
    assembly = project.build()
    placed = {item.reader_name: item for item in assembly.parts}

    def bounds(name):
        box = placed[name].world_solid().val().BoundingBox()
        return box.xmin, box.xmax

    case = {
        role: bounds(f"DV72 {role.replace('_', ' ')}")
        for role in ("left_end", "center_divider", "right_end")
    }
    openings = {
        "left": (case["left_end"][1], case["center_divider"][0]),
        "right": (case["center_divider"][1], case["right_end"][0]),
    }
    for bay in ("left", "right"):
        for level in ("upper", "lower"):
            names = [
                item.reader_name for item in assembly.parts
                if item.reader_name.startswith(f"DV72 drawer {bay} {level} ")
            ]
            part_bounds = [bounds(name) for name in names]
            outer = min(value[0] for value in part_bounds), max(
                value[1] for value in part_bounds
            )
            assert outer[0] == pytest.approx(openings[bay][0] + 6.0)
            assert outer[1] == pytest.approx(openings[bay][1] - 6.0)
            assert all(
                openings[bay][0] <= x0 <= x1 <= openings[bay][1]
                for x0, x1 in part_bounds
            )


def test_lateral_drawer_mutation_fails_runner_applicability_loudly():
    from detailgen.packs.cabinetry.double_vanity import validate_double_vanity_model

    model = _project().model
    mutated = replace(
        model,
        parts=tuple(
            replace(part, at_mm=(part.at_mm[0] - 1, *part.at_mm[1:]))
            if part.role == "drawer_left_upper_side_left" else part
            for part in model.parts
        ),
    )
    assert validate_double_vanity_model(mutated).by_rule(
        "double_vanity.drawer.runner_applicability"
    ).verdict == "FAIL"


def test_typed_fabrication_basis_and_acceptance_gate_production():
    from detailgen.packs.cabinetry.double_vanity import (
        FabricationAcceptance,
        apply_fabrication_acceptance,
        build_double_vanity_artifacts,
        validate_double_vanity_model,
    )

    model = _project().model
    with pytest.raises(FrozenInstanceError):
        model.fabrication_basis.version = "2"  # type: ignore[misc]
    assert len(model.fabrication_basis.digest()) == 64
    assert all("study plywood" not in item.material for item in _project().artifacts.cut_list)
    assert _project().artifacts.edge_banding
    accepted = apply_fabrication_acceptance(model, FabricationAcceptance(
        status="ACCEPTED", accepted_by="Example Cabinet Fabricator",
        accepted_on="2026-07-15",
        basis_digest=model.fabrication_basis.digest(),
        evidence_revision="signed-shop-basis-r1",
    ))
    artifacts = build_double_vanity_artifacts(
        accepted, validate_double_vanity_model(accepted),
    )
    assert artifacts.fabrication_ready
    assert "PRODUCTION AUTHORIZED" in artifacts.fabrication_steps[0].instruction
    with pytest.raises(ProjectSchemaError, match="exact fabrication-basis digest"):
        apply_fabrication_acceptance(model, FabricationAcceptance(
            status="ACCEPTED", accepted_by="Example Cabinet Fabricator",
            accepted_on="2026-07-15", basis_digest="0" * 64,
            evidence_revision="signed-shop-basis-r1",
        ))


def test_every_dv72_edge_band_uses_the_shared_physical_edge_length():
    from detailgen.packs.cabinetry.artifacts import edge_band_length

    project = _project()
    for item in project.artifacts.edge_banding:
        part = next(
            part for part in project.model.parts if part.part_id == item.part_id
        )
        assert item.length_mm == pytest.approx(edge_band_length(part, item.edge))


def test_impossible_acceptance_date_and_incoherent_basis_are_rejected():
    from detailgen.packs.cabinetry.double_vanity import (
        FabricationAcceptance,
        apply_fabrication_acceptance,
    )

    model = _project().model
    with pytest.raises(ProjectSchemaError, match="valid normalized ISO date"):
        apply_fabrication_acceptance(model, FabricationAcceptance(
            status="ACCEPTED", accepted_by="Example Cabinet Fabricator",
            accepted_on="2026-99-99", basis_digest=model.fabrication_basis.digest(),
            evidence_revision="signed-shop-basis-r1",
        ))
    changed = replace(
        model,
        fabrication_basis=replace(
            model.fabrication_basis,
            countertop_structural_thickness_mm=40.0,
        ),
    )
    with pytest.raises(ProjectSchemaError, match="fabrication basis contradicts"):
        apply_fabrication_acceptance(changed, FabricationAcceptance(
            status="ACCEPTED", accepted_by="Example Cabinet Fabricator",
            accepted_on="2026-07-15",
            basis_digest=changed.fabrication_basis.digest(),
            evidence_revision="signed-shop-basis-r1",
        ))


def test_coherent_accepted_project_validates_and_serializes_typed_authority():
    from detailgen.packs.cabinetry.double_vanity import (
        FabricationAcceptance,
        accept_double_vanity_project,
    )

    pending = _project()
    acceptance = FabricationAcceptance(
        status="ACCEPTED", accepted_by="Example Cabinet Fabricator",
        accepted_on="2026-07-15",
        basis_digest=pending.model.fabrication_basis.digest(),
        evidence_revision="signed-shop-basis-r1",
    )
    accepted = accept_double_vanity_project(pending, acceptance)
    assert len(accepted.build().parts) == len(accepted.model.parts)
    assert accepted.validate().ok
    assert accepted.fabrication_ready
    assert accepted.require_fabrication_release() is accepted
    payload = accepted.manifest()
    assert payload["artifacts"]["fabrication_ready"] is True
    assert payload["artifacts"]["release_contract"] == (
        "typed_fabrication_acceptance/v1"
    )
    audit = payload["artifacts"]["fabrication_audit"]
    assert audit["basis_digest"] == acceptance.basis_digest
    assert audit["accepted_by"] == acceptance.accepted_by
    assert accepted.artifacts.hardware_schedule[0].quantity == 0
    assert "quantity and procurement are not authorized" in (
        accepted.artifacts.hardware_schedule[0].procurement_note
    )
    assert not pending.fabrication_ready
    pending.validate()
    assert not pending.fabrication_ready
    assert pending.artifacts.release_contract == "typed_fabrication_acceptance/v1"


def test_invalid_edge_schedule_cannot_emit_fabrication_authority():
    from detailgen.packs.cabinetry.double_vanity import (
        build_double_vanity_artifacts,
        validate_double_vanity_model,
    )

    model = _project().model
    invalid = replace(
        model,
        parts=tuple(
            replace(part, edge_bands=("diagonal",))
            if part.role == "left_end" else part
            for part in model.parts
        ),
    )
    with pytest.raises(ValueError, match="unknown edge-band edge"):
        build_double_vanity_artifacts(
            invalid, validate_double_vanity_model(invalid),
        )


def test_manual_acceptance_replace_cannot_cross_the_sole_transition_gate():
    from detailgen.packs.cabinetry.double_vanity import (
        FabricationAcceptance,
        build_double_vanity_artifacts,
        validate_double_vanity_model,
    )

    pending = _project()
    acceptance = FabricationAcceptance(
        status="ACCEPTED", accepted_by="Example Cabinet Fabricator",
        accepted_on="2026-07-15",
        basis_digest=pending.model.fabrication_basis.digest(),
        evidence_revision="signed-shop-basis-r1",
    )
    forged_model = replace(
        pending.model, fabrication_acceptance=acceptance,
    )
    assert not forged_model.fabrication_release_contract()[0]
    with pytest.raises(ProjectSchemaError, match="canonical transition"):
        build_double_vanity_artifacts(
            forged_model, validate_double_vanity_model(forged_model),
        )
    forged_project = replace(pending, model=forged_model)
    with pytest.raises(ProjectSchemaError, match="artifact authority disagree"):
        forged_project.validate()
    assert not forged_project.fabrication_ready
    with pytest.raises(ProjectReleaseError):
        forged_project.require_fabrication_release()
    from detailgen.packs.cabinetry.double_vanity_documents import (
        build_double_vanity_document_set,
    )
    with pytest.raises(ValueError, match="authority state is inconsistent"):
        build_double_vanity_document_set(forged_project)


def test_co_mutated_40mm_granite_basis_requires_full_regeneration():
    from detailgen.packs.cabinetry.double_vanity import (
        FabricationAcceptance,
        apply_fabrication_acceptance,
    )

    model = _project().model
    basis = replace(
        model.fabrication_basis,
        countertop_material="granite",
        countertop_structural_thickness_mm=40.0,
    )
    mutated = replace(
        model,
        fabrication_basis=basis,
        countertop=replace(
            model.countertop, material="granite", structural_thickness_mm=40.0,
        ),
        section=replace(
            model.section,
            vanity=replace(
                model.section.vanity, countertop_thickness_mm=40.0,
            ),
        ),
    )
    with pytest.raises(ProjectSchemaError, match="substitutions require regeneration"):
        apply_fabrication_acceptance(mutated, FabricationAcceptance(
            status="ACCEPTED", accepted_by="Example Cabinet Fabricator",
            accepted_on="2026-07-15", basis_digest=basis.digest(),
            evidence_revision="signed-shop-basis-r1",
        ))


def test_fabrication_audit_is_frozen_typed_evidence():
    from detailgen.packs.cabinetry.artifacts import FabricationAudit

    audit = _project().artifacts.fabrication_audit
    assert isinstance(audit, FabricationAudit)
    with pytest.raises(FrozenInstanceError):
        audit.accepted_by = "forged"  # type: ignore[misc]


def test_countertop_load_and_model_project_the_canonical_basis():
    model = _project().model
    basis = model.fabrication_basis
    vanity = model.section.vanity
    expected_volume_ft3 = (
        vanity.width_mm * vanity.countertop_depth_mm
        * basis.countertop_structural_thickness_mm
        / (12 * 25.4) ** 3
    )
    assert vanity.countertop_thickness_mm == (
        basis.countertop_structural_thickness_mm
    )
    assert model.countertop.structural_thickness_mm == (
        basis.countertop_structural_thickness_mm
    )
    assert model.countertop.material == basis.countertop_material
    assert model.load_case.quartz_countertop_lb == pytest.approx(
        expected_volume_ft3 * model.load_case.quartz_density_pcf
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
    ].verdict == "PASS"
    assert findings[
        "double_vanity.drawer.runner_applicability"
    ].severity == "advisory"
    assert len(project.report.blocking) == 10
    assert findings[
        "double_vanity.geometry.fixture_plumbing_drawer"
    ].verdict == "PASS"
    assert {finding.rule for finding in project.report.blocking} == (
        expected | {"double_vanity.mount.layout"}
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
