#!/usr/bin/env python3
"""Generate one self-contained build document from a packed cabinetry project."""

from __future__ import annotations

import argparse
import base64
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
    "front", "side", "plan", "isometric", "exploded", "drawer-detail"
)
VIEW_CAPTIONS = {
    "front": "Dimensioned front elevation with progressive fronts and centered pulls.",
    "side": "Right elevation of the compiled product assembly.",
    "plan": "Plan view showing cabinet depth and installation anchors.",
    "isometric": "Compiled product assembly; use Explore in 3D to isolate and explode parts.",
    "exploded": "Drawer-bank exploded diagram, grouped by stable top/middle/bottom identity.",
    "drawer-detail": (
        "Typical MOVENTO wood-drawer geometry with runner and lateral-stabilizer preparation."
    ),
}


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
    <img src="{images['isometric']}" alt="Interactive DB40 assembly">
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


def _gallery(images) -> str:
    figures = []
    for view in REQUIRED_VIEWS:
        figures.append(
            f'<figure data-view="{_esc(view)}"><img src="{images[view]}" '
            f'alt="{_esc(view)} cabinetry view" loading="lazy">'
            f'<figcaption><strong>{_esc(view.replace("-", " ").title())}.</strong> '
            f'{_esc(VIEW_CAPTIONS[view])}</figcaption></figure>'
        )
    return (
        '<section><h2>Drawings</h2><p>Full-height surveyed wall studs are omitted '
        'from these product views for legibility; the canonical model, anchor '
        'validation, evidence register, and installation instructions retain them.</p>'
        '<div class="gallery">' + "".join(figures) + "</div></section>"
    )


def build_cabinetry_html(project, *, images: dict[str, str],
                          viewer_payload: dict, glb_b64: str,
                          companion_href: str | None = None) -> str:
    """Pure HTML composition from one fabrication-released PackedProject."""

    if project.base_report is None or not project.fabrication_ready:
        raise ValueError(
            "cabinetry report requires a fabrication-released project"
        )
    missing = set(REQUIRED_VIEWS) - images.keys()
    if missing:
        raise ValueError(f"missing cabinetry report views: {sorted(missing)}")
    cabinet = project.model.section.cabinets[0]
    whole = project.report.by_rule("cabinetry.performance.whole_cabinet_capacity") \
        if hasattr(project.model, "drawer_bank") else None
    whole_text = ("UNKNOWN — not qualified" if whole is not None
                  else "UNKNOWN — physical qualification not performed")
    base_text = ("PASS" if project.base_report is not None and project.base_report.ok
                 else "NOT RUN")
    title = project.project_doc.name
    if companion_href is not None and (
        Path(companion_href).name != companion_href
        or not companion_href.endswith(".html")
    ):
        raise ValueError("companion_href must be a relative HTML basename")
    companion_link = (
        f'<a class="companion-link" href="{_esc(companion_href)}">'
        "Open the illustrated assembly manual →</a>"
        if companion_href else ""
    )
    if project.installation_use_ready:
        installation_status = (
            '<div class="status pass"><b>Installation/use release: PASS</b>'
            "The typed pack and base-language installation/use gates pass for "
            "this project.</div>"
        )
    else:
        policy = project.report.installation_use_policy
        hold_text = (
            policy.reader_notice(released=False) if policy is not None
            else "Installation/use remains blocked by the active typed findings."
        )
        installation_status = (
            '<div class="status fail"><b>Installation/use release: HOLD</b>'
            + _esc(hold_text)
            + '</div>'
        )
    css = f"""
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
figure {{ margin:0; border:1px solid var(--line); background:#fafafa; }}
figure img,.viewer-slot img {{ display:block; width:100%; height:auto; }}
figcaption {{ padding:9px 11px; color:var(--muted); font-size:13px; }}
.viewer-section .viewer-slot {{ max-width:980px; aspect-ratio:4/3; background:#f8f8f6; overflow:hidden; }}
.table-wrap {{ overflow-x:auto; margin-bottom:14px; }} table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th,td {{ padding:7px 8px; border:1px solid var(--faint); text-align:left; vertical-align:top; }}
th {{ background:#eef1f3; font-size:11px; text-transform:uppercase; letter-spacing:.04em; }}
td code {{ font-size:10.5px; overflow-wrap:anywhere; }} a {{ color:var(--acc); }}
.verdict {{ font-weight:800; }} footer {{ margin-top:42px; padding-top:16px; border-top:2px solid var(--ink); color:var(--muted); }}
.notice,.before-start .lede {{ background:var(--acc-soft); border-left:4px solid var(--acc); padding:10px 14px; }}
.companion-link {{ display:inline-block;margin-top:9px;padding:8px 11px;
  border:1px solid var(--acc);border-radius:6px;font-weight:800;text-decoration:none; }}
{viewer_css()}
@media (max-width:900px) {{ .sheet {{ padding:20px 16px 40px; }} header {{ grid-template-columns:1fr; }}
  .gallery {{ grid-template-columns:1fr 1fr; }} }}
@media (max-width:560px) {{ .gallery,.status-grid {{ grid-template-columns:1fr; }} }}
@media print {{ body {{ background:white; }} .sheet {{ width:100%; padding:0; }} .viewer-btn {{ display:none; }} }}
"""
    body = "".join((
        f"""<header><div><div class="eyebrow">cabinetry.frameless@1 · model-backed build document</div>
<h1>{_esc(title)}</h1><p>Fabrication, assembly, conventional shipping, and installation-planning
data generated from the expanded pack model and the unchanged
DetailSpec assembly.</p>{companion_link}</div><div class="status-grid">
<div class="status"><b>Fabrication/model gate: PASS</b>{_esc(project.report.summary)}</div>
<div class="status"><b>Base geometry: {base_text}</b>Collision, contact, connectivity, and intrinsic checks.</div>
<div class="status unknown"><b>Whole-cabinet structural capacity</b>{whole_text}</div>
{installation_status}
<div class="status"><b>Product</b>{_fmt(cabinet.width_mm)} W × {_fmt(cabinet.height_mm)} H × {_fmt(cabinet.depth_mm)} D</div>
</div></header>""",
        _render_before_start(project),
        _gallery(images),
        _viewer_block(images, viewer_payload, glb_b64),
        f"<section>{_render_part_key(project)}</section>",
        f"<section>{render_dimension_tables(project.model)}</section>",
        f"<section>{_render_cut_list(project)}{_render_edge_banding(project)}</section>",
        f"<section>{_render_hardware(project)}{_render_machining(project)}</section>",
        f"<section>{_render_steps('Fabrication', project.artifacts.fabrication_steps)}</section>",
        f"<section>{_render_steps('Assembly & shipping', project.artifacts.assembly_steps)}</section>",
        f"<section>{_render_steps('Installation & commissioning', project.artifacts.installation_steps)}</section>",
        f"<section>{_render_findings(project)}</section>",
        f"<section>{_render_source_map(project)}</section>",
        f"<footer>Generated from <code>{_esc(project.project_doc.name)}</code>. "
        "Manufacturer ratings apply only under their documented product conditions; "
        "this document is not a code approval or structural certification.</footer>",
    ))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:,">
<title>{_esc(title)} — Build Document</title><style>{css}</style></head>
<body><main class="sheet">{body}</main>
<script>{vendor_js()}\n{viewer_js()}</script></body></html>"""


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
    fig, ax = plt.subplots(figsize=(8, 7), dpi=150)
    ax.add_patch(Rectangle((0, 0), cabinet.width_mm, cabinet.height_mm,
                           fill=False, linewidth=2.2, edgecolor="#18212b"))
    ax.plot((0, cabinet.width_mm), (cabinet.toe_kick_height_mm,
                                   cabinet.toe_kick_height_mm),
            color="#78838d", linewidth=1)
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
    ax.set_xlim(-55, cabinet.width_mm + 55)
    ax.set_ylim(-50, cabinet.height_mm + 40)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Front elevation — canonical reader labels and pull centers")
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
        "side": views_dir / "side.png",
        "plan": views_dir / "plan.png",
        "isometric": views_dir / "isometric.png",
        "exploded": views_dir / "exploded.png",
        "drawer-detail": views_dir / "drawer_detail.png",
    }
    _render_front_drawing(project, paths["front"])
    export_png(assembly, paths["side"], view="right", size=(1200, 900))
    export_png(assembly, paths["plan"], view="top", size=(1200, 900))
    export_png(assembly, paths["isometric"], view="iso", size=(1200, 900))
    _render_exploded_drawing(project, paths["exploded"])
    _render_drawer_detail(project, paths["drawer-detail"])
    return {name: _png_data_uri(path) for name, path in paths.items()}


def _web_glb_b64(assembly: DetailAssembly, work_dir: Path) -> str:
    work_dir.mkdir(parents=True, exist_ok=True)
    path = export_glb(
        assembly, work_dir / "cabinetry.web.glb",
        tolerance=0.4, angular_tolerance=0.6,
    )
    return base64.b64encode(
        gzip.compress(path.read_bytes(), compresslevel=9, mtime=0)
    ).decode("ascii")


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
    assembly = product_view_assembly(project)
    images = _render_views(project, assembly, out_path.parent)
    payload = product_viewer_payload(project, assembly, instruction_manual)
    glb_b64 = _web_glb_b64(assembly, out_path.parent / "_glb")
    document = build_cabinetry_html(
        project, images=images, viewer_payload=payload, glb_b64=glb_b64,
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
