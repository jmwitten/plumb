"""PIL dimension overlay for the 'dimensioned' Blender render.

Blender projects each dimension's world anchors to pixel coordinates with the
actual render camera (``camera_map.json``); this pass draws extension lines,
arrowed dimension lines and labels on top of the flat elevation render. Kept in
PIL (not in-scene geometry) so styling is instant to iterate without re-render.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ACCENT = (200, 90, 36, 255)
INK = (38, 40, 42, 255)


def _font(size):
    for p in ("/System/Library/Fonts/Menlo.ttc",
              "/System/Library/Fonts/Supplemental/Courier New.ttf",
              "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _arrow(draw, a, b, color, width=3, head=11):
    draw.line([a, b], fill=color, width=width)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    for s in (+1, -1):
        draw.line([b, (b[0] - head * math.cos(ang + s * 0.4),
                       b[1] - head * math.sin(ang + s * 0.4))],
                  fill=color, width=width)


def draw_dimensions(render_png: str | Path, camera_map: str | Path,
                    out_png: str | Path, title: str | None = None):
    img = Image.open(render_png).convert("RGBA")
    W, H = img.size
    dr = ImageDraw.Draw(img)
    dims = json.loads(Path(camera_map).read_text())
    font = _font(max(20, W // 55))
    tfont = _font(max(26, W // 42))

    for d in dims:
        p0 = tuple(d["p0"]); p1 = tuple(d["p1"])
        # offset the dimension line outboard from the geometry so it's readable
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        length = math.hypot(dx, dy) or 1
        # perpendicular unit
        nx, ny = -dy / length, dx / length
        off = 46
        # push the dimension outboard on whichever side is toward the frame edge
        cx = (p0[0] + p1[0]) / 2
        side = 1 if cx < W / 2 else -1
        o0 = (p0[0] + side * off * nx, p0[1] + side * off * ny)
        o1 = (p1[0] + side * off * nx, p1[1] + side * off * ny)
        # extension lines
        dr.line([p0, o0], fill=ACCENT, width=1)
        dr.line([p1, o1], fill=ACCENT, width=1)
        # double-headed dimension line
        _arrow(dr, o1, o0, ACCENT)
        _arrow(dr, o0, o1, ACCENT)
        # label at midpoint, nudged further outboard
        mid = ((o0[0] + o1[0]) / 2 + side * 12 * nx,
               (o0[1] + o1[1]) / 2 + side * 12 * ny)
        tb = dr.textbbox((0, 0), d["label"], font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        lx, ly = mid[0] - tw / 2, mid[1] - th / 2
        dr.rectangle([lx - 5, ly - 3, lx + tw + 5, ly + th + 5],
                     fill=(255, 255, 255, 230))
        dr.text((lx, ly), d["label"], fill=ACCENT, font=font)

    if title:
        dr.text((28, 24), title, fill=INK, font=tfont)
    img.convert("RGB").save(out_png)
    return out_png
