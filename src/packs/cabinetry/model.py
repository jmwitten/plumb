"""Cabinet-domain semantic model derived from the compact author declaration."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ...core.units import IN
from .catalogs import (
    HingeProduct,
    WallAnchorProduct,
    get_hinge_product,
    get_wall_anchor_product,
    get_adhesive,
    get_assembly_fastener,
)
from .profiles import ConstructionProfile, get_profile
from .schema import CabinetrySection
from .evidence import EVIDENCE_LEVELS


@dataclass(frozen=True)
class Provenance:
    declared_at: str
    rule: str
    pack_version: str = "cabinetry.frameless@1.0.0"
    profile_id: str = ""
    catalog_id: str = ""
    archetype_id: str = ""


@dataclass(frozen=True)
class DerivedValue:
    name: str
    value: float
    unit: str
    inputs: tuple[str, ...]
    rule: str
    evidence: str = "derived"


@dataclass(frozen=True)
class PartModel:
    part_id: str
    role: str
    name: str
    component_type: str
    params: tuple[tuple[str, object], ...]
    at_mm: tuple[float, float, float]
    rotate: tuple[tuple[str, float], ...] = ()
    length_mm: float = 0.0
    width_mm: float = 0.0
    thickness_mm: float = 0.0
    surface_class: str = "concealed"
    edge_bands: tuple[str, ...] = ()

    def params_dict(self) -> dict:
        return dict(self.params)


@dataclass(frozen=True)
class MachiningFeature:
    feature_id: str
    kind: str
    part_id: str
    location_mm: tuple[float, ...]
    diameter_mm: float = 0.0
    depth_mm: float = 0.0
    pitch_mm: float = 0.0
    count: int = 1
    source: str = ""
    width_mm: float = 0.0
    length_mm: float = 0.0
    face: str = ""
    coordinate_system: str = "part_local_xy_from_cut_list_origin"


@dataclass(frozen=True)
class HardwareSystem:
    system_id: str
    kind: str
    product_id: str
    quantity: int
    related_parts: tuple[str, ...]
    evidence: str
    source_url: str = ""

    def __post_init__(self):
        if self.evidence not in EVIDENCE_LEVELS:
            raise ValueError(
                f"unknown evidence level {self.evidence!r}; known: "
                f"{sorted(EVIDENCE_LEVELS)}"
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


def _params(**kwargs) -> tuple[tuple[str, object], ...]:
    return tuple(kwargs.items())


def build_model(section: CabinetrySection, *, project_name: str) -> CabinetModel:
    """Expand the v1 declaration into real parts, machining, and interfaces."""

    profile = get_profile(section.profile_id)
    hinge = get_hinge_product(profile.hinge_product_id)
    wall_anchor = get_wall_anchor_product(
        "grk_low_profile_cabinet_8x3_1_8@2026.1"
    )
    confirmat = get_assembly_fastener(
        "hafele_confirmat_7x50_264_42_190@2026.1"
    )
    toe_attachment = get_assembly_fastener(
        "grk_low_profile_cabinet_8x1_1_4_114069@2026.1"
    )
    adhesive = get_adhesive("titebond_original_5064@2026.1")
    cabinet = section.cabinets[0]
    wall = section.site.wall
    x0 = wall.plane_origin_mm[0] + cabinet.from_left_datum_mm
    front_y = wall.plane_origin_mm[1] - cabinet.depth_mm
    base_z = section.site.floor.high_point_elevation_mm
    width = cabinet.width_mm
    height = cabinet.height_mm
    depth = cabinet.depth_mm
    toe = cabinet.toe_kick_height_mm
    t = profile.carcass_thickness_mm
    back_t = profile.back_thickness_mm
    body_h = height - toe
    inside_w = width - 2 * t
    back_plane = wall.plane_origin_mm[1] - profile.back_inset_mm
    carcass_depth = back_plane - front_y
    inside_depth = carcass_depth - back_t
    groove_w = profile.back_groove_width_mm
    groove_d = profile.back_groove_depth_mm
    back_blank_w = inside_w + 2 * groove_d
    back_blank_h = body_h - 2 * t + 2 * groove_d
    door_w = (
        width
        - 2 * profile.door_side_reveal_mm
        - profile.door_center_gap_mm
    ) / 2
    door_h = (
        body_h
        - profile.door_top_reveal_mm
        - profile.door_bottom_reveal_mm
    )
    shelf_w = inside_w - 2 * profile.shelf_side_clearance_mm
    shelf_depth = inside_depth - profile.shelf_front_setback_mm
    shelf_z = toe + t + (body_h - 2 * t) / 2
    anchor_h = profile.stretcher_depth_mm
    anchor_front_y = back_plane - back_t - t
    anchor_z = base_z + height - t - anchor_h

    parts: list[PartModel] = []
    source_map: dict[str, Provenance] = {}

    def add_panel(
        role: str,
        rule: str,
        *,
        length: float,
        panel_width: float,
        thickness: float,
        at: tuple[float, float, float],
        rotate: tuple[tuple[str, float], ...] = (),
        surface: str = "concealed",
        bands: tuple[str, ...] = (),
        grooves: tuple[dict[str, object], ...] = (),
    ) -> None:
        part_id = f"cabinetry.{cabinet.cabinet_id}.{role}"
        parts.append(PartModel(
            part_id=part_id,
            role=role,
            name=f"{cabinet.cabinet_id} {role.replace('_', ' ')}",
            component_type="plywood_panel",
            params=_params(
                length=length, width=panel_width, thickness=thickness,
                **({"grooves": grooves} if grooves else {}),
            ),
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

    # Carcass. PlywoodPanel is laid flat (X length, Y width, Z thickness);
    # rotations put panels upright while keeping installed orientation out of
    # the reusable base component.
    add_panel(
        "left_end", "carcass.left_end",
        length=body_h, panel_width=depth, thickness=t,
        at=(x0, front_y + depth, base_z + toe),
        rotate=(("Y", -90.0), ("Z", 180.0)),
        surface=("exposed_exterior" if cabinet.left_end == "exposed"
                 else "semi_exposed"), bands=("front",),
        grooves=({
            "x": t - groove_d,
            # This end is rotated 180° about Z, so its local rear edge is at
            # small Y (the right end below keeps rear at large local Y).
            "y": profile.back_inset_mm,
            "length": back_blank_h,
            "width": groove_w,
            "depth": groove_d,
            "face": "top",
            "feature": "captured_back",
            "source": "carcass.captured_back.groove.left_end",
        },),
    )
    add_panel(
        "right_end", "carcass.right_end",
        length=body_h, panel_width=depth, thickness=t,
        at=(x0 + width, front_y, base_z + toe), rotate=(("Y", -90.0),),
        surface=("exposed_exterior" if cabinet.right_end == "exposed"
                 else "semi_exposed"), bands=("front",),
        grooves=({
            "x": t - groove_d,
            "y": depth - profile.back_inset_mm - groove_w,
            "length": back_blank_h,
            "width": groove_w,
            "depth": groove_d,
            "face": "top",
            "feature": "captured_back",
            "source": "carcass.captured_back.groove.right_end",
        },),
    )
    add_panel(
        "bottom", "carcass.bottom",
        length=inside_w, panel_width=carcass_depth, thickness=t,
        at=(x0 + t, front_y, base_z + toe),
        surface="semi_exposed", bands=("front",),
        grooves=({
            "x": 0.0, "y": carcass_depth - groove_w,
            "length": inside_w, "width": groove_w, "depth": groove_d,
            "face": "top", "feature": "captured_back",
            "source": "carcass.captured_back.groove.bottom",
        },),
    )
    add_panel(
        "captured_back", "carcass.captured_back",
        length=back_blank_w, panel_width=back_blank_h, thickness=back_t,
        at=(x0 + t - groove_d, back_plane,
            base_z + toe + t - groove_d), rotate=(("X", 90.0),),
        surface="semi_exposed",
    )
    add_panel(
        "front_stretcher", "carcass.front_stretcher",
        length=inside_w, panel_width=profile.stretcher_depth_mm, thickness=t,
        at=(x0 + t, front_y, base_z + height - t), surface="concealed",
    )
    add_panel(
        "rear_stretcher", "carcass.rear_stretcher",
        length=inside_w, panel_width=profile.stretcher_depth_mm, thickness=t,
        at=(x0 + t, front_y + carcass_depth - profile.stretcher_depth_mm,
            base_z + height - t), surface="concealed",
        grooves=({
            "x": 0.0, "y": profile.stretcher_depth_mm - groove_w,
            "length": inside_w, "width": groove_w, "depth": groove_d,
            "face": "bottom", "feature": "captured_back",
            "source": "carcass.captured_back.groove.rear_stretcher",
        },),
    )
    add_panel(
        "anchor_strip", "installation.anchor_strip",
        length=inside_w, panel_width=anchor_h, thickness=t,
        at=(x0 + t, back_plane - back_t, anchor_z),
        rotate=(("X", 90.0),), surface="concealed",
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

    # Independent toe-kick base: front/rear rails plus two transverse sleepers.
    # Side sleepers butt between the full-width front/rear rails. Subtract both
    # rail thicknesses so the four corners are face contacts, not unintended
    # lapped volumes that the base interference sweep would correctly reject.
    base_depth = (
        depth
        - cabinet.toe_kick_setback_mm
        - 2 * profile.toe_base_member_thickness_mm
    )
    add_panel(
        "toe_front", "base.toe_front",
        length=width, panel_width=toe,
        thickness=profile.toe_base_member_thickness_mm,
        at=(x0, front_y + cabinet.toe_kick_setback_mm
            + profile.toe_base_member_thickness_mm, base_z),
        rotate=(("X", 90.0),), surface="exposed_exterior", bands=("top",),
    )
    add_panel(
        "toe_rear", "base.toe_rear",
        length=width, panel_width=toe,
        thickness=profile.toe_base_member_thickness_mm,
        at=(x0, front_y + depth, base_z), rotate=(("X", 90.0),),
        surface="concealed",
    )
    add_panel(
        "toe_left", "base.toe_left",
        length=base_depth, panel_width=toe,
        thickness=profile.toe_base_member_thickness_mm,
        at=(x0, front_y + cabinet.toe_kick_setback_mm
            + profile.toe_base_member_thickness_mm, base_z),
        rotate=(("X", 90.0), ("Z", 90.0)), surface="concealed",
    )
    add_panel(
        "toe_right", "base.toe_right",
        length=base_depth, panel_width=toe,
        thickness=profile.toe_base_member_thickness_mm,
        at=(x0 + width - profile.toe_base_member_thickness_mm,
            front_y + cabinet.toe_kick_setback_mm
            + profile.toe_base_member_thickness_mm, base_z),
        rotate=(("X", 90.0), ("Z", 90.0)), surface="concealed",
    )

    # Existing surveyed studs. Their actual 1.5 x 3.5 section is oriented with
    # the narrow face across the wall (X) and depth behind the finish plane (+Y).
    for stud in wall.studs:
        part_id = f"site.{wall.wall_id}.{stud.stud_id}"
        parts.append(PartModel(
            part_id=part_id,
            role=f"wall_stud_{stud.stud_id}",
            name=f"{wall.wall_id} {stud.stud_id}",
            component_type="lumber",
            params=_params(nominal="2x4", length=wall.height_mm),
            at_mm=(wall.plane_origin_mm[0] + stud.position_mm
                   - wall.stud_width_mm / 2,
                   wall.plane_origin_mm[1] + wall.finish_thickness_mm,
                   wall.plane_origin_mm[2]),
            rotate=(("Y", -90.0), ("Z", -90.0)),
            length_mm=wall.height_mm,
            width_mm=wall.stud_width_mm,
            thickness_mm=wall.stud_depth_mm,
            surface_class="existing_concealed",
        ))
        source_map[part_id] = Provenance(
            declared_at=f"site.wall.studs.{stud.stud_id}",
            rule="site.surveyed_stud",
            profile_id=profile.profile_id,
        )

    # Use every declared stud center inside the cabinet span; verification is a
    # separate evidence status, so draft geometry can still show an unverified
    # candidate without pretending it is field-confirmed.
    anchor_min_x = x0 + t + profile.anchor_edge_clearance_mm
    anchor_max_x = x0 + width - t - profile.anchor_edge_clearance_mm
    anchor_studs = tuple(
        stud for stud in wall.studs
        if anchor_min_x <= wall.plane_origin_mm[0] + stud.position_mm <= anchor_max_x
    )
    screw_length = wall_anchor.length_mm
    screw_z = anchor_z + anchor_h / 2
    for stud in anchor_studs:
        role = f"wall_anchor_{stud.stud_id}"
        part_id = f"cabinetry.{cabinet.cabinet_id}.{role}"
        parts.append(PartModel(
            part_id=part_id,
            role=role,
            name=f"{cabinet.cabinet_id} wall anchor at {stud.stud_id}",
            component_type="structural_screw",
            params=_params(diameter=wall_anchor.diameter_mm, length=screw_length),
            at_mm=(wall.plane_origin_mm[0] + stud.position_mm,
                   anchor_front_y, screw_z),
            rotate=(("X", 90.0),),
            length_mm=screw_length,
            width_mm=wall_anchor.diameter_mm,
            thickness_mm=wall_anchor.diameter_mm,
            surface_class="concealed",
        ))
        source_map[part_id] = Provenance(
            declared_at=f"site.wall.studs.{stud.stud_id}",
            rule="installation.wall_anchor",
            profile_id=profile.profile_id,
        )

    machining: list[MachiningFeature] = []
    for part in parts:
        for index, groove in enumerate(part.params_dict().get("grooves", ())):
            machining.append(MachiningFeature(
                feature_id=f"{part.part_id}.captured_back_groove_{index + 1}",
                kind="captured_back_groove",
                part_id=part.part_id,
                location_mm=(float(groove["x"]), float(groove["y"])),
                depth_mm=float(groove["depth"]),
                width_mm=float(groove["width"]),
                length_mm=float(groove["length"]),
                face=str(groove["face"]),
                source=str(groove["source"]),
            ))
    overlay = t - profile.door_side_reveal_mm
    cup_from_edge = overlay + 6.5  # H002 table: cup center = overlay + 6.5 mm.
    hinge_z_local = (profile.hinge_edge_offset_mm,
                     door_h - profile.hinge_edge_offset_mm)
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
    pin_count = max(1, int(math.floor(pin_available / profile.shelf_pin_pitch_mm)) + 1)
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

    # One canonical step-drill schedule for the 26 Confirmat connectors:
    # 18 in the two carcass ends and 8 in the independent toe frame. These are
    # aggregate rows with a start coordinate, pitch, and count, not prose-only
    # quantities that a shop must re-invent.
    side_rows = (
        ("bottom", 3, 50.0, (carcass_depth - 100.0) / 2),
        ("front_stretcher", 2, 25.0, 50.0),
        ("rear_stretcher", 2, carcass_depth - profile.stretcher_depth_mm + 25.0,
         50.0),
        ("anchor_strip", 2, carcass_depth - back_t - t / 2, 50.0),
    )
    for side_role in ("left_end", "right_end"):
        side_id = f"cabinetry.{cabinet.cabinet_id}.{side_role}"
        for joint, count, y_start, pitch in side_rows:
            machining.append(MachiningFeature(
                feature_id=f"{side_id}.confirmat_{joint}",
                kind="confirmat_step_drill",
                part_id=side_id,
                location_mm=(t / 2 if joint == "bottom" else body_h - t / 2,
                             y_start),
                diameter_mm=confirmat.blind_pilot_diameter_mm,
                depth_mm=confirmat.length_mm - t,
                pitch_mm=pitch,
                count=count,
                source=confirmat.product_id,
                width_mm=confirmat.through_shank_diameter_mm,
                length_mm=confirmat.countersink_diameter_mm,
                face="outside",
            ))
    for role in ("toe_front", "toe_rear"):
        part_id = f"cabinetry.{cabinet.cabinet_id}.{role}"
        machining.append(MachiningFeature(
            feature_id=f"{part_id}.confirmat_sleepers",
            kind="confirmat_step_drill",
            part_id=part_id,
            location_mm=(t / 2, toe * 0.3),
            diameter_mm=confirmat.blind_pilot_diameter_mm,
            depth_mm=confirmat.length_mm - t,
            pitch_mm=toe * 0.4,
            count=4,
            source=confirmat.product_id,
            width_mm=confirmat.through_shank_diameter_mm,
            length_mm=confirmat.countersink_diameter_mm,
            face="outside",
        ))

    hardware = (
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
        HardwareSystem(
            system_id=f"cabinetry.{cabinet.cabinet_id}.wall_anchors",
            kind="wall_anchor_system",
            product_id=wall_anchor.product_id,
            quantity=len(anchor_studs),
            related_parts=tuple(
                f"cabinetry.{cabinet.cabinet_id}.wall_anchor_{stud.stud_id}"
                for stud in anchor_studs
            ),
            evidence="calculated",
            source_url=wall_anchor.source_url,
        ),
        HardwareSystem(
            system_id=f"cabinetry.{cabinet.cabinet_id}.carcass_confirmats",
            kind="carcass_confirmat_system", product_id=confirmat.product_id,
            quantity=26,
            related_parts=tuple(
                f"cabinetry.{cabinet.cabinet_id}.{role}" for role in (
                    "left_end", "right_end", "bottom", "front_stretcher",
                    "rear_stretcher", "anchor_strip", "toe_front", "toe_rear",
                    "toe_left", "toe_right",
                )
            ),
            evidence="manufacturer_rated",
            source_url=confirmat.source_url,
        ),
        HardwareSystem(
            system_id=f"cabinetry.{cabinet.cabinet_id}.toe_attachment",
            kind="toe_base_attachment_system",
            product_id=toe_attachment.product_id,
            quantity=6,
            related_parts=(
                f"cabinetry.{cabinet.cabinet_id}.bottom",
                f"cabinetry.{cabinet.cabinet_id}.toe_front",
                f"cabinetry.{cabinet.cabinet_id}.toe_rear",
            ),
            evidence="manufacturer_rated",
            source_url=toe_attachment.source_url,
        ),
        HardwareSystem(
            system_id=f"cabinetry.{cabinet.cabinet_id}.wood_glue",
            kind="wood_adhesive", product_id=adhesive.product_id,
            quantity=1,
            related_parts=tuple(
                f"cabinetry.{cabinet.cabinet_id}.{role}" for role in (
                    "left_end", "right_end", "bottom", "front_stretcher",
                    "rear_stretcher", "captured_back",
                )
            ),
            evidence="manufacturer_rated",
            source_url=adhesive.source_url,
        ),
    )
    derived = (
        DerivedValue("inside_width", inside_w, "mm",
                     ("cabinet_width", "carcass_thickness"),
                     "carcass.clear_width"),
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
        wall_anchor=wall_anchor,
        section=section,
        parts=tuple(parts),
        machining=tuple(machining),
        hardware=hardware,
        derived=derived,
        source_map=source_map,
        anchor_stud_ids=tuple(stud.stud_id for stud in anchor_studs),
    )
