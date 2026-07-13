"""Versioned archetype expansion into the strict cabinet/vanity schemas."""

from __future__ import annotations

import copy
import difflib
from dataclasses import replace

from ..project import ProjectSchemaError
from .schema import _length

_CABINET_ARCHETYPES = {
    "base_two_door_30@1",
    "base_two_door@1",
    "straight_base_run@1",
}
_VANITY_ARCHETYPES = {"floating_vanity_two_door@1"}
_BASE_OVERRIDES = {
    "height", "depth", "toe_kick_height", "toe_kick_setback",
    "design_load_psf",
}
_VANITY_OVERRIDES = {"height", "depth"}


def _mapping(value, ctx: str) -> dict:
    if not isinstance(value, dict):
        raise ProjectSchemaError(f"{ctx} must be a mapping")
    return value


def _strict_keys(raw: dict, required: set[str], optional: set[str], ctx: str):
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


def _known_archetype(value, known: set[str], ctx: str) -> str:
    archetype = str(value).strip()
    if archetype in known:
        return archetype
    suggestion = difflib.get_close_matches(archetype, sorted(known), n=1)
    hint = f"; did you mean {suggestion[0]!r}?" if suggestion else ""
    raise ProjectSchemaError(
        f"unknown {ctx} archetype {archetype!r}; known: {sorted(known)}{hint}"
    )


def _overrides(value, allowed: set[str], ctx: str) -> dict:
    raw = _mapping(value, ctx)
    for key in raw:
        if key in allowed:
            continue
        suggestion = difflib.get_close_matches(str(key), sorted(allowed), n=1)
        hint = f"; did you mean {suggestion[0]!r}?" if suggestion else ""
        raise ProjectSchemaError(
            f"{ctx}: unknown override {key!r}; allowed overrides: "
            f"{sorted(allowed)}{hint}"
        )
    return dict(raw)


def _base_cabinet(
    raw: dict,
    *,
    units: str,
    ctx: str,
) -> tuple[dict, str]:
    _strict_keys(
        raw,
        {"archetype", "id", "placement", "conditions"},
        {"width", "overrides"},
        ctx,
    )
    archetype = _known_archetype(
        raw["archetype"], _CABINET_ARCHETYPES - {"straight_base_run@1"},
        "cabinet",
    )
    if archetype == "base_two_door_30@1":
        if "width" in raw:
            raise ProjectSchemaError(
                f"{ctx}.width: base_two_door_30@1 fixes width at 30 in; "
                "use base_two_door@1 for a parameterized width"
            )
        width = "30 in"
    else:
        if "width" not in raw:
            raise ProjectSchemaError(
                f"{ctx}.width is required by base_two_door@1"
            )
        width = raw["width"]
    overrides = _overrides(
        raw.get("overrides", {}), _BASE_OVERRIDES, f"{ctx}.overrides"
    )
    result = {
        "id": raw["id"],
        "type": "base",
        "width": width,
        "placement": copy.deepcopy(raw["placement"]),
        "front": {"doors": 2},
        "interior": {
            "adjustable_shelves": 1,
            "design_load_psf": overrides.pop("design_load_psf", 15),
        },
        "conditions": copy.deepcopy(raw["conditions"]),
        "countertop": {
            "type": "field_installed",
            "support": "cabinet_stretchers",
        },
    }
    result.update(overrides)
    # Resolve once here only to reject nonsensical compact widths immediately;
    # the strict schema remains the canonical converter and validates it again.
    _length(result["width"], units, f"{ctx}.width", positive=True)
    return result, archetype


def _run_cabinets(raw: dict, overrides: dict, *, units: str) -> list[dict]:
    ctx = "cabinetry.run"
    _strict_keys(
        raw,
        {"against", "origin", "left_end", "right_end", "cabinets"},
        set(),
        ctx,
    )
    items = raw["cabinets"]
    if not isinstance(items, list) or len(items) < 2:
        raise ProjectSchemaError(
            "cabinetry.run.cabinets must contain at least two cabinets"
        )
    cursor_mm = _length(raw["origin"], units, "cabinetry.run.origin")
    if cursor_mm < 0:
        raise ProjectSchemaError("cabinetry.run.origin must be non-negative")
    result: list[dict] = []
    for index, item in enumerate(items):
        item = _mapping(item, f"cabinetry.run.cabinets[{index}]")
        _strict_keys(
            item, {"id", "width"}, {"overrides"},
            f"cabinetry.run.cabinets[{index}]",
        )
        local = dict(overrides)
        local.update(_overrides(
            item.get("overrides", {}), _BASE_OVERRIDES,
            f"cabinetry.run.cabinets[{index}].overrides",
        ))
        width_mm = _length(
            item["width"], units, f"cabinetry.run.cabinets[{index}].width",
            positive=True,
        )
        cabinet = {
            "id": item["id"],
            "type": "base",
            "width": item["width"],
            "placement": {
                "against": raw["against"],
                "from_left_datum": f"{cursor_mm:.9f} mm",
            },
            "front": {"doors": 2},
            "interior": {
                "adjustable_shelves": 1,
                "design_load_psf": local.pop("design_load_psf", 15),
            },
            "conditions": {
                "left_end": raw["left_end"] if index == 0 else "adjacent_cabinet",
                "right_end": (
                    raw["right_end"] if index == len(items) - 1
                    else "adjacent_cabinet"
                ),
            },
            "countertop": {
                "type": "field_installed",
                "support": "cabinet_stretchers",
            },
        }
        cabinet.update(local)
        result.append(cabinet)
        cursor_mm += width_mm
    return result


def expand_cabinetry_project(doc):
    """Return ``(expanded_doc, cabinet_id -> archetype_id)``."""

    raw_section = doc.sections.get("cabinetry")
    if not isinstance(raw_section, dict):
        return doc, {}
    section = copy.deepcopy(raw_section)
    source: dict[str, str] = {}
    if "archetype" in section:
        archetype = _known_archetype(
            section["archetype"], _CABINET_ARCHETYPES, "cabinetry"
        )
        if archetype != "straight_base_run@1":
            raise ProjectSchemaError(
                "top-level cabinetry.archetype supports only straight_base_run@1; "
                "put base cabinet archetypes inside cabinetry.cabinets"
            )
        _strict_keys(
            section,
            {"mode", "profile", "material_evidence", "archetype", "run"},
            {"overrides"},
            "cabinetry",
        )
        overrides = _overrides(
            section.get("overrides", {}), _BASE_OVERRIDES,
            "cabinetry.overrides",
        )
        cabinets = _run_cabinets(section["run"], overrides, units=doc.units)
        source = {str(item["id"]).strip(): archetype for item in cabinets}
        section = {
            "mode": section["mode"],
            "profile": section["profile"],
            "material_evidence": section["material_evidence"],
            "cabinets": cabinets,
        }
    elif isinstance(section.get("cabinets"), list):
        expanded = []
        for index, item in enumerate(section["cabinets"]):
            if not isinstance(item, dict) or "archetype" not in item:
                expanded.append(item)
                continue
            cabinet, archetype = _base_cabinet(
                item, units=doc.units, ctx=f"cabinetry.cabinets[{index}]"
            )
            cabinet_id = str(cabinet["id"]).strip()
            source[cabinet_id] = archetype
            expanded.append(cabinet)
        section["cabinets"] = expanded
    if not source:
        return doc, {}
    sections = copy.deepcopy(doc.sections)
    sections["cabinetry"] = section
    return replace(doc, sections=sections), source


def expand_vanity_project(doc):
    """Return ``(expanded_doc, source_archetype)`` for a compact vanity."""

    raw_section = doc.sections.get("vanity")
    if not isinstance(raw_section, dict) or "archetype" not in raw_section:
        return doc, ""
    section = copy.deepcopy(raw_section)
    _strict_keys(
        section,
        {
            "mode", "profile", "material_evidence", "archetype", "cabinet",
            "plumbing", "loads", "mounting",
        },
        {"overrides"},
        "vanity",
    )
    archetype = _known_archetype(
        section["archetype"], _VANITY_ARCHETYPES, "vanity"
    )
    cabinet = _mapping(section["cabinet"], "vanity.cabinet")
    _strict_keys(
        cabinet, {"id", "width", "bottom_elevation", "placement"}, set(),
        "vanity.cabinet",
    )
    overrides = _overrides(
        section.get("overrides", {}), _VANITY_OVERRIDES, "vanity.overrides"
    )
    section["cabinet"] = {
        "id": cabinet["id"],
        "type": "floating",
        "width": cabinet["width"],
        "height": overrides.pop("height", "24 in"),
        "depth": overrides.pop("depth", "21 in"),
        "bottom_elevation": cabinet["bottom_elevation"],
        "placement": cabinet["placement"],
        "front": {"doors": 2},
        "top": {"type": "field_installed", "sink": "field_installed"},
    }
    section.pop("archetype")
    section.pop("overrides", None)
    sections = copy.deepcopy(doc.sections)
    sections["vanity"] = section
    return replace(doc, sections=sections), archetype

