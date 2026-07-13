"""Sheet-steel connectors: joist hangers, post bases, angle brackets.

All parts follow the Component contract documented in ``lumber.py``.

These are *detail-grade* simplifications of manufactured connectors
(Simpson Strong-Tie et al.): correct envelope, seat and flange geometry,
no embossing/nail holes. When a drawing must show a specific SKU, drop the
manufacturer's STEP file into ``assets/manufacturer/`` and load it with
``detailgen.assemblies.load_step`` instead of modeling it here.

Local frames
------------
- JoistHanger: seats a member running along +X; the **back face (against the
  header) is the X=0 plane**, seat bottom at Z=0, centered in Y.
- PostBase: base plate on Z=0, post pocket opening upward, centered in X/Y.
- AngleBracket: corner line along Y at the origin, legs on +X and +Z.
"""

from __future__ import annotations

import cadquery as cq

from ..core.base import Component
from ..core.frame import Frame
from ..core.registry import register_component
from ..core.units import IN, fmt_in
from ._geometry import angle_profile, axis_cylinder, ease_edges


@register_component("joist_hanger")
class JoistHanger(Component):
    """Face-mount joist hanger (U shape + header flanges).

    Parameters are the *joist* dimensions it wraps: pass the same numbers as
    the Lumber member it carries (plus a little play, handled internally).
    """

    material_key = "steel_galv"

    PLAY = 0.06 * IN          # clearance each side of the joist
    GAUGE = 0.048 * IN        # 18ga
    FLANGE_WIDTH = 1.5 * IN   # each header flange
    SEAT_LENGTH = 2.0 * IN    # how far the stirrup extends along the joist

    def __init__(self, joist_thickness: float, joist_depth: float,
                 height_ratio: float = 0.75, name: str = "joist hanger"):
        super().__init__(name)
        self.joist_thickness = float(joist_thickness)
        self.joist_depth = float(joist_depth)
        #: sides extend this fraction of joist depth (real hangers don't reach full depth)
        self.height_ratio = float(height_ratio)

    def _build(self) -> cq.Workplane:
        w = self.joist_thickness + 2 * self.PLAY   # inner width
        t = self.GAUGE
        h = self.joist_depth * self.height_ratio
        L = self.SEAT_LENGTH

        # Stirrup: bottom seat + two sides, joist axis along +X, back at X=0.
        seat = cq.Workplane("XY").box(L, w + 2 * t, t, centered=(False, True, False)).translate((0, 0, -t))
        side_l = cq.Workplane("XY").box(L, t, h, centered=(False, False, False)).translate((0, w / 2, 0))
        side_r = side_l.mirror("XZ")

        # Header flanges: in the X=0 plane, bent outward from the sides.
        flange = (
            cq.Workplane("YZ")
            .box(self.FLANGE_WIDTH, h + t, t, centered=(False, False, False))
            .translate((-t, w / 2 + t, -t))
        )
        flange_l = flange
        flange_r = flange.mirror("XZ")

        return seat.union(side_l).union(side_r).union(flange_l).union(flange_r)

    def _datums(self) -> dict[str, Frame]:
        # Local: back face (against the header) is the X=0 plane, seat bottom at
        # Z=0, centered in Y.
        return {
            "back": Frame.from_origin_axes((0, 0, 0), (0, 0, 1), (-1, 0, 0)),
            "seat": Frame.from_origin_axes((self.SEAT_LENGTH / 2, 0, 0),
                                           (1, 0, 0), (0, 0, 1)),
        }

    def check(self) -> list[str]:
        problems = super().check()
        if not 0.4 <= self.height_ratio <= 1.0:
            problems.append(f"{self.name}: height_ratio {self.height_ratio} outside 0.4-1.0")
        return problems


@register_component("post_base")
class PostBase(Component):
    """Elevated post base (plate + standoff + U bracket), e.g. Simpson ABU.

    Datum: bottom of base plate at Z=0, centered in X/Y. ``standoff`` keeps
    post end grain off the concrete (code wants >= 1").
    """

    material_key = "steel_galv"

    GAUGE = 0.108 * IN   # 12ga
    PLATE_MARGIN = 0.75 * IN
    SIDE_HEIGHT = 2.5 * IN

    def __init__(self, post_size: float, standoff: float = 1.0 * IN,
                 name: str = "post base"):
        super().__init__(name)
        self.post_size = float(post_size)     # square post actual dimension
        self.standoff = float(standoff)

    def _build(self) -> cq.Workplane:
        t = self.GAUGE
        p = self.post_size + 2 * 0.06 * IN    # pocket with play
        plate_w = p + 2 * self.PLATE_MARGIN

        plate = cq.Workplane("XY").box(plate_w, plate_w, t, centered=(True, True, False))
        riser = (
            cq.Workplane("XY")
            .box(1.5 * IN, 1.5 * IN, self.standoff, centered=(True, True, False))
        )
        seat_z = self.standoff
        seat = (
            cq.Workplane("XY")
            .box(p + 2 * t, p + 2 * t, t, centered=(True, True, False))
            .translate((0, 0, seat_z))
        )
        side = (
            cq.Workplane("XY")
            .box(p + 2 * t, t, self.SIDE_HEIGHT, centered=(True, False, False))
            .translate((0, p / 2, seat_z + t))
        )
        return plate.union(riser).union(seat).union(side).union(side.mirror("XZ"))

    def _datums(self) -> dict[str, Frame]:
        # Local: base plate bottom at Z=0, centered X/Y; post seats at standoff.
        return {
            "base": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
            "seat": Frame.from_origin_axes((0, 0, self.standoff), (1, 0, 0), (0, 0, 1)),
        }

    def check(self) -> list[str]:
        problems = super().check()
        if self.standoff < 1.0 * IN:
            problems.append(
                f"{self.name}: standoff under 1\" — post end grain too close to concrete"
            )
        return problems


@register_component("angle_bracket")
class AngleBracket(Component):
    """Hot-rolled / bent steel angle with a real inner bend radius, broken toe
    corners and (optionally) punched bolt holes.

    Datum: the heel (outer corner) is at the origin. The **base flange** lies on
    Z in [0, thickness] extending +Y; the **upright flange** lies on Y in
    [0, thickness] extending +Z. The member length runs along X, centered on
    X=0. (This is the datum the rock-anchor detail relies on.)

    Holes are given in the flange's own 2D coordinates:
    - ``holes_base``: [(x, y, diameter)] drilled through the base flange (axis Z)
    - ``holes_up``:   [(x, z, diameter)] drilled through the upright flange (axis Y)
    """

    material_key = "steel_galv"

    def __init__(self, leg1: float = 3 * IN, leg2: float = 3 * IN,
                 thickness: float = 0.25 * IN, length: float = 3.5 * IN,
                 bend_radius: float | None = None,
                 holes_base: tuple = (), holes_up: tuple = (),
                 name: str = "angle bracket"):
        super().__init__(name)
        self.leg1 = float(leg1)          # upright flange length (+Z)
        self.leg2 = float(leg2)          # base flange length (+Y)
        self.thickness = float(thickness)
        self.length = float(length)
        self.bend_radius = float(bend_radius if bend_radius is not None else thickness)
        self.holes_base = list(holes_base)
        self.holes_up = list(holes_up)

    def _build(self) -> cq.Workplane:
        sk = angle_profile(self.leg1, self.leg2, self.thickness, self.bend_radius)
        # profile drawn in (y, z); extrude along X, centered on X=0.
        wp = (cq.Workplane("YZ").placeSketch(sk).extrude(self.length)
              .translate((-self.length / 2, 0, 0)))
        t = self.thickness
        for (hx, hy, hd) in self.holes_base:
            wp = wp.cut(axis_cylinder(hd / 2, t * 6, (hx, hy, -t * 3), (0, 0, 1)))
        for (hx, hz, hd) in self.holes_up:
            wp = wp.cut(axis_cylinder(hd / 2, t * 6, (hx, -t * 3, hz), (0, 1, 0)))
        return ease_edges(wp, "|X", 0.03 * IN)

    def _datums(self) -> dict[str, Frame]:
        # Local: heel (outer corner) at origin, member length along X centered on
        # X=0. Base flange on Z in [0,t] extending +Y; upright flange on Y in
        # [0,t] extending +Z (module + class docstring). Face datums use the
        # true outward normal for +Z; hole datums put +Z along the hole axis and
        # sit at each flange surface, so a rod/bolt or a bearing part seats on
        # the named hole.
        t = self.thickness
        d: dict[str, Frame] = {
            "heel": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
            # base flange faces (outer = underside on Z=0, inner = top at Z=t)
            "base_outer": Frame.from_origin_axes((0, self.leg2 / 2, 0), (1, 0, 0), (0, 0, -1)),
            "base_inner": Frame.from_origin_axes((0, self.leg2 / 2, t), (1, 0, 0), (0, 0, 1)),
            # upright flange faces (outer on Y=0, inner at Y=t)
            "upright_outer": Frame.from_origin_axes((0, 0, self.leg1 / 2), (1, 0, 0), (0, -1, 0)),
            "upright_inner": Frame.from_origin_axes((0, t, self.leg1 / 2), (1, 0, 0), (0, 1, 0)),
        }
        # Bolt-hole centers, at both surfaces of the flange they pierce.
        for i, (hx, hy, _hd) in enumerate(self.holes_base):
            d[f"base_hole_{i}_bottom"] = Frame.from_origin_axes((hx, hy, 0), (1, 0, 0), (0, 0, 1))
            d[f"base_hole_{i}_top"] = Frame.from_origin_axes((hx, hy, t), (1, 0, 0), (0, 0, 1))
        for i, (hx, hz, _hd) in enumerate(self.holes_up):
            d[f"up_hole_{i}_outer"] = Frame.from_origin_axes((hx, 0, hz), (1, 0, 0), (0, -1, 0))
            d[f"up_hole_{i}_inner"] = Frame.from_origin_axes((hx, t, hz), (1, 0, 0), (0, 1, 0))
        return d

    def describe(self) -> str:
        return (f'{fmt_in(self.leg1)} x {fmt_in(self.leg2)} x '
                f'{fmt_in(self.thickness)} angle, {fmt_in(self.length, 1)} long')

    def assumptions(self) -> str:
        return ("Hot-rolled angle; inner bend radius = thickness, concentric "
                "outer bend; punched holes; edges broken.")

    def bom_group(self) -> str:
        return (f"AngleBracket|{round(self.leg1,2)}|{round(self.leg2,2)}|"
                f"{round(self.thickness,3)}|{round(self.length,2)}")

    def bom_label(self) -> str:
        return "Steel angle"

    def check(self) -> list[str]:
        problems = super().check()
        if self.bend_radius < self.thickness * 0.8:
            problems.append(
                f"{self.name}: bend radius {fmt_in(self.bend_radius)} tight for "
                f"{fmt_in(self.thickness)} steel — cracking risk"
            )
        return problems
