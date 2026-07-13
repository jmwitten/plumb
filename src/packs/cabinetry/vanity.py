"""Narrow wall-hung vanity extension over the unchanged DetailSpec language."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ...core.units import IN
from ...spec import compile_spec
from ...spec.schema import (
    AuthoredStage,
    BondSpec,
    ComponentSpec,
    ContactSpec,
    DetailSpecDoc,
    OverlapSpec,
    RawSpec,
    SequenceSpec,
    ValidationSpec,
)
from ..project import PackedProject, ProjectSchemaError
from .artifacts import (
    CabinetArtifacts,
    CutListItem,
    EdgeBandItem,
    HardwareItem,
    WorkStep,
)
from .catalogs import (
    get_adhesive,
    get_assembly_fastener,
    get_hinge_product,
    get_wall_anchor_product,
)
from .evidence import EvidenceRecord
from .model import (
    DerivedValue,
    HardwareSystem,
    MachiningFeature,
    PartModel,
    Provenance,
)
from .profiles import get_profile
from .presets import expand_vanity_project
from .schema import (
    MaterialEvidence,
    SiteSurvey,
    _finite_number,
    _length,
    _parse_site,
    _take,
)
from .validation import CabinetFinding, CabinetReport


@dataclass(frozen=True)
class FloatingVanityDecl:
    vanity_id: str
    width_mm: float
    height_mm: float
    depth_mm: float
    bottom_elevation_mm: float
    wall_id: str
    from_left_datum_mm: float
    door_count: int
    top_type: str
    sink_type: str
    source_archetype: str = ""


@dataclass(frozen=True)
class PlumbingKeepout:
    from_cabinet_left_mm: float
    width_mm: float
    bottom_elevation_mm: float
    height_mm: float


@dataclass(frozen=True)
class VanityLoads:
    top_and_sink_dead_load_lb: float
    service_load_lb: float


@dataclass(frozen=True)
class BackingSurvey:
    nominal: str
    from_left_datum_mm: float
    width_mm: float
    bottom_elevation_mm: float
    flush_with_stud_face: bool
    verified: bool


@dataclass(frozen=True)
class MountEngineering:
    status: str
    reference: str


@dataclass(frozen=True)
class VanityMounting:
    rear_rail_height_mm: float
    backing: BackingSurvey
    fastener_product_id: str
    pilot_diameter_mm: float
    engineering: MountEngineering


@dataclass(frozen=True)
class AnchorTarget:
    """One modeled rail fastener and the surveyed structure it penetrates."""

    target_id: str
    target_part_id: str
    x_mm: float
    kind: str
    verified: bool


@dataclass(frozen=True)
class VanitySection:
    mode: str
    profile_id: str
    material_evidence: MaterialEvidence
    site: SiteSurvey
    vanity: FloatingVanityDecl
    plumbing: PlumbingKeepout
    loads: VanityLoads
    mounting: VanityMounting


def _material_evidence(raw) -> MaterialEvidence:
    f = _take(
        raw,
        {
            "tsca_title_vi", "reference", "product", "density_kg_m3",
            "modulus_elasticity_mpa", "property_reference",
        },
        set(),
        "vanity.material_evidence",
    )
    if f["tsca_title_vi"] not in {"verified", "required", "unknown"}:
        raise ProjectSchemaError(
            "vanity.material_evidence.tsca_title_vi must be one of "
            "['required', 'unknown', 'verified']"
        )
    return MaterialEvidence(
        str(f["tsca_title_vi"]),
        str(f["reference"]).strip(),
        str(f["product"]).strip(),
        _finite_number(
            f["density_kg_m3"], "vanity.material_evidence.density_kg_m3",
            positive=True,
        ),
        _finite_number(
            f["modulus_elasticity_mpa"],
            "vanity.material_evidence.modulus_elasticity_mpa",
            positive=True,
        ),
        str(f["property_reference"]).strip(),
    )


def parse_vanity_project(doc, source_archetype: str = "") -> VanitySection:
    missing = [key for key in ("site", "vanity") if key not in doc.sections]
    if missing:
        raise ProjectSchemaError(
            f"vanity.frameless@1 requires project sections {missing}"
        )
    site = _parse_site(doc.sections["site"], doc.units)
    f = _take(
        doc.sections["vanity"],
        {
            "mode", "profile", "material_evidence", "cabinet", "plumbing",
            "loads", "mounting",
        },
        set(),
        "vanity",
    )
    if f["mode"] not in {"draft", "release"}:
        raise ProjectSchemaError("vanity.mode must be 'draft' or 'release'")
    profile = get_profile(str(f["profile"]))

    cf = _take(
        f["cabinet"],
        {
            "id", "type", "width", "height", "depth", "bottom_elevation",
            "placement", "front", "top",
        },
        set(),
        "vanity.cabinet",
    )
    vanity_id = str(cf["id"]).strip()
    if not vanity_id:
        raise ProjectSchemaError("vanity.cabinet.id must be non-empty")
    if cf["type"] != "floating":
        raise ProjectSchemaError(
            "vanity.frameless@1 requires cabinet.type 'floating'"
        )
    placement = _take(
        cf["placement"], {"against", "from_left_datum"}, set(),
        "vanity.cabinet.placement",
    )
    if placement["against"] != site.wall.wall_id:
        raise ProjectSchemaError(
            f"vanity.cabinet.placement.against: unknown wall "
            f"{placement['against']!r}; known wall: {site.wall.wall_id!r}"
        )
    front = _take(cf["front"], {"doors"}, set(), "vanity.cabinet.front")
    if front["doors"] != 2:
        raise ProjectSchemaError(
            "vanity.cabinet.front.doors: v1 requires exactly two overlay doors"
        )
    top = _take(cf["top"], {"type", "sink"}, set(), "vanity.cabinet.top")
    if top["type"] != "field_installed" or top["sink"] != "field_installed":
        raise ProjectSchemaError(
            "vanity v1 requires a field_installed top and field_installed sink"
        )
    width = _length(cf["width"], doc.units, "vanity.cabinet.width", positive=True)
    height = _length(
        cf["height"], doc.units, "vanity.cabinet.height", positive=True
    )
    depth = _length(cf["depth"], doc.units, "vanity.cabinet.depth", positive=True)
    bottom = _length(
        cf["bottom_elevation"], doc.units,
        "vanity.cabinet.bottom_elevation",
    )
    from_left = _length(
        placement["from_left_datum"], doc.units,
        "vanity.cabinet.placement.from_left_datum",
    )
    if bottom < 0:
        raise ProjectSchemaError("vanity.cabinet.bottom_elevation must be non-negative")
    if from_left < 0 or from_left + width > site.wall.length_mm:
        raise ProjectSchemaError("vanity cabinet span lies outside the surveyed wall")
    if bottom + height > site.wall.height_mm:
        raise ProjectSchemaError("vanity cabinet height lies outside the surveyed wall")
    vanity = FloatingVanityDecl(
        vanity_id, width, height, depth, bottom, site.wall.wall_id, from_left,
        2, str(top["type"]), str(top["sink"]), source_archetype,
    )

    pf = _take(f["plumbing"], {"keepout"}, set(), "vanity.plumbing")
    kf = _take(
        pf["keepout"],
        {"from_cabinet_left", "width", "bottom_elevation", "height"},
        set(),
        "vanity.plumbing.keepout",
    )
    keepout = PlumbingKeepout(
        _length(
            kf["from_cabinet_left"], doc.units,
            "vanity.plumbing.keepout.from_cabinet_left",
        ),
        _length(
            kf["width"], doc.units, "vanity.plumbing.keepout.width",
            positive=True,
        ),
        _length(
            kf["bottom_elevation"], doc.units,
            "vanity.plumbing.keepout.bottom_elevation",
        ),
        _length(
            kf["height"], doc.units, "vanity.plumbing.keepout.height",
            positive=True,
        ),
    )
    if (
        keepout.from_cabinet_left_mm <= profile.carcass_thickness_mm
        or keepout.from_cabinet_left_mm + keepout.width_mm
        >= width - profile.carcass_thickness_mm
    ):
        raise ProjectSchemaError(
            "vanity plumbing keepout must leave positive cabinet width on both sides"
        )
    if (
        keepout.bottom_elevation_mm < bottom
        or keepout.bottom_elevation_mm + keepout.height_mm > bottom + height
    ):
        raise ProjectSchemaError(
            "vanity plumbing keepout must lie within the cabinet elevation"
        )

    lf = _take(
        f["loads"], {"top_and_sink_dead_load_lb", "service_load_lb"}, set(),
        "vanity.loads",
    )
    loads = VanityLoads(
        _finite_number(
            lf["top_and_sink_dead_load_lb"],
            "vanity.loads.top_and_sink_dead_load_lb", positive=True,
        ),
        _finite_number(
            lf["service_load_lb"], "vanity.loads.service_load_lb",
            positive=True,
        ),
    )

    mf = _take(
        f["mounting"], {"rear_rail_height", "backing", "fastener", "engineering"},
        set(), "vanity.mounting",
    )
    bf = _take(
        mf["backing"],
        {
            "type", "from_left_datum", "width", "bottom_elevation",
            "flush_with_stud_face", "verified",
        },
        set(),
        "vanity.mounting.backing",
    )
    if bf["type"] != "blocking_2x8":
        raise ProjectSchemaError(
            "vanity.mounting.backing.type: v1 requires 'blocking_2x8'"
        )
    for key in ("flush_with_stud_face", "verified"):
        if not isinstance(bf[key], bool):
            raise ProjectSchemaError(
                f"vanity.mounting.backing.{key} must be true or false"
            )
    backing = BackingSurvey(
        "2x8",
        _length(
            bf["from_left_datum"], doc.units,
            "vanity.mounting.backing.from_left_datum",
        ),
        _length(
            bf["width"], doc.units, "vanity.mounting.backing.width",
            positive=True,
        ),
        _length(
            bf["bottom_elevation"], doc.units,
            "vanity.mounting.backing.bottom_elevation",
        ),
        bf["flush_with_stud_face"],
        bf["verified"],
    )
    if backing.from_left_datum_mm < 0 or (
        backing.from_left_datum_mm + backing.width_mm > site.wall.length_mm
    ):
        raise ProjectSchemaError("vanity mounting backing lies outside the wall")

    ff = _take(
        mf["fastener"], {"product", "pilot_diameter"}, set(),
        "vanity.mounting.fastener",
    )
    fastener = get_wall_anchor_product(str(ff["product"]))
    if fastener.product_id != "grk_rss_5_16x4@2026.1":
        raise ProjectSchemaError(
            "vanity v1 supports only grk_rss_5_16x4@2026.1"
        )
    pilot = _length(
        ff["pilot_diameter"], doc.units,
        "vanity.mounting.fastener.pilot_diameter", positive=True,
    )
    ef = _take(
        mf["engineering"], {"status", "reference"}, set(),
        "vanity.mounting.engineering",
    )
    if ef["status"] not in {"verified", "required", "unknown"}:
        raise ProjectSchemaError(
            "vanity.mounting.engineering.status must be one of "
            "['required', 'unknown', 'verified']"
        )
    engineering = MountEngineering(
        str(ef["status"]), str(ef["reference"]).strip()
    )
    mounting = VanityMounting(
        _length(
            mf["rear_rail_height"], doc.units,
            "vanity.mounting.rear_rail_height", positive=True,
        ),
        backing,
        fastener.product_id,
        pilot,
        engineering,
    )
    return VanitySection(
        str(f["mode"]), profile.profile_id, _material_evidence(f["material_evidence"]),
        site, vanity, keepout, loads, mounting,
    )


@dataclass(frozen=True)
class VanityModel:
    project_name: str
    mode: str
    profile: object
    hinge: object
    wall_anchor: object
    section: VanitySection
    parts: tuple[PartModel, ...]
    machining: tuple[MachiningFeature, ...]
    hardware: tuple[HardwareSystem, ...]
    derived: tuple[DerivedValue, ...]
    source_map: dict[str, Provenance]
    anchor_stud_ids: tuple[str, ...]
    anchor_targets: tuple[AnchorTarget, ...]

    def part(self, role: str) -> PartModel:
        matches = [part for part in self.parts if part.role == role]
        if len(matches) != 1:
            raise KeyError(f"expected one vanity part {role!r}, found {len(matches)}")
        return matches[0]

    def derived_value(self, name: str) -> DerivedValue:
        return next(item for item in self.derived if item.name == name)


_VANITY_BOND_ROLES = (
    ("bottom", "left_end"),
    ("bottom", "right_end"),
    ("front_stretcher", "left_end"),
    ("front_stretcher", "right_end"),
    ("rear_mounting_rail", "left_end"),
    ("rear_mounting_rail", "right_end"),
    ("lower_back_left", "bottom"),
    ("lower_back_left", "left_end"),
    ("lower_back_right", "bottom"),
    ("lower_back_right", "right_end"),
)


def _params(**kwargs):
    return tuple(kwargs.items())


def build_vanity_model(section: VanitySection, *, project_name: str) -> VanityModel:
    profile = get_profile(section.profile_id)
    hinge = get_hinge_product(profile.hinge_product_id)
    anchor = get_wall_anchor_product(section.mounting.fastener_product_id)
    confirmat = get_assembly_fastener("hafele_confirmat_7x50_264_42_190@2026.1")
    adhesive = get_adhesive("titebond_original_5064@2026.1")
    vanity = section.vanity
    wall = section.site.wall
    x0 = wall.plane_origin_mm[0] + vanity.from_left_datum_mm
    wall_y = wall.plane_origin_mm[1]
    front_y = wall_y - vanity.depth_mm
    bottom_z = vanity.bottom_elevation_mm
    width, height, depth = vanity.width_mm, vanity.height_mm, vanity.depth_mm
    t = profile.carcass_thickness_mm
    inside_w = width - 2 * t
    rail_h = section.mounting.rear_rail_height_mm
    rail_z = bottom_z + height - t - rail_h
    door_w = (
        width - 2 * profile.door_side_reveal_mm - profile.door_center_gap_mm
    ) / 2
    door_h = height - profile.door_top_reveal_mm - profile.door_bottom_reveal_mm
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
        rotate=(),
        surface="concealed",
        bands=(),
    ):
        part_id = f"vanity.{vanity.vanity_id}.{role}"
        parts.append(PartModel(
            part_id, role, f"{vanity.vanity_id} {role.replace('_', ' ')}",
            "plywood_panel",
            _params(length=length, width=panel_width, thickness=thickness),
            at, tuple(rotate), length, panel_width, thickness, surface, tuple(bands),
        ))
        source_map[part_id] = Provenance(
            f"vanity.cabinet.{vanity.vanity_id}", rule,
            pack_version="vanity.frameless@1.0.0",
            profile_id=profile.profile_id,
            archetype_id=vanity.source_archetype,
        )

    add_panel(
        "left_end", "vanity.carcass.left_end",
        length=height, panel_width=depth, thickness=t,
        at=(x0, wall_y, bottom_z),
        rotate=(("Y", -90.0), ("Z", 180.0)),
        surface="exposed_exterior", bands=("front", "bottom"),
    )
    add_panel(
        "right_end", "vanity.carcass.right_end",
        length=height, panel_width=depth, thickness=t,
        at=(x0 + width, front_y, bottom_z), rotate=(("Y", -90.0),),
        surface="exposed_exterior", bands=("front", "bottom"),
    )
    add_panel(
        "bottom", "vanity.carcass.bottom",
        length=inside_w, panel_width=depth, thickness=t,
        at=(x0 + t, front_y, bottom_z),
        surface="semi_exposed", bands=("front",),
    )
    add_panel(
        "front_stretcher", "vanity.carcass.front_stretcher",
        length=inside_w, panel_width=profile.stretcher_depth_mm, thickness=t,
        at=(x0 + t, front_y, bottom_z + height - t),
    )
    add_panel(
        "rear_mounting_rail", "vanity.mount.full_width_rear_rail",
        length=inside_w, panel_width=rail_h, thickness=t,
        at=(x0 + t, wall_y, rail_z), rotate=(("X", 90.0),),
    )
    keepout_left = x0 + section.plumbing.from_cabinet_left_mm
    keepout_right = keepout_left + section.plumbing.width_mm
    lower_h = min(profile.stretcher_depth_mm, section.plumbing.height_mm)
    left_len = keepout_left - (x0 + t)
    right_len = x0 + width - t - keepout_right
    add_panel(
        "lower_back_left", "vanity.plumbing.split_lower_back.left",
        length=left_len, panel_width=lower_h, thickness=t,
        at=(x0 + t, wall_y, bottom_z + t), rotate=(("X", 90.0),),
    )
    add_panel(
        "lower_back_right", "vanity.plumbing.split_lower_back.right",
        length=right_len, panel_width=lower_h, thickness=t,
        at=(keepout_right, wall_y, bottom_z + t), rotate=(("X", 90.0),),
    )
    add_panel(
        "door_left", "vanity.fronts.paired_overlay.left",
        length=door_w, panel_width=door_h, thickness=profile.door_thickness_mm,
        at=(x0 + profile.door_side_reveal_mm, front_y,
            bottom_z + profile.door_bottom_reveal_mm),
        rotate=(("X", 90.0),), surface="exposed_exterior",
        bands=("left", "right", "top", "bottom"),
    )
    add_panel(
        "door_right", "vanity.fronts.paired_overlay.right",
        length=door_w, panel_width=door_h, thickness=profile.door_thickness_mm,
        at=(x0 + profile.door_side_reveal_mm + door_w
            + profile.door_center_gap_mm, front_y,
            bottom_z + profile.door_bottom_reveal_mm),
        rotate=(("X", 90.0),), surface="exposed_exterior",
        bands=("left", "right", "top", "bottom"),
    )

    for stud in wall.studs:
        part_id = f"site.{wall.wall_id}.{stud.stud_id}"
        parts.append(PartModel(
            part_id, f"wall_stud_{stud.stud_id}",
            f"{wall.wall_id} {stud.stud_id}", "lumber",
            _params(nominal="2x4", length=wall.height_mm),
            (
                wall.plane_origin_mm[0] + stud.position_mm - wall.stud_width_mm / 2,
                wall_y + wall.finish_thickness_mm,
                wall.plane_origin_mm[2],
            ),
            (("Y", -90.0), ("Z", -90.0)),
            wall.height_mm, wall.stud_width_mm, wall.stud_depth_mm,
            "existing_concealed",
        ))
        source_map[part_id] = Provenance(
            f"site.wall.studs.{stud.stud_id}", "site.surveyed_stud",
            pack_version="vanity.frameless@1.0.0", profile_id=profile.profile_id,
        )

    backing = section.mounting.backing
    backing_start = wall.plane_origin_mm[0] + backing.from_left_datum_mm
    backing_end = backing_start + backing.width_mm
    sorted_studs = sorted(wall.studs, key=lambda item: item.position_mm)
    backing_index = 0
    backing_segments: list[tuple[str, float, float]] = []
    for left, right in zip(sorted_studs, sorted_studs[1:]):
        left_face = wall.plane_origin_mm[0] + left.position_mm + wall.stud_width_mm / 2
        right_face = wall.plane_origin_mm[0] + right.position_mm - wall.stud_width_mm / 2
        seg_start = max(backing_start, left_face)
        seg_end = min(backing_end, right_face)
        if seg_end - seg_start <= 1e-6:
            continue
        backing_index += 1
        part_id = f"site.{wall.wall_id}.vanity_backing_{backing_index}"
        parts.append(PartModel(
            part_id, f"backing_{backing_index}",
            f"{wall.wall_id} vanity 2x8 backing {backing_index}", "lumber",
            _params(nominal="2x8", length=seg_end - seg_start),
            (seg_start, wall_y + wall.finish_thickness_mm,
             backing.bottom_elevation_mm),
            (), seg_end - seg_start, 1.5 * IN, 7.25 * IN,
            "existing_concealed",
        ))
        source_map[part_id] = Provenance(
            "vanity.mounting.backing", "site.verified_blocking_2x8",
            pack_version="vanity.frameless@1.0.0", profile_id=profile.profile_id,
        )
        backing_segments.append((part_id, seg_start, seg_end))

    anchor_min = x0 + t + profile.anchor_edge_clearance_mm
    anchor_max = x0 + width - t - profile.anchor_edge_clearance_mm
    anchor_studs = tuple(
        stud for stud in sorted_studs
        if anchor_min <= wall.plane_origin_mm[0] + stud.position_mm <= anchor_max
    )
    anchor_targets: list[AnchorTarget] = [
        AnchorTarget(
            stud.stud_id,
            f"site.{wall.wall_id}.{stud.stud_id}",
            wall.plane_origin_mm[0] + stud.position_mm,
            "stud",
            stud.verified,
        )
        for stud in anchor_studs
    ]
    # V1 conservatively requires both the surveyed stud layout and full-width
    # blocking.  One fastener near each rail end engages that blocking, making
    # it an active substrate rather than dead context geometry.
    for label, target_x in (("backing_left", anchor_min),
                            ("backing_right", anchor_max)):
        segment = next(
            (item for item in backing_segments
             if item[1] - 1e-6 <= target_x <= item[2] + 1e-6),
            None,
        )
        if segment is not None:
            anchor_targets.append(AnchorTarget(
                label, segment[0], target_x, "backing", backing.verified,
            ))
    anchor_targets.sort(key=lambda item: (item.x_mm, item.target_id))
    screw_z = rail_z + rail_h / 2
    for target in anchor_targets:
        role = f"wall_anchor_{target.target_id}"
        part_id = f"vanity.{vanity.vanity_id}.{role}"
        parts.append(PartModel(
            part_id, role,
            f"{vanity.vanity_id} structural anchor {target.target_id}",
            "structural_screw",
            _params(diameter=anchor.diameter_mm, length=anchor.length_mm),
            (target.x_mm, wall_y - t, screw_z),
            (("X", 90.0),), anchor.length_mm, anchor.diameter_mm,
            anchor.diameter_mm, "concealed",
        ))
        source_map[part_id] = Provenance(
            (f"site.wall.studs.{target.target_id}"
             if target.kind == "stud" else "vanity.mounting.backing"),
            "vanity.mount.structural_anchor",
            pack_version="vanity.frameless@1.0.0", profile_id=profile.profile_id,
            catalog_id=anchor.product_id,
        )

    machining: list[MachiningFeature] = []
    overlay = t - profile.door_side_reveal_mm
    cup_from_edge = overlay + 6.5
    hinge_z = (profile.hinge_edge_offset_mm,
               door_h - profile.hinge_edge_offset_mm)
    for door_role, side_role, side in (
        ("door_left", "left_end", "left"),
        ("door_right", "right_end", "right"),
    ):
        door_id = f"vanity.{vanity.vanity_id}.{door_role}"
        side_id = f"vanity.{vanity.vanity_id}.{side_role}"
        for label, z_local in zip(("bottom", "top"), hinge_z):
            edge_x = cup_from_edge if side == "left" else door_w - cup_from_edge
            machining.append(MachiningFeature(
                f"{door_id}.hinge_{label}_cup", "hinge_cup", door_id,
                (edge_x, z_local), hinge.cup_diameter_mm, hinge.cup_depth_mm,
                source=hinge.product_id,
            ))
            machining.append(MachiningFeature(
                f"{side_id}.hinge_{label}_plate", "mounting_plate", side_id,
                (hinge.plate_line_mm, z_local), pitch_mm=hinge.plate_hole_spacing_mm,
                count=2, source=hinge.product_id,
            ))
    for target in anchor_targets:
        machining.append(MachiningFeature(
            f"vanity.{vanity.vanity_id}.rear_mounting_rail."
            f"pilot_{target.target_id}",
            "structural_anchor_pilot",
            f"vanity.{vanity.vanity_id}.rear_mounting_rail",
            (target.x_mm - (x0 + t), rail_h / 2),
            section.mounting.pilot_diameter_mm, t,
            source=anchor.evaluation_report_url,
        ))

    hardware = (
        HardwareSystem(
            f"vanity.{vanity.vanity_id}.hinges", "concealed_hinge_system",
            hinge.product_id, 4,
            tuple(f"vanity.{vanity.vanity_id}.{role}" for role in
                  ("door_left", "door_right", "left_end", "right_end")),
            "manufacturer_rated", hinge.source_url,
        ),
        HardwareSystem(
            f"vanity.{vanity.vanity_id}.structural_anchors",
            "wall_hung_structural_anchor_system", anchor.product_id,
            len(anchor_targets),
            tuple(f"vanity.{vanity.vanity_id}.wall_anchor_{target.target_id}"
                  for target in anchor_targets),
            "calculated", anchor.evaluation_report_url,
        ),
        HardwareSystem(
            f"vanity.{vanity.vanity_id}.carcass_confirmats",
            "carcass_confirmat_system", confirmat.product_id, 24,
            tuple(f"vanity.{vanity.vanity_id}.{role}" for role in
                  ("left_end", "right_end", "bottom", "front_stretcher",
                   "rear_mounting_rail", "lower_back_left", "lower_back_right")),
            "manufacturer_rated", confirmat.source_url,
        ),
        HardwareSystem(
            f"vanity.{vanity.vanity_id}.wood_glue", "wood_adhesive",
            adhesive.product_id, 1,
            tuple(f"vanity.{vanity.vanity_id}.{role}" for role in
                  ("left_end", "right_end", "bottom", "front_stretcher",
                   "rear_mounting_rail")),
            "manufacturer_rated", adhesive.source_url,
        ),
    )
    derived = (
        DerivedValue("inside_width", inside_w, "mm", ("width", "panel_thickness"),
                     "vanity.carcass.clear_width"),
        DerivedValue("door_width", door_w, "mm", ("width", "reveals"),
                     "vanity.fronts.paired_overlay.width"),
        DerivedValue("door_height", door_h, "mm", ("height", "reveals"),
                     "vanity.fronts.paired_overlay.height"),
        DerivedValue("hinge_overlay", overlay, "mm", ("panel_thickness", "reveal"),
                     "hardware.blum.overlay"),
        DerivedValue("mounting_rail_elevation", rail_z, "mm",
                     ("bottom_elevation", "height", "rail_height"),
                     "vanity.mount.rear_rail"),
    )
    return VanityModel(
        project_name, section.mode, profile, hinge, anchor, section,
        tuple(parts), tuple(machining), hardware, derived, source_map,
        tuple(stud.stud_id for stud in anchor_studs),
        tuple(anchor_targets),
    )


def _component(part: PartModel) -> ComponentSpec:
    return ComponentSpec(
        id=part.part_id,
        type=part.component_type,
        name=part.name,
        params=part.params_dict(),
        place=RawSpec(at=part.at_mm, rotate=part.rotate),
    )


def lower_vanity_model(model: VanityModel) -> DetailSpecDoc:
    vanity = model.section.vanity
    prefix = f"vanity.{vanity.vanity_id}."

    def cid(role):
        return prefix + role

    bonds = [BondSpec(cid(a), cid(b)) for a, b in _VANITY_BOND_ROLES]
    contacts = [ContactSpec(item.a, item.b) for item in bonds]
    overlaps: list[OverlapSpec] = []
    for target in model.anchor_targets:
        screw = cid(f"wall_anchor_{target.target_id}")
        overlaps.extend((
            OverlapSpec(screw, cid("rear_mounting_rail")),
            OverlapSpec(screw, target.target_part_id),
        ))
    existing_ids = tuple(
        part.part_id for part in model.parts if part.part_id.startswith("site.")
    )
    structural_case_ids = tuple(
        cid(role) for role in (
            "left_end", "right_end", "bottom", "front_stretcher",
            "rear_mounting_rail", "lower_back_left", "lower_back_right",
        )
    )
    anchor_ids = tuple(
        cid(f"wall_anchor_{target.target_id}")
        for target in model.anchor_targets
    )
    sequence_stages = [AuthoredStage(
        name="assemble_wall_hung_case",
        why=("The structural case and full-width rear rail are assembled "
             "before the case is offered to the wall."),
        parts=structural_case_ids,
    )]
    if anchor_ids:
        sequence_stages.append(AuthoredStage(
            name="anchor_case_to_wall",
            why=("Structural anchors are driven only after the complete case "
                 "is supported, aligned, level, and plumb."),
            parts=anchor_ids,
        ))
    return DetailSpecDoc(
        name=model.project_name,
        type="vanity_frameless_floating",
        units="mm",
        components=[_component(part) for part in model.parts],
        validation=ValidationSpec(
            bonds=bonds, contacts=contacts, expected_overlaps=overlaps,
        ),
        roles={part_id: "existing" for part_id in existing_ids},
        context_grounds=frozenset(existing_ids),
        sequence=SequenceSpec(stages=tuple(sequence_stages)),
    )


def _door_weight_kg(model: VanityModel, role: str) -> float:
    part = model.part(role)
    volume_m3 = part.length_mm * part.width_mm * part.thickness_mm / 1e9
    return volume_m3 * model.section.material_evidence.density_kg_m3


def validate_vanity_model(model: VanityModel) -> CabinetReport:
    findings: list[CabinetFinding] = []
    evidence: list[EvidenceRecord] = []

    def add(
        rule, verdict, severity, message, level, *, source="", affected=(),
        base_check="",
    ):
        evidence_id = f"evidence:{rule}"
        evidence.append(EvidenceRecord(
            evidence_id, rule, level, message, source=source,
        ))
        findings.append(CabinetFinding(
            rule, verdict, severity, message, level, (evidence_id,), tuple(affected),
            base_check,
        ))

    section = model.section
    vanity = section.vanity
    profile = model.profile
    clear = vanity.width_mm - 2 * profile.carcass_thickness_mm
    dimensions_ok = (
        clear > 0
        and vanity.height_mm > section.mounting.rear_rail_height_mm
        + 2 * profile.carcass_thickness_mm
        and vanity.depth_mm > profile.stretcher_depth_mm
    )
    add(
        "vanity.geometry.dimensions", "PASS" if dimensions_ok else "FAIL",
        "required",
        (f"Wall-hung carcass has {clear:.2f} mm clear width and positive rail, "
         "panel, and depth relationships." if dimensions_ok else
         "Wall-hung carcass dimensions are not buildable."),
        "derived", affected=(f"vanity.{vanity.vanity_id}",),
    )

    panels = [part for part in model.parts if part.component_type == "plywood_panel"]
    oversize = [
        part.part_id for part in panels
        if min(part.length_mm, part.width_mm) > 48 * IN
        or max(part.length_mm, part.width_mm) > 96 * IN
    ]
    add(
        "vanity.fabrication.panel_stock", "FAIL" if oversize else "PASS",
        "required",
        f"Panels outside the 4x8 stock envelope: {oversize}." if oversize else
        "Every generated vanity panel fits a 4x8 stock envelope.",
        "derived", affected=tuple(oversize),
    )

    material = section.material_evidence
    material_ok = material.tsca_title_vi == "verified" and bool(material.reference)
    add(
        "vanity.material.tsca_title_vi", "PASS" if material_ok else "UNKNOWN",
        "required",
        f"TSCA Title VI record supplied: {material.reference}." if material_ok else
        "A verified TSCA Title VI procurement record is required.",
        "field_verified" if material_ok else "unknown", source=material.reference,
    )
    properties_ok = bool(material.product and material.property_reference)
    add(
        "vanity.material.design_properties",
        "PASS" if properties_ok else "UNKNOWN", "required",
        (f"Pinned panel {material.product!r} uses density "
         f"{material.density_kg_m3:g} kg/m3 and MOE "
         f"{material.modulus_elasticity_mpa:g} MPa." if properties_ok else
         "Selected panel properties require a traceable product reference."),
        "manufacturer_rated" if properties_ok else "unknown",
        source=material.property_reference,
    )

    overlay = model.derived_value("hinge_overlay").value
    hinge_fit = (
        model.hinge.overlay_range_mm[0] <= overlay <= model.hinge.overlay_range_mm[1]
        and model.hinge.door_thickness_range_mm[0]
        <= profile.door_thickness_mm <= model.hinge.door_thickness_range_mm[1]
    )
    add(
        "vanity.hardware.hinge_fit", "PASS" if hinge_fit else "FAIL", "required",
        f"Pinned Blum hinge adapter {'fits' if hinge_fit else 'does not fit'} "
        f"the {overlay:.2f} mm overlay and {profile.door_thickness_mm:.2f} mm door.",
        "manufacturer_rated", source=model.hinge.source_url,
        affected=(model.part("door_left").part_id, model.part("door_right").part_id),
    )
    door_ok = all(
        model.part(role).length_mm <= model.hinge.max_chart_door_width_mm
        and model.part(role).width_mm <= model.hinge.max_two_hinge_door_height_mm
        and _door_weight_kg(model, role) <= model.hinge.max_two_hinge_door_weight_kg
        for role in ("door_left", "door_right")
    )
    add(
        "vanity.hardware.hinge_quantity", "PASS" if door_ok else "FAIL",
        "required",
        "Two hinges per door are inside the pinned Blum width, height, and mass chart."
        if door_ok else "Two hinges per door exceed the pinned Blum chart.",
        "manufacturer_rated", source=model.hinge.quantity_source_url,
    )

    backing = section.mounting.backing
    x0 = section.site.wall.plane_origin_mm[0] + vanity.from_left_datum_mm
    backing_end = backing.from_left_datum_mm + backing.width_mm
    backing_span_ok = (
        backing.from_left_datum_mm <= vanity.from_left_datum_mm + 1e-6
        and backing_end + 1e-6 >= vanity.from_left_datum_mm + vanity.width_mm
    )
    rail_z = model.derived_value("mounting_rail_elevation").value
    backing_vertical_ok = (
        backing.bottom_elevation_mm <= rail_z + 1e-6
        and backing.bottom_elevation_mm + 7.25 * IN + 1e-6
        >= rail_z + section.mounting.rear_rail_height_mm
    )
    if not backing.flush_with_stud_face or not backing_span_ok or not backing_vertical_ok:
        backing_verdict = "FAIL"
        backing_message = (
            "Declared 2x8 backing is not flush with framing or does not cover "
            "the full rear mounting rail in plan and elevation."
        )
        backing_level = "derived"
    elif not backing.verified:
        backing_verdict = "UNKNOWN"
        backing_message = "Full-rail 2x8 backing is declared but not field-verified."
        backing_level = "unknown"
    else:
        backing_verdict = "PASS"
        backing_message = (
            "Field-verified flush 2x8 blocking covers the full rear mounting rail."
        )
        backing_level = "field_verified"
    add(
        "vanity.mount.backing", backing_verdict, "required", backing_message,
        backing_level, source="https://techcomm.kohler.com/techcomm/pdf/1533268-2.pdf",
        affected=tuple(part.part_id for part in model.parts
                       if part.role.startswith("backing_")),
    )

    unverified = [
        target.target_id for target in model.anchor_targets
        if not target.verified
    ]
    rail_left = x0 + profile.carcass_thickness_mm
    rail_right = x0 + vanity.width_mm - profile.carcass_thickness_mm
    end_ok = bool(model.anchor_targets) and (
        model.anchor_targets[0].x_mm - rail_left <= 16 * IN
        and rail_right - model.anchor_targets[-1].x_mm <= 16 * IN
    )
    if len(model.anchor_targets) < 2 or not end_ok:
        target_verdict, target_level = "FAIL", "derived"
        target_message = (
            "V1 requires at least two anchor targets with one within 16 in of "
            "each rear-rail end."
        )
    elif unverified:
        target_verdict, target_level = "UNKNOWN", "unknown"
        target_message = f"Anchor targets {unverified} are not field-verified."
    else:
        target_verdict, target_level = "PASS", "field_verified"
        target_message = (
            f"Verified anchors {[item.target_id for item in model.anchor_targets]} "
            "engage surveyed blocking near both rail ends and intervening studs."
        )
    add(
        "vanity.mount.targets", target_verdict, "required", target_message,
        target_level,
        source="https://techcomm.kohler.com/techcomm/pdf/1533268-2.pdf",
    )

    keepout_left = x0 + section.plumbing.from_cabinet_left_mm
    keepout_right = keepout_left + section.plumbing.width_mm
    keepout_bottom = section.plumbing.bottom_elevation_mm
    keepout_top = keepout_bottom + section.plumbing.height_mm
    anchor_z = rail_z + section.mounting.rear_rail_height_mm / 2
    conflicts = [
        target.target_id for target in model.anchor_targets
        if keepout_left <= target.x_mm <= keepout_right
        and keepout_bottom <= anchor_z <= keepout_top
    ]
    add(
        "vanity.plumbing.anchor_clearance", "FAIL" if conflicts else "PASS",
        "required",
        f"Structural anchors conflict with the plumbing keepout: {conflicts}."
        if conflicts else "Structural anchors clear the declared plumbing keepout.",
        "derived", affected=tuple(
            f"vanity.{vanity.vanity_id}.wall_anchor_{sid}" for sid in conflicts
        ),
    )

    # Domain-level load-path representation to the existing building boundary.
    # This deliberately says nothing about capacity: the engine traces modeled
    # members and fasteners; the project-specific review remains a separate
    # release obligation for force, eccentricity, substrate, and connection
    # adequacy.
    graph: dict[str, set[str]] = {}
    present_roles = {part.role for part in model.parts}
    present_ids = {part.part_id for part in model.parts}
    for a, b in _VANITY_BOND_ROLES:
        if a not in present_roles or b not in present_roles:
            continue
        graph.setdefault(a, set()).add(b)
        graph.setdefault(b, set()).add(a)
    for target in model.anchor_targets:
        screw = f"wall_anchor_{target.target_id}"
        screw_part_id = f"vanity.{vanity.vanity_id}.{screw}"
        if (screw_part_id not in present_ids
                or target.target_part_id not in present_ids):
            continue
        graph.setdefault("rear_mounting_rail", set()).add(screw)
        graph.setdefault(screw, set()).update(
            {"rear_mounting_rail", target.target_part_id}
        )
        graph.setdefault(target.target_part_id, set()).add(screw)
    terminal_ids = {
        target.target_part_id for target in model.anchor_targets
        if target.target_part_id in present_ids
        and f"vanity.{vanity.vanity_id}.wall_anchor_{target.target_id}"
        in present_ids
    }

    def reaches_structure(start: str) -> bool:
        seen = {start}
        pending = [start]
        while pending:
            current = pending.pop()
            if current in terminal_ids:
                return True
            for neighbor in graph.get(current, ()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    pending.append(neighbor)
        return False

    load_inputs = ("bottom", "front_stretcher", "left_end", "right_end")
    missing_paths = [role for role in load_inputs if not reaches_structure(role)]
    path_ok = not missing_paths and bool(terminal_ids)
    add(
        "vanity.mount.load_path_representation",
        "PASS" if path_ok else "FAIL", "required",
        (
            "The modeled carcass bonds and structural anchors represent a "
            "continuous path from the loaded case members through the rear rail "
            "to the surveyed existing wall-structure boundary; representation "
            "does not establish capacity."
            if path_ok else
            f"No represented wall-structure path exists for loaded members "
            f"{missing_paths}; capacity review cannot repair a missing model path."
        ),
        "derived",
        affected=tuple(f"vanity.{vanity.vanity_id}.{role}"
                       for role in missing_paths),
        base_check="load_path",
    )

    stack = profile.carcass_thickness_mm + section.site.wall.finish_thickness_mm
    embedment = model.wall_anchor.length_mm - stack
    min_embedment = 1.5 * IN
    embedment_ok = embedment + 1e-6 >= min_embedment
    pilot_ok = math.isclose(
        section.mounting.pilot_diameter_mm,
        model.wall_anchor.pilot_diameter_mm,
        abs_tol=0.2,
    )
    add(
        "vanity.mount.fastener_stack",
        "PASS" if embedment_ok and pilot_ok else "FAIL", "required",
        f"The modeled 4 in structural screw leaves {embedment / IN:.3f} in "
        f"embedment after the rail/finish stack; pilot is "
        f"{section.mounting.pilot_diameter_mm / IN:.4f} in.",
        "calculated", source=model.wall_anchor.evaluation_report_url,
    )

    loads_ok = (
        section.loads.top_and_sink_dead_load_lb > 0
        and section.loads.service_load_lb > 0
    )
    add(
        "vanity.mount.design_loads", "PASS" if loads_ok else "FAIL", "required",
        f"Recorded top/sink dead load {section.loads.top_and_sink_dead_load_lb:g} lb "
        f"and service load {section.loads.service_load_lb:g} lb; these are inputs "
        "to the project-specific mount review, not a capacity calculation.",
        "assumed",
    )

    engineering = section.mounting.engineering
    engineering_ok = engineering.status == "verified" and bool(engineering.reference)
    add(
        "vanity.mount.engineering", "PASS" if engineering_ok else "UNKNOWN",
        "required",
        (f"Author-declared project-specific wall-hung mount review record: "
         f"{engineering.reference}." if engineering_ok else
         "A referenced project-specific review of the rail, rail-to-case joinery, "
         "fasteners, backing connections, substrate, and eccentric vanity loads "
         "is required; manufacturer precedent and a screw report do not prove "
         "the custom assembly."),
        "field_verified" if engineering_ok else "unknown",
        source=engineering.reference,
    )

    env = section.site.environment
    missing = []
    if not env.building_enclosed:
        missing.append("building not enclosed")
    if not env.wet_work_complete:
        missing.append("wet work incomplete")
    if not env.hvac_operating:
        missing.append("HVAC not operating")
    if env.acclimation_hours < 72:
        missing.append("less than 72 hours acclimation")
    if not section.site.floor.verified:
        missing.append("floor datum not verified")
    add(
        "vanity.install.site_readiness", "FAIL" if missing else "PASS", "required",
        "Site is not ready: " + "; ".join(missing) + "." if missing else
        "Enclosure, wet-work, HVAC, acclimation, and floor datum are verified.",
        "field_verified",
    )
    add(
        "vanity.plumbing.local_code", "UNKNOWN", "advisory",
        "Trap, vent, supply, waterproofing, and penetration requirements depend "
        "on the selected products and local plumbing/building code.",
        "unknown",
    )
    add(
        "vanity.performance.physical_tests", "UNKNOWN", "advisory",
        "The custom wall-hung carcass and mount have not undergone manufacturer "
        "or KCMA physical testing.", "unknown",
    )
    return CabinetReport(
        model.mode,
        tuple(sorted(findings, key=lambda item: item.rule)),
        tuple(sorted(evidence, key=lambda item: item.evidence_id)),
    )


def _edge_length(part: PartModel, edge: str) -> float:
    if part.role.startswith("door_") and edge in {"left", "right"}:
        return part.width_mm
    return part.length_mm


def build_vanity_artifacts(model: VanityModel, report: CabinetReport) -> CabinetArtifacts:
    vanity = model.section.vanity
    fabricated = sorted(
        (part for part in model.parts if part.component_type == "plywood_panel"),
        key=lambda item: item.part_id,
    )
    cut_list = tuple(
        CutListItem(
            part.part_id, part.role, part.name, 1, part.length_mm, part.width_mm,
            part.thickness_mm, "prefinished plywood", part.surface_class,
            model.source_map[part.part_id].rule,
        )
        for part in fabricated
    )
    edge_banding = tuple(
        EdgeBandItem(
            part.part_id, edge, "band", _edge_length(part, edge),
            "applied matching edge band",
            "surface_policy.exposed_or_semi_exposed_edge",
        )
        for part in fabricated for edge in part.edge_bands
    )
    hardware = tuple(
        HardwareItem(
            item.system_id, item.kind, item.product_id, item.quantity,
            item.source_url, item.evidence, item.related_parts,
        )
        for item in sorted(model.hardware, key=lambda item: item.system_id)
    )
    panel_ids = tuple(part.part_id for part in fabricated)
    fabrication_steps = (
        WorkStep(10, "fab.verify_material",
                 "Verify panel product, thickness, finish faces, and TSCA lot record.",
                 panel_ids, "unknown"),
        WorkStep(20, "fab.breakdown",
                 "Break down and label all panels from the cut list, preserving "
                 "finish-face orientation and part ids.", panel_ids),
        WorkStep(30, "fab.rail_and_joinery",
                 "Machine the rear structural rail, split lower back rails, and "
                 "the pinned 7 x 50 mm Confirmat joinery schedule; do not introduce "
                 "a field plumbing cut outside the declared open bay.", panel_ids),
        WorkStep(40, "fab.hinges",
                 "Bore the pinned Blum cup and mounting-plate schedule.",
                 (f"vanity.{vanity.vanity_id}.door_left",
                  f"vanity.{vanity.vanity_id}.door_right"), "manufacturer_rated"),
        WorkStep(50, "fab.anchor_pilots",
                 f"Lay out the {model.section.mounting.pilot_diameter_mm / IN:.4f} in "
                 "rear-rail pilots from verified target centers; preserve at least "
                 "one anchor near each rail end and clear the plumbing keepout.",
                 (f"vanity.{vanity.vanity_id}.rear_mounting_rail",), "calculated"),
        WorkStep(60, "fab.dry_fit",
                 "Dry-fit the carcass, rail, doors, and hardware; verify diagonals, "
                 "rail seating, plumbing bay, and anchor access.", panel_ids),
    )
    assembly_steps = (
        WorkStep(10, "assembly.carcass",
                 "Assemble the bottom and front/lower rails between the ends with "
                 "the scheduled adhesive and Confirmat connectors on a flat bench.",
                 panel_ids),
        WorkStep(20, "assembly.structural_rail",
                 "Seat the full-width rear mounting rail tightly between the ends, "
                 "install its scheduled joinery, square the carcass, and inspect "
                 "the rail-to-case load path before finishing.",
                 (f"vanity.{vanity.vanity_id}.rear_mounting_rail",
                  f"vanity.{vanity.vanity_id}.left_end",
                  f"vanity.{vanity.vanity_id}.right_end")),
        WorkStep(30, "assembly.hardware_dry_fit",
                 "Dry-fit and cycle both doors, then ship fronts detached and "
                 "protect the structural rail and anchor pilot faces.",
                 (f"vanity.{vanity.vanity_id}.door_left",
                  f"vanity.{vanity.vanity_id}.door_right"), "manufacturer_rated"),
    )
    studs = ", ".join(model.anchor_stud_ids)
    targets = ", ".join(target.target_id for target in model.anchor_targets)
    installation_steps = (
        WorkStep(10, "install.release_gate",
                 "Confirm that pack and base-language release gates pass, including "
                 "the referenced project-specific wall-mount review.", evidence="unknown"),
        WorkStep(20, "install.verify_backing_and_services",
                 f"Open or otherwise verify the flush 2x8 backing, stud centers "
                 f"{studs}, finished wall plane, fastener path, and plumbing rough-in; "
                 "stop if site conditions differ from the released model.", evidence="unknown"),
        WorkStep(30, "install.datums",
                 "Transfer level vanity top and bottom datums from the verified "
                 "floor datum; mark the plumbing keepout and every anchor center."),
        WorkStep(40, "install.temporary_support",
                 "With two installers, construct and level a temporary full-width "
                 "support at the vanity bottom elevation; do not rely on workers "
                 "holding the case while anchors are drilled."),
        WorkStep(50, "install.set_and_align",
                 "Lift the vanity onto the temporary support, place it against the "
                 "finished wall, then verify level, plumb, top datum, wall contact, "
                 "and untwisted diagonals; shim only as allowed by the mount review.",
                 (f"vanity.{vanity.vanity_id}.left_end",
                  f"vanity.{vanity.vanity_id}.right_end")),
        WorkStep(60, "install.structural_anchors",
                 f"Drill the specified pilots near each end and at every intervening "
                 f"verified target ({targets}); install the scheduled 5/16 x 4 in GRK "
                 "RSS fasteners through the rear rail and finish into structural "
                 "framing/backing. Do not substitute drywall anchors.",
                 tuple(f"vanity.{vanity.vanity_id}.wall_anchor_{target.target_id}"
                       for target in model.anchor_targets), "manufacturer_rated"),
        WorkStep(70, "install.inspect_load_path",
                 "Inspect every anchor head, embedment path, rear-rail bearing, "
                 "rail-to-case joint, wall contact, level, and plumb against the "
                 "released mount review before you remove the temporary support.",
                 (f"vanity.{vanity.vanity_id}.rear_mounting_rail",),
                 "unknown"),
        WorkStep(80, "install.top_sink_and_plumbing",
                 "Install the selected top, sink, faucet, supplies, trap, and drain "
                 "to their manufacturer instructions and all local plumbing/building "
                 "requirements; keep structural members and anchors unmodified.",
                 evidence="unknown"),
        WorkStep(90, "install.leak_test",
                 "Seal required wall/cabinet penetrations with compatible products; "
                 "run and drain the fixture repeatedly, inspect every connection and "
                 "the cabinet interior, and correct all leakage before closing out.",
                 evidence="unknown"),
        WorkStep(100, "install.commission",
                 "Commission the vanity: recheck level/plumb, anchor and rail condition, "
                 "top/sink attachment, leaks, visible deflection, door engagement, "
                 "reveals, closure, finish damage, and clean-up.", evidence="unknown"),
    )
    return CabinetArtifacts(
        "detailgen/vanity-artifacts/v1", model.project_name,
        "vanity.frameless@1.0.0", model.profile.profile_id, model.mode, False,
        cut_list, edge_banding, hardware,
        tuple(sorted(model.machining, key=lambda item: item.feature_id)),
        fabrication_steps, assembly_steps, installation_steps,
    )


class FramelessVanityPack:
    pack_id = "vanity.frameless"
    major_version = 1
    version = "1.0.0"
    section_keys = ("site", "vanity")

    def parse(self, doc) -> VanitySection:
        expanded, source_archetype = expand_vanity_project(doc)
        return parse_vanity_project(expanded, source_archetype)

    def compile(self, doc):
        expanded, source_archetype = expand_vanity_project(doc)
        section = parse_vanity_project(expanded, source_archetype)
        model = build_vanity_model(section, project_name=doc.name)
        lowered = lower_vanity_model(model)
        report = validate_vanity_model(model)
        artifacts = build_vanity_artifacts(model, report)
        return PackedProject(
            project_doc=doc,
            model=model,
            lowered_doc=lowered,
            detail=compile_spec(lowered),
            report=report,
            artifacts=artifacts,
            pack_id=self.pack_id,
            pack_version=self.version,
            expanded_project_doc=expanded,
            required_base_coverage=("Load-path representation",),
        )
