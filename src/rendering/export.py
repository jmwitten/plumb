"""Exporters: STEP (assembly with colors), STL (fused mesh), PNG (offscreen
VTK preview).

Everything takes a DetailAssembly and writes into ``outputs/`` by default:

    from detailgen.rendering import export_all
    export_all(detail)   # outputs/<slug>.step / .stl / .png

PNG rendering is offscreen (no window) via VTK, which ships with CadQuery.
Solids are tessellated per-part so each keeps its material color.
"""

from __future__ import annotations

from pathlib import Path

import cadquery as cq

from ..assemblies.assembly import DetailAssembly
from ..core.buildinfo import MESH_TOL_LINEAR, MESH_TOL_ANGULAR, build_manifest
from ..core.registry import register_exporter

#: Default output directory — resolved relative to the project root
#: (two levels up from this file: src/rendering/ -> project).
OUTPUTS_DIR = Path(__file__).resolve().parents[2] / "outputs"

#: Named camera directions for PNG previews (position offsets, unit-ish).
VIEWS: dict[str, tuple[float, float, float]] = {
    "iso": (1.0, -1.0, 0.6),       # camera front-right-above (from -Y)
    "iso_back": (1.0, 1.0, 0.6),   # camera back-right-above (from +Y)
    "front": (0.0, -1.0, 0.0),
    "back": (0.0, 1.0, 0.0),
    "right": (1.0, 0.0, 0.0),
    "top": (0.0, 0.0, 1.0),
}


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")


def _out_path(assembly: DetailAssembly, suffix: str, path: str | Path | None) -> Path:
    p = Path(path) if path else OUTPUTS_DIR / f"{_slug(assembly.name)}{suffix}"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@register_exporter("step")
def export_step(assembly: DetailAssembly, path: str | Path | None = None) -> Path:
    """STEP with per-part names and colors (the CAD interchange artifact)."""
    p = _out_path(assembly, ".step", path)
    assembly.to_cq_assembly().export(str(p))
    return p


@register_exporter("stl")
def export_stl(
    assembly: DetailAssembly,
    path: str | Path | None = None,
    tolerance: float = MESH_TOL_LINEAR,
    angular_tolerance: float = MESH_TOL_ANGULAR,
) -> Path:
    """Single fused STL mesh (3D printing / quick viewers; colors are lost)."""
    p = _out_path(assembly, ".stl", path)
    cq.exporters.export(
        cq.Workplane(obj=assembly.compound(isolated=True)), str(p),
        tolerance=tolerance, angularTolerance=angular_tolerance,
    )
    return p


@register_exporter("png")
def export_png(
    assembly: DetailAssembly,
    path: str | Path | None = None,
    view: str = "iso",
    size: tuple[int, int] = (1600, 1200),
    background: tuple[float, float, float] = (1.0, 1.0, 1.0),
    mesh_tolerance: float = MESH_TOL_LINEAR,
    mesh_angular_tolerance: float = MESH_TOL_ANGULAR,
) -> Path:
    """Offscreen PNG preview with per-part material colors.

    ``view`` is a key of VIEWS ("iso", "front", "back", "right", "top").
    """
    import vtk  # ships with cadquery; imported lazily to keep STEP/STL light

    p = _out_path(assembly, f"_{view}.png" if view != "iso" else ".png", path)

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(*background)

    for placed, world in assembly.isolated_world_solids():
        color = placed.component.material.rgba
        for solid in world.vals():
            verts, tris = solid.tessellate(mesh_tolerance, mesh_angular_tolerance)

            points = vtk.vtkPoints()
            for v in verts:
                points.InsertNextPoint(v.x, v.y, v.z)
            cells = vtk.vtkCellArray()
            for tri in tris:
                cells.InsertNextCell(3)
                for idx in tri:
                    cells.InsertCellPoint(idx)

            poly = vtk.vtkPolyData()
            poly.SetPoints(points)
            poly.SetPolys(cells)

            normals = vtk.vtkPolyDataNormals()
            normals.SetInputData(poly)

            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(normals.GetOutputPort())

            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(*color[:3])
            actor.GetProperty().SetOpacity(color[3])
            renderer.AddActor(actor)

    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(*size)
    window.AddRenderer(renderer)

    camera = renderer.GetActiveCamera()
    direction = VIEWS[view]
    camera.SetPosition(*direction)
    camera.SetFocalPoint(0, 0, 0)
    camera.SetViewUp(0, 0, 1)
    if view == "top":
        camera.SetViewUp(0, 1, 0)
    renderer.ResetCamera()
    camera.Zoom(1.1)

    window.Render()

    grabber = vtk.vtkWindowToImageFilter()
    grabber.SetInput(window)
    grabber.Update()

    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(p))
    writer.SetInputConnection(grabber.GetOutputPort())
    writer.Write()
    return p


@register_exporter("glb")
def export_glb(assembly: DetailAssembly, path: str | Path | None = None,
               tolerance: float = MESH_TOL_LINEAR,
               angular_tolerance: float = MESH_TOL_ANGULAR) -> Path:
    """glTF binary with per-part node names + colors, for Blender import.

    Node names are the part names; a photorealistic renderer reassigns
    materials by name, so colors here are only a fallback.
    """
    p = _out_path(assembly, ".glb", path)
    assembly.to_cq_assembly(isolated=True).export(
        str(p), tolerance=tolerance, angularTolerance=angular_tolerance)
    return p


@register_exporter("manifest")
def export_manifest(assembly: DetailAssembly, path: str | Path | None = None,
                    extra: dict | None = None) -> Path:
    """JSON sidecar describing each part's material tag for the Blender
    renderer, plus any extra render metadata (explode vectors, dimensions).

    Always carries a ``"build"`` key (geometry content-hashes per part + for
    the whole assembly, plus toolchain versions) — diffing that key across
    two manifests of the same detail is the geometric-regression check.

    ``extra`` must not contain a ``"build"`` key: ``data.update(extra)`` would
    silently clobber the auto-generated one, disabling that regression check
    without any error.
    """
    import json
    if extra and "build" in extra:
        raise ValueError(
            '"build" is a reserved manifest key (auto-generated geometry '
            "content-hashes) — remove it from extra"
        )
    p = _out_path(assembly, ".manifest.json", path)
    data = {
        "name": assembly.name,
        "units": "mm",
        "parts": [
            {"name": pl.name,
             "material": pl.component.material_key,
             "material_name": pl.component.material.name,
             "rgba": list(pl.component.material.rgba)}
            for pl in assembly.parts
        ],
        "build": build_manifest(assembly),
    }
    if extra:
        data.update(extra)
    p.write_text(json.dumps(data, indent=1))
    return p


def export_all(
    assembly: DetailAssembly,
    out_dir: str | Path | None = None,
    views: tuple[str, ...] = ("iso",),
) -> list[Path]:
    """STEP + STL + one PNG per requested view. Returns written paths."""
    base = Path(out_dir) if out_dir else OUTPUTS_DIR
    slug = _slug(assembly.name)
    written = [
        export_step(assembly, base / f"{slug}.step"),
        export_stl(assembly, base / f"{slug}.stl"),
    ]
    for view in views:
        written.append(export_png(assembly, base / f"{slug}_{view}.png", view=view))
    return written
