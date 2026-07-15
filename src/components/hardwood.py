"""Indoor hardwood furniture panels and wooden corner-key dowels.

Both parts use explicit furniture vocabulary instead of pretending that indoor
hardwood is SPF dimensional lumber or pressure-treated decking.
"""

from __future__ import annotations

from fractions import Fraction

import cadquery as cq

from ..core.base import Component
from ..core.frame import Frame
from ..core.registry import register_component
from ..core.units import inches
from ._geometry import axis_cylinder


def _fraction_inches(value_mm: float) -> str:
    value = Fraction(inches(value_mm)).limit_denominator(16)
    whole, remainder = divmod(value.numerator, value.denominator)
    if not remainder:
        return str(whole)
    fraction = f"{remainder}/{value.denominator}"
    return f"{whole} {fraction}" if whole else fraction


@register_component("hardwood_panel")
class HardwoodPanel(Component):
    """A solid indoor-hardwood panel laid flat in local X/Y/Z."""

    material_key = "hardwood"

    def __init__(
        self,
        length: float,
        width: float,
        thickness: float,
        miter_ends=(),
        ease_radius: float = 0.0,
        name: str = "hardwood panel",
    ):
        super().__init__(name)
        self.length = float(length)
        self.width = float(width)
        self.thickness = float(thickness)
        self.miter_ends = tuple(str(end) for end in miter_ends)
        self.ease_radius = float(ease_radius)
        self._feature_cut: tuple[float, float, float] | None = None
        self._feature: tuple[str, str, str] | None = None

    @property
    def WIDTH(self) -> float:
        """Board-like feature compatibility for the current compiler surface."""
        return self.width

    def apply_feature_cut(
        self,
        cx: float,
        cy: float,
        radius: float,
        *,
        noun: str,
        step_kind: str,
        provenance: str,
    ) -> None:
        self._feature_cut = (float(cx), float(cy), float(radius))
        self._feature = (str(noun), str(step_kind), str(provenance))

    def cache_key(self) -> tuple:
        return super().cache_key() + (
            ("feature_cut", repr(self._feature_cut)),
            ("feature", repr(self._feature)),
        )

    def fabrication_record(self, part_id: str = ""):
        from ..core.process_graph import ProcessRecord, ProcessStep, StockRef

        profile = (
            f"{_fraction_inches(self.thickness)} in hardwood panel, "
            f"{_fraction_inches(self.width)} in wide"
        )
        stock = StockRef(
            profile=profile,
            form="linear_stick",
            section=(self.width, self.thickness),
            material_key=self.material_key,
        )
        steps = [ProcessStep.crosscut(self.length, provenance="finished-length")]
        if self.ease_radius > 0:
            steps.append(
                ProcessStep.ease(
                    self.ease_radius,
                    provenance="ease_radius",
                    edges="|X",
                )
            )
        for end in self.miter_ends:
            steps.append(
                ProcessStep.miter_crosscut(
                    end,
                    angle_degrees=45.0,
                    long_face="top",
                    provenance=f"miter_ends:{end}",
                )
            )
        if self._feature_cut is not None:
            cx, cy, radius = self._feature_cut
            noun, step_kind, provenance = self._feature or (
                "",
                "bore",
                "feature",
            )
            make_step = (
                ProcessStep.bore if step_kind == "bore" else ProcessStep.notch
            )
            steps.append(
                make_step(
                    cx,
                    cy,
                    radius,
                    feature=noun,
                    provenance=provenance,
                )
            )
        return ProcessRecord(stock, tuple(steps), part_id=part_id or self.name)

    def _build(self) -> cq.Workplane:
        return self.fabrication_record().installed_geometry()

    def _datums(self) -> dict[str, Frame]:
        length, width, thickness = self.length, self.width, self.thickness
        return {
            "base": Frame.from_origin_axes(
                (length / 2, width / 2, 0), (1, 0, 0), (0, 0, 1)
            ),
            "top": Frame.from_origin_axes(
                (length / 2, width / 2, thickness), (1, 0, 0), (0, 0, 1)
            ),
            "end_near": Frame.from_origin_axes(
                (0, width / 2, thickness / 2), (0, 0, 1), (-1, 0, 0)
            ),
            "end_far": Frame.from_origin_axes(
                (length, width / 2, thickness / 2), (0, 0, 1), (1, 0, 0)
            ),
        }

    def describe(self) -> str:
        return (
            f"{_fraction_inches(self.thickness)} in hardwood, "
            f"{_fraction_inches(self.length)} x "
            f"{_fraction_inches(self.width)} in"
        )

    def assumptions(self) -> str:
        return (
            "Solid indoor hardwood panel; species and grade are selected for "
            "appearance and workability but are not analyzed structurally."
        )

    def bom_group(self) -> str:
        return (
            f"HardwoodPanel|{round(self.thickness, 3)}|"
            f"{round(self.width, 3)}|{round(self.length, 3)}|"
            f"{self.miter_ends!r}|{self._feature_cut!r}"
        )

    def bom_label(self) -> str:
        return f"{_fraction_inches(self.thickness)} in hardwood panel"

    def bom_length_mm(self) -> float | None:
        return self.fabrication_record().crosscut_length()

    def check(self) -> list[str]:
        problems = super().check()
        for label, value in (
            ("length", self.length),
            ("width", self.width),
            ("thickness", self.thickness),
        ):
            if value <= 0:
                problems.append(f"{self.name}: non-positive {label}")
        return problems


@register_component("wood_dowel")
class WoodDowel(Component):
    """A finished flush hardwood dowel pin with its axis along local +X."""

    material_key = "hardwood"

    def __init__(
        self,
        diameter: float,
        length: float,
        name: str = "hardwood dowel",
        end_trim: str = "square",
    ):
        super().__init__(name)
        self.diameter = float(diameter)
        self.length = float(length)
        self.end_trim = str(end_trim)
        if self.end_trim not in {"square", "miter_flush"}:
            raise ValueError(
                "wood dowel end_trim must be 'square' or 'miter_flush'; "
                f"got {self.end_trim!r}"
            )

    def _build(self) -> cq.Workplane:
        radius = self.diameter / 2
        cylinder = axis_cylinder(
            radius, self.length, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)
        )
        if self.end_trim == "square":
            return cylinder

        # The nominal axis runs from the top-face center to the side-face
        # center. Stock extends beyond both centers before two 45-degree
        # face-plane trims are made; otherwise square cylinder ends protrude.
        # In local X/Z the retained half-spaces are z <= x and z <= L - x.
        # After placement those are the horizontal top and vertical side faces,
        # exposing two oval plugs while staying inside the panel union.
        extended = axis_cylinder(
            radius,
            self.length + 4 * radius,
            (-2 * radius, 0.0, 0.0),
            (1.0, 0.0, 0.0),
        )
        half = self.length / 2
        margin = self.length + 2 * radius
        envelope = (
            cq.Workplane("XZ")
            .polyline(((-margin, -margin), (half, half),
                       (self.length + margin, -margin)))
            .close()
            .extrude(self.diameter + 2.0, both=True)
        )
        return extended.intersect(envelope)

    def _datums(self) -> dict[str, Frame]:
        return {
            "axis": Frame.from_origin_axes(
                (self.length / 2, 0, 0), (0, 1, 0), (1, 0, 0)
            ),
            "end_near": Frame.from_origin_axes(
                (0, 0, 0), (0, 1, 0), (-1, 0, 0)
            ),
            "end_far": Frame.from_origin_axes(
                (self.length, 0, 0), (0, 1, 0), (1, 0, 0)
            ),
        }

    def describe(self) -> str:
        return (
            f"{_fraction_inches(self.diameter)} in hardwood dowel x "
            f"{_fraction_inches(self.length)} in finished"
        )

    def assumptions(self) -> str:
        if self.end_trim == "miter_flush":
            return (
                "Modeled with skew end trims flush to the two outside faces of "
                "a 45-degree miter; install from dowel rod with glue, then trim "
                "and sand both exposed ends flush."
            )
        return (
            "Modeled at its finished square-cut length; install from dowel rod "
            "with glue and finish the exposed ends as specified."
        )

    def bom_group(self) -> str:
        return (
            f"WoodDowel|{round(self.diameter, 3)}|{round(self.length, 3)}|"
            f"{self.end_trim}"
        )

    def bom_label(self) -> str:
        return f"{_fraction_inches(self.diameter)} in hardwood dowel"

    def bom_length_mm(self) -> float | None:
        return self.length

    def check(self) -> list[str]:
        problems = super().check()
        if self.diameter <= 0:
            problems.append(f"{self.name}: non-positive diameter")
        if self.length <= 0:
            problems.append(f"{self.name}: non-positive length")
        return problems
