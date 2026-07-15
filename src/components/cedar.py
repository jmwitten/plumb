"""Untreated exterior cedar panels with fabrication-record feature cuts."""

from __future__ import annotations

from fractions import Fraction

import cadquery as cq

from ..core.base import Component
from ..core.frame import Frame
from ..core.registry import register_component
from ..core.units import inches


def _fraction_inches(value_mm: float) -> str:
    value = Fraction(inches(value_mm)).limit_denominator(16)
    whole, remainder = divmod(value.numerator, value.denominator)
    if not remainder:
        return str(whole)
    fraction = f"{remainder}/{value.denominator}"
    return f"{whole} {fraction}" if whole else fraction


@register_component("cedar_panel")
class CedarPanel(Component):
    """A solid untreated cedar panel laid flat in local X/Y/Z."""

    material_key = "cedar"

    def __init__(
        self,
        length: float,
        width: float,
        thickness: float,
        ease_radius: float = 0.0,
        name: str = "cedar panel",
    ):
        super().__init__(name)
        self.length = float(length)
        self.width = float(width)
        self.thickness = float(thickness)
        self.ease_radius = float(ease_radius)
        self._feature_cuts: list[
            tuple[float, float, float, str, str, str]
        ] = []

    @property
    def WIDTH(self) -> float:
        """Board-like feature compatibility for the compiler surface."""
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
        self._feature_cuts.append(
            (
                float(cx),
                float(cy),
                float(radius),
                str(noun),
                str(step_kind),
                str(provenance),
            )
        )

    def cache_key(self) -> tuple:
        return super().cache_key() + (("feature_cuts", repr(self._feature_cuts)),)

    def fabrication_record(self, part_id: str = ""):
        from ..core.process_graph import ProcessRecord, ProcessStep, StockRef

        profile = (
            f"{_fraction_inches(self.thickness)} in cedar panel, "
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
        for cx, cy, radius, noun, step_kind, provenance in self._feature_cuts:
            make_step = ProcessStep.bore if step_kind == "bore" else ProcessStep.notch
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
            f"{_fraction_inches(self.thickness)} in cedar, "
            f"{_fraction_inches(self.length)} x "
            f"{_fraction_inches(self.width)} in"
        )

    def assumptions(self) -> str:
        return (
            "Solid untreated exterior cedar panel; species, grade, weathering, "
            "and structural capacity are not analyzed."
        )

    def bom_group(self) -> str:
        return (
            f"CedarPanel|{round(self.thickness, 3)}|"
            f"{round(self.width, 3)}|{round(self.length, 3)}|"
            f"{self._feature_cuts!r}"
        )

    def bom_label(self) -> str:
        return f"{_fraction_inches(self.thickness)} in cedar panel"

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

