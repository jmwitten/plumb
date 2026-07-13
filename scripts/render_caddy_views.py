"""Rasterize shaded views of the caddy assembly with matplotlib (no Blender).

Tessellates each part's world solid and draws it as a lit Poly3DCollection, from
a set of primary + zoom camera angles, saving one PNG per view. Used to produce
images for the adversarial visual review (task 8) in an environment without a
Blender/GPU render path.
"""
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from detailgen.spec.compiler import compile_spec_file

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else (Path(__file__).resolve().parents[1] / "outputs" / "armchair_caddy" / "views")
OUT.mkdir(parents=True, exist_ok=True)

SPEC = Path(__file__).resolve().parents[1] / "details" / "armchair_caddy.spec.yaml"
d = compile_spec_file(SPEC)
d.build()

# per-part face color by role/material (RGB 0..1)
COLOR = {
    "sofa arm": (0.78, 0.75, 0.70),        # existing context — pale stone/tan
    "side board +X": (0.80, 0.62, 0.42),   # SPF wood
    "side board -X": (0.80, 0.62, 0.42),
    "top board": (0.66, 0.48, 0.30),       # PT decking, darker
    "registration rail +X": (0.86, 0.72, 0.50),   # 1x6 rail — lighter wood so it reads apart
    "registration rail -X": (0.86, 0.72, 0.50),
}
SCREW = (0.55, 0.57, 0.60)                 # galvanized steel

ls = LightSource(azdeg=-35, altdeg=55)


def part_polys(part):
    verts, tris = part.world_solid().val().tessellate(0.05)
    V = np.array([[v.x, v.y, v.z] for v in verts])
    faces = [V[list(t)] for t in tris]
    return V, faces


def shade(base, faces):
    """Flat-shade each triangle by its normal against the light source."""
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
        pc = Poly3DCollection(faces, facecolors=shade(base, faces),
                              edgecolors=(0, 0, 0, 0.18), linewidths=0.2)
        ax.add_collection3d(pc)
    if lims is None:
        lo, hi = gmin, gmax
    else:
        lo, hi = np.array(lims[0]), np.array(lims[1])
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect((hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]))
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel("X (across arm)"); ax.set_ylabel("Y (along arm)"); ax.set_zlabel("Z up")
    ax.set_title(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / fname)
    plt.close(fig)
    print("wrote", fname)


IN = 25.4
# primary views
draw("v1_iso.png", 22, -55, "ISO — whole caddy saddling the arm")
draw("v2_front.png", 6, -89, "FRONT (along -Y): straddle, cup-hole edge, sides hang free")
draw("v3_end.png", 6, 1, "END (along -X): arm length, side-board 7in drop")
draw("v4_top.png", 88, -90, "TOP (-Z): cup-hole opening — clean show face, NO fasteners")
# zoom views
draw("z1_cup.png", 55, -60, "ZOOM cup-hole interior (top board notch)",
     lims=([-60, -60, -20], [60, 60, 40]))
draw("z2_joint.png", 26, -55, "ZOOM +X corner: hidden full-depth 1x6 rail, face-grain screws (2 pairs)",
     lims=([40, -55, -155], [125, 55, 40]))
draw("z3_gap.png", 8, -89, "ZOOM arm-clearance fit (+X rail holds the 0.25in reveal off the arm)",
     lims=([55, -75, -160], [125, 75, 35]))
print("done")

# --- arm-ghosted variants (context hidden so the joinery is inspectable) ------
draw("g1_iso.png", 24, -55, "ISO (arm hidden) — 3 boards + 2 hidden full-depth registration rails",
     hide=("sofa arm",))
draw("g2_joint.png", 30, -60, "ZOOM +X corner (arm hidden): 1x6 rail screwed up into the top + into the side face (upper + lower)",
     lims=([40, -60, -155], [125, 60, 40]), hide=("sofa arm",))
draw("g3_underside.png", -35, -55, "UNDERSIDE (arm hidden): deep rails register + fasten the top to the sides, no show-face screws",
     hide=("sofa arm",))
