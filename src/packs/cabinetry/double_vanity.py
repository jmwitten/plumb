"""Analytic, opt-in double-sink vanity design-study pack.

The first increment deliberately separates useful coordination geometry from
fabrication authority.  It models the cabinet, fixture/plumbing/service
envelopes, removable drawers, and wall load path, then blocks release on the
nine project facts that a photograph or generic catalog cannot establish.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re

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
from .artifacts import CabinetArtifacts, CutListItem, WorkStep
from .catalogs import get_wall_anchor_product
from .evidence import EvidenceRecord
from .profiles import get_profile
from .schema import SiteSurvey, _length, _parse_site, _take
from .shell import PartModel, Provenance, params
from .validation import CabinetFinding, CabinetReport


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


@dataclass(frozen=True)
class CatalogAssetRef:
    """Metadata-only external model reference with consumer authority."""

    asset_id: str
    manufacturer: str
    sku: str
    variant: str
    asset_role: str
    authority: str
    source_url: str
    source_page_url: str
    specification_url: str
    source_revision: str
    retrieved_at: str
    media_type: str
    format: str
    byte_length: int
    sha256_raw: str
    source_units: str
    source_frame: tuple[str, str, str, str]
    transform_to_project_mm: tuple[float, ...]
    calibration_anchors: tuple[str, ...]
    terms_url: str
    terms_checked_at: str
    license_class: str
    redistribution: str
    analytic_adapter: str

    def __post_init__(self):
        if self.asset_role not in {
            "visual_reference", "cutout_template", "collision_hint",
            "analytic_seed",
        }:
            raise ValueError(f"unknown catalog asset role {self.asset_role!r}")
        if self.authority not in {"reference_only", "manufacturer_template"}:
            raise ValueError(f"unknown catalog asset authority {self.authority!r}")
        if self.redistribution not in {
            "permitted", "local_only", "prohibited", "unknown",
        }:
            raise ValueError(
                f"unknown catalog asset redistribution {self.redistribution!r}"
            )
        if not _SHA256.fullmatch(self.sha256_raw):
            raise ValueError("sha256_raw must be a lowercase 64-character digest")
        if len(self.transform_to_project_mm) != 16:
            raise ValueError("catalog asset transform must contain 16 values")
        if len(self.source_frame) != 4:
            raise ValueError("catalog asset source frame must contain four fields")
        if len(set(self.calibration_anchors)) < 3:
            raise ValueError("catalog asset requires three calibration anchors")
        if self.byte_length < 0:
            raise ValueError("catalog asset byte length cannot be negative")

    @property
    def may_embed(self) -> bool:
        return self.redistribution == "permitted"

    def allows_consumer(self, consumer: str) -> bool:
        if consumer == "renderer":
            return self.asset_role in {"visual_reference", "collision_hint"}
        if consumer == "cutout_template":
            return (
                self.asset_role == "cutout_template"
                and self.authority == "manufacturer_template"
            )
        return False

    def manifest(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ServiceEnvelope:
    width_mm: float
    depth_mm: float
    height_mm: float


@dataclass(frozen=True)
class SinkFixtureAdapter:
    adapter_id: str
    manufacturer: str
    sku: str
    overall_width_mm: float
    overall_depth_mm: float
    overall_height_mm: float
    bowl_width_mm: float
    bowl_depth_mm: float
    bowl_height_mm: float
    drain_diameter_mm: float
    tailpiece_od_mm: float
    cutout_template_id: str
    specification_url: str


@dataclass(frozen=True)
class WallFaucetAdapter:
    adapter_id: str
    trim_sku: str
    valve_sku: str
    nominal_wall_to_drain_mm: float
    reach_range_mm: tuple[float, float]
    spout_to_rim_range_mm: tuple[float, float]
    specification_urls: tuple[str, str]


@dataclass(frozen=True)
class PlumbingCodeProfile:
    profile_id: str
    jurisdiction: str
    edition: str
    lavatory_side_clearance_mm: float
    lavatory_center_spacing_mm: float
    front_clearance_mm: float
    outlet_to_trap_weir_vertical_max_mm: float
    concealed_access_min_mm: float
    source_url: str


_CODE_PROFILES = {
    "nyc_2022": PlumbingCodeProfile(
        "nyc_2022", "New York City", "2022 Plumbing Code",
        15 * IN, 30 * IN, 21 * IN, 48 * IN, 12 * IN,
        "https://www.nyc.gov/site/buildings/codes/2022-construction-codes.page",
    ),
    "ipc_2024": PlumbingCodeProfile(
        "ipc_2024", "International model code", "2024 IPC",
        15 * IN, 30 * IN, 21 * IN, 24 * IN, 12 * IN,
        "https://codes.iccsafe.org/content/IPC2024P1",
    ),
}


def plumbing_code_profile(profile_id: str) -> PlumbingCodeProfile:
    try:
        return _CODE_PROFILES[profile_id]
    except KeyError:
        raise ProjectSchemaError(
            f"unknown plumbing jurisdiction profile {profile_id!r}; known: "
            f"{sorted(_CODE_PROFILES)}"
        ) from None


K20000 = SinkFixtureAdapter(
    adapter_id="kohler_caxton_k20000@2024-06-10",
    manufacturer="Kohler",
    sku="K-20000",
    overall_width_mm=514.0,
    overall_depth_mm=398.0,
    overall_height_mm=186.0,
    bowl_width_mm=448.0,
    bowl_depth_mm=334.0,
    bowl_height_mm=135.0,
    drain_diameter_mm=44.0,
    tailpiece_od_mm=31.75,
    cutout_template_id="1281904-7",
    specification_url=(
        "https://resources.kohler.com/webassets/kpna/catalog/pdf/en/"
        "K-20000_spec_US-CA_Kohler_en.pdf"
    ),
)

PURIST_WALL = WallFaucetAdapter(
    adapter_id="kohler_purist_t14414_4_k410_k@2026.1",
    trim_sku="K-T14414-4",
    valve_sku="K-410-K",
    nominal_wall_to_drain_mm=229.0,
    reach_range_mm=(8.25 * IN, 9.5 * IN),
    spout_to_rim_range_mm=(1.5 * IN, 6 * IN),
    specification_urls=(
        "https://resources.kohler.com/webassets/kpna/catalog/pdf/en/"
        "K-T14414-4_spec.pdf",
        "https://resources.kohler.com/webassets/kpna/catalog/pdf/en/"
        "K-410-K_spec.pdf",
    ),
)


@dataclass(frozen=True)
class DoubleVanityDecl:
    vanity_id: str
    archetype_id: str
    wall_id: str
    x0_mm: float
    width_mm: float
    body_height_mm: float
    body_depth_mm: float
    countertop_depth_mm: float
    countertop_thickness_mm: float
    bottom_elevation_mm: float


@dataclass(frozen=True)
class DoubleVanitySection:
    mode: str
    profile_id: str
    site: SiteSurvey
    vanity: DoubleVanityDecl
    jurisdiction_id: str
    sink_adapter_id: str
    faucet_adapter_id: str


@dataclass(frozen=True)
class StudyRunner:
    family_id: str
    soft_close: bool
    full_extension: bool
    selected_sku: str
    source_url: str


@dataclass(frozen=True)
class DrawerStudy:
    drawer_id: str
    bay_id: str
    level: str
    kind: str
    box_width_mm: float
    box_depth_mm: float
    box_height_mm: float
    u_void_width_mm: float
    u_void_depth_mm: float
    removable: bool
    runner: StudyRunner
    closed_clearance_mm: float
    full_extension_clearance_mm: float
    removal_clearance_mm: float


@dataclass(frozen=True)
class PlumbingPath:
    path_id: str
    bay_id: str
    trap_count: int
    service_envelope: ServiceEnvelope
    access_min_mm: float
    topology: str = "independent_p_trap_to_wall"


@dataclass(frozen=True)
class SinkBay:
    bay_id: str
    sink_center_x_mm: float
    bay_left_x_mm: float
    bay_right_x_mm: float
    measured_service_opening_width_mm: float


@dataclass(frozen=True)
class DoubleVanityModel:
    project_name: str
    mode: str
    profile: object
    section: DoubleVanitySection
    sink: SinkFixtureAdapter
    faucet: WallFaucetAdapter
    code_profile: PlumbingCodeProfile
    sink_bays: tuple[SinkBay, ...]
    plumbing_paths: tuple[PlumbingPath, ...]
    drawers: tuple[DrawerStudy, ...]
    service_chase_depth_mm: float
    parts: tuple[PartModel, ...]
    machining: tuple
    hardware: tuple
    derived: tuple
    source_map: dict[str, Provenance]
    anchor_stud_ids: tuple[str, ...]
    catalog_assets: tuple[CatalogAssetRef, ...]

    def part(self, role: str) -> PartModel:
        matches = [part for part in self.parts if part.role == role]
        if len(matches) != 1:
            raise KeyError(f"expected one double-vanity part {role!r}")
        return matches[0]

    def drawer(self, bay_id: str, level: str) -> DrawerStudy:
        matches = [
            drawer for drawer in self.drawers
            if drawer.bay_id == bay_id and drawer.level == level
        ]
        if len(matches) != 1:
            raise KeyError(f"expected one {bay_id} {level} drawer")
        return matches[0]

    def catalog_manifest(self) -> dict[str, str]:
        return {
            "sink": self.sink.adapter_id,
            "faucet": self.faucet.adapter_id,
            "drawer_motion": self.drawers[0].runner.family_id,
            "wall_anchor_candidate": "grk_rss_5_16x4@2026.1",
        }

    def catalog_source_manifest(self) -> dict[str, str]:
        return {
            "sink": self.sink.specification_url,
            "faucet_trim": self.faucet.specification_urls[0],
            "faucet_valve": self.faucet.specification_urls[1],
            "drawer_motion": self.drawers[0].runner.source_url,
            "plumbing_code": self.code_profile.source_url,
        }

    def catalog_asset_manifest(self) -> list[dict]:
        return [asset.manifest() for asset in self.catalog_assets]

    def derived_fact_manifest(self) -> dict:
        return {
            "sink_centers_mm": {
                bay.bay_id: bay.sink_center_x_mm for bay in self.sink_bays
            },
            "service_chase_depth_mm": self.service_chase_depth_mm,
            "drawers": {
                drawer.drawer_id: {
                    "kind": drawer.kind,
                    "box_width_mm": drawer.box_width_mm,
                    "box_depth_mm": drawer.box_depth_mm,
                    "u_void_width_mm": drawer.u_void_width_mm,
                    "u_void_depth_mm": drawer.u_void_depth_mm,
                    "runner_selected": bool(drawer.runner.selected_sku),
                }
                for drawer in self.drawers
            },
        }


def parse_double_vanity_project(doc) -> DoubleVanitySection:
    missing = [key for key in ("site", "double_vanity") if key not in doc.sections]
    if missing:
        raise ProjectSchemaError(
            f"vanity.double_sink@1 requires project sections {missing}"
        )
    site = _parse_site(doc.sections["site"], doc.units)
    raw = _take(
        doc.sections["double_vanity"],
        {
            "mode", "archetype", "id", "profile", "placement",
            "jurisdiction", "sink", "faucet",
        },
        set(),
        "double_vanity",
    )
    if raw["mode"] != "study":
        raise ProjectSchemaError("double_vanity.mode v1 must be 'study'")
    if raw["archetype"] != "floating_double_sink_four_drawer@1":
        raise ProjectSchemaError(
            "double_vanity.archetype v1 requires "
            "'floating_double_sink_four_drawer@1'"
        )
    if raw["sink"] != K20000.adapter_id:
        raise ProjectSchemaError(
            f"double_vanity.sink v1 requires {K20000.adapter_id!r}"
        )
    if raw["faucet"] != PURIST_WALL.adapter_id:
        raise ProjectSchemaError(
            f"double_vanity.faucet v1 requires {PURIST_WALL.adapter_id!r}"
        )
    profile = get_profile(str(raw["profile"]))
    placement = _take(
        raw["placement"], {"against", "from_left_datum"}, set(),
        "double_vanity.placement",
    )
    if placement["against"] != site.wall.wall_id:
        raise ProjectSchemaError(
            f"double_vanity.placement.against must name {site.wall.wall_id!r}"
        )
    from_left = _length(
        placement["from_left_datum"], doc.units,
        "double_vanity.placement.from_left_datum",
    )
    width = 72 * IN
    x0 = site.wall.plane_origin_mm[0] + from_left
    if from_left < 0 or from_left + width > site.wall.length_mm:
        raise ProjectSchemaError("DV72 span lies outside the surveyed wall")
    plumbing_code_profile(str(raw["jurisdiction"]))
    vanity_id = str(raw["id"]).strip()
    if not vanity_id:
        raise ProjectSchemaError("double_vanity.id must be non-empty")
    vanity = DoubleVanityDecl(
        vanity_id=vanity_id,
        archetype_id=str(raw["archetype"]),
        wall_id=site.wall.wall_id,
        x0_mm=x0,
        width_mm=width,
        body_height_mm=20 * IN,
        body_depth_mm=21 * IN,
        countertop_depth_mm=22 * IN,
        countertop_thickness_mm=1.5 * IN,
        bottom_elevation_mm=10 * IN,
    )
    return DoubleVanitySection(
        mode="study",
        profile_id=profile.profile_id,
        site=site,
        vanity=vanity,
        jurisdiction_id=str(raw["jurisdiction"]),
        sink_adapter_id=K20000.adapter_id,
        faucet_adapter_id=PURIST_WALL.adapter_id,
    )


def _catalog_assets() -> tuple[CatalogAssetRef, ...]:
    identity = (
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    )
    common = {
        "asset_role": "visual_reference",
        "authority": "reference_only",
        "retrieved_at": "2026-07-14T00:00:00Z",
        "media_type": "application/x-unfetched-reference",
        "format": "unfetched_reference",
        "byte_length": 0,
        "sha256_raw": _EMPTY_SHA256,
        "source_units": "mm",
        "source_frame": (
            "right", "z", "negative_y", "manufacturer-defined; not imported",
        ),
        "transform_to_project_mm": identity,
        "terms_checked_at": "2026-07-14",
        "license_class": "local_project_use_only",
        "redistribution": "prohibited",
    }
    return (
        CatalogAssetRef(
            asset_id="kohler.caxton.k20000.visual",
            manufacturer="Kohler", sku="K-20000", variant="0 white",
            source_url="https://la.kohler.com/en/product-detail/20000?skuid=K-20000-0",
            source_page_url="https://la.kohler.com/en/product-detail/20000",
            specification_url=K20000.specification_url,
            source_revision="2024-06-10",
            calibration_anchors=("drain_center", "overall_left", "overall_front"),
            terms_url="https://la.kohler.com/en/legal-statement",
            analytic_adapter="kohler_k20000_v1",
            **common,
        ),
        CatalogAssetRef(
            asset_id="kohler.purist.t14414.visual",
            manufacturer="Kohler", sku="K-T14414-4 + K-410-K",
            variant="wall-mount candidate",
            source_url="https://la.kohler.com/en/product-detail/T14414-4",
            source_page_url="https://la.kohler.com/en/product-detail/T14414-4",
            specification_url=PURIST_WALL.specification_urls[0],
            source_revision="2026 research snapshot",
            calibration_anchors=("spout_center", "hot_valve", "cold_valve"),
            terms_url="https://la.kohler.com/en/legal-statement",
            analytic_adapter="kohler_t14414_k410_v1",
            **common,
        ),
    )


def build_double_vanity_model(
    section: DoubleVanitySection, *, project_name: str,
) -> DoubleVanityModel:
    profile = get_profile(section.profile_id)
    vanity = section.vanity
    wall = section.site.wall
    code = plumbing_code_profile(section.jurisdiction_id)
    t = profile.carcass_thickness_mm
    wall_y = wall.plane_origin_mm[1]
    front_y = wall_y - vanity.body_depth_mm
    z0 = vanity.bottom_elevation_mm
    bay_width = vanity.width_mm / 2
    service_envelope = ServiceEnvelope(12 * IN, 13 * IN, 12 * IN)
    service_chase_depth = 8 * IN
    drawer_clear_width = bay_width - 2 * t - 42.0
    runner = StudyRunner(
        family_id="blum_movento_sink_drawer_family@study",
        soft_close=True,
        full_extension=True,
        selected_sku="",
        source_url=(
            "https://www.blum.com/us/en/products/cabinet-applications/"
            "sinkunit/overview/"
        ),
    )

    bays: list[SinkBay] = []
    paths: list[PlumbingPath] = []
    drawers: list[DrawerStudy] = []
    for index, bay_id in enumerate(("left", "right")):
        bay_left = vanity.x0_mm + index * bay_width
        bay_right = bay_left + bay_width
        center = (bay_left + bay_right) / 2
        bays.append(SinkBay(
            bay_id, center, bay_left, bay_right, service_envelope.width_mm,
        ))
        paths.append(PlumbingPath(
            f"plumbing.{vanity.vanity_id}.{bay_id}", bay_id, 1,
            service_envelope, code.concealed_access_min_mm,
        ))
        drawers.extend((
            DrawerStudy(
                f"{bay_id}.upper", bay_id, "upper", "upper_u_service",
                drawer_clear_width, 18 * IN, 5 * IN,
                service_envelope.width_mm, service_envelope.depth_mm,
                True, runner, 0.5 * IN, 2 * IN, 2 * IN,
            ),
            DrawerStudy(
                f"{bay_id}.lower", bay_id, "lower", "lower_short_service",
                drawer_clear_width,
                vanity.body_depth_mm - service_chase_depth - IN,
                6 * IN, 0.0, 0.0, True, runner,
                0.5 * IN, 2 * IN, 2 * IN,
            ),
        ))

    parts: list[PartModel] = []
    source_map: dict[str, Provenance] = {}

    def add_panel(
        role: str,
        *,
        length: float,
        width: float,
        thickness: float,
        at: tuple[float, float, float],
        rotate: tuple[tuple[str, float], ...] = (),
        rule: str,
        surface: str = "concealed",
        bands: tuple[str, ...] = (),
    ) -> None:
        part_id = f"double_vanity.{vanity.vanity_id}.{role}"
        parts.append(PartModel(
            part_id, role, f"{vanity.vanity_id} {role.replace('_', ' ')}",
            "plywood_panel", params(length=length, width=width, thickness=thickness),
            at, rotate, length, width, thickness, surface, bands,
        ))
        source_map[part_id] = Provenance(
            declared_at=f"double_vanity.{vanity.vanity_id}", rule=rule,
            pack_version="vanity.double_sink@1.0.0",
            profile_id=profile.profile_id,
            archetype_id=vanity.archetype_id,
        )

    # Floating case: three verticals, two independent bay bottoms, paired front
    # rails, and one continuous rear mounting rail/service datum.
    for role, x in (
        ("left_end", vanity.x0_mm),
        ("center_divider", vanity.x0_mm + bay_width - t / 2),
        ("right_end", vanity.x0_mm + vanity.width_mm - t),
    ):
        add_panel(
            role, length=vanity.body_height_mm, width=vanity.body_depth_mm,
            thickness=t, at=(x, front_y, z0),
            rotate=(("Y", -90.0),), rule="double_vanity.case.vertical",
            surface="exposed_exterior" if role != "center_divider" else "concealed",
            bands=("front",),
        )
    for bay_id, x in (
        ("left", vanity.x0_mm + t),
        ("right", vanity.x0_mm + bay_width + t / 2),
    ):
        add_panel(
            f"bottom_{bay_id}", length=bay_width - 1.5 * t,
            width=vanity.body_depth_mm, thickness=t, at=(x, front_y, z0),
            rule="double_vanity.case.bay_bottom", bands=("front",),
        )
        add_panel(
            f"front_stretcher_{bay_id}", length=bay_width - 1.5 * t,
            width=profile.stretcher_depth_mm, thickness=t,
            at=(x, front_y, z0 + vanity.body_height_mm - t),
            rule="double_vanity.case.front_stretcher",
        )
    add_panel(
        "rear_mounting_rail", length=vanity.width_mm - 2 * t,
        width=6 * IN, thickness=t,
        at=(vanity.x0_mm + t, wall_y, z0 + vanity.body_height_mm - 6 * IN),
        rotate=(("X", 90.0),), rule="double_vanity.mount.continuous_rear_rail",
    )

    front_gap = 2.25
    side_reveal = 1.75
    front_width = bay_width - 2 * side_reveal
    front_height = (vanity.body_height_mm - 2 * side_reveal - front_gap) / 2
    for index, bay_id in enumerate(("left", "right")):
        x = vanity.x0_mm + index * bay_width + side_reveal
        for level, z in (
            ("lower", z0 + side_reveal),
            ("upper", z0 + side_reveal + front_height + front_gap),
        ):
            add_panel(
                f"drawer_front_{bay_id}_{level}", length=front_width,
                width=front_height, thickness=profile.door_thickness_mm,
                at=(x, front_y, z), rotate=(("X", 90.0),),
                rule="double_vanity.front.four_drawer",
                surface="exposed_exterior", bands=("left", "right", "top", "bottom"),
            )

    # Physical removable drawer boxes. Upper boxes are seven-piece U forms;
    # lower boxes are conventional five-piece shallow-depth boxes.
    for index, bay_id in enumerate(("left", "right")):
        bay_left = vanity.x0_mm + index * bay_width + t + 21.0
        upper = next(d for d in drawers if d.bay_id == bay_id and d.level == "upper")
        lower = next(d for d in drawers if d.bay_id == bay_id and d.level == "lower")
        for level, drawer, base_z in (
            ("upper", upper, z0 + vanity.body_height_mm / 2 + 25.0),
            ("lower", lower, z0 + 25.0),
        ):
            side_t = 15.0
            bottom_t = 9.0
            box_front_y = front_y + 22.0
            for side, x in (
                ("left", bay_left),
                ("right", bay_left + drawer.box_width_mm - side_t),
            ):
                add_panel(
                    f"drawer_{bay_id}_{level}_side_{side}",
                    length=drawer.box_depth_mm, width=drawer.box_height_mm,
                    thickness=side_t, at=(x, box_front_y, base_z),
                    rotate=(("X", 90.0), ("Z", 90.0)),
                    rule="double_vanity.drawer.side",
                )
            add_panel(
                f"drawer_{bay_id}_{level}_front",
                length=drawer.box_width_mm - 2 * side_t,
                width=drawer.box_height_mm, thickness=side_t,
                at=(bay_left + side_t, box_front_y, base_z),
                rotate=(("X", 90.0),), rule="double_vanity.drawer.box_front",
            )
            if level == "lower":
                add_panel(
                    f"drawer_{bay_id}_{level}_back",
                    length=drawer.box_width_mm - 2 * side_t,
                    width=drawer.box_height_mm, thickness=side_t,
                    at=(bay_left + side_t, box_front_y + drawer.box_depth_mm - side_t,
                        base_z),
                    rotate=(("X", 90.0),), rule="double_vanity.drawer.box_back",
                )
                add_panel(
                    f"drawer_{bay_id}_{level}_bottom",
                    length=drawer.box_width_mm - 2 * side_t,
                    width=drawer.box_depth_mm - side_t, thickness=bottom_t,
                    at=(bay_left + side_t, box_front_y, base_z),
                    rule="double_vanity.drawer.bottom",
                )
            else:
                wing = (drawer.box_width_mm - 2 * side_t
                        - drawer.u_void_width_mm) / 2
                for side, x in (
                    ("left", bay_left + side_t),
                    ("right", bay_left + side_t + wing + drawer.u_void_width_mm),
                ):
                    add_panel(
                        f"drawer_{bay_id}_{level}_back_{side}",
                        length=wing, width=drawer.box_height_mm, thickness=side_t,
                        at=(x, box_front_y + drawer.box_depth_mm - side_t, base_z),
                        rotate=(("X", 90.0),),
                        rule="double_vanity.drawer.u_back",
                    )
                    add_panel(
                        f"drawer_{bay_id}_{level}_bottom_{side}",
                        length=wing, width=drawer.box_depth_mm - side_t,
                        thickness=bottom_t, at=(x, box_front_y, base_z),
                        rule="double_vanity.drawer.u_bottom_wing",
                    )

    anchor = get_wall_anchor_product("grk_rss_5_16x4@2026.1")
    anchor_studs = tuple(
        stud for stud in wall.studs
        if vanity.x0_mm <= wall.plane_origin_mm[0] + stud.position_mm
        <= vanity.x0_mm + vanity.width_mm
    )
    anchor_z = z0 + vanity.body_height_mm - 3 * IN
    for stud in wall.studs:
        part_id = f"site.{wall.wall_id}.{stud.stud_id}"
        parts.append(PartModel(
            part_id, f"wall_stud_{stud.stud_id}",
            f"{wall.wall_id} {stud.stud_id}", "lumber",
            params(nominal="2x4", length=wall.height_mm),
            (
                wall.plane_origin_mm[0] + stud.position_mm - wall.stud_width_mm / 2,
                wall_y + wall.finish_thickness_mm,
                wall.plane_origin_mm[2],
            ),
            (("Y", -90.0), ("Z", -90.0)), wall.height_mm,
            wall.stud_width_mm, wall.stud_depth_mm, "existing_concealed",
        ))
        source_map[part_id] = Provenance(
            f"site.wall.studs.{stud.stud_id}", "site.surveyed_stud",
            pack_version="vanity.double_sink@1.0.0",
            profile_id=profile.profile_id,
        )
    for stud in anchor_studs:
        role = f"wall_anchor_{stud.stud_id}"
        part_id = f"double_vanity.{vanity.vanity_id}.{role}"
        x = wall.plane_origin_mm[0] + stud.position_mm
        parts.append(PartModel(
            part_id, role, f"{vanity.vanity_id} candidate anchor {stud.stud_id}",
            "structural_screw",
            params(diameter=anchor.diameter_mm, length=anchor.length_mm),
            (x, wall_y - t, anchor_z), (("X", 90.0),),
            anchor.length_mm, anchor.diameter_mm, anchor.diameter_mm, "concealed",
        ))
        source_map[part_id] = Provenance(
            f"site.wall.studs.{stud.stud_id}",
            "double_vanity.mount.candidate_anchor",
            pack_version="vanity.double_sink@1.0.0",
            profile_id=profile.profile_id,
            catalog_id=anchor.product_id,
            archetype_id=vanity.archetype_id,
        )

    return DoubleVanityModel(
        project_name, section.mode, profile, section, K20000, PURIST_WALL, code,
        tuple(bays), tuple(paths), tuple(drawers), service_chase_depth,
        tuple(parts), (), (), (), source_map,
        tuple(stud.stud_id for stud in anchor_studs), _catalog_assets(),
    )


def lower_double_vanity_model(model: DoubleVanityModel) -> DetailSpecDoc:
    vanity = model.section.vanity
    prefix = f"double_vanity.{vanity.vanity_id}."

    def cid(role: str) -> str:
        return prefix + role

    shell_pairs = (
        ("bottom_left", "left_end"),
        ("bottom_left", "center_divider"),
        ("bottom_right", "center_divider"),
        ("bottom_right", "right_end"),
        ("front_stretcher_left", "left_end"),
        ("front_stretcher_left", "center_divider"),
        ("front_stretcher_right", "center_divider"),
        ("front_stretcher_right", "right_end"),
        ("rear_mounting_rail", "left_end"),
        ("rear_mounting_rail", "center_divider"),
        ("rear_mounting_rail", "right_end"),
    )
    bonds = [BondSpec(cid(a), cid(b)) for a, b in shell_pairs]
    contacts = [ContactSpec(item.a, item.b) for item in bonds]
    drawer_parts = [
        part for part in model.parts if part.role.startswith("drawer_")
        and not part.role.startswith("drawer_front_")
    ]
    by_drawer: dict[str, list[str]] = {}
    for part in drawer_parts:
        tokens = part.role.split("_")
        by_drawer.setdefault("_".join(tokens[1:3]), []).append(part.part_id)
    for part_ids in by_drawer.values():
        root = next(item for item in part_ids if item.endswith("_front"))
        bonds.extend(BondSpec(root, item) for item in part_ids if item != root)

    overlaps = []
    for stud_id in model.anchor_stud_ids:
        screw = cid(f"wall_anchor_{stud_id}")
        overlaps.extend((
            OverlapSpec(screw, cid("rear_mounting_rail")),
            OverlapSpec(screw, f"site.{vanity.wall_id}.{stud_id}"),
        ))
    existing_ids = tuple(
        part.part_id for part in model.parts if part.part_id.startswith("site.")
    )
    case_ids = tuple(
        cid(role) for role in (
            "left_end", "center_divider", "right_end", "bottom_left",
            "bottom_right", "front_stretcher_left", "front_stretcher_right",
            "rear_mounting_rail",
        )
    )
    drawer_ids = tuple(part.part_id for part in drawer_parts)
    anchor_ids = tuple(cid(f"wall_anchor_{sid}") for sid in model.anchor_stud_ids)
    return DetailSpecDoc(
        name=model.project_name,
        type="vanity_double_sink_floating_study",
        units="mm",
        components=[ComponentSpec(
            id=part.part_id,
            type=part.component_type,
            name=part.name,
            reader_name=part.name,
            params=part.params_dict(),
            place=RawSpec(at=part.at_mm, rotate=part.rotate),
        ) for part in model.parts],
        validation=ValidationSpec(
            bonds=bonds,
            contacts=contacts,
            expected_overlaps=overlaps,
        ),
        roles={part_id: "existing" for part_id in existing_ids},
        context_grounds=frozenset(existing_ids),
        sequence=SequenceSpec(stages=(
            AuthoredStage(
                "coordinate_case_study",
                "Establish the floating case and continuous rear-rail datum before "
                "evaluating drawers, fixtures, or anchors.",
                parts=case_ids,
            ),
            AuthoredStage(
                "coordinate_removable_drawers",
                "All four removable boxes are modeled before plumbing/service "
                "envelopes can be accepted.",
                parts=drawer_ids,
            ),
            AuthoredStage(
                "coordinate_candidate_mount",
                "Candidate anchors are represented only after the study case is "
                "complete; capacity remains an unresolved project gate.",
                parts=anchor_ids,
            ),
        )),
    )


_RELEASE_GATES = (
    ("double_vanity.release.fixture_template",
     "Confirm the exact K-20000 SKU/revision and current 1281904-7 template digest."),
    ("double_vanity.release.countertop_fabricator",
     "Approve top material/thickness, cutout, reveal, web, clamps, reinforcement, sealant, and sink placement."),
    ("double_vanity.release.faucet",
     "Select the final trim/valve and verify wall build-up, bores, reach, water target, rim gap, and service path."),
    ("double_vanity.release.site_survey",
     "Verify wall/floor datums, span, front clearance, obstructions, studs/backing, rough-ins, and shutoffs."),
    ("double_vanity.release.plumbing_approval",
     "A Licensed Master Plumber must select fittings and confirm waste, vent, supply, access, slope, and jurisdiction compliance."),
    ("double_vanity.release.drawer_derivation",
     "Derive buildable U voids, lower depths, runner SKUs, and clearances from the accepted plumbing/service geometry."),
    ("double_vanity.release.dynamic_access",
     "Prove drawer travel/removal and plumbing assembly, inspection, tool, and service sweeps in both bays."),
    ("double_vanity.release.wall_mount",
     "Provide a project-specific wall-mount/load-path calculation for substrate, rail, joinery, anchors, loads, and tolerances."),
    ("double_vanity.release.commissioning",
     "Record leak, fixture, drawer, anchor, loading, and service-access commissioning after installation."),
)


def validate_double_vanity_model(model: DoubleVanityModel) -> CabinetReport:
    findings: list[CabinetFinding] = []
    evidence: list[EvidenceRecord] = []

    def add(rule: str, verdict: str, severity: str, message: str, level: str,
            *, source: str = "", affected: tuple[str, ...] = ()):
        evidence_id = f"evidence:{rule}"
        evidence.append(EvidenceRecord(
            evidence_id, rule, level, message, source=source,
        ))
        findings.append(CabinetFinding(
            rule, verdict, severity, message, level, (evidence_id,), affected,
        ))

    vanity = model.section.vanity
    add(
        "double_vanity.geometry.two_bays", "PASS", "required",
        f"The {vanity.width_mm:.1f} mm study splits into two equal "
        f"{vanity.width_mm / 2:.1f} mm service bays with two fixture centers.",
        "derived",
    )
    topology_ok = (
        len(model.plumbing_paths) == 2
        and len({path.path_id for path in model.plumbing_paths}) == 2
        and all(path.trap_count == 1 for path in model.plumbing_paths)
        and all(path.topology == "independent_p_trap_to_wall"
                for path in model.plumbing_paths)
    )
    add(
        "double_vanity.plumbing.independent_traps",
        "PASS" if topology_ok else "FAIL", "required",
        "Two independent, singly trapped P-trap-to-wall analytic paths are "
        "represented; no S-trap or double-trap topology is emitted."
        if topology_ok else "The two-bay trap topology is not independent.",
        "derived",
    )
    centers = [bay.sink_center_x_mm for bay in model.sink_bays]
    spacing = centers[1] - centers[0]
    left_offset = centers[0] - vanity.x0_mm
    right_offset = vanity.x0_mm + vanity.width_mm - centers[1]
    placement_ok = (
        spacing >= model.code_profile.lavatory_center_spacing_mm
        and left_offset >= model.code_profile.lavatory_side_clearance_mm
        and right_offset >= model.code_profile.lavatory_side_clearance_mm
    )
    add(
        "double_vanity.code.fixture_spacing",
        "PASS" if placement_ok else "FAIL", "required",
        f"Study centers provide {spacing:.1f} mm center spacing and "
        f"{left_offset:.1f}/{right_offset:.1f} mm side offsets under "
        f"{model.code_profile.profile_id}; room-front clearance remains gated.",
        "calculated", source=model.code_profile.source_url,
    )
    service_ok = all(
        bay.measured_service_opening_width_mm >= path.access_min_mm
        for bay, path in zip(model.sink_bays, model.plumbing_paths)
    )
    add(
        "double_vanity.geometry.service_openings",
        "PASS" if service_ok else "FAIL", "required",
        "Both modeled drawer-removal openings meet the selected profile's "
        "provisional 12 in minimum dimension; final fitting/tool access remains gated.",
        "calculated", source=model.code_profile.source_url,
    )
    add(
        "double_vanity.mount.representation", "PASS", "required",
        "A continuous rear rail, surveyed wall studs, and candidate fastener axes "
        "represent the load path; representation does not establish capacity.",
        "derived",
    )
    for rule, message in _RELEASE_GATES:
        sources = {
            "double_vanity.release.fixture_template": model.sink.specification_url,
            "double_vanity.release.faucet": " | ".join(model.faucet.specification_urls),
            "double_vanity.release.plumbing_approval": model.code_profile.source_url,
            "double_vanity.release.drawer_derivation": model.drawers[0].runner.source_url,
        }
        add(rule, "UNKNOWN", "required", message, "unknown",
            source=sources.get(rule, ""))
    return CabinetReport(
        mode=model.mode,
        findings=tuple(sorted(findings, key=lambda item: item.rule)),
        evidence=tuple(sorted(evidence, key=lambda item: item.evidence_id)),
    )


def build_double_vanity_artifacts(
    model: DoubleVanityModel, report: CabinetReport,
) -> CabinetArtifacts:
    fabricated = tuple(
        part for part in model.parts if part.component_type == "plywood_panel"
    )
    cut_list = tuple(CutListItem(
        part_id=part.part_id,
        role=part.role,
        description=part.name,
        quantity=1,
        length_mm=part.length_mm,
        width_mm=part.width_mm,
        thickness_mm=part.thickness_mm,
        material="study plywood; product, finish, grain, and nesting unresolved",
        surface_class=part.surface_class,
        source_rule=model.source_map[part.part_id].rule,
    ) for part in sorted(fabricated, key=lambda item: item.part_id))
    return CabinetArtifacts(
        schema="detailgen/double-vanity-study-artifacts/v1",
        project=model.project_name,
        pack="vanity.double_sink@1.0.0",
        profile=model.profile.profile_id,
        mode=model.mode,
        release_ready=False,
        cut_list=cut_list,
        edge_banding=(),
        hardware_schedule=(),
        machining_schedule=(),
        fabrication_steps=(WorkStep(
            10, "study.no_fabrication",
            "DESIGN STUDY ONLY — do not purchase, cut, drill, fabricate, or install "
            "from these provisional dimensions while any release gate is UNKNOWN.",
            evidence="unknown",
        ),),
        assembly_steps=(
            WorkStep(
                10, "study.coordinate_fixtures",
                "Coordinate both K-20000 templates, final top, wall faucet rough-ins, "
                "and the fabricator-approved water targets.",
                evidence="unknown",
            ),
            WorkStep(
                20, "study.coordinate_drawers",
                "Coordinate each U drawer and shortened lower drawer against its "
                "own accepted trap, supply, hand/tool, removal, and service sweeps.",
                evidence="unknown",
            ),
        ),
        installation_steps=(WorkStep(
            10, "install.release_gate",
            "INSTALLATION HOLD — all nine required fixture, top, faucet, site, "
            "plumbing, drawer, dynamic-access, wall-mount, and commissioning gates "
            "must be resolved by the responsible trades and reviewers.",
            evidence="unknown",
        ),),
    )


class DoubleSinkVanityPack:
    pack_id = "vanity.double_sink"
    major_version = 1
    version = "1.0.0"
    section_keys = ("site", "double_vanity")

    def parse(self, doc) -> DoubleVanitySection:
        return parse_double_vanity_project(doc)

    def compile(self, doc):
        section = self.parse(doc)
        model = build_double_vanity_model(section, project_name=doc.name)
        lowered = lower_double_vanity_model(model)
        report = validate_double_vanity_model(model)
        artifacts = build_double_vanity_artifacts(model, report)
        detail = compile_spec(lowered)
        return PackedProject(
            project_doc=doc,
            model=model,
            lowered_doc=lowered,
            detail=detail,
            report=report,
            artifacts=artifacts,
            pack_id=self.pack_id,
            pack_version=self.version,
            expanded_project_doc=doc,
        )

