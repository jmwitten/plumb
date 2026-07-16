"""Untreated exterior cedar compatibility wrapper."""

from __future__ import annotations

from ..core.registry import register_component
from .panel import FabricatedPanel


@register_component("cedar_panel")
class CedarPanel(FabricatedPanel):
    """Compatibility surface for an untreated exterior cedar panel."""

    material_key = "cedar"

    def __init__(
        self,
        length: float,
        width: float,
        thickness: float,
        ease_radius: float = 0.0,
        name: str = "cedar panel",
    ):
        super().__init__(
            length,
            width,
            thickness,
            material_key="cedar",
            stock_label="cedar",
            material_assumptions=(
                "Solid untreated exterior cedar panel; species, grade, "
                "weathering, and structural capacity are not analyzed."
            ),
            ease_radius=ease_radius,
            name=name,
        )

    def bom_group(self) -> str:
        return (
            f"CedarPanel|{round(self.thickness, 3)}|"
            f"{round(self.width, 3)}|{round(self.length, 3)}|"
            f"{self._feature_cuts!r}"
        )
