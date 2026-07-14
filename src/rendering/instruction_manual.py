"""Self-contained HTML document for grouped illustrated instructions."""

from __future__ import annotations

import base64
import html
from datetime import datetime
from pathlib import Path

from .instruction_panels import InstructionPresentationError
from .instruction_render import panel_callout_ids
from .part_labels import part_labels


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def _rows(rows, class_name: str) -> str:
    if not rows:
        return ""
    body = "".join(
        f'<li data-icon="{_e(row.icon)}"><span>{_e(row.label)}</span></li>'
        for row in rows)
    return f'<ul class="{class_name}">{body}</ul>'


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
      <section class="directions">
        <h3>Do this</h3>
        <ol>{instructions}</ol>
      </section>
      {stations}
      {why}
      {honesty}
      <nav class="panel-nav" aria-label="Panel navigation">
        <a href="#panel-{max(1, panel.index - 1)}"
           class="{'disabled' if panel.index == 1 else ''}">&larr; Previous</a>
        <a href="#panel-{min(total, panel.index + 1)}"
           class="{'disabled' if panel.index == total else ''}">Next &rarr;</a>
      </nav>
    </article>"""


def render_instruction_manual_html(detail, manual, image_paths: dict[int, Path]) -> str:
    """Compose one offline HTML manual from typed panels and keyed PNGs."""
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

    inventory = "".join(
        f'<li data-icon="{_e(row.icon)}">{_e(row.label)}</li>'
        for row in manual.inventory)
    nav = "".join(
        f'<a href="#panel-{panel.index}"><b>{panel.index}</b>'
        f'<span>{_e(panel.action)}</span></a>'
        for panel in manual.panels)
    panels = "".join(
        _panel_html(detail, panel, Path(image_paths[panel.index]), len(manual.panels))
        for panel in manual.panels)
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    total = len(manual.panels)
    declared_constraints = len(
        detail._connection_checks.event_graph.constraints)
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
  show(currentFromHash(), false);
})();
</script>""".replace("__TOTAL__", str(total))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(manual.title)}</title>
<style>
:root{{--ink:#111827;--muted:#475569;--line:#cbd5e1;--paper:#fff;--blue:#2563eb;
--blue-soft:#eff6ff;--amber:#92400e;--amber-soft:#fffbeb;--red:#991b1b;--red-soft:#fef2f2}}
*{{box-sizing:border-box}} html{{scroll-behavior:smooth}}
body{{margin:0;background:#e2e8f0;color:var(--ink);font:16px/1.48 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
.manual{{max-width:1050px;margin:0 auto;background:var(--paper);min-height:100vh;box-shadow:0 0 30px #64748b55}}
.manual-head{{padding:2rem 2.25rem 1.5rem;background:#0f172a;color:white}}
.eyebrow{{font-size:.78rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#93c5fd}}
h1{{font-size:clamp(2rem,5vw,3.25rem);line-height:1.05;margin:.35rem 0 .75rem}} h2,h3{{line-height:1.2}}
.lede{{max-width:760px;color:#dbeafe;font-size:1.07rem}} .manual-link{{display:inline-block;margin-top:.8rem;padding:.65rem .85rem;border:1px solid #93c5fd;border-radius:7px;color:white;font-weight:750;text-decoration:none}}
.generated{{margin-top:1rem;font-size:.78rem;color:#94a3b8}}
.overview{{padding:1.4rem 2.25rem;border-bottom:1px solid var(--line);display:grid;grid-template-columns:1.1fr 1fr;gap:1.25rem}}
.overview h2{{margin:.1rem 0 .55rem;font-size:1.05rem}} .inventory{{margin:.2rem 0;padding-left:1.25rem}}
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
.resources ul{{display:flex;flex-wrap:wrap;gap:.5rem 1.2rem;list-style:none;margin:0;padding:0}} .resources li{{font-weight:700;font-size:.9rem}}
.resources li:before{{content:"•";color:var(--blue);margin-right:.45rem}} .badge{{font-size:.74rem;font-weight:850;text-transform:uppercase;padding:.25rem .5rem;border-radius:999px;background:#e2e8f0}}
.hard-stop{{background:#fee2e2;color:#991b1b}} figure{{margin:0}} img.scene{{display:block;width:100%;height:auto;background:white}}
figcaption{{display:flex;align-items:center;flex-wrap:wrap;gap:.6rem 1rem;padding:.55rem 1rem;background:#f8fafc;border-top:1px solid var(--line);font-size:.86rem}}
.picture-key{{display:flex;gap:.8rem 1.15rem;flex-wrap:wrap;list-style:none;margin:0;padding:0}} .picture-key li{{display:flex;align-items:center;gap:.35rem}}
.callout-number{{display:inline-grid;place-items:center;width:1.55rem;height:1.55rem;border:2px solid var(--ink);border-radius:50%;background:white;font-weight:850}}
.render-legend{{margin-left:auto;color:var(--muted)}} .swatch{{display:inline-block;width:.85rem;height:.85rem;border:1px solid #64748b;margin:0 .3rem 0 .8rem;vertical-align:-.1rem}} .current{{background:#9a7b4f}} .ghost{{background:#e5e7eb}}
.directions,.station-box,.why,.honesty{{margin:1rem 1.2rem;padding:.8rem 1rem;border-radius:7px}} .directions{{padding:0 1rem}} .directions h3,.station-box h3,.why h3,.honesty h3{{font-size:1rem;margin:.1rem 0 .45rem}}
.directions li,.station-box li{{margin:.35rem 0}} .station-box{{background:var(--blue-soft);border-left:5px solid var(--blue)}}
.station-box ul{{margin:.2rem 0;padding-left:1.2rem}} .why{{background:var(--amber-soft);border-left:5px solid #d97706}} .why p,.honesty p{{margin:.3rem 0}}
.honesty{{background:var(--red-soft);border-left:5px solid #dc2626}} .panel-nav{{display:flex;justify-content:space-between;padding:.8rem 1.2rem;border-top:1px solid var(--line)}}
.panel-nav a{{color:var(--blue);font-weight:750;text-decoration:none}} .panel-nav .disabled{{visibility:hidden}}
@media(max-width:700px){{.overview{{grid-template-columns:1fr}}.instruction-panel{{margin:1rem .5rem}}.manual-head,.overview{{padding-left:1rem;padding-right:1rem}}.panel-index{{grid-template-columns:repeat(3,1fr)}}.render-legend{{width:100%;margin-left:0}}.panel-controls{{grid-template-columns:auto 1fr auto}}#panel-progress{{grid-column:1/-1;text-align:center}}}}
@media print{{body{{background:white}}.manual{{box-shadow:none;max-width:none}}.instruction-panel{{break-inside:avoid;margin:1rem 0}}.panel-nav{{display:none}}.panel-controls{{display:none}}.manual-link{{color:white}}}}
</style></head><body><main class="manual">
<header class="manual-head"><div class="eyebrow">Model-backed · illustrated assembly</div>
<h1>{_e(manual.title)}</h1>
<p class="lede">This is one machine-checked build order from the validated construction process graph. Its phase boundary includes {_e(declared_constraints)} authored process-order constraints; their declared reasons are printed where they apply. Deterministic tie-breaks between otherwise independent events are a readable build choice, not proof that no other valid order exists. Colored parts are current work, pale gray parts are already present, and blue marks share the compiled measurements used by the placement text.</p>
<a class="manual-link" href="{_e(manual.technical_href)}">Open the technical build document &rarr;</a>
<div class="generated">Generated {_e(generated)} · Offline/self-contained</div></header>
<section class="overview"><div><h2>Modeled parts</h2><ul class="inventory">{inventory}</ul></div>
<div><h2>Five-panel build path</h2><nav class="panel-index">{nav}</nav></div></section>
<nav class="panel-controls" aria-label="Assembly panel navigator">
  <button id="panel-prev" type="button">&larr;</button>
  <input id="panel-slider" type="range" min="1" max="{total}" value="1" step="1"
         aria-label="Assembly panel">
  <button id="panel-next" type="button">&rarr;</button>
  <output id="panel-progress" for="panel-slider">Panel 1 of {total}</output>
</nav>
{panels}
</main>{navigation_script}</body></html>"""
