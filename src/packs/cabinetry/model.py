"""Door-base product model composed over the reusable cabinet shell."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .catalogs import HingeProduct, WallAnchorProduct, get_hinge_product
from .profiles import ConstructionProfile
from .schema import CabinetrySection
from .shell import (
    DerivedValue,
    HardwareSystem,
    MachiningFeature,
    PartModel,
    Provenance,
    build_base_shell,
    params,
)


@dataclass(frozen=True)
class CabinetModel:
    project_name: str
    mode: str
    profile: ConstructionProfile
    hinge: HingeProduct
    wall_anchor: WallAnchorProduct
    section: CabinetrySection
    parts: tuple[PartModel, ...]
    machining: tuple[MachiningFeature, ...]
    hardware: tuple[HardwareSystem, ...]
    derived: tuple[DerivedValue, ...]
    source_map: dict[str, Provenance] = field(compare=True)
    anchor_stud_ids: tuple[str, ...] = ()

    def part(self, role: str) -> PartModel:
        matches = [part for part in self.parts if part.role == role]
        if len(matches) != 1:
            raise KeyError(
                f"expected one cabinet part with role {role!r}, found "
                f"{[part.role for part in matches]}"
            )
        return matches[0]

    def derived_value(self, name: str) -> DerivedValue:
        try:
            return next(value for value in self.derived if value.name == name)
        except StopIteration:
            raise KeyError(
                f"unknown derived cabinet value {name!r}; known: "
                f"{[value.name for value in self.derived]}"
            ) from None

    def catalog_manifest(self) -> dict[str, str]:
        return {
            "hinge": self.hinge.product_id,
            "wall_anchor": self.wall_anchor.product_id,
        }

    def catalog_source_manifest(self) -> dict[str, str]:
        # Preserve the v1 door-cabinet manifest byte-for-byte. Drawer products
        # opt into source entries because their multi-product adapter contract
        # requires the URLs at manifest level.
        return {}

    def sizing_policy_manifest(self) -> tuple[str, ...]:
        return ()


def build_model(section: CabinetrySection, *, project_name: str) -> CabinetModel:
    """Compose the existing two-door product over the common base shell."""

    cabinet = section.cabinets[0]
    shell = build_base_shell(section, cabinet)
    profile = shell.profile
    hinge = get_hinge_product(profile.hinge_product_id)
    x0 = shell.x0_mm
    front_y = shell.front_y_mm
    base_z = shell.base_z_mm
    width = cabinet.width_mm
    depth = cabinet.depth_mm
    toe = cabinet.toe_kick_height_mm
    t = profile.carcass_thickness_mm
    body_h = shell.body_height_mm
    inside_w = shell.inside_width_mm
    inside_depth = shell.inside_depth_mm
    door_w = (
        width - 2 * profile.door_side_reveal_mm - profile.door_center_gap_mm
    ) / 2
    door_h = (
        body_h - profile.door_top_reveal_mm - profile.door_bottom_reveal_mm
    )
    shelf_w = inside_w - 2 * profile.shelf_side_clearance_mm
    shelf_depth = inside_depth - profile.shelf_front_setback_mm
    shelf_z = toe + t + (body_h - 2 * t) / 2

    product_parts: list[PartModel] = []
    source_map = dict(shell.source_map)

    def add_panel(role: str, rule: str, *, length: float, panel_width: float,
                  thickness: float, at: tuple[float, float, float],
                  rotate: tuple[tuple[str, float], ...] = (),
                  surface: str = "concealed",
                  bands: tuple[str, ...] = ()) -> None:
        part_id = f"cabinetry.{cabinet.cabinet_id}.{role}"
        product_parts.append(PartModel(
            part_id=part_id,
            role=role,
            name=f"{cabinet.cabinet_id} {role.replace('_', ' ')}",
            component_type="plywood_panel",
            params=params(length=length, width=panel_width, thickness=thickness),
            at_mm=at,
            rotate=rotate,
            length_mm=length,
            width_mm=panel_width,
            thickness_mm=thickness,
            surface_class=surface,
            edge_bands=bands,
        ))
        source_map[part_id] = Provenance(
            declared_at=cabinet.cabinet_id,
            rule=rule,
            profile_id=profile.profile_id,
            archetype_id=cabinet.source_archetype,
        )

    add_panel(
        "adjustable_shelf", "interior.adjustable_shelf",
        length=shelf_w, panel_width=shelf_depth, thickness=t,
        at=(x0 + t + profile.shelf_side_clearance_mm, front_y,
            base_z + shelf_z),
        surface="semi_exposed", bands=("front",),
    )
    add_panel(
        "door_left", "fronts.paired_overlay.left",
        length=door_w, panel_width=door_h, thickness=profile.door_thickness_mm,
        at=(x0 + profile.door_side_reveal_mm, front_y,
            base_z + toe + profile.door_bottom_reveal_mm),
        rotate=(("X", 90.0),), surface="exposed_exterior",
        bands=("left", "right", "top", "bottom"),
    )
    add_panel(
        "door_right", "fronts.paired_overlay.right",
        length=door_w, panel_width=door_h, thickness=profile.door_thickness_mm,
        at=(x0 + profile.door_side_reveal_mm + door_w
            + profile.door_center_gap_mm, front_y,
            base_z + toe + profile.door_bottom_reveal_mm),
        rotate=(("X", 90.0),), surface="exposed_exterior",
        bands=("left", "right", "top", "bottom"),
    )

    machining = list(shell.groove_machining)
    overlay = t - profile.door_side_reveal_mm
    cup_from_edge = overlay + 6.5
    hinge_z_local = (
        profile.hinge_edge_offset_mm,
        door_h - profile.hinge_edge_offset_mm,
    )
    for door_role, hinge_side in (("door_left", "left"),
                                  ("door_right", "right")):
        door_id = f"cabinetry.{cabinet.cabinet_id}.{door_role}"
        side_role = "left_end" if hinge_side == "left" else "right_end"
        side_id = f"cabinetry.{cabinet.cabinet_id}.{side_role}"
        for position, z_local in zip(("bottom", "top"), hinge_z_local):
            edge_x = cup_from_edge if hinge_side == "left" else door_w - cup_from_edge
            machining.append(MachiningFeature(
                feature_id=f"{door_id}.hinge_{position}_cup",
                kind="hinge_cup", part_id=door_id,
                location_mm=(edge_x, z_local),
                diameter_mm=hinge.cup_diameter_mm,
                depth_mm=hinge.cup_depth_mm,
                source=hinge.product_id,
            ))
            machining.append(MachiningFeature(
                feature_id=f"{side_id}.hinge_{position}_plate",
                kind="mounting_plate", part_id=side_id,
                location_mm=(hinge.plate_line_mm, z_local),
                pitch_mm=hinge.plate_hole_spacing_mm,
                count=2,
                source=hinge.product_id,
            ))

    pin_start = 64.0
    pin_available = max(0.0, body_h - 2 * t - 2 * pin_start)
    pin_count = max(
        1, int(math.floor(pin_available / profile.shelf_pin_pitch_mm)) + 1
    )
    for side_role in ("left_end", "right_end"):
        side_id = f"cabinetry.{cabinet.cabinet_id}.{side_role}"
        for row, depth_line in (("front", profile.shelf_pin_front_line_mm),
                                ("rear", depth - profile.shelf_pin_rear_line_mm)):
            machining.append(MachiningFeature(
                feature_id=f"{side_id}.shelf_pin_{row}_row",
                kind="shelf_pin_row", part_id=side_id,
                location_mm=(depth_line, pin_start),
                diameter_mm=profile.shelf_pin_diameter_mm,
                depth_mm=12.0,
                pitch_mm=profile.shelf_pin_pitch_mm,
                count=pin_count,
                source="frameless_plywood_shop_v1.system32",
            ))
    machining.extend(shell.joinery_machining)

    product_hardware = (
        HardwareSystem(
            system_id=f"cabinetry.{cabinet.cabinet_id}.hinges",
            kind="concealed_hinge_system", product_id=hinge.product_id,
            quantity=4,
            related_parts=(
                f"cabinetry.{cabinet.cabinet_id}.door_left",
                f"cabinetry.{cabinet.cabinet_id}.door_right",
                f"cabinetry.{cabinet.cabinet_id}.left_end",
                f"cabinetry.{cabinet.cabinet_id}.right_end",
            ),
            evidence="manufacturer_rated",
            source_url=hinge.source_url,
        ),
        HardwareSystem(
            system_id=f"cabinetry.{cabinet.cabinet_id}.shelf_supports",
            kind="adjustable_shelf_support_system",
            product_id="system32_5mm_shelf_support",
            quantity=4,
            related_parts=(f"cabinetry.{cabinet.cabinet_id}.adjustable_shelf",),
            evidence="derived",
        ),
    )
    derived = shell.derived + (
        DerivedValue("door_width", door_w, "mm",
                     ("cabinet_width", "side_reveals", "center_gap"),
                     "fronts.paired_overlay.width"),
        DerivedValue("door_height", door_h, "mm",
                     ("cabinet_height", "toe_kick_height", "top_reveal",
                      "bottom_reveal"),
                     "fronts.paired_overlay.height"),
        DerivedValue("shelf_width", shelf_w, "mm",
                     ("inside_width", "shelf_side_clearance"),
                     "interior.adjustable_shelf.width"),
        DerivedValue("hinge_overlay", overlay, "mm",
                     ("carcass_thickness", "door_side_reveal"),
                     "hardware.blum.overlay"),
        DerivedValue("hinge_cup_edge_distance", cup_from_edge, "mm",
                     ("hinge_overlay", "blum_h002_table"),
                     "hardware.blum.cup_center"),
    )
    return CabinetModel(
        project_name=project_name,
        mode=section.mode,
        profile=profile,
        hinge=hinge,
        wall_anchor=shell.wall_anchor,
        section=section,
        parts=shell.carcass_parts + tuple(product_parts) + shell.support_parts,
        machining=tuple(machining),
        hardware=product_hardware + shell.hardware,
        derived=derived,
        source_map=source_map,
        anchor_stud_ids=shell.anchor_stud_ids,
    )
