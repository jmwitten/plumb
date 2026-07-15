"""Analytic, opt-in double-sink vanity design-study pack.

The first increment deliberately separates useful coordination geometry from
fabrication authority.  It models the cabinet, fixture/plumbing/service
envelopes, removable drawers, and wall load path, then blocks release on the
nine project facts that a photograph or generic catalog cannot establish.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
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
from .schema import SiteSurvey, _length, _list, _parse_site, _take
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

    @property
    def may_use_locally(self) -> bool:
        return (
            self.redistribution != "unknown"
            and self.license_class in {
                "local_project_use_only", "permissive", "manufacturer_project_use",
            }
        )

    def allows_consumer(self, consumer: str) -> bool:
        if consumer == "local_preview_renderer":
            return (
                self.may_use_locally
                and self.byte_length > 0
                and self.sha256_raw != _EMPTY_SHA256
                and self.asset_role in {"visual_reference", "collision_hint"}
            )
        if consumer in {
            "renderer", "publish_renderer", "self_contained_renderer",
        }:
            return (
                self.may_embed
                and self.asset_role in {"visual_reference", "collision_hint"}
            )
        if consumer == "cutout_template":
            return (
                self.asset_role == "cutout_template"
                and self.authority == "manufacturer_template"
                and self.may_use_locally
                and self.byte_length > 0
                and self.sha256_raw != _EMPTY_SHA256
            )
        return False

    def manifest(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AnalyticEnvelope:
    """Axis-aligned, project-frame study geometry with explicit authority."""

    envelope_id: str
    bay_id: str
    kind: str
    x0_mm: float
    y0_mm: float
    z0_mm: float
    x1_mm: float
    y1_mm: float
    z1_mm: float
    authority: str = "provisional_study_target"

    def __post_init__(self):
        if not (
            self.x1_mm > self.x0_mm
            and self.y1_mm > self.y0_mm
            and self.z1_mm > self.z0_mm
        ):
            raise ValueError(
                f"analytic envelope {self.envelope_id!r} must have positive bounds"
            )

    @property
    def width_mm(self) -> float:
        return self.x1_mm - self.x0_mm

    @property
    def depth_mm(self) -> float:
        return self.y1_mm - self.y0_mm

    @property
    def height_mm(self) -> float:
        return self.z1_mm - self.z0_mm

    def intersects_z(self, z0_mm: float, z1_mm: float) -> bool:
        return min(self.z1_mm, z1_mm) > max(self.z0_mm, z0_mm)

    def touches_or_intersects(self, other: "AnalyticEnvelope") -> bool:
        return (
            min(self.x1_mm, other.x1_mm) >= max(self.x0_mm, other.x0_mm)
            and min(self.y1_mm, other.y1_mm) >= max(self.y0_mm, other.y0_mm)
            and min(self.z1_mm, other.z1_mm) >= max(self.z0_mm, other.z0_mm)
        )

    def within_xy(
        self, x0_mm: float, x1_mm: float, y0_mm: float, y1_mm: float,
    ) -> bool:
        return (
            self.x0_mm >= x0_mm
            and self.x1_mm <= x1_mm
            and self.y0_mm >= y0_mm
            and self.y1_mm <= y1_mm
        )

    def contains(self, other: "AnalyticEnvelope") -> bool:
        return (
            other.x0_mm >= self.x0_mm
            and other.y0_mm >= self.y0_mm
            and other.z0_mm >= self.z0_mm
            and other.x1_mm <= self.x1_mm
            and other.y1_mm <= self.y1_mm
            and other.z1_mm <= self.z1_mm
        )


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
class DrainProduct:
    adapter_id: str
    manufacturer: str
    sku: str
    with_overflow: bool
    connection_od_mm: float
    body_height_mm: float
    specification_url: str


@dataclass(frozen=True)
class TrapProduct:
    adapter_id: str
    manufacturer: str
    sku: str
    inlet_od_mm: float
    outlet_od_mm: float
    overall_length_mm: float
    overall_height_mm: float
    slip_joint: bool
    cleanout: bool
    specification_url: str


@dataclass(frozen=True)
class MountReference:
    adapter_id: str
    manufacturer: str
    sku: str
    width_mm: float
    depth_mm: float
    static_capacity_lb: float
    capacity_basis: str
    required_screws_per_bracket: int
    maximum_spacing_mm: float
    authority: str
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
    trap_source_url: str


_CODE_PROFILES = {
    "nyc_2022": PlumbingCodeProfile(
        "nyc_2022", "New York City", "2022 Plumbing Code",
        15 * IN, 30 * IN, 21 * IN, 48 * IN, 12 * IN,
        "https://www.nyc.gov/assets/buildings/codes-pdf/cons_codes_2022/"
        "2022PC_Chapter4_FixturesWBwm.pdf",
        "https://www.nyc.gov/assets/buildings/codes-pdf/cons_codes_2022/"
        "2022PC_Chapter10_TrapsWBwm.pdf",
    ),
    "ipc_2024": PlumbingCodeProfile(
        "ipc_2024", "International model code", "2024 IPC",
        15 * IN, 30 * IN, 21 * IN, 24 * IN, 12 * IN,
        "https://codes.iccsafe.org/content/IPC2024V2.0/"
        "chapter-4-fixtures-faucets-and-fixture-fittings",
        "https://codes.iccsafe.org/s/IPC2024P1/"
        "chapter-10-traps-interceptors-and-separators/"
        "IPC2024P1-Ch10-Sec1002.1",
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

K7124_A = DrainProduct(
    "kohler_k7124_a@2018-09-28", "Kohler", "K-7124-A", True,
    1.25 * IN, 130.0,
    "https://resources.kohler.com/onlinecatalog/pdf/K-7124-A_spec.pdf",
)

K8998 = TrapProduct(
    "kohler_k8998@2026-07-14", "Kohler", "K-8998",
    1.25 * IN, 1.25 * IN, 298.0, 111.0, True, True,
    "https://la.kohler.com/en/product-detail/8998?skuid=K-8998-CP",
)

_REQUIRED_PRODUCT_IDS = {
    "sink": "kohler_caxton_k20000@2024-06-10",
    "drain": "kohler_k7124_a@2018-09-28",
    "trap": "kohler_k8998@2026-07-14",
}

_REQUIRED_RUNNERS = {
    "upper": ("blum_movento_763_4570s@2026.1", "763.4570S"),
    "lower": ("blum_movento_763_3050s@2026.1", "763.3050S"),
}

RAKKS_EH_1818_LV = MountReference(
    "rakks_eh_1818_lv@2022.1.0", "Rakks", "EH-1818-LV",
    18 * IN, 21.5 * IN, 450.0, "evenly_distributed_static_load",
    4, 48 * IN, "comparative_reference_only",
    "https://www.rakks.com/install/support-hardware/"
    "Rakks_EH_Vanity_Support_Bracket_2022.1.0.pdf",
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
class CountertopStudy:
    material: str
    structural_thickness_mm: float
    visual_edge_height_mm: float
    cutout_template_id: str
    stone_cut_authority: str


@dataclass(frozen=True)
class ConditionalRelease:
    fabrication_status: str
    installation_status: str
    trade_status: str
    commissioning_status: str


@dataclass(frozen=True)
class RoughInPoint:
    point_id: str
    kind: str
    x_mm: float
    y_mm: float
    z_mm: float
    provenance: str


@dataclass(frozen=True)
class AssumedSiteBasis:
    provenance: str
    field_verified: bool
    wall_length_mm: float
    wall_height_mm: float
    vanity_left_mm: float
    floor_elevation_mm: float
    finish_thickness_mm: float
    backing: str
    wastes: tuple[RoughInPoint, ...]
    supplies: tuple[RoughInPoint, ...]


@dataclass(frozen=True)
class DoubleVanitySection:
    mode: str
    profile_id: str
    site: SiteSurvey
    assumed_site: AssumedSiteBasis
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
    minimum_drawer_length_mm: float | None
    minimum_inside_depth_mm: float | None


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
    closed_clearance_mm: float | None
    full_extension_clearance_mm: float | None
    removal_clearance_mm: float | None
    dynamic_verified: bool


@dataclass(frozen=True)
class PlumbingPath:
    path_id: str
    bay_id: str
    trap_count: int
    fixture_envelope: AnalyticEnvelope
    elements: tuple[AnalyticEnvelope, ...]
    service_envelope: AnalyticEnvelope
    access_min_mm: float
    topology: str = "independent_p_trap_to_wall"

    def element(self, kind: str) -> AnalyticEnvelope:
        matches = [element for element in self.elements if element.kind == kind]
        if len(matches) != 1:
            raise KeyError(f"expected one plumbing element {kind!r}")
        return matches[0]


@dataclass(frozen=True)
class SinkBay:
    bay_id: str
    sink_center_x_mm: float
    bay_left_x_mm: float
    bay_right_x_mm: float
    clear_opening_width_mm: float
    clear_opening_height_mm: float

    @property
    def service_opening_smallest_mm(self) -> float:
        return min(self.clear_opening_width_mm, self.clear_opening_height_mm)


@dataclass(frozen=True)
class DoubleVanityModel:
    project_name: str
    mode: str
    profile: object
    section: DoubleVanitySection
    assumed_site: AssumedSiteBasis
    sink: SinkFixtureAdapter
    drain: DrainProduct
    trap: TrapProduct
    faucet: WallFaucetAdapter
    mount_reference: MountReference
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
    countertop: CountertopStudy
    release: ConditionalRelease

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
            "drain": self.drain.adapter_id,
            "trap": self.trap.adapter_id,
            "faucet": self.faucet.adapter_id,
            "upper_drawer_motion": self.drawer("left", "upper").runner.family_id,
            "lower_drawer_motion": self.drawer("left", "lower").runner.family_id,
            "wall_anchor_candidate": "grk_rss_5_16x4@2026.1",
            "comparative_mount": self.mount_reference.adapter_id,
        }

    def catalog_source_manifest(self) -> dict[str, str]:
        return {
            "sink": self.sink.specification_url,
            "drain": self.drain.specification_url,
            "trap": self.trap.specification_url,
            "faucet_trim": self.faucet.specification_urls[0],
            "faucet_valve": self.faucet.specification_urls[1],
            "upper_drawer_motion": self.drawer("left", "upper").runner.source_url,
            "lower_drawer_motion": self.drawer("left", "lower").runner.source_url,
            "plumbing_code": self.code_profile.source_url,
            "plumbing_traps": self.code_profile.trap_source_url,
            "comparative_mount": self.mount_reference.specification_url,
        }

    def catalog_asset_manifest(self) -> list[dict]:
        return [asset.manifest() for asset in self.catalog_assets]

    def derived_fact_manifest(self) -> dict:
        return {
            "sink_centers_mm": {
                bay.bay_id: bay.sink_center_x_mm for bay in self.sink_bays
            },
            "service_chase_depth_mm": self.service_chase_depth_mm,
            "drain": {
                "sku": self.drain.sku,
                "connection_od_mm": self.drain.connection_od_mm,
                "body_height_mm": self.drain.body_height_mm,
            },
            "trap": {
                "sku": self.trap.sku,
                "overall_length_mm": self.trap.overall_length_mm,
                "overall_height_mm": self.trap.overall_height_mm,
                "cleanout": self.trap.cleanout,
            },
            "comparative_mount": {
                "sku": self.mount_reference.sku,
                "static_capacity_lb": self.mount_reference.static_capacity_lb,
                "capacity_basis": self.mount_reference.capacity_basis,
                "authority": self.mount_reference.authority,
            },
            "plumbing_paths": {
                path.path_id: {
                    "bay_id": path.bay_id,
                    "fixture_bounds_mm": (
                        path.fixture_envelope.x0_mm,
                        path.fixture_envelope.y0_mm,
                        path.fixture_envelope.z0_mm,
                        path.fixture_envelope.x1_mm,
                        path.fixture_envelope.y1_mm,
                        path.fixture_envelope.z1_mm,
                    ),
                    "service_bounds_mm": (
                        path.service_envelope.x0_mm,
                        path.service_envelope.y0_mm,
                        path.service_envelope.z0_mm,
                        path.service_envelope.x1_mm,
                        path.service_envelope.y1_mm,
                        path.service_envelope.z1_mm,
                    ),
                    "elements": tuple(
                        (element.kind, element.x0_mm, element.y0_mm,
                         element.z0_mm, element.x1_mm, element.y1_mm,
                         element.z1_mm)
                        for element in path.elements
                    ),
                }
                for path in self.plumbing_paths
            },
            "drawers": {
                drawer.drawer_id: {
                    "kind": drawer.kind,
                    "box_width_mm": drawer.box_width_mm,
                    "box_depth_mm": drawer.box_depth_mm,
                    "u_void_width_mm": drawer.u_void_width_mm,
                    "u_void_depth_mm": drawer.u_void_depth_mm,
                    "runner_family": drawer.runner.family_id,
                    "runner_selected": bool(drawer.runner.selected_sku),
                }
                for drawer in self.drawers
            },
        }


def _rough_ins_by_bay(
    basis: AssumedSiteBasis,
) -> dict[str, dict[str, RoughInPoint]] | None:
    points = basis.wastes + basis.supplies
    if len({point.point_id for point in points}) != len(points):
        return None
    owned: dict[str, dict[str, RoughInPoint]] = {}
    used_ids: set[str] = set()
    for bay_id in ("left", "right"):
        owned[bay_id] = {}
        for kind in ("waste", "hot_supply", "cold_supply"):
            matches = [
                point for point in points
                if point.point_id.startswith(f"{bay_id}_")
                and point.kind == kind
            ]
            if len(matches) != 1:
                return None
            owned[bay_id][kind] = matches[0]
            used_ids.add(matches[0].point_id)
    return owned if len(used_ids) == len(points) else None


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
            "jurisdiction", "sink", "faucet", "assumed_conditions",
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
    assumed_raw = _take(
        raw["assumed_conditions"],
        {
            "provenance", "field_verified", "wall_length", "wall_height",
            "vanity_left", "floor_elevation", "finish_thickness", "backing",
            "wastes", "supplies",
        },
        set(),
        "double_vanity.assumed_conditions",
    )
    if assumed_raw["provenance"] != "owner_assumed":
        raise ProjectSchemaError(
            "double_vanity.assumed_conditions.provenance must be "
            "'owner_assumed'"
        )
    if not isinstance(assumed_raw["field_verified"], bool):
        raise ProjectSchemaError(
            "double_vanity.assumed_conditions.field_verified must be a boolean"
        )
    if assumed_raw["field_verified"]:
        raise ProjectSchemaError(
            "double_vanity.assumed_conditions.field_verified must be false"
        )

    def rough_ins(key: str) -> tuple[RoughInPoint, ...]:
        points = []
        for index, item in enumerate(_list(
            assumed_raw[key], f"double_vanity.assumed_conditions.{key}",
        )):
            ctx = f"double_vanity.assumed_conditions.{key}[{index}]"
            point = _take(
                item, {"id", "kind", "x", "y", "z", "provenance"}, set(), ctx,
            )
            if point["provenance"] != "owner_assumed":
                raise ProjectSchemaError(f"{ctx}.provenance must be 'owner_assumed'")
            point_id = str(point["id"]).strip()
            kind = str(point["kind"]).strip()
            if not point_id or not kind:
                raise ProjectSchemaError(f"{ctx}.id and kind must be non-empty")
            points.append(RoughInPoint(
                point_id=point_id,
                kind=kind,
                x_mm=_length(point["x"], doc.units, f"{ctx}.x"),
                y_mm=_length(point["y"], doc.units, f"{ctx}.y"),
                z_mm=_length(point["z"], doc.units, f"{ctx}.z"),
                provenance="owner_assumed",
            ))
        return tuple(points)

    backing = str(assumed_raw["backing"]).strip()
    if not backing:
        raise ProjectSchemaError(
            "double_vanity.assumed_conditions.backing must be non-empty"
        )
    assumed_site = AssumedSiteBasis(
        provenance="owner_assumed",
        field_verified=False,
        wall_length_mm=_length(
            assumed_raw["wall_length"], doc.units,
            "double_vanity.assumed_conditions.wall_length", positive=True,
        ),
        wall_height_mm=_length(
            assumed_raw["wall_height"], doc.units,
            "double_vanity.assumed_conditions.wall_height", positive=True,
        ),
        vanity_left_mm=_length(
            assumed_raw["vanity_left"], doc.units,
            "double_vanity.assumed_conditions.vanity_left",
        ),
        floor_elevation_mm=_length(
            assumed_raw["floor_elevation"], doc.units,
            "double_vanity.assumed_conditions.floor_elevation",
        ),
        finish_thickness_mm=_length(
            assumed_raw["finish_thickness"], doc.units,
            "double_vanity.assumed_conditions.finish_thickness", positive=True,
        ),
        backing=backing,
        wastes=rough_ins("wastes"),
        supplies=rough_ins("supplies"),
    )
    declared_geometry = (
        ("wall_length", assumed_site.wall_length_mm, site.wall.length_mm,
         "site.wall.length"),
        ("wall_height", assumed_site.wall_height_mm, site.wall.height_mm,
         "site.wall.height"),
        ("finish_thickness", assumed_site.finish_thickness_mm,
         site.wall.finish_thickness_mm, "site.wall.finish_thickness"),
        ("floor_elevation", assumed_site.floor_elevation_mm,
         site.floor.high_point_elevation_mm, "site.floor.high_point_elevation"),
        ("vanity_left", assumed_site.vanity_left_mm, from_left,
         "double_vanity.placement.from_left_datum"),
    )
    for key, assumed_value, declared_value, declared_at in declared_geometry:
        if abs(assumed_value - declared_value) > 1e-6:
            raise ProjectSchemaError(
                f"double_vanity.assumed_conditions.{key} must match "
                f"{declared_at}"
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
        body_height_mm=34.5 * IN - 11 * IN - 30.0,
        body_depth_mm=21 * IN,
        countertop_depth_mm=22 * IN,
        countertop_thickness_mm=30.0,
        bottom_elevation_mm=11 * IN,
    )
    return DoubleVanitySection(
        mode="study",
        profile_id=profile.profile_id,
        site=site,
        assumed_site=assumed_site,
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
    drawer_clear_width = bay_width - 2 * t - 42.0
    drawer_side_t = 15.0
    box_front_y = front_y + 22.0
    upper_depth = 18 * IN
    upper_height = 5 * IN
    lower_height = 6 * IN
    upper_base_z = z0 + vanity.body_height_mm / 2 + 25.0
    lower_base_z = z0 + 25.0
    study_clearance = 0.5 * IN
    sink_center_y = wall_y - PURIST_WALL.nominal_wall_to_drain_mm
    countertop_underside_z = z0 + vanity.body_height_mm
    upper_runner = StudyRunner(
        family_id="blum_movento_763_4570s@2026.1",
        soft_close=True,
        full_extension=True,
        selected_sku="763.4570S",
        source_url=(
            "https://d2.blum.com/services/BEC003/"
            "movento_ep_dok_bus_%24sen-us_%24aof_%24v7.pdf"
        ),
        minimum_drawer_length_mm=457.0,
        minimum_inside_depth_mm=477.0,
    )
    lower_runner = StudyRunner(
        family_id="blum_movento_763_3050s@2026.1",
        soft_close=True,
        full_extension=True,
        selected_sku="763.3050S",
        source_url=(
            "https://d2.blum.com/services/BEC003/"
            "movento_ep_dok_bus_%24sen-us_%24aof_%24v7.pdf"
        ),
        minimum_drawer_length_mm=305.0,
        minimum_inside_depth_mm=325.0,
    )
    rough_ins_by_bay = _rough_ins_by_bay(section.assumed_site)
    if rough_ins_by_bay is None:
        raise ProjectSchemaError(
            "assumed waste and hot/cold rough-ins require one owner per bay"
        )

    bays: list[SinkBay] = []
    paths: list[PlumbingPath] = []
    drawers: list[DrawerStudy] = []
    chase_depths: list[float] = []
    for index, bay_id in enumerate(("left", "right")):
        bay_left = vanity.x0_mm + index * bay_width
        bay_right = bay_left + bay_width
        center = (bay_left + bay_right) / 2
        clear_opening_width = bay_width - 1.5 * t
        clear_opening_height = vanity.body_height_mm - 2 * t
        bays.append(SinkBay(
            bay_id, center, bay_left, bay_right,
            clear_opening_width, clear_opening_height,
        ))

        def envelope(
            kind: str,
            x0_: float,
            y0_: float,
            z0_: float,
            x1_: float,
            y1_: float,
            z1_: float,
            *,
            authority: str = "provisional_study_target",
        ) -> AnalyticEnvelope:
            return AnalyticEnvelope(
                f"{vanity.vanity_id}.{bay_id}.{kind}", bay_id, kind,
                x0_, y0_, z0_, x1_, y1_, z1_, authority,
            )

        fixture = envelope(
            "fixture_body",
            center - K20000.overall_width_mm / 2,
            sink_center_y - K20000.overall_depth_mm / 2,
            countertop_underside_z - K20000.overall_height_mm,
            center + K20000.overall_width_mm / 2,
            sink_center_y + K20000.overall_depth_mm / 2,
            countertop_underside_z,
            authority="manufacturer_dimensions_provisional_placement",
        )
        bay_rough_ins = rough_ins_by_bay[bay_id]
        waste = bay_rough_ins["waste"]
        supplies_by_kind = {
            kind: bay_rough_ins[kind]
            for kind in ("hot_supply", "cold_supply")
        }
        tailpiece_radius = K7124_A.connection_od_mm / 2
        tailpiece = envelope(
            "tailpiece", center - tailpiece_radius,
            sink_center_y - tailpiece_radius,
            fixture.z0_mm - K7124_A.body_height_mm,
            center + tailpiece_radius,
            sink_center_y + tailpiece_radius,
            fixture.z0_mm,
            authority="manufacturer_product_bounding_envelope_vertical",
        )
        trap_service_allowance = study_clearance if K8998.cleanout else 0.0
        trap_half_width = max(K8998.inlet_od_mm, K8998.outlet_od_mm) / 2
        p_trap = envelope(
            "p_trap",
            center - trap_half_width - trap_service_allowance,
            waste.y_mm - K8998.overall_length_mm,
            waste.z_mm - K8998.outlet_od_mm / 2,
            center + trap_half_width + trap_service_allowance,
            waste.y_mm,
            waste.z_mm - K8998.outlet_od_mm / 2 + K8998.overall_height_mm,
            authority=(
                "manufacturer_gross_bounding_envelope_oriented_to_waste_"
                "with_cleanout_service_allowance"
            ),
        )
        trap_arm_radius = K8998.outlet_od_mm / 2
        trap_arm = envelope(
            "trap_arm", waste.x_mm - trap_arm_radius,
            waste.y_mm - trap_arm_radius,
            waste.z_mm - trap_arm_radius,
            waste.x_mm + trap_arm_radius, waste.y_mm,
            waste.z_mm + trap_arm_radius,
            authority="owner_assumed_waste_connection_bounding_envelope",
        )

        def supply_envelopes(kind: str) -> tuple[AnalyticEnvelope, AnalyticEnvelope]:
            point = supplies_by_kind[kind]
            radius = 15.0
            supply = envelope(
                kind, point.x_mm - radius, point.y_mm - 80.0,
                point.z_mm - radius, point.x_mm + radius, point.y_mm,
                point.z_mm + radius,
                authority="owner_assumed_supply_path_bounding_envelope",
            )
            shutoff = envelope(
                kind.replace("supply", "shutoff"),
                point.x_mm - 35.0, point.y_mm - 125.0,
                point.z_mm - 35.0, point.x_mm + 35.0,
                point.y_mm - 55.0, point.z_mm + 35.0,
                authority="unproved_shutoff_service_bounding_envelope",
            )
            return supply, shutoff

        hot_supply, hot_shutoff = supply_envelopes("hot_supply")
        cold_supply, cold_shutoff = supply_envelopes("cold_supply")
        elements = (
            fixture, tailpiece, p_trap, trap_arm, hot_supply, cold_supply,
            hot_shutoff, cold_shutoff,
        )

        upper_z1 = upper_base_z + upper_height
        upper_obstacles = tuple(
            item for item in elements
            if item.intersects_z(upper_base_z, upper_z1)
        )
        if not upper_obstacles:
            raise ProjectSchemaError(
                f"{bay_id} sink study has no obstacle geometry at upper drawer"
            )
        obstacle_x0 = min(item.x0_mm for item in upper_obstacles)
        obstacle_x1 = max(item.x1_mm for item in upper_obstacles)
        obstacle_y0 = min(item.y0_mm for item in upper_obstacles)
        upper_box_rear = box_front_y + upper_depth
        service = envelope(
            "service_access",
            obstacle_x0 - study_clearance,
            obstacle_y0 - study_clearance,
            min(item.z0_mm for item in elements) - study_clearance,
            obstacle_x1 + study_clearance,
            wall_y,
            max(item.z1_mm for item in elements) + study_clearance,
        )
        u_width = service.width_mm
        u_depth = upper_box_rear - service.y0_mm
        interior_width = drawer_clear_width - 2 * drawer_side_t
        wing = (interior_width - u_width) / 2
        bridge_depth = upper_depth - u_depth
        if wing <= drawer_side_t or bridge_depth <= drawer_side_t:
            raise ProjectSchemaError(
                f"{bay_id} fixture/plumbing envelope cannot form a positive "
                "U-drawer within the 36 in study bay"
            )

        lower_z1 = lower_base_z + lower_height
        lower_obstacles = tuple(
            item for item in elements
            if item.intersects_z(lower_base_z, lower_z1)
        )
        lower_available_depth = (
            min(item.y0_mm for item in lower_obstacles) - box_front_y
            - study_clearance
            if lower_obstacles else
            vanity.body_depth_mm - 22.0 - study_clearance
        )
        lower_depth = lower_runner.minimum_drawer_length_mm
        assert lower_depth is not None
        if lower_depth > lower_available_depth:
            raise ProjectSchemaError(
                f"{bay_id} plumbing envelope cannot fit the selected lower runner"
            )
        chase_depths.append(vanity.body_depth_mm - 22.0 - lower_depth)

        paths.append(PlumbingPath(
            f"plumbing.{vanity.vanity_id}.{bay_id}", bay_id, 1,
            fixture, elements, service, code.concealed_access_min_mm,
        ))
        drawers.extend((
            DrawerStudy(
                f"{bay_id}.upper", bay_id, "upper", "upper_u_service",
                drawer_clear_width, upper_depth, upper_height,
                u_width, u_depth, True, upper_runner,
                study_clearance, None, None, False,
            ),
            DrawerStudy(
                f"{bay_id}.lower", bay_id, "lower", "lower_short_service",
                drawer_clear_width, lower_depth, lower_height,
                0.0, 0.0, True, lower_runner,
                study_clearance, None, None, False,
            ),
        ))

    service_chase_depth = max(chase_depths)

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

    # Physical removable drawer boxes. Each upper box expresses the derived
    # void with two bottom wings, a front bridge, and two inner return walls;
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
                void_left_x = bay_left + side_t + wing
                bridge_depth = drawer.box_depth_mm - drawer.u_void_depth_mm
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
                add_panel(
                    f"drawer_{bay_id}_{level}_bottom_bridge",
                    length=drawer.u_void_width_mm, width=bridge_depth,
                    thickness=bottom_t,
                    at=(void_left_x, box_front_y, base_z),
                    rule="double_vanity.drawer.u_bottom_bridge",
                )
                for side, x in (
                    ("left", void_left_x - side_t),
                    ("right", void_left_x + drawer.u_void_width_mm),
                ):
                    add_panel(
                        f"drawer_{bay_id}_{level}_inner_return_{side}",
                        length=drawer.u_void_depth_mm,
                        width=drawer.box_height_mm,
                        thickness=side_t,
                        at=(x, box_front_y + bridge_depth, base_z),
                        rotate=(("X", 90.0), ("Z", 90.0)),
                        rule="double_vanity.drawer.u_inner_return",
                    )

    anchor = get_wall_anchor_product("grk_rss_5_16x4@2026.1")
    rail_x0 = vanity.x0_mm + t
    rail_x1 = vanity.x0_mm + vanity.width_mm - t
    anchor_studs = tuple(
        stud for stud in wall.studs
        if rail_x0 <= wall.plane_origin_mm[0] + stud.position_mm <= rail_x1
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
            f"site.wall.studs.{stud.stud_id}", "site.owner_assumed_stud",
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
        project_name, section.mode, profile, section, section.assumed_site,
        K20000, K7124_A, K8998,
        PURIST_WALL, RAKKS_EH_1818_LV, code,
        tuple(bays), tuple(paths), tuple(drawers), service_chase_depth,
        tuple(parts), (), (), (), source_map,
        tuple(stud.stud_id for stud in anchor_studs), _catalog_assets(),
        CountertopStudy(
            material="stone selected by countertop fabricator",
            structural_thickness_mm=30.0,
            visual_edge_height_mm=38.0,
            cutout_template_id=K20000.cutout_template_id,
            stone_cut_authority=(
                "WITHHELD_UNTIL_FABRICATOR_ACCEPTS_K-20000_TEMPLATE"
            ),
        ),
        ConditionalRelease(
            fabrication_status="CONDITIONAL_FABRICATION_RELEASE",
            installation_status="HOLD_FIELD_VERIFY",
            trade_status="HOLD_RESPONSIBLE_TRADE_APPROVAL",
            commissioning_status="HOLD_COMMISSIONING",
        ),
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
    # The study records intended joinery connectivity but does not claim a
    # released bearing-face/contact detail. Several simplified panel solids
    # deliberately intersect at their future joint zone; name only those
    # intersections so the base sweep can distinguish them from a collision.
    contacts: list[ContactSpec] = []
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

    intentional_intersections = (
        ("center_divider", "bottom_left"),
        ("center_divider", "front_stretcher_left"),
        ("center_divider", "rear_mounting_rail"),
        ("right_end", "bottom_right"),
        ("right_end", "front_stretcher_right"),
        ("right_end", "rear_mounting_rail"),
        ("drawer_left_upper_back_left", "drawer_left_upper_bottom_left"),
        ("drawer_left_upper_back_left", "drawer_left_upper_inner_return_left"),
        ("drawer_left_upper_back_right", "drawer_left_upper_bottom_right"),
        ("drawer_left_upper_back_right", "drawer_left_upper_inner_return_right"),
        ("drawer_left_upper_bottom_left", "drawer_left_upper_inner_return_left"),
        ("drawer_left_upper_bottom_right", "drawer_left_upper_inner_return_right"),
        ("drawer_left_lower_back", "drawer_left_lower_bottom"),
        ("drawer_right_upper_back_left", "drawer_right_upper_bottom_left"),
        ("drawer_right_upper_back_left", "drawer_right_upper_inner_return_left"),
        ("drawer_right_upper_back_right", "drawer_right_upper_bottom_right"),
        ("drawer_right_upper_back_right", "drawer_right_upper_inner_return_right"),
        ("drawer_right_upper_bottom_left", "drawer_right_upper_inner_return_left"),
        ("drawer_right_upper_bottom_right", "drawer_right_upper_inner_return_right"),
        ("drawer_right_lower_back", "drawer_right_lower_bottom"),
    )
    overlaps = [OverlapSpec(cid(a), cid(b))
                for a, b in intentional_intersections]
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


_REQUIRED_PATH_KINDS = frozenset({
    "fixture_body", "tailpiece", "p_trap", "trap_arm",
    "hot_supply", "cold_supply", "hot_shutoff", "cold_shutoff",
})


def _path_is_complete_and_connected(
    path: PlumbingPath,
    bay: SinkBay,
    *,
    front_y_mm: float,
    wall_y_mm: float,
) -> bool:
    kinds = [element.kind for element in path.elements]
    if (
        set(kinds) != _REQUIRED_PATH_KINDS
        or len(kinds) != len(_REQUIRED_PATH_KINDS)
        or len({element.envelope_id for element in path.elements}) != len(kinds)
    ):
        return False
    by_kind = {element.kind: element for element in path.elements}
    if by_kind["fixture_body"] != path.fixture_envelope:
        return False
    if not all(
        element.bay_id == path.bay_id
        and element.within_xy(
            bay.bay_left_x_mm, bay.bay_right_x_mm, front_y_mm, wall_y_mm,
        )
        for element in path.elements
    ):
        return False
    if not path.service_envelope.within_xy(
        bay.bay_left_x_mm, bay.bay_right_x_mm, front_y_mm, wall_y_mm,
    ):
        return False
    if not all(
        path.service_envelope.contains(element) for element in path.elements
    ):
        return False
    fixture_center_x = (
        path.fixture_envelope.x0_mm + path.fixture_envelope.x1_mm
    ) / 2
    if abs(fixture_center_x - bay.sink_center_x_mm) > 1e-6:
        return False
    required_adjacencies = (
        ("fixture_body", "tailpiece"),
        ("tailpiece", "p_trap"),
        ("p_trap", "trap_arm"),
        ("hot_supply", "hot_shutoff"),
        ("cold_supply", "cold_shutoff"),
    )
    if not all(
        by_kind[left].touches_or_intersects(by_kind[right])
        for left, right in required_adjacencies
    ):
        return False
    return abs(by_kind["trap_arm"].y1_mm - wall_y_mm) <= 1e-6


def _physical_upper_void_bounds(
    model: DoubleVanityModel, bay_id: str,
) -> tuple[float, float, float, float, float, float] | None:
    try:
        bridge = model.part(f"drawer_{bay_id}_upper_bottom_bridge")
        left = model.part(f"drawer_{bay_id}_upper_inner_return_left")
        right = model.part(f"drawer_{bay_id}_upper_inner_return_right")
        back_left = model.part(f"drawer_{bay_id}_upper_back_left")
        back_right = model.part(f"drawer_{bay_id}_upper_back_right")
    except KeyError:
        return None
    x0 = left.at_mm[0] + left.thickness_mm
    x1 = right.at_mm[0]
    y0 = left.at_mm[1]
    y1 = left.at_mm[1] + left.length_mm
    z0 = left.at_mm[2]
    z1 = left.at_mm[2] + left.width_mm
    coherent = (
        x1 > x0
        and y1 > y0
        and abs(right.at_mm[1] - y0) <= 1e-6
        and abs(right.length_mm - left.length_mm) <= 1e-6
        and abs(bridge.at_mm[0] - x0) <= 1e-6
        and abs(bridge.length_mm - (x1 - x0)) <= 1e-6
        and abs(bridge.at_mm[1] + bridge.width_mm - y0) <= 1e-6
        and abs(back_left.at_mm[1] + back_left.thickness_mm - y1) <= 1e-6
        and abs(back_right.at_mm[1] + back_right.thickness_mm - y1) <= 1e-6
    )
    return (x0, y0, z0, x1, y1, z1) if coherent else None


def _physical_lower_box_bounds(
    model: DoubleVanityModel, bay_id: str,
) -> tuple[float, float, float] | None:
    try:
        left = model.part(f"drawer_{bay_id}_lower_side_left")
        right = model.part(f"drawer_{bay_id}_lower_side_right")
        front = model.part(f"drawer_{bay_id}_lower_front")
        back = model.part(f"drawer_{bay_id}_lower_back")
        bottom = model.part(f"drawer_{bay_id}_lower_bottom")
    except KeyError:
        return None
    front_y = left.at_mm[1]
    rear_y = front_y + left.length_mm
    max_rear_y = max(
        left.at_mm[1] + left.length_mm,
        right.at_mm[1] + right.length_mm,
        front.at_mm[1] + front.thickness_mm,
        back.at_mm[1] + back.thickness_mm,
        bottom.at_mm[1] + bottom.width_mm,
    )
    coherent = (
        abs(right.at_mm[1] - front_y) <= 1e-6
        and abs(right.length_mm - left.length_mm) <= 1e-6
        and abs(front.at_mm[1] - front_y) <= 1e-6
        and abs(bottom.at_mm[1] - front_y) <= 1e-6
        and abs(back.at_mm[1] + back.thickness_mm - rear_y) <= 1e-6
        and abs(bottom.at_mm[1] + bottom.width_mm - back.at_mm[1]) <= 1e-6
        and abs(front.at_mm[0] - (left.at_mm[0] + left.thickness_mm)) <= 1e-6
        and abs(front.at_mm[0] + front.length_mm - right.at_mm[0]) <= 1e-6
        and abs(bottom.at_mm[0] - front.at_mm[0]) <= 1e-6
        and abs(bottom.length_mm - front.length_mm) <= 1e-6
        and abs(back.at_mm[0] - front.at_mm[0]) <= 1e-6
        and abs(back.length_mm - front.length_mm) <= 1e-6
        and abs(max_rear_y - rear_y) <= 1e-6
    )
    if not coherent:
        return None
    return (left.at_mm[2], left.at_mm[2] + left.width_mm, rear_y)


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
    wall_y = model.section.site.wall.plane_origin_mm[1]
    front_y = wall_y - vanity.body_depth_mm
    bays_by_id = {bay.bay_id: bay for bay in model.sink_bays}
    add(
        "double_vanity.geometry.two_bays", "PASS", "required",
        f"The {vanity.width_mm:.1f} mm study splits into two equal "
        f"{vanity.width_mm / 2:.1f} mm service bays with two fixture centers.",
        "derived",
    )
    topology_ok = (
        len(model.plumbing_paths) == 2
        and len({path.path_id for path in model.plumbing_paths}) == 2
        and {path.bay_id for path in model.plumbing_paths} == {"left", "right"}
        and all(path.trap_count == 1 for path in model.plumbing_paths)
        and all(path.topology == "independent_p_trap_to_wall"
                for path in model.plumbing_paths)
        and all(
            _path_is_complete_and_connected(
                path, bays_by_id[path.bay_id],
                front_y_mm=front_y, wall_y_mm=wall_y,
            )
            for path in model.plumbing_paths
        )
        and not model.plumbing_paths[0].service_envelope.touches_or_intersects(
            model.plumbing_paths[1].service_envelope
        )
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
        bay.bay_id == path.bay_id
        and bay.service_opening_smallest_mm >= path.access_min_mm
        for bay, path in zip(model.sink_bays, model.plumbing_paths)
    )
    opening_summary = ", ".join(
        f"{bay.bay_id} {bay.clear_opening_width_mm:.1f} x "
        f"{bay.clear_opening_height_mm:.1f} mm "
        f"(smallest {bay.service_opening_smallest_mm:.1f} mm)"
        for bay in model.sink_bays
    )
    add(
        "double_vanity.geometry.service_openings",
        "PASS" if service_ok else "FAIL", "required",
        f"Drawer-removed case openings derive from the shell: {opening_summary}. "
        "The static smallest dimension meets the selected profile; actual "
        "fitting/tool paths remain gated.",
        "calculated", source=model.code_profile.source_url,
    )

    tolerance = 1e-6
    product_authority_complete = all((
        model.sink.adapter_id,
        model.sink.specification_url,
        model.drain.adapter_id,
        model.drain.specification_url,
        model.trap.adapter_id,
        model.trap.specification_url,
    ))
    required_product_ids_match = (
        model.sink.adapter_id in {"", _REQUIRED_PRODUCT_IDS["sink"]}
        and model.drain.adapter_id in {"", _REQUIRED_PRODUCT_IDS["drain"]}
        and model.trap.adapter_id in {"", _REQUIRED_PRODUCT_IDS["trap"]}
    )
    connections_agree = (
        abs(model.sink.tailpiece_od_mm - model.drain.connection_od_mm)
        <= tolerance
        and abs(model.drain.connection_od_mm - model.trap.inlet_od_mm)
        <= tolerance
    )
    rough_ins_by_bay = _rough_ins_by_bay(model.assumed_site)
    product_geometry_ok = (
        topology_ok
        and connections_agree
        and required_product_ids_match
        and rough_ins_by_bay is not None
    )
    for path in model.plumbing_paths:
        if path.bay_id not in bays_by_id:
            product_geometry_ok = False
            continue
        bay = bays_by_id[path.bay_id]
        if rough_ins_by_bay is None:
            product_geometry_ok = False
            continue
        bay_rough_ins = rough_ins_by_bay[path.bay_id]
        waste = bay_rough_ins["waste"]
        supplies_by_kind = {
            kind: bay_rough_ins[kind]
            for kind in ("hot_supply", "cold_supply")
        }
        try:
            fixture = path.element("fixture_body")
            tailpiece = path.element("tailpiece")
            p_trap = path.element("p_trap")
            trap_arm = path.element("trap_arm")
            supplies_by_kind_and_path = {
                kind: path.element(kind)
                for kind in ("hot_supply", "cold_supply")
            }
        except KeyError:
            product_geometry_ok = False
            continue
        trap_service_allowance = (
            model.drawer(path.bay_id, "upper").closed_clearance_mm
            if model.trap.cleanout else 0.0
        )
        if trap_service_allowance is None:
            product_authority_complete = False
            trap_service_allowance = 0.0
        expected_trap_width = (
            max(model.trap.inlet_od_mm, model.trap.outlet_od_mm)
            + 2 * trap_service_allowance
        )

        def contains_point(
            item: AnalyticEnvelope, point: RoughInPoint,
        ) -> bool:
            return (
                item.x0_mm - tolerance <= point.x_mm <= item.x1_mm + tolerance
                and item.y0_mm - tolerance <= point.y_mm <= item.y1_mm + tolerance
                and item.z0_mm - tolerance <= point.z_mm <= item.z1_mm + tolerance
            )

        drain_outlet = (
            (tailpiece.x0_mm + tailpiece.x1_mm) / 2,
            (tailpiece.y0_mm + tailpiece.y1_mm) / 2,
            tailpiece.z0_mm,
        )
        fixture_drain_center = (
            (fixture.x0_mm + fixture.x1_mm) / 2,
            (fixture.y0_mm + fixture.y1_mm) / 2,
        )
        outlet_reaches_trap = (
            abs(drain_outlet[0] - fixture_drain_center[0]) <= tolerance
            and abs(drain_outlet[1] - fixture_drain_center[1]) <= tolerance
            and p_trap.x0_mm - tolerance <= drain_outlet[0]
            <= p_trap.x1_mm + tolerance
            and p_trap.y0_mm - tolerance <= drain_outlet[1]
            <= p_trap.y1_mm + tolerance
            and p_trap.z0_mm - tolerance <= drain_outlet[2]
            <= p_trap.z1_mm + tolerance
        )

        path_products_match = (
            fixture == path.fixture_envelope
            and abs(fixture.width_mm - model.sink.overall_width_mm) <= tolerance
            and abs(fixture.depth_mm - model.sink.overall_depth_mm) <= tolerance
            and abs(fixture.height_mm - model.sink.overall_height_mm) <= tolerance
            and fixture.authority
            == "manufacturer_dimensions_provisional_placement"
            and abs(tailpiece.width_mm - model.drain.connection_od_mm)
            <= tolerance
            and abs(tailpiece.depth_mm - model.drain.connection_od_mm)
            <= tolerance
            and abs(tailpiece.height_mm - model.drain.body_height_mm)
            <= tolerance
            and tailpiece.authority
            == "manufacturer_product_bounding_envelope_vertical"
            and abs(p_trap.width_mm - expected_trap_width) <= tolerance
            and abs(p_trap.depth_mm - model.trap.overall_length_mm)
            <= tolerance
            and abs(p_trap.height_mm - model.trap.overall_height_mm)
            <= tolerance
            and p_trap.authority
            == (
                "manufacturer_gross_bounding_envelope_oriented_to_waste_"
                "with_cleanout_service_allowance"
            )
            and abs(p_trap.y1_mm - waste.y_mm) <= tolerance
            and outlet_reaches_trap
            and contains_point(trap_arm, waste)
            and p_trap.contains(trap_arm)
            and all(
                contains_point(supplies_by_kind_and_path[kind], supplies_by_kind[kind])
                for kind in ("hot_supply", "cold_supply")
            )
        )
        product_geometry_ok = product_geometry_ok and path_products_match
        drawer = model.drawer(path.bay_id, "upper")
        void = _physical_upper_void_bounds(model, path.bay_id)
        if void is None:
            product_geometry_ok = False
            continue
        x0, y0, z0_, x1, y1, z1_ = void
        service = path.service_envelope
        upper_obstacles = tuple(
            element for element in path.elements
            if element.intersects_z(z0_, z1_)
        )
        physical_matches = (
            abs((x1 - x0) - drawer.u_void_width_mm) <= 1e-6
            and abs((y1 - y0) - drawer.u_void_depth_mm) <= 1e-6
            and abs(service.x0_mm - x0) <= 1e-6
            and abs(service.x1_mm - x1) <= 1e-6
            and abs(service.y0_mm - y0) <= 1e-6
            and service.y1_mm >= y1
            and upper_obstacles
            and all(
                obstacle.x0_mm > x0
                and obstacle.x1_mm < x1
                and obstacle.y0_mm > y0
                for obstacle in upper_obstacles
            )
        )
        lower_bounds = _physical_lower_box_bounds(model, path.bay_id)
        if lower_bounds is None:
            physical_matches = False
        else:
            lower = model.drawer(path.bay_id, "lower")
            lower_z0, lower_top, lower_rear = lower_bounds
            lower_obstacles = tuple(
                element for element in path.elements
                if element.intersects_z(lower_z0, lower_top)
            )
            physical_matches = physical_matches and (
                abs(
                    lower_rear
                    - model.part(
                        f"drawer_{path.bay_id}_lower_side_left"
                    ).at_mm[1]
                    - lower.box_depth_mm
                ) <= 1e-6
                and all(
                    obstacle.y0_mm > lower_rear
                    for obstacle in lower_obstacles
                )
            )
        product_geometry_ok = product_geometry_ok and physical_matches

    runners_authoritative = True
    runners_fit = True
    for drawer in model.drawers:
        runner = drawer.runner
        if not all((
            runner.family_id,
            runner.selected_sku,
            runner.source_url,
        )) or (
            runner.minimum_drawer_length_mm is None
            or runner.minimum_inside_depth_mm is None
        ):
            runners_authoritative = False
            continue
        if (
            (runner.family_id, runner.selected_sku)
            != _REQUIRED_RUNNERS[drawer.level]
        ):
            runners_fit = False
            continue
        try:
            drawer_front_y = model.part(
                f"drawer_{drawer.bay_id}_{drawer.level}_side_left"
            ).at_mm[1]
        except KeyError:
            runners_fit = False
            continue
        usable_inside_depth = wall_y - drawer_front_y
        if (
            drawer.box_depth_mm + tolerance < runner.minimum_drawer_length_mm
            or usable_inside_depth + tolerance
            < runner.minimum_inside_depth_mm
        ):
            runners_fit = False
    product_authority_complete = (
        product_authority_complete and runners_authoritative
    )
    coordination_ok = product_geometry_ok and runners_fit
    coordination_verdict = (
        "FAIL" if not coordination_ok else
        "PASS" if product_authority_complete else
        "UNKNOWN"
    )
    add(
        "double_vanity.geometry.fixture_plumbing_drawer",
        coordination_verdict, "required",
        "Selected product IDs and dimensions drive the fixture, vertical drain, "
        "oriented gross trap bounding envelopes, 1/2-inch cleanout allowance, "
        "assumed rough-in endpoints, physical drawer clearances, and fitting "
        "runner SKUs. Exact fitting shape, field rough-in, tool access, and "
        "dynamic removal remain explicitly unproved release holds."
        if coordination_verdict == "PASS" else
        "Fixture, plumbing, service, runner, and drawer study geometry agree, "
        "but one or more product authority fields are missing."
        if coordination_verdict == "UNKNOWN" else
        "Fixture, plumbing, service, runner, and drawer study geometry contradict "
        "the selected products or assumed rough-ins.",
        "calculated" if coordination_verdict != "UNKNOWN" else "unknown",
    )

    incompatible_runners = []
    unknown_runners = []
    for drawer in model.drawers:
        runner = drawer.runner
        if (
            runner.family_id.startswith("unselected_")
            or runner.minimum_drawer_length_mm is None
            or runner.minimum_inside_depth_mm is None
        ):
            unknown_runners.append(drawer.drawer_id)
            continue
        if (
            (runner.family_id, runner.selected_sku)
            != _REQUIRED_RUNNERS[drawer.level]
        ):
            incompatible_runners.append(drawer.drawer_id)
            continue
        try:
            drawer_front_y = model.part(
                f"drawer_{drawer.bay_id}_{drawer.level}_side_left"
            ).at_mm[1]
        except KeyError:
            incompatible_runners.append(drawer.drawer_id)
            continue
        usable_inside_depth = wall_y - drawer_front_y
        if (
            drawer.box_depth_mm < runner.minimum_drawer_length_mm
            or usable_inside_depth < runner.minimum_inside_depth_mm
        ):
            incompatible_runners.append(drawer.drawer_id)
    runner_verdict = (
        "FAIL" if incompatible_runners else
        "UNKNOWN" if unknown_runners else "PASS"
    )
    add(
        "double_vanity.drawer.runner_applicability",
        runner_verdict, "advisory",
        f"Incompatible runner studies: {incompatible_runners}; unselected "
        f"runner families: {unknown_runners}. The selected 18-inch and 12-inch "
        "MOVENTO full-extension soft-close runners fit the modeled upper and "
        "lower drawer depths; dynamic travel and removal remain gated.",
        "calculated" if runner_verdict != "UNKNOWN" else "unknown",
        source=model.drawer("left", "upper").runner.source_url,
    )

    rail_parts = [part for part in model.parts if part.role == "rear_mounting_rail"]
    anchor_parts = {
        part.role.removeprefix("wall_anchor_"): part
        for part in model.parts if part.role.startswith("wall_anchor_")
    }
    site_parts = {
        part.role.removeprefix("wall_stud_"): part
        for part in model.parts if part.role.startswith("wall_stud_")
    }
    surveyed = {stud.stud_id: stud for stud in model.section.site.wall.studs}
    mount_ok = len(rail_parts) == 1
    if mount_ok:
        rail = rail_parts[0]
        rail_x0 = rail.at_mm[0]
        rail_x1 = rail_x0 + rail.length_mm
        rail_z0 = rail.at_mm[2]
        rail_z1 = rail_z0 + rail.width_mm
        wall = model.section.site.wall
        expected_targets = {
            stud.stud_id
            for stud in wall.studs
            if rail_x0 <= wall.plane_origin_mm[0] + stud.position_mm <= rail_x1
        }
        target_axes = sorted(
            wall.plane_origin_mm[0] + surveyed[stud_id].position_mm
            for stud_id in expected_targets
        )
        mount_ok = (
            len(expected_targets) >= 2
            and set(model.anchor_stud_ids) == expected_targets
            and set(anchor_parts) == expected_targets
            and expected_targets <= set(site_parts)
            and target_axes[0] - rail_x0 <= 16 * IN
            and rail_x1 - target_axes[-1] <= 16 * IN
            and all(
            rail_x0 <= anchor_parts[stud_id].at_mm[0] <= rail_x1
            and rail_z0 <= anchor_parts[stud_id].at_mm[2] <= rail_z1
            and abs(anchor_parts[stud_id].at_mm[0]
                    - site_parts[stud_id].at_mm[0]
                    - model.section.site.wall.stud_width_mm / 2) <= 1e-6
            and anchor_parts[stud_id].at_mm[1] <= wall.plane_origin_mm[1]
            and (
                anchor_parts[stud_id].at_mm[1]
                + anchor_parts[stud_id].length_mm
                >= wall.plane_origin_mm[1] + wall.finish_thickness_mm
            )
                for stud_id in expected_targets
            )
        )
    add(
        "double_vanity.mount.representation",
        "PASS" if mount_ok else "FAIL", "required",
        "A continuous rear rail, study-declared stud axes, and candidate fastener "
        "axes share X coordinates and represent a proposed load path; this does "
        "not establish a field survey or capacity."
        if mount_ok else
        "The rail, study-declared studs, and candidate fastener axes do not form a "
        "complete represented load path.",
        "derived",
    )
    for rule, message in _RELEASE_GATES:
        sources = {
            "double_vanity.release.fixture_template": model.sink.specification_url,
            "double_vanity.release.faucet": " | ".join(model.faucet.specification_urls),
            "double_vanity.release.plumbing_approval": (
                f"{model.code_profile.source_url} | "
                f"{model.code_profile.trap_source_url}"
            ),
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
    drawer_cut_authority = all(
        report.by_rule(rule).verdict == "PASS"
        for rule in (
            "double_vanity.geometry.fixture_plumbing_drawer",
            "double_vanity.drawer.runner_applicability",
        )
    )
    fabricated = tuple(
        part for part in model.parts
        if part.component_type == "plywood_panel"
        and part.role != "countertop"
        and (
            drawer_cut_authority
            or not part.role.startswith("drawer_")
        )
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
        report = validate_double_vanity_model(model)
        drawer_cut_authority = all(
            report.by_rule(rule).verdict == "PASS"
            for rule in (
                "double_vanity.geometry.fixture_plumbing_drawer",
                "double_vanity.drawer.runner_applicability",
            )
        )
        if not drawer_cut_authority:
            model = replace(
                model,
                release=replace(
                    model.release,
                    fabrication_status="HOLD_PRODUCT_GEOMETRY",
                ),
            )
        lowered = lower_double_vanity_model(model)
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
