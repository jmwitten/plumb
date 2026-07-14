"""Closed manufacturer adapters for the DB40 drawer hardware system."""

from __future__ import annotations

import pytest

from detailgen.packs import ProjectSchemaError


def test_movento_21_in_runner_pins_geometry_rating_and_soft_close():
    from detailgen.packs.cabinetry.catalogs import get_drawer_runner

    runner = get_drawer_runner("blum_movento_763_5330s@2026.1")

    assert runner.manufacturer == "Blum"
    assert runner.sku == "763.5330S"
    assert runner.nominal_length_mm == pytest.approx(533)
    assert runner.physical_length_mm == pytest.approx(544)
    assert runner.minimum_inside_depth_mm == pytest.approx(553)
    assert runner.maximum_side_thickness_mm == pytest.approx(16)
    assert runner.inside_width_deduction_mm == pytest.approx(42)
    assert runner.bottom_recess_mm == pytest.approx(13)
    assert runner.bottom_clearance_mm == pytest.approx(16)
    assert runner.minimum_rear_notch_mm == pytest.approx(50)
    assert runner.hook_bore_mm == pytest.approx((6, 10))
    assert runner.hook_bore_inset_from_side_mm == pytest.approx(7)
    assert runner.hook_bore_height_from_bottom_mm == pytest.approx(11)
    assert runner.minimum_top_clearance_mm == pytest.approx(7)
    assert runner.opening_height_deduction_mm == pytest.approx(23)
    assert runner.front_setback_mm == pytest.approx(3)
    assert runner.mounting_line_mm == pytest.approx(37)
    assert runner.required_rear_fixing_stations_mm == pytest.approx((261, 357))
    assert runner.installation_screw_product_id == "blum_606n_no6x5_8@2026.1"
    assert runner.installation_screw_sku == "606N"
    assert runner.installation_screws_per_runner == 2
    assert runner.static_rating_lb == pytest.approx(125)
    assert runner.dynamic_rating_lb == pytest.approx(110)
    assert runner.motion == "blumotion_soft_close"
    assert runner.source_url.startswith("https://d2.blum.com/")


def test_locking_device_adapter_pins_handed_pair_and_adjustment():
    from detailgen.packs.cabinetry.catalogs import get_drawer_locking_device

    locking = get_drawer_locking_device("blum_t51_7601_pair@2026.1")

    assert locking.left_sku == "T51.7601 L"
    assert locking.right_sku == "T51.7601 R"
    assert locking.quantity_per_drawer == 2
    assert locking.minimum_inside_drawer_width_mm == pytest.approx(170)
    assert locking.side_adjustment_mm == pytest.approx((-1.5, 1.5))
    assert locking.pilot_bore_diameter_mm == pytest.approx(2.5)
    assert locking.pilot_bore_depth_mm == pytest.approx(10)
    assert locking.pilot_bores_per_device == 2
    assert locking.installation_angle_deg == pytest.approx(75)
    assert locking.installation_screw_product_id == \
        "blum_606n_no6x5_8@2026.1"
    assert locking.installation_screw_sku == "606N"
    assert locking.installation_screw_quantity_per_device == 2
    assert locking.installation_screw_length_mm == pytest.approx(15.875)
    assert locking.mass_per_device_kg == pytest.approx(0.05626)
    assert locking.mass_source_url
    assert locking.template_sku == "T65.1600.01"
    assert locking.source_url.startswith("https://d2.blum.com/")


def test_lateral_stabilizer_is_required_by_width_but_adds_no_capacity():
    from detailgen.packs.cabinetry.catalogs import get_lateral_stabilizer

    stabilizer = get_lateral_stabilizer("blum_zs7m686mu@2026.1")

    assert stabilizer.sku == "ZS7M686MU"
    assert stabilizer.recommended_from_opening_mm == pytest.approx(610)
    assert stabilizer.maximum_opening_mm == pytest.approx(1369)
    assert stabilizer.linkage_rod_length_mm == pytest.approx(1051)
    assert stabilizer.linkage_rod_cut_deduction_mm == pytest.approx(318)
    assert stabilizer.gear_rack_length_mm == pytest.approx(560)
    assert stabilizer.capacity_increase_lb == 0
    assert stabilizer.quantity_per_drawer == 1
    assert stabilizer.shipping_mass_kg == pytest.approx(0.408233, rel=1e-5)
    assert stabilizer.mass_source_url
    assert stabilizer.source_url.startswith("https://d2.blum.com/")


def test_hafele_pull_adapter_pins_hole_spacing_and_fastener_thread():
    from detailgen.packs.cabinetry.catalogs import get_drawer_pull

    pull = get_drawer_pull("hafele_vogue_155_01_613@2026.1")

    assert pull.manufacturer == "Häfele"
    assert pull.sku == "155.01.613"
    assert pull.finish == "matte black"
    assert pull.hole_spacing_mm == pytest.approx(224)
    assert pull.thread == "M4"
    assert pull.overall_length_mm == pytest.approx(233)
    assert pull.cross_section_mm == pytest.approx((9, 9))
    assert pull.height_mm == pytest.approx(28.575)
    assert pull.quantity_per_drawer == 1
    assert pull.mounting_screw_product_id == \
        "hafele_handle_screw_m4x26_022_35_261@2026.1"
    assert pull.mounting_screw_length_mm == pytest.approx(26)
    assert pull.thread_diameter_mm == pytest.approx(4)
    assert pull.minimum_thread_engagement_factor == pytest.approx(1.5)
    assert pull.thread_engagement_reference_url.startswith("https://standards.nasa.gov/")
    assert pull.mounting_screw_quantity_per_pull == 2
    assert pull.mounting_screw_source_url.startswith("https://www.hafele.com/")
    assert pull.source_url.startswith("https://www.hafele.com/")


@pytest.mark.parametrize(
    ("getter_name", "bad_id", "suggestion"),
    [
        ("get_drawer_runner", "blum_movento_763_530s@2026.1", "763_5330s"),
        ("get_drawer_locking_device", "blum_t51_761_pair@2026.1", "t51_7601"),
        ("get_lateral_stabilizer", "blum_zs7m686m@2026.1", "zs7m686mu"),
        ("get_drawer_pull", "hafele_vogue_155_01_61@2026.1", "155_01_613"),
    ],
)
def test_unknown_drawer_product_fails_with_near_miss(
    getter_name, bad_id, suggestion
):
    from detailgen.packs.cabinetry import catalogs

    with pytest.raises(ProjectSchemaError, match=suggestion):
        getattr(catalogs, getter_name)(bad_id)
