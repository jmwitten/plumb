"""Guard-rail infill for the zipline platform: welded-wire mesh panels.

Follows the Component contract documented in ``lumber.py``. The platform's rail
posts, top rails, diagonal braces and steps are all plain :class:`Lumber`
members (2x4 / 2x6 PT) — no new class is needed for those. The one thing the
stock library has no part for is the galvanized welded-wire mesh that screens
the open guard bays, so it lives here.

Per the framework brief, a wire MESH is modeled as a single thin solid panel
(NOT individual wires): the wires read as noise at detail scale and the panel's
envelope is what matters for the guard-envelope (sphere-rule) intent. The
per-part ``assumptions()`` states this so it surfaces in the BOM/report.

Local frame (datum)
-------------------
A ``WireMesh`` panel is modeled like a thin board:

    X: 0 .. length      (along the rail run)
    Y: 0 .. thickness   (the panel's small thickness — the mesh plane is X-Z)
    Z: 0 .. height      (deck-to-rail span)

origin at a bottom corner, so the mesh plane is the X-Z face. Datums mirror
Lumber's (``base``/``top`` on the wide faces, ``face_near``/``face_far`` on the
thin faces, ``end_near``/``end_far`` at the ends) so a panel can be seated
against a rail or a post by a datum mate just like a board.
"""

from __future__ import annotations

import cadquery as cq

from ..core.base import Component
from ..core.frame import Frame
from ..core.registry import register_component
from ..core.units import IN, fmt_in


@register_component("wire_mesh")
class WireMesh(Component):
    """A welded-wire / hardware-cloth guard panel, modeled as one thin solid
    panel (see module docstring).

    Parameters
    ----------
    length, height:
        Panel extents in the rail plane (mm) — ``length`` along the run,
        ``height`` the deck-to-rail span.
    thickness:
        Panel thickness (mm). Default ~1/8" — the mesh's visual/envelope depth,
        not a structural dimension.
    opening:
        Nominal mesh opening (mm) carried for the BOM/sphere-rule note only; it
        does not change the solid (the panel is solid, not perforated).
    name:
        Human label for assemblies/BOM.
    """

    material_key = "steel_galv"

    def __init__(self, length: float, height: float,
                 thickness: float = 0.125 * IN, opening: float = 2.0 * IN,
                 name: str = "wire mesh"):
        super().__init__(name)
        self.length = float(length)
        self.height = float(height)
        self.thickness = float(thickness)
        self.opening = float(opening)

    def _build(self) -> cq.Workplane:
        # Origin at a bottom corner; the mesh plane is the wide X-Z face.
        return cq.Workplane("XY").box(
            self.length, self.thickness, self.height, centered=False)

    def _datums(self) -> dict[str, Frame]:
        # Local frame: length +X, thickness +Y, height +Z, corner origin — the
        # same datum layout as Lumber so a panel mates like a board.
        L, t, h = self.length, self.thickness, self.height
        return {
            "base": Frame.from_origin_axes((L / 2, t / 2, 0), (1, 0, 0), (0, 0, 1)),
            "top": Frame.from_origin_axes((L / 2, t / 2, h), (1, 0, 0), (0, 0, 1)),
            "face_near": Frame.from_origin_axes((L / 2, 0, h / 2), (1, 0, 0), (0, -1, 0)),
            "face_far": Frame.from_origin_axes((L / 2, t, h / 2), (1, 0, 0), (0, 1, 0)),
            "end_near": Frame.from_origin_axes((0, t / 2, h / 2), (0, 0, 1), (-1, 0, 0)),
            "end_far": Frame.from_origin_axes((L, t / 2, h / 2), (0, 0, 1), (1, 0, 0)),
        }

    def describe(self) -> str:
        return (f'welded-wire mesh {fmt_in(self.length, 1)} x '
                f'{fmt_in(self.height, 1)}, {fmt_in(self.opening)} openings')

    def assumptions(self) -> str:
        return ("Mesh modeled as a single thin panel, not individual wires "
                f"(envelope only); {fmt_in(self.opening)} openings satisfy the "
                "4\" sphere rule. Fastened with staples/screws + fender washers.")

    def bom_group(self) -> str:
        return (f"WireMesh|{round(self.length,1)}|{round(self.height,1)}|"
                f"{round(self.thickness,3)}")

    def bom_label(self) -> str:
        return "Welded-wire mesh panel"

    def check(self) -> list[str]:
        problems = super().check()
        if self.opening > 4.0 * IN:
            problems.append(
                f"{self.name}: {fmt_in(self.opening)} opening exceeds the 4\" "
                f"guard sphere rule")
        return problems


# TODO(consolidate): 5/4 decking is a real nominal the shared ``lumber.py``
# module has no entry for (NOMINAL_SIZES stops at 1x/2x). If a "5/4x6" key is
# ever added there, this class collapses into ``Lumber("5/4x6", ...)``. Kept
# here (my owned module) per the parallel-authoring rule rather than editing
# the shared lumber module.
@register_component("deck_board")
class DeckBoard(Component):
    """A 5/4x6 pressure-treated decking board (1" x 5.5" dressed), laid flat.

    Local frame (datum)
    -------------------
        X: 0 .. length      (the board run)
        Y: 0 .. width       (5.5" wide face, laid horizontal)
        Z: 0 .. thickness   (1" — the board laid flat, wide face up)

    origin at a bottom corner, so ``base`` (Z=0) seats down on the joists and
    ``top`` (Z=thickness) is the walking surface.
    """

    material_key = "lumber_pt"

    WIDTH = 5.5 * IN
    THICKNESS = 1.0 * IN     # 5/4 stock dresses to a full 1"

    def __init__(self, length: float, name: str = "deck board",
                 ease_radius: float = 0.125 * IN, trunk_cut: tuple | None = None):
        super().__init__(name)
        self.length = float(length)
        self.ease_radius = float(ease_radius)
        #: board-local trunk notch (cx, cy, radius) in mm, cut straight through the
        #: thickness (+Z) — a board fitted around the live trunk where the deck field
        #: crosses it (TREEFREE deck cutout). Underscored: it is not a purchased
        #: distinction (the board is still bought full-length, notched on site), so
        #: it stays out of ``params()``/BOM; ``cache_key`` folds it in so a notched
        #: board never shares a cached solid with an un-notched one of equal length.
        self._trunk_cut = None if trunk_cut is None else tuple(float(c) for c in trunk_cut)
        #: The FEATURE (CL-2) that produced the cut, if any: ``(noun, step_kind,
        #: provenance)`` set post-placement by the compiler's feature pass so the
        #: fabrication step speaks the feature's own name (a clearance_cut around
        #: the trunk vs a designed cup-hole bore). ``None`` for a legacy direct
        #: ``trunk_cut=`` construction, which keeps the old trunk wording.
        self._notch_feature = None

    def apply_feature_cut(self, cx: float, cy: float, radius: float, *,
                          noun: str, step_kind: str, provenance: str) -> None:
        """Install a CL-2 FEATURE's derived board-local cut ``(cx, cy, radius)``
        and the identity its fabrication step speaks. Called after placement (the
        cut center is derived from the referenced part's placed position); the
        installed solid stays lazy, so setting it here is byte-identical to the
        same cut authored as the old ``trunk_cut`` param."""
        self._trunk_cut = (float(cx), float(cy), float(radius))
        self._notch_feature = (str(noun), str(step_kind), str(provenance))

    def cache_key(self) -> tuple:
        return super().cache_key() + (("trunk_cut", repr(self._trunk_cut)),)

    def fabrication_record(self, part_id: str = ""):
        """This board's fabrication story: crosscut to length, ease the long
        edges, then — only if the trunk actually crosses this board — notch it.
        The installed solid is DERIVED from these steps (see
        ``process_graph.fold``), so the geometry and the cut list read the one
        step list and cannot describe different realities (retro R28).

        A board whose ``trunk_cut`` cylinder falls entirely outside its own
        footprint is the §6.2 geometric no-op: it carries NO ``notch`` step, so
        its cut list reads "plain" truthfully — the ABSENCE of the operation is
        the fact, and today's no-op cut must not become a phantom op. (Every
        shipped platform board is crossed and gets a real notch.)"""
        from ..core.process_graph import (
            ProcessRecord, ProcessStep, StockRef, notch_removes_material)

        stock = StockRef(profile="5/4x6 PT", form="linear_stick",
                         section=(self.WIDTH, self.THICKNESS),
                         material_key=self.material_key)
        steps = [ProcessStep.crosscut(self.length, provenance="finished-length")]
        if self.ease_radius > 0:
            steps.append(ProcessStep.ease(self.ease_radius, provenance="ease_radius"))
        if self._trunk_cut is not None:
            cx, cy, r = self._trunk_cut
            if notch_removes_material(cx, cy, r, self.length, self.WIDTH):
                # The step's noun + kind + provenance come from the FEATURE that
                # produced the cut (CL-2). A legacy direct ``trunk_cut=`` keeps the
                # old trunk clearance wording, byte-identical.
                noun, step_kind, prov = (
                    self._notch_feature or ("trunk", "notch", "clearance_cut:trunk"))
                make = ProcessStep.bore if step_kind == "bore" else ProcessStep.notch
                steps.append(make(cx, cy, r, feature=noun, provenance=prov))
        return ProcessRecord(stock, tuple(steps), part_id=part_id or self.name)

    def _build(self) -> cq.Workplane:
        # Delegate to fold(stock, steps): the ProcessRecord is the single
        # authoritative source of this board's installed geometry. The steps
        # reproduce exactly the box -> ease -> notch sequence, so the folded
        # solid is byte-identical to the former inline build.
        return self.fabrication_record().installed_geometry()

    def _datums(self) -> dict[str, Frame]:
        L, w, t = self.length, self.WIDTH, self.THICKNESS
        return {
            "base": Frame.from_origin_axes((L / 2, w / 2, 0), (1, 0, 0), (0, 0, 1)),
            "top": Frame.from_origin_axes((L / 2, w / 2, t), (1, 0, 0), (0, 0, 1)),
            "end_near": Frame.from_origin_axes((0, w / 2, t / 2), (0, 0, 1), (-1, 0, 0)),
            "end_far": Frame.from_origin_axes((L, w / 2, t / 2), (0, 0, 1), (1, 0, 0)),
        }

    def describe(self) -> str:
        return f'5/4x6 decking x {fmt_in(self.length, 1)}'

    def assumptions(self) -> str:
        return ("5/4 decking dresses to 1\" x 5.5\"; modeled butt-tight, "
                "field-install with ~1/8\" gaps. Long edges eased.")

    def bom_group(self) -> str:
        return f"DeckBoard|{round(self.length,1)}"

    def bom_label(self) -> str:
        return "PT 5/4x6 decking"

    def bom_length_mm(self) -> float | None:
        # Single-source (retro R28): the cut length is the crosscut step's
        # to_length_mm in this board's ProcessRecord — the SAME record the notch
        # and the installed solid derive from — so the BOM cannot report a length
        # the geometry does not carry. A thin reader, never an independent
        # declaration of self.length.
        return self.fabrication_record().crosscut_length()
