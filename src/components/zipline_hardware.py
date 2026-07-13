"""Trolley/launch-edge hardware: the pre-existing zipline cable/trolley/hanger/
grab-bar (context/reference geometry) plus the two new fabricated parts the
launch edge adds — the strap gate and the grab handle.

All parts follow the Component contract documented in
``detailgen.components.lumber``.

Local frames
------------
- ``Cable``, ``TrolleyWheel``, ``Hanger``, ``GrabBar`` are deliberately built
  with their datum axes **already aligned to this detail's world axes**
  (X = across the deck width, Y = direction of travel, Z = up), so the whole
  hanging chain places via ``place().on()`` mates with zero rotation anywhere
  — see ``details/trolley_launch.py`` for why that matters. Only ``Cable`` is
  positioned by a global measurement (``add``); the rest mate onto their
  neighbor.
- ``StrapGate`` spans local +X (post to post) with rings at each end whose
  axis is also local X, so it presses flat against a post's X-facing inner
  face; placed with ``add`` (its span is a fixed global measurement).
- ``GrabHandle`` mounts flush on a vertical face at local Y=0, standing off
  in +Y, with the grip running vertically in local Z; placed with ``add``
  (its mount height above the deck is a global design measurement).

These four "existing hardware" parts carry ``self.source = "existing — not
purchased"`` (per the common brief: model as context/reference geometry,
excluded from buy-list semantics via source metadata) — real geometry
included for correct placement of the launch-edge structure relative to
them, but they never appear as a "to buy" BOM line.
"""

from __future__ import annotations

import cadquery as cq

from ..core.base import Component
from ..core.frame import Frame
from ..core.registry import register_component
from ..core.units import fmt_in
from ._geometry import axis_cylinder

# TODO(consolidate): Cable/TrolleyWheel/Hanger/GrabBar are generic enough to
# belong in a shared "existing hardware" module eventually; kept here per the
# common brief's file-ownership split (three agents building in parallel).


@register_component("cable")
class Cable(Component):
    """Pre-existing zipline cable — reference/context geometry only; not
    purchased, not in this build's BOM. Anchored to the tree at the far end
    (out of scope — the tree-attachment detail owns that anchorage); this
    models a short straight segment at the launch end, long enough to read as
    a cable in the assembly, not the full tree-to-launch run.

    Datum: axis along local +Y (the direction of travel — matches the
    platform's beam-run axis), centered on the local origin. ``mid`` is the
    point along the cable the trolley rides at.
    """

    material_key = "steel_galv"

    def __init__(self, diameter: float, length: float, name: str = "zipline cable"):
        super().__init__(name)
        self.diameter = float(diameter)
        self.length = float(length)
        self.source = "existing — not purchased"

    def _build(self) -> cq.Workplane:
        return axis_cylinder(self.diameter / 2, self.length,
                              (0, -self.length / 2, 0), (0, 1, 0))

    def _datums(self) -> dict[str, Frame]:
        return {"mid": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1))}

    def describe(self) -> str:
        return f'{fmt_in(self.diameter)} dia cable, {fmt_in(self.length, 1)} shown'

    def assumptions(self) -> str:
        return ("Pre-existing zipline cable, already installed and anchored to "
                "the tree — not purchased or fabricated as part of this build. "
                "Modeled as a short reference segment at the launch end only; "
                "diameter is an assumed representative size (no callout given).")

    def bom_label(self) -> str:
        return "Zipline cable (existing)"


@register_component("trolley_wheel")
class TrolleyWheel(Component):
    """Pre-existing zipline trolley wheel/pulley — reference/context geometry
    only; not purchased, not in this build's BOM. Rides on the cable.

    Datum: local origin at the wheel's bore center (where the cable threads
    through) — ``grip`` mates onto the cable's ``mid`` datum. ``bottom`` is
    where the hanger attaches, directly below the wheel.

    The bore is modeled intentionally **smaller** than the cable diameter
    (see ``assumptions``) so the wheel-cable contact is a deterministic,
    allowlisted overlap representing "rides on/wraps the cable" in this
    simplified reference geometry — not a real pulley-groove fabrication.
    """

    material_key = "steel_galv"

    def __init__(self, diameter: float, width: float, bore_diameter: float,
                 name: str = "trolley wheel"):
        super().__init__(name)
        self.diameter = float(diameter)
        self.width = float(width)
        self.bore_diameter = float(bore_diameter)
        self.source = "existing — not purchased"

    def _build(self) -> cq.Workplane:
        # Disc: flat faces perpendicular to X (rotation axis), circular
        # profile in the Y-Z plane. The bore runs along Y (the cable's own
        # direction, once placed) THROUGH the diameter, at the disc's
        # centerline — not through the thin X-width — so the cable actually
        # threads through the wheel.
        disc = (cq.Workplane("YZ").circle(self.diameter / 2)
                .extrude(self.width, both=True))
        bore = axis_cylinder(self.bore_diameter / 2, self.diameter * 6,
                              (0, -self.diameter * 3, 0), (0, 1, 0))
        return disc.cut(bore)

    def _datums(self) -> dict[str, Frame]:
        return {
            "grip": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
            "bottom": Frame.from_origin_axes((0, 0, -self.diameter / 2),
                                             (1, 0, 0), (0, 0, 1)),
        }

    def describe(self) -> str:
        return f'{fmt_in(self.diameter)} dia x {fmt_in(self.width)} wide wheel'

    def assumptions(self) -> str:
        return ("Pre-existing zipline trolley wheel — not purchased/fabricated "
                "here. Drawing shows a schematic circle with no callout; "
                "diameter/width are assumed representative sizes (visualization "
                "placeholders). Bore modeled smaller than the cable (no "
                "clearance) as a simplified 'wraps the cable' representation, "
                "not a real pulley-groove spec — allowlisted overlap.")

    def bom_label(self) -> str:
        return "Trolley wheel (existing)"


@register_component("hanger")
class Hanger(Component):
    """Pre-existing rod/chain connecting the trolley to the grab bar —
    reference/context geometry only; not purchased, not in this build's BOM.

    Datum: axis +Z, ``bottom`` at the origin, ``top`` at +length (mirrors
    ``ThreadedRod``'s convention).
    """

    material_key = "steel_galv"

    def __init__(self, diameter: float, length: float, name: str = "hanger"):
        super().__init__(name)
        self.diameter = float(diameter)
        self.length = float(length)
        self.source = "existing — not purchased"

    def _build(self) -> cq.Workplane:
        return axis_cylinder(self.diameter / 2, self.length, (0, 0, 0), (0, 0, 1))

    def _datums(self) -> dict[str, Frame]:
        return {
            "top": Frame.from_origin_axes((0, 0, self.length), (1, 0, 0), (0, 0, 1)),
            "bottom": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
        }

    def describe(self) -> str:
        return f'{fmt_in(self.diameter)} dia x {fmt_in(self.length, 1)} hanger rod'

    def assumptions(self) -> str:
        return ("Pre-existing hanger (rod/chain) — not purchased/fabricated "
                "here. Length is not directly dimensioned; derived as "
                "cable height minus grab-bar height, near the low end of the "
                "vault note's ~8-16in estimate. Modeled as a plain rod "
                "(chain links not represented).")

    def bom_label(self) -> str:
        return "Hanger (existing)"


@register_component("grab_bar")
class GrabBar(Component):
    """Pre-existing grab bar the rider holds before/during launch — reference/
    context geometry only; not purchased, not in this build's BOM. Its height
    is the platform's primary design driver.

    Datum: axis +X, centered on the local origin, rounded/capped ends.
    ``top_mid`` is the centerline's top surface where the hanger attaches.
    """

    material_key = "steel_zinc"

    def __init__(self, diameter: float, length: float, name: str = "grab bar"):
        super().__init__(name)
        self.diameter = float(diameter)
        self.length = float(length)
        self.source = "existing — not purchased"

    def _build(self) -> cq.Workplane:
        r = self.diameter / 2
        straight = self.length - 2 * r
        body = axis_cylinder(r, straight, (-straight / 2, 0, 0), (1, 0, 0))
        cap_a = cq.Workplane("XY").add(cq.Solid.makeSphere(r, cq.Vector(-straight / 2, 0, 0)))
        cap_b = cq.Workplane("XY").add(cq.Solid.makeSphere(r, cq.Vector(straight / 2, 0, 0)))
        return body.union(cap_a).union(cap_b)

    def _datums(self) -> dict[str, Frame]:
        return {
            "top_mid": Frame.from_origin_axes((0, 0, self.diameter / 2),
                                              (1, 0, 0), (0, 0, 1)),
        }

    def describe(self) -> str:
        return f'{fmt_in(self.diameter)} dia x {fmt_in(self.length, 1)} grab bar, rounded ends'

    def assumptions(self) -> str:
        return ("Pre-existing grab bar — not purchased/fabricated here. "
                "Drawing shows a schematic rounded bar with no callout; "
                "length/diameter are assumed representative sizes "
                "(visualization placeholders, ~16-18in typical).")

    def bom_label(self) -> str:
        return "Grab bar (existing)"

    def check(self) -> list[str]:
        problems = super().check()
        if self.length <= 2 * self.diameter:
            problems.append(f"{self.name}: implausibly short for its diameter")
        return problems


@register_component("strap_gate")
class StrapGate(Component):
    """NEW — fabricated. Closes the open launch edge with a short safety
    strap/chain and a carabiner at each end (in the project's shopping list).
    Modeled as simple solids per the common brief (straps/gates are not
    modeled as a real buckle/hook mechanism): a flat webbing strap with a
    torus ring fused at each end representing the carabiner attachment point.

    Datum: local +X is the span direction (post to post); the strap is
    centered on Y=0 (across its width) and Z=0 (through its thickness). Ring
    axes lie along local X so each ring presses flat against the facing
    post's X-normal face. ``span`` is ring-center to ring-center; placed with
    ``add`` in the detail (its span is a fixed global measurement — the clear
    gap between the two launch posts — not a mate).
    """

    material_key = "steel_galv"

    def __init__(self, span: float, width: float, thickness: float,
                 ring_od: float, ring_tube_dia: float, name: str = "strap gate"):
        super().__init__(name)
        self.span = float(span)
        self.width = float(width)
        self.thickness = float(thickness)
        self.ring_od = float(ring_od)
        self.ring_tube_dia = float(ring_tube_dia)

    @property
    def ring_major_radius(self) -> float:
        return (self.ring_od - self.ring_tube_dia) / 2

    def _build(self) -> cq.Workplane:
        strap = cq.Workplane("XY").box(
            self.span, self.width, self.thickness, centered=(False, True, True))
        r_maj, r_min = self.ring_major_radius, self.ring_tube_dia / 2
        ring_a = cq.Workplane("XY").add(
            cq.Solid.makeTorus(r_maj, r_min, cq.Vector(0, 0, 0), cq.Vector(1, 0, 0)))
        ring_b = cq.Workplane("XY").add(
            cq.Solid.makeTorus(r_maj, r_min, cq.Vector(self.span, 0, 0), cq.Vector(1, 0, 0)))
        return strap.union(ring_a).union(ring_b)

    def _datums(self) -> dict[str, Frame]:
        return {
            "ring_a": Frame.from_origin_axes((0, 0, 0), (0, 1, 0), (-1, 0, 0)),
            "ring_b": Frame.from_origin_axes((self.span, 0, 0), (0, 1, 0), (1, 0, 0)),
        }

    def describe(self) -> str:
        return (f'{fmt_in(self.width)} strap x {fmt_in(self.span, 1)} span '
                f'+ 2 carabiner rings')

    def assumptions(self) -> str:
        return ("Strap/chain + carabiner represented as a flat webbing strap "
                "with a torus ring fused at each end — a simplified solid per "
                "the framework's straps/gates convention, not a literal "
                "buckle/carabiner mechanism. Width/thickness/ring size are "
                "assumed (the spec calls it 'short', no dimensions given).")

    def bom_group(self) -> str:
        return f"StrapGate|{round(self.span, 1)}|{round(self.width, 2)}"

    def bom_label(self) -> str:
        return "Strap gate (safety strap + carabiner)"

    def check(self) -> list[str]:
        problems = super().check()
        if self.span <= self.ring_od:
            problems.append(f"{self.name}: span too short for the ring size to clear")
        return problems


@register_component("grab_handle")
class GrabHandle(Component):
    """NEW — fabricated. Fixed galvanized grab handle mounted on the
    launch-corner post (in the project's shopping list), so a kid has
    something to hold before the trolley bar takes their weight. Modeled as a
    bent tube: two short standoff legs perpendicular to the mounting face,
    joined by a vertical grip bar — engineering-grade but legible, not a
    specific manufacturer SKU.

    Datum: mounts flush against a flat vertical face at local Y=0 (the
    mounting plane), standing off into +Y. The grip runs vertically in local
    Z: ``mount_bottom`` at Z=0, ``mount_top`` at Z=``grip_length``.
    """

    material_key = "steel_galv"

    def __init__(self, grip_length: float, diameter: float, standoff: float,
                 name: str = "grab handle"):
        super().__init__(name)
        self.grip_length = float(grip_length)
        self.diameter = float(diameter)
        self.standoff = float(standoff)

    def _build(self) -> cq.Workplane:
        r = self.diameter / 2
        leg_bottom = axis_cylinder(r, self.standoff, (0, 0, 0), (0, 1, 0))
        leg_top = axis_cylinder(r, self.standoff, (0, 0, self.grip_length), (0, 1, 0))
        grip = axis_cylinder(r, self.grip_length, (0, self.standoff, 0), (0, 0, 1))
        corner_bottom = cq.Workplane("XY").add(
            cq.Solid.makeSphere(r, cq.Vector(0, self.standoff, 0)))
        corner_top = cq.Workplane("XY").add(
            cq.Solid.makeSphere(r, cq.Vector(0, self.standoff, self.grip_length)))
        return (leg_bottom.union(leg_top).union(grip)
                .union(corner_bottom).union(corner_top))

    def _datums(self) -> dict[str, Frame]:
        return {
            "mount_bottom": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 1, 0)),
            "mount_top": Frame.from_origin_axes((0, 0, self.grip_length),
                                                (1, 0, 0), (0, 1, 0)),
        }

    def describe(self) -> str:
        return (f'{fmt_in(self.diameter)} dia grab handle, '
                f'{fmt_in(self.grip_length)} grip, {fmt_in(self.standoff)} standoff')

    def assumptions(self) -> str:
        return ("Bent-tube grab handle simplified as straight standoff legs "
                "with spherical corner blends (no true tube-bend fillet). "
                "Mount height (between the 36in rail and the 46in-above-deck "
                "trolley bar) and all dimensions are this detail's own "
                "assumption — not given in the source drawing — since no "
                "handle height/size callout exists. Not a specific "
                "manufacturer SKU.")

    def bom_label(self) -> str:
        return "Grab handle (galvanized)"

    def check(self) -> list[str]:
        problems = super().check()
        if self.standoff < self.diameter:
            problems.append(
                f"{self.name}: standoff {fmt_in(self.standoff)} tight for "
                f"fingers behind a {fmt_in(self.diameter)} grip"
            )
        return problems
