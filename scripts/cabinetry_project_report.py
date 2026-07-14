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
from detailgen.assemblies.assembly import DetailAssembly  # noqa: E402
from detailgen.rendering.export import export_glb, export_png  # noqa: E402
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
                f"{cell.rated_moving_load_lb:.2f} lb",
            )
            for cell in bank.cells
        )
        product = _table(("Drawer-bank dimension", "Value", "Derivation"), bank_rows)
        cells = _table(
            ("Cell", "Front height", "Box height", "Contents", "Moving rated load"),
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
    }


def _render_cut_list(project) -> str:
    rows = tuple(
        (
            f"<code>{_esc(item.part_id)}</code>", _esc(item.role),
            _fmt(item.length_mm), _fmt(item.width_mm), _fmt(item.thickness_mm),
            _esc(item.material), _esc(item.source_rule),
        )
        for item in project.artifacts.cut_list
    )
    return "<h2>Cut list</h2>" + _table(
        ("Part id", "Role", "Length", "Width", "Thickness", "Material", "Rule"),
        rows,
    )


def _render_edge_banding(project) -> str:
    rows = tuple(
        (f"<code>{_esc(item.part_id)}</code>", _esc(item.edge),
         _fmt(item.length_mm), _esc(item.material))
        for item in project.artifacts.edge_banding
    )
    return "<h2>Edge banding</h2>" + _table(
        ("Part id", "Edge", "Length", "Material"), rows
    )


def _render_hardware(project) -> str:
    rows = tuple(
        (
            f"<code>{_esc(item.system_id)}</code>", _esc(item.kind),
            f"<code>{_esc(item.product_id)}</code>", str(item.quantity),
            (f'<a href="{_esc(item.source_url)}">manufacturer source</a>'
             if item.source_url else "—"),
            _esc(item.evidence),
        )
        for item in project.artifacts.hardware_schedule
    )
    return "<h2>Hardware schedule</h2>" + _table(
        ("System", "Kind", "Product", "Qty", "Source", "Evidence"), rows
    )


def _render_machining(project) -> str:
    rows = tuple(
        (
            f"<code>{_esc(item.part_id)}</code>", _esc(item.kind),
            _esc(" × ".join(f"{value:g}" for value in item.location_mm)),
            _fmt(item.diameter_mm) if item.diameter_mm else "—",
            _fmt(item.depth_mm) if item.depth_mm else "—",
            _fmt(item.length_mm) if item.length_mm else "—",
            _esc(item.face or "—"),
            _esc(item.coordinate_system or "—"),
            f"<code>{_esc(item.source)}</code>",
        )
        for item in project.artifacts.machining_schedule
    )
    return "<h2>Machining schedule</h2>" + _table(
        ("Target id", "Operation", "Location", "Diameter", "Depth", "Length",
         "Face", "Datum/template", "Source"),
        rows,
    )


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
            (f'<a href="{_esc(item.source)}">source</a>'
             if str(item.source).startswith("http") else _esc(item.source or "—")),
        )
        for item in project.report.evidence
    )
    return (
        "<h2>Validation findings</h2>"
        + _table(("Rule", "Verdict", "Severity", "Message", "Evidence"), finding_rows)
        + "<h2>Evidence register</h2>"
        + _table(("Evidence id", "Level", "Statement", "Source"), evidence_rows)
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
     explode control to separate the compiled parts.</p>
  <div class="viewer-slot" data-detail="{_esc(slug)}">
    <img src="{images['isometric']}" alt="Interactive DB40 assembly">
    <button type="button" class="viewer-btn">Explore in 3D</button>
  </div>
</section>
<script type="application/json" id="detail-data-{_esc(slug)}">{payload_json}</script>
<script type="text/plain" id="detail-glb-{_esc(slug)}">{glb_b64}</script>
"""


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
                          viewer_payload: dict, glb_b64: str) -> str:
    """Pure HTML composition from one already-released PackedProject."""

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
{viewer_css()}
@media (max-width:900px) {{ .sheet {{ padding:20px 16px 40px; }} header {{ grid-template-columns:1fr; }}
  .gallery {{ grid-template-columns:1fr 1fr; }} }}
@media (max-width:560px) {{ .gallery,.status-grid {{ grid-template-columns:1fr; }} }}
@media print {{ body {{ background:white; }} .sheet {{ width:100%; padding:0; }} .viewer-btn {{ display:none; }} }}
"""
    body = "".join((
        f"""<header><div><div class="eyebrow">cabinetry.frameless@1 · model-backed build document</div>
<h1>{_esc(title)}</h1><p>Fabrication, assembly, conventional shipping, installation,
and commissioning data generated from the expanded pack model and the unchanged
DetailSpec assembly.</p></div><div class="status-grid">
<div class="status"><b>Pack release: PASS</b>{_esc(project.report.summary)}</div>
<div class="status"><b>Base geometry: {base_text}</b>Collision, contact, connectivity, and intrinsic checks.</div>
<div class="status unknown"><b>Whole-cabinet structural capacity</b>{whole_text}</div>
<div class="status"><b>Product</b>{_fmt(cabinet.width_mm)} W × {_fmt(cabinet.height_mm)} H × {_fmt(cabinet.depth_mm)} D</div>
</div></header>""",
        _gallery(images),
        _viewer_block(images, viewer_payload, glb_b64),
        f"<section>{render_dimension_tables(project.model)}</section>",
        f"<section>{_render_cut_list(project)}{_render_edge_banding(project)}</section>",
        f"<section>{_render_hardware(project)}{_render_machining(project)}</section>",
        f"<section>{_render_findings(project)}</section>",
        f"<section>{_render_source_map(project)}</section>",
        f"<section>{_render_steps('Fabrication', project.artifacts.fabrication_steps)}</section>",
        f"<section>{_render_steps('Assembly & shipping', project.artifacts.assembly_steps)}</section>",
        f"<section>{_render_steps('Installation & commissioning', project.artifacts.installation_steps)}</section>",
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


def product_viewer_payload(project, assembly: DetailAssembly) -> dict:
    """Project the canonical viewer metadata onto the product-only scene."""

    payload = build_viewer_payload(project.detail)
    names = {part.name for part in assembly.parts}
    return {
        **payload,
        "parts": {
            name: value for name, value in payload["parts"].items()
            if name in names
        },
    }


def _render_front_drawing(project, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    model = project.model
    cabinet = model.section.cabinets[0]
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
                    f"{cell.cell_id} · H {_fmt(front.width_mm)}",
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
    ax.set_xlim(-55, cabinet.width_mm + 55)
    ax.set_ylim(-50, cabinet.height_mm + 40)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Front elevation — model dimensions and pull centers")
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
    fig, ax = plt.subplots(figsize=(9, 6), dpi=150)
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
            ax.text(shift + 5, z + front.width_mm + 10, cell.cell_id,
                    color="#9b3a24", fontsize=9, weight="bold")
    ax.set_xlim(-40, cabinet.width_mm + 280)
    ax.set_ylim(-40, cabinet.height_mm + 70)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Exploded front/box groups — offsets are diagrammatic")
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
        ax.add_patch(Rectangle((0, 0), bank.box_length_mm, cell.box_height_mm,
                               fill=False, linewidth=2))
        ax.add_patch(Rectangle((detail["bottom_side_origin_mm"],
                                runner.bottom_recess_mm),
                               detail["bottom_blank_depth_mm"],
                               bottom_thickness,
                               facecolor="#d4b18a", edgecolor="#9b3a24"))
        ax.plot((0, detail["runner_physical_length_mm"]), (3, 3),
                color="#355e7c", linewidth=3)
        ax.plot((bank.box_length_mm - runner.minimum_rear_notch_mm,
                 bank.box_length_mm), (0, 0),
                color="#9b3a24", linewidth=4)
        ax.text(bank.box_length_mm / 2, cell.box_height_mm / 2,
                f"{_fmt(bank.box_length_mm)} nominal\n"
                f"{_fmt(runner.minimum_rear_notch_mm)} rear notch\n"
                f"Ø{runner.hook_bore_mm[0]:g} × {runner.hook_bore_mm[1]:g} mm hook bore\n"
                f"{runner.hook_bore_inset_from_side_mm:g} mm inset · "
                f"{runner.hook_bore_height_from_bottom_mm:g} mm high\n"
                f"runner physical {_fmt(detail['runner_physical_length_mm'])}",
                ha="center", va="center")
        ax.set_title("Side and rear preparation")

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
        for ax in axes:
            ax.set_aspect("equal")
            ax.autoscale_view()
            ax.axis("off")
        fig.suptitle(
            "Purchased hardware is shown as schematic visual proxies; "
            "proxies are not capacity geometry.",
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
    project.require_release()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    assembly = product_view_assembly(project)
    images = _render_views(project, assembly, out_path.parent)
    payload = product_viewer_payload(project, assembly)
    glb_b64 = _web_glb_b64(assembly, out_path.parent / "_glb")
    document = build_cabinetry_html(
        project, images=images, viewer_payload=payload, glb_b64=glb_b64
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
