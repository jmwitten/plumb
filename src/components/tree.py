"""Tree-attachment components: a live trunk (context body) and a 2x6 beam end
with vertical slotted lag holes.

Both follow the Component contract documented in ``lumber.py``.

Local frames
------------
- ``TreeTrunk``: a vertical cylinder, axis **+Z**, base at Z=0, centered on
  the X/Y origin. It is a *context/interface* body — a live tree, neither cut
  nor fabricated — modeled as a clean cylinder so it is a well-behaved
  validation and ground datum (the round surface is exactly what makes the
  beam-to-trunk contact a tangent line rather than a face).

- ``SlottedBeamEnd``: the trunk-side end segment of a platform 2x6, modeled
  **on edge** in the same axis convention as ``Lumber`` but with a
  **center-X** origin so the two beams straddle the trunk symmetrically:

      X: -length/2 .. +length/2   (member run, centered on the trunk)
      Y: 0 .. thickness (1.5")     (the flat face toward the trunk is Y=0)
      Z: 0 .. depth (5.5")         (member stands on edge, 5.5" vertical)

  Each lag station gets a **vertical slotted hole** (racetrack: ``slot_w`` wide
  x ``slot_h`` tall) cut clean through the thickness, and a ``lag_face_i`` datum
  on the *outer* face (Y=thickness) at the lag axis height, so a washer/lag
  seats on the beam by a datum mate. The lag bears at the TOP of the slot with
  open travel below it (see the tree-attachment spec).
"""

from __future__ import annotations

import cadquery as cq

from ..core.base import Component
from ..core.frame import Frame
from ..core.registry import register_component
from ..core.units import IN, fmt_in
from ._geometry import axis_cylinder
from .lumber import NOMINAL_SIZES


@register_component("tree_trunk")
class TreeTrunk(Component):
    """A live tree trunk, modeled as a clean vertical cylinder (context only).

    Datum: axis +Z, base at Z=0, centered on X/Y; ``top`` at Z=height.

    Parameters
    ----------
    diameter, height: trunk size in mm (use ``n * IN``).
    """

    material_key = "lumber_spf"

    def __init__(self, diameter: float, height: float, name: str = "trunk"):
        super().__init__(name)
        self.diameter = float(diameter)
        self.height = float(height)
        #: existing live tree — excluded from buy-list semantics (BOM source).
        self.source = "existing (not purchased)"

    def _build(self) -> cq.Workplane:
        return cq.Workplane("XY").circle(self.diameter / 2).extrude(self.height)

    def _datums(self) -> dict[str, Frame]:
        return {
            "base": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
            "top": Frame.from_origin_axes((0, 0, self.height), (1, 0, 0), (0, 0, 1)),
            "axis": Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 0, 1)),
        }

    def describe(self) -> str:
        return (f'~{fmt_in(self.diameter)} dia x {fmt_in(self.height, 1)} '
                f'live trunk (attach zone)')

    def assumptions(self) -> str:
        return ("Existing live tree — not cut, notched or purchased. Modeled as "
                "an exact cylinder (clean validation/ground body); the real trunk "
                "is irregular and grows, which the per-side growth gap (the beams "
                "clear the trunk, platform detail) accommodates. Bark and surface "
                "irregularity are field concerns, not modeled.")

    def bom_label(self) -> str:
        return "Tree trunk (existing)"

    def bom_group(self) -> str:
        return f"TreeTrunk|{round(self.diameter, 2)}|{round(self.height, 2)}"


@register_component("slotted_beam_end")
class SlottedBeamEnd(Component):
    """A 2x6 platform-beam end segment with vertical slotted lag holes.

    See the module docstring for the local frame. Only the trunk-side end is
    modeled; the full beam run and its far (leg) end belong to the platform
    detail.

    Parameters
    ----------
    nominal: nominal lumber size (e.g. ``"2x6"``).
    length: modeled segment length in mm (a stub, not the full beam run).
    slots: ``[(x_station, lag_axis_z)]`` in mm (local frame) — one per lag.
    slot_w, slot_h: slotted-hole width and height in mm.
    shank_dia: lag shank diameter in mm; the lag bears at the slot top, so the
        slot top is placed a shank *radius* above ``lag_axis_z``.
    treated: pressure-treated (material/color).
    """

    def __init__(self, nominal: str, length: float,
                 slots: tuple = (), slot_w: float = 0.5625 * IN,
                 slot_h: float = 1.5 * IN, shank_dia: float = 0.5 * IN,
                 name: str | None = None, treated: bool = True,
                 ease_radius: float = 0.0, full_length: float | None = None):
        super().__init__(name or f"{nominal} beam end")
        if nominal not in NOMINAL_SIZES:
            raise ValueError(f"Unknown nominal size {nominal!r}")
        self.nominal = nominal
        self.length = float(length)
        self.slots = [(float(x), float(z)) for (x, z) in slots]
        self.slot_w = float(slot_w)
        self.slot_h = float(slot_h)
        self.shank_dia = float(shank_dia)
        self.treated = bool(treated)
        self.ease_radius = float(ease_radius)
        self.material_key = "lumber_pt" if treated else "lumber_spf"
        #: partial-member metadata (mm) — set when this end segment is a stub
        #: of the platform's continuous beam. Underscored so it stays out of
        #: ``params()``/BOM specs; surfaced through ``stub_of()``.
        self._full_length = None if full_length is None else float(full_length)

    @property
    def thickness(self) -> float:
        return NOMINAL_SIZES[self.nominal][0]

    @property
    def depth(self) -> float:
        return NOMINAL_SIZES[self.nominal][1]

    def _slot_cutter(self, x: float, lag_axis_z: float) -> cq.Workplane:
        """A racetrack (obround) slot solid, cut axis +Y (through thickness).
        The slot top sits a shank radius above the lag axis (lag bears at top);
        the straight run + bottom semicircle open the travel room below."""
        t = self.thickness
        w, h = self.slot_w, self.slot_h
        slot_top = lag_axis_z + self.shank_dia / 2.0
        center_z = slot_top - h / 2.0
        straight = max(h - w, 0.0)
        cutter = (cq.Workplane("XY")
                  .box(w, t * 4, straight, centered=True)
                  .translate((x, t / 2.0, center_z)))
        for dz in (straight / 2.0, -straight / 2.0):
            cutter = cutter.union(
                axis_cylinder(w / 2.0, t * 3, (x, -t, center_z + dz), (0, 1, 0)))
        return cutter

    def _build(self) -> cq.Workplane:
        # centered in X, from 0 in Y (thickness) and Z (depth).
        wp = cq.Workplane("XY").box(
            self.length, self.thickness, self.depth,
            centered=(True, False, False))
        if self.ease_radius > 0:
            try:
                wp = wp.edges("|X").fillet(self.ease_radius)
            except Exception:
                pass
        for (x, z) in self.slots:
            wp = wp.cut(self._slot_cutter(x, z))
        return wp

    def _datums(self) -> dict[str, Frame]:
        t, d = self.thickness, self.depth
        out: dict[str, Frame] = {
            # inner (trunk-side) face, outward normal -Y
            "inner_face": Frame.from_origin_axes((0, 0, d / 2), (1, 0, 0), (0, -1, 0)),
            # outer face, outward normal +Y
            "outer_face": Frame.from_origin_axes((0, t, d / 2), (1, 0, 0), (0, 1, 0)),
        }
        for i, (x, z) in enumerate(self.slots):
            # a seating datum on the OUTER face at the lag axis; +Z = outward
            # (+Y) so a washer's base mates flush and the lag drives inward.
            out[f"lag_face_{i}"] = Frame.from_origin_axes((x, t, z), (1, 0, 0), (0, 1, 0))
        return out

    def describe(self) -> str:
        return f'{self.nominal} x {fmt_in(self.length, 1)} (trunk-end stub)'

    def assumptions(self) -> str:
        return ("Actual dressed dimensions (PS 20). Only the trunk-side end is "
                "modeled — full beam run and leg end are the platform detail. "
                f"Lag holes are vertical slots {fmt_in(self.slot_w)} x "
                f"{fmt_in(self.slot_h)} (ASSUMED default: taller than the lag, "
                "lag bears at top, ~1\" travel below).")

    def bom_label(self) -> str:
        return ("PT " if self.treated else "") + self.nominal + " lumber"

    def bom_group(self) -> str:
        sig = ";".join(f"{round(x, 2)},{round(z, 2)}" for x, z in self.slots)
        return (f"SlottedBeamEnd|{self.nominal}|{round(self.length, 1)}|"
                f"{self.treated}|{round(self.slot_w, 3)}x{round(self.slot_h, 3)}|{sig}")

    def stub_of(self) -> dict | None:
        """See ``Component.stub_of``. Set only when constructed with
        ``full_length`` — this end segment is a stub of the platform's
        continuous beam."""
        if self._full_length is None:
            return None
        return {
            "full_dims": f'{self.nominal} x {fmt_in(self._full_length, 1)} '
                         '(continuous beam)',
            "modeled_dims": self.describe(),
            "note": f'shown: trunk-end {fmt_in(self.length, 1)} portion '
                    '— full run in the platform detail',
        }

    def check(self) -> list[str]:
        problems = super().check()
        if self.slot_h <= self.shank_dia:
            problems.append(f"{self.name}: slot no taller than the lag shank")
        if self.slot_w <= self.shank_dia:
            problems.append(f"{self.name}: slot no wider than the lag shank")
        return problems
