"""Rasterize shaded views of the 3-foot backyard trebuchet with matplotlib (no
Blender). Same approach as render_sitreach_views.py / render_stool_views.py
(their own scripts, untouched): tessellate each part's world solid, draw it as a
lit Poly3DCollection from a set of primary + zoom camera angles, one PNG per
view. Feeds the single-detail build document + the adversarial visual review.

View selection is the auditable decision table in
reviews/visual/trebuchet-view-coverage.json (view-coverage-directive.md).
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
    Path(__file__).resolve().parents[1] / "outputs" / "trebuchet" / "views")
OUT.mkdir(parents=True, exist_ok=True)

SPEC = Path(__file__).resolve().parents[1] / "details" / "trebuchet.spec.yaml"
d = compile_spec_file(SPEC)
d.build()

LUM = (0.82, 0.70, 0.48)                       # 2x4 framing lumber
DECK = (0.76, 0.58, 0.38)                      # 5/4x6 deck board (uprights)
ARM = (0.88, 0.52, 0.30)                       # the throwing arm — the mechanism, warmest
PLY = (0.90, 0.82, 0.62)                       # sanded ply (gussets, runway)
STEEL = (0.55, 0.57, 0.62)                     # zinc rod / nuts / washers
COLOR = {
    "ground": (0.72, 0.72, 0.70),              # existing context — pale grey
    "base rail +X": LUM, "base rail -X": LUM,
    "cross member front": LUM, "cross member mid": LUM, "cross member rear": LUM,
    "upright +X": DECK, "upright -X": DECK,
    "gusset knee +X": PLY, "gusset knee -X": PLY,
    "runway plate": PLY,
    "throwing arm": ARM,
    "axle rod": (0.42, 0.44, 0.50),            # the rod darker so it reads in the stack
}


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
    base = COLOR.get(p.name, STEEL)
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
    ax.set_xlabel("X (across)"); ax.set_ylabel("Y (throw axis)"); ax.set_zlabel("Z up")
    ax.set_title(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / fname)
    plt.close(fig)
    print("wrote", fname)


IN = 25.4
# primary views (ground shown; LAUNCH is toward -Y, the cocked tip goes +Y)
draw("v1_iso.png", 20, -128,
     "ISO, launch side — level-arm reference pose")
draw("v2_side.png", 6, 1,
     "SIDE: the mechanism elevation — 32in axle, 4:1 arm")
draw("v3_front.png", 8, -91,
     "FRONT (down the throw axis): the 14in CW lane")
draw("v4_top.png", 88, -90,
     "TOP: ladder base, runway, arm over the centerline")
# ground-hidden hero + zooms
draw("g1_iso.png", 22, -128,
     "ISO (ground hidden) — frame, rod axle, hung arm",
     hide=("ground",))
draw("z_pivot.png", 22, -40,
     "ZOOM pivot, ARM HIDDEN: rod through both uprights",
     lims=([1 * IN, -7 * IN, 27 * IN], [11 * IN, 7 * IN, 37 * IN]),
     hide=("ground", "throwing arm"))
draw("z_lap.png", 14, -38,
     "ZOOM base corner (+X): upright lap, gusset knee, cross",
     lims=([2 * IN, -12 * IN, 0], [14 * IN, 12 * IN, 16 * IN]),
     hide=("ground",))
draw("z_arm.png", 24, -42,
     "ZOOM arm on rod (uprights hidden): bore rides the shank",
     lims=([-5 * IN, -8 * IN, 27 * IN], [9 * IN, 8 * IN, 37 * IN]),
     hide=("ground", "upright +X", "upright -X", "gusset knee +X", "gusset knee -X"))

# --------------------------------------------------------------------------- #
# DRAWDIM sheets — 2D derived-dimension drawings. Every rectangle is a placed
# part's own world bounding box; every printed number is read from the compiled
# spec namespace or a placed bbox — NOTHING is hand-typed. Added after a
# naive-builder review: the frame built fine from the shaded views, but every
# load-bearing NUMBER (stations, bore heights, screw lengths, stack order,
# launch direction) lived in prose only. These sheets put the numbers ON paper.
# --------------------------------------------------------------------------- #
import matplotlib.patches as mp

ns = d.namespace
PART = {p.name: p for p in d.assembly.parts}


def bb_in(name):
    b = PART[name].world_solid().val().BoundingBox()
    return (b.xmin / IN, b.xmax / IN, b.ymin / IN, b.ymax / IN,
            b.zmin / IN, b.zmax / IN)


def fmt(v):
    """Inches, rounded past tessellation noise (13.9998 -> 14)."""
    return f"{round(v, 3):g}"


def rect(ax, a, b, c, e, fc, ec="k", lw=0.8, ls="-", alpha=1.0, z=2):
    ax.add_patch(mp.Rectangle((a, c), b - a, e - c, facecolor=fc, edgecolor=ec,
                              lw=lw, ls=ls, alpha=alpha, zorder=z))


def hdim(ax, y0, y1, z, label, off=0.9, fs=7.5, color="k"):
    ax.annotate("", (y0, z), (y1, z),
                arrowprops=dict(arrowstyle="<->", color=color, lw=0.9))
    ax.text((y0 + y1) / 2, z + off, label, ha="center", va="bottom",
            fontsize=fs, color=color)


def vdim(ax, y, z0, z1, label, off=0.6, fs=7.5, color="k"):
    ax.annotate("", (y, z0), (y, z1),
                arrowprops=dict(arrowstyle="<->", color=color, lw=0.9))
    ax.text(y + off, (z0 + z1) / 2, label, ha="left", va="center",
            fontsize=fs, rotation=90, color=color)


def note(ax, xy, xytext, text, fs=7.5, color="k"):
    ax.annotate(text, xy=xy, xytext=xytext, fontsize=fs, color=color,
                ha="left", va="center",
                arrowprops=dict(arrowstyle="->", color=color, lw=0.8))


def side_frame(ax, ghost_arm=True):
    """The side elevation (Y-Z) from placed bboxes: rail, crosses (dashed —
    they hide behind the rail in this view), runway, upright, knee, rod, arm."""
    rl = bb_in("base rail +X")
    rect(ax, rl[2], rl[3], rl[4], rl[5], LUM)
    for nm in ("cross member front", "cross member mid", "cross member rear"):
        c = bb_in(nm)
        rect(ax, c[2], c[3], c[4], c[5], "none", ec="0.35", ls="--", lw=0.7)
    rw = bb_in("runway plate")
    rect(ax, rw[2], rw[3], rw[4], rw[5], PLY)
    up = bb_in("upright +X")
    rect(ax, up[2], up[3], up[4], up[5], DECK)
    gu = bb_in("gusset knee +X")
    rect(ax, gu[2], gu[3], gu[4], gu[5], PLY, alpha=0.85)
    rod = bb_in("axle rod")
    ax.add_patch(mp.Circle((0, (rod[4] + rod[5]) / 2), (rod[5] - rod[4]) / 2,
                           facecolor="0.3", zorder=5))
    if ghost_arm:
        am = bb_in("throwing arm")
        rect(ax, am[2], am[3], am[4], am[5], ARM)
    ax.axhline(0, color="0.6", lw=0.8)


# --- Sheet D1: dimensioned side elevation ---------------------------------- #
fig, ax = plt.subplots(figsize=(11, 7.5), dpi=140)
side_frame(ax)
am = bb_in("throwing arm")
rl = bb_in("base rail +X")
up = bb_in("upright +X")
rw = bb_in("runway plate")

# Arm split + which end is which (the wrong-end bore is the wrong machine).
hdim(ax, am[2], 0, am[5] + 2.2, f'{ns["long_arm"]:g}" THROW SIDE')
hdim(ax, 0, am[3], am[5] + 2.2, f'{ns["short_arm"]:g}" CW SIDE')
ax.text(am[3] + 1.2, (am[4] + am[5]) / 2,
        "COUNTERWEIGHT END\n(bucket hangs here)", fontsize=8, va="center",
        color="darkred", fontweight="bold")
ax.text(am[2] - 1.2, (am[4] + am[5]) / 2, "THROW TIP\n(sling + release pin)",
        fontsize=8, va="center", ha="right", color="darkgreen",
        fontweight="bold")
ax.annotate("LAUNCHES THIS WAY", (am[2] - 2, 20), (am[2] + 14, 20),
            fontsize=10, color="darkgreen", fontweight="bold", va="center",
            arrowprops=dict(arrowstyle="-|>", color="darkgreen", lw=2))
# Governing verticals.
vdim(ax, rl[3] + 4.5, 0, ns["axle_h"], f'AXLE {ns["axle_h"]:g}"')
vdim(ax, rl[3] + 8.5, 0, up[5], f'UPRIGHT {up[5]:g}"')
vdim(ax, rl[2] - 3.0, 0, rw[5], f'RUNWAY TOP {ns["runway_top"]:g}"')
gu = bb_in("gusset knee +X")
vdim(ax, gu[3] + 1.0, 0, ns["gusset_h"],
     f'KNEE {ns["gusset_h"]:g}" (plain rectangle, no taper)', off=0.9)
# Base stations, chained from the REAR rail end (one datum, tape once).
zc = -3.2
for nm, tag in (("cross member rear", "REAR CROSS"),
                ("cross member mid", "MID CROSS"),
                ("cross member front", "FRONT CROSS")):
    c = bb_in(nm)
    mid = (c[2] + c[3]) / 2
    hdim(ax, mid, rl[3], zc, f'{tag} {rl[3] - mid:g}"', off=-2.6, fs=7)
    zc -= 3.4
hdim(ax, 0, rl[3], zc, f'AXLE PLANE {rl[3]:g}" from rear end '
     f'({-rl[2]:g}" from front end)', off=-2.6, fs=7)
zc -= 3.4
ax.text(rl[3], zc, "station chain: all from the REAR rail end, to centers "
        "— set the tape once", fontsize=7.5, ha="right", style="italic")
# Screw map (lengths from the spec's own params, per joint).
note(ax, (bb_in("cross member rear")[2] + 1.75, 0.75), (12, 8.5),
     f'cross ends: 2 screws/end, {ns["screw_len_butt"]:g}" thru the rail\n'
     f'into the cross END GRAIN (drive from outside)')
note(ax, (1.5, 2.0), (13, 13.5),
     f'upright lap: 3 screws, {ns["screw_len_lap"]:g}" thru the RAIL\n'
     f'into the upright (drive from outside)')
note(ax, (-4, 15), (-28, 12),
     f'knee: 3 screws, {ns["screw_len_ply"]:g}" thru the ply\n'
     f'into the upright (drive from the lane side)')
note(ax, (bb_in("cross member mid")[2] + 1.75, rw[5]), (16, 5.5),
     f'runway: 2 screws per cross, {ns["screw_len_ply"]:g}" straight down,\n'
     f'countersunk FLUSH (pouch slide lane)')
note(ax, (0, ns["axle_h"] - 3), (-32, 25),
     f'axle bores: uprights {ns["bore_up"]:g}" dia at {ns["axle_h"]:g}" up;\n'
     f'arm {ns["bore_arm"]:g}" dia at {ns["short_arm"]:g}" from the CW end\n'
     f'(stations repeated on the cut plan)')
ax.set_xlim(am[2] - 16, rl[3] + 12)
ax.set_ylim(zc - 6, am[5] + 7)
ax.set_aspect("equal")
ax.axis("off")
ax.set_title("D1 — DIMENSIONED SIDE ELEVATION (every number derived from the "
             "compiled model; +Y = rear/cocked side)", fontsize=10)
fig.tight_layout()
fig.savefig(OUT / "d1_dimensions.png")
plt.close(fig)
print("wrote d1_dimensions.png")

# --- Sheet D2: pivot stack, front view (X-Z) -------------------------------- #
fig, ax = plt.subplots(figsize=(10, 6), dpi=140)
for nm in ("upright +X", "upright -X"):
    b = bb_in(nm)
    rect(ax, b[0], b[1], b[4], b[5], DECK)
rodb = bb_in("axle rod")
rect(ax, rodb[0], rodb[1], rodb[4], rodb[5], "0.35")
amb = bb_in("throwing arm")
rect(ax, amb[0], amb[1], amb[4], amb[5], ARM)
HW = ("axle nut -X outer", "axle washer -X outer", "axle washer -X inner",
      "axle nut -X inner", "arm jam nut -X outer", "arm jam nut -X inner",
      "arm washer -X", "arm washer +X", "arm jam nut +X inner",
      "arm jam nut +X outer", "axle nut +X inner", "axle washer +X inner",
      "axle washer +X outer", "axle nut +X outer")
for nm in HW:
    b = bb_in(nm)
    rect(ax, b[0], b[1], b[4], b[5], "0.55", ec="k", lw=0.6)
# Stack-order labels, one side annotated (mirror identical).
order = [("axle nut +X outer", "washer + NUT outside"),
         ("axle nut +X inner", "NUT + washer inside"),
         ("arm jam nut +X outer", "double JAM NUTS"),
         ("arm washer +X", "fender thrust washer (flush to the arm;\n"
                           "back off a paper's width in the field)")]
ztext = 38.5
for nm, lab in order:
    b = bb_in(nm)
    note(ax, ((b[0] + b[1]) / 2, b[5]), ((b[0] + b[1]) / 2 - 1.5, ztext), lab,
         fs=7.5)
    ztext += 2.0
upP, upM = bb_in("upright +X"), bb_in("upright -X")
hdim(ax, upM[1], upP[0], 27.2, f'{fmt(upP[0] - upM[1])}" COUNTERWEIGHT LANE '
     f'(bucket swings through here)')
ax.text(0, 25.2,
        "THREADING ORDER (before standing the second upright): nut+washer > "
        "first upright > washer+nut >\njam pair+thrust washer > ARM > thrust "
        "washer+jam pair > nut+washer > second upright > washer+nut",
        fontsize=7.5, ha="center")
ax.set_xlim(-13, 13)
ax.set_ylim(24.2, 47)
ax.set_aspect("equal")
ax.axis("off")
ax.set_title("D2 — PIVOT STACK, front view (parts drawn at their modeled "
             "positions; wax the rod — the arm must spin dead-free)",
             fontsize=10)
fig.tight_layout()
fig.savefig(OUT / "d2_pivot_stack.png")
plt.close(fig)
print("wrote d2_pivot_stack.png")

# --- Sheet D3: OPERATING DIAGRAM (cocked pose + rigging, declared schematic) - #
# The cocked pose is ARITHMETIC over the modeled geometry (arm rotated about
# the axle until the tip sits a declared 2in above the runway); the rigging
# lengths are the doc's declared recipe (17.5in hang, 34in sling legs). Kinematics
# are NOT ANALYZED — this sheet shows WHERE THINGS GO; it proves nothing.
fig, ax = plt.subplots(figsize=(11, 7.5), dpi=140)
side_frame(ax, ghost_arm=False)
am = bb_in("throwing arm")
rect(ax, am[2], am[3], am[4], am[5], "none", ec=ARM, ls=":", lw=1.2)
ax.text(am[2] + 3, am[5] + 0.6, "level reference pose (modeled)", fontsize=7,
        color=ARM)
TIP_CLEAR = 2.0                    # declared: tip pulled to 2in above the runway
tip_z = ns["runway_top"] + TIP_CLEAR
theta = float(np.arcsin((ns["axle_h"] - tip_z) / ns["long_arm"]))
ct, st = float(np.cos(theta)), float(np.sin(theta))
half_w = (am[5] - am[4]) / 2


def arm_pt(l, w):
    """Arm-local (l: + toward the CW end, w across) -> world (Y, Z) in the
    cocked pose (throw tip rotated down toward +Y/rear)."""
    return (-l * ct + w * st, ns["axle_h"] + l * st + w * ct)


corners = [arm_pt(l, w) for l, w in
           ((-ns["long_arm"], -half_w), (-ns["long_arm"], half_w),
            (ns["short_arm"], half_w), (ns["short_arm"], -half_w))]
ax.add_patch(mp.Polygon(corners, closed=True, facecolor=ARM, edgecolor="k",
                        lw=0.8, zorder=4))
tip = arm_pt(-ns["long_arm"], 0)
cw_end = arm_pt(ns["short_arm"], 0)
# Counterweight bucket, cocked (hangs plumb from the CW end) + at bottom-dead-
# center (ghost) with the derived runway clearance.
BK_W, BK_H = 9.5, 9.5              # declared: a 2-gallon bucket, schematic
for (cy, ztop), alpha in (((cw_end[0], cw_end[1]), 1.0),
                          ((0.0, ns["axle_h"] - ns["short_arm"]), 0.35)):
    zb = ztop - ns["cw_drop"]
    ax.plot([cy, cy], [ztop, zb + BK_H], ls="--", color="0.2", lw=1.0,
            alpha=alpha)
    rect(ax, cy - BK_W / 2, cy + BK_W / 2, zb, zb + BK_H, "none", ec="0.2",
         ls="--", lw=1.2, alpha=alpha)
note(ax, (cw_end[0] - BK_W / 2, cw_end[1] - ns["cw_drop"] + BK_H / 2),
     (-46, 33), f'BUCKET on a {ns["cw_drop"]:g}" rope hitch\n(hitch the loop '
     f'1.5" from the CW end);\nghost = bottom-dead-center', fs=7.5)
vdim(ax, 5.8, ns["runway_top"], ns["cw_low"],
     f'{fmt(ns["cw_clearance"])}" BDC clearance (derived)',
     off=0.5, fs=7, color="darkred")
# Sling + pouch on the runway. SLING is the recipe's 34in cord legs
# (trebuchet.spec.yaml rigging prose — the ONE source; review-drawdim N1);
# the pouch pointer is a hedged schematic position, not a fab station.
SLING = 34.0
pouch_y = tip[0] - SLING
ax.plot([tip[0], pouch_y], [tip[1], ns["runway_top"] + 0.4], ls="--",
        color="darkgreen", lw=1.2)
ax.add_patch(mp.Ellipse((pouch_y, ns["runway_top"] + 0.5), 6, 1.6,
                        facecolor="none", edgecolor="darkgreen", ls="--",
                        lw=1.4))
note(ax, (pouch_y, ns["runway_top"] + 1.2), (pouch_y - 22, 8),
     f'POUCH starts here on the runway\n(~{abs(pouch_y):.0f}" '
     f'{"behind" if pouch_y > 0 else "ahead of"} the axle), ball inside',
     fs=7.5, color="darkgreen")
note(ax, tip, (-20, 17),
     "release pin: #10 screw in the tip end grain,\nbent ~30 deg toward the "
     "THROW side; the sling's\nloop leg slips off it at release", fs=7.5,
     color="darkgreen")
# Trigger at the rear cross: eyes + the pin at the cocked tip.
cr_ = bb_in("cross member rear")
for ey in ((cr_[2] + 0.9), (cr_[3] - 0.9)):
    ax.add_patch(mp.Circle((ey, cr_[5] + 0.5), 0.45, facecolor="none",
                           edgecolor="darkblue", lw=1.3))
ax.add_patch(mp.Circle((tip[0], tip[1] + 1.2), 0.45, facecolor="none",
                       edgecolor="darkblue", lw=1.3))
note(ax, (cr_[3], cr_[5] + 0.6), (cr_[3] - 8, -9),
     f'TRIGGER: two eye lags in the rear cross, one under the arm near the '
     f'tip.\nCocked tip lands ~{tip[0]:.1f}" behind the axle, ~{tip_z:g}" up '
     f'(assumes the tip\npulled to {TIP_CLEAR:g}" above the runway) — line up '
     f'the three eyes, slide the\n3/8" bolt through, pull its cord from 10 ft '
     f'BEHIND the machine', fs=7.5, color="darkblue")
ax.annotate("THROWS UP AND OVER,\nTOWARD THE FRONT", (am[2] + 4, 42),
            (am[2] + 26, 44), fontsize=10, color="darkgreen",
            fontweight="bold", va="center", ha="center",
            arrowprops=dict(arrowstyle="-|>", color="darkgreen", lw=2,
                            connectionstyle="arc3,rad=-0.3"))
ax.set_xlim(-50, 46)
ax.set_ylim(-14, 50)
ax.set_aspect("equal")
ax.axis("off")
ax.set_title("D3 — OPERATING DIAGRAM (cocked pose = derived arithmetic; "
             "rigging = declared recipe; kinematics NOT ANALYZED)",
             fontsize=9.5)
fig.tight_layout()
fig.savefig(OUT / "d3_operating.png")
plt.close(fig)
print("wrote d3_operating.png")
print("done ->", OUT)
