"""Versioned construction profiles: reusable cabinet-making decisions."""

from __future__ import annotations

from dataclasses import dataclass

from ...core.units import IN
from ..project import ProjectSchemaError


@dataclass(frozen=True)
class ConstructionProfile:
    profile_id: str
    construction: str
    carcass_thickness_mm: float
    back_thickness_mm: float
    door_thickness_mm: float
    default_height_mm: float
    default_depth_mm: float
    toe_kick_height_mm: float
    toe_kick_setback_mm: float
    toe_base_member_thickness_mm: float
    stretcher_depth_mm: float
    back_inset_mm: float
    back_groove_width_mm: float
    back_groove_depth_mm: float
    shelf_side_clearance_mm: float
    shelf_front_setback_mm: float
    door_side_reveal_mm: float
    door_top_reveal_mm: float
    door_bottom_reveal_mm: float
    door_center_gap_mm: float
    hinge_edge_offset_mm: float
    shelf_pin_pitch_mm: float
    shelf_pin_diameter_mm: float
    shelf_pin_front_line_mm: float
    shelf_pin_rear_line_mm: float
    anchor_edge_clearance_mm: float
    base_assembly: str
    joinery: str
    edge_treatment: str
    hinge_product_id: str
    performance_reference: str
    assembly_location: str
    delivery_state: str
    panel_modulus_elasticity_mpa: float
    panel_density_kg_m3: float


FRAMELESS_PLYWOOD_SHOP_V1 = ConstructionProfile(
    profile_id="frameless_plywood_shop_v1@1.0.0",
    construction="frameless",
    carcass_thickness_mm=0.75 * IN,
    back_thickness_mm=0.25 * IN,
    door_thickness_mm=0.75 * IN,
    default_height_mm=34.5 * IN,
    default_depth_mm=23.25 * IN,
    toe_kick_height_mm=4.0 * IN,
    toe_kick_setback_mm=3.0 * IN,
    toe_base_member_thickness_mm=0.75 * IN,
    stretcher_depth_mm=4.0 * IN,
    back_inset_mm=0.375 * IN,
    back_groove_width_mm=0.25 * IN + 0.5,
    back_groove_depth_mm=0.375 * IN,
    shelf_side_clearance_mm=1.5,
    shelf_front_setback_mm=1.0 * IN,
    door_side_reveal_mm=1.5,
    door_top_reveal_mm=1.5,
    door_bottom_reveal_mm=1.5,
    door_center_gap_mm=2.0,
    hinge_edge_offset_mm=3.5 * IN,
    shelf_pin_pitch_mm=32.0,
    shelf_pin_diameter_mm=5.0,
    shelf_pin_front_line_mm=37.0,
    shelf_pin_rear_line_mm=37.0,
    anchor_edge_clearance_mm=1.0 * IN,
    base_assembly="independent_toe_kick",
    joinery="glue_and_cabinet_screws",
    edge_treatment="applied_edge_band",
    hinge_product_id="blum_clip_top_blumotion_110_h002@2025.1",
    performance_reference="ANSI_KCMA_A161_1_2022",
    assembly_location="shop",
    delivery_state="carcass_assembled_doors_detached",
    # Declared design properties for the initial generic plywood profile. The
    # evidence report labels these assumptions; a real selected panel may
    # override them in a future product catalog rather than inheriting silently.
    panel_modulus_elasticity_mpa=6895.0,
    panel_density_kg_m3=680.0,
)

_PROFILES = {FRAMELESS_PLYWOOD_SHOP_V1.profile_id: FRAMELESS_PLYWOOD_SHOP_V1}


def get_profile(profile_id: str) -> ConstructionProfile:
    try:
        return _PROFILES[profile_id]
    except KeyError:
        raise ProjectSchemaError(
            f"unknown cabinetry profile {profile_id!r}; known profiles: "
            f"{sorted(_PROFILES)}"
        ) from None
