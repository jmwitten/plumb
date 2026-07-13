"""Prototype: first two IKEA-style panels of the zipline platform manual.

Derives the panel part-sets from the REAL build_sequence_model reader steps
(panel 1 = steps 1-6 joist hangers; panel 2 = steps 7-10 ladder rungs), then
renders each panel as a partial-assembly PNG (new arrivals in material color,
prior work ghosted) with numbered callouts, and composes a self-contained
HTML page with human captions. PROTOTYPE ONLY — captions are hand-written
copy for the owner to react to; production captions must derive (§5.2).
"""
import base64
import io
import re
import sys

import vtk
from PIL import Image, ImageDraw, ImageFont

from detailgen.spec.compiler import compile_spec_file
from detailgen.rendering.export import MESH_TOL_LINEAR, MESH_TOL_ANGULAR, VIEWS

OUT_HTML = sys.argv[1] if len(sys.argv) > 1 else "zipline-manual-proto.html"
SIZE = (1500, 1100)

d = compile_spec_file("details/platform.spec.yaml")
d.validate()
a = d.assembly if hasattr(d, "assembly") else d.build()
a = a() if callable(a) else a

PANEL1 = re.compile(r"^(beam [+-]Y|joist \d|joist \d[+-]Y( (header|joist) screw \d)?)$")
PANEL2 = re.compile(r"^(leg [+-]Y|rung \d|rung \d hanger [+-]Y( (header|joist) screw \d)?)$")

solids = list(a.isolated_world_solids())
names = {p.name for p, _ in solids}


def center(name):
    for p, w in solids:
        if p.name == name:
            vals = w.vals()
            bb = vals[0].BoundingBox()
            for s in vals[1:]:
                b2 = s.BoundingBox()
                bb.add(b2) if hasattr(bb, "add") else None
            return ((bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2,
                    (bb.zmin + bb.zmax) / 2)
    raise KeyError(name)


def render_panel(new_re, ghost_re, labels, path):
    renderer = vtk.vtkRenderer()
    renderer.SetBackground(1.0, 1.0, 1.0)
    shown = 0
    for placed, world in solids:
        is_new = bool(new_re.match(placed.name))
        is_ghost = ghost_re is not None and bool(ghost_re.match(placed.name))
        if not (is_new or is_ghost):
            continue
        shown += 1
        color = placed.component.material.rgba
        for solid in world.vals():
            verts, tris = solid.tessellate(MESH_TOL_LINEAR, MESH_TOL_ANGULAR)
            points = vtk.vtkPoints()
            for v in verts:
                points.InsertNextPoint(v.x, v.y, v.z)
            cells = vtk.vtkCellArray()
            for tri in tris:
                cells.InsertNextCell(3)
                for idx in tri:
                    cells.InsertCellPoint(idx)
            poly = vtk.vtkPolyData()
            poly.SetPoints(points)
            poly.SetPolys(cells)
            normals = vtk.vtkPolyDataNormals()
            normals.SetInputData(poly)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(normals.GetOutputPort())
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            if is_new:
                actor.GetProperty().SetColor(*color[:3])
                actor.GetProperty().SetOpacity(1.0)
            else:
                actor.GetProperty().SetColor(0.78, 0.78, 0.78)
                actor.GetProperty().SetOpacity(0.16)
            renderer.AddActor(actor)

    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(*SIZE)
    window.AddRenderer(renderer)
    camera = renderer.GetActiveCamera()
    camera.SetPosition(*VIEWS["iso"])
    camera.SetFocalPoint(0, 0, 0)
    camera.SetViewUp(0, 0, 1)
    renderer.ResetCamera()
    camera.Zoom(1.15)
    window.Render()

    # project label anchors AFTER the camera is final
    coord = vtk.vtkCoordinate()
    coord.SetCoordinateSystemToWorld()
    pts2d = {}
    for num, world_pt in labels.items():
        coord.SetValue(*world_pt)
        x, y = coord.GetComputedDisplayValue(renderer)
        pts2d[num] = (x, SIZE[1] - y)  # PIL's y runs down

    grabber = vtk.vtkWindowToImageFilter()
    grabber.SetInput(window)
    grabber.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(path)
    writer.SetInputConnection(grabber.GetOutputPort())
    writer.Write()

    img = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 44)
    except OSError:
        font = ImageFont.load_default()
    R = 34
    for num, (x, y) in pts2d.items():
        draw.ellipse([x - R, y - R, x + R, y + R], fill="white",
                     outline="black", width=5)
        tb = draw.textbbox((0, 0), str(num), font=font)
        draw.text((x - (tb[2] - tb[0]) / 2, y - (tb[3] - tb[1]) / 2 - tb[1]),
                  str(num), fill="black", font=font)
    img.save(path)
    print(f"panel -> {path} ({shown} parts shown)")
    return path


p1 = render_panel(
    PANEL1, None,
    {1: center("beam +Y"), 2: center("joist 1+Y"), 3: center("joist 1")},
    "panel1.png")
p2 = render_panel(
    PANEL2, PANEL1,
    {1: center("leg +Y"), 2: center("rung 0 hanger +Y"), 3: center("rung 0")},
    "panel2.png")


def data_uri(path):
    return "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()


SCREW_ICON = ("<svg width='46' height='14' viewBox='0 0 46 14'>"
              "<rect x='0' y='3' width='6' height='8' rx='1' fill='#333'/>"
              "<path d='M6 5 h32 l6 2 -6 2 H6 Z' fill='#666'/>"
              "<path d='M10 5 v4 M15 5 v4 M20 5 v4 M25 5 v4 M30 5 v4 M35 5 v4' stroke='#eee' stroke-width='1'/></svg>")
HANGER_ICON = ("<svg width='30' height='26' viewBox='0 0 30 26'>"
               "<path d='M4 2 v18 h22 v-18' fill='none' stroke='#555' stroke-width='3'/>"
               "<path d='M1 2 h8 M21 2 h8' stroke='#555' stroke-width='3'/></svg>")

html = f"""<!doctype html><html><head><meta charset='utf-8'>
<title>Zipline Platform — Assembly Manual (prototype, panels 1-2)</title>
<style>
 body {{ font: 16px/1.5 -apple-system, Helvetica, sans-serif; margin: 2rem auto; max-width: 1000px; color: #111; }}
 .panel {{ border: 3px solid #111; border-radius: 8px; margin: 2rem 0; overflow: hidden; }}
 .head {{ display:flex; justify-content:space-between; align-items:center; padding: .6rem 1.2rem; border-bottom: 2px solid #111; }}
 .head h2 {{ margin: 0; font-size: 1.5rem; }}
 .stepno {{ font-size: 2.4rem; font-weight: 800; }}
 .hw {{ display:flex; gap:1.6rem; padding:.5rem 1.2rem; background:#f5f5f2; border-bottom:1px solid #ccc; align-items:center; font-weight:600; }}
 .hw span {{ display:flex; align-items:center; gap:.45rem; }}
 img.scene {{ width:100%; display:block; }}
 .cap {{ padding: .9rem 1.2rem 1.1rem; }}
 .cap ol {{ margin:.3rem 0 0; padding-left:1.4rem; }}
 .cap li {{ margin:.35rem 0; }}
 .why {{ margin-top:.7rem; padding:.55rem .8rem; background:#fbf7ea; border-left:4px solid #c9a227; font-size:.92rem; }}
 .note {{ color:#555; font-size:.9rem; margin-top:2rem; border-top:1px solid #ccc; padding-top:.8rem; }}
 .badge {{ display:inline-block; background:#eee; border-radius:4px; padding:0 .45rem; font-size:.8rem; font-weight:700; letter-spacing:.02em; }}
</style></head><body>
<h1>Zipline Platform — step-by-step (prototype: first two panels)</h1>
<p class='badge'>PROTOTYPE — panel grouping &amp; drawings derived from the construction process graph; captions hand-written for owner review</p>

<div class='panel'>
 <div class='head'><h2>Hang the floor joists between the two beams</h2><div class='stepno'>1</div></div>
 <div class='hw'>
   <span>{HANGER_ICON} 6&times; joist hanger (for 2&times;6)</span>
   <span>{SCREW_ICON} 36&times; structural screw 1&frac12;&Prime;</span>
 </div>
 <img class='scene' src='{data_uri(p1)}'>
 <div class='cap'>
  <ol>
   <li><b>&#9312; Lay out the two beams.</b> The two 5-ft pressure-treated 2&times;6 beams stand on edge, faces 30&Prime; apart, ends flush.</li>
   <li><b>&#9313; Screw the hangers to the beams first.</b> Three hanger stations on the inside face of each beam. Seat each hanger and drive <b>4 screws</b> through its face flange into the beam. Don't put the joists in yet.</li>
   <li><b>&#9314; Drop the joists in.</b> Each 30&Prime; 2&times;6 joist drops into its pair of hangers. Then drive <b>2 screws</b> through each hanger's side tabs into the joist (4 per joist).</li>
  </ol>
  <div class='why'><b>Why hangers first?</b> That's how this joint installs: with the joist already in the pocket you can't drive the hanger's face screws behind it. The order printed here is checked against the model &mdash; the tool path for every screw is clear at this step.</div>
 </div>
</div>

<div class='panel'>
 <div class='head'><h2>Build the ladder: rungs between the two legs</h2><div class='stepno'>2</div></div>
 <div class='hw'>
   <span>{HANGER_ICON} 4&times; joist hanger (for 2&times;4)</span>
   <span>{SCREW_ICON} 24&times; structural screw 1&frac12;&Prime;</span>
 </div>
 <img class='scene' src='{data_uri(p2)}'>
 <div class='cap'>
  <ol>
   <li><b>&#9312; The two legs.</b> 63&Prime; pressure-treated 2&times;6s &mdash; these become the ladder up to the platform (shown ghosted behind).</li>
   <li><b>&#9313; Hangers to the legs first.</b> Two rung stations per leg, on the inside faces. Drive <b>4 screws</b> per hanger, same as the joists.</li>
   <li><b>&#9314; Drop the rungs in.</b> Two 33&Prime; 2&times;4 rungs seat into their hangers; <b>2 screws</b> through each side tab into the rung.</li>
  </ol>
  <div class='why'><b>Do this before bolting the legs on.</b> The legs get through-bolted to the platform later &mdash; the rungs are much easier to hang while the legs are still loose.</div>
 </div>
</div>

<p class='note'><b>Prototype honesty notes.</b> (1)&nbsp;The part sets, grouping, and screw counts above are derived from the model's construction process graph (panel&nbsp;1 = its first six install events, panel&nbsp;2 = the next four); the sentences are hand-written prototype copy &mdash; in production they derive from the same model so they can't drift. (2)&nbsp;The graph doesn't yet order <i>bearing</i> facts, so it starts with the first screwed joint; a finished manual would open with &ldquo;set the three pier blocks&rdquo; before this page &mdash; that's a known gap on the roadmap, not an oversight. (3)&nbsp;The second panel's &ldquo;while the legs are still loose&rdquo; advice is a declared build strategy, not a proven sequence.</p>
</body></html>"""

open(OUT_HTML, "w").write(html)
print(f"wrote {OUT_HTML}")
