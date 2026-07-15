"""Rasterize shaded views of a compiled caddy assembly with matplotlib.

The callable renderer accepts the already-compiled detail used by the document
pair.  The CLI remains available for standalone regeneration.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

from detailgen.spec.compiler import compile_spec_file


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "outputs" / "armchair_caddy" / "views"
SPEC = ROOT / "details" / "armchair_caddy.spec.yaml"

COLOR = {
    "sofa arm": (0.78, 0.75, 0.70),
    "side panel +X": (0.80, 0.62, 0.42),
    "side panel -X": (0.80, 0.62, 0.42),
    "top panel": (0.66, 0.48, 0.30),
    "corner key +X front": (0.93, 0.80, 0.42),
    "corner key +X back": (0.93, 0.80, 0.42),
    "corner key -X front": (0.93, 0.80, 0.42),
    "corner key -X back": (0.93, 0.80, 0.42),
}
OTHER = (0.55, 0.57, 0.60)
LIGHT = LightSource(azdeg=-35, altdeg=55)


def _part_polys(part):
    verts, tris = part.world_solid().val().tessellate(0.05)
    vertices = np.array([[value.x, value.y, value.z] for value in verts])
    faces = [vertices[list(triangle)] for triangle in tris]
    return vertices, faces


def _shade(base, faces, alpha=1.0):
    """Flat-shade each triangle by its normal against the light source."""
    colors = []
    for face in faces:
        normal = np.cross(face[1] - face[0], face[2] - face[0])
        length = np.linalg.norm(normal)
        normal = normal / length if length > 1e-9 else np.array([0, 0, 1.0])
        light = np.array([-0.4, -0.5, 0.9])
        light = light / np.linalg.norm(light)
        strength = 0.45 + 0.55 * max(0.0, float(np.dot(normal, light)))
        colors.append((*[channel * strength for channel in base], alpha))
    return colors


def render_caddy_views(detail, out_dir: str | Path = DEFAULT_OUT) -> tuple[Path, ...]:
    """Render the ten registered legacy views from one compiled detail."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    detail.build()

    parts = []
    all_vertices = []
    for part in detail.assembly.parts:
        vertices, faces = _part_polys(part)
        all_vertices.append(vertices)
        parts.append((part.name, COLOR.get(part.name, OTHER), faces))
    vertices = np.vstack(all_vertices)
    global_min, global_max = vertices.min(0), vertices.max(0)
    written = []

    def draw(filename, elev, azim, title, lims=None, hide=(), ghost=()):
        figure = plt.figure(figsize=(7, 6), dpi=130)
        ax = figure.add_subplot(111, projection="3d")
        for name, base, faces in parts:
            if name in hide:
                continue
            is_ghost = name in ghost
            collection = Poly3DCollection(
                faces,
                facecolors=_shade(base, faces, 0.16 if is_ghost else 1.0),
                edgecolors=(0, 0, 0, 0.08 if is_ghost else 0.18),
                linewidths=0.1 if is_ghost else 0.2,
            )
            ax.add_collection3d(collection)
        if lims is None:
            low, high = global_min, global_max
        else:
            low, high = np.array(lims[0]), np.array(lims[1])
        ax.set_xlim(low[0], high[0])
        ax.set_ylim(low[1], high[1])
        ax.set_zlim(low[2], high[2])
        ax.set_box_aspect((high[0] - low[0], high[1] - low[1], high[2] - low[2]))
        ax.view_init(elev=elev, azim=azim)
        ax.set_xlabel("X (across arm)")
        ax.set_ylabel("Y (along arm)")
        ax.set_zlabel("Z up")
        ax.set_title(title, fontsize=10)
        figure.tight_layout()
        path = out_dir / filename
        figure.savefig(path)
        plt.close(figure)
        written.append(path)

    draw("v1_iso.png", 22, -55, "ISO — three-panel caddy saddling the arm")
    draw("v2_front.png", 6, -89, "FRONT (along -Y): panel-defined fit and 7in drop")
    draw("v3_end.png", 6, 1, "END: arm length and removable waterfall sleeve")
    draw("v4_top.png", 88, -90, "TOP (-Z): cup opening + flush wooden key ends")
    draw("z1_cup.png", 55, -60, "ZOOM cup-hole interior (3/4in top panel)",
         lims=([-60, -60, -20], [60, 60, 40]))
    draw("z2_joint.png", 26, -55,
         "ZOOM reinforced miter: two diagonal hardwood corner keys",
         lims=([40, -55, -155], [125, 55, 40]))
    draw("z3_gap.png", 8, -89,
         "ZOOM panel-defined fit: 0.25in nominal clearance each side",
         lims=([55, -75, -160], [125, 75, 35]))
    draw("g1_iso.png", 24, -55,
         "ISO (arm hidden) — three matching hardwood panels",
         hide=("sofa arm",))
    draw("g2_joint.png", 30, -60,
         "CUTAWAY reinforced miter: ghosted panels expose two diagonal keys",
         lims=([40, -60, -155], [125, 60, 40]), hide=("sofa arm",),
         ghost=("top panel", "side panel +X"))
    draw("g3_underside.png", -35, -55,
         "UNDERSIDE (arm hidden): keyed miters, no rails or metal fasteners",
         hide=("sofa arm",))
    return tuple(written)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    out_dir = Path(args[0]) if args else DEFAULT_OUT
    detail = compile_spec_file(SPEC)
    detail.build()
    for path in render_caddy_views(detail, out_dir):
        print("wrote", path.name)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
