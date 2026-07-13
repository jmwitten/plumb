"""Concrete elements: piers, footings, slabs.

All parts follow the Component contract documented in ``lumber.py``.

Local frames
------------
- ConcretePier: axis along +Z, **top of pier at Z=0** (below-grade portion
  extends into -Z). This makes it natural to place hardware at the origin.
- Footing / Slab: top surface at Z=0, centered in X/Y, body extends into -Z.
"""

from __future__ import annotations

import cadquery as cq

from ..core.base import Component
from ..core.frame import Frame
from ..core.registry import register_component
from ..core.units import IN, fmt_in
from ._geometry import axis_cylinder, ease_edges

#: Frost depth floor for check() warnings (48" is a common NY-upstate figure;
#: pass your jurisdiction's value to check(frost_depth=...) to override).
DEFAULT_FROST_DEPTH = 48 * IN


@register_component("concrete_pier")
class ConcretePier(Component):
    """Cylindrical cast pier (e.g. Sonotube).

    Datum: top face centered at origin, shaft extends down (-Z).

    Parameters
    ----------
    diameter: pier diameter in mm (Sonotube: 8", 10", 12" typical).
    depth: total depth of concrete below the top face, in mm.
    exposure: how much of `depth` sits above grade (metadata for checks).
    """

    material_key = "concrete"

    def __init__(self, diameter: float, depth: float, exposure: float = 0.0,
                 name: str = "pier"):
        super().__init__(name)
        self.diameter = float(diameter)
        self.depth = float(depth)
        self.exposure = float(exposure)

    def _build(self) -> cq.Workplane:
        return (
            cq.Workplane("XY")
            .circle(self.diameter / 2)
            .extrude(-self.depth)
        )

    def _datums(self) -> dict[str, Frame]:
        # Local: top face centered at origin, shaft into -Z.
        return {
            "top": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
            "axis": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
        }

    def check(self, frost_depth: float = DEFAULT_FROST_DEPTH) -> list[str]:
        problems = super().check()
        buried = self.depth - self.exposure
        if buried < frost_depth:
            problems.append(
                f"{self.name}: {fmt_in(buried)} below grade is shallower than "
                f"frost depth {fmt_in(frost_depth)}"
            )
        return problems


@register_component("footing")
class Footing(Component):
    """Rectangular spread footing. Datum: top face at Z=0, centered in X/Y."""

    material_key = "concrete"

    def __init__(self, width: float, length: float, thickness: float,
                 name: str = "footing"):
        super().__init__(name)
        self.width = float(width)
        self.length = float(length)
        self.thickness = float(thickness)

    def _build(self) -> cq.Workplane:
        return (
            cq.Workplane("XY")
            .box(self.length, self.width, self.thickness,
                 centered=(True, True, False))
            .translate((0, 0, -self.thickness))
        )

    def _datums(self) -> dict[str, Frame]:
        # Local: top face at Z=0, centered in X/Y, body into -Z.
        return {"top": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1))}

    def check(self) -> list[str]:
        problems = super().check()
        if self.thickness < 6 * IN:
            problems.append(
                f"{self.name}: {fmt_in(self.thickness)} thick — most codes "
                f"require 6\" minimum for footings"
            )
        return problems


@register_component("boulder")
class Boulder(Component):
    """Natural rock foundation (e.g. a glacial boulder anchored into with epoxy
    rods). Modeled as an exact rectangular chunk so it is a clean validation
    body; the organic surface is a render-time concern, not a CAD one.

    Datum: top pad plane at Z=0, centered in X/Y, body extends into -Z.

    ``holes``: [(x, y, diameter, depth)] drilled straight down from the pad.
    """

    material_key = "rock"

    def __init__(self, width: float, length: float, depth: float,
                 holes: tuple = (), name: str = "boulder"):
        super().__init__(name)
        self.width = float(width)
        self.length = float(length)
        self.depth = float(depth)
        self.holes = list(holes)

    def _build(self) -> cq.Workplane:
        wp = (cq.Workplane("XY")
              .box(self.length, self.width, self.depth, centered=(True, True, False))
              .translate((0, 0, -self.depth)))
        for (hx, hy, hd, hdep) in self.holes:
            wp = wp.cut(axis_cylinder(hd / 2, hdep, (hx, hy, 0), (0, 0, -1)))
        return wp

    def _datums(self) -> dict[str, Frame]:
        # Local: top pad plane at Z=0, centered in X/Y; anchor holes drilled
        # straight down from the pad. Each hole gets a ``hole_i_top`` (pad
        # surface) and ``hole_i_bottom`` (drilled depth) datum for seating epoxy
        # / anchor rods; +Z is up in every case.
        d: dict[str, Frame] = {
            "top": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
        }
        for i, (hx, hy, hd, hdep) in enumerate(self.holes):
            d[f"hole_{i}_top"] = Frame.from_origin_axes((hx, hy, 0), (1, 0, 0), (0, 0, 1))
            d[f"hole_{i}_bottom"] = Frame.from_origin_axes((hx, hy, -hdep), (1, 0, 0), (0, 0, 1))
        return d

    def describe(self) -> str:
        return (f'{fmt_in(self.length, 1)} x {fmt_in(self.width, 1)} x '
                f'{fmt_in(self.depth, 1)} chunk')

    def assumptions(self) -> str:
        return ("Exact prism as validation body; real boulder irregular — "
                "leveling nuts absorb surface variation. Render displacement "
                "is display-only.")

    def bom_label(self) -> str:
        return "Boulder (existing)"


@register_component("pier_block")
class PierBlock(Component):
    """Precast concrete pier block — the foundation under a free-standing post
    that does not land on the rock anchor.

    Datum: top pad plane at Z=0, centered in X/Y, body extends into -Z (the same
    convention as ``Footing`` — a post's base bears directly on the pad). The
    post is held its own leveling standoff above grade by setting the block so
    its pad sits at that height; the block itself is a purchased item.

    Modeled as an exact rectangular prism so it is a clean validation body; a
    real precast block is tapered with a cast-in post saddle/slot, which is a
    render- and field-detail concern, not a CAD one.
    """

    material_key = "concrete"

    def __init__(self, width: float, length: float, height: float,
                 exposure: float = 0.0, name: str = "pier_block"):
        super().__init__(name)
        self.width = float(width)
        self.length = float(length)
        self.height = float(height)
        #: How much of ``height`` stands PROUD of grade (metadata for the
        #: embedment/frost check — the mirror of ``ConcretePier.exposure``). The
        #: buried portion is ``height - exposure``; the render solid is unchanged.
        self.exposure = float(exposure)

    def _build(self) -> cq.Workplane:
        return (
            cq.Workplane("XY")
            .box(self.length, self.width, self.height, centered=(True, True, False))
            .translate((0, 0, -self.height))
        )

    def _datums(self) -> dict[str, Frame]:
        # Local: top pad plane at Z=0 (the post bears here), centered in X/Y,
        # body into -Z. A ``bottom`` datum marks the buried/bearing face on grade.
        return {
            "top": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
            "bottom": Frame.from_origin_axes((0, 0, -self.height), (1, 0, 0), (0, 0, 1)),
        }

    @property
    def buried_depth(self) -> float:
        """Depth of the block's bearing base below grade — ``height`` minus the
        portion standing proud of grade (``exposure``). The quantity the
        foundation-role embedment/frost obligation compares against a DECLARED
        frost depth (see :mod:`detailgen.validation.foundation`).

        Frost is deliberately NOT a component ``check()`` here (unlike
        :class:`ConcretePier`): frost depth is a jurisdiction input the
        foundation SYSTEM declares, not a block-intrinsic parameter, so a bare
        block never self-fails the parameter-consistency sweep — the obligation
        pack owns the frost verdict, with the declared depth in hand."""
        return self.height - self.exposure

    def describe(self) -> str:
        return (f'{fmt_in(self.length, 1)} x {fmt_in(self.width, 1)} x '
                f'{fmt_in(self.height, 1)} precast block')

    def assumptions(self) -> str:
        return ("Exact prism as validation body; real precast pier block is "
                "tapered with a cast-in post saddle. Set on compacted grade "
                "(no separate leveling part modeled — the post's standoff is the "
                "leveling gap). P1: field-verify seating + bearing on grade.")

    def bom_group(self) -> str:
        return f"PierBlock|{round(self.length,2)}|{round(self.width,2)}|{round(self.height,2)}"

    def bom_label(self) -> str:
        return "Precast pier block"


@register_component("standoff_post_base")
class PostBase(Component):
    """An adjustable standoff post base — the purchased mechanical connector
    that holds a post DOWN onto its foundation against uplift and lateral load
    (exemplar: a Simpson ABU-class galvanized standoff). This is the part R29
    found missing: a pier block a leg merely *rests on* has no attachment; a
    post base is the attachment.

    Datum: base plate at Z=0 (bears on the foundation pad), the saddle body
    rises into +Z around the post's end (the reverse of ``PierBlock``, which
    drops into -Z). Modeled as an exact rectangular standoff so it is a clean
    validation body; the real connector is a formed-sheet saddle with a
    stand-off gap, a render- and field-detail concern, not a CAD one. Its
    anchor into the block and its post fasteners are field hardware carried on
    this part's own BOM line (see :meth:`assumptions`), so v1 adds ONE purchased
    part per foundation rather than a speculative fastener schedule.
    """

    material_key = "steel_galv"

    def __init__(self, width: float, length: float, height: float,
                 name: str = "post_base"):
        super().__init__(name)
        self.width = float(width)
        self.length = float(length)
        self.height = float(height)

    def _build(self) -> cq.Workplane:
        # Base plate at Z=0, saddle rising into +Z (bears DOWN on the block pad,
        # wraps the post base UP), the mirror of PierBlock's -Z body.
        return (
            cq.Workplane("XY")
            .box(self.length, self.width, self.height, centered=(True, True, False))
        )

    def _datums(self) -> dict[str, Frame]:
        # Local: base plate at Z=0 (seats on the foundation pad), saddle seat at
        # the top (+Z) where the post's end grain lands.
        return {
            "bottom": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
            "top": Frame.from_origin_axes((0, 0, self.height), (1, 0, 0), (0, 0, 1)),
        }

    def describe(self) -> str:
        return (f'{fmt_in(self.length, 1)} x {fmt_in(self.width, 1)} x '
                f'{fmt_in(self.height, 1)} standoff post base')

    def assumptions(self) -> str:
        return ("Exact rectangular standoff as validation body; real connector "
                "is a formed galvanized saddle with a stand-off gap. Its concrete "
                "anchor and post fasteners are field hardware carried on this "
                "BOM line (installed per the manufacturer's schedule) — not "
                "modeled as separate parts in v1. P1: field-verify anchor "
                "embedment + fastener count.")

    def bom_group(self) -> str:
        return f"PostBase|{round(self.length,2)}|{round(self.width,2)}|{round(self.height,2)}"

    def bom_label(self) -> str:
        return "Adjustable standoff post base"


@register_component("epoxy")
class Epoxy(Component):
    """Anchoring-epoxy annulus filling a drilled hole around an anchor rod.
    Datum: top at Z=0, annulus extends into -Z."""

    material_key = "epoxy"

    def __init__(self, hole_diameter: float, rod_diameter: float, depth: float,
                 name: str = "epoxy"):
        super().__init__(name)
        self.hole_diameter = float(hole_diameter)
        self.rod_diameter = float(rod_diameter)
        self.depth = float(depth)

    def _build(self) -> cq.Workplane:
        return (cq.Workplane("XY")
                .circle(self.hole_diameter / 2)
                .circle(self.rod_diameter / 2)
                .extrude(-self.depth))

    def _datums(self) -> dict[str, Frame]:
        # Local: top at Z=0, annulus into -Z.
        return {
            "top": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
            "bottom": Frame.from_origin_axes((0, 0, -self.depth), (1, 0, 0), (0, 0, 1)),
        }

    def describe(self) -> str:
        return (f'{fmt_in(self.hole_diameter)}/{fmt_in(self.rod_diameter)} '
                f'annulus x {fmt_in(self.depth, 1)} deep')

    def assumptions(self) -> str:
        return "Perfect annulus; real injection imperfect (clean-hole procedure)."

    def bom_group(self) -> str:
        return f"Epoxy|{round(self.hole_diameter,3)}|{round(self.depth,2)}"

    def bom_label(self) -> str:
        return "Anchoring epoxy"


@register_component("slab")
class Slab(Footing):
    """Slab-on-grade — a Footing with a slab-appropriate default check."""

    def __init__(self, width: float, length: float, thickness: float = 4 * IN,
                 name: str = "slab"):
        super().__init__(width, length, thickness, name)

    def check(self) -> list[str]:
        problems = Component.check(self)
        if self.thickness < 3.5 * IN:
            problems.append(
                f"{self.name}: {fmt_in(self.thickness)} thick — 3.5\" is the "
                f"practical minimum for a slab-on-grade"
            )
        return problems
