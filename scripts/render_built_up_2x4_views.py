#!/usr/bin/env python3
"""Render model-backed fabrication views for the built-up 2x4 member.

The drawings deliberately read dimensions and hardware locations from the
compiled DetailSpec.  They are shop communication views, not structural
engineering drawings.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Rectangle

from detailgen.spec.compiler import compile_spec_file


_REPO = Path(__file__).resolve().parents[1]
SPEC = _REPO / "details" / "built_up_2x4.spec.yaml"
DEFAULT_OUT = _REPO / "outputs" / "built_up_2x4" / "views"
MM_PER_IN = 25.4

WOOD_A = "#d9a86c"
WOOD_B = "#bf8248"
WOOD_EDGE = "#5f3a1f"
STEEL = "#3f4b55"
INK = "#20252a"
MUTED = "#687078"
PAPER = "#fbfaf6"


def _bbox_in(part) -> tuple[float, float, float, float, float, float]:
    box = part.world_solid().val().BoundingBox()
    return tuple(
        value / MM_PER_IN
        for value in (box.xmin, box.xmax, box.ymin, box.ymax, box.zmin, box.zmax)
    )


def _model_facts(detail) -> dict:
    """Extract dimensions and screw centers from the built assembly."""
    detail.build()
    ns = detail.namespace
    parts = {part.name: part for part in detail.assembly.parts}
    ply_a = _bbox_in(parts["2x4 ply A"])
    ply_b = _bbox_in(parts["2x4 ply B"])
    screws = []
    for name, part in parts.items():
        if not name.startswith("screw at "):
            continue
        box = _bbox_in(part)
        screws.append(
            {
                "x": (box[0] + box[1]) / 2,
                "face": "A" if "face A" in name else "B",
                "name": name,
            }
        )
    screws.sort(key=lambda item: item["x"])
    return {
        "length": float(ns["member_length"]),
        "ply_thickness": float(ns["stud_thickness"]),
        "depth": float(ns["stud_depth"]),
        "assembly_width": float(ns["assembly_width"]),
        "first": float(ns["first_station"]),
        "last": float(ns["final_station"]),
        "spacing": float(ns["station_spacing"]),
        "count": int(ns["station_count"]),
        "screw_length": float(ns["screw_length"]),
        "screw_diameter": float(ns["screw_diameter"]),
        "ply_a": ply_a,
        "ply_b": ply_b,
        "screws": screws,
    }


def _new_figure(figsize=(12, 4.6)):
    fig, ax = plt.subplots(figsize=figsize, dpi=160)
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)
    return fig, ax


def _finish(fig, ax, path: Path, title: str, subtitle: str) -> None:
    ax.set_title(title, loc="left", fontsize=14, fontweight="bold", color=INK, pad=16)
    ax.text(
        0,
        1.015,
        subtitle,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.5,
        color=MUTED,
    )
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    fig.tight_layout(pad=1.5)
    fig.savefig(path, bbox_inches="tight", facecolor=PAPER)
    plt.close(fig)


def _dimension(ax, x0, x1, y, label, *, witness_y=None, color=INK):
    ax.annotate(
        "",
        xy=(x1, y),
        xytext=(x0, y),
        arrowprops={"arrowstyle": "<->", "color": color, "lw": 0.9},
    )
    if witness_y is not None:
        ax.plot([x0, x0], [witness_y, y], color=color, lw=0.6)
        ax.plot([x1, x1], [witness_y, y], color=color, lw=0.6)
    ax.text((x0 + x1) / 2, y + 0.22, label, ha="center", va="bottom", fontsize=8, color=color)


def _project(x, y, z):
    """Compact axonometric projection; dimensions, not perspective, govern."""
    return x + 0.70 * y, z + 0.42 * y


def _box_faces(x0, x1, y0, y1, z0, z1):
    corners = {
        key: _project(x, y, z)
        for key, (x, y, z) in {
            "000": (x0, y0, z0),
            "100": (x1, y0, z0),
            "010": (x0, y1, z0),
            "110": (x1, y1, z0),
            "001": (x0, y0, z1),
            "101": (x1, y0, z1),
            "011": (x0, y1, z1),
            "111": (x1, y1, z1),
        }.items()
    }
    return [
        [corners[k] for k in ("001", "101", "111", "011")],
        [corners[k] for k in ("000", "100", "101", "001")],
        [corners[k] for k in ("100", "110", "111", "101")],
    ]


def _render_iso(facts: dict, path: Path) -> None:
    fig, ax = _new_figure((13, 4.2))
    length = facts["length"]
    depth = facts["depth"]
    split = facts["ply_thickness"]
    width = facts["assembly_width"]

    for y0, y1, color in ((0, split, WOOD_A), (split, width, WOOD_B)):
        faces = _box_faces(0, length, y0, y1, 0, depth)
        shades = (color, "#c88e55" if y0 == 0 else "#a96f38", "#aa713b")
        for points, shade in zip(faces, shades):
            ax.add_patch(Polygon(points, closed=True, facecolor=shade, edgecolor=WOOD_EDGE, lw=0.7))

    for screw in facts["screws"]:
        y = 0 if screw["face"] == "A" else width
        sx, sy = _project(screw["x"], y, depth / 2)
        ax.add_patch(Circle((sx, sy), 0.55, facecolor=STEEL, edgecolor="white", lw=0.5, zorder=5))
        ax.text(sx, sy - 1.0, screw["face"], ha="center", va="top", fontsize=6.5, color=INK)

    _dimension(ax, 0, length, -2.3, f'{length:g}" overall', witness_y=0)
    ax.text(
        length / 2,
        depth + width * 0.42 + 1.5,
        f'{facts["count"]} screws · {facts["spacing"]:g}" o.c. · alternating faces',
        ha="center",
        fontsize=9,
        color=INK,
    )
    ax.set_xlim(-4, length + 6)
    ax.set_ylim(-4, depth + width * 0.42 + 4)
    _finish(
        fig,
        ax,
        path,
        "ASSEMBLED MEMBER — AXONOMETRIC",
        f'Two nominal 2×4s, wide face to wide face · actual section {width:g}" × {depth:g}" · long axis compressed for legibility',
    )


def _render_face(facts: dict, path: Path, face: str) -> None:
    fig, ax = _new_figure((13, 4.3))
    length = facts["length"]
    depth = facts["depth"]
    own = [s for s in facts["screws"] if s["face"] == face]
    opposite = [s for s in facts["screws"] if s["face"] != face]
    ax.add_patch(Rectangle((0, 0), length, depth, facecolor=WOOD_A if face == "A" else WOOD_B, edgecolor=WOOD_EDGE, lw=1.2))
    ax.plot([0, length], [depth / 2, depth / 2], color="white", alpha=0.20, lw=0.8)
    for screw in opposite:
        ax.add_patch(Circle((screw["x"], depth / 2), 0.37, facecolor="none", edgecolor="#7a6f63", lw=0.8, ls="--"))
    for screw in own:
        x = screw["x"]
        ax.add_patch(Circle((x, depth / 2), 0.52, facecolor=STEEL, edgecolor="white", lw=0.6))
        ax.plot([x - 0.28, x + 0.28], [depth / 2, depth / 2], color="white", lw=0.7)
        ax.text(x, depth + 0.6, f'{x:g}"', ha="center", va="bottom", fontsize=8, color=INK)
        ax.plot([x, x], [depth, depth + 0.42], color=INK, lw=0.6)
    _dimension(ax, 0, length, -1.35, f'{length:g}" overall', witness_y=0)
    ax.text(length / 2, -2.35, "Solid heads = drive from this face · dashed rings = heads on opposite face", ha="center", fontsize=8, color=MUTED)
    ax.set_xlim(-3, length + 3)
    ax.set_ylim(-3, depth + 2.2)
    _finish(
        fig,
        ax,
        path,
        f"FACE {face} — DRIVE STATIONS",
        f'{len(own)} heads on face {face}; centerline at half of the {depth:g}" broad face',
    )


def _render_section(facts: dict, path: Path) -> None:
    fig, ax = _new_figure((7.3, 6.2))
    width = facts["assembly_width"]
    depth = facts["depth"]
    split = facts["ply_thickness"]
    ax.add_patch(Rectangle((0, 0), split, depth, facecolor=WOOD_A, edgecolor=WOOD_EDGE, lw=1.2))
    ax.add_patch(Rectangle((split, 0), split, depth, facecolor=WOOD_B, edgecolor=WOOD_EDGE, lw=1.2))
    ax.plot([split, split], [0, depth], color="#6c3f20", lw=1.6)
    ax.text(split / 2, depth / 2, "PLY A\n1½ × 3½", ha="center", va="center", fontsize=10, color=INK)
    ax.text(split + split / 2, depth / 2, "PLY B\n1½ × 3½", ha="center", va="center", fontsize=10, color=INK)
    _dimension(ax, 0, width, -0.8, f'{width:g}" actual built-up width', witness_y=0)
    ax.annotate("", xy=(width + 0.8, depth), xytext=(width + 0.8, 0), arrowprops={"arrowstyle": "<->", "color": INK, "lw": 0.9})
    ax.plot([width, width + 0.8], [0, 0], color=INK, lw=0.6)
    ax.plot([width, width + 0.8], [depth, depth], color=INK, lw=0.6)
    ax.text(width + 1.0, depth / 2, f'{depth:g}" actual depth', ha="left", va="center", rotation=90, fontsize=8, color=INK)
    ax.text(width / 2, depth + 0.55, "WIDE-FACE CONTACT", ha="center", fontsize=8, fontweight="bold", color=INK)
    ax.set_xlim(-1.2, width + 2.1)
    ax.set_ylim(-1.4, depth + 1.2)
    _finish(
        fig,
        ax,
        path,
        "SECTION — ACTUAL SIZE RELATIONSHIP",
        "Nominal lumber names are not finished dimensions; this is closer to a 4×4, but it is not a true 4×4",
    )


def _render_stations(facts: dict, path: Path) -> None:
    fig, ax = _new_figure((13, 4.9))
    length = facts["length"]
    depth = facts["depth"]
    screws = facts["screws"]
    y = 2.3
    ax.plot([0, length], [y, y], color=WOOD_EDGE, lw=5, solid_capstyle="butt")
    for screw in screws:
        x = screw["x"]
        marker = "o" if screw["face"] == "A" else "s"
        ax.plot(x, y, marker=marker, ms=7, mfc=STEEL, mec="white", mew=0.7)
        ax.text(x, y + 0.75, f'{x:g}"', ha="center", fontsize=7.5, color=INK)
        ax.text(x, y - 0.75, screw["face"], ha="center", fontsize=7.5, color=INK)
    dim_y = 0.1
    _dimension(ax, 0, facts["first"], dim_y, f'{facts["first"]:g}"')
    for left, right in zip(screws, screws[1:]):
        _dimension(ax, left["x"], right["x"], dim_y, f'{facts["spacing"]:g}"')
    _dimension(ax, facts["last"], length, dim_y, f'{length - facts["last"]:g}"')
    ax.text(length / 2, -1.25, "○ face A · ■ face B · consecutive stations alternate drive direction", ha="center", fontsize=8.5, color=MUTED)
    ax.text(
        length / 2,
        depth + 1.2,
        f'{facts["count"]} total · representative Ø {facts["screw_diameter"]:g}" × {facts["screw_length"]:g}" structural wood screws',
        ha="center",
        fontsize=9,
        color=INK,
    )
    ax.set_xlim(-3, length + 3)
    ax.set_ylim(-1.8, depth + 2)
    _finish(
        fig,
        ax,
        path,
        "FASTENER STATION CHAIN",
        "Reference all stations from one end; do not accumulate tape-measure error",
    )


def render_built_up_2x4_views(detail=None, out_dir: str | Path | None = None) -> dict[str, Path]:
    """Render the five registered views without recompiling when detail is supplied."""
    if detail is None:
        detail = compile_spec_file(SPEC)
    facts = _model_facts(detail)
    out = Path(out_dir) if out_dir is not None else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "iso": out / "iso.png",
        "side_a": out / "side_a.png",
        "side_b": out / "side_b.png",
        "section": out / "section.png",
        "stations": out / "stations.png",
    }
    _render_iso(facts, paths["iso"])
    _render_face(facts, paths["side_a"], "A")
    _render_face(facts, paths["side_b"], "B")
    _render_section(facts, paths["section"])
    _render_stations(facts, paths["stations"])
    for path in paths.values():
        print(f"wrote {path}")
    return paths


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    out = Path(argv[0]) if argv else DEFAULT_OUT
    render_built_up_2x4_views(out_dir=out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
