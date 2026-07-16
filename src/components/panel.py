"""Material-parameterized solid panels with fabrication-record geometry."""

from __future__ import annotations

from fractions import Fraction

import cadquery as cq

from ..core.base import Component
from ..core.frame import Frame
from ..core.materials import MATERIALS
from ..core.registry import register_component
from ..core.units import inches


def _fraction_inches(value_mm: float) -> str:
    value = Fraction(inches(value_mm)).limit_denominator(16)
    whole, remainder = divmod(value.numerator, value.denominator)
    if not remainder:
        return str(whole)
    fraction = f"{remainder}/{value.denominator}"
    return f"{whole} {fraction}" if whole else fraction


@register_component("fabricated_panel")
class FabricatedPanel(Component):
    """A solid panel whose material identity and fabrication are data."""

    def __init__(
        self,
        length: float,
        width: float,
        thickness: float,
        material_key: str,
        stock_label: str | None = None,
        material_assumptions: str | None = None,
        miter_ends=(),
        ease_radius: float = 0.0,
        name: str = "fabricated panel",
    ):
        if material_key not in MATERIALS:
            raise ValueError(
                f"unknown panel material {material_key!r}; "
                f"known materials: {sorted(MATERIALS)}"
            )
        normalized_miters = tuple(str(end) for end in miter_ends)
        unknown_miters = set(normalized_miters) - {"near", "far"}
        if unknown_miters:
            raise ValueError(
                "fabricated panel miter_ends must contain only 'near' or "
                f"'far'; got {sorted(unknown_miters)}"
            )
        super().__init__(name)
        self.length = float(length)
        self.width = float(width)
        self.thickness = float(thickness)
        self.material_key = str(material_key)
        self.stock_label = (
            str(stock_label)
            if stock_label is not None
            else self.material_key.replace("_", " ")
        )
        self.material_assumptions = (
            str(material_assumptions)
            if material_assumptions is not None
            else None
        )
        self.miter_ends = normalized_miters
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
        step_kind = str(step_kind)
        if step_kind not in {"bore", "notch"}:
            raise ValueError(
                "fabricated panel feature step_kind must be 'bore' or "
                f"'notch'; got {step_kind!r}"
            )
        self._feature_cuts.append(
            (
                float(cx),
                float(cy),
                float(radius),
                str(noun),
                step_kind,
                str(provenance),
            )
        )

    def cache_key(self) -> tuple:
        return super().cache_key() + (("feature_cuts", repr(self._feature_cuts)),)

    def fabrication_record(self, part_id: str = ""):
        from ..core.process_graph import ProcessRecord, ProcessStep, StockRef

        profile = (
            f"{_fraction_inches(self.thickness)} in {self.stock_label} panel, "
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
            f"{_fraction_inches(self.thickness)} in {self.stock_label}, "
            f"{_fraction_inches(self.length)} x "
            f"{_fraction_inches(self.width)} in"
        )

    def assumptions(self) -> str:
        if self.material_assumptions is not None:
            return self.material_assumptions
        return (
            f"{self.material.name} fabricated panel; grade, moisture condition, "
            "finish, and structural capacity are not analyzed."
        )

    def bom_group(self) -> str:
        return (
            f"FabricatedPanel|{self.material_key}|{self.stock_label}|"
            f"{round(self.thickness, 3)}|{round(self.width, 3)}|"
            f"{round(self.length, 3)}|{self.miter_ends!r}|"
            f"{self.ease_radius!r}|{self._feature_cuts!r}"
        )

    def bom_label(self) -> str:
        return f"{_fraction_inches(self.thickness)} in {self.stock_label} panel"

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
