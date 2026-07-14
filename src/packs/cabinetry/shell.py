"""Common floor-supported frameless base-cabinet shell construction."""

from __future__ import annotations

from dataclasses import dataclass, field

from .catalogs import (
    WallAnchorProduct,
    get_adhesive,
    get_assembly_fastener,
    get_wall_anchor_product,
)
from .evidence import EVIDENCE_LEVELS
from .profiles import ConstructionProfile, get_profile
from .schema import BaseCabinetDecl, CabinetrySection, DrawerBaseDecl


@dataclass(frozen=True)
class Provenance:
    declared_at: str
    rule: str
    pack_version: str = "cabinetry.frameless@1.1.0"
    profile_id: str = ""
    catalog_id: str = ""
    archetype_id: str = ""


@dataclass(frozen=True)
class HardwareProvenance(Provenance):
    """Source-map provenance for purchased systems rather than cut parts."""

    source_url: str = ""


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
    coordinate_system: str = (
        "named face; origin=cut-list lower-left; +X=cut-list length; "
        "+Y=cut-list width; no implicit mirror"
    )
    pitch_axis: str = ""
    receiving_part_id: str = ""


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
class BaseShellModel:
    profile: ConstructionProfile
    wall_anchor: WallAnchorProduct
    cabinet: BaseCabinetDecl | DrawerBaseDecl
    x0_mm: float
    front_y_mm: float
    base_z_mm: float
    body_height_mm: float
    inside_width_mm: float
    carcass_depth_mm: float
    inside_depth_mm: float
    carcass_parts: tuple[PartModel, ...]
    support_parts: tuple[PartModel, ...]
    groove_machining: tuple[MachiningFeature, ...]
    joinery_machining: tuple[MachiningFeature, ...]
    hardware: tuple[HardwareSystem, ...]
    derived: tuple[DerivedValue, ...]
    source_map: dict[str, Provenance] = field(compare=True)
    anchor_stud_ids: tuple[str, ...] = ()


def params(**kwargs) -> tuple[tuple[str, object], ...]:
    return tuple(kwargs.items())


def build_base_shell(
    section: CabinetrySection,
    cabinet: BaseCabinetDecl | DrawerBaseDecl,
) -> BaseShellModel:
    """Build only the carcass, toe platform, surveyed wall, and common hardware."""

    profile = get_profile(section.profile_id)
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
    anchor_h = profile.stretcher_depth_mm
    anchor_front_y = back_plane - back_t - t
    anchor_z = base_z + height - t - anchor_h

    carcass_parts: list[PartModel] = []
    support_parts: list[PartModel] = []
    source_map: dict[str, Provenance] = {}

    def add_panel(target: list[PartModel], role: str, rule: str, *,
                  length: float, panel_width: float, thickness: float,
                  at: tuple[float, float, float],
                  rotate: tuple[tuple[str, float], ...] = (),
                  surface: str = "concealed", bands: tuple[str, ...] = (),
                  grooves: tuple[dict[str, object], ...] = ()) -> None:
        part_id = f"cabinetry.{cabinet.cabinet_id}.{role}"
        target.append(PartModel(
            part_id=part_id,
            role=role,
            name=f"{cabinet.cabinet_id} {role.replace('_', ' ')}",
            component_type="plywood_panel",
            params=params(
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

    add_panel(
        carcass_parts, "left_end", "carcass.left_end",
        length=body_h, panel_width=depth, thickness=t,
        at=(x0, front_y + depth, base_z + toe),
        rotate=(("Y", -90.0), ("Z", 180.0)),
        surface=("exposed_exterior" if cabinet.left_end == "exposed"
                 else "semi_exposed"), bands=("front",),
        grooves=({
            "x": t - groove_d, "y": profile.back_inset_mm,
            "length": back_blank_h, "width": groove_w, "depth": groove_d,
            "face": "top", "feature": "captured_back",
            "source": "carcass.captured_back.groove.left_end",
        },),
    )
    add_panel(
        carcass_parts, "right_end", "carcass.right_end",
        length=body_h, panel_width=depth, thickness=t,
        at=(x0 + width, front_y, base_z + toe), rotate=(("Y", -90.0),),
        surface=("exposed_exterior" if cabinet.right_end == "exposed"
                 else "semi_exposed"), bands=("front",),
        grooves=({
            "x": t - groove_d, "y": depth - profile.back_inset_mm - groove_w,
            "length": back_blank_h, "width": groove_w, "depth": groove_d,
            "face": "top", "feature": "captured_back",
            "source": "carcass.captured_back.groove.right_end",
        },),
    )
    add_panel(
        carcass_parts, "bottom", "carcass.bottom",
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
        carcass_parts, "captured_back", "carcass.captured_back",
        length=back_blank_w, panel_width=back_blank_h, thickness=back_t,
        at=(x0 + t - groove_d, back_plane,
            base_z + toe + t - groove_d), rotate=(("X", 90.0),),
        surface="semi_exposed",
    )
    add_panel(
        carcass_parts, "front_stretcher", "carcass.front_stretcher",
        length=inside_w, panel_width=profile.stretcher_depth_mm, thickness=t,
        at=(x0 + t, front_y, base_z + height - t), surface="concealed",
    )
    add_panel(
        carcass_parts, "rear_stretcher", "carcass.rear_stretcher",
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
        carcass_parts, "anchor_strip", "installation.anchor_strip",
        length=inside_w, panel_width=anchor_h, thickness=t,
        at=(x0 + t, back_plane - back_t, anchor_z),
        rotate=(("X", 90.0),), surface="concealed",
    )

    base_depth = (
        carcass_depth - groove_w - cabinet.toe_kick_setback_mm
        - 2 * profile.toe_base_member_thickness_mm
    )
    add_panel(
        support_parts, "toe_front", "base.toe_front",
        length=width, panel_width=toe,
        thickness=profile.toe_base_member_thickness_mm,
        at=(x0, front_y + cabinet.toe_kick_setback_mm
            + profile.toe_base_member_thickness_mm, base_z),
        rotate=(("X", 90.0),), surface="exposed_exterior", bands=("top",),
    )
    add_panel(
        support_parts, "toe_rear", "base.toe_rear",
        length=width, panel_width=toe,
        thickness=profile.toe_base_member_thickness_mm,
        # The back face stops at the bottom-groove front.  This keeps the
        # attachment line in solid bottom stock instead of through the
        # captured-back groove or on the bottom's rear edge.
        at=(x0, front_y + carcass_depth - groove_w, base_z),
        rotate=(("X", 90.0),),
        surface="concealed",
    )
    add_panel(
        support_parts, "toe_left", "base.toe_left",
        length=base_depth, panel_width=toe,
        thickness=profile.toe_base_member_thickness_mm,
        at=(x0, front_y + cabinet.toe_kick_setback_mm
            + profile.toe_base_member_thickness_mm, base_z),
        rotate=(("X", 90.0), ("Z", 90.0)), surface="concealed",
    )
    add_panel(
        support_parts, "toe_right", "base.toe_right",
        length=base_depth, panel_width=toe,
        thickness=profile.toe_base_member_thickness_mm,
        at=(x0 + width - profile.toe_base_member_thickness_mm,
            front_y + cabinet.toe_kick_setback_mm
            + profile.toe_base_member_thickness_mm, base_z),
        rotate=(("X", 90.0), ("Z", 90.0)), surface="concealed",
    )

    for stud in wall.studs:
        part_id = f"site.{wall.wall_id}.{stud.stud_id}"
        support_parts.append(PartModel(
            part_id=part_id,
            role=f"wall_stud_{stud.stud_id}",
            name=f"{wall.wall_id} {stud.stud_id}",
            component_type="lumber",
            params=params(nominal="2x4", length=wall.height_mm),
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

    anchor_min_x = x0 + t + profile.anchor_edge_clearance_mm
    anchor_max_x = x0 + width - t - profile.anchor_edge_clearance_mm
    anchor_studs = tuple(
        stud for stud in wall.studs
        if anchor_min_x <= wall.plane_origin_mm[0] + stud.position_mm <= anchor_max_x
    )
    screw_z = anchor_z + anchor_h / 2
    for stud in anchor_studs:
        role = f"wall_anchor_{stud.stud_id}"
        part_id = f"cabinetry.{cabinet.cabinet_id}.{role}"
        support_parts.append(PartModel(
            part_id=part_id,
            role=role,
            name=f"{cabinet.cabinet_id} wall anchor at {stud.stud_id}",
            component_type="structural_screw",
            params=params(
                diameter=wall_anchor.diameter_mm, length=wall_anchor.length_mm
            ),
            at_mm=(wall.plane_origin_mm[0] + stud.position_mm,
                   anchor_front_y, screw_z),
            rotate=(("X", 90.0),),
            length_mm=wall_anchor.length_mm,
            width_mm=wall_anchor.diameter_mm,
            thickness_mm=wall_anchor.diameter_mm,
            surface_class="concealed",
        ))
        source_map[part_id] = Provenance(
            declared_at=f"site.wall.studs.{stud.stud_id}",
            rule="installation.wall_anchor",
            profile_id=profile.profile_id,
        )

    groove_machining: list[MachiningFeature] = []
    for part in (*carcass_parts, *support_parts):
        for index, groove in enumerate(part.params_dict().get("grooves", ())):
            groove_machining.append(MachiningFeature(
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

    joinery_machining: list[MachiningFeature] = []
    side_rows = (
        # receiving role, count, start (X,Y), pitch, pitch axis
        ("bottom", 3, (t / 2, 50.0), (carcass_depth - 100.0) / 2, "Y"),
        ("front_stretcher", 2, (body_h - t / 2, 25.0), 50.0, "Y"),
        (
            "rear_stretcher", 2,
            (body_h - t / 2,
             carcass_depth - profile.stretcher_depth_mm + 25.0),
            50.0, "Y",
        ),
        (
            "anchor_strip", 2,
            (body_h - anchor_h + 25.0, carcass_depth - back_t - t / 2),
            50.0, "X",
        ),
    )
    for side_role in ("left_end", "right_end"):
        side_id = f"cabinetry.{cabinet.cabinet_id}.{side_role}"
        for receiving_role, count, start, pitch, pitch_axis in side_rows:
            joinery_machining.append(MachiningFeature(
                feature_id=f"{side_id}.confirmat_{receiving_role}",
                kind="confirmat_step_drill",
                part_id=side_id,
                location_mm=start,
                diameter_mm=confirmat.blind_pilot_diameter_mm,
                depth_mm=confirmat.length_mm - t,
                pitch_mm=pitch,
                count=count,
                source=confirmat.product_id,
                width_mm=confirmat.through_shank_diameter_mm,
                length_mm=confirmat.countersink_diameter_mm,
                face="outside",
                coordinate_system=(
                    "side outside face; origin=bottom-front corner; "
                    "+X=up/cut-list length; +Y=toward wall/cut-list width"
                ),
                pitch_axis=pitch_axis,
                receiving_part_id=(
                    f"cabinetry.{cabinet.cabinet_id}.{receiving_role}"
                ),
            ))
    for rail_role in ("toe_front", "toe_rear"):
        rail_id = f"cabinetry.{cabinet.cabinet_id}.{rail_role}"
        for sleeper_role, x in (
            ("toe_left", t / 2), ("toe_right", width - t / 2),
        ):
            joinery_machining.append(MachiningFeature(
                feature_id=f"{rail_id}.confirmat_{sleeper_role}",
                kind="confirmat_step_drill",
                part_id=rail_id,
                location_mm=(x, toe * 0.3),
                diameter_mm=confirmat.blind_pilot_diameter_mm,
                depth_mm=confirmat.length_mm - t,
                pitch_mm=toe * 0.4,
                count=2,
                source=confirmat.product_id,
                width_mm=confirmat.through_shank_diameter_mm,
                length_mm=confirmat.countersink_diameter_mm,
                face="outside",
                coordinate_system=(
                    "toe-rail outside face; origin=left-bottom corner; "
                    "+X=right/cut-list length; +Y=up/cut-list width"
                ),
                pitch_axis="Y",
                receiving_part_id=(
                    f"cabinetry.{cabinet.cabinet_id}.{sleeper_role}"
                ),
            ))

    toe_attachment_x = inside_w / 4
    toe_attachment_pitch = inside_w / 4
    toe_attachment_y = {
        "toe_front": (
            cabinet.toe_kick_setback_mm
            + profile.toe_base_member_thickness_mm / 2
        ),
        "toe_rear": (
            carcass_depth - groove_w
            - profile.toe_base_member_thickness_mm / 2
        ),
    }
    bottom_id = f"cabinetry.{cabinet.cabinet_id}.bottom"
    for rail_role in ("toe_front", "toe_rear"):
        joinery_machining.append(MachiningFeature(
            feature_id=f"{bottom_id}.toe_attachment_{rail_role}",
            kind="toe_attachment_station",
            part_id=bottom_id,
            location_mm=(toe_attachment_x, toe_attachment_y[rail_role]),
            pitch_mm=toe_attachment_pitch,
            count=3,
            source=toe_attachment.product_id,
            face="top",
            coordinate_system=(
                "cabinet-bottom top face; origin=front-left corner; "
                "+X=right/cut-list length; +Y=toward wall/cut-list width"
            ),
            pitch_axis="X",
            receiving_part_id=(
                f"cabinetry.{cabinet.cabinet_id}.{rail_role}"
            ),
        ))

    hardware = (
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
    return BaseShellModel(
        profile=profile,
        wall_anchor=wall_anchor,
        cabinet=cabinet,
        x0_mm=x0,
        front_y_mm=front_y,
        base_z_mm=base_z,
        body_height_mm=body_h,
        inside_width_mm=inside_w,
        carcass_depth_mm=carcass_depth,
        inside_depth_mm=inside_depth,
        carcass_parts=tuple(carcass_parts),
        support_parts=tuple(support_parts),
        groove_machining=tuple(groove_machining),
        joinery_machining=tuple(joinery_machining),
        hardware=hardware,
        derived=(DerivedValue(
            "inside_width", inside_w, "mm",
            ("cabinet_width", "carcass_thickness"),
            "carcass.clear_width",
        ),),
        source_map=source_map,
        anchor_stud_ids=tuple(stud.stud_id for stud in anchor_studs),
    )
