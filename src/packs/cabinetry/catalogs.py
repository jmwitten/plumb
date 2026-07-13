"""Pinned manufacturer adapters used by the frameless cabinetry profile."""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from ..project import ProjectSchemaError


@dataclass(frozen=True)
class HingeProduct:
    product_id: str
    manufacturer: str
    product: str
    sku: str
    cup_diameter_mm: float
    cup_depth_mm: float
    plate_line_mm: float
    plate_hole_spacing_mm: float
    door_thickness_range_mm: tuple[float, float]
    overlay_range_mm: tuple[float, float]
    opening_angle_deg: float
    max_two_hinge_door_height_mm: float
    max_two_hinge_door_weight_kg: float
    max_chart_door_width_mm: float
    side_adjustment_mm: tuple[float, float]
    height_adjustment_mm: tuple[float, float]
    depth_adjustment_mm: tuple[float, float]
    source_url: str
    quantity_source_url: str
    source_date: str


@dataclass(frozen=True)
class WallAnchorProduct:
    product_id: str
    manufacturer: str
    product: str
    sku: str
    gauge: str
    diameter_mm: float
    length_mm: float
    drive: str
    head: str
    source_url: str
    source_date: str
    pilot_diameter_mm: float = 0.0
    evaluation_report_url: str = ""


@dataclass(frozen=True)
class AssemblyFastenerProduct:
    product_id: str
    manufacturer: str
    product: str
    sku: str
    diameter_mm: float
    length_mm: float
    blind_pilot_diameter_mm: float
    through_shank_diameter_mm: float
    countersink_diameter_mm: float
    drive: str
    source_url: str
    source_date: str


@dataclass(frozen=True)
class AdhesiveProduct:
    product_id: str
    manufacturer: str
    product: str
    sku: str
    minimum_spread_mil: float
    open_time_minutes: tuple[float, float]
    total_assembly_time_minutes: tuple[float, float]
    minimum_application_temperature_c: float
    source_url: str
    source_date: str


@dataclass(frozen=True)
class DrawerRunnerProduct:
    product_id: str
    manufacturer: str
    product: str
    sku: str
    nominal_length_mm: float
    physical_length_mm: float
    minimum_inside_depth_mm: float
    maximum_side_thickness_mm: float
    inside_width_deduction_mm: float
    bottom_recess_mm: float
    bottom_clearance_mm: float
    minimum_rear_notch_mm: float
    hook_bore_mm: tuple[float, float]
    minimum_top_clearance_mm: float
    opening_height_deduction_mm: float
    front_setback_mm: float
    mounting_line_mm: float
    required_rear_fixing_stations_mm: tuple[float, ...]
    static_rating_lb: float
    dynamic_rating_lb: float
    motion: str
    source_url: str
    source_date: str


@dataclass(frozen=True)
class DrawerLockingDeviceProduct:
    product_id: str
    manufacturer: str
    product: str
    left_sku: str
    right_sku: str
    quantity_per_drawer: int
    minimum_inside_drawer_width_mm: float
    side_adjustment_mm: tuple[float, float]
    source_url: str
    source_date: str


@dataclass(frozen=True)
class LateralStabilizerProduct:
    product_id: str
    manufacturer: str
    product: str
    sku: str
    recommended_from_opening_mm: float
    maximum_opening_mm: float
    linkage_rod_length_mm: float
    capacity_increase_lb: float
    quantity_per_drawer: int
    source_url: str
    source_date: str


@dataclass(frozen=True)
class DrawerPullProduct:
    product_id: str
    manufacturer: str
    product: str
    sku: str
    finish: str
    hole_spacing_mm: float
    thread: str
    quantity_per_drawer: int
    source_url: str
    source_date: str


BLUM_H002 = HingeProduct(
    product_id="blum_clip_top_blumotion_110_h002@2025.1",
    manufacturer="Blum",
    product="CLIP top BLUMOTION 110° screw-on hinge kit H002",
    sku="H002",
    cup_diameter_mm=35.0,
    cup_depth_mm=13.0,
    plate_line_mm=37.0,
    plate_hole_spacing_mm=32.0,
    door_thickness_range_mm=(16.0, 26.0),
    overlay_range_mm=(14.0, 18.0),
    opening_angle_deg=110.0,
    max_two_hinge_door_height_mm=1000.0,
    max_two_hinge_door_weight_kg=6.0,
    max_chart_door_width_mm=600.0,
    side_adjustment_mm=(-2.0, 2.0),
    height_adjustment_mm=(-2.0, 2.0),
    depth_adjustment_mm=(-2.0, 3.0),
    source_url=(
        "https://d2.blum.com/services/BEC003/"
        "cme198264_ma_dok_bus_%24sen-us_%24aof_%24v1.pdf"
    ),
    quantity_source_url="https://publications.blum.com/2024/catalogue/en/718/",
    source_date="2025",
)

_HINGES = {BLUM_H002.product_id: BLUM_H002}

GRK_CABINET_8X3_1_8 = WallAnchorProduct(
    product_id="grk_low_profile_cabinet_8x3_1_8@2026.1",
    manufacturer="GRK Fasteners",
    product="Low Profile Cabinet Screw #8 x 3-1/8 in",
    sku="110083",
    gauge="#8",
    diameter_mm=4.0,
    length_mm=3.125 * 25.4,
    drive="T-15 star",
    head="washer-style low profile",
    source_url=(
        "https://www.grkfasteners.com/grk-products/finish/"
        "low-profile-cabinet-screw"
    ),
    source_date="2026",
)

GRK_RSS_5_16X4 = WallAnchorProduct(
    product_id="grk_rss_5_16x4@2026.1",
    manufacturer="GRK Fasteners",
    product="RSS Rugged Structural Screw 5/16 x 4 in",
    sku="RSS 5/16 x 4",
    gauge="5/16 in",
    diameter_mm=5 / 16 * 25.4,
    length_mm=4 * 25.4,
    drive="T-30 star",
    head="integral washer head",
    source_url=(
        "https://www.grkfasteners.com/grk-products/structural-framing-screws/"
        "rss-rugged-structural-screw"
    ),
    source_date="2026",
    pilot_diameter_mm=3 / 16 * 25.4,
    evaluation_report_url=(
        "https://www.grkfasteners.com/getmedia/"
        "5f4f72a8-8d1f-479b-8ae0-5fc043e2943d/ESR-2442.pdf?ext=.pdf"
    ),
)

_WALL_ANCHORS = {
    item.product_id: item
    for item in (GRK_CABINET_8X3_1_8, GRK_RSS_5_16X4)
}

HAFELE_CONFIRMAT_7X50 = AssemblyFastenerProduct(
    product_id="hafele_confirmat_7x50_264_42_190@2026.1",
    manufacturer="Häfele",
    product="Confirmat connector screw 7 x 50 mm",
    sku="264.42.190",
    diameter_mm=7.0,
    length_mm=50.0,
    blind_pilot_diameter_mm=5.0,
    through_shank_diameter_mm=7.0,
    countersink_diameter_mm=10.0,
    drive="PZ3",
    source_url=(
        "https://www.hafele.com/INTERSHOP/static/WFS/Haefele-COM-Site/"
        "-Haefele-COM/en_US/opentext/assets/com/Hafele_Serbia_catalog.pdf"
    ),
    source_date="2026",
)

GRK_CABINET_8X1_1_4 = AssemblyFastenerProduct(
    product_id="grk_low_profile_cabinet_8x1_1_4_114069@2026.1",
    manufacturer="GRK Fasteners",
    product="Low Profile Cabinet Screw #8 x 1-1/4 in",
    sku="114069",
    diameter_mm=4.0,
    length_mm=1.25 * 25.4,
    blind_pilot_diameter_mm=0.0,
    through_shank_diameter_mm=0.0,
    countersink_diameter_mm=0.0,
    drive="T-15 star",
    source_url=(
        "https://www.grkfasteners.com/grk-products/finish/"
        "low-profile-cabinet-screw"
    ),
    source_date="2026",
)

TITEBOND_ORIGINAL = AdhesiveProduct(
    product_id="titebond_original_5064@2026.1",
    manufacturer="Franklin International",
    product="Titebond Original Wood Glue",
    sku="5064",
    minimum_spread_mil=6.0,
    open_time_minutes=(4.0, 6.0),
    total_assembly_time_minutes=(10.0, 15.0),
    minimum_application_temperature_c=10.0,
    source_url="https://www.titebond.com/print/product/d4d28015-603f-4dfc-a7d9-f684acc71207",
    source_date="2026",
)

_ASSEMBLY_FASTENERS = {
    item.product_id: item for item in (HAFELE_CONFIRMAT_7X50, GRK_CABINET_8X1_1_4)
}
_ADHESIVES = {TITEBOND_ORIGINAL.product_id: TITEBOND_ORIGINAL}

_MOVENTO_SOURCE = (
    "https://d2.blum.com/services/BEC003/"
    "movento_ep_dok_bus_%24sen-us_%24aof_%24v7.pdf"
)

BLUM_MOVENTO_763_5330S = DrawerRunnerProduct(
    product_id="blum_movento_763_5330s@2026.1",
    manufacturer="Blum",
    product="MOVENTO 763 standard-duty full-extension runner with BLUMOTION",
    sku="763.5330S",
    nominal_length_mm=533.0,
    physical_length_mm=544.0,
    minimum_inside_depth_mm=553.0,
    maximum_side_thickness_mm=16.0,
    inside_width_deduction_mm=42.0,
    bottom_recess_mm=13.0,
    bottom_clearance_mm=16.0,
    minimum_rear_notch_mm=50.0,
    hook_bore_mm=(6.0, 10.0),
    minimum_top_clearance_mm=7.0,
    opening_height_deduction_mm=23.0,
    front_setback_mm=3.0,
    mounting_line_mm=37.0,
    required_rear_fixing_stations_mm=(261.0, 357.0),
    static_rating_lb=125.0,
    dynamic_rating_lb=110.0,
    motion="blumotion_soft_close",
    source_url=_MOVENTO_SOURCE,
    source_date="2026-04-14",
)

BLUM_T51_7601_PAIR = DrawerLockingDeviceProduct(
    product_id="blum_t51_7601_pair@2026.1",
    manufacturer="Blum",
    product="MOVENTO standard locking-device handed pair",
    left_sku="T51.7601 L",
    right_sku="T51.7601 R",
    quantity_per_drawer=2,
    minimum_inside_drawer_width_mm=170.0,
    side_adjustment_mm=(-1.5, 1.5),
    source_url=_MOVENTO_SOURCE,
    source_date="2026-04-14",
)

BLUM_ZS7M686MU = LateralStabilizerProduct(
    product_id="blum_zs7m686mu@2026.1",
    manufacturer="Blum",
    product="MOVENTO 763/769 lateral stabilizer set",
    sku="ZS7M686MU",
    recommended_from_opening_mm=610.0,
    maximum_opening_mm=1369.0,
    linkage_rod_length_mm=1051.0,
    capacity_increase_lb=0.0,
    quantity_per_drawer=1,
    source_url=(
        "https://d2.blum.com/services/BEC003/"
        "moventolatstab_ma_dok_bus_%24sen-us_%24aof_%24v3.pdf"
    ),
    source_date="2024-02-06",
)

HAFELE_VOGUE_224_BLACK = DrawerPullProduct(
    product_id="hafele_vogue_155_01_613@2026.1",
    manufacturer="Häfele",
    product="Vogue zinc pull, 224 mm center-to-center",
    sku="155.01.613",
    finish="matte black",
    hole_spacing_mm=224.0,
    thread="M4",
    quantity_per_drawer=1,
    source_url="https://www.hafele.com/us/en/product/handle-zinc/15501623/",
    source_date="2025-10-22",
)

_DRAWER_RUNNERS = {BLUM_MOVENTO_763_5330S.product_id: BLUM_MOVENTO_763_5330S}
_DRAWER_LOCKING_DEVICES = {
    BLUM_T51_7601_PAIR.product_id: BLUM_T51_7601_PAIR
}
_LATERAL_STABILIZERS = {BLUM_ZS7M686MU.product_id: BLUM_ZS7M686MU}
_DRAWER_PULLS = {HAFELE_VOGUE_224_BLACK.product_id: HAFELE_VOGUE_224_BLACK}


def _drawer_product(products: dict, product_id: str, kind: str):
    try:
        return products[product_id]
    except KeyError:
        suggestions = difflib.get_close_matches(product_id, sorted(products), n=1)
        hint = f"; did you mean {suggestions[0]!r}?" if suggestions else ""
        raise ProjectSchemaError(
            f"unknown {kind} {product_id!r}; known products: "
            f"{sorted(products)}{hint}"
        ) from None


def get_hinge_product(product_id: str) -> HingeProduct:
    try:
        return _HINGES[product_id]
    except KeyError:
        raise ProjectSchemaError(
            f"unknown hinge product {product_id!r}; known hinge products: "
            f"{sorted(_HINGES)}"
        ) from None


def get_wall_anchor_product(product_id: str) -> WallAnchorProduct:
    try:
        return _WALL_ANCHORS[product_id]
    except KeyError:
        raise ProjectSchemaError(
            f"unknown wall anchor product {product_id!r}; known wall anchors: "
            f"{sorted(_WALL_ANCHORS)}"
        ) from None


def get_assembly_fastener(product_id: str) -> AssemblyFastenerProduct:
    try:
        return _ASSEMBLY_FASTENERS[product_id]
    except KeyError:
        raise ProjectSchemaError(
            f"unknown assembly fastener {product_id!r}; known products: "
            f"{sorted(_ASSEMBLY_FASTENERS)}"
        ) from None


def get_adhesive(product_id: str) -> AdhesiveProduct:
    try:
        return _ADHESIVES[product_id]
    except KeyError:
        raise ProjectSchemaError(
            f"unknown adhesive {product_id!r}; known products: "
            f"{sorted(_ADHESIVES)}"
        ) from None


def get_drawer_runner(product_id: str) -> DrawerRunnerProduct:
    return _drawer_product(_DRAWER_RUNNERS, product_id, "drawer runner")


def get_drawer_locking_device(product_id: str) -> DrawerLockingDeviceProduct:
    return _drawer_product(
        _DRAWER_LOCKING_DEVICES, product_id, "drawer locking device"
    )


def get_lateral_stabilizer(product_id: str) -> LateralStabilizerProduct:
    return _drawer_product(
        _LATERAL_STABILIZERS, product_id, "lateral stabilizer"
    )


def get_drawer_pull(product_id: str) -> DrawerPullProduct:
    return _drawer_product(_DRAWER_PULLS, product_id, "drawer pull")
