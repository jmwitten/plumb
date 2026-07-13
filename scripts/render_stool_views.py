"""Rasterize shaded views of the kids' two-step step stool with matplotlib (no Blender).

Same approach as render_caddy_views.py (its own script, untouched): tessellate each
part's world solid, draw it as a lit Poly3DCollection from a set of primary + zoom
camera angles, one PNG per view. Feeds the single-detail build document + the
adversarial visual review.
"""
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from detailgen.spec.compiler import compile_spec_file

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path(__file__).resolve().parents[1] / "outputs" / "step_stool" / "views")
OUT.mkdir(parents=True, exist_ok=True)

SPEC = Path(__file__).resolve().parents[1] / "details" / "step_stool.spec.yaml"
d = compile_spec_file(SPEC)
d.build()

COLOR = {
    "floor": (0.72, 0.72, 0.70),           # existing context — pale grey
    "side panel +X": (0.80, 0.62, 0.42),   # SPF panel
    "side panel -X": (0.80, 0.62, 0.42),
    "upper tread": (0.66, 0.48, 0.30),      # PT decking, darker
    "lower tread": (0.66, 0.48, 0.30),
    "cleat +X": (0.86, 0.72, 0.50),         # 1x2 cleat — lighter so it reads apart
    "cleat -X": (0.86, 0.72, 0.50),
}
SCREW = (0.55, 0.57, 0.60)                  # galvanized steel


def part_polys(part):
    verts, tris = part.world_solid().val().tessellate(0.1)
    V = np.array([[v.x, v.y, v.z] for v in verts])
    faces = [V[list(t)] for t in tris]
    return V, faces


def shade(base, faces):
    cols = []
    for f in faces:
        n = np.cross(f[1] - f[0], f[2] - f[0])
        ln = np.linalg.norm(n)
        n = n / ln if ln > 1e-9 else np.array([0, 0, 1.0])
        lv = np.array([-0.4, -0.5, 0.9]); lv = lv / np.linalg.norm(lv)
        s = 0.45 + 0.55 * max(0.0, float(np.dot(n, lv)))
        cols.append((base[0] * s, base[1] * s, base[2] * s, 1.0))
    return cols


PARTS = []
allV = []
for p in d.assembly.parts:
    base = COLOR.get(p.name, SCREW)
    V, faces = part_polys(p)
    allV.append(V)
    PARTS.append((p.name, base, faces))
allV = np.vstack(allV)
gmin, gmax = allV.min(0), allV.max(0)


def draw(fname, elev, azim, title, lims=None, hide=()):
    fig = plt.figure(figsize=(7, 6), dpi=130)
    ax = fig.add_subplot(111, projection="3d")
    for name, base, faces in PARTS:
        if name in hide:
            continue
        ax.add_collection3d(Poly3DCollection(
            faces, facecolors=shade(base, faces),
            edgecolors=(0, 0, 0, 0.18), linewidths=0.2))
    if lims is None:
        lo, hi = gmin, gmax
    else:
        lo, hi = np.array(lims[0]), np.array(lims[1])
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect((hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]))
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel("X (width)"); ax.set_ylabel("Y (depth)"); ax.set_zlabel("Z up")
    ax.set_title(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / fname)
    plt.close(fig)
    print("wrote", fname)


IN = 25.4
# primary views (floor shown)
draw("v1_iso.png", 22, -55, "ISO — the two-step stool on the floor")
draw("v2_front.png", 8, -89, "FRONT (along -Y): two step surfaces (5.5in + 10.25in), footprint width")
draw("v3_side.png", 8, 1, "SIDE (along -X): depth, front/back tread stagger, toe room")
draw("v4_top.png", 88, -90, "TOP (-Z): both treads, screw pattern")
# floor-hidden variants (the stool joinery reads without the slab)
draw("g1_iso.png", 24, -55, "ISO (floor hidden) — panels + 2 treads + cleats", hide=("floor",))
draw("z_cleat.png", -18, -108, "ZOOM +X lower-tread cleat (from below, inside): 1x2 cleat_screwed to the panel face; the tread rests on the cleat top",
     lims=([10, -150, 20], [140, 30, 130]), hide=("floor", "side panel -X", "cleat -X"))
draw("z_upper.png", 22, -60, "ZOOM +X upper joint: tread rail_cap_screwed down onto the panel top",
     lims=([40, -40, 160], [170, 160, 290]), hide=("floor",))
print("done ->", OUT)
