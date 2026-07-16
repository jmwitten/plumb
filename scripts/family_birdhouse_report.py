#!/usr/bin/env python3
"""Generate the complete model-backed family-birdhouse review package."""

from __future__ import annotations

import argparse
import csv
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
import hashlib
from html import escape
import json
from pathlib import Path
import shutil
import sys
from time import perf_counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np


_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))

import single_detail_report as SDR

from detailgen.core.units import IN
from detailgen.design_review import (
    load_design_review_file,
    render_design_review_html,
    validate_design_review,
)
from detailgen.rendering.instruction_manual import render_instruction_manual_html
from detailgen.rendering.instruction_panels import (
    DisplayRow,
    JoinPresentation,
    RelatedDocumentLink,
    build_instruction_manual,
)
from detailgen.rendering.instruction_render import DEFAULT_SIZE, render_instruction_images
from detailgen.spec.compiler import compile_spec_file


SPEC = _REPO / "details" / "family_birdhouse.spec.yaml"
REVIEW = _REPO / "details" / "family_birdhouse.design-review.yaml"
DEFAULT_OUT_DIR = _REPO / "outputs" / "family_birdhouse"

TECHNICAL_BASENAME = "family_birdhouse_technical.html"
MANUAL_BASENAME = "family_birdhouse_family_build_guide.html"
FABRICATION_BASENAME = "family_birdhouse_fabrication_guide.html"
INSTALLATION_BASENAME = "family_birdhouse_installation_service_guide.html"
DESIGN_REVIEW_BASENAME = "family_birdhouse_design_review.html"
BOM_CSV_BASENAME = "family_birdhouse_bom.csv"
CUT_CSV_BASENAME = "family_birdhouse_cut_list.csv"
PACKAGE_MANIFEST_BASENAME = "family_birdhouse_package_manifest.json"
PREVIEW_NOTICE = "PREVIEW — NOT APPROVED FOR DELIVERY"

BIRDHOUSE_JOIN_PRESENTATION = JoinPresentation(
    title="Bench assembly complete — field installation remains on hold",
    instructions=(
        "Confirm all 21 modeled screws are installed and the pivoting cleanout "
        "side opens, closes, and latches without binding.",
        "Stop after the bench build. An adult must resolve every hold in the "
        "separate installation and service guide before mounting the box.",
    ),
    honesty=(
        "FIELD HOLD — pole, predator baffle, clamp/U-bolt interface, soil and "
        "foundation conditions, frost and wind, utilities, coating, and "
        "installation fastener capacity are not selected or analyzed.",
    ),
    tools=(DisplayRow("fit", "Adult review of the installation hold checklist"),),
)

VIEW_FILES = {
    "iso": "iso.png",
    "front": "front.png",
    "side": "cleanout_side.png",
    "top": "top.png",
    "exploded": "exploded.png",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fmt_in(value_mm: float) -> str:
    value = value_mm / IN
    return f"{value:g} in"


def _is_cedar_component(component) -> bool:
    return component.material_key == "cedar"


def _is_ordinary_wood_screw(component) -> bool:
    return "ordinary_wood_screw" in component.capability_tags()


def _part_polys(part, isolated_world_solid):
    """Tessellate an isolated copy, never ``part.world_solid()``'s cache."""
    vertices, triangles = isolated_world_solid.val().tessellate(0.12)
    values = np.array([[v.x, v.y, v.z] for v in vertices], dtype=float)
    return values, tuple(tuple(triangle) for triangle in triangles)


@contextmanager
def _record_phase(phases: dict[str, float], name: str):
    started = perf_counter()
    try:
        yield
    finally:
        phases[name] = perf_counter() - started


def _shade(base, faces, alpha=1.0):
    light = np.array([-0.4, -0.5, 0.9])
    light /= np.linalg.norm(light)
    colors = []
    for face in faces:
        normal = np.cross(face[1] - face[0], face[2] - face[0])
        length = np.linalg.norm(normal)
        normal = normal / length if length > 1e-9 else np.array([0, 0, 1.0])
        strength = 0.48 + 0.52 * abs(float(np.dot(normal, light)))
        colors.append((*[channel * strength for channel in base], alpha))
    return colors


def _part_color(part):
    if _is_ordinary_wood_screw(part.component):
        return (0.50, 0.53, 0.58)
    if part.name == "sloped oversized roof":
        return (0.53, 0.25, 0.12)
    if part.name == "pole mounting cleat":
        return (0.76, 0.49, 0.26)
    if part.name == "pivoting cleanout side":
        return (0.86, 0.57, 0.28)
    return (0.69, 0.39, 0.19)


def _configure_still_axis(axis, low, high, *, elev, azim, title):
    axis.set_xlim(low[0], high[0])
    axis.set_ylim(low[1], high[1])
    axis.set_zlim(low[2], high[2])
    axis.set_box_aspect(tuple(high - low))
    axis.view_init(elev=elev, azim=azim)
    axis.set_proj_type("ortho")
    axis.set_axis_off()
    axis.set_title(title, fontsize=10)


def _still_edge_style() -> dict:
    return {"edgecolors": "none", "linewidths": 0.0}


def render_family_birdhouse_views(
    detail,
    out_dir: str | Path,
) -> tuple[Path, ...]:
    """Render five model-derived views from the compiled CadQuery solids."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    detail.build()
    meshes = [
        (part, *_part_polys(part, isolated_world_solid))
        for part, isolated_world_solid in (
            detail.assembly.isolated_world_solids()
        )
    ]
    explode = {
        name: tuple(value * IN for value in vector)
        for name, vector in detail.explode_vectors().items()
    }
    written: list[Path] = []

    def draw(filename, elev, azim, title, *, ghost=(), exploded=False):
        parts = []
        all_vertices = []
        for part, base_vertices, triangles in meshes:
            offset = explode.get(part.name, (0.0, 0.0, 0.0)) if exploded else (0, 0, 0)
            vertices = base_vertices + np.array(offset, dtype=float)
            faces = [vertices[list(triangle)] for triangle in triangles]
            all_vertices.append(vertices)
            parts.append((part, faces))
        vertices = np.vstack(all_vertices)
        low, high = vertices.min(0), vertices.max(0)
        span = np.maximum(high - low, 1.0)
        margin = span * 0.08
        low, high = low - margin, high + margin

        figure = plt.figure(figsize=(7.2, 6.2), dpi=135)
        axis = figure.add_subplot(111, projection="3d")
        for part, faces in parts:
            is_ghost = part.name in ghost
            collection = Poly3DCollection(
                faces,
                facecolors=_shade(
                    _part_color(part), faces, 0.18 if is_ghost else 1.0
                ),
                **_still_edge_style(),
            )
            axis.add_collection3d(collection)
        _configure_still_axis(
            axis,
            low,
            high,
            elev=elev,
            azim=azim,
            title=title,
        )
        figure.tight_layout()
        path = out_dir / filename
        figure.savefig(path)
        plt.close(figure)
        written.append(path)

    draw("iso.png", 24, -55, "ISO — closed cedar birdhouse")
    draw("front.png", 6, -90, "FRONT — 1 1/8 in entrance, no perch")
    draw(
        "cleanout_side.png",
        8,
        0,
        "CLEANOUT SIDE — two upper pivots + lower latch",
        ghost=("pivoting cleanout side",),
    )
    draw("top.png", 82, -90, "TOP — roof overhang and screw pattern")
    draw("exploded.png", 24, -55, "EXPLODED — model-derived part separation", exploded=True)
    return tuple(written)


def _document_links(current: str) -> str:
    links = (
        (TECHNICAL_BASENAME, "Technical model + interactive 3D"),
        (MANUAL_BASENAME, "Family build guide"),
        (FABRICATION_BASENAME, "Adult fabrication guide"),
        (INSTALLATION_BASENAME, "Adult installation + service guide"),
    )
    return "<nav class='doc-nav' aria-label='Package documents'>" + "".join(
        f"<a href='{escape(href)}'>{escape(label)}</a>"
        for href, label in links
        if href != current
    ) + "</nav>"


def _base_document(title: str, current: str, body: str, *, preview: bool) -> str:
    notice = (
        f"<aside class='preview' role='alert'>{escape(PREVIEW_NOTICE)}</aside>"
        if preview else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>
:root{{--ink:#172033;--muted:#4b5563;--line:#cbd5e1;--cedar:#8b451f;--soft:#fff8ef}}
*{{box-sizing:border-box}} body{{margin:0;background:#e5e7eb;color:var(--ink);font:15px/1.48 system-ui,sans-serif}}
main{{max-width:980px;margin:auto;background:white;min-height:100vh;padding:30px 38px 48px}}
.preview{{position:sticky;top:0;z-index:4;padding:12px;text-align:center;background:#7f1d1d;color:white;font-weight:900}}
.doc-nav{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px}} .doc-nav a{{padding:8px 11px;border:1px solid #94a3b8;border-radius:8px;color:#1d4ed8;font-weight:750;text-decoration:none}}
h1,h2,h3{{line-height:1.18}} h1{{color:var(--cedar)}} .hold{{border:3px solid #b91c1c;background:#fff1f2;padding:14px 18px;border-radius:10px}}
.safe{{border-left:5px solid #15803d;background:#f0fdf4;padding:10px 15px}} .adult{{border-left:5px solid #b91c1c;background:#fff1f2;padding:10px 15px}}
table{{width:100%;border-collapse:collapse;margin:14px 0 24px}} th,td{{border:1px solid var(--line);padding:8px;vertical-align:top;text-align:left}} th{{background:#f8fafc}}
code{{word-break:break-all}} footer{{margin-top:32px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted)}}
@media(max-width:650px){{main{{padding:20px 16px}} table{{font-size:12px}}}}
@media print{{body{{background:white}} main{{max-width:none;padding:.45in}} .preview{{position:static}} .doc-nav{{display:none}} a{{color:black}} footer{{display:none}}}}
</style></head><body>{notice}<main>{_document_links(current)}{body}
<footer>Generated {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')} from the governed Plumb DetailSpec. Geometry authority: compiled model and fabrication records.</footer>
</main></body></html>"""


def _technical_extra_section() -> str:
    return f"""
<section class="notes family-boundary">
  <h2>Family work boundary and package navigation</h2>
  <p><strong>ADULT-ONLY:</strong> every saw cut, entrance/vent/drain bore,
  pilot setup, sharp-edge correction, pole operation, lift, and field installation.</p>
  <p><strong>CHILD-SUITABLE with direct adult supervision:</strong> measure,
  mark, match labels, sand already-prepared exterior edges, decorate exterior
  faces only, sort fasteners, and finish selected pre-started screws.</p>
  <p>The compiled enclosure has one 1 1/8 inch entrance, four high side vents,
  four floor drains, a rough interior below the entrance, and no exterior perch.</p>
  <p><strong>FIELD HOLD:</strong> pole, predator baffle, clamps/U-bolts,
  soil/foundation, frost, wind, utilities, coating, and service access remain
  unselected and unproved. Connection capacity NOT analyzed.</p>
  {_document_links(TECHNICAL_BASENAME)}
</section>"""


def _register_technical_consumer(out_dir: Path) -> None:
    views_dir = out_dir / "views"
    panel = {
        "letter": "A",
        "title": "Family Cedar Birdhouse",
        "sub": "pivot-side chickadee/wren box with a field-held pole interface",
        "views": ["iso", "front", "side", "top", "exploded"],
        "captions": {
            "iso": "Closed model: six primary cedar enclosure pieces plus the separate mounting cleat.",
            "front": "Entrance face: one 1 1/8 inch bore, rough interior below it, and no exterior perch.",
            "side": "Ghosted service panel: two aligned upper pivot screws and one lower front latch screw.",
            "top": "Oversized single-slope roof: 1 inch side overhang and protected wall-top ventilation wedge.",
            "exploded": "Exploded offsets come from the DetailSpec manifest; every still and interactive mesh shares the same compiled solids.",
        },
        "why": (
            "WHY THE CLASSIC PIVOT SIDE?",
            "It preserves ordinary square cedar preparation, a familiar six-board enclosure, meaningful child-safe participation, and tool-light annual cleaning without adding specialized hinges.",
        ),
        "narrative": [
            "The body is {body_w:g}in wide and deep. A {floor_w:g}in square floor is recessed {floor_recess:g}in above the wall bottoms; the front and sides are {wall_h:g}in high, and the extended back reaches {back_h:g}in.",
            "The {entrance_dia:g}in entrance, four {vent_dia:g}in vents, and four {drain_dia:g}in drains are nine distinct bore operations in the fabrication records.",
            "Two upper screws act only as pivots and one lower screw only as a latch. Plumb carries no fixed-joint or load-path claim across the cleanout side.",
            "Pole stability, predator resistance, wind, fastener capacity, coating selection, and site suitability remain explicit field holds.",
        ],
        "fieldnotes": [
            ("Pre-cut verification.", "Measure actual dressed cedar thickness before cutting the {floor_w:g}in floor or drilling pivot pilots; the model is based on {cedar_thk:g}in stock."),
            ("Adult cutting/drilling.", "An adult owns every saw and bore. Clamp each labeled part, back up the entrance cut, and keep the four drain and four vent paths open."),
            ("Child work.", "Children may transfer story-stick marks, sand prepared exterior edges, decorate exterior faces only, match labels, sort hardware, and finish selected pre-started screws under direct supervision."),
            ("Cleanout.", "Support the side, loosen only the lower front latch screw, swing the lower edge out around the two upper pivots, clean after nesting season, dry, close, and hand-retighten."),
            ("Installation hold.", "Do not field-mount until the actual pole, baffle, clamp, soil/foundation, frost, wind, utilities, and service clearance are accepted from field/product evidence."),
        ],
    }
    SDR.CONSUMERS[SPEC.name] = {
        "name": "family_birdhouse",
        "spec": SPEC,
        "panel": panel,
        "views_dir": views_dir,
        "view_files": VIEW_FILES,
        "store": None,
        "design_store": None,
        "title": "Family Cedar Birdhouse — Model-Backed Technical Document",
        "title_block": {
            "eyebrow": "Family Build · Outdoor Nest Box",
            "h1": "Family Cedar Birdhouse",
            "lede": "A governed pivot-side chickadee/wren nest box. Every drawing, cut operation, fastener, dimension, and interactive mesh below comes from one validated Plumb model.",
            "scale": "Model-derived; verify actual dressed stock",
            "stock": "Untreated 3/4in cedar + ordinary corrosion-resistant exterior screws; pole/baffle system held",
        },
        "buy_lede": (
            "Modeled enclosure only: seven cedar pieces (six primary box parts plus "
            "one pole-interface cleat), fifteen 1-1/2-inch exterior screws, and six "
            "2-1/4-inch roof screws. Pole, baffle, clamps, coating, and site work "
            "remain FIELD HOLD items rather than invented BOM rows."
        ),
        "footer": {
            "byline": "Witten Dacha · Family Cedar Birdhouse",
            "tagline": "Drawings and numbers generated from one governed Plumb model",
            "regen_cmd": ".venv/bin/python scripts/family_birdhouse_report.py --preview",
            "render_note": "model-derived CadQuery meshes; offline matplotlib stills",
        },
        "cut_note_context": "",
        "extra_sections": (_technical_extra_section(),),
        "render_views": render_family_birdhouse_views,
        "ensure_views": lambda: None,
    }


def _fabrication_html(detail, selection_fp: str, model_fp: str, *, preview: bool) -> str:
    rows = []
    for part in detail.assembly.parts:
        component = part.component
        if not _is_cedar_component(component):
            continue
        record = component.fabrication_record(part.id)
        bores = [step for step in record.steps if step.kind == "bore"]
        rows.append(
            "<tr>"
            f"<td>{escape(part.name)}</td>"
            f"<td>{escape(_fmt_in(component.length))} × {escape(_fmt_in(component.width))} × {escape(_fmt_in(component.thickness))}</td>"
            f"<td>{len(bores)}</td>"
            f"<td>{escape(record.fab_note() or 'Square crosscut only; preserve labeled show face.')}</td>"
            "</tr>"
        )
    body = f"""
<h1>Adult Fabrication Guide</h1>
<p>This cut/boring schedule is projected from the compiled fabrication records,
not redrawn from a static sketch. Selection fingerprint <code>{selection_fp}</code>;
model fingerprint <code>{model_fp}</code>.</p>
<div class="adult"><strong>ADULT-ONLY:</strong> all sawing, the 1 1/8 inch
entrance, four high side vents, four floor drains, every pilot/countersink,
and every sharp-edge correction.</div>
<div class="safe"><strong>CHILD-SUITABLE after adult preparation:</strong>
transfer story-stick marks, check labels, sand prepared exterior edges, decorate
exterior faces only, sort screws, and finish selected pre-started screws with
direct supervision.</div>
<h2>Seven cedar pieces</h2>
<table><thead><tr><th>Part</th><th>Finished size</th><th>Bores</th><th>Model-derived operation note</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<h2>Shop order</h2><ol>
<li>Verify actual cedar thickness and flatness. Stop if it differs materially from 3/4 inch; recalculate the captured floor and pilot stations before cutting.</li>
<li>Adult labels and square-cuts all seven pieces. Preserve the interior/show-face marks.</li>
<li>Adult bores the entrance with backup stock, then drills two vents in each side and four floor drains. Break splinters without smoothing the rough bird-facing climbing surface.</li>
<li>Dry-fit the recessed floor, fixed side, moving side, roof, and cleat. Confirm the cleanout side can move before decoration.</li>
<li>Children complete only the green-boundary tasks above. Keep coating off the interior, entrance rim, vents, drains, seams, and mounting faces.</li>
</ol>
<div class="hold"><strong>STOP:</strong> exact screw product, coating compatibility,
pilot chart, clutch/torque, and connection capacity NOT analyzed. Select from the
purchased fastener manufacturer's cedar/exposure data.</div>"""
    return _base_document(
        "Family Birdhouse — Adult Fabrication Guide",
        FABRICATION_BASENAME,
        body,
        preview=preview,
    )


def _installation_html(detail, selection_fp: str, model_fp: str, *, preview: bool) -> str:
    ns = detail.namespace
    body = f"""
<h1>Adult Installation + Seasonal Service Guide</h1>
<p>The wooden model ends at the {ns['body_w']:g}in × {ns['cleat_h']:g}in ×
{ns['cedar_thk']:g}in cedar cleat on the extended back. Selection fingerprint
<code>{selection_fp}</code>; model fingerprint <code>{model_fp}</code>.</p>
<div class="hold"><h2>FIELD HOLD — do not install yet</h2>
<p>The actual freestanding metal pole, commercial predator baffle, clamps or
U-bolts, cleat interface, soil/foundation, frost, wind exposure, underground
and overhead utilities, setbacks, coating, and adult service clearance are not
selected or verified. Pole stability, wind capacity, connection capacity,
predator resistance, and site suitability are NOT analyzed.</p></div>
<h2>Adult release record</h2>
<table><tbody>
<tr><th>Pole and baffle product/revision</th><td>____________________________</td></tr>
<tr><th>Manufacturer mounting method and limits</th><td>____________________________</td></tr>
<tr><th>Clamp/U-bolt and cleat detail</th><td>____________________________</td></tr>
<tr><th>Soil/foundation/frost acceptance</th><td>____________________________</td></tr>
<tr><th>Utility/site/wind check</th><td>____________________________</td></tr>
<tr><th>Adult installer/date</th><td>____________________________</td></tr>
</tbody></table>
<h2>Conditional adult installation sequence</h2><ol>
<li>Resolve and record every hold above from the purchased product instructions and dacha field conditions.</li>
<li>Assemble the pole, foundation, and predator baffle exactly to their accepted manufacturer/site detail. Do not improvise through the nesting cavity.</li>
<li>Keep the pivoting cleanout side reachable. Attach only through the separate rear cleat using the accepted clamp/interface detail.</li>
<li>Adult lifts the empty box, secures it, verifies plumb/level and all clearances, then checks that roof, vents, drains, entrance, latch, and service swing remain unobstructed.</li>
<li>Record a final empty-box movement check. This is an inspection, not proof of wind or predator capacity.</li>
</ol>
<h2>Seasonal cleanout</h2><ol>
<li>Adult confirms the nesting season is over and the box is empty before opening.</li>
<li>Support the cleanout side. Loosen only the lower front latch screw; do not remove the two upper pivot screws.</li>
<li>Swing the lower edge outward, remove old nesting material, inspect for damage, and let the cavity dry.</li>
<li>Keep the rough interior, 1 1/8 inch entrance, four high side vents, four floor drains, and no exterior perch condition intact.</li>
<li>Close the side, hand-retighten the latch, and record cedar-thread wear or hardware replacement.</li>
</ol>
<div class="adult"><strong>ADULT-ONLY:</strong> every pole/baffle operation,
ladder or lift, site/utility check, installation, and seasonal opening.</div>"""
    return _base_document(
        "Family Birdhouse — Adult Installation and Service Guide",
        INSTALLATION_BASENAME,
        body,
        preview=preview,
    )


def _write_bom_csv(detail, path: Path) -> None:
    fields = ("item", "qty", "material", "dimensions", "assumptions", "ids")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in detail.bom_table():
            writer.writerow({
                **{field: row.get(field, "") for field in fields},
                "ids": ";".join(row.get("ids", ())),
            })


def _write_cut_csv(detail, path: Path) -> None:
    fields = (
        "part_id",
        "part_name",
        "stock_profile",
        "length_in",
        "width_in",
        "thickness_in",
        "bore_count",
        "fabrication_note",
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for part in detail.assembly.parts:
            component = part.component
            if not _is_cedar_component(component):
                continue
            record = component.fabrication_record(part.id)
            writer.writerow({
                "part_id": part.id,
                "part_name": part.name,
                "stock_profile": record.stock.profile,
                "length_in": f"{component.length / IN:g}",
                "width_in": f"{component.width / IN:g}",
                "thickness_in": f"{component.thickness / IN:g}",
                "bore_count": sum(step.kind == "bore" for step in record.steps),
                "fabrication_note": record.fab_note(),
            })


def build_family_birdhouse_package(
    out_dir: str | Path = DEFAULT_OUT_DIR,
    *,
    image_size: tuple[int, int] = DEFAULT_SIZE,
    spec_path: str | Path = SPEC,
    preview: bool = True,
) -> dict:
    """Build the governed package; refuse unconfirmed customer delivery."""
    total_started = perf_counter()
    phases: dict[str, float] = {}
    spec_path = Path(spec_path)
    with _record_phase(phases, "compile_validate"):
        detail = compile_spec_file(spec_path)
        report = detail.validate()
        if preview:
            detail.require_modeling_approval()
        else:
            detail.require_delivery_ready()

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model_dir = out_dir / "model"
    with _record_phase(phases, "documentation_export"):
        detail.render_documentation(model_dir)

    _register_technical_consumer(out_dir)
    technical_path = out_dir / TECHNICAL_BASENAME
    manual_path = out_dir / MANUAL_BASENAME
    fabrication_path = out_dir / FABRICATION_BASENAME
    installation_path = out_dir / INSTALLATION_BASENAME
    design_review_path = out_dir / DESIGN_REVIEW_BASENAME
    bom_path = out_dir / BOM_CSV_BASENAME
    cut_path = out_dir / CUT_CSV_BASENAME

    with _record_phase(phases, "still_views"):
        render_family_birdhouse_views(detail, out_dir / "views")

    phase_started = perf_counter()
    related = (
        RelatedDocumentLink("Technical model + interactive 3D", TECHNICAL_BASENAME),
        RelatedDocumentLink("Adult fabrication guide", FABRICATION_BASENAME),
        RelatedDocumentLink("Adult installation + service guide", INSTALLATION_BASENAME),
    )
    manual = build_instruction_manual(
        detail,
        TECHNICAL_BASENAME,
        title="Family Cedar Birdhouse — Illustrated Family Build Guide",
        basename=MANUAL_BASENAME,
        lede=(
            "One machine-checked bench sequence from the governed Plumb model. "
            "ADULT-ONLY: cuts, bores, pilot setup, sharp tools, lifting, and field "
            "installation. CHILD-SUITABLE with direct supervision: measure, mark, "
            "sand prepared exterior edges, decorate exterior faces, sort parts, and "
            "finish selected pre-started screws. The box has one 1 1/8 inch entrance, "
            "four high side vents, four floor drains, a rough interior, and no exterior "
            "perch. FIELD HOLD: pole, predator baffle, site, utilities, coating, and "
            "capacity NOT analyzed."
        ),
        related_documents=related,
        join_presentation=BIRDHOUSE_JOIN_PRESENTATION,
    )
    if preview:
        manual = replace(
            manual,
            title=f"{PREVIEW_NOTICE} · {manual.title}",
            lede=f"{PREVIEW_NOTICE}. {manual.lede}",
        )
    image_paths = render_instruction_images(
        detail,
        manual,
        out_dir / "instruction_panels",
        size=image_size,
        style="high_contrast",
    )
    manual_path.write_text(
        render_instruction_manual_html(detail, manual, image_paths),
        encoding="utf-8",
    )
    phases["instruction_panels"] = perf_counter() - phase_started

    with _record_phase(phases, "technical_document"):
        SDR.build_document(
            technical_path,
            spec_path=spec_path,
            companion_href=MANUAL_BASENAME,
            compiled_detail=detail,
            instruction_manual=manual,
            document_notice=PREVIEW_NOTICE if preview else None,
            prepared_documentation_dir=model_dir,
        )

    phase_started = perf_counter()
    governance = detail.design_governance
    selection_fp = governance.selection_digest
    model_fp = governance.model_digest
    fabrication_path.write_text(
        _fabrication_html(detail, selection_fp, model_fp, preview=preview),
        encoding="utf-8",
    )
    installation_path.write_text(
        _installation_html(detail, selection_fp, model_fp, preview=preview),
        encoding="utf-8",
    )

    review = load_design_review_file(REVIEW)
    review_result = validate_design_review(review)
    design_review_path.write_text(
        render_design_review_html(review, review_result, governance),
        encoding="utf-8",
    )
    _write_bom_csv(detail, bom_path)
    _write_cut_csv(detail, cut_path)
    phases["companion_documents"] = perf_counter() - phase_started

    phase_started = perf_counter()
    step_path = model_dir / "family_birdhouse.step"
    glb_path = model_dir / "detail.glb"
    model_manifest_path = model_dir / "detail.manifest.json"
    model_manifest = json.loads(model_manifest_path.read_text())
    cedar_parts = [
        part for part in detail.assembly.parts
        if _is_cedar_component(part.component)
    ]
    screws = [
        part for part in detail.assembly.parts
        if _is_ordinary_wood_screw(part.component)
    ]
    bore_count = sum(
        step.kind == "bore"
        for part in cedar_parts
        for step in part.component.fabrication_record(part.id).steps
    )
    hash_paths = (
        technical_path,
        manual_path,
        fabrication_path,
        installation_path,
        design_review_path,
        bom_path,
        cut_path,
        step_path,
        glb_path,
        model_manifest_path,
        *[image_paths[index] for index in sorted(image_paths)],
        *sorted((out_dir / "views").glob("*.png")),
    )
    file_sha256 = {
        str(path.relative_to(out_dir)): _sha256(path)
        for path in hash_paths
    }
    phases["package_hashing"] = perf_counter() - phase_started
    performance_seconds = {
        **phases,
        "total": perf_counter() - total_started,
    }
    package_manifest = {
        "schema": "detailgen/family-birdhouse-package/v1",
        "release_state": PREVIEW_NOTICE if preview else "DELIVERY CONFIRMED",
        "geometry_authority": "compiled Plumb DetailSpec",
        "spec": spec_path.name,
        "selection_fingerprint": selection_fp,
        "model_fingerprint": model_fp,
        "assembly_hash": model_manifest["build"]["assembly_hash"],
        "validation": {
            "ok": report.ok,
            "blocking_count": len(report.blocking),
            "pairs_total": report.pairs_total,
            "pairs_fully_checked": report.pairs_fully_checked,
        },
        "facts": {
            "cedar_part_count": len(cedar_parts),
            "exterior_screw_count": len(screws),
            "bore_count": bore_count,
            "entrance_diameter_in": detail.namespace["entrance_dia"],
            "side_vent_count": 4,
            "floor_drain_count": 4,
            "perch_count": 0,
        },
        "holds": [
            "pole and baffle product",
            "clamp/U-bolt and cleat interface",
            "soil/foundation/frost/wind",
            "underground and overhead utilities",
            "coating suitability",
            "fastener and installation capacity",
        ],
        "performance_seconds": performance_seconds,
        "file_sha256": file_sha256,
    }
    package_manifest_path = out_dir / PACKAGE_MANIFEST_BASENAME
    package_manifest_path.write_text(
        json.dumps(package_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "technical_path": str(technical_path),
        "manual_path": str(manual_path),
        "fabrication_path": str(fabrication_path),
        "installation_path": str(installation_path),
        "design_review_path": str(design_review_path),
        "bom_csv_path": str(bom_path),
        "cut_csv_path": str(cut_path),
        "package_manifest_path": str(package_manifest_path),
        "step_path": str(step_path),
        "glb_path": str(glb_path),
        "model_manifest_path": str(model_manifest_path),
        "panel_count": len(manual.panels),
        "panel_images": tuple(
            str(image_paths[index]) for index in sorted(image_paths)
        ),
        "performance_seconds": performance_seconds,
        "preview": preview,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--width", type=int, default=DEFAULT_SIZE[0])
    parser.add_argument("--height", type=int, default=DEFAULT_SIZE[1])
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(argv)
    result = build_family_birdhouse_package(
        args.out_dir,
        image_size=(args.width, args.height),
        preview=args.preview,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
