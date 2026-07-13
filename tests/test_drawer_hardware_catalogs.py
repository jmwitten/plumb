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
    assert runner.minimum_top_clearance_mm == pytest.approx(7)
    assert runner.opening_height_deduction_mm == pytest.approx(23)
    assert runner.front_setback_mm == pytest.approx(3)
    assert runner.mounting_line_mm == pytest.approx(37)
    assert runner.required_rear_fixing_stations_mm == pytest.approx((261, 357))
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
    assert locking.source_url.startswith("https://d2.blum.com/")


def test_lateral_stabilizer_is_required_by_width_but_adds_no_capacity():
    from detailgen.packs.cabinetry.catalogs import get_lateral_stabilizer

    stabilizer = get_lateral_stabilizer("blum_zs7m686mu@2026.1")

    assert stabilizer.sku == "ZS7M686MU"
    assert stabilizer.recommended_from_opening_mm == pytest.approx(610)
    assert stabilizer.maximum_opening_mm == pytest.approx(1369)
    assert stabilizer.linkage_rod_length_mm == pytest.approx(1051)
    assert stabilizer.capacity_increase_lb == 0
    assert stabilizer.quantity_per_drawer == 1
    assert stabilizer.source_url.startswith("https://d2.blum.com/")


def test_hafele_pull_adapter_pins_hole_spacing_and_fastener_thread():
    from detailgen.packs.cabinetry.catalogs import get_drawer_pull

    pull = get_drawer_pull("hafele_vogue_155_01_613@2026.1")

    assert pull.manufacturer == "Häfele"
    assert pull.sku == "155.01.613"
    assert pull.finish == "matte black"
    assert pull.hole_spacing_mm == pytest.approx(224)
    assert pull.thread == "M4"
    assert pull.quantity_per_drawer == 1
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
