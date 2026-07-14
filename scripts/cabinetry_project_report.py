#!/usr/bin/env python3
"""Generate one self-contained build document from a packed cabinetry project."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass, replace
import gzip
import html
import json
from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from detailgen.packs import compile_project_file  # noqa: E402
from detailgen.packs.cabinetry.catalogs import get_assembly_fastener  # noqa: E402
from detailgen.packs.cabinetry.validation import (  # noqa: E402
    anchor_embedment_facts,
)
from detailgen.assemblies.assembly import DetailAssembly  # noqa: E402
from detailgen.rendering.export import export_glb, export_png  # noqa: E402
from detailgen.rendering.part_labels import part_labels  # noqa: E402
from detailgen.rendering.web_viewer import (  # noqa: E402
    build_viewer_payload,
    vendor_js,
    viewer_css,
    viewer_js,
)


REQUIRED_VIEWS = (
    "front", "installation-plan", "anchor-section", "isometric",
    "exploded", "drawer-detail",
)
VIEW_CAPTIONS = {
    "front": (
        "Installed front/setout elevation with model-bound fronts, stud and "
        "anchor centerlines, high-floor datum, and countertop boundary."
    ),
    "installation-plan": (
        "Installation plan with cabinet and toe footprints, wall datum, "
        "surveyed studs, and cabinet-local anchor offsets."
    ),
    "anchor-section": (
        "Anchor/toe section showing the selected screw, modeled stack and "
        "stud embedment without claiming capacity or torque."
    ),
    "isometric": "Compiled product assembly; use Explore in 3D to isolate and explode parts.",
    "exploded": "Drawer-bank exploded diagram, grouped by stable top/middle/bottom identity.",
    "drawer-detail": (
        "Typical MOVENTO wood-drawer geometry with runner and lateral-stabilizer preparation."
    ),
}

REVIEW_BASENAME = "frameless_three_drawer_40_build_document.html"
MANUAL_BASENAME = "frameless_three_drawer_40_assembly_manual.html"
FABRICATION_BASENAME = "frameless_three_drawer_40_fabrication_packet.html"
AUDIT_BASENAME = "frameless_three_drawer_40_review_trace.html"


def _relative_html_basename(value: str, *, field: str) -> str:
    value = str(value)
    if (
        not value
        or Path(value).name != value
        or not value.endswith(".html")
        or ":" in value
        or "/" in value
        or "\\" in value
    ):
        raise ValueError(f"{field} must be a relative HTML basename")
    return value


@dataclass(frozen=True)
class CabinetryDocumentLinks:
    """Validated filenames for the four reciprocal cabinetry surfaces."""

    review_href: str = REVIEW_BASENAME
    manual_href: str = MANUAL_BASENAME
    fabrication_href: str = FABRICATION_BASENAME
    audit_href: str = AUDIT_BASENAME

    def __post_init__(self) -> None:
        for field in (
            "review_href", "manual_href", "fabrication_href", "audit_href",
        ):
            object.__setattr__(
                self,
                field,
                _relative_html_basename(getattr(self, field), field=field),
            )


@dataclass(frozen=True)
class CabinetrySharedAssets:
    """One render pass shared by every document composer."""

    assembly: DetailAssembly
    images: dict[str, str]
    viewer_payload: dict
    glb_bytes: bytes


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _fmt(value: float) -> str:
    return f"{value:.2f} mm"


def _number(value: float) -> str:
    """Format a catalog or machining number without false trailing precision."""

    return f"{value:g}"


def _table(headers, rows, *, css_class="") -> str:
    head = "".join(f"<th>{_esc(item)}</th>" for item in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return (
        f'<div class="table-wrap"><table class="{_esc(css_class)}">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def render_dimension_tables(model) -> str:
    """Project dimensions directly from the packed semantic model."""

    cabinet = model.section.cabinets[0]
    overall = _table(
        ("Overall", "Value", "Source"),
        (
            ("Width", _fmt(cabinet.width_mm), "declaration"),
            ("Height", _fmt(cabinet.height_mm), "archetype/profile"),
            ("Depth", _fmt(cabinet.depth_mm), "archetype/profile"),
            ("Toe height", _fmt(cabinet.toe_kick_height_mm), "archetype/profile"),
            ("Toe setback", _fmt(cabinet.toe_kick_setback_mm), "archetype/profile"),
        ),
    )
    if hasattr(model, "drawer_bank"):
        bank = model.drawer_bank
        bank_rows = (
            ("Clear opening width", _fmt(bank.opening_width_mm),
             "carcass width − two ends"),
            ("Applied-front width", _fmt(model.derived_value("front_width").value),
             "overall width − two side reveals"),
            ("Outside box width", _fmt(bank.outside_box_width_mm),
             "runner formula"),
            ("Inside box width", _fmt(bank.inside_box_width_mm),
             "opening width − 42 mm"),
            ("Box length", _fmt(bank.box_length_mm), "runner nominal length"),
            ("Side reveal", _fmt(bank.front_edge_reveal_mm), "front policy"),
            ("Inter-front gap", _fmt(bank.front_gap_mm), "front policy"),
        )
        cell_rows = tuple(
            (
                _esc(cell.cell_id),
                _fmt(model.part(f"drawer_front_{cell.cell_id}").width_mm),
                _fmt(model.part(f"drawer_{cell.cell_id}_side_left").width_mm),
                f"{cell.contents_load_lb:.0f} lb",
                f"{cell.calculated_moving_load_lb:.2f} lb",
            )
            for cell in bank.cells
        )
        product = _table(("Drawer-bank dimension", "Value", "Derivation"), bank_rows)
        cells = _table(
            ("Cell", "Front height", "Box height", "Declared contents",
             "Calculated moving load (not a rating)"),
            cell_rows,
        )
        return f"<h2>Dimensions</h2>{overall}{product}{cells}"

    derived_rows = tuple(
        (_esc(item.name.replace("_", " ").title()), _fmt(item.value), _esc(item.rule))
        for item in model.derived
    )
    return (
        f"<h2>Dimensions</h2>{overall}"
        + _table(("Derived dimension", "Value", "Rule"), derived_rows)
    )


def drawer_detail_geometry(model) -> dict[str, object]:
    """Return model-bound facts used by the drawer-detail schematic."""

    bank = model.drawer_bank
    bottom = model.part("drawer_top_bottom")
    return {
        "bottom_front_origin_mm": (
            bank.outside_box_width_mm - bottom.length_mm
        ) / 2,
        "bottom_side_origin_mm": (bank.box_length_mm - bottom.width_mm) / 2,
        "bottom_blank_width_mm": bottom.length_mm,
        "bottom_blank_depth_mm": bottom.width_mm,
        "bottom_thickness_mm": bottom.thickness_mm,
        "runner_physical_length_mm": bank.runner.physical_length_mm,
        "pull_hole_spacing_mm": bank.pull_product.hole_spacing_mm,
        "locking_skus": (
            bank.locking_device.left_sku,
            bank.locking_device.right_sku,
        ),
        "rear_notch_mm": (
            bank.runner.minimum_rear_notch_mm,
            bank.runner.minimum_rear_notch_height_mm,
        ),
        "rear_hook_centers_mm": (
            (
                bank.runner.hook_bore_inset_from_side_mm,
                bank.runner.hook_bore_height_from_bottom_mm,
            ),
            (
                bank.inside_box_width_mm
                - bank.runner.hook_bore_inset_from_side_mm,
                bank.runner.hook_bore_height_from_bottom_mm,
            ),
        ),
    }


def installation_drawing_facts(project) -> dict[str, object]:
    """Project installation geometry from one coherent packed model.

    The drawing functions deliberately consume only this projection.  Missing
    or contradictory cabinet, toe, stud, strip, or screw geometry raises here
    rather than allowing a plausible-looking coordination drawing to drift
    from the model.
    """

    model = project.model
    cabinets = tuple(model.section.cabinets)
    if len(cabinets) != 1:
        raise ValueError(
            "installation drawings require exactly one cabinet declaration; "
            f"found {len(cabinets)}"
        )
    cabinet = cabinets[0]
    wall = model.section.site.wall
    floor = model.section.site.floor
    tolerance = 1e-6
    cabinet_x0 = wall.plane_origin_mm[0] + cabinet.from_left_datum_mm
    cabinet_front_y = wall.plane_origin_mm[1] - cabinet.depth_mm
    cabinet_base_z = floor.high_point_elevation_mm

    if wall.plane_normal != (0.0, -1.0, 0.0):
        raise ValueError(
            "installation drawings require the cabinetry v1 wall frame with "
            "normal (0, -1, 0)"
        )
    if abs(wall.plane_origin_mm[1] - (cabinet_front_y + cabinet.depth_mm)) \
            > tolerance:
        raise ValueError(
            "cabinet back and surveyed wall plane are incoherent; the drawing "
            "cannot invent a wall gap"
        )

    parts_by_role: dict[str, list] = {}
    for part in model.parts:
        parts_by_role.setdefault(part.role, []).append(part)

    def one_part(role: str, *, component_type: str | None = None):
        matches = parts_by_role.get(role, ())
        if len(matches) != 1:
            raise ValueError(
                f"installation drawings require exactly one {role!r} part; "
                f"found {len(matches)}"
            )
        part = matches[0]
        if component_type is not None and part.component_type != component_type:
            raise ValueError(
                f"installation drawing role {role!r} must be a "
                f"{component_type}, got {part.component_type!r}"
            )
        return part

    anchor_strip = one_part("anchor_strip", component_type="plywood_panel")
    if anchor_strip.rotate != (("X", 90.0),):
        raise ValueError(
            "anchor strip must use the compiled vertical strip orientation"
        )
    anchor_strip_bounds = {
        "x": (
            anchor_strip.at_mm[0] - cabinet_x0,
            anchor_strip.at_mm[0] - cabinet_x0 + anchor_strip.length_mm,
        ),
        "z": (
            anchor_strip.at_mm[2] - cabinet_base_z,
            anchor_strip.at_mm[2] - cabinet_base_z + anchor_strip.width_mm,
        ),
    }

    toe_roles = ("toe_front", "toe_rear", "toe_left", "toe_right")
    toe_parts = {
        role: one_part(role, component_type="plywood_panel")
        for role in toe_roles
    }
    toe_plan_bounds = {}
    for role, part in toe_parts.items():
        if role in {"toe_front", "toe_rear"}:
            if part.rotate != (("X", 90.0),):
                raise ValueError(
                    f"{role} must use the compiled transverse toe-rail orientation"
                )
            x_bounds = (part.at_mm[0], part.at_mm[0] + part.length_mm)
            y_bounds = (part.at_mm[1] - part.thickness_mm, part.at_mm[1])
        else:
            if part.rotate != (("X", 90.0), ("Z", 90.0)):
                raise ValueError(
                    f"{role} must use the compiled toe-sleeper orientation"
                )
            x_bounds = (part.at_mm[0], part.at_mm[0] + part.thickness_mm)
            y_bounds = (part.at_mm[1], part.at_mm[1] + part.length_mm)
        if abs(part.width_mm - cabinet.toe_kick_height_mm) > tolerance:
            raise ValueError(
                f"{role} height does not match the declared toe-kick height"
            )
        toe_plan_bounds[role] = (x_bounds, y_bounds)

    toe_x = (
        min(bounds[0][0] for bounds in toe_plan_bounds.values()),
        max(bounds[0][1] for bounds in toe_plan_bounds.values()),
    )
    toe_y = (
        min(bounds[1][0] for bounds in toe_plan_bounds.values()),
        max(bounds[1][1] for bounds in toe_plan_bounds.values()),
    )
    if (
        abs(toe_x[0] - cabinet_x0) > tolerance
        or abs(toe_x[1] - (cabinet_x0 + cabinet.width_mm)) > tolerance
        or abs(toe_plan_bounds["toe_left"][1][0]
               - toe_plan_bounds["toe_front"][1][1]) > tolerance
        or abs(toe_plan_bounds["toe_left"][1][1]
               - toe_plan_bounds["toe_rear"][1][0]) > tolerance
        or toe_plan_bounds["toe_left"][1] != toe_plan_bounds["toe_right"][1]
    ):
        raise ValueError(
            "compiled toe parts do not form one closed rectangular support "
            "footprint under the cabinet"
        )

    survey_by_id = {stud.stud_id: stud for stud in wall.studs}
    if len(survey_by_id) != len(wall.studs):
        raise ValueError("surveyed wall stud ids must be unique")
    target_ids = tuple(model.anchor_stud_ids)
    anchor_roles = {
        part.role.removeprefix("wall_anchor_"): part
        for part in model.parts
        if part.role.startswith("wall_anchor_")
        and part.component_type == "structural_screw"
    }
    if (
        not target_ids
        or len(anchor_roles) != len(target_ids)
        or set(anchor_roles) != set(target_ids)
    ):
        raise ValueError(
            "installation drawings require one structural-screw anchor per "
            "surveyed stud target"
        )
    wall_anchor_systems = tuple(
        item for item in model.hardware if item.kind == "wall_anchor_system"
    )
    expected_anchor_part_ids = {
        f"cabinetry.{cabinet.cabinet_id}.wall_anchor_{stud_id}"
        for stud_id in target_ids
    }
    if (
        len(wall_anchor_systems) != 1
        or wall_anchor_systems[0].product_id != model.wall_anchor.product_id
        or wall_anchor_systems[0].quantity != len(target_ids)
        or set(wall_anchor_systems[0].related_parts) != expected_anchor_part_ids
    ):
        raise ValueError(
            "wall-anchor hardware schedule must name the selected product and "
            "exactly the modeled structural-screw paths"
        )

    stud_centers = []
    anchors = []
    anchor_z_values = []
    stack_values = []
    embedment_values = []
    head_plane_y = anchor_strip.at_mm[1] - anchor_strip.thickness_mm
    stud_front_y = wall.plane_origin_mm[1] + wall.finish_thickness_mm
    strip_center_z = anchor_strip.at_mm[2] + anchor_strip.width_mm / 2
    for stud_id in target_ids:
        if stud_id not in survey_by_id:
            raise ValueError(
                f"anchor target {stud_id!r} is absent from the surveyed studs"
            )
        survey = survey_by_id[stud_id]
        stud = one_part(f"wall_stud_{stud_id}", component_type="lumber")
        anchor = anchor_roles[stud_id]
        expected_stud_id = f"site.{wall.wall_id}.{stud_id}"
        expected_anchor_id = f"cabinetry.{cabinet.cabinet_id}.wall_anchor_{stud_id}"
        center_x = wall.plane_origin_mm[0] + survey.position_mm
        placed_stud_center = stud.at_mm[0] + stud.width_mm / 2
        if (
            stud.part_id != expected_stud_id
            or anchor.part_id != expected_anchor_id
            or abs(placed_stud_center - center_x) > tolerance
            or anchor.rotate != (("X", 90.0),)
            or abs(anchor.at_mm[0] - center_x) > tolerance
            or abs(anchor.at_mm[1] - head_plane_y) > tolerance
            or abs(anchor.at_mm[2] - strip_center_z) > tolerance
            or abs(anchor.length_mm - model.wall_anchor.length_mm) > tolerance
            or abs(anchor.width_mm - model.wall_anchor.diameter_mm) > tolerance
            or abs(anchor.thickness_mm - model.wall_anchor.diameter_mm) > tolerance
        ):
            raise ValueError(
                f"modeled stud/anchor path for {stud_id!r} is incoherent with "
                "the survey, anchor strip, or selected screw geometry"
            )
        local_x = anchor.at_mm[0] - cabinet_x0
        local_z = anchor.at_mm[2] - cabinet_base_z
        stack = stud_front_y - anchor.at_mm[1]
        embedment = anchor.length_mm - stack
        if stack <= 0 or embedment <= 0:
            raise ValueError(
                f"modeled anchor path for {stud_id!r} does not reach the stud"
            )
        stud_centers.append((stud_id, center_x))
        anchor_z_values.append(local_z)
        stack_values.append(stack)
        embedment_values.append(embedment)
        anchors.append({
            "stud_id": stud_id,
            "stud_part_id": stud.part_id,
            "anchor_part_id": anchor.part_id,
            "stud_verified": survey.verified,
            "global_x_mm": center_x,
            "local_x_mm": local_x,
            "local_z_mm": local_z,
        })

    def require_common(values: list[float], label: str) -> float:
        if not values or max(values) - min(values) > tolerance:
            raise ValueError(
                f"installation drawings require one common {label} for all anchors"
            )
        return values[0]

    anchor_z = require_common(anchor_z_values, "anchor elevation")
    stack = require_common(stack_values, "modeled anchor stack")
    embedment = require_common(embedment_values, "modeled stud embedment")
    validation_stack, validation_embedment, minimum_embedment, _embedment_ok = \
        anchor_embedment_facts(model)
    if (
        abs(validation_stack - stack) > tolerance
        or abs(validation_embedment - embedment) > tolerance
    ):
        raise ValueError(
            "installation drawing anchor facts disagree with the canonical "
            "anchor-path validation"
        )

    released = bool(project.installation_use_ready)
    stamp = (
        "INSTALLATION/USE RELEASE: PASS — FOLLOW THE REVIEWED PROJECT-SPECIFIC "
        "PROCEDURE"
        if released else
        "COORDINATION ONLY — DO NOT ANCHOR OR ATTACH COUNTERTOP UNTIL HOLD CLEARED"
    )
    return {
        "cabinet_id": cabinet.cabinet_id,
        "cabinet_bounds_local_mm": {
            "x": (0.0, cabinet.width_mm),
            "y": (0.0, cabinet.depth_mm),
            "z": (0.0, cabinet.height_mm),
        },
        "cabinet_left_global_mm": cabinet_x0,
        "wall_left_datum_global_mm": wall.plane_origin_mm[0],
        "wall_plane_y_global_mm": wall.plane_origin_mm[1],
        "wall_finish_thickness_mm": wall.finish_thickness_mm,
        "stud_width_mm": wall.stud_width_mm,
        "stud_depth_mm": wall.stud_depth_mm,
        "toe_footprint_local_mm": {
            "x": (toe_x[0] - cabinet_x0, toe_x[1] - cabinet_x0),
            "y": (toe_y[0] - cabinet_front_y, toe_y[1] - cabinet_front_y),
        },
        "toe_height_mm": cabinet.toe_kick_height_mm,
        "toe_setback_mm": cabinet.toe_kick_setback_mm,
        "anchor_strip_bounds_local_mm": anchor_strip_bounds,
        "anchor_strip_thickness_mm": anchor_strip.thickness_mm,
        "stud_centers_global_mm": tuple(stud_centers),
        "anchor_x_local_mm": tuple(item["local_x_mm"] for item in anchors),
        "anchor_z_local_mm": anchor_z,
        "anchors": tuple(anchors),
        "selected_screw_product_id": model.wall_anchor.product_id,
        "selected_screw_name": model.wall_anchor.product,
        "selected_screw_source_url": model.wall_anchor.source_url,
        "selected_screw_length_mm": model.wall_anchor.length_mm,
        "selected_screw_diameter_mm": model.wall_anchor.diameter_mm,
        "modeled_stack_mm": stack,
        "stud_embedment_mm": embedment,
        "minimum_stud_embedment_mm": minimum_embedment,
        "high_floor_local_z_mm": floor.high_point_elevation_mm - cabinet_base_z,
        "high_floor_verified": floor.verified,
        "installation_use_status": "PASS" if released else "HOLD",
        "drawing_stamp": stamp,
    }


def _render_cut_list(project) -> str:
    labels = reader_labels_by_part_id(project)
    rows = tuple(
        (
            '<span aria-label="not checked">□</span>',
            _esc(labels[item.part_id]),
            f"<code>{_esc(item.part_id)}</code>", str(item.quantity),
            _fmt(item.length_mm), _fmt(item.width_mm), _fmt(item.thickness_mm),
            _esc(item.material), _esc(item.source_rule),
        )
        for item in project.artifacts.cut_list
    )
    return (
        "<h2>Cut list</h2><p><strong>Pre-band cut size:</strong> Length and "
        "width are raw blank dimensions. The compiled geometry and front "
        "reveal checks use finished dimensions after the declared band build.</p>"
        + _table(
        ("Done", "Reader name", "Part id", "Qty", "Pre-band cut length",
         "Pre-band cut width", "Panel thickness", "Material", "Rule"),
        rows,
    ))


def reader_labels_by_part_id(project) -> dict[str, str]:
    """Return the compiled hover label for every modeled cabinetry part id."""

    placed_by_name = {part.name: part for part in project.detail.assembly.parts}
    labels = part_labels(project.detail.assembly.parts)
    result = {}
    for part in project.model.parts:
        placed = placed_by_name.get(part.name)
        if placed is None:
            raise ValueError(
                f"modeled cabinetry part {part.part_id!r} is absent from the "
                "compiled assembly used by the reader surfaces"
            )
        result[part.part_id] = labels[placed.id].display_name
    return result


def _render_part_key(project) -> str:
    labels = reader_labels_by_part_id(project)
    rows = []
    for part in project.model.parts:
        if part.part_id.startswith("site."):
            scope = "Existing site context"
        elif part.component_type == "structural_screw":
            scope = "Installation hardware"
        else:
            scope = "Fabricated cabinet part"
        rows.append((
            _esc(labels[part.part_id]),
            _esc(scope),
            f"<code>{_esc(part.part_id)}</code>",
            _esc(part.role),
        ))
    return (
        "<h2>Part key</h2>"
        "<p>These are the same reader names shown when a part is hovered in "
        "the 3D viewer. Stable ids remain visible for cut, machining, and "
        "evidence cross-reference.</p>"
        + _table(("Reader name", "Scope", "Stable id", "Role"), tuple(rows))
    )


def _render_edge_banding(project) -> str:
    rows = tuple(
        (f"<code>{_esc(item.part_id)}</code>", _esc(item.edge),
         _fmt(item.length_mm), _fmt(item.thickness_mm),
         f"<code>{_esc(item.product_id)}</code>", _esc(item.material),
         _esc(item.cut_size_basis))
        for item in project.artifacts.edge_banding
    )
    return "<h2>Edge banding</h2>" + _table(
        ("Part id", "Edge", "Length", "Finished thickness", "Product",
         "Material", "Cut-size basis"), rows
    )


def _render_hardware(project) -> str:
    rows = tuple(
        (
            f"<code>{_esc(item.system_id)}</code>", _esc(item.kind),
            f"<code>{_esc(item.product_id)}</code>", str(item.quantity),
            _esc(item.quantity_unit), _esc(item.procurement_note),
            (f'<a href="{_esc(item.source_url)}">manufacturer source</a>'
             if item.source_url else "—"),
            _esc(item.evidence),
        )
        for item in project.artifacts.hardware_schedule
    )
    return "<h2>Hardware schedule</h2>" + _table(
        ("System", "Kind", "Product", "Physical qty", "Unit",
         "Procurement meaning", "Source", "Evidence"), rows
    )


def _render_machining(project) -> str:
    def operation(item) -> str:
        if item.kind in {
            "confirmat_step_drill", "drawer_box_confirmat_step_drill",
        }:
            return (
                f"{_number(item.diameter_mm)} mm pilot / "
                f"{_number(item.width_mm)} mm shank / "
                f"{_number(item.length_mm)} mm countersink"
            )
        return item.kind

    def location_semantics(item) -> str:
        kind = item.kind.lower()
        if "groove" in kind or "notch" in kind:
            return "lower-left feature origin"
        if any(token in kind for token in (
            "bore", "drill", "fixing", "attachment",
        )):
            return "feature center"
        if "cut" in kind:
            return "cut origin"
        return "feature datum"

    def control_method(item) -> str:
        kind = item.kind.lower()
        if "groove" in kind:
            return "measured-stock offcut trial; sliding seated fit"
        if "confirmat" in kind:
            return "guided stepped drill and depth stop"
        if any(token in kind for token in (
            "hinge", "mounting_plate", "locking_device", "runner_fixing",
        )):
            return "named manufacturer template/instructions"
        if "notch" in kind:
            return "hard template; verify paired runner fit"
        return "marked datum plus sacrificial-backup trial"

    rows = tuple(
        (
            f"<code>{_esc(item.part_id)}</code>", _esc(operation(item)),
            (f"<code>{_esc(item.receiving_part_id)}</code>"
             if item.receiving_part_id else "—"),
            _esc(" × ".join(f"{value:g}" for value in item.location_mm)),
            _esc(location_semantics(item)),
            _esc(control_method(item)),
            _fmt(item.diameter_mm) if item.diameter_mm else "—",
            _fmt(item.depth_mm) if item.depth_mm else "—",
            _fmt(item.width_mm) if item.width_mm else "—",
            _fmt(item.length_mm) if item.length_mm else "—",
            str(item.count),
            _fmt(item.pitch_mm) if item.count > 1 else "—",
            _esc(item.pitch_axis or "—"),
            _esc(item.face or "—"),
            _esc(item.coordinate_system or "—"),
            f"<code>{_esc(item.source)}</code>",
        )
        for item in project.artifacts.machining_schedule
    )
    return (
        "<h2>Machining schedule</h2>"
        "<div class=\"notice\"><h3>Machining datum rules</h3>"
        "<p>Mark the physical origin and axes stated in each row before "
        "machining. Bore locations are centers; groove/notch locations are "
        "lower-left feature origins. The Location meaning column resolves every "
        "other operation explicitly. No generic numeric tolerance is invented: "
        "the row's Control method governs by template, depth stop, or measured-fit "
        "trial. Count repeats the stated location at the "
        "stated Pitch along the stated Pitch axis. For a "
        "Confirmat row, the target part receives the through-shank hole and "
        "countersink while the named Receiving part receives the centered "
        "blind pilot. Make a trial groove in offcut from the selected stock "
        "and verify a sliding, fully seated fit; do not assume nominal plywood "
        "equals measured thickness.</p></div>"
        + _table(
            ("Target id", "Operation", "Receiving part", "Start location",
             "Location meaning",
             "Control",
             "Pilot/diameter", "Depth", "Width/cutter",
             "Length/countersink", "Count", "Pitch", "Pitch axis", "Face",
             "Datum/template", "Source"),
            rows,
        )
    )


def _source_links(source: str) -> str:
    """Render a provenance list without turning several URLs into one bad href."""

    values = tuple(value.strip() for value in str(source).split(" | ")
                   if value.strip())
    if not values:
        return "—"
    rendered = []
    for index, value in enumerate(values, start=1):
        if value.startswith(("https://", "http://")):
            label = "source" if len(values) == 1 else f"source {index}"
            rendered.append(f'<a href="{_esc(value)}">{label}</a>')
        else:
            rendered.append(_esc(value))
    return " · ".join(rendered)


def _render_findings(project) -> str:
    finding_rows = tuple(
        (
            f"<code>{_esc(item.rule)}</code>",
            f'<span class="verdict {item.verdict.lower()}">{_esc(item.verdict)}</span>',
            _esc(item.severity), _esc(item.message), _esc(item.evidence_level),
        )
        for item in project.report.findings
    )
    evidence_rows = tuple(
        (
            f"<code>{_esc(item.evidence_id)}</code>", _esc(item.level),
            _esc(item.statement),
            _source_links(item.source),
            _esc(item.standard_ref or "—"),
        )
        for item in project.report.evidence
    )
    return (
        "<h2>Validation findings</h2>"
        + _table(("Rule", "Verdict", "Severity", "Message", "Evidence"), finding_rows)
        + "<h2>Evidence register</h2>"
        + _table(
            ("Evidence id", "Level", "Statement", "Source", "Standard/scope"),
            evidence_rows,
        )
    )


def _render_source_map(project) -> str:
    rows = tuple(
        (
            f"<code>{_esc(part_id)}</code>", _esc(provenance.declared_at),
            f"<code>{_esc(provenance.rule)}</code>",
            f"<code>{_esc(provenance.catalog_id or '—')}</code>",
            f"<code>{_esc(provenance.archetype_id or '—')}</code>",
            (f'<a href="{_esc(provenance.source_url)}">source</a>'
             if getattr(provenance, "source_url", "") else "—"),
        )
        for part_id, provenance in sorted(project.model.source_map.items())
    )
    return "<h2>Source map</h2>" + _table(
        ("Target id", "Declared at", "Rule", "Catalog", "Archetype", "Source"),
        rows,
    )


def _render_steps(title: str, steps) -> str:
    rows = tuple(
        (str(item.phase), f"<code>{_esc(item.step_id)}</code>",
         _esc(item.instruction), _esc(item.evidence))
        for item in steps
    )
    return f"<h2>{title}</h2>" + _table(
        ("Phase", "Step", "Instruction", "Evidence"), rows
    )


def _viewer_block(images, payload, glb_b64) -> str:
    slug = payload["slug"]
    payload_json = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    return f"""
<section class="viewer-section">
  <h2>Interactive assembly</h2>
  <p>Click a component to inspect its dimensions and fabrication record; use the
     explode control to separate the compiled parts. The scene contains every
     cut wood part and the two installation anchors; purchased runners, locks,
     stabilizers, pulls, screws, and glue remain schedule items or explicitly
     labeled schematic proxies, not false detailed geometry.</p>
  <div class="viewer-slot" data-detail="{_esc(slug)}">
    <img src="{images['isometric']}" alt="Interactive cabinetry assembly">
    <button type="button" class="viewer-btn">Explore in 3D</button>
  </div>
</section>
<script type="application/json" id="detail-data-{_esc(slug)}">{payload_json}</script>
<script type="text/plain" id="detail-glb-{_esc(slug)}">{glb_b64}</script>
"""


def _render_before_start(project) -> str:
    """A builder-first readiness sheet projected from selected adapters."""

    model = project.model
    bank = getattr(model, "drawer_bank", None)
    edge_band_net_mm = sum(item.length_mm for item in project.artifacts.edge_banding)
    tool_rows = []
    if bank is not None:
        tool_rows = [
            ("Safety and dust control",
             "Safety glasses and hearing protection; effective source dust "
             "extraction and respiratory protection selected for the panel "
             "product and tool. Follow the current tool/material instructions."),
            ("Layout and checking",
             "Metric rule/tape, marking knife or sharp pencil, two squares, "
             "straightedge, clamps, and diagonal measurement."),
            ("Sheet breakdown",
             "Table saw or track saw with a supported guide; router or table-saw "
             "groove setup; offcut for every fit trial."),
            ("Confirmat joinery",
             f'<a href="{_esc(bank.joinery_fastener.tooling_source_url)}">'
             f"Häfele {bank.joinery_fastener.tooling_sku}</a> guided/stepped "
             f"tooling for "
             f"{_number(bank.joinery_fastener.blind_pilot_diameter_mm)} mm pilot, "
             f"{_number(bank.joinery_fastener.through_shank_diameter_mm)} mm "
             f"shank, and "
             f"{_number(bank.joinery_fastener.countersink_diameter_mm)} mm "
             f"countersink; {bank.joinery_fastener.drive} driver bit; depth stops."),
            ("MOVENTO preparation",
             f"Blum {bank.locking_device.template_sku} template, Ø"
             f"{_number(bank.locking_device.pilot_bore_diameter_mm)} mm extension "
             f"bit, {', '.join(bank.runner.required_tool_skus)}, depth stops/"
             "collar, 50 × 13 mm back-notch template, and the selected "
             "runner/stabilizer instructions."),
            ("Fronts and pulls",
             f"Ø5 mm bit, sacrificial backer, spacers, clamps, and "
             f"{_number(bank.pull_product.hole_spacing_mm)} mm pull-layout check."),
            ("Installation",
             "Laser or spirit level, plumb reference, verified stud-locating "
             "method, shims at bearing points, drill/driver, and the scheduled "
             f"{model.wall_anchor.drive} bit."),
        ]
    else:
        joinery = next(
            row for row in model.machining if row.kind == "confirmat_step_drill"
        )
        joinery_product = get_assembly_fastener(joinery.source)
        tool_rows = [
            ("Safety and dust control",
             "Safety glasses and hearing protection; effective source dust "
             "extraction and respiratory protection selected for the panel "
             "product and tool. Follow the current tool/material instructions."),
            ("Layout and checking",
             "Metric rule/tape, marking knife or sharp pencil, two squares, "
             "straightedge, clamps, and diagonal measurement."),
            ("Sheet breakdown",
             "Table saw or track saw with a supported guide; router or "
             "table-saw groove setup; offcut for every fit trial."),
            ("Confirmat joinery",
             f'<a href="{_esc(joinery_product.tooling_source_url)}">Häfele '
             f"{_esc(joinery_product.tooling_sku)}</a> guided/stepped tooling "
             f"for {_number(joinery.diameter_mm)} mm "
             f"pilot, {_number(joinery.width_mm)} mm shank, and "
             f"{_number(joinery.length_mm)} mm countersink; depth stops and "
             f"a {joinery_product.drive} driver bit."),
            ("Doors and shelf",
             f"Ø{_number(model.hinge.cup_diameter_mm)} mm hinge-cup bit with "
             f"{_number(model.hinge.cup_depth_mm)} mm depth stop; System-32 "
             "boring jig/fence, Ø5 mm bit, sacrificial backer, and the "
             f"{model.hinge.sku} instructions."),
            ("Installation",
             "Laser or spirit level, plumb reference, verified stud-locating "
             "method, shims at bearing points, drill/driver, and the scheduled "
             f"{model.wall_anchor.drive} bit."),
        ]
    boundary_rows = (
        ("Primary declared panel record",
         f"{model.section.material_evidence.product}; verify supplier label, "
         "lot, actual thickness, finish face, and grain/face direction before cutting."),
        ("Cut parts", f"{len(project.artifacts.cut_list)} individually identified "
         "pieces; each row is one receiving/checkoff record."),
        ("Edge band", f"Net modeled application length {_fmt(edge_band_net_mm)}; "
         f"{model.profile.edge_band_thickness_mm:g} mm declared finished "
         "thickness is included in model dimensions and subtracted from raw "
         "cut sizes. Product/SKU, roll size, waste, and order allowance remain "
         "procurement gates."),
        ("Sheet purchasing", "Sheet nesting, kerf, yield, and sheet count are not "
         "derived in this pack increment; create and approve a nesting plan before purchase."),
        ("Field/by others", "Countertop and its attachment, wall repair, shims, "
         "scribe fillers, packaging, and finish touch-up are not supplied by this cut list."),
    )
    vocabulary_rows = (
        ("Cabinet side", "The main left or right carcass panel; older shop "
         "language may call this an end panel."),
        ("Drawer box front/back", "The structural 16 mm pieces between the two "
         "drawer-box sides."),
        ("Applied drawer front", "The visible decorative front attached after "
         "the drawer box is square; e.g. Bottom drawer front."),
        ("Drawer-box bottom", "The captured 12 mm panel in one drawer. Bottom "
         "drawer means the lowest complete drawer, not this panel."),
        ("Target / receiving part", "For stepped joinery the target receives "
         "the through-hole and countersink; the receiver gets the blind edge pilot."),
    )
    return (
        '<section class="before-start"><h2>Before you start</h2>'
        '<p class="lede">Do not begin fabrication until every required jig, '
        'selected material, manufacturer instruction, and unresolved field '
        'condition below has been checked. Machine dimensions are nominal '
        'model values; a named template or measured-fit trial controls where stated.</p>'
        '<h3>Required tools and jigs</h3>'
        + _table(("Work", "Requirement"), tuple(tool_rows))
        + '<h3>Material and inclusion boundary</h3>'
        + _table(("Category", "What this document proves or excludes"), boundary_rows)
        + '<h3>Vocabulary used everywhere</h3>'
        + _table(("Term", "Meaning"), vocabulary_rows)
        + '</section>'
    )


def _require_fabrication_release(project) -> None:
    if project.base_report is None or not project.fabrication_ready:
        raise ValueError("cabinetry report requires a fabrication-released project")


def _require_views(images: dict[str, str]) -> None:
    missing = set(REQUIRED_VIEWS) - images.keys()
    if missing:
        raise ValueError(f"missing cabinetry report views: {sorted(missing)}")


def _reader_css() -> str:
    """Responsive and print-safe base shared by all three reader surfaces."""

    return f"""
:root {{ --ink:#18212b; --muted:#5e6b78; --line:#bec8d0; --faint:#dde3e8;
  --sheet:#fff; --acc:#9b3a24; --acc-soft:#f7e9e5; --chipbg:#f3f5f6; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:#e9ecef; color:var(--ink);
  font:15px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }}
.sheet {{ width:min(1500px,100%); margin:0 auto; background:var(--sheet); padding:32px 38px 60px; }}
header {{ border-bottom:3px solid var(--ink); display:grid; grid-template-columns:2fr 1fr;
  gap:24px; padding-bottom:22px; }} h1 {{ font-size:clamp(30px,4vw,54px); line-height:1; margin:7px 0 12px; }}
h2 {{ margin:36px 0 12px; font-size:22px; border-bottom:1px solid var(--line); padding-bottom:7px; }}
.eyebrow, code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
.eyebrow {{ text-transform:uppercase; letter-spacing:.13em; color:var(--acc); font-weight:800; }}
.status-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; align-content:start; }}
.status {{ border:1px solid var(--line); padding:10px; }} .status b {{ display:block; }}
.unknown {{ color:#8a5200; }} .pass {{ color:#17633b; }} .fail {{ color:#a12622; }}
.gallery {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }}
figure {{ margin:0; border:1px solid var(--line); background:#fafafa; break-inside:avoid; }}
figure img,.viewer-slot img {{ display:block; width:100%; height:auto; }}
figcaption {{ padding:9px 11px; color:var(--muted); font-size:13px; }}
.viewer-section .viewer-slot {{ max-width:980px; aspect-ratio:4/3; background:#f8f8f6; overflow:hidden; }}
.table-wrap {{ overflow-x:auto; margin-bottom:14px; }} table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th,td {{ padding:7px 8px; border:1px solid var(--faint); text-align:left; vertical-align:top; }}
th {{ background:#eef1f3; font-size:11px; text-transform:uppercase; letter-spacing:.04em; }}
td code {{ font-size:10.5px; overflow-wrap:anywhere; }} a {{ color:var(--acc); }}
.verdict {{ font-weight:800; }} footer {{ margin-top:42px; padding-top:16px; border-top:2px solid var(--ink); color:var(--muted); }}
.notice,.before-start .lede {{ background:var(--acc-soft); border-left:4px solid var(--acc); padding:10px 14px; }}
.document-nav {{ display:flex; flex-wrap:wrap; gap:8px; margin:12px 0; }}
.document-nav a {{ display:inline-block; padding:7px 10px; border:1px solid var(--acc); border-radius:5px; font-weight:750; text-decoration:none; }}
.checklist li {{ margin:.45em 0; }}
@media (max-width:900px) {{ .sheet {{ padding:20px 16px 40px; }} header {{ grid-template-columns:1fr; }}
  .gallery {{ grid-template-columns:1fr 1fr; }} }}
@media (max-width:560px) {{ .gallery,.status-grid {{ grid-template-columns:1fr; }} }}
@media print {{ body {{ background:white; }} .sheet {{ width:100%; padding:0; }} .viewer-btn {{ display:none; }}
  .table-wrap {{ overflow:visible; }} section,table {{ break-inside:auto; }} tr,figure,.notice {{ break-inside:avoid; }} }}
"""


def _release_banner(project) -> str:
    try:
        whole = project.report.by_rule(
            "cabinetry.performance.whole_cabinet_capacity"
        )
        whole_verdict = whole.verdict
    except KeyError:
        whole_verdict = "UNKNOWN"
    policy = project.report.installation_use_policy
    install_verdict = "PASS" if project.installation_use_ready else "HOLD"
    install_copy = (
        "The typed installation/use gates pass for this project."
        if project.installation_use_ready else
        (policy.reader_notice(released=False) if policy is not None else
         "Installation/use remains blocked by active typed findings.")
    )
    policy_copy = ""
    if policy is not None:
        policy_copy = (
            f'<p><a href="{_esc(policy.source_url)}">CPSC Anchor It! general guidance</a>. '
            f'{_esc(policy.scope_note)} Scope source: '
            f'<a href="{_esc(policy.scope_source_url)}">CPSC clothing-storage-unit guidance</a>.</p>'
        )
    return (
        '<div class="status-grid">'
        f'<div class="status pass"><b>Model/shop-data gate: PASS</b>{_esc(project.report.summary)}</div>'
        '<div class="status unknown"><b>Purchasing/cutting preflight: OPEN</b>'
        'Sheet nesting and the final edge-band order remain open.</div>'
        f'<div class="status unknown"><b>Whole-cabinet structural capacity: {_esc(whole_verdict)}</b>'
        'Geometry does not qualify the complete cabinet/toe/anchor load path.</div>'
        f'<div class="status {"pass" if project.installation_use_ready else "fail"}">'
        f'<b>Installation/use release: {install_verdict}</b>{_esc(install_copy)}</div>'
        '</div>' + policy_copy
    )


def _procurement_preflight(project) -> str:
    net_edge_band_mm = sum(
        item.length_mm for item in project.artifacts.edge_banding
    )
    thicknesses = ", ".join(
        f"{value:g}" for value in sorted({
            item.thickness_mm for item in project.artifacts.cut_list
        })
    )
    product_ids = sorted({
        item.product_id for item in project.artifacts.edge_banding
    })
    products = ", ".join(product_ids) if product_ids else "no selected product"
    return (
        '<section class="notice"><h2>Purchasing/cutting preflight: OPEN</h2>'
        '<p><strong>Procurement HOLD — edge band:</strong> compiled net application '
        f'is {_fmt(net_edge_band_mm)} at {project.model.profile.edge_band_thickness_mm:g} mm '
        f'finished thickness ({_esc(products)}); select matching SKU, roll size, waste, '
        'and order allowance before purchase.</p>'
        '<p><strong>Procurement HOLD — sheet nesting:</strong> approve product/SKU, '
        f'finish, grain direction, kerf, nesting, yield, and sheet count for {_esc(thicknesses)} '
        'mm panels before purchase or cutting.</p>'
        '<p><strong>Field/by-others HOLD:</strong> countertop and attachment, wall repair, '
        'shims, fillers, packaging, and finish touch-up are excluded.</p></section>'
    )


def _document_nav(links: CabinetryDocumentLinks, documents: tuple[str, ...]) -> str:
    definitions = {
        "review": ("Review & installation sheet", links.review_href),
        "manual": ("Illustrated assembly manual", links.manual_href),
        "fabrication": ("Fabrication packet", links.fabrication_href),
        "audit": ("Review trace", links.audit_href),
    }
    return '<nav class="document-nav" aria-label="Related documents">' + "".join(
        f'<a href="{_esc(definitions[key][1])}">{_esc(definitions[key][0])}</a>'
        for key in documents
    ) + '</nav>'


def _drawing_figure(images: dict[str, str], view: str) -> str:
    return (
        f'<figure data-view="{_esc(view)}"><img src="{images[view]}" '
        f'alt="{_esc(view)} cabinetry view" loading="lazy">'
        f'<figcaption><strong>{_esc(view.replace("-", " ").title())}.</strong> '
        f'{_esc(VIEW_CAPTIONS[view])}</figcaption></figure>'
    )


def _review_drawings(images: dict[str, str]) -> str:
    views = ("front", "installation-plan", "anchor-section")
    return (
        '<section><h2>Drawings</h2><p>Printed dimensions and the compiled model '
        'control. Anchor coordinates are coordination geometry, not a capacity '
        'or installation-torque claim.</p><div class="gallery">'
        + "".join(_drawing_figure(images, view) for view in views)
        + '</div></section>'
    )


def _shop_drawings(images: dict[str, str]) -> str:
    views = ("front", "exploded", "drawer-detail")
    return (
        '<section><h2>Shop drawings</h2><p>Full-height surveyed wall studs are omitted '
        'from these shop views; installation geometry is owned by the review sheet.</p>'
        '<div class="gallery">'
        + "".join(_drawing_figure(images, view) for view in views)
        + '</div></section>'
    )


def _render_active_nonpass(project) -> str:
    rows = tuple(
        (
            f'<code>{_esc(item.rule)}</code>',
            f'<span class="verdict {item.verdict.lower()}">{_esc(item.verdict)}</span>',
            _esc(item.message),
        )
        for item in project.report.findings if item.verdict != "PASS"
    )
    return '<h2>Active gates</h2>' + _table(
        ("Rule", "Verdict", "Release meaning"), rows
    )


def _render_field_clearance_checklist(project) -> str:
    policy = project.report.installation_use_policy
    authority = (
        policy.clearance_authority if policy is not None
        else "the responsible project professional"
    )
    return (
        '<section><h2>Field verification and signed clearance</h2>'
        '<ul class="checklist">'
        '<li>Field-verify stud centers against the drawing before drilling.</li>'
        '<li>Record wall flatness, services, obstructions, and the highest floor point.</li>'
        '<li>Confirm stable bearing and record every required shim location in the field.</li>'
        '<li>Obtain signed, project-specific acceptance of the cabinet, toe-platform, '
        f'anchor, countertop, and service-load path from {_esc(authority)} before anchoring, '
        'loading, commissioning, or attaching the countertop.</li></ul></section>'
    )


def _render_installation_hardware(project) -> str:
    rows = tuple(
        (
            f'<code>{_esc(item.product_id)}</code>', str(item.quantity),
            _esc(item.procurement_note),
            f'<a href="{_esc(item.source_url)}">manufacturer source</a>',
        )
        for item in project.artifacts.hardware_schedule
        if item.kind == "wall_anchor_system"
    )
    return '<h2>Installation-only hardware</h2>' + _table(
        ("Selected product", "Qty", "Procurement meaning", "Source"), rows
    )


def build_cabinetry_review_html(
    project,
    *,
    images: dict[str, str],
    viewer_payload: dict,
    glb_b64: str,
    links: CabinetryDocumentLinks | None = None,
) -> str:
    """Compose the concise A0/I1 review and installation landing sheet."""

    _require_fabrication_release(project)
    _require_views(images)
    links = links or CabinetryDocumentLinks()
    cabinet = project.model.section.cabinets[0]
    title = project.project_doc.name
    nav = _document_nav(links, ("manual", "fabrication", "audit"))
    body = "".join((
        f'<header><div><div class="eyebrow">A0/I1 · project sheet & installation plan</div>'
        f'<h1>{_esc(title)}</h1><p>One model-backed review surface for fit, release, '
        f'field setout, and unloaded installation planning.</p>{nav}</div>'
        f'<div>{_release_banner(project)}<div class="status"><b>Product</b>'
        f'{_fmt(cabinet.width_mm)} W × {_fmt(cabinet.height_mm)} H × '
        f'{_fmt(cabinet.depth_mm)} D</div></div></header>',
        _procurement_preflight(project),
        f'<section>{_render_active_nonpass(project)}</section>',
        f'<section>{render_dimension_tables(project.model)}</section>',
        _review_drawings(images),
        _render_field_clearance_checklist(project),
        f'<section>{_render_installation_hardware(project)}</section>',
        f'<section>{_render_steps("Installation & commissioning", project.artifacts.installation_steps)}</section>',
        _viewer_block(images, viewer_payload, glb_b64),
        f'<footer>{nav}Generated from <code>{_esc(project.project_doc.name)}</code>. '
        'This coordination document is not a code approval or structural certification.</footer>',
    ))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:,">
<title>{_esc(title)} — Review & Installation Sheet</title><style>{_reader_css()}{viewer_css()}</style></head>
<body><main class="sheet">{body}</main>
<script>{vendor_js()}\n{viewer_js()}</script></body></html>"""


def build_cabinetry_fabrication_html(
    project,
    *,
    images: dict[str, str],
    links: CabinetryDocumentLinks | None = None,
) -> str:
    """Compose the detailed S1+ fabrication and assembly packet."""

    _require_fabrication_release(project)
    _require_views(images)
    links = links or CabinetryDocumentLinks()
    title = project.project_doc.name
    nav = _document_nav(links, ("review", "manual"))
    body = "".join((
        f'<header><div><div class="eyebrow">S1+ · fabrication packet</div>'
        f'<h1>{_esc(title)}</h1><p>Shop-owned cut, edge, hardware, machining, '
        f'fabrication, assembly, and shipping records.</p>{nav}</div>'
        f'<div>{_release_banner(project)}</div></header>',
        _procurement_preflight(project),
        _render_before_start(project),
        _shop_drawings(images),
        f'<section>{_render_part_key(project)}</section>',
        f'<section>{render_dimension_tables(project.model)}</section>',
        f'<section>{_render_cut_list(project)}{_render_edge_banding(project)}</section>',
        f'<section>{_render_hardware(project)}{_render_machining(project)}</section>',
        f'<section>{_render_steps("Fabrication", project.artifacts.fabrication_steps)}</section>',
        f'<section>{_render_steps("Assembly & shipping", project.artifacts.assembly_steps)}</section>',
        f'<footer>{nav}Generated from <code>{_esc(project.project_doc.name)}</code>. '
        'Use the review sheet for installation release and field setout.</footer>',
    ))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:,">
<title>{_esc(title)} — Fabrication Packet</title><style>{_reader_css()}</style></head>
<body><main class="sheet">{body}</main></body></html>"""


def build_cabinetry_audit_html(
    project,
    *,
    links: CabinetryDocumentLinks | None = None,
) -> str:
    """Compose the complete R1 validation/evidence/source review trace."""

    _require_fabrication_release(project)
    links = links or CabinetryDocumentLinks()
    title = project.project_doc.name
    nav = _document_nav(links, ("review",))
    counts = {}
    for finding in project.report.findings:
        counts[finding.verdict] = counts.get(finding.verdict, 0) + 1
    count_text = " · ".join(
        f"{verdict} {counts.get(verdict, 0)}"
        for verdict in ("PASS", "FAIL", "UNKNOWN")
    )
    body = "".join((
        f'<header><div><div class="eyebrow">R1 · review trace</div>'
        f'<h1>{_esc(title)}</h1><p>Complete validation, evidence, and source-map '
        f'trace. Verdict counts: {_esc(count_text)}.</p>{nav}</div>'
        f'<div>{_release_banner(project)}</div></header>',
        f'<section>{_render_findings(project)}</section>',
        f'<section>{_render_source_map(project)}</section>',
        f'<footer>{nav}Generated from <code>{_esc(project.project_doc.name)}</code>. '
        'Model and generator provenance are retained in the source map and direct links.</footer>',
    ))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:,">
<title>{_esc(title)} — Review Trace</title><style>{_reader_css()}</style></head>
<body><main class="sheet">{body}</main></body></html>"""


def build_cabinetry_html(project, *, images: dict[str, str],
                          viewer_payload: dict, glb_b64: str,
                          companion_href: str | None = None) -> str:
    """Compatibility wrapper for the focused review/install composer."""

    links = CabinetryDocumentLinks()
    if companion_href is not None:
        links = replace(
            links,
            manual_href=_relative_html_basename(
                companion_href, field="companion_href"
            ),
        )
    return build_cabinetry_review_html(
        project,
        images=images,
        viewer_payload=viewer_payload,
        glb_b64=glb_b64,
        links=links,
    )


def _png_data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def product_view_assembly(project) -> DetailAssembly:
    """Return the released product scene without full-height surveyed context.

    Site studs remain in the canonical assembly, validation, evidence, and
    installation schedule.  Excluding them only from the report scene keeps
    the cabinet at a useful scale while retaining its modeled wall anchors.
    """

    context_names = {
        part.name for part in project.model.parts
        if part.role.startswith("wall_stud_")
    }
    assembly = DetailAssembly(project.detail.assembly.name)
    assembly.parts = [
        part for part in project.detail.assembly.parts
        if part.name not in context_names
    ]
    return assembly


def product_viewer_payload(project, assembly: DetailAssembly,
                           instruction_manual=None) -> dict:
    """Project the canonical viewer metadata onto the product-only scene."""

    payload = build_viewer_payload(project.detail, instruction_manual)
    names = {part.name for part in assembly.parts}
    model_by_name = {part.name: part for part in project.model.parts}
    cut_by_part_id = {
        item.part_id: item for item in project.artifacts.cut_list
    }
    parts = {}
    for name, value in payload["parts"].items():
        if name not in names:
            continue
        row = dict(value)
        modeled = model_by_name.get(name)
        cut = cut_by_part_id.get(modeled.part_id) if modeled is not None else None
        if cut is not None:
            # A hover describes this identified piece.  Do not leak a pooled
            # base-language BOM-group quantity or generic material name into
            # the pack document when its canonical cut record is more exact.
            row["qty"] = cut.quantity
            row["material"] = cut.material
        parts[name] = row
    return {
        **payload,
        "parts": parts,
    }


def front_annotation_labels(project) -> dict[str, str]:
    """Canonical labels that the front drawing places on visible members."""

    labels = reader_labels_by_part_id(project)
    prefix = f"cabinetry.{project.model.section.cabinets[0].cabinet_id}."
    result = {
        "left_side": labels[prefix + "left_end"],
        "right_side": labels[prefix + "right_end"],
        "cabinet_bottom": labels[prefix + "bottom"],
        "toe_front": labels[prefix + "toe_front"],
    }
    drawer_bank = getattr(project.model, "drawer_bank", None)
    if drawer_bank is not None:
        for cell in drawer_bank.cells:
            result[f"drawer_{cell.cell_id}"] = labels[
                prefix + f"drawer_front_{cell.cell_id}"
            ]
    return result


def _render_front_drawing(project, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    model = project.model
    cabinet = model.section.cabinets[0]
    labels = front_annotation_labels(project)
    facts = installation_drawing_facts(project)
    fig, ax = plt.subplots(figsize=(8, 7), dpi=150)
    ax.add_patch(Rectangle((0, 0), cabinet.width_mm, cabinet.height_mm,
                           fill=False, linewidth=2.2, edgecolor="#18212b"))
    ax.plot((0, cabinet.width_mm), (cabinet.toe_kick_height_mm,
                                   cabinet.toe_kick_height_mm),
            color="#78838d", linewidth=1)
    strip = facts["anchor_strip_bounds_local_mm"]
    ax.add_patch(Rectangle(
        (strip["x"][0], strip["z"][0]),
        strip["x"][1] - strip["x"][0],
        strip["z"][1] - strip["z"][0],
        fill=False, linestyle="--", linewidth=1.2, edgecolor="#355e7c",
    ))
    if hasattr(model, "drawer_bank"):
        for cell in model.drawer_bank.cells:
            front = model.part(f"drawer_front_{cell.cell_id}")
            x = front.at_mm[0] - model.shell.x0_mm
            z = front.at_mm[2] - model.shell.base_z_mm
            ax.add_patch(Rectangle((x, z), front.length_mm, front.width_mm,
                                   facecolor="#d4b18a", edgecolor="#493a2e"))
            bores = [item for item in model.machining
                     if item.kind == "pull_bore" and item.part_id == front.part_id]
            if len(bores) == 2:
                xs = [x + item.location_mm[0] for item in bores]
                pull_z = z + bores[0].location_mm[1]
                ax.plot(xs, (pull_z, pull_z), color="#1a1a1a", linewidth=5,
                        solid_capstyle="round")
            ax.text(x + 14, z + front.width_mm - 10,
                    f"{labels['drawer_' + cell.cell_id]} · H {_fmt(front.width_mm)}",
                    ha="left", va="top", fontsize=8, color="#48392e",
                    bbox={"facecolor": "white", "edgecolor": "none", "alpha": .72,
                          "pad": 1.5})
    else:
        for role in ("door_left", "door_right"):
            part = model.part(role)
            ax.add_patch(Rectangle((part.at_mm[0] - model.parts[0].at_mm[0],
                                    part.at_mm[2]), part.length_mm, part.width_mm,
                                   facecolor="#d4b18a", edgecolor="#493a2e"))
    ax.annotate(_fmt(cabinet.width_mm), (cabinet.width_mm / 2, -28),
                ha="center", va="top")
    for anchor in facts["anchors"]:
        x = anchor["local_x_mm"]
        z = anchor["local_z_mm"]
        ax.axvline(x, color="#355e7c", linestyle=(0, (3, 4)), linewidth=.8)
        ax.scatter((x,), (z,), color="#9b3a24", s=22, zorder=5)
        ax.annotate(
            f"{anchor['stud_id']} / anchor\nX {_fmt(x)} · Z {_fmt(z)}",
            xy=(x, z), xytext=(x, cabinet.height_mm + 18),
            ha="center", va="bottom", fontsize=7,
            arrowprops={"arrowstyle": "-", "color": "#9b3a24"},
        )
    ax.annotate(
        labels["left_side"], xy=(0, cabinet.height_mm * .72),
        xytext=(-48, cabinet.height_mm * .82), ha="right", va="center",
        arrowprops={"arrowstyle": "-", "color": "#9b3a24"}, fontsize=8,
    )
    ax.annotate(
        labels["right_side"], xy=(cabinet.width_mm, cabinet.height_mm * .72),
        xytext=(cabinet.width_mm + 48, cabinet.height_mm * .82),
        ha="left", va="center",
        arrowprops={"arrowstyle": "-", "color": "#9b3a24"}, fontsize=8,
    )
    ax.annotate(
        labels["cabinet_bottom"],
        xy=(cabinet.width_mm * .24, cabinet.toe_kick_height_mm),
        xytext=(cabinet.width_mm * .20, cabinet.toe_kick_height_mm - 34),
        ha="center", va="top",
        arrowprops={"arrowstyle": "-", "color": "#9b3a24"}, fontsize=8,
    )
    ax.text(
        cabinet.width_mm * .72, cabinet.toe_kick_height_mm * .45,
        labels["toe_front"], ha="center", va="center", fontsize=8,
        color="#48392e",
    )
    high_floor = facts["high_floor_local_z_mm"]
    ax.plot((-34, cabinet.width_mm + 34), (high_floor, high_floor),
            color="#17633b", linewidth=1.3)
    ax.text(
        cabinet.width_mm * .5, high_floor - 8,
        "VERIFIED HIGH-FLOOR DATUM", ha="center", va="top",
        fontsize=7, color="#17633b", weight="bold",
    )
    ax.add_patch(Rectangle(
        (0, cabinet.height_mm), cabinet.width_mm, 26,
        fill=False, linestyle=(0, (5, 4)), linewidth=1.2,
        edgecolor="#9b3a24",
    ))
    ax.text(
        cabinet.width_mm / 2, cabinet.height_mm + 13,
        "FIELD INSTALLED / BY OTHERS / HOLD — COUNTERTOP BOUNDARY",
        ha="center", va="center", fontsize=7, color="#9b3a24", weight="bold",
    )
    ax.set_xlim(-55, cabinet.width_mm + 55)
    ax.set_ylim(-50, cabinet.height_mm + 62)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(
        "Installed front/setout elevation\n" + facts["drawing_stamp"],
        color="#9b3a24" if facts["installation_use_status"] == "HOLD" else "#18212b",
        fontsize=10,
    )
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def _render_installation_plan_drawing(project, path: Path) -> None:
    """Render a model-bound cabinet/wall/toe/stud coordination plan."""

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    facts = installation_drawing_facts(project)
    bounds = facts["cabinet_bounds_local_mm"]
    toe = facts["toe_footprint_local_mm"]
    width = bounds["x"][1]
    depth = bounds["y"][1]
    finish = facts["wall_finish_thickness_mm"]
    stud_width = facts["stud_width_mm"]
    stud_depth = facts["stud_depth_mm"]
    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=150)

    ax.add_patch(Rectangle(
        (0, 0), width, depth, facecolor="#f7f4ef",
        edgecolor="#18212b", linewidth=2.1,
    ))
    ax.add_patch(Rectangle(
        (toe["x"][0], toe["y"][0]),
        toe["x"][1] - toe["x"][0],
        toe["y"][1] - toe["y"][0],
        facecolor="none", edgecolor="#9b3a24", hatch="///", linewidth=1.2,
    ))
    ax.add_patch(Rectangle(
        (-45, depth), width + 90, finish,
        facecolor="#dadde0", edgecolor="#707b84", linewidth=1,
    ))
    ax.plot((-45, width + 45), (depth, depth), color="#18212b", linewidth=2)

    for anchor in facts["anchors"]:
        x = anchor["local_x_mm"]
        ax.add_patch(Rectangle(
            (x - stud_width / 2, depth + finish), stud_width, stud_depth,
            facecolor="#d8b58d", edgecolor="#493a2e", linewidth=1,
        ))
        head_y = depth + finish - facts["modeled_stack_mm"]
        ax.plot(
            (x, x), (head_y, head_y + facts["selected_screw_length_mm"]),
            color="#9b3a24", linewidth=2.2,
        )
        ax.scatter((x,), (head_y,), color="#9b3a24", s=25, zorder=5)
        ax.text(
            x, depth + finish + stud_depth + 12,
            f"{anchor['stud_id']}\nglobal X {_fmt(anchor['global_x_mm'])}\n"
            f"cabinet X {_fmt(anchor['local_x_mm'])}",
            ha="center", va="bottom", fontsize=7,
        )

    ax.annotate(
        "FRONT", xy=(width * .5, -70), xytext=(width * .5, -18),
        ha="center", va="top", color="#355e7c", weight="bold",
        arrowprops={"arrowstyle": "-|>", "color": "#355e7c"},
    )
    ax.text(
        width / 2, depth / 2,
        f"CABINET {facts['cabinet_id']}\n"
        f"{_fmt(width)} W × {_fmt(depth)} D\n"
        f"global left datum {_fmt(facts['cabinet_left_global_mm'])}",
        ha="center", va="center", fontsize=9,
        bbox={"facecolor": "white", "edgecolor": "#bec8d0", "alpha": .86},
    )
    ax.text(
        width / 2, (toe["y"][0] + toe["y"][1]) / 2,
        f"COMPILED TOE FOOTPRINT · front setback {_fmt(toe['y'][0])}",
        ha="center", va="center", fontsize=7, color="#9b3a24",
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": .74},
    )
    ax.text(
        -40, depth + finish / 2,
        f"WALL PLANE · wall-left datum {_fmt(facts['wall_left_datum_global_mm'])}",
        ha="left", va="center", fontsize=7, color="#18212b",
    )
    survey = (
        "FIELD SURVEY STRIP — verify wall flatness, services, obstructions, "
        "and every stud center before drilling"
    )
    ax.text(
        width / 2, depth + finish + stud_depth + 72, survey,
        ha="center", va="center", fontsize=8, color="#9b3a24", weight="bold",
        bbox={"facecolor": "#f7e9e5", "edgecolor": "#9b3a24", "pad": 5},
    )
    ax.text(
        width / 2, -112, facts["drawing_stamp"],
        ha="center", va="center", fontsize=8, color="#9b3a24", weight="bold",
    )
    ax.set_xlim(-60, width + 60)
    ax.set_ylim(-135, depth + finish + stud_depth + 105)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Installation plan — wall, cabinet, toe, studs, and anchors")
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def _render_anchor_section_drawing(project, path: Path) -> None:
    """Render the selected anchor path and toe bearing as a side section."""

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle

    facts = installation_drawing_facts(project)
    bounds = facts["cabinet_bounds_local_mm"]
    toe = facts["toe_footprint_local_mm"]
    depth = bounds["y"][1]
    height = bounds["z"][1]
    wall_finish = facts["wall_finish_thickness_mm"]
    stud_depth = facts["stud_depth_mm"]
    strip_t = facts["anchor_strip_thickness_mm"]
    anchor_z = facts["anchor_z_local_mm"]
    stud_front = depth + wall_finish
    head_y = stud_front - facts["modeled_stack_mm"]
    screw_end = head_y + facts["selected_screw_length_mm"]

    fig, ax = plt.subplots(figsize=(9, 7), dpi=150)
    ax.add_patch(Rectangle(
        (0, facts["toe_height_mm"]), depth,
        height - facts["toe_height_mm"],
        facecolor="#f7f4ef", edgecolor="#18212b", linewidth=2,
    ))
    ax.add_patch(Rectangle(
        (toe["y"][0], 0), toe["y"][1] - toe["y"][0],
        facts["toe_height_mm"],
        facecolor="none", edgecolor="#9b3a24", hatch="///", linewidth=1.2,
    ))
    ax.add_patch(Rectangle(
        (head_y, facts["anchor_strip_bounds_local_mm"]["z"][0]),
        strip_t,
        facts["anchor_strip_bounds_local_mm"]["z"][1]
        - facts["anchor_strip_bounds_local_mm"]["z"][0],
        facecolor="#d8b58d", edgecolor="#493a2e", linewidth=1.2,
    ))
    ax.add_patch(Rectangle(
        (depth, 0), wall_finish, height + 60,
        facecolor="#dadde0", edgecolor="#707b84", linewidth=1,
    ))
    ax.add_patch(Rectangle(
        (stud_front, 0), stud_depth, height + 60,
        facecolor="#d8b58d", edgecolor="#493a2e", linewidth=1,
    ))
    ax.plot((head_y, screw_end), (anchor_z, anchor_z),
            color="#9b3a24", linewidth=4, solid_capstyle="round")
    ax.scatter((head_y,), (anchor_z,), color="#9b3a24", s=40, zorder=5)
    ax.plot((-24, depth + wall_finish + stud_depth + 24), (0, 0),
            color="#17633b", linewidth=1.4)
    ax.add_patch(Polygon(
        ((toe["y"][0] + 30, 0), (toe["y"][0] + 55, 0),
         (toe["y"][0] + 42.5, 15)),
        closed=True, facecolor="#f2d28b", edgecolor="#8a5200",
    ))
    ax.text(
        toe["y"][0] + 42.5, 24,
        "FIELD-LOCATE SHIM ONLY AT STABLE BEARING",
        ha="center", va="bottom", fontsize=6.5, color="#8a5200",
    )
    ax.add_patch(Rectangle(
        (0, height), depth, 30, fill=False, linestyle=(0, (5, 4)),
        edgecolor="#9b3a24", linewidth=1.2,
    ))
    ax.text(
        depth / 2, height + 15,
        "COUNTERTOP · FIELD INSTALLED / BY OTHERS / HOLD",
        ha="center", va="center", fontsize=7, color="#9b3a24", weight="bold",
    )
    ax.annotate(
        f"SELECTED SCREW {_fmt(facts['selected_screw_length_mm'])}\n"
        f"{facts['selected_screw_name']}",
        xy=((head_y + screw_end) / 2, anchor_z),
        xytext=(depth * .38, anchor_z - 105), ha="center", va="top",
        fontsize=8, arrowprops={"arrowstyle": "-", "color": "#9b3a24"},
    )
    ax.text(
        depth + wall_finish / 2, height * .55,
        f"WALL FINISH {_fmt(wall_finish)}\nNO ANCHORAGE CREDIT",
        ha="center", va="center", rotation=90, fontsize=7,
        color="#9b3a24", weight="bold",
    )
    ax.text(
        stud_front + stud_depth / 2, height * .52,
        f"SURVEYED STUD\nMODELED EMBEDMENT {_fmt(facts['stud_embedment_mm'])}",
        ha="center", va="center", rotation=90, fontsize=7, color="#493a2e",
    )
    ax.text(
        head_y + facts["modeled_stack_mm"] / 2, anchor_z + 30,
        f"MODELED STACK {_fmt(facts['modeled_stack_mm'])}",
        ha="center", va="bottom", fontsize=8, color="#355e7c", weight="bold",
    )
    ax.text(
        depth * .42, facts["toe_height_mm"] / 2,
        f"TOE H {_fmt(facts['toe_height_mm'])} · SETBACK {_fmt(facts['toe_setback_mm'])}",
        ha="center", va="center", fontsize=7,
    )
    ax.text(
        depth * .5, -48, facts["drawing_stamp"],
        ha="center", va="center", fontsize=8, color="#9b3a24", weight="bold",
    )
    ax.set_xlim(-35, depth + wall_finish + stud_depth + 40)
    ax.set_ylim(-70, height + 90)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(
        "Anchor/toe section — coordination geometry only; no capacity or torque claim"
    )
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def _render_exploded_drawing(project, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    model = project.model
    cabinet = model.section.cabinets[0]
    labels = reader_labels_by_part_id(project)
    fig, axes = plt.subplots(1, 2, figsize=(15, 7), dpi=150)
    ax = axes[0]
    ax.add_patch(Rectangle((0, 0), cabinet.width_mm, cabinet.height_mm,
                           fill=False, linewidth=2, edgecolor="#18212b"))
    if hasattr(model, "drawer_bank"):
        for index, cell in enumerate(reversed(model.drawer_bank.cells)):
            front = model.part(f"drawer_front_{cell.cell_id}")
            shift = 80 + index * 80
            z = front.at_mm[2] - model.shell.base_z_mm
            ax.add_patch(Rectangle((shift, z), front.length_mm * .82,
                                   front.width_mm, facecolor="#d4b18a",
                                   edgecolor="#493a2e", alpha=.9))
            ax.add_patch(Rectangle((shift + 20, z + 18),
                                   model.drawer_bank.outside_box_width_mm * .72,
                                   cell.box_height_mm, fill=False,
                                   edgecolor="#9b3a24", linewidth=1.5))
            ax.text(
                shift + 5, z + front.width_mm + 10,
                labels[front.part_id], color="#9b3a24", fontsize=8,
                weight="bold",
            )
    ax.set_xlim(-40, cabinet.width_mm + 280)
    ax.set_ylim(-40, cabinet.height_mm + 70)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Drawer-bank groups — offsets are diagrammatic")

    detail = axes[1]
    if hasattr(model, "drawer_bank"):
        prefix = f"cabinetry.{cabinet.cabinet_id}."
        cell_id = model.drawer_bank.cells[0].cell_id
        roles = {
            "applied": f"drawer_front_{cell_id}",
            "front": f"drawer_{cell_id}_front",
            "back": f"drawer_{cell_id}_back",
            "left": f"drawer_{cell_id}_side_left",
            "right": f"drawer_{cell_id}_side_right",
            "bottom": f"drawer_{cell_id}_bottom",
        }
        parts = {key: labels[prefix + role] for key, role in roles.items()}
        patches = {
            "applied": Rectangle((.10, .03), .80, .10,
                                 facecolor="#d4b18a", edgecolor="#493a2e"),
            "front": Rectangle((.20, .23), .60, .06,
                               facecolor="#e4c9a8", edgecolor="#493a2e"),
            "bottom": Rectangle((.23, .36), .54, .30,
                                facecolor="#ead9bf", edgecolor="#9b3a24"),
            "left": Rectangle((.14, .33), .06, .48,
                              facecolor="#d4b18a", edgecolor="#493a2e"),
            "right": Rectangle((.80, .33), .06, .48,
                               facecolor="#d4b18a", edgecolor="#493a2e"),
            "back": Rectangle((.23, .77), .54, .06,
                              facecolor="#e4c9a8", edgecolor="#493a2e"),
        }
        for item in patches.values():
            detail.add_patch(item)
        callouts = {
            "applied": ((.50, .08), (.50, -.02), "center", "top"),
            "front": ((.50, .26), (.50, .17), "center", "top"),
            "bottom": ((.50, .51), (.50, .51), "center", "center"),
            "left": ((.17, .57), (.02, .57), "left", "center"),
            "right": ((.83, .57), (.98, .57), "right", "center"),
            "back": ((.50, .80), (.50, .92), "center", "bottom"),
        }
        for key, (xy, text_xy, horizontal, vertical) in callouts.items():
            detail.annotate(
                parts[key], xy=xy, xytext=text_xy, xycoords="axes fraction",
                textcoords="axes fraction", ha=horizontal, va=vertical,
                fontsize=8,
                arrowprops={"arrowstyle": "-", "color": "#9b3a24"},
            )
        detail.text(
            .5, .98,
            "One typical drawer; all six labels match the cut list and 3D hover",
            transform=detail.transAxes, ha="center", va="top", fontsize=8,
            color="#48392e",
        )
    detail.set_xlim(0, 1)
    detail.set_ylim(-.08, 1.02)
    detail.set_aspect("equal")
    detail.axis("off")
    detail.set_title("Typical drawer — exploded construction map")
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def _render_drawer_detail(project, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    model = project.model
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), dpi=150)
    if hasattr(model, "drawer_bank"):
        bank = model.drawer_bank
        cell = bank.cells[0]
        detail = drawer_detail_geometry(model)
        side_thickness = model.part("drawer_top_side_left").thickness_mm
        bottom_thickness = detail["bottom_thickness_mm"]
        runner = bank.runner
        stabilizer = bank.stabilizer
        pull = bank.pull_product
        locking = bank.locking_device
        ax = axes[0]
        ax.add_patch(Rectangle((0, 0), bank.outside_box_width_mm,
                               cell.box_height_mm, fill=False, linewidth=2))
        ax.add_patch(Rectangle((detail["bottom_front_origin_mm"],
                                runner.bottom_recess_mm),
                               detail["bottom_blank_width_mm"], bottom_thickness,
                               facecolor="#d4b18a", edgecolor="#9b3a24"))
        pull_center = bank.outside_box_width_mm / 2
        pull_y = cell.box_height_mm * .72
        pull_left = pull_center - pull.hole_spacing_mm / 2
        pull_right = pull_center + pull.hole_spacing_mm / 2
        ax.plot((pull_left, pull_right), (pull_y, pull_y),
                color="#1f1f1f", linewidth=4)
        ax.scatter((pull_left, pull_right), (pull_y, pull_y),
                   color="#1f1f1f", s=18)
        ax.scatter((side_thickness, bank.outside_box_width_mm - side_thickness),
                   (5, 5), color="#355e7c", marker="s", s=32)
        ax.text(bank.outside_box_width_mm / 2, cell.box_height_mm / 2,
                f"outside {_fmt(bank.outside_box_width_mm)}\n"
                f"inside {_fmt(bank.inside_box_width_mm)}\n"
                f"bottom blank {_fmt(detail['bottom_blank_width_mm'])}\n"
                f"pull CTC {_fmt(detail['pull_hole_spacing_mm'])}\n"
                f"locks {locking.left_sku} / {locking.right_sku}",
                ha="center", va="center")
        ax.set_title("Front section and hardware proxies")
        ax = axes[1]
        back_width = bank.inside_box_width_mm
        notch_width, notch_height = detail["rear_notch_mm"]
        ax.add_patch(Rectangle((0, 0), back_width, cell.box_height_mm,
                               fill=False, linewidth=2))
        for x in (0, back_width - notch_width):
            ax.add_patch(Rectangle(
                (x, 0), notch_width, notch_height,
                facecolor="white", edgecolor="#9b3a24", hatch="///",
                linewidth=1.5,
            ))
        hook_x = [point[0] for point in detail["rear_hook_centers_mm"]]
        hook_y = [point[1] for point in detail["rear_hook_centers_mm"]]
        ax.scatter(hook_x, hook_y, color="#355e7c", s=38, zorder=3)
        ax.text(back_width / 2, cell.box_height_mm / 2,
                f"DRAWER BACK — rear face\n"
                f"two {_number(notch_width)} × {_number(notch_height)} mm notches\n"
                f"Ø{runner.hook_bore_mm[0]:g} × {runner.hook_bore_mm[1]:g} mm hook bores\n"
                f"centers ({_number(hook_x[0])}, {_number(hook_y[0])}) and "
                f"({_number(hook_x[1])}, {_number(hook_y[1])}) mm\n"
                "origin = lower-left corner",
                ha="center", va="center")
        ax.set_title("Drawer back — notch and hook preparation")

        ax = axes[2]
        ax.add_patch(Rectangle((0, 0), bank.outside_box_width_mm,
                               bank.box_length_mm, fill=False, linewidth=2))
        rack_x = side_thickness * 1.5
        rack_length = min(stabilizer.gear_rack_length_mm, bank.box_length_mm)
        for x in (rack_x, bank.outside_box_width_mm - rack_x):
            ax.plot((x, x), (0, rack_length), color="#9b3a24", linewidth=4)
        linkage_length = bank.opening_width_mm - stabilizer.linkage_rod_cut_deduction_mm
        linkage_left = (bank.outside_box_width_mm - linkage_length) / 2
        linkage_y = rack_length * .55
        ax.plot((linkage_left, linkage_left + linkage_length),
                (linkage_y, linkage_y), color="#355e7c", linewidth=4)
        ax.text(bank.outside_box_width_mm / 2, bank.box_length_mm * .8,
                f"gear racks {_fmt(stabilizer.gear_rack_length_mm)}\n"
                f"linkage rod {_fmt(linkage_length)}\n"
                f"opening − {_fmt(stabilizer.linkage_rod_cut_deduction_mm)}",
                ha="center", va="center")
        ax.set_title("Lateral stabilizer cut schematic")
        # These are machining schematics, not scaled elevations. Keeping an
        # equal data aspect compresses a ~1 m drawer width into a strip too
        # shallow to read. Let each panel use its available height while the
        # printed dimensions remain the controlling geometry.
        axes[0].set_xlim(-30, bank.outside_box_width_mm + 30)
        axes[0].set_ylim(-15, max(cell.box_height_mm * 1.25, 160))
        axes[1].set_xlim(-30, bank.inside_box_width_mm + 30)
        axes[1].set_ylim(-15, max(cell.box_height_mm * 1.25, 160))
        axes[2].set_xlim(-30, bank.outside_box_width_mm + 30)
        axes[2].set_ylim(-25, bank.box_length_mm + 40)
        for ax in axes:
            ax.set_aspect("auto")
            ax.axis("off")
        fig.suptitle(
            "Purchased hardware is shown as schematic visual proxies; "
            "proxies are not capacity geometry. Panels are not to scale; "
            "printed dimensions control.",
            fontsize=10,
        )
    else:
        axes[0].text(.5, .5, "Door/hinge detail is listed in the machining schedule.",
                     ha="center", va="center", transform=axes[0].transAxes)
        axes[1].axis("off")
        axes[2].axis("off")
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def _render_views(project, assembly: DetailAssembly, out_dir: Path) -> dict[str, str]:
    views_dir = out_dir / "views"
    views_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "front": views_dir / "front.png",
        "installation-plan": views_dir / "installation_plan.png",
        "anchor-section": views_dir / "anchor_section.png",
        "isometric": views_dir / "isometric.png",
        "exploded": views_dir / "exploded.png",
        "drawer-detail": views_dir / "drawer_detail.png",
    }
    _render_front_drawing(project, paths["front"])
    _render_installation_plan_drawing(project, paths["installation-plan"])
    _render_anchor_section_drawing(project, paths["anchor-section"])
    export_png(assembly, paths["isometric"], view="iso", size=(1200, 900))
    _render_exploded_drawing(project, paths["exploded"])
    _render_drawer_detail(project, paths["drawer-detail"])
    return {name: _png_data_uri(path) for name, path in paths.items()}


def _web_glb_bytes(assembly: DetailAssembly, work_dir: Path) -> bytes:
    work_dir.mkdir(parents=True, exist_ok=True)
    path = export_glb(
        assembly, work_dir / "cabinetry.web.glb",
        tolerance=0.4, angular_tolerance=0.6,
    )
    return path.read_bytes()


def _glb_b64(glb_bytes: bytes) -> str:
    return base64.b64encode(
        gzip.compress(glb_bytes, compresslevel=9, mtime=0)
    ).decode("ascii")


def _web_glb_b64(assembly: DetailAssembly, work_dir: Path) -> str:
    """Compatibility helper returning the viewer's deterministic payload."""

    return _glb_b64(_web_glb_bytes(assembly, work_dir))


def render_shared_product_assets(
    project,
    out_dir: str | Path,
    *,
    instruction_manual=None,
) -> CabinetrySharedAssets:
    """Render the product scene, six views, payload, and GLB exactly once."""

    _require_fabrication_release(project)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    assembly = product_view_assembly(project)
    images = _render_views(project, assembly, out_dir)
    payload = product_viewer_payload(project, assembly, instruction_manual)
    glb_bytes = _web_glb_bytes(assembly, out_dir / "_glb")
    return CabinetrySharedAssets(assembly, images, payload, glb_bytes)


def generate_build_document(project_path: str | Path, out_path: str | Path) -> Path:
    project_path = Path(project_path)
    out_path = Path(out_path)
    project = compile_project_file(project_path)
    project.require_fabrication_release()
    return generate_released_build_document(project, out_path)


def generate_released_build_document(
    project,
    out_path: str | Path,
    *,
    companion_href: str | None = None,
    instruction_manual=None,
) -> Path:
    """Render one fabrication-released project without recompiling it."""

    if project.base_report is None or not project.fabrication_ready:
        raise ValueError(
            "cabinetry report requires a fabrication-released project"
        )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    assets = render_shared_product_assets(
        project, out_path.parent, instruction_manual=instruction_manual,
    )
    document = build_cabinetry_html(
        project,
        images=assets.images,
        viewer_payload=assets.viewer_payload,
        glb_b64=_glb_b64(assets.glb_bytes),
        companion_href=companion_href,
    )
    out_path.write_text(document, encoding="utf-8")
    return out_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    written = generate_build_document(args.project, args.out)
    print(f"wrote {written} ({written.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
