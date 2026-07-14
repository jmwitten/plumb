"""Print-first HTML composition for the consumer assembly manual.

One `section.sheet` per composed Letter page; CSS pagination guarantees no
frame splits across printed pages. High-contrast, grayscale-legible reader
register: reader names and hardware letters only — machine identifiers stay
in data attributes for traceability and never in visible text.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path

from .action_frames import FrameContractError
from .consumer_pages import ConsumerManual
from .instruction_manual import _icon_svg
from .part_labels import part_labels


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _data_uri(path: Path) -> str:
    payload = base64.b64encode(Path(path).read_bytes()).decode()
    return f"data:image/png;base64,{payload}"


def _letter_chip(letter: str, quantity: int) -> str:
    return (f'<span class="chip hardware-chip">'
            f'<b>{_e(letter)}</b> &times;{quantity}</span>')


def _frame_html(detail, frame, number: int | None, image_path: Path) -> str:
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
    key_names = []
    for part_id in frame.focus_part_ids:
        name = labels[part_id].reader_name
        if name not in key_names:
            key_names.append(name)
    picture_key = "".join(f"<li>{_e(name)}</li>" for name in key_names[:6])
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
    return (
        f'<article class="frame" data-frame-id="{_e(frame.frame_id)}" '
        f'data-step-ids="{_e(",".join(frame.source_step_ids))}">'
        f"{header}"
        f'<figure><img src="{_data_uri(image_path)}" '
        f'alt="Assembly view: step {number}">'
        f"{inset}</figure>"
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
                     tools: tuple[str, ...]) -> str:
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
        f"{kit}<h2>Parts</h2><ul class=\"parts\">{parts}</ul>"
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
:root { --ink: #14161a; --line: #444; --paper: #fff; }
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
.inventory h2 { margin: 0.55rem 0 0.25rem; }
ul.parts, ul.letters, ul.tools { list-style: none; margin: 0.1rem 0;
  padding: 0; font-size: 0.78rem; }
ul.parts li, ul.letters li, ul.tools li { display: flex; gap: 0.4rem;
  align-items: center; margin: 0.14rem 0; min-width: 0;
  break-inside: avoid; }
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
  padding: 0.5rem 0.7rem 0.7rem; margin: 0 0 0.55rem;
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
.frame img { display: block; max-width: 100%; max-height: 2.7in;
  width: auto; height: auto; margin: 0 auto; background: var(--paper); }
.inset-note { font-size: 0.8rem; color: var(--line); }
.caption { font-size: 0.98rem; margin: 0.35rem 0 0.15rem; }
.tool { margin: 0.1rem 0; font-size: 0.82rem; color: #222; }
.tool::before { content: "Tool: "; font-weight: 800; }
.warning, .hold-note { display: flex; gap: 0.5rem; align-items: baseline;
  border: 3px solid var(--ink); border-left-width: 12px; border-radius: 6px;
  padding: 0.28rem 0.55rem; margin: 0.3rem 0; font-weight: 600;
  font-size: 0.85rem; }
.hold-frame { border-width: 6px; }
.hold-frame .warning { font-size: 1.05rem; }
.picture-key { list-style: none; display: flex; flex-wrap: wrap;
  gap: 0.15rem 0.8rem; margin: 0.25rem 0 0; padding: 0; font-size: 0.72rem;
  color: #333; }
.picture-key li::before { content: "\\25A0"; margin-right: 0.3rem; }
.record table { width: 100%; table-layout: fixed; border-collapse: collapse;
  font-size: 0.85rem; }
.record th, .record td { border: 1.5px solid var(--ink); padding: 0.45rem;
  text-align: left; vertical-align: top; overflow-wrap: anywhere; }
.record .entry { width: 30%; height: 2.4rem; }
.page-number { text-align: right; font-size: 0.72rem; color: #555;
  padding-top: 0.25rem; }
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
}
"""


def render_consumer_manual_html(
    detail,
    consumer: ConsumerManual,
    image_paths: dict[str, Path],
    *,
    cover_image: str | Path,
    inventory_rows=(),
) -> str:
    """Compose the self-contained consumer manual HTML."""
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
                consumer, page.number, inventory_rows, tools))
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
                    detail, frame, number, Path(image_paths[frame.frame_id])))
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

    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<link rel="icon" href="data:,">\n'
        f"<title>{_e(consumer.title)}</title>\n"
        f"<style>{_STYLE}</style></head>\n"
        f"<body>{''.join(sheets)}</body></html>")
