"""Rasterize shaded views of the sit-and-reach test box with matplotlib (no Blender).

Same approach as render_stool_views.py / render_caddy_views.py (their own scripts,
untouched): tessellate each part's world solid, draw it as a lit Poly3DCollection
from a set of primary + zoom camera angles, one PNG per view. Feeds the
single-detail build document + the adversarial visual review.
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
    Path(__file__).resolve().parents[1] / "outputs" / "sit_reach_box" / "views")
OUT.mkdir(parents=True, exist_ok=True)

SPEC = Path(__file__).resolve().parents[1] / "details" / "sit_reach_box.spec.yaml"
d = compile_spec_file(SPEC)
d.build()

PLY = (0.85, 0.72, 0.50)                      # sanded ply
COLOR = {
    "floor": (0.72, 0.72, 0.70),              # existing context — pale grey
    "side panel +X": PLY,
    "side panel -X": PLY,
    "front (foot) panel": (0.78, 0.60, 0.40),  # the FOOT FACE — darker so it reads
    "back panel": PLY,
    "top plate (reach surface)": (0.90, 0.80, 0.60),  # the scale surface — lightest
}
SCREW = (0.55, 0.57, 0.60)                    # zinc/galv steel


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
# primary views (floor shown; the sitter is at -Y)
draw("v1_iso.png", 22, -125, "ISO from the sitter's side — the 23cm overhang over the sitter's legs")
draw("v2_side.png", 8, 1, "SIDE (along -X): THE protocol view — 12in reach surface, 23cm foot-line overhang")
draw("v3_front.png", 8, -91, "FRONT (facing the foot face): the 12in-wide plane the soles press")
draw("v4_top.png", 88, -90, "TOP (-Z): the reach/scale surface and the screw stations")
# floor-hidden hero + zooms
draw("g1_iso.png", 24, -125, "ISO (floor hidden) — five-panel box: sides, captured front/back, capping top",
     hide=("floor",))
draw("z_corner.png", 10, -15, "ZOOM +X front corner (floor, top + near side hidden): butt_screwed — the screw's head sits where the hidden side's outside face was, its shank biting the front panel's ply edge",
     lims=([90, -40, 0], [250, 340, 300]),
     hide=("floor", "top plate (reach surface)", "side panel +X"))
draw("z_overhang.png", 6, -18, "ZOOM overhang from the sitter's side: the top plate cantilevers 9.055in (23cm) past the foot face",
     lims=([-180, -260, 200], [180, 60, 330]), hide=("floor",))
print("done ->", OUT)
