from .export import (
    export_step, export_stl, export_png, export_all, export_glb, export_manifest,
)
from .overlay import draw_dimensions
from .instruction_panels import (
    InstructionManual, InstructionPanel, PlacementStation,
    build_instruction_manual, panel_part_schedule,
)
from .caddy_stations import attach_caddy_stations
from .instruction_render import (
    panel_content_key, render_instruction_images, render_instruction_panel,
)

__all__ = [
    "export_step", "export_stl", "export_png", "export_all",
    "export_glb", "export_manifest", "draw_dimensions",
    "InstructionManual", "InstructionPanel", "PlacementStation",
    "build_instruction_manual", "panel_part_schedule",
    "attach_caddy_stations", "panel_content_key",
    "render_instruction_images", "render_instruction_panel",
]

# blender rendering is optional (needs a Blender install); import lazily.
try:
    from .blender import render_blender, blender_path  # noqa: F401
    __all__ += ["render_blender", "blender_path"]
except Exception:  # pragma: no cover
    pass
