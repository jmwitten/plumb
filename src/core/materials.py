"""Materials: render color + metadata shared by all components.

A Material carries no geometry — it drives assembly coloring (PNG previews,
STEP part colors) and shows up in bills of materials. Add new materials by
registering them below (``@register_material("key")`` or the ``_material``
helper) rather than hardcoding colors in components.
"""

from dataclasses import dataclass

from .registry import materials as _materials_registry


@dataclass(frozen=True)
class Material:
    name: str
    #: RGB in 0-1 floats, used for cq.Color in assemblies and VTK previews.
    color: tuple[float, float, float]
    #: Opacity 0-1 (concrete slightly transparent reads better in details).
    alpha: float = 1.0

    @property
    def rgba(self) -> tuple[float, float, float, float]:
        return (*self.color, self.alpha)


def _material(key: str, name: str, color: tuple[float, float, float],
              alpha: float = 1.0) -> Material:
    """Build one ``Material`` and register it under ``key`` (roadmap item
    8's material registry) in the same step — the registry is the source
    of truth; ``MATERIALS`` below is a plain-dict view built from it for
    every existing ``MATERIALS[key]`` call site, so this conversion changes
    no public behavior."""
    mat = Material(name, color, alpha)
    _materials_registry.register(key)(mat)
    return mat


MATERIALS: dict[str, Material] = {
    "lumber_pt": _material("lumber_pt", "Pressure-treated lumber", (0.55, 0.45, 0.25)),
    "lumber_spf": _material("lumber_spf", "SPF lumber", (0.82, 0.68, 0.45)),
    "hardwood": _material("hardwood", "Indoor hardwood", (0.54, 0.32, 0.16)),
    "plywood": _material("plywood", "Sanded plywood", (0.87, 0.76, 0.55)),
    "concrete": _material("concrete", "Concrete", (0.62, 0.62, 0.60), alpha=0.95),
    "steel_galv": _material("steel_galv", "Galvanized steel", (0.65, 0.68, 0.72)),
    "steel_zinc": _material("steel_zinc", "Zinc-plated steel", (0.75, 0.77, 0.80)),
    "stainless": _material("stainless", "Stainless steel", (0.80, 0.82, 0.85)),
    "rock": _material("rock", "Natural stone", (0.60, 0.61, 0.62)),
    "epoxy": _material("epoxy", "Anchoring epoxy", (0.80, 0.45, 0.20)),
}
