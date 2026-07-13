"""Drive a headless Blender (Cycles) render of a detail.

detailgen produces a GLB + a manifest (materials, explode vectors, dimension
anchors). This module writes those and shells out to Blender, which runs
``_blender_render.py`` to produce the presentation / exploded / hidden-line /
dimensioned views. Blender is optional — everything else in detailgen works
without it; this just needs a Blender install (path via ``BLENDER`` env or the
common macOS location).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from ..assemblies.assembly import DetailAssembly
from .export import export_glb, export_manifest

_SCRIPT = Path(__file__).with_name("_blender_render.py")

_DEFAULT_BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"


def blender_path() -> str:
    return os.environ.get("BLENDER", _DEFAULT_BLENDER)


def render_blender(assembly: DetailAssembly, out_dir: str | Path,
                   extra_manifest: dict | None = None,
                   modes: tuple[str, ...] = (
                       "presentation", "exploded", "hidden", "dimensioned"),
                   samples: int = 180, resolution: int = 1500,
                   gpu: bool = True) -> list[Path]:
    """Write GLB + manifest into ``out_dir`` and render the requested modes.
    Returns the rendered PNG paths (missing ones are dropped)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    glb = export_glb(assembly, out / "detail.glb")
    manifest = export_manifest(assembly, out / "detail.manifest.json",
                               extra=extra_manifest)
    cmd = [
        blender_path(), "--background", "--factory-startup",
        "--python", str(_SCRIPT), "--",
        "--glb", str(glb), "--manifest", str(manifest), "--out", str(out),
        "--modes", ",".join(modes), "--samples", str(samples),
        "--resolution", str(resolution), "--gpu", "1" if gpu else "0",
    ]
    subprocess.run(cmd, check=True)
    return [out / f"render_{m}.png" for m in modes
            if (out / f"render_{m}.png").exists()]
