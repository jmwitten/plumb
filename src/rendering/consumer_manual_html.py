"""Print-first HTML composition for the consumer assembly manual.

One `section.sheet` per composed Letter page; CSS pagination guarantees no
frame splits across printed pages. High-contrast, grayscale-legible reader
register: reader names and hardware letters only — machine identifiers stay
in data attributes for traceability and never in visible text.
"""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from .action_frames import FrameContractError
from .consumer_pages import ConsumerManual
from .instruction_manual import _diagram_primitive_svg, _icon_svg
from .part_labels import part_labels


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _data_uri(path: Path) -> str:
    payload = base64.b64encode(Path(path).read_bytes()).decode()
    return f"data:image/png;base64,{payload}"


def _as_data_uri(value) -> str:
    """Accept a PNG path or an already-encoded ``data:image/…`` string."""
    if isinstance(value, str) and value.startswith("data:image/"):
        return value
    return _data_uri(value)


def _letter_chip(letter: str, quantity: int) -> str:
    return (f'<span class="chip hardware-chip">'
            f'<b>{_e(letter)}</b> &times;{quantity}</span>')


def _consumer_diagram_html(diagram) -> str:
    """One typed operation diagram in the consumer register: title + marks.

    The technical surfaces keep the long captions and compiled coordinate
    keys; here the diagram itself is the payload — it shows where the
    fasteners and stations go.
    """
    import re as _re

    marker_id = "carrow-" + "".join(
        ch if ch.isalnum() else "-" for ch in diagram.diagram_id)
    marks = "".join(
        _diagram_primitive_svg(primitive, marker_id)
        for primitive in diagram.primitives)
    # The consumer register carries no machine part names: drop the
    # technical hover titles and per-mark aria labels (station identities
    # remain machine-traceable via data-fact-ref attributes).
    marks = _re.sub(r"<title>.*?</title>", "", marks, flags=_re.S)
    marks = _re.sub(r' aria-label="[^"]*"', "", marks)
    return (
        f'<figure class="op-diagram" data-diagram-id="'
        f'{_e(diagram.diagram_id)}">'
        f"<figcaption>{_e(diagram.title)}</figcaption>"
        f'<svg viewBox="0 0 100 100" role="img" '
        f'aria-label="{_e(diagram.title)}" '
        'preserveAspectRatio="xMidYMid meet">'
        f'<defs><marker id="{_e(marker_id)}" markerWidth="7" '
        'markerHeight="7" refX="6" refY="3.5" orient="auto">'
        '<path d="M0,0 L7,3.5 L0,7 z"/></marker></defs>'
        f"{marks}</svg>"
        f'<figcaption class="op-caption">{_e(diagram.caption)}'
        "</figcaption></figure>")


def _frame_html(detail, frame, number: int | None, image_path: Path,
                diagrams=None) -> str:
    labels = part_labels(detail.assembly.parts)
    chips = "".join(
        _letter_chip(row.letter, row.quantity) for row in frame.hardware)
    badge = ""
    if frame.repeat > 1:
        badge = (f'<span class="chip repeat-badge">{frame.repeat}&times; '
                 f'<small>{_e(frame.repeat_subject)}</small></span>')
    tool = ""
    if frame.tool:
        tool = f'<p class="tool">{_e(frame.tool)}</p>'
    warning = ""
    if frame.warning:
        warning = (f'<aside class="warning" role="alert"><b>&#9888;</b> '
                   f'<span>{_e(frame.warning)}</span></aside>')
    hold = ""
    if frame.hold:
        hold = (f'<aside class="hold-note"><b>HOLD</b> '
                f'<span>{_e(frame.hold)}</span></aside>')
    inset = ""
    if frame.illustration is not None and frame.illustration.inset:
        inset = (f'<figcaption class="inset-note">Detail: '
                 f'{_e(frame.illustration.inset)}</figcaption>')
    # Mirrors panel_callout_ids: first part per reader family, in focus
    # order — so key number N is the same part as circle N in the scene.
    key_names = []
    for part_id in frame.focus_part_ids:
        name = labels[part_id].reader_name
        if name not in key_names:
            key_names.append(name)
    picture_key = "".join(
        f'<li><span class="key-num">{number}</span>{_e(name)}</li>'
        for number, name in enumerate(key_names, start=1))
    number_html = (f'<span class="step-number">{number}</span>'
                   if number is not None
                   else '<span class="step-number stop">STOP</span>')
    header = (f'<header>{number_html}<div class="chips">{badge}{chips}'
              '</div></header>')
    if frame.is_hold_gate:
        # The alert must be unavoidable: it precedes caption and imagery.
        return (
            f'<article class="frame hold-frame" '
            f'data-frame-id="{_e(frame.frame_id)}" '
            f'data-step-ids="{_e(",".join(frame.source_step_ids))}">'
            f'{header}{warning}'
            f'<p class="caption">{_e(frame.caption)}</p>'
            "</article>")
    diagram_html = ""
    for diagram_id in frame.detail_diagram_ids:
        if diagrams is None or diagram_id not in diagrams:
            raise FrameContractError(
                f"frame {frame.frame_id!r} references diagram "
                f"{diagram_id!r} but no such typed diagram was supplied")
        diagram_html += _consumer_diagram_html(diagrams[diagram_id])
    scene = (f'<figure class="scene-figure">'
             f'<img src="{_data_uri(image_path)}" '
             f'alt="Assembly view: step {number}">'
             f"{inset}</figure>")
    return (
        f'<article class="frame" data-frame-id="{_e(frame.frame_id)}" '
        f'data-step-ids="{_e(",".join(frame.source_step_ids))}">'
        f"{header}"
        f'<div class="figures">{scene}{diagram_html}</div>'
        f'<p class="caption">{_e(frame.caption)}</p>'
        f"{tool}{warning}{hold}"
        f'<ul class="picture-key">{picture_key}</ul>'
        "</article>")


def _cover_sheet(consumer, cover_image: Path) -> str:
    return (
        '<section class="sheet cover" data-page="1">'
        f"<h1>{_e(consumer.title)}</h1>"
        f'<img src="{_data_uri(cover_image)}" alt="Finished product view">'
        f'<p class="caption">{_e(consumer.cover_caption)}</p>'
        + "".join(
            f'<p class="related"><a href="{_e(link.href)}">{_e(link.label)}'
            "</a></p>"
            for link in consumer.related_documents)
        + "</section>")


def _inventory_sheet(consumer, number: int, inventory_rows,
                     tools: tuple[str, ...],
                     parts_heading: str = "Parts") -> str:
    kit = (f'<aside class="kit-gate" role="note"><b>Before you start</b> '
           f'<span>{_e(consumer.kit_gate)}</span></aside>')
    parts = "".join(
        f'<li>{_icon_svg(row.icon)}<span>{_e(row.label)}</span></li>'
        for row in inventory_rows)
    letters = "".join(
        f'<li data-letter="{_e(lt.letter)}">'
        f'<span class="chip hardware-chip"><b>{_e(lt.letter)}</b> '
        f"&times;{lt.quantity_total}</span>"
        f"{_icon_svg(lt.icon)}"
        f"<span>{_e(lt.reader_label)}<br><small>{_e(lt.size_text)}"
        "</small></span></li>"
        for lt in consumer.letters)
    tool_rows = "".join(f"<li>{_e(tool)}</li>" for tool in tools)
    return (
        f'<section class="sheet inventory" data-page="{number}">'
        f'{kit}<h2>{_e(parts_heading)}</h2><ul class="parts">{parts}</ul>'
        f'<h2>Hardware</h2><ul class="letters">{letters}</ul>'
        f'<h2>Tools</h2><ul class="tools">{tool_rows}</ul>'
        "</section>")


def _record_sheet(page) -> str:
    rows = "".join(
        f'<tr><th scope="row">{_e(field.label)}</th>'
        f"<td>{_e(field.guidance)}</td>"
        '<td class="entry" aria-label="Blank field">&nbsp;</td></tr>'
        for field in page.record_fields)
    return (
        f'<section class="sheet record" data-page="{page.number}">'
        f"<h2>{_e(page.record_title)}</h2>"
        "<p>Complete in ink; blank fields do not constitute approval.</p>"
        "<table><thead><tr><th>Field</th><th>What to record</th>"
        f"<th>Recorded value</th></tr></thead><tbody>{rows}</tbody></table>"
        "</section>")


_STYLE = """
/* --acc themes the embedded 3D viewer's hover highlight and dimension
   lines (viewer.js reads it; its orange fallback read as yellow on the
   gray parts). */
:root { --ink: #14161a; --line: #444; --paper: #fff; --acc: #2563eb;
  --sheet: #fff; --muted: #555; --faint: #f2f2f2; --chipbg: #ececec;
  --acc-soft: #dbeafe; }
* { box-sizing: border-box; }
body { margin: 0; background: #d8dbe0; color: var(--ink);
  font: 15px/1.45 -apple-system, "Segoe UI", "Helvetica Neue", sans-serif; }
.sheet { width: 8.5in; min-height: 10in; max-width: 100%;
  margin: 0.35rem auto; padding: 0.55in; background: var(--paper);
  break-after: page; break-inside: avoid; box-shadow: 0 1px 8px #0003;
  overflow: hidden; }
h1 { font-size: 2.1rem; line-height: 1.1; margin: 0 0 1rem; }
h2 { font-size: 1.1rem; margin: 1rem 0 0.5rem; }
.cover img { display: block; max-width: 100%; max-height: 5.4in;
  width: auto; height: auto; margin: 0 auto;
  border: 3px solid var(--ink); border-radius: 8px; }
.cover .caption { font-size: 1.05rem; }
.related a { color: var(--ink); font-weight: 700; }
.kit-gate { display: block; border: 3px solid var(--ink); border-radius: 8px;
  padding: 0.6rem 0.8rem; font-size: 0.95rem; }
.kit-gate b { display: block; text-transform: uppercase;
  letter-spacing: 0.06em; font-size: 0.8rem; }
.inventory h2 { margin: 0.45rem 0 0.2rem; font-size: 1rem; }
ul.parts, ul.letters, ul.tools { list-style: none; margin: 0.05rem 0;
  padding: 0; font-size: 0.72rem; line-height: 1.25; }
ul.parts li, ul.letters li, ul.tools li { display: flex; gap: 0.35rem;
  align-items: center; margin: 0.09rem 0; min-width: 0;
  break-inside: avoid; }
ul.parts .resource-icon { width: 1rem; height: 1rem; }
ul.parts li span, ul.letters li span { overflow-wrap: anywhere; }
ul.parts { columns: 2; column-gap: 1.1rem; }
ul.letters { display: grid; grid-template-columns: 1fr 1fr;
  gap: 0.1rem 1.1rem; }
ul.tools { columns: 2; column-gap: 1.1rem; }
ul.tools li::before { content: "\\2022"; margin-right: 0.4rem; }
.resource-icon { width: 1.3rem; height: 1.3rem; flex: 0 0 auto; fill: none;
  stroke: var(--ink); stroke-width: 1.8; stroke-linecap: round;
  stroke-linejoin: round; }
.frame { border: 3px solid var(--ink); border-radius: 10px;
  padding: 0.4rem 0.6rem 0.5rem; margin: 0 0 0.45rem;
  break-inside: avoid; }
.frame header { display: flex; align-items: center; gap: 0.5rem;
  flex-wrap: wrap; margin-bottom: 0.35rem; }
.step-number { display: inline-grid; place-items: center;
  min-width: 2.4rem; height: 2.4rem; padding: 0 0.4rem;
  border: 3px solid var(--ink); border-radius: 50%;
  font-size: 1.35rem; font-weight: 900; }
.step-number.stop { border-radius: 10px; background: var(--ink);
  color: var(--paper); font-size: 1rem; letter-spacing: 0.08em; }
.chips { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-left: auto; }
.chip { display: inline-flex; align-items: baseline; gap: 0.25rem;
  border: 2px solid var(--ink); border-radius: 999px;
  padding: 0.1rem 0.55rem; font-weight: 800; font-size: 0.95rem;
  background: var(--paper); }
.repeat-badge { background: var(--ink); color: var(--paper); }
.repeat-badge small { font-weight: 600; }
.frame figure { margin: 0; }
.frame .figures { display: flex; gap: 0.35rem; align-items: center;
  justify-content: center; }
.frame .scene-figure { flex: 1 1 55%; min-width: 0; }
.frame img { display: block; max-width: 100%; max-height: 2.45in;
  width: auto; height: auto; margin: 0 auto; background: var(--paper); }
.op-diagram { flex: 0 1 42%; min-width: 0; margin: 0;
  border: 1.5px solid var(--ink); border-radius: 6px; overflow: hidden; }
.op-diagram figcaption { padding: 0.15rem 0.4rem; font-size: 0.68rem;
  font-weight: 700; border-bottom: 1.5px solid var(--ink);
  background: #f2f2f2; }
.op-diagram svg { display: block; width: 100%; height: auto;
  max-height: 1.45in; background: var(--paper); }
.op-caption { padding: 0.12rem 0.35rem; font-size: 0.57rem;
  line-height: 1.28; color: #333; border-top: 1px solid var(--line);
  border-bottom: 0; background: var(--paper); font-weight: 400; }
.diagram-mark { vector-effect: non-scaling-stroke; stroke: var(--ink);
  stroke-width: 1.1; fill: #cfcfcf; }
.diagram-mark.role-prior { fill: #ececec; stroke: #777; }
.diagram-mark.role-receiver { fill: #e2e2e2; stroke: var(--ink);
  stroke-width: 1.4; }
.diagram-mark.role-hold { fill: none; stroke: var(--ink);
  stroke-dasharray: 4 3; }
.diagram-mark.role-groove { fill: none; stroke: var(--ink);
  stroke-width: 2.2; }
.diagram-mark.role-motion { fill: none; stroke: var(--ink);
  stroke-width: 1.8; }
.diagram-mark.role-fastener { fill: var(--ink); stroke: var(--paper);
  stroke-width: 0.7; }
.diagram-mark.role-station { fill: var(--ink); stroke: var(--paper);
  stroke-width: 0.7; }
.diagram-mark.role-hardware { fill: #9a9a9a; stroke: var(--ink);
  stroke-width: 1; }
text.diagram-mark, .diagram-mark.role-datum { fill: var(--ink);
  stroke: none; font-size: 3px; font-weight: 800; }
text.diagram-mark.role-hold { fill: var(--ink); stroke: none; }
.op-diagram marker path { fill: var(--ink); }
.inset-note { font-size: 0.8rem; color: var(--line); }
.caption { font-size: 0.95rem; margin: 0.3rem 0 0.1rem;
  line-height: 1.38; }
.tool { margin: 0.1rem 0; font-size: 0.82rem; color: #222; }
.tool::before { content: "Tool: "; font-weight: 800; }
.warning, .hold-note { display: flex; gap: 0.5rem; align-items: baseline;
  border: 3px solid var(--ink); border-left-width: 12px; border-radius: 6px;
  padding: 0.2rem 0.5rem; margin: 0.25rem 0; font-weight: 600;
  font-size: 0.8rem; line-height: 1.3; }
.hold-frame { border-width: 6px; }
.hold-frame .warning { font-size: 1.05rem; }
.picture-key { list-style: none; display: flex; flex-wrap: wrap;
  gap: 0.15rem 0.8rem; margin: 0.25rem 0 0; padding: 0; font-size: 0.72rem;
  color: #333; }
.picture-key li { display: inline-flex; align-items: center;
  gap: 0.28rem; }
.key-num { display: inline-grid; place-items: center; width: 1.05rem;
  height: 1.05rem; border: 1.6px solid var(--ink); border-radius: 50%;
  background: var(--paper); font-weight: 800; font-size: 0.62rem;
  color: var(--ink); }
.record table { width: 100%; table-layout: fixed; border-collapse: collapse;
  font-size: 0.85rem; }
.record th, .record td { border: 1.5px solid var(--ink); padding: 0.45rem;
  text-align: left; vertical-align: top; overflow-wrap: anywhere; }
.record .entry { width: 30%; height: 2.4rem; }
.sheet { position: relative; }
.page-number { position: absolute; right: 0.55in; bottom: 0.16in;
  font-size: 0.72rem; color: #555; margin: 0; }
@media print { .page-number { right: 0.12in; bottom: 0.02in; } }
@media (max-width: 700px) {
  .sheet { width: 100%; min-height: 0; padding: 4vw; }
  ul.letters { grid-template-columns: 1fr; }
}
@page { size: Letter; margin: 0.3in; }
@media print {
  body { background: var(--paper); font-size: 13.5px; }
  .sheet { width: auto; min-height: 0; margin: 0; padding: 0.12in;
    box-shadow: none; overflow: visible; }
  .sheet:last-of-type { break-after: auto; }
  .frame { margin-bottom: 0.4rem; }
  .viewer-section { display: none; }
}
.viewer-section { max-width: 8.5in; margin: 0.35rem auto 1.2rem;
  padding: 0.55in; background: var(--paper); box-shadow: 0 1px 8px #0003; }
.viewer-section h2 { margin: 0 0 0.4rem; }
.viewer-section p { font-size: 0.9rem; }
.viewer-slot { position: relative; aspect-ratio: 4/3; background: #f6f6f4;
  overflow: hidden; }
.viewer-slot img { display: block; width: 100%; height: auto; }

"""


def render_consumer_manual_html(
    detail,
    consumer: ConsumerManual,
    image_paths: dict[str, Path],
    *,
    cover_image: str | Path,
    inventory_rows=(),
    parts_heading: str = "Parts",
    diagrams=None,
    viewer=None,
) -> str:
    """Compose the self-contained consumer manual HTML.

    ``diagrams`` maps diagram ids to the typed OperationDiagrams referenced
    by frames. ``viewer``, when supplied as ``{"payload": dict, "glb_b64":
    str, "isometric": Path}``, appends the screen-only interactive 3D
    section (explode + per-milestone isolation); print output is unaffected.
    """
    cover_image = Path(cover_image)
    frame_ids = [frame.frame_id for page in consumer.pages
                 for frame in page.frames if not frame.is_hold_gate]
    missing = [frame_id for frame_id in frame_ids
               if frame_id not in image_paths
               or not Path(image_paths[frame_id]).is_file()]
    if missing or not cover_image.is_file():
        raise FrameContractError(
            f"consumer manual is missing frame/cover image files: "
            f"{missing!r}")

    tools = tuple(dict.fromkeys(
        frame.tool for page in consumer.pages for frame in page.frames
        if frame.tool))

    number = 0
    sheets = []
    for page in consumer.pages:
        if page.kind == "cover":
            sheets.append(_cover_sheet(consumer, cover_image))
        elif page.kind == "inventory":
            sheets.append(_inventory_sheet(
                consumer, page.number, inventory_rows, tools,
                parts_heading=parts_heading))
        elif page.kind == "record":
            sheets.append(_record_sheet(page))
        elif page.kind == "hold":
            sheets.append(
                f'<section class="sheet hold" data-page="{page.number}">'
                + _frame_html(detail, page.frames[0], None, cover_image)
                + "</section>")
        else:
            body = []
            for frame in page.frames:
                number += 1
                body.append(_frame_html(
                    detail, frame, number, Path(image_paths[frame.frame_id]),
                    diagrams=diagrams))
            sheets.append(
                f'<section class="sheet frames" data-page="{page.number}">'
                + "".join(body) + "</section>")

    total_pages = len(consumer.pages)
    numbered = []
    for page, sheet in zip(consumer.pages, sheets):
        footer = (f'<div class="page-number">Page {page.number} of '
                  f"{total_pages}</div>")
        numbered.append(sheet.replace("</section>", footer + "</section>", 1))
    sheets = numbered

    viewer_html = ""
    viewer_style = ""
    viewer_script = ""
    if viewer is not None:
        from .web_viewer import vendor_js, viewer_css, viewer_js

        payload = viewer["payload"]
        slug = payload["slug"]
        payload_json = json.dumps(
            payload, separators=(",", ":")).replace("</", "<\\/")
        viewer_style = viewer_css()
        viewer_html = (
            '<section class="viewer-section" aria-label="Interactive 3D">'
            "<h2>Explore the build in 3D</h2>"
            "<p>Screen only — this section does not print. Use the explode "
            "control to separate the compiled parts and the milestone "
            "steps to isolate what each stage adds; click any part for its "
            "size. Purchased hardware remains schedule items, not false "
            "geometry.</p>"
            f'<div class="viewer-slot" data-detail="{_e(slug)}">'
            f'<img src="{_as_data_uri(viewer["isometric"])}" '
            'alt="Interactive assembly preview">'
            '<button type="button" class="viewer-btn">Explore in 3D'
            "</button></div></section>"
            f'<script type="application/json" id="detail-data-{_e(slug)}">'
            f"{payload_json}</script>"
            f'<script type="text/plain" id="detail-glb-{_e(slug)}">'
            f'{viewer["glb_b64"]}</script>'
        )
        viewer_script = f"<script>{vendor_js()}\n{viewer_js()}</script>"

    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<link rel="icon" href="data:,">\n'
        f"<title>{_e(consumer.title)}</title>\n"
        f"<style>{_STYLE}{viewer_style}</style></head>\n"
        f"<body>{''.join(sheets)}{viewer_html}{viewer_script}</body></html>")
