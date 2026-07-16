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
import re

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


_STEP_TIMESTAMP_RE = re.compile(
    r"(FILE_NAME\([^,]+,)'[^']*'",
)
_STEP_OCCURRENCE_RE = re.compile(
    r"(NEXT_ASSEMBLY_USAGE_OCCURRENCE\(')[^']*(')",
)
_STEP_PRESENTATION_START_RE = re.compile(
    r"(?m)^#(\d+)\s*=\s*"
    r"MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION",
)
_STEP_ENTITY_RE = re.compile(
    r"(?ms)^#(\d+)\s*=\s*(.*?);\s*(?=^#|^ENDSEC;)",
)


def _compact_step_whitespace(text: str) -> str:
    """Remove layout-only whitespace while preserving quoted STEP strings."""
    out = []
    in_string = False
    index = 0
    while index < len(text):
        char = text[index]
        if char == "'":
            out.append(char)
            if in_string and index + 1 < len(text) and text[index + 1] == "'":
                out.append("'")
                index += 2
                continue
            in_string = not in_string
        elif not in_string and char.isspace():
            index += 1
            continue
        else:
            out.append(char)
        index += 1
    if in_string:
        raise RuntimeError("STEP export contains an unterminated quoted string")
    return "".join(out) + "\n"


def _canonical_step_text(text: str) -> str:
    """Remove OCCT process noise while preserving STEP names and colors.

    OCCT stamps wall time and process-global occurrence ordinals into STEP,
    then emits the final color-presentation records in pointer-dependent order.
    Geometry and product records are already stable. Normalize the two metadata
    fields and rebuild only the presentation tail, ordered by its stable
    representation/shape references with one explicit RGB record per item.
    """
    text, timestamp_count = _STEP_TIMESTAMP_RE.subn(
        r"\1'1970-01-01T00:00:00'",
        text,
        count=1,
    )
    if timestamp_count != 1:
        raise RuntimeError("STEP export lacks the expected FILE_NAME timestamp")

    occurrence = 0

    def normalize_occurrence(match: re.Match) -> str:
        nonlocal occurrence
        occurrence += 1
        return f"{match.group(1)}{occurrence}{match.group(2)}"

    text = _STEP_OCCURRENCE_RE.sub(normalize_occurrence, text)

    start_match = _STEP_PRESENTATION_START_RE.search(text)
    if start_match is None:
        return _compact_step_whitespace(text)
    start = start_match.start()
    end = text.index("ENDSEC;", start)
    tail = text[start:end]
    entities = {
        int(ident): body.strip()
        for ident, body in _STEP_ENTITY_RE.findall(tail + "ENDSEC;")
    }
    presentation_ids = sorted(
        ident for ident, body in entities.items()
        if body.startswith(
            "MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION"
        )
    )
    if not presentation_ids:
        return _compact_step_whitespace(text)

    supported_prefixes = (
        "MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION",
        "STYLED_ITEM",
        "PRESENTATION_STYLE_ASSIGNMENT",
        "SURFACE_STYLE_USAGE",
        "SURFACE_SIDE_STYLE",
        "SURFACE_STYLE_FILL_AREA",
        "FILL_AREA_STYLE",
        "FILL_AREA_STYLE_COLOUR",
        "COLOUR_RGB",
        "SURFACE_STYLE_RENDERING_WITH_PROPERTIES",
        "SURFACE_STYLE_TRANSPARENT",
    )
    if not all(body.startswith(supported_prefixes) for body in entities.values()):
        raise RuntimeError("STEP presentation tail contains an unsupported entity")

    rows = []
    used = set()
    for presentation_id in presentation_ids:
        presentation = entities[presentation_id]
        refs = [int(value) for value in re.findall(r"#(\d+)", presentation)]
        if len(refs) < 2:
            raise RuntimeError("STEP presentation record has no styled item")
        styled_ids, context_id = refs[:-1], refs[-1]
        used.add(presentation_id)

        for styled_id in styled_ids:
            styled = entities[styled_id]
            styled_refs = [int(value) for value in re.findall(r"#(\d+)", styled)]
            if not styled.startswith("STYLED_ITEM") or len(styled_refs) != 2:
                raise RuntimeError("STEP styled item is not unary")
            assignment_id, target_id = styled_refs

            assignment = entities[assignment_id]
            assignment_refs = [
                int(value) for value in re.findall(r"#(\d+)", assignment)
            ]
            if (not assignment.startswith("PRESENTATION_STYLE_ASSIGNMENT")
                    or len(assignment_refs) != 1):
                raise RuntimeError("STEP style assignment is not unary")
            usage_id = assignment_refs[0]

            usage = entities[usage_id]
            usage_refs = [int(value) for value in re.findall(r"#(\d+)", usage)]
            if not usage.startswith("SURFACE_STYLE_USAGE") or len(usage_refs) != 1:
                raise RuntimeError("STEP surface style usage is not unary")
            side_id = usage_refs[0]

            side = entities[side_id]
            side_refs = [int(value) for value in re.findall(r"#(\d+)", side)]
            if not side.startswith("SURFACE_SIDE_STYLE") or not side_refs:
                raise RuntimeError("STEP surface side style has no fill")
            fill_id, *render_ids = side_refs
            if len(render_ids) > 1:
                raise RuntimeError("STEP surface side style has multiple renderers")

            fill = entities[fill_id]
            fill_refs = [int(value) for value in re.findall(r"#(\d+)", fill)]
            if not fill.startswith("SURFACE_STYLE_FILL_AREA") or len(fill_refs) != 1:
                raise RuntimeError("STEP surface fill style is not unary")
            area_id = fill_refs[0]

            area = entities[area_id]
            area_refs = [int(value) for value in re.findall(r"#(\d+)", area)]
            if not area.startswith("FILL_AREA_STYLE") or len(area_refs) != 1:
                raise RuntimeError("STEP fill area style is not unary")
            area_color_id = area_refs[0]

            area_color = entities[area_color_id]
            color_refs = [
                int(value) for value in re.findall(r"#(\d+)", area_color)
            ]
            if (not area_color.startswith("FILL_AREA_STYLE_COLOUR")
                    or len(color_refs) != 1):
                raise RuntimeError("STEP fill color is not unary")
            color_id = color_refs[0]
            color_body = entities[color_id]
            if not color_body.startswith("COLOUR_RGB"):
                raise RuntimeError("STEP presentation chain does not end in RGB")

            render_mode = None
            transparency_body = None
            extra_ids = []
            if render_ids:
                render_id = render_ids[0]
                render = entities[render_id]
                render_refs = [
                    int(value) for value in re.findall(r"#(\d+)", render)
                ]
                mode = re.match(
                    r"SURFACE_STYLE_RENDERING_WITH_PROPERTIES\(([^,]+),",
                    render,
                )
                if (mode is None or len(render_refs) != 2
                        or render_refs[0] != color_id):
                    raise RuntimeError("STEP transparent rendering is unsupported")
                transparency_id = render_refs[1]
                transparency_body = entities[transparency_id]
                if not transparency_body.startswith("SURFACE_STYLE_TRANSPARENT"):
                    raise RuntimeError("STEP renderer lacks transparency")
                render_mode = mode.group(1)
                extra_ids.extend((render_id, transparency_id))

            used.update((
                styled_id,
                assignment_id,
                usage_id,
                side_id,
                fill_id,
                area_id,
                area_color_id,
                color_id,
                *extra_ids,
            ))
            rows.append((
                context_id,
                target_id,
                color_body,
                render_mode,
                transparency_body,
            ))

    if used != set(entities):
        raise RuntimeError("STEP presentation tail contains unreferenced entities")

    next_id = min(entities)
    canonical = []
    for context_id, target_id, color_body, render_mode, transparency in sorted(
        rows,
        key=lambda row: (row[0], row[1], row[2], row[3] or "", row[4] or ""),
    ):
        count = 11 if transparency is not None else 9
        ids = tuple(range(next_id, next_id + count))
        next_id += count
        side_refs = f"#{ids[5]}" + (f",#{ids[9]}" if transparency else "")
        canonical.extend((
            f"#{ids[0]} = MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',(#{ids[1]}),#{context_id});",
            f"#{ids[1]} = STYLED_ITEM('color',(#{ids[2]}),#{target_id});",
            f"#{ids[2]} = PRESENTATION_STYLE_ASSIGNMENT((#{ids[3]}));",
            f"#{ids[3]} = SURFACE_STYLE_USAGE(.BOTH.,#{ids[4]});",
            f"#{ids[4]} = SURFACE_SIDE_STYLE('',({side_refs}));",
            f"#{ids[5]} = SURFACE_STYLE_FILL_AREA(#{ids[6]});",
            f"#{ids[6]} = FILL_AREA_STYLE('',(#{ids[7]}));",
            f"#{ids[7]} = FILL_AREA_STYLE_COLOUR('',#{ids[8]});",
            f"#{ids[8]} = {color_body};",
        ))
        if transparency is not None:
            canonical.extend((
                f"#{ids[9]} = SURFACE_STYLE_RENDERING_WITH_PROPERTIES({render_mode},#{ids[8]},(#{ids[10]}));",
                f"#{ids[10]} = {transparency};",
            ))
    return _compact_step_whitespace(
        text[:start] + "\n".join(canonical) + "\n" + text[end:]
    )


@register_exporter("step")
def export_step(assembly: DetailAssembly, path: str | Path | None = None) -> Path:
    """STEP with per-part names and colors (the CAD interchange artifact)."""
    p = _out_path(assembly, ".step", path)
    assembly.to_cq_assembly().export(str(p))
    p.write_text(_canonical_step_text(p.read_text()), encoding="utf-8")
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
