"""Self-contained HTML document for grouped illustrated instructions."""

from __future__ import annotations

import base64
import html
import json
from datetime import datetime
from pathlib import Path

from .instruction_panels import (
    InstructionPresentationError,
    _relative_html_basename,
)
from .instruction_render import panel_callout_ids
from .part_labels import part_labels


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


_ICON_GEOMETRY = {
    "part": '<path d="M4 7l8-4 8 4-8 4zM4 7v10l8 4 8-4V7M12 11v10"/>',
    "saw": '<path d="M3 15h11l6-8H9zM4 15l2 4 2-4 2 4 2-4"/>',
    "ease": '<path d="M4 18h7a7 7 0 007-7V4M6 14h5a3 3 0 003-3V6"/>',
    "drill": '<path d="M3 8h11v7H3zM14 10h5v3h-5M6 15l-2 6h5l1-6M19 11.5h3"/>',
    "adhesive": '<path d="M9 3h6v4l2 3v11H7V10l2-3zM9 12h6v5H9z"/>',
    "clamp": '<path d="M18 4H9a5 5 0 00-5 5v6a5 5 0 005 5h9M15 2v5M15 17v5M12 5h6M12 19h6"/>',
    "screw": '<path d="M5 5l4-3 4 4-3 4M9 9l10 10M13 11l-3 3M16 14l-3 3M19 17l-3 3"/>',
    "driver": '<path d="M3 7h11v7H3zM14 9h5v3h-5M6 14l-2 7h5l1-7M19 10.5h3"/>',
    "countersink": '<path d="M4 5h16M7 5l5 8 5-8M12 13v8M9 18l3 3 3-3"/>',
    "fit": '<path d="M4 8h16M4 16h16M7 5L4 8l3 3M17 13l3 3-3 3"/>',
    "ppe": '<path d="M3 12h5l2-3h4l2 3h5M4 12v4h5l2-3h2l2 3h5v-4M12 9V4M9 6l3-2 3 2"/>',
}


def _icon_svg(icon: str) -> str:
    geometry = _ICON_GEOMETRY.get(icon)
    if geometry is None:
        raise InstructionPresentationError(
            f"manual has no vetted SVG for resource icon {icon!r}")
    return (
        f'<svg class="resource-icon" role="img" '
        f'aria-label="{_e(icon)} icon" viewBox="0 0 24 24">'
        f'{geometry}</svg>')


def _rows(rows, class_name: str) -> str:
    if not rows:
        return ""
    body = "".join(
        f'<li data-icon="{_e(row.icon)}">{_icon_svg(row.icon)}'
        f'<span>{_e(row.label)}</span></li>'
        for row in rows)
    return f'<ul class="{class_name}">{body}</ul>'


def _procedure_links(rows) -> str:
    if not rows:
        return ""
    body = "".join(
        f'<li data-link-kind="{_e(row.kind)}"><a href="{_e(row.href)}" '
        f'rel="noreferrer">{_e(row.label)}</a></li>'
        for row in rows)
    return (
        '<aside class="procedure-links"><h3>Manufacturer procedures and product references</h3>'
        f'<ul>{body}</ul></aside>')


def _related_documents(links, aria_label: str) -> str:
    rows = []
    for index, link in enumerate(links):
        href = _relative_html_basename(
            link.href, f"related_documents[{index}].href"
        )
        rows.append(f'<li><a href="{_e(href)}">{_e(link.label)}</a></li>')
    return (
        f'<nav class="related-documents" aria-label="{_e(aria_label)}">'
        f'<ul>{"".join(rows)}</ul></nav>'
    )


def _callout_rows(detail, panel) -> str:
    labels = part_labels(detail.assembly.parts)
    candidates = panel.arrival_part_ids or panel.focus_part_ids
    family_count = {}
    for part_id in candidates:
        family = labels[part_id].reader_name
        family_count[family] = family_count.get(family, 0) + 1
    rows = []
    for number, part_id in enumerate(panel_callout_ids(detail, panel), start=1):
        family = labels[part_id].reader_name
        count = family_count[family]
        count_text = f"{count} × " if count > 1 else ""
        rows.append(
            f'<li><span class="callout-number">{number}</span>'
            f'<span>{_e(count_text + family)}</span></li>')
    return '<ol class="picture-key">' + "".join(rows) + "</ol>"


def _diagram_primitive_svg(primitive, marker_id: str) -> str:
    coords = primitive.coords
    role = _e(primitive.role)
    label = _e(primitive.label)
    title = f"<title>{label}</title>" if label else ""
    fact_ref = _e(primitive.fact_ref)
    common = (
        f'class="diagram-mark role-{role}" aria-label="{label}" '
        f'data-fact-ref="{fact_ref}"')
    if primitive.kind == "rect" and len(coords) == 4:
        x, y, width, height = coords
        return (
            f'<rect {common} x="{x:g}" y="{y:g}" width="{width:g}" '
            f'height="{height:g}">{title}</rect>')
    if primitive.kind == "line" and len(coords) == 4:
        x1, y1, x2, y2 = coords
        return (
            f'<line {common} x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" '
            f'y2="{y2:g}">{title}</line>')
    if primitive.kind == "arrow" and len(coords) == 4:
        x1, y1, x2, y2 = coords
        return (
            f'<line {common} x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" '
            f'y2="{y2:g}" marker-end="url(#{marker_id})">{title}</line>')
    if primitive.kind == "circle" and len(coords) == 3:
        cx, cy, radius = coords
        return (
            f'<circle {common} cx="{cx:g}" cy="{cy:g}" r="{radius:g}">'
            f'{title}</circle>')
    if primitive.kind == "text" and len(coords) == 2 and primitive.label:
        x, y = coords
        rotate = ""
        if getattr(primitive, "rotation", 0.0):
            rotate = (f' transform="rotate({primitive.rotation:g} '
                      f'{x:g} {y:g})"')
        return (
            f'<text {common} x="{x:g}" y="{y:g}" text-anchor="middle"'
            f'{rotate}>{label}</text>')
    raise InstructionPresentationError(
        f"unsupported diagram primitive {primitive.kind!r} with "
        f"{len(coords)} coordinates")


def _diagram_coordinate_key(diagram) -> tuple[str, str]:
    """Expose every exact plotted coordinate without relying on hover."""

    points = tuple(
        primitive for primitive in diagram.primitives
        if primitive.model_point_mm
    )
    if not points:
        return "", ""
    key_id = "coordinate-key-" + "".join(
        char if char.isalnum() else "-" for char in diagram.diagram_id)
    rows = "".join(
        '<li class="diagram-coordinate-row" '
        f'data-fact-ref="{_e(primitive.fact_ref)}" '
        f'data-model-point="{_e(",".join(f"{value:g}" for value in primitive.model_point_mm))}">'
        f'{_e(primitive.label)}</li>'
        for primitive in points
    )
    return (
        f'<section class="diagram-coordinate-key" id="{_e(key_id)}">'
        f'<h4>Compiled coordinate key — {len(points)} marks</h4>'
        f'<ol>{rows}</ol></section>',
        key_id,
    )


def _diagram_html(diagram) -> str:
    marker_id = "arrow-" + "".join(
        char if char.isalnum() else "-" for char in diagram.diagram_id)
    marks = "".join(
        _diagram_primitive_svg(primitive, marker_id)
        for primitive in diagram.primitives)
    coordinate_key, key_id = _diagram_coordinate_key(diagram)
    described_by = f' aria-describedby="{_e(key_id)}"' if key_id else ""
    return f"""
      <figure class="operation-diagram" data-diagram-id="{_e(diagram.diagram_id)}">
        <h3>{_e(diagram.title)}</h3>
        <svg viewBox="0 0 100 100" role="img"
             aria-label="{_e(diagram.title)}"{described_by}
             preserveAspectRatio="xMidYMid meet">
          <defs><marker id="{_e(marker_id)}" markerWidth="7" markerHeight="7"
            refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 z"/></marker></defs>
          {marks}
        </svg>
        <figcaption>{_e(diagram.caption)}</figcaption>
        {coordinate_key}
      </figure>"""


def _panel_html(detail, panel, image_path: Path, total: int) -> str:
    instructions = "".join(f"<li>{_e(value)}</li>"
                           for value in panel.instructions)
    stations = ""
    if panel.stations:
        station_rows = "".join(
            f"<li>{_e(station.label)}</li>" for station in panel.stations)
        stations = f"""
        <section class="station-box">
          <h3>Placement marks — measured from the compiled model</h3>
          <ul>{station_rows}</ul>
        </section>"""
    why = ""
    if panel.rationales:
        why = "".join(f"<p>{_e(value)}</p>" for value in panel.rationales)
        why = f'<aside class="why"><h3>Why this order</h3>{why}</aside>'
    honesty = ""
    if panel.honesty:
        honesty = "".join(f"<p>{_e(value)}</p>" for value in panel.honesty)
        honesty = f'<aside class="honesty"><h3>Proof boundary</h3>{honesty}</aside>'
    process_badge = (
        f'<span class="badge hard-stop">{_e(panel.process_kind)} gate</span>'
        if panel.process_kind else "")
    diagrams = ""
    if panel.diagrams:
        diagrams = (
            '<section class="operation-diagrams" aria-label="Operation diagrams">'
            + "".join(_diagram_html(diagram) for diagram in panel.diagrams)
            + "</section>"
        )
    stop_notice = ""
    if panel.stop_notice is not None:
        stop_notice = (
            '<aside class="stop-notice" role="alert">'
            f'<h3>{_e(panel.stop_notice.heading)}</h3>'
            f'<p>{_e(panel.stop_notice.body)}</p></aside>'
        )
    record = ""
    if panel.record_fields:
        rows = "".join(
            '<tr><th scope="row">'
            f'{_e(field.label)}</th><td>{_e(field.guidance)}</td>'
            '<td class="record-entry" aria-label="Blank field">&nbsp;</td></tr>'
            for field in panel.record_fields
        )
        record = (
            '<section class="record-form">'
            f'<h3>{_e(panel.record_title or "Completion record")}</h3>'
            '<p>Complete in ink or in the controlled project record; blank '
            'fields do not constitute approval.</p>'
            '<table><thead><tr><th>Field</th><th>What to record</th>'
            f'<th>Recorded value</th></tr></thead><tbody>{rows}</tbody></table>'
            '</section>'
        )

    return f"""
    <article class="instruction-panel" id="panel-{panel.index}"
             data-panel-index="{panel.index}" data-action="{_e(panel.action)}">
      <header class="panel-head">
        <div>
          <div class="panel-kicker">Panel {panel.index} of {total} · {_e(panel.action)}</div>
          <h2>{_e(panel.title)}</h2>
        </div>
        <div class="panel-number">{panel.index}</div>
      </header>
      {stop_notice}
      <div class="resources">
        {_rows(panel.hardware, "hardware")}
        {_rows(panel.tools, "tools")}
        {process_badge}
      </div>
      <figure>
        <img class="scene" src="{_data_uri(image_path)}"
             alt="Model-backed assembly view for panel {panel.index}: {_e(panel.title)}">
        <figcaption>
          <strong>Picture key</strong>
          {_callout_rows(detail, panel)}
          <span class="render-legend"><i class="swatch current"></i>work in color
          <i class="swatch ghost"></i>prior work ghosted</span>
        </figcaption>
      </figure>
      {diagrams}
      <section class="directions">
        <h3>Do this</h3>
        <ol>{instructions}</ol>
      </section>
      {_procedure_links(panel.procedure_links)}
      {stations}
      {why}
      {honesty}
      {record}
      <nav class="panel-nav" aria-label="Panel navigation">
        <a href="#panel-{max(1, panel.index - 1)}"
           class="{'disabled' if panel.index == 1 else ''}">&larr; Previous</a>
        <a href="#panel-{min(total, panel.index + 1)}"
           class="{'disabled' if panel.index == total else ''}">Next &rarr;</a>
      </nav>
    </article>"""


def render_instruction_manual_html(
    detail,
    manual,
    image_paths: dict[int, Path],
    *,
    generated_at: str | None = None,
    viewer: dict[str, object] | None = None,
) -> str:
    """Compose one offline HTML manual from typed panels and keyed PNGs.

    ``viewer`` reuses the platform's existing interactive payload and GLB
    contract. It is screen-only and appears before the instruction overview.
    """
    expected = {panel.index for panel in manual.panels}
    if set(image_paths) != expected:
        raise InstructionPresentationError(
            f"manual image set {sorted(image_paths)!r} does not match panels "
            f"{sorted(expected)!r}")
    missing = [str(image_paths[index]) for index in sorted(expected)
               if not Path(image_paths[index]).is_file()]
    if missing:
        raise InstructionPresentationError(
            f"manual panel images are missing: {missing!r}")

    inventory = _rows(manual.inventory, "inventory")
    nav = "".join(
        f'<a href="#panel-{panel.index}"><b>{panel.index}</b>'
        f'<span>{_e(panel.action)}</span></a>'
        for panel in manual.panels)
    panels = "".join(
        _panel_html(detail, panel, Path(image_paths[panel.index]), len(manual.panels))
        for panel in manual.panels)
    generated = generated_at or datetime.now().astimezone().strftime(
        "%Y-%m-%d %H:%M %Z"
    )
    total = len(manual.panels)
    declared_constraints = len(detail.construction_event_graph.constraints)
    lede = manual.lede.replace(
        "{declared_constraints}", str(declared_constraints))
    navigation_script = """
<script>
(() => {
  const total = __TOTAL__;
  const slider = document.getElementById("panel-slider");
  const progress = document.getElementById("panel-progress");
  const clamp = value => Math.max(1, Math.min(total, Number(value) || 1));
  const currentFromHash = () => {
    const match = location.hash.match(/^#panel-(\\d+)$/);
    return clamp(match ? match[1] : slider.value);
  };
  const show = (value, scroll = true) => {
    const panel = clamp(value);
    slider.value = panel;
    progress.textContent = `Panel ${panel} of ${total}`;
    if (location.hash !== `#panel-${panel}`) history.replaceState(null, "", `#panel-${panel}`);
    if (scroll) document.getElementById(`panel-${panel}`).scrollIntoView({behavior:"smooth", block:"start"});
  };
  slider.addEventListener("input", () => show(slider.value));
  document.getElementById("panel-prev").addEventListener("click", () => show(Number(slider.value) - 1));
  document.getElementById("panel-next").addEventListener("click", () => show(Number(slider.value) + 1));
  addEventListener("keydown", event => {
    if (event.target.matches("input,textarea,select")) return;
    if (event.key === "ArrowLeft") show(Number(slider.value) - 1);
    if (event.key === "ArrowRight") show(Number(slider.value) + 1);
  });
  addEventListener("hashchange", () => show(currentFromHash(), false));
  if (location.hash.match(/^#panel-\\d+$/)) show(currentFromHash(), true);
})();
</script>""".replace("__TOTAL__", str(total))

    if manual.related_documents:
        header_documents = _related_documents(
            manual.related_documents, "Related documents"
        )
        footer_documents = _related_documents(
            manual.related_documents, "Related documents footer"
        )
        related_document_styles = (
            ".related-documents ul{display:flex;flex-wrap:wrap;gap:.45rem 1rem;"
            "list-style:none;margin:.8rem 0 0;padding:0}\n"
            ".related-documents a{font-weight:800} "
            ".manual-head .related-documents a{color:white}\n"
        )
    else:
        header_documents = (
            f'<a class="manual-link" href="{_e(manual.technical_href)}">'
            "Open the technical build document &rarr;</a>"
        )
        footer_documents = (
            f'<a href="{_e(manual.technical_href)}">'
            "&larr; Return to the technical build document</a>"
        )
        related_document_styles = ""

    viewer_html = ""
    viewer_style = ""
    viewer_script = ""
    if viewer is not None:
        from .web_viewer import vendor_js, viewer_css, viewer_js

        payload = viewer["payload"]
        slug = payload["slug"]
        payload_json = json.dumps(
            payload, separators=(",", ":")
        ).replace("</", "<\\/")
        isometric_href = str(viewer["isometric_href"])
        viewer_html = (
            '<section class="viewer-section" aria-label="Interactive 3D">'
            '<div class="viewer-copy"><h2>Explore the build in 3D</h2>'
            '<p>Use Explode to separate the compiled parts, then click any part '
            'for its model-derived size and build information.</p></div>'
            f'<div class="viewer-slot" data-detail="{_e(slug)}">'
            f'<img src="{_e(isometric_href)}" alt="Interactive assembly preview">'
            '<button type="button" class="viewer-btn">Explore in 3D</button>'
            '</div></section>'
            f'<script type="application/json" id="detail-data-{_e(slug)}">'
            f'{payload_json}</script>'
            f'<script type="text/plain" id="detail-glb-{_e(slug)}">'
            f'{viewer["glb_b64"]}</script>'
        )
        viewer_style = viewer_css()
        viewer_script = f"<script>{vendor_js()}\n{viewer_js()}</script>"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="data:,">
<title>{_e(manual.title)}</title>
<style>
:root{{--ink:#111827;--muted:#475569;--line:#cbd5e1;--paper:#fff;--blue:#2563eb;
--blue-soft:#eff6ff;--amber:#92400e;--amber-soft:#fffbeb;--red:#991b1b;--red-soft:#fef2f2;
--sheet:var(--paper);--acc:var(--blue);--acc-soft:var(--blue-soft);--faint:var(--line);--chipbg:#f8fafc}}
*{{box-sizing:border-box}} html{{scroll-behavior:smooth}}
body{{margin:0;background:#e2e8f0;color:var(--ink);font:16px/1.48 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
.manual{{max-width:1050px;margin:0 auto;background:var(--paper);min-height:100vh;box-shadow:0 0 30px #64748b55}}
.manual-head{{padding:2rem 2.25rem 1.5rem;background:#0f172a;color:white}}
.eyebrow{{font-size:.78rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#93c5fd}}
h1{{font-size:clamp(2rem,5vw,3.25rem);line-height:1.05;margin:.35rem 0 .75rem}} h2,h3{{line-height:1.2}}
.lede{{max-width:760px;color:#dbeafe;font-size:1.07rem}} .manual-link{{display:inline-block;margin-top:.8rem;padding:.65rem .85rem;border:1px solid #93c5fd;border-radius:7px;color:white;font-weight:750;text-decoration:none}}
{related_document_styles}.generated{{margin-top:1rem;font-size:.78rem;color:#94a3b8}}
.safety-banner{{margin:0;padding:.7rem 1.2rem;background:#fff7ed;border-bottom:2px solid #c2410c;color:#7c2d12;font-weight:750}}
.viewer-section{{padding:1.4rem 2.25rem 1.6rem;border-bottom:1px solid var(--line);background:#f8fafc}}
.viewer-copy h2{{margin:.1rem 0 .35rem}}.viewer-copy p{{margin:.2rem 0 1rem;color:var(--muted)}}
.viewer-slot{{aspect-ratio:4/3;overflow:hidden;background:white;border:1px solid var(--line);border-radius:8px}}
.viewer-slot>img{{display:block;width:100%;height:100%;object-fit:contain}}
.stop-notice{{margin:0;padding:1rem 1.2rem;background:var(--red-soft);border-bottom:4px solid #b91c1c;color:var(--red)}}
.stop-notice h3{{margin:0 0 .25rem;font-size:1.2rem;letter-spacing:.04em}} .stop-notice p{{margin:0;font-weight:800}}
.overview{{padding:1.4rem 2.25rem;border-bottom:1px solid var(--line);display:grid;grid-template-columns:1.1fr 1fr;gap:1.25rem}}
.overview>div{{min-width:0}} .overview h2{{margin:.1rem 0 .55rem;font-size:1.05rem}} .inventory{{margin:.2rem 0;list-style:none;padding:0}} .inventory li{{display:flex;align-items:center;gap:.5rem;margin:.4rem 0;min-width:0}} .inventory li span{{min-width:0;overflow-wrap:anywhere}}
.panel-index{{display:grid;grid-template-columns:repeat(5,1fr);gap:.4rem}}
.panel-index a{{padding:.55rem .25rem;border:1px solid var(--line);border-radius:6px;text-align:center;text-decoration:none;color:var(--ink)}}
.panel-index b,.panel-index span{{display:block}} .panel-index span{{font-size:.72rem;text-transform:uppercase;color:var(--muted)}}
.panel-controls{{position:sticky;top:0;z-index:5;display:grid;grid-template-columns:auto 1fr auto auto;gap:.7rem;align-items:center;padding:.7rem 1rem;background:#f8fafcf2;border-bottom:1px solid var(--line);backdrop-filter:blur(8px)}}
.panel-controls button{{border:1px solid var(--line);background:white;border-radius:6px;padding:.45rem .7rem;font-weight:750;color:var(--blue)}}
.panel-controls input{{width:100%}} #panel-progress{{min-width:6.5rem;text-align:right;font-size:.85rem;font-weight:800}}
.instruction-panel{{margin:2rem;border:3px solid var(--ink);border-radius:11px;overflow:hidden;scroll-margin-top:1rem}}
.panel-head{{display:flex;justify-content:space-between;align-items:center;padding:1rem 1.2rem;border-bottom:2px solid var(--ink)}}
.panel-head h2{{margin:.15rem 0;font-size:1.45rem}} .panel-kicker{{font-size:.76rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:800}}
.panel-number{{font-size:2.6rem;font-weight:900;line-height:1}}
.resources{{display:flex;align-items:center;flex-wrap:wrap;gap:.65rem;padding:.55rem 1.2rem;background:#f8fafc;border-bottom:1px solid var(--line)}}
.resources ul{{display:flex;flex-wrap:wrap;gap:.5rem 1.2rem;list-style:none;margin:0;padding:0;min-width:0;max-width:100%}} .resources li{{display:flex;align-items:center;gap:.4rem;font-weight:700;font-size:.9rem;min-width:0;max-width:100%}} .resources li span{{overflow-wrap:anywhere}}
.resource-icon{{width:1.45rem;height:1.45rem;flex:0 0 auto;fill:none;stroke:var(--blue);stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}} .badge{{font-size:.74rem;font-weight:850;text-transform:uppercase;padding:.25rem .5rem;border-radius:999px;background:#e2e8f0}}
.hard-stop{{background:#fee2e2;color:#991b1b}} figure{{margin:0}} img.scene{{display:block;width:100%;height:auto;background:white}}
figcaption{{display:flex;align-items:center;flex-wrap:wrap;gap:.6rem 1rem;padding:.55rem 1rem;background:#f8fafc;border-top:1px solid var(--line);font-size:.86rem}}
.picture-key{{display:flex;gap:.8rem 1.15rem;flex-wrap:wrap;list-style:none;margin:0;padding:0}} .picture-key li{{display:flex;align-items:center;gap:.35rem}}
.callout-number{{display:inline-grid;place-items:center;width:1.55rem;height:1.55rem;border:2px solid var(--ink);border-radius:50%;background:white;font-weight:850}}
.render-legend{{margin-left:auto;color:var(--muted)}} .swatch{{display:inline-block;width:.85rem;height:.85rem;border:1px solid #64748b;margin:0 .3rem 0 .8rem;vertical-align:-.1rem}} .current{{background:#9a7b4f}} .ghost{{background:#e5e7eb}}
.operation-diagrams{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:.8rem;margin:1rem 1.2rem}}
.operation-diagram{{margin:0;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:white}}
.operation-diagram h3{{margin:0;padding:.55rem .75rem;background:#f8fafc;border-bottom:1px solid var(--line);font-size:.95rem}}
.operation-diagram svg{{display:block;width:100%;height:auto;max-height:390px;background:#fff}}
.operation-diagram figcaption{{display:block;padding:.55rem .75rem;border-top:1px solid var(--line);font-size:.84rem;color:var(--muted)}}
.diagram-coordinate-key{{padding:.55rem .75rem;border-top:1px solid var(--line);background:#eff6ff}}
.diagram-coordinate-key h4{{margin:.1rem 0 .35rem;font-size:.82rem}}
.diagram-coordinate-key ol{{margin:.2rem 0;padding-left:1.25rem;columns:2;column-gap:1.5rem}}
.diagram-coordinate-row{{break-inside:avoid;margin:.2rem 0;font-size:.75rem}}
.diagram-mark{{vector-effect:non-scaling-stroke;stroke:var(--ink);stroke-width:1.25;fill:#d6c09a}}
.diagram-mark.role-prior{{fill:#e5e7eb;stroke:#64748b}}
.diagram-mark.role-hold{{fill:#fff;stroke:#dc2626;stroke-dasharray:4 3}}
.diagram-mark.role-receiver{{fill:#dbeafe;stroke:var(--blue);stroke-width:1.6}}
.diagram-mark.role-groove{{fill:none;stroke:#dc2626;stroke-width:2.5}}
.diagram-mark.role-motion{{fill:none;stroke:var(--blue);stroke-width:2}}
.diagram-mark.role-fastener{{fill:var(--ink);stroke:#fff;stroke-width:.8}}
.diagram-mark.role-station{{fill:var(--blue);stroke:#fff;stroke-width:.8}}
.diagram-mark.role-hardware{{fill:#f59e0b;stroke:#78350f;stroke-width:1.1}}
text.diagram-mark{{fill:var(--ink);stroke:none;font-size:3px;font-weight:800}}
text.diagram-mark.role-hold{{fill:#dc2626;stroke:none;font-size:3px}}
.diagram-mark.role-datum{{fill:var(--ink);stroke:none;font-size:3px;font-weight:800}}
.operation-diagram marker path{{fill:var(--blue)}}
.directions,.station-box,.why,.honesty{{margin:1rem 1.2rem;padding:.8rem 1rem;border-radius:7px}} .directions{{padding:0 1rem}} .directions h3,.station-box h3,.why h3,.honesty h3{{font-size:1rem;margin:.1rem 0 .45rem}}
.directions li,.station-box li{{margin:.35rem 0}} .station-box{{background:var(--blue-soft);border-left:5px solid var(--blue)}}
.station-box ul{{margin:.2rem 0;padding-left:1.2rem}} .why{{background:var(--amber-soft);border-left:5px solid #d97706}} .why p,.honesty p{{margin:.3rem 0}}
.procedure-links{{margin:1rem 1.2rem;padding:.7rem 1rem;border:1px solid #93c5fd;border-radius:7px;background:var(--blue-soft)}}
.procedure-links h3{{font-size:1rem;margin:.1rem 0 .35rem}} .procedure-links ul{{margin:.2rem 0;padding-left:1.2rem}}
.procedure-links a{{color:var(--blue);font-weight:750;overflow-wrap:anywhere}}
.honesty{{background:var(--red-soft);border-left:5px solid #dc2626}} .panel-nav{{display:flex;justify-content:space-between;padding:.8rem 1.2rem;border-top:1px solid var(--line)}}
.record-form{{margin:1rem 1.2rem;padding:.8rem 1rem;border:2px solid var(--ink);border-radius:7px;overflow-x:auto}}
.record-form h3{{margin:.1rem 0 .25rem}} .record-form p{{margin:.2rem 0 .7rem;color:var(--muted)}}
.record-form table{{width:100%;table-layout:fixed;border-collapse:collapse;font-size:.86rem}} .record-form th,.record-form td{{border:1px solid var(--line);padding:.5rem;text-align:left;vertical-align:top;overflow-wrap:anywhere}}
.record-entry{{width:30%;height:2.2rem;background:#fff}}
.panel-nav a{{color:var(--blue);font-weight:750;text-decoration:none}} .panel-nav .disabled{{visibility:hidden}}
.manual-foot{{padding:1.5rem 2.25rem 2rem;border-top:1px solid var(--line);background:#f8fafc}} .manual-foot a{{color:var(--blue);font-weight:800}}
@media(max-width:700px){{.overview{{grid-template-columns:1fr}}.instruction-panel{{margin:1rem .5rem}}.manual-head,.overview{{padding-left:1rem;padding-right:1rem}}.panel-index{{grid-template-columns:repeat(3,1fr)}}.render-legend{{width:100%;margin-left:0}}.panel-controls{{grid-template-columns:auto 1fr auto}}#panel-progress{{grid-column:1/-1;text-align:center}}.diagram-coordinate-key ol{{columns:1}}}}
@media print{{body{{background:white}}.manual{{box-shadow:none;max-width:none}}.manual-head{{padding:.65rem 1.2rem}}.manual-head h1{{font-size:1.65rem;margin:.2rem 0}}.lede{{font-size:.78rem;line-height:1.25;margin:.3rem 0}}.manual-link{{margin-top:.25rem;padding:.15rem 0;border:0;color:white}}.generated{{margin-top:.2rem}}.safety-banner{{font-size:.72rem;padding:.35rem 1rem}}.viewer-section{{display:none}}.overview{{display:flex;flex-direction:column;padding:.55rem 1.2rem}}.overview>div:last-child{{order:-1;margin-bottom:.6rem}}.overview h2{{font-size:.85rem}}.inventory{{columns:2;column-gap:1rem}}.inventory{{font-size:.68rem;line-height:1.18}}.inventory li{{break-inside:avoid;margin:.25rem 0}}.inventory .resource-icon{{width:1rem;height:1rem}}.instruction-panel{{break-inside:avoid;margin:1rem 0}}.panel-nav{{display:none}}.panel-controls{{display:none}}.manual-foot{{display:none}}}}
{viewer_style}
</style></head><body><main class="manual">
<header class="manual-head"><div class="eyebrow">Model-backed · illustrated assembly</div>
<h1>{_e(manual.title)}</h1>
<p class="lede">{_e(lede)}</p>
{header_documents}
<div class="generated">Generated {_e(generated)} · Core document embedded; external manufacturer links require internet</div></header>
<aside class="safety-banner" role="note"><strong>Safety throughout.</strong>
Wear safety glasses for cutting, drilling, routing, and powered fastening; use
hearing protection, effective dust extraction, and material-appropriate
respiratory protection. Follow every tool and product manufacturer instruction.</aside>
{viewer_html}
<section class="overview"><div><h2>Parts and required consumables</h2>{inventory}</div>
<div><h2>{total}-panel build path</h2><nav class="panel-index">{nav}</nav></div></section>
<nav class="panel-controls" aria-label="Assembly panel navigator">
  <button id="panel-prev" type="button">&larr;</button>
  <input id="panel-slider" type="range" min="1" max="{total}" value="1" step="1"
         aria-label="Assembly panel">
  <button id="panel-next" type="button">&rarr;</button>
  <output id="panel-progress" for="panel-slider">Panel 1 of {total}</output>
</nav>
{panels}
<footer class="manual-foot">{footer_documents}</footer>
</main>{navigation_script}{viewer_script}</body></html>"""
