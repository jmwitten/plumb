"""Strict authoring schema for ``cabinetry.frameless@1``."""

from __future__ import annotations

import difflib
import math
from dataclasses import dataclass

from ...core.units import IN
from ...spec.values import Resolver, UNIT_FACTORS
from ..project import ProjectDoc, ProjectSchemaError
from .profiles import get_profile

_MISSING = object()


def _mapping(value, ctx: str) -> dict:
    if not isinstance(value, dict):
        raise ProjectSchemaError(f"{ctx} must be a mapping, got {type(value).__name__}")
    return value


def _take(raw, required: set[str], optional: set[str], ctx: str) -> dict:
    raw = _mapping(raw, ctx)
    allowed = required | optional
    for key in raw:
        if key in allowed:
            continue
        suggestion = difflib.get_close_matches(str(key), sorted(allowed), n=1)
        hint = f"; did you mean {suggestion[0]!r}?" if suggestion else ""
        raise ProjectSchemaError(
            f"{ctx}: unknown key {key!r}; allowed keys: {sorted(allowed)}{hint}"
        )
    missing = sorted(required - raw.keys())
    if missing:
        raise ProjectSchemaError(f"{ctx}: missing required keys {missing}")
    return {key: raw.get(key, _MISSING) for key in allowed}


def _list(value, ctx: str) -> list:
    if not isinstance(value, list):
        raise ProjectSchemaError(f"{ctx} must be a list, got {type(value).__name__}")
    return value


def _length(value, units: str, ctx: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise ProjectSchemaError(f"{ctx} must be a length, got boolean {value!r}")
    if isinstance(value, (int, float)):
        resolved = float(value) * UNIT_FACTORS[units]
    elif isinstance(value, str):
        resolved = Resolver({}, UNIT_FACTORS[units]).resolve(value)
        if isinstance(resolved, str) or isinstance(resolved, bool):
            raise ProjectSchemaError(
                f"{ctx} must be a length (number in project units or explicit "
                f"'mm'/'in'/'ft' quantity), got {value!r}"
            )
        resolved = float(resolved)
    else:
        raise ProjectSchemaError(
            f"{ctx} must be a length, got {type(value).__name__} {value!r}"
        )
    if not math.isfinite(resolved):
        raise ProjectSchemaError(f"{ctx} must be finite, got {value!r}")
    if positive and resolved <= 0:
        raise ProjectSchemaError(f"{ctx} must be greater than zero, got {value!r}")
    return resolved


def _finite_number(value, ctx: str, *, positive: bool = False,
                   non_negative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProjectSchemaError(f"{ctx} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ProjectSchemaError(f"{ctx} must be finite, got {value!r}")
    if positive and number <= 0:
        raise ProjectSchemaError(f"{ctx} must be positive")
    if non_negative and number < 0:
        raise ProjectSchemaError(f"{ctx} must be non-negative")
    return number


def _vector3(value, units: str, ctx: str, *, lengths: bool) -> tuple[float, float, float]:
    items = _list(value, ctx)
    if len(items) != 3:
        raise ProjectSchemaError(f"{ctx} must contain exactly three coordinates")
    if lengths:
        return tuple(_length(item, units, f"{ctx}[{i}]")
                     for i, item in enumerate(items))
    return tuple(_finite_number(item, f"{ctx}[{i}]")
                 for i, item in enumerate(items))


@dataclass(frozen=True)
class StudSurvey:
    stud_id: str
    position_mm: float
    verified: bool


@dataclass(frozen=True)
class StudWallSurvey:
    wall_id: str
    plane_origin_mm: tuple[float, float, float]
    plane_normal: tuple[float, float, float]
    length_mm: float
    height_mm: float
    finish_thickness_mm: float
    stud_width_mm: float
    stud_depth_mm: float
    studs: tuple[StudSurvey, ...]


@dataclass(frozen=True)
class FloorSurvey:
    high_point_elevation_mm: float
    verified: bool


@dataclass(frozen=True)
class SiteEnvironment:
    building_enclosed: bool
    wet_work_complete: bool
    hvac_operating: bool
    acclimation_hours: float


@dataclass(frozen=True)
class SiteSurvey:
    wall: StudWallSurvey
    floor: FloorSurvey
    environment: SiteEnvironment


@dataclass(frozen=True)
class MaterialEvidence:
    tsca_title_vi: str
    reference: str
    product: str
    density_kg_m3: float
    modulus_elasticity_mpa: float
    property_reference: str


@dataclass(frozen=True)
class BaseCabinetDecl:
    cabinet_id: str
    kind: str
    width_mm: float
    height_mm: float
    depth_mm: float
    toe_kick_height_mm: float
    toe_kick_setback_mm: float
    wall_id: str
    from_left_datum_mm: float
    door_count: int
    adjustable_shelf_count: int
    design_load_psf: float
    left_end: str
    right_end: str
    countertop_type: str
    countertop_support: str
    source_archetype: str = ""


@dataclass(frozen=True)
class CabinetrySection:
    mode: str
    profile_id: str
    material_evidence: MaterialEvidence
    site: SiteSurvey
    cabinets: tuple[BaseCabinetDecl, ...]


def _parse_wall(raw, units: str) -> StudWallSurvey:
    f = _take(
        raw,
        {"id", "type", "plane", "length", "height", "finish_thickness", "studs"},
        {"stud_width", "stud_depth"},
        "site.wall",
    )
    if f["type"] != "stud_wall":
        raise ProjectSchemaError(
            f"site.wall.type: cabinetry v1 requires 'stud_wall', got {f['type']!r}"
        )
    wall_id = str(f["id"]).strip()
    if not wall_id:
        raise ProjectSchemaError("site.wall.id must be non-empty")
    length = _length(f["length"], units, "site.wall.length", positive=True)
    plane = _take(f["plane"], {"origin", "normal"}, set(), "site.wall.plane")
    plane_origin = _vector3(
        plane["origin"], units, "site.wall.plane.origin", lengths=True
    )
    plane_normal = _vector3(
        plane["normal"], units, "site.wall.plane.normal", lengths=False
    )
    if plane_normal != (0.0, -1.0, 0.0):
        raise ProjectSchemaError(
            "site.wall.plane.normal: cabinetry v1 requires [0, -1, 0] "
            "(wall run +X, cabinet projection -Y, elevation +Z)"
        )
    studs: list[StudSurvey] = []
    seen: set[str] = set()
    for i, raw_stud in enumerate(_list(f["studs"], "site.wall.studs")):
        sf = _take(raw_stud, {"id", "position", "verified"}, set(),
                   f"site.wall.studs[{i}]")
        stud_id = str(sf["id"]).strip()
        if not stud_id:
            raise ProjectSchemaError(f"site.wall.studs[{i}].id must be non-empty")
        if stud_id in seen:
            raise ProjectSchemaError(f"duplicate stud id {stud_id!r}")
        seen.add(stud_id)
        position = _length(sf["position"], units,
                           f"site.wall.studs[{i}].position")
        if not 0 <= position <= length:
            raise ProjectSchemaError(
                f"site.wall.studs[{i}].position lies outside the wall length"
            )
        if not isinstance(sf["verified"], bool):
            raise ProjectSchemaError(
                f"site.wall.studs[{i}].verified must be true or false"
            )
        studs.append(StudSurvey(stud_id, position, sf["verified"]))
    if not studs:
        raise ProjectSchemaError("site.wall.studs must identify at least one stud")
    stud_width = (1.5 * IN if f["stud_width"] is _MISSING else _length(
        f["stud_width"], units, "site.wall.stud_width", positive=True
    ))
    stud_depth = (3.5 * IN if f["stud_depth"] is _MISSING else _length(
        f["stud_depth"], units, "site.wall.stud_depth", positive=True
    ))
    if not (math.isclose(stud_width, 1.5 * IN, abs_tol=1e-6)
            and math.isclose(stud_depth, 3.5 * IN, abs_tol=1e-6)):
        raise ProjectSchemaError(
            "site.wall: cabinetry v1 lowers only nominal 2x4 studs "
            "(1.5 in x 3.5 in actual); custom stud geometry is unsupported"
        )
    return StudWallSurvey(
        wall_id=wall_id,
        plane_origin_mm=plane_origin,
        plane_normal=plane_normal,
        length_mm=length,
        height_mm=_length(f["height"], units, "site.wall.height", positive=True),
        finish_thickness_mm=_length(
            f["finish_thickness"], units, "site.wall.finish_thickness", positive=True
        ),
        stud_width_mm=stud_width,
        stud_depth_mm=stud_depth,
        studs=tuple(studs),
    )


def _parse_site(raw, units: str) -> SiteSurvey:
    f = _take(raw, {"wall", "floor", "environment"}, set(), "site")
    ff = _take(f["floor"], {"high_point_elevation", "verified"}, set(), "site.floor")
    if not isinstance(ff["verified"], bool):
        raise ProjectSchemaError("site.floor.verified must be true or false")
    ef = _take(
        f["environment"],
        {"building_enclosed", "wet_work_complete", "hvac_operating",
         "acclimation_hours"},
        set(),
        "site.environment",
    )
    for key in ("building_enclosed", "wet_work_complete", "hvac_operating"):
        if not isinstance(ef[key], bool):
            raise ProjectSchemaError(f"site.environment.{key} must be true or false")
    hours = _finite_number(
        ef["acclimation_hours"], "site.environment.acclimation_hours",
        non_negative=True,
    )
    return SiteSurvey(
        wall=_parse_wall(f["wall"], units),
        floor=FloorSurvey(
            _length(ff["high_point_elevation"], units,
                    "site.floor.high_point_elevation"),
            ff["verified"],
        ),
        environment=SiteEnvironment(
            ef["building_enclosed"], ef["wet_work_complete"],
            ef["hvac_operating"], float(hours)
        ),
    )


def _parse_cabinet(raw, units: str, profile, wall: StudWallSurvey,
                   index: int, source_archetype: str = "") -> BaseCabinetDecl:
    ctx = f"cabinetry.cabinets[{index}]"
    f = _take(
        raw,
        {"id", "type", "width", "placement", "front", "interior",
         "conditions", "countertop"},
        {"height", "depth", "toe_kick_height", "toe_kick_setback"},
        ctx,
    )
    cabinet_id = str(f["id"]).strip()
    if not cabinet_id:
        raise ProjectSchemaError(f"{ctx}.id must be non-empty")
    if f["type"] != "base":
        raise ProjectSchemaError(
            f"{ctx}.type: cabinetry v1 supports only 'base', got {f['type']!r}"
        )
    pf = _take(f["placement"], {"against", "from_left_datum"}, set(),
               f"{ctx}.placement")
    if pf["against"] != wall.wall_id:
        raise ProjectSchemaError(
            f"{ctx}.placement.against: unknown wall {pf['against']!r}; "
            f"known wall: {wall.wall_id!r}"
        )
    front = _take(f["front"], {"doors"}, set(), f"{ctx}.front")
    if front["doors"] != 2:
        raise ProjectSchemaError(
            f"{ctx}.front.doors: v1 requires exactly two overlay doors"
        )
    interior = _take(f["interior"], {"adjustable_shelves", "design_load_psf"},
                     set(), f"{ctx}.interior")
    if interior["adjustable_shelves"] != 1:
        raise ProjectSchemaError(
            f"{ctx}.interior.adjustable_shelves: v1 requires exactly one "
            f"adjustable shelf"
        )
    load = _finite_number(
        interior["design_load_psf"], f"{ctx}.interior.design_load_psf",
        positive=True,
    )
    conditions = _take(f["conditions"], {"left_end", "right_end"}, set(),
                       f"{ctx}.conditions")
    allowed_conditions = {"exposed", "adjacent_cabinet", "wall_filler"}
    for key in ("left_end", "right_end"):
        if conditions[key] not in allowed_conditions:
            raise ProjectSchemaError(
                f"{ctx}.conditions.{key}: expected one of "
                f"{sorted(allowed_conditions)}, got {conditions[key]!r}"
            )
    countertop = _take(f["countertop"], {"type", "support"}, set(),
                       f"{ctx}.countertop")
    if countertop["type"] != "field_installed":
        raise ProjectSchemaError(
            f"{ctx}.countertop.type: v1 supports only field_installed; "
            f"got {countertop['type']!r}"
        )
    if countertop["support"] != "cabinet_stretchers":
        raise ProjectSchemaError(
            f"{ctx}.countertop.support: v1 supports only cabinet_stretchers; "
            f"got {countertop['support']!r}"
        )

    def optional_length(key: str, default: float) -> float:
        return default if f[key] is _MISSING else _length(
            f[key], units, f"{ctx}.{key}", positive=True
        )

    width = _length(f["width"], units, f"{ctx}.width", positive=True)
    from_left = _length(
        pf["from_left_datum"], units, f"{ctx}.placement.from_left_datum"
    )
    if from_left < 0 or from_left + width > wall.length_mm:
        raise ProjectSchemaError(
            f"{ctx}: cabinet span [{from_left:.2f}, {from_left + width:.2f}] mm "
            f"lies outside surveyed wall [0, {wall.length_mm:.2f}] mm"
        )
    return BaseCabinetDecl(
        cabinet_id=cabinet_id,
        kind="base",
        width_mm=width,
        height_mm=optional_length("height", profile.default_height_mm),
        depth_mm=optional_length("depth", profile.default_depth_mm),
        toe_kick_height_mm=optional_length(
            "toe_kick_height", profile.toe_kick_height_mm
        ),
        toe_kick_setback_mm=optional_length(
            "toe_kick_setback", profile.toe_kick_setback_mm
        ),
        wall_id=wall.wall_id,
        from_left_datum_mm=from_left,
        door_count=2,
        adjustable_shelf_count=1,
        design_load_psf=float(load),
        left_end=str(conditions["left_end"]),
        right_end=str(conditions["right_end"]),
        countertop_type=str(countertop["type"]),
        countertop_support=str(countertop["support"]),
        source_archetype=source_archetype,
    )


def parse_cabinetry_project(
    doc: ProjectDoc,
    source_archetypes: dict[str, str] | None = None,
) -> CabinetrySection:
    missing = [key for key in ("site", "cabinetry") if key not in doc.sections]
    if missing:
        raise ProjectSchemaError(
            f"cabinetry.frameless@1 requires project sections {missing}"
        )
    site = _parse_site(doc.sections["site"], doc.units)
    f = _take(
        doc.sections["cabinetry"],
        {"mode", "profile", "material_evidence", "cabinets"},
        set(),
        "cabinetry",
    )
    if f["mode"] not in {"draft", "release"}:
        raise ProjectSchemaError(
            f"cabinetry.mode must be 'draft' or 'release', got {f['mode']!r}"
        )
    profile = get_profile(str(f["profile"]))
    evidence = _take(
        f["material_evidence"], {
            "tsca_title_vi", "reference", "product", "density_kg_m3",
            "modulus_elasticity_mpa", "property_reference",
        }, set(),
        "cabinetry.material_evidence"
    )
    if evidence["tsca_title_vi"] not in {"verified", "required", "unknown"}:
        raise ProjectSchemaError(
            "cabinetry.material_evidence.tsca_title_vi must be one of "
            "['required', 'unknown', 'verified']"
        )
    source_archetypes = source_archetypes or {}
    cabinets = tuple(
        _parse_cabinet(
            raw, doc.units, profile, site.wall, i,
            source_archetypes.get(str(raw.get("id", "")).strip(), ""),
        )
        for i, raw in enumerate(_list(f["cabinets"], "cabinetry.cabinets"))
    )
    if not cabinets:
        raise ProjectSchemaError(
            "cabinetry.frameless@1 requires at least one cabinet"
        )
    ids = [cabinet.cabinet_id for cabinet in cabinets]
    if len(ids) != len(set(ids)):
        raise ProjectSchemaError("cabinetry.cabinets contains duplicate cabinet ids")
    cabinets = tuple(sorted(cabinets, key=lambda item: item.from_left_datum_mm))
    if len(cabinets) > 1:
        if cabinets[0].left_end == "adjacent_cabinet":
            raise ProjectSchemaError(
                f"cabinetry run starts at {cabinets[0].cabinet_id}; its left_end "
                "cannot be adjacent_cabinet"
            )
        if cabinets[-1].right_end == "adjacent_cabinet":
            raise ProjectSchemaError(
                f"cabinetry run ends at {cabinets[-1].cabinet_id}; its right_end "
                "cannot be adjacent_cabinet"
            )
    for left, right in zip(cabinets, cabinets[1:]):
        left_edge = left.from_left_datum_mm + left.width_mm
        delta = right.from_left_datum_mm - left_edge
        if delta < -1e-6:
            raise ProjectSchemaError(
                f"cabinetry run overlap: {left.cabinet_id} ends at "
                f"{left_edge:.2f} mm but {right.cabinet_id} starts at "
                f"{right.from_left_datum_mm:.2f} mm"
            )
        if delta > 1e-6:
            raise ProjectSchemaError(
                f"cabinetry run gap {delta:.2f} mm between {left.cabinet_id} "
                f"and {right.cabinet_id}; declare a supported filler increment "
                "instead of leaving an unresolved void"
            )
        if not (left.right_end == right.left_end == "adjacent_cabinet"):
            raise ProjectSchemaError(
                f"cabinetry run adjacent conditions must agree for "
                f"{left.cabinet_id} and {right.cabinet_id}: expected "
                "right_end/left_end = adjacent_cabinet"
            )
    return CabinetrySection(
        mode=str(f["mode"]),
        profile_id=profile.profile_id,
        material_evidence=MaterialEvidence(
            str(evidence["tsca_title_vi"]), str(evidence["reference"]).strip(),
            str(evidence["product"]).strip(),
            _finite_number(
                evidence["density_kg_m3"],
                "cabinetry.material_evidence.density_kg_m3", positive=True,
            ),
            _finite_number(
                evidence["modulus_elasticity_mpa"],
                "cabinetry.material_evidence.modulus_elasticity_mpa",
                positive=True,
            ),
            str(evidence["property_reference"]).strip(),
        ),
        site=site,
        cabinets=cabinets,
    )
