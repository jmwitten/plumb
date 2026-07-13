"""Sheet-goods panels (plywood).

Vocabulary added for the sit-and-reach box (task SITREACH): the box is the
prior-art standard 3/4" plywood five-panel construction, and no existing
component could say "a plywood panel" honestly — ``lumber`` claims an SPF
dressed nominal (PS 20) the panel is not, and there is no sheet component at
all. Model vocabulary is a normal implementation task (vocabulary-gap
directive, route-by-class), so the word is added here rather than faking a
nominal.

HONEST LIMIT (disclosed, a recorded work order — not a bug): the fabrication
vocabulary has no ``rip`` step and no sheet-stock form, so a panel's
ProcessRecord starts from a RIPPED STRIP of the panel's width (the stock
profile says exactly that) and carries the one crosscut to length. The
sheet-level nesting story — which panels come out of which 24x48 project
panel, and the rip sequence — is NOT derived; the owning detail must disclose
it as a modeling assumption. When a ``rip``/sheet-form vocabulary lands, this
component's record grows the real sheet -> strip -> panel chain and the
disclosure retires.

Local frame (datum)
-------------------
A panel is modeled LAID FLAT, matching ``fold``'s stock box and DeckBoard:

    X: 0 .. length      (the cut run — the crosscut dimension)
    Y: 0 .. width       (the ripped-strip width)
    Z: 0 .. thickness   (sheet thickness, wide face up)

origin at a bottom corner. Assemblies rotate it upright as needed; the
component never bakes in an installed orientation.
"""

from __future__ import annotations

import cadquery as cq

from ..core.base import Component
from ..core.frame import Frame
from ..core.registry import register_component
from ..core.units import IN, fmt_in

#: Common retail sheet/project-panel sizes (mm), largest rip-able width first.
#: ``check()`` warns when a panel cannot come out of the largest stocked sheet.
SHEET_MAX_LENGTH = 96 * IN
SHEET_MAX_WIDTH = 48 * IN


@register_component("plywood_panel")
class PlywoodPanel(Component):
    """A rectangular plywood panel cut from sheet stock.

    Parameters
    ----------
    length:
        The crosscut run in mm (local X).
    width:
        The ripped-strip width in mm (local Y).
    thickness:
        Sheet thickness in mm (local Z) — e.g. ``0.75 * IN`` sanded ply.
    name:
        Human label used in assemblies, BOMs and validation reports.
    """

    material_key = "plywood"

    def __init__(self, length: float, width: float, thickness: float,
                 grooves=(), name: str = "plywood panel"):
        super().__init__(name)
        self.length = float(length)
        self.width = float(width)
        self.thickness = float(thickness)
        self.grooves = tuple(
            tuple(sorted((str(key), value) for key, value in dict(groove).items()))
            for groove in grooves
        )

    # -- Component contract ----------------------------------------------------

    def fabrication_record(self, part_id: str = ""):
        """This panel's fabrication story: one crosscut to length on a ripped
        strip of the panel's width. The strip IS the stock (profile says so) —
        the rip that produced it is NOT derived (no ``rip`` vocabulary yet;
        module docstring), which keeps the record honest rather than phantom.
        The installed solid is DERIVED from this record (``process_graph.fold``),
        so the cut list and the geometry read one source and cannot disagree."""
        from ..core.process_graph import ProcessRecord, ProcessStep, StockRef

        stock = StockRef(
            profile=f'{fmt_in(self.thickness)} ply strip {fmt_in(self.width, 2)}',
            form="linear_stick",
            section=(self.width, self.thickness),
            material_key=self.material_key,
        )
        steps = [ProcessStep.crosscut(self.length, provenance="finished-length")]
        for raw in self.grooves:
            groove = dict(raw)
            steps.append(ProcessStep.groove(
                x=groove["x"], y=groove["y"], length=groove["length"],
                width=groove["width"], depth=groove["depth"],
                face=groove.get("face", "top"),
                feature=groove["feature"],
                provenance=groove.get("source", groove["feature"]),
            ))
        return ProcessRecord(stock, tuple(steps), part_id=part_id or self.name)

    def _build(self) -> cq.Workplane:
        # Delegate to fold(stock, steps): the ProcessRecord is the single
        # authoritative source of this panel's installed geometry.
        return self.fabrication_record().installed_geometry()

    def _datums(self) -> dict[str, Frame]:
        # Local frame: length +X [0..L], width +Y [0..W], thickness +Z [0..t],
        # corner origin (see module docstring). ``base`` seats down, ``top`` is
        # the upper wide face.
        L, W, t = self.length, self.width, self.thickness
        return {
            "base": Frame.from_origin_axes((L / 2, W / 2, 0), (1, 0, 0), (0, 0, 1)),
            "top": Frame.from_origin_axes((L / 2, W / 2, t), (1, 0, 0), (0, 0, 1)),
        }

    def describe(self) -> str:
        return (f'{fmt_in(self.thickness)} ply, '
                f'{fmt_in(self.length, 2)} x {fmt_in(self.width, 2)}')

    def assumptions(self) -> str:
        return ("Cut from sheet stock; the rip to strip width is not derived "
                "(no rip vocabulary) — stock is stated as the ripped strip. "
                "Edges square; ply edge grain is not face grain.")

    def bom_group(self) -> str:
        return (f"Ply|{round(self.thickness, 2)}|{round(self.width, 1)}"
                f"|{round(self.length, 1)}")

    def bom_label(self) -> str:
        # The width rides in the label: a BOM row shows qty + label + cut length,
        # and a panel is not cuttable from a length alone.
        return (f'{fmt_in(self.thickness)} plywood panel, '
                f'{fmt_in(self.width, 2)} wide')

    def bom_length_mm(self) -> float | None:
        # Single-source (retro R28): the authoritative cut length is the
        # crosscut step in this panel's ProcessRecord — the SAME record its
        # installed geometry folds from.
        return self.fabrication_record().crosscut_length()

    def check(self) -> list[str]:
        problems = super().check()
        for dim, label in ((self.length, "length"), (self.width, "width"),
                           (self.thickness, "thickness")):
            if dim <= 0:
                problems.append(f"{self.name}: non-positive {label}")
        for raw in self.grooves:
            groove = dict(raw)
            if groove.get("face", "top") not in {"top", "bottom"}:
                problems.append(f"{self.name}: groove face must be top or bottom")
            for key in ("length", "width", "depth"):
                if float(groove[key]) <= 0:
                    problems.append(f"{self.name}: groove {key} must be positive")
            if float(groove["depth"]) >= self.thickness:
                problems.append(
                    f"{self.name}: groove depth must be less than panel thickness"
                )
        if self.thickness > 1.5 * IN:
            problems.append(
                f"{self.name}: {fmt_in(self.thickness)} thick — thicker than any "
                f"stocked plywood; is this really sheet goods?")
        if min(self.length, self.width) > SHEET_MAX_WIDTH or \
                max(self.length, self.width) > SHEET_MAX_LENGTH:
            problems.append(
                f"{self.name}: {fmt_in(self.length, 1)} x {fmt_in(self.width, 1)} "
                f"cannot come out of a 4x8 sheet")
        return problems
