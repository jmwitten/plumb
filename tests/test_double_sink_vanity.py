"""DV72 opt-in pack: analytic fixtures, service drawers, and honest gates."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from detailgen.core.registry import components, materials
from detailgen.packs import ProjectReleaseError, compile_project_file


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

    assert asset.allows_consumer("renderer")
    for forbidden in ("cut_list", "machining", "plumbing", "structure", "code"):
        assert not asset.allows_consumer(forbidden)
    assert not asset.may_embed
    with pytest.raises(ValueError, match="64-character"):
        replace(asset, sha256_raw="not-a-digest")
    with pytest.raises(ValueError, match="three calibration anchors"):
        replace(asset, calibration_anchors=("drain_center",))


def test_dv72_expands_to_two_independent_service_bays_and_four_drawers():
    project = _project()
    model = project.model

    assert model.section.vanity.width_mm == pytest.approx(72 * 25.4)
    assert model.section.vanity.body_height_mm == pytest.approx(20 * 25.4)
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
            f"drawer_{bay}_lower_side_left",
            f"drawer_{bay}_lower_side_right",
            f"drawer_{bay}_lower_front",
            f"drawer_{bay}_lower_back",
            f"drawer_{bay}_lower_bottom",
        } <= roles
    assert project.lowered_doc.type == "vanity_double_sink_floating_study"


def test_service_geometry_is_derived_from_fixture_and_plumbing_envelopes():
    model = _project().model

    for bay, path in zip(model.sink_bays, model.plumbing_paths):
        upper = model.drawer(bay.bay_id, "upper")
        lower = model.drawer(bay.bay_id, "lower")
        assert upper.u_void_width_mm == pytest.approx(
            path.service_envelope.width_mm
        )
        assert upper.u_void_depth_mm >= path.service_envelope.depth_mm
        assert lower.box_depth_mm + model.service_chase_depth_mm \
            <= model.section.vanity.body_depth_mm
        assert bay.measured_service_opening_width_mm >= path.access_min_mm
        assert upper.closed_clearance_mm > 0
        assert upper.full_extension_clearance_mm > 0
        assert upper.removal_clearance_mm > 0
        assert lower.closed_clearance_mm > 0
        assert lower.full_extension_clearance_mm > 0
        assert lower.removal_clearance_mm > 0


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
    assert "local_path" not in first.manifest_json()

