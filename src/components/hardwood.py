"""Indoor hardwood furniture panels and wooden corner-key dowels.

Both parts use explicit furniture vocabulary instead of pretending that indoor
hardwood is SPF dimensional lumber or pressure-treated decking.
"""

from __future__ import annotations

import cadquery as cq

from ..core.base import Component
from ..core.frame import Frame
from ..core.registry import register_component
from ._geometry import axis_cylinder
from .panel import FabricatedPanel, _fraction_inches


@register_component("hardwood_panel")
class HardwoodPanel(FabricatedPanel):
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
        super().__init__(
            length,
            width,
            thickness,
            material_key="hardwood",
            stock_label="hardwood",
            material_assumptions=(
                "Solid indoor hardwood panel; species and grade are selected "
                "for appearance and workability but are not analyzed "
                "structurally."
            ),
            miter_ends=miter_ends,
            ease_radius=ease_radius,
            name=name,
        )

    def bom_group(self) -> str:
        feature_cut = (
            self._feature_cuts[-1][:3] if self._feature_cuts else None
        )
        if len(self._feature_cuts) > 1:
            feature_cut = tuple(self._feature_cuts)
        return (
            f"HardwoodPanel|{round(self.thickness, 3)}|"
            f"{round(self.width, 3)}|{round(self.length, 3)}|"
            f"{self.miter_ends!r}|{feature_cut!r}"
        )


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
