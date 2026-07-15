"""Threaded fasteners: lag screws, hex bolts, structural screws, washers,
hex nuts, all-thread rod.

All parts follow the Component contract documented in ``lumber.py``.

Local frame (headed fasteners)
------------------------------
Axis along **-Z**: the underside of the head sits at Z=0 and the shank/tip
extends downward. Placing a fastener is then just "put the origin where the
head bears and rotate the -Z axis into the drive direction."

Threads are modeled as a *representation* — a single revolved V-groove profile
on the visible zones (see ``_geometry.threaded_shaft``). Real helices only slow
boolean ops and exports and read as noise at detail scale; pitch is exaggerated
for legibility, which is a stated representation, not a fabrication spec.
"""

from __future__ import annotations

import cadquery as cq

from ..core.base import Component
from ..core.frame import Frame
from ..core.registry import register_component
from ..core.units import IN, fmt_in
from ._geometry import hex_prism, threaded_shaft, axis_cylinder

#: Hex head/nut width-across-flats by nominal diameter (inch fasteners), in mm.
HEX_AF: dict[float, float] = {
    0.25 * IN: 7 / 16 * IN,
    0.3125 * IN: 1 / 2 * IN,
    0.375 * IN: 9 / 16 * IN,
    0.5 * IN: 3 / 4 * IN,
    0.625 * IN: 15 / 16 * IN,
    0.75 * IN: 1.125 * IN,
}

#: Nut height by nominal diameter (finished hex nut), in mm.
NUT_HEIGHT: dict[float, float] = {
    0.25 * IN: 7 / 32 * IN, 0.3125 * IN: 17 / 64 * IN, 0.375 * IN: 21 / 64 * IN,
    0.5 * IN: 7 / 16 * IN, 0.625 * IN: 35 / 64 * IN, 0.75 * IN: 41 / 64 * IN,
}


def _hex_af(diameter: float) -> float:
    return HEX_AF.get(diameter, 1.5 * diameter)


class _AxialFastener(Component):
    """Shared geometry for headed, shanked fasteners (see module frame note)."""

    material_key = "steel_zinc"
    #: fraction of the *threaded* shank length that carries thread representation
    thread_fraction = 0.55
    thread_pitch_ratio = 0.22   # display pitch as a fraction of diameter

    def __init__(self, diameter: float, length: float, name: str):
        super().__init__(name)
        self.diameter = float(diameter)
        self.length = float(length)  # under-head length

    @property
    def head_af(self) -> float:
        return _hex_af(self.diameter)

    @property
    def head_height(self) -> float:
        return 0.65 * self.diameter

    def _build(self) -> cq.Workplane:
        head = hex_prism(self.head_af, self.head_height)
        tip_len = self._tip_length()
        shank_len = self.length - tip_len
        pitch = self.thread_pitch_ratio * self.diameter
        thread_zone = shank_len * self.thread_fraction
        # threaded_shaft builds +Z from 0; flip it to run -Z under the head.
        shaft = threaded_shaft(
            self.diameter, shank_len, pitch,
            zones=[(0.0, thread_zone)],
        ).rotate((0, 0, 0), (1, 0, 0), 180)
        wp = head.union(shaft)
        tip = self._tip()
        if tip.vals():
            wp = wp.union(tip)
        return wp

    def _datums(self) -> dict[str, Frame]:
        # Local frame: head underside at Z=0, shank/tip run -Z (module note).
        return {
            # bearing surface under the head; +Z points up toward the head
            # (away from the shank) so a washer/part seats under the head.
            "head_bearing": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
            # tip end; +Z points back up the shank toward the head, the
            # direction a nut travels as it threads on.
            "tip": Frame.from_origin_axes((0, 0, -self.length), (1, 0, 0), (0, 0, 1)),
            # drive/insertion axis: +Z runs down the shank.
            "axis": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, -1)),
        }

    # Subclasses override for pointed vs flat ends.
    def _tip_length(self) -> float:
        return 0.0

    def _tip(self) -> cq.Workplane:
        return cq.Workplane("XY")  # empty

    def check(self) -> list[str]:
        problems = super().check()
        if self.length < 2 * self.diameter:
            problems.append(f"{self.name}: implausibly short for its diameter")
        return problems


    def describe(self) -> str:
        return f'{fmt_in(self.diameter)} dia x {fmt_in(self.length, 1)}'

    def assumptions(self) -> str:
        return ("Thread represented as a revolved V-groove on the threaded "
                "zone; pitch exaggerated for legibility, not a fab spec.")

    def bom_group(self) -> str:
        return f"{type(self).__name__}|{round(self.diameter,2)}|{round(self.length,2)}"


@register_component("lag_screw")
class LagScrew(_AxialFastener):
    """Hex-head lag screw with a conical gimlet tip.

    Datum: underside of head at Z=0, tip at Z=-length.
    """

    material_key = "steel_galv"

    def __init__(self, diameter: float, length: float, name: str | None = None):
        super().__init__(
            diameter, length,
            name or f'{fmt_in(diameter)} x {fmt_in(length, 1)} lag',
        )

    def _tip_length(self) -> float:
        return 1.2 * self.diameter

    def _tip(self) -> cq.Workplane:
        cyl_end = -(self.length - self._tip_length())
        return (
            cq.Workplane("XY")
            .workplane(offset=cyl_end)
            .circle(self.diameter / 2)
            .workplane(offset=-self._tip_length())
            .circle(0.02 * IN)  # near-point; zero radius makes loft unstable
            .loft()
        )


@register_component("hex_bolt")
class HexBolt(_AxialFastener):
    """Hex bolt (flat end). Datum: underside of head at Z=0."""

    def __init__(self, diameter: float, length: float, name: str | None = None):
        super().__init__(
            diameter, length,
            name or f'{fmt_in(diameter)} x {fmt_in(length, 1)} bolt',
        )


@register_component("structural_screw")
class StructuralScrew(LagScrew):
    """Structural wood screw (GRK/LedgerLOK class) — geometry is lag-like;
    exists as its own class so BOMs and checks can distinguish it."""

    material_key = "steel_galv"


@register_component("exterior_wood_screw")
class ExteriorWoodScrew(_AxialFastener):
    """Pointed, corrosion-resistant exterior wood screw with a round head.

    This ordinary assembly/service fastener is deliberately distinct from the
    GRK/LedgerLOK-class :class:`StructuralScrew`: its presence carries no
    structural capacity implication. The local datum contract is the common
    headed-fastener frame (head underside at Z=0, shank along -Z).
    """

    material_key = "steel_galv"
    thread_fraction = 0.72

    def __init__(self, diameter: float, length: float, name: str | None = None):
        super().__init__(
            diameter,
            length,
            name or f"{fmt_in(diameter)} x {fmt_in(length, 1)} exterior wood screw",
        )

    @property
    def head_diameter(self) -> float:
        return 2.3 * self.diameter

    @property
    def head_height(self) -> float:
        return 0.45 * self.diameter

    def _tip_length(self) -> float:
        return 1.2 * self.diameter

    def _tip(self) -> cq.Workplane:
        cyl_end = -(self.length - self._tip_length())
        return (
            cq.Workplane("XY")
            .workplane(offset=cyl_end)
            .circle(self.diameter / 2)
            .workplane(offset=-self._tip_length())
            .circle(0.02 * IN)
            .loft()
        )

    def _build(self) -> cq.Workplane:
        head = axis_cylinder(
            self.head_diameter / 2,
            self.head_height,
            (0, 0, 0),
            (0, 0, 1),
        )
        tip_len = self._tip_length()
        shank_len = self.length - tip_len
        pitch = self.thread_pitch_ratio * self.diameter
        shaft = threaded_shaft(
            self.diameter,
            shank_len,
            pitch,
            zones=[(0.0, shank_len * self.thread_fraction)],
        ).rotate((0, 0, 0), (1, 0, 0), 180)
        return head.union(shaft).union(self._tip())

    def describe(self) -> str:
        return (
            f"{fmt_in(self.diameter)} dia x {fmt_in(self.length, 1)} "
            "exterior wood screw"
        )

    def assumptions(self) -> str:
        return (
            "Corrosion-resistant exterior wood screw with a simplified round "
            "head and represented threads; manufacturer, coating system, drive, "
            "and capacity are not selected or analyzed."
        )

    def bom_label(self) -> str:
        return "Exterior wood screw"


@register_component("hex_nut")
class HexNut(Component):
    """Finished hex nut with washer-face chamfers.

    Datum: bottom face at Z=0, axis +Z, bore centered on the axis.
    """

    material_key = "steel_zinc"

    def __init__(self, diameter: float, height: float | None = None,
                 across_flats: float | None = None, name: str | None = None,
                 label: str = "hex nut"):
        super().__init__(name or f"{fmt_in(diameter)} {label}")
        self.diameter = float(diameter)
        self.height = float(height or NUT_HEIGHT.get(diameter, 0.85 * diameter))
        self.across_flats = float(across_flats or _hex_af(diameter))
        self.label = label

    def _build(self) -> cq.Workplane:
        return (
            hex_prism(self.across_flats, self.height)
            .faces(">Z").workplane().hole(self.diameter)
        )

    def _datums(self) -> dict[str, Frame]:
        # Local: bottom face Z=0, axis +Z, top at Z=height.
        return {
            "base": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
            "top": Frame.from_origin_axes((0, 0, self.height), (1, 0, 0), (0, 0, 1)),
            "axis": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
        }

    def describe(self) -> str:
        return f'{fmt_in(self.diameter)} {self.label} ({fmt_in(self.across_flats)} AF)'

    def assumptions(self) -> str:
        return "Finished hex nut; threads not modeled (bore at nominal)."

    def bom_group(self) -> str:
        return f"HexNut|{round(self.diameter,3)}|{self.label}"

    def bom_label(self) -> str:
        return self.label.capitalize()


@register_component("washer")
class Washer(Component):
    """Flat/fender washer. Datum: bottom face at Z=0, axis +Z."""

    material_key = "steel_zinc"

    def __init__(self, inner_diameter: float, outer_diameter: float | None = None,
                 thickness: float | None = None, name: str | None = None,
                 fender: bool = False):
        kind = "fender washer" if fender else "washer"
        super().__init__(name or f"{fmt_in(inner_diameter)} {kind}")
        self.inner_diameter = float(inner_diameter)
        default_od = (3.0 if fender else 2.2) * inner_diameter
        self.outer_diameter = float(outer_diameter or default_od)
        self.thickness = float(thickness or 0.1 * inner_diameter + 1.0)
        self.fender = fender

    def _build(self) -> cq.Workplane:
        return (
            cq.Workplane("XY")
            .circle(self.outer_diameter / 2)
            .circle(self.inner_diameter / 2)
            .extrude(self.thickness)
        )

    def _datums(self) -> dict[str, Frame]:
        # Local: bottom face Z=0, axis +Z, top at Z=thickness.
        return {
            "base": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
            "top": Frame.from_origin_axes((0, 0, self.thickness), (1, 0, 0), (0, 0, 1)),
            "axis": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
        }

    def describe(self) -> str:
        kind = "fender washer" if self.fender else "flat washer"
        return (f'{kind} {fmt_in(self.outer_diameter)} OD x '
                f'{fmt_in(self.inner_diameter)} ID x {fmt_in(self.thickness)}')

    def assumptions(self) -> str:
        return "Nominal catalog dimensions."

    def bom_group(self) -> str:
        return (f"Washer|{round(self.inner_diameter,3)}|"
                f"{round(self.outer_diameter,3)}|{self.fender}")

    def bom_label(self) -> str:
        return "Fender washer" if self.fender else "Flat washer"


@register_component("threaded_rod")
class ThreadedRod(Component):
    """All-thread rod (anchor rod). Thread representation on chosen zones only;
    the embedded portion is left smooth.

    Datum: axis +Z, Z=0 at the bottom (embedded) end.
    """

    material_key = "steel_galv"
    thread_pitch_ratio = 0.3   # exaggerated display pitch / diameter

    def __init__(self, diameter: float, length: float,
                 thread_zones: list[tuple[float, float]] | None = None,
                 name: str | None = None):
        super().__init__(name or f'{fmt_in(diameter)} x {fmt_in(length, 1)} all-thread')
        self.diameter = float(diameter)
        self.length = float(length)
        #: defensively copied (like every other list-typed param in this
        #: package, e.g. Lumber.holes) so a caller mutating the list they
        #: passed in after construction can't retroactively change this
        #: instance's geometry.
        self.thread_zones = list(thread_zones) if thread_zones is not None else None

    def _build(self) -> cq.Workplane:
        pitch = self.thread_pitch_ratio * self.diameter
        return threaded_shaft(self.diameter, self.length, pitch,
                              zones=self.thread_zones)

    def _datums(self) -> dict[str, Frame]:
        # Local: axis +Z, Z=0 at the bottom (embedded) end, exposed end at +L.
        return {
            "bottom": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
            "top": Frame.from_origin_axes((0, 0, self.length), (1, 0, 0), (0, 0, 1)),
            "axis": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
        }

    def describe(self) -> str:
        return f'{fmt_in(self.diameter)} dia x {fmt_in(self.length, 1)} all-thread'

    def assumptions(self) -> str:
        return ("Thread represented on exposed zone only; embedded length "
                "smooth. Pitch exaggerated for legibility.")

    def bom_group(self) -> str:
        return f"ThreadedRod|{round(self.diameter,3)}|{round(self.length,2)}"

    def bom_label(self) -> str:
        return "Anchor rod (all-thread)"

    def check(self) -> list[str]:
        problems = super().check()
        if self.length < 3 * self.diameter:
            problems.append(f"{self.name}: implausibly short for its diameter")
        return problems
