"""Content keys and image rendering for grouped instruction panels."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import tempfile

from ..core.buildinfo import build_manifest
from ..core.buildinfo import MESH_TOL_ANGULAR, MESH_TOL_LINEAR
from ..details.base import fmt_frac_in
from .part_labels import part_labels


RENDERER_VERSION = "instruction-panel-v2"
DEFAULT_SIZE = (1500, 1100)

CALLOUT_INK = (17, 24, 39)
DIMENSION_BLUE = (37, 99, 235)


@dataclass(frozen=True)
class InstructionStyle:
    """Typed scene palette for one instruction rendering register."""

    name: str
    use_material_color: bool     # current work keeps material color
    work_color: tuple[float, float, float]   # used when not material color
    prior_color: tuple[float, float, float]
    prior_opacity: float
    edge_visibility: bool
    edge_color: tuple[float, float, float]
    edge_width: float


_STYLES = {
    # The established technical register: material-colored work over a
    # translucent ghost. Byte-stable with the pre-style renderer.
    "technical": InstructionStyle(
        name="technical",
        use_material_color=True,
        work_color=(0.0, 0.0, 0.0),
        prior_color=(0.72, 0.72, 0.72),
        prior_opacity=0.16,
        edge_visibility=False,
        edge_color=(0.0, 0.0, 0.0),
        edge_width=1.0,
    ),
    # Consumer manual register: current work a readable mid gray under
    # black feature edges, prior assembly near-white, grayscale-print
    # legible. (Owner feedback: near-black fills hid grooves and notches.)
    "high_contrast": InstructionStyle(
        name="high_contrast",
        use_material_color=False,
        work_color=(0.44, 0.45, 0.47),
        prior_color=(0.93, 0.93, 0.93),
        prior_opacity=1.0,
        edge_visibility=True,
        edge_color=(0.0, 0.0, 0.0),
        edge_width=1.6,
    ),
}


def instruction_style(name: str) -> InstructionStyle:
    """Resolve a named instruction rendering style."""
    style = _STYLES.get(name)
    if style is None:
        raise ValueError(
            f"unknown instruction style {name!r}; known: "
            f"{sorted(_STYLES)}")
    return style


def panel_callout_ids(detail, panel) -> tuple[str, ...]:
    """One representative per reader part family, preserving source order."""
    candidates = panel.arrival_part_ids or panel.focus_part_ids
    labels = part_labels(detail.assembly.parts)
    seen = set()
    result = []
    for part_id in candidates:
        family = labels[part_id].reader_name
        if family in seen:
            continue
        seen.add(family)
        result.append(part_id)
    return tuple(result)


def panel_camera(panel) -> tuple[float, float, float]:
    """Stable camera region selected by semantic action family."""
    if panel.action == "prepare":
        return (1.0, 1.0, 0.75)
    if panel.action in {"bond", "cure", "fasten"}:
        return (1.0, -1.0, -0.35)
    return (1.0, -1.0, 0.6)


def _station_payload(station) -> dict:
    return {
        "feature": station.feature,
        "reference_part_id": station.reference_part_id,
        "near_mm": station.near_mm,
        "far_mm": station.far_mm,
        "reference_length_mm": station.reference_length_mm,
        "datum": station.datum,
        "p0": station.p0,
        "p1": station.p1,
        "secondary_mm": station.secondary_mm,
        "secondary_datum": station.secondary_datum,
        "q0": station.q0,
        "q1": station.q1,
        "mirror_p0": station.mirror_p0,
        "mirror_p1": station.mirror_p1,
    }


def panel_content_key(
    detail,
    panel,
    renderer_version: str = RENDERER_VERSION,
    size: tuple[int, int] = DEFAULT_SIZE,
    *,
    style: str = "technical",
    callouts: bool = True,
    callout_numbers=None,
) -> str:
    """Hash only image-relevant geometry, order, camera, and station inputs."""
    instruction_style(style)
    manifest = build_manifest(detail.assembly)
    geometry_by_id = {
        part.id: row["geometry_hash"]
        for part, row in zip(detail.assembly.parts, manifest["parts"])
    }
    image_part_ids = tuple(dict.fromkeys((
        *panel.visible_part_ids,
        *panel.arrival_part_ids,
        *panel.focus_part_ids,
    )))
    payload = {
        "renderer_version": renderer_version,
        "part_geometry": tuple(
            (part_id, geometry_by_id[part_id]) for part_id in image_part_ids),
        "source_events": panel.source_events,
        "reader_steps": panel.reader_step_indexes,
        "visible_part_ids": panel.visible_part_ids,
        "arrival_part_ids": panel.arrival_part_ids,
        "focus_part_ids": panel.focus_part_ids,
        "camera": panel_camera(panel),
        "size": size,
        "callouts": panel_callout_ids(detail, panel),
        "stations": tuple(_station_payload(value) for value in panel.stations),
    }
    # The established technical register predates styles; leaving it out of
    # the payload keeps every existing content key (and cached PNG) stable.
    if style != "technical":
        payload["style"] = style
        # Bumped when a non-default style's scene composition changes
        # (e.g. feature-edge outlines, palette revisions); the technical
        # register keeps its pre-style keys and cached renders.
        payload["style_impl"] = 3
    if not callouts:
        payload["callouts_drawn"] = False
    if callout_numbers:
        payload["callout_numbers"] = tuple(sorted(callout_numbers.items()))
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _part_centers(detail) -> dict[str, tuple[float, float, float]]:
    centers = {}
    for part in detail.assembly.parts:
        bb = part.world_solid().val().BoundingBox()
        centers[part.id] = (
            (bb.xmin + bb.xmax) / 2,
            (bb.ymin + bb.ymax) / 2,
            (bb.zmin + bb.zmax) / 2,
        )
    return centers


def _font(size: int):
    from PIL import ImageFont

    candidates = (
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _project(renderer, vtk, point, height: int) -> tuple[int, int]:
    coord = vtk.vtkCoordinate()
    coord.SetCoordinateSystemToWorld()
    coord.SetValue(*point)
    x, y = coord.GetComputedDisplayValue(renderer)
    return int(x), int(height - y)


def _fmt_dimension(mm: float) -> str:
    inches = mm / 25.4
    sixteenths = round(inches * 16)
    if abs(inches - sixteenths / 16) < 1e-6:
        return fmt_frac_in(inches)
    return f'{inches:.2f}"'


def _stations_for_overlay(panel) -> tuple[tuple, tuple]:
    """Return every station that must be marked and dimensioned in the image."""
    dimensions = tuple(panel.stations)
    markers = dimensions if panel.action in ("bond", "fasten") else ()
    return markers, dimensions


def _is_valid_cached_panel(
    path: Path,
    *,
    key: str,
    size: tuple[int, int],
) -> bool:
    """Accept only a complete overlaid PNG for this exact render request."""
    from PIL import Image

    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            return (
                image.size == size
                and image.info.get("detailgen_panel_key") == key
            )
    except (OSError, ValueError):
        return False


def _draw_overlay(
    path: Path,
    *,
    detail,
    panel,
    renderer,
    vtk,
    size: tuple[int, int],
    key: str,
    callouts: bool = True,
    callout_numbers=None,
) -> None:
    from PIL import Image, ImageDraw
    from PIL.PngImagePlugin import PngInfo

    centers = _part_centers(detail)
    labels = part_labels(detail.assembly.parts)
    callout_ids = panel_callout_ids(detail, panel) if callouts else ()
    callout_font = _font(34)
    dimension_font = _font(19)

    with Image.open(path) as raw:
        image = raw.convert("RGB")
    draw = ImageDraw.Draw(image)

    radius = 26
    for local_number, part_id in enumerate(callout_ids, start=1):
        number = (callout_numbers.get(part_id, local_number)
                  if callout_numbers else local_number)
        anchor_x, anchor_y = _project(
            renderer, vtk, centers[part_id], size[1])
        x, y = anchor_x, anchor_y
        # A small deterministic stagger keeps coincident fastener callouts legible.
        x += ((local_number - 1) % 3 - 1) * 12
        y += ((local_number - 1) // 3 % 2) * 10
        if panel.action == "fasten":
            x += 90
            y += 70
            draw.line(
                (anchor_x, anchor_y, x, y), fill=CALLOUT_INK, width=3)
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=(255, 255, 255), outline=CALLOUT_INK, width=4)
        text = str(number)
        box = draw.textbbox((0, 0), text, font=callout_font)
        draw.text(
            (x - (box[2] - box[0]) / 2,
             y - (box[3] - box[1]) / 2 - box[1]),
            text, fill=CALLOUT_INK, font=callout_font)

    station_markers, stations_to_draw = _stations_for_overlay(panel)

    for station in station_markers:
        for point in (station.p1, station.mirror_p1):
            if point is None:
                continue
            x, y = _project(renderer, vtk, point, size[1])
            r = 7
            draw.ellipse(
                (x - r, y - r, x + r, y + r),
                fill=DIMENSION_BLUE, outline=(255, 255, 255), width=2)

    for index, station in enumerate(stations_to_draw):
        p0 = _project(renderer, vtk, station.p0, size[1])
        p1 = _project(renderer, vtk, station.p1, size[1])
        draw.line((*p0, *p1), fill=DIMENSION_BLUE, width=4)
        arrow = 7
        for x, y in (p0, p1):
            draw.line((x - arrow, y - arrow, x, y), fill=DIMENSION_BLUE, width=3)
            draw.line((x - arrow, y + arrow, x, y), fill=DIMENSION_BLUE, width=3)
        if station.mirror_p0 is not None and station.mirror_p1 is not None:
            mirror_p0 = _project(renderer, vtk, station.mirror_p0, size[1])
            mirror_p1 = _project(renderer, vtk, station.mirror_p1, size[1])
            draw.line((*mirror_p0, *mirror_p1), fill=DIMENSION_BLUE, width=4)
            for x, y in (mirror_p0, mirror_p1):
                draw.line(
                    (x + arrow, y - arrow, x, y),
                    fill=DIMENSION_BLUE, width=3)
                draw.line(
                    (x + arrow, y + arrow, x, y),
                    fill=DIMENSION_BLUE, width=3)
            text = f"{_fmt_dimension(station.near_mm)} each end"
        else:
            text = (f"{_fmt_dimension(station.near_mm)} / "
                    f"{_fmt_dimension(station.far_mm)}")
        if station.secondary_mm is not None:
            text += f" · {_fmt_dimension(station.secondary_mm)} down"
        mx = (p0[0] + p1[0]) // 2
        my = (p0[1] + p1[1]) // 2 - 12 - (index % 2) * 22
        box = draw.textbbox((0, 0), text, font=dimension_font)
        pad = 4
        draw.rounded_rectangle(
            (mx - (box[2] - box[0]) / 2 - pad,
             my - (box[3] - box[1]) / 2 - pad,
             mx + (box[2] - box[0]) / 2 + pad,
             my + (box[3] - box[1]) / 2 + pad),
            radius=3, fill=(255, 255, 255), outline=DIMENSION_BLUE, width=2)
        draw.text(
            (mx - (box[2] - box[0]) / 2,
             my - (box[3] - box[1]) / 2 - box[1]),
            text, fill=DIMENSION_BLUE, font=dimension_font)
        if station.q0 is not None and station.q1 is not None:
            q0 = _project(renderer, vtk, station.q0, size[1])
            q1 = _project(renderer, vtk, station.q1, size[1])
            draw.line((*q0, *q1), fill=DIMENSION_BLUE, width=3)

    ghost_ids = tuple(pid for pid in panel.visible_part_ids
                      if pid not in panel.focus_part_ids
                      and pid not in panel.arrival_part_ids)
    metadata = PngInfo()
    metadata.add_text("detailgen_panel_key", key)
    metadata.add_text("detailgen_callout_count", str(len(callout_ids)))
    metadata.add_text("detailgen_station_count", str(len(panel.stations)))
    metadata.add_text(
        "detailgen_drawn_station_reference_ids",
        ",".join(dict.fromkeys(
            station.reference_part_id for station in stations_to_draw)))
    metadata.add_text("detailgen_visible_part_ids", ",".join(panel.visible_part_ids))
    metadata.add_text("detailgen_arrival_count", str(len(panel.arrival_part_ids)))
    metadata.add_text("detailgen_focus_count", str(len(panel.focus_part_ids)))
    metadata.add_text("detailgen_ghost_count", str(len(ghost_ids)))
    metadata.add_text(
        "detailgen_callout_labels",
        json.dumps([labels[pid].display_name for pid in callout_ids]))
    image.save(path, format="PNG", pnginfo=metadata, optimize=False)


def render_instruction_panel(
    detail,
    panel,
    out_dir: str | Path,
    *,
    size: tuple[int, int] = DEFAULT_SIZE,
    style: str = "technical",
    callouts: bool = True,
    callout_numbers=None,
) -> Path:
    """Render one ghost/arrival panel and reuse an exact content-key hit."""
    import vtk

    palette = instruction_style(style)
    key = panel_content_key(detail, panel, size=size, style=style,
                            callouts=callouts,
                            callout_numbers=callout_numbers)
    output = Path(out_dir) / f"{key}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and _is_valid_cached_panel(output, key=key, size=size):
        return output
    if output.exists():
        output.unlink()

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(1.0, 1.0, 1.0)
    visible = set(panel.visible_part_ids)
    emphasized = set(panel.focus_part_ids) | set(panel.arrival_part_ids)
    shown = set()
    for placed, world in detail.assembly.isolated_world_solids():
        if placed.id not in visible:
            continue
        shown.add(placed.id)
        material = placed.component.material.rgba
        for solid in world.vals():
            verts, tris = solid.tessellate(
                MESH_TOL_LINEAR, MESH_TOL_ANGULAR)
            points = vtk.vtkPoints()
            for vertex in verts:
                points.InsertNextPoint(vertex.x, vertex.y, vertex.z)
            cells = vtk.vtkCellArray()
            for triangle in tris:
                cells.InsertNextCell(3)
                for vertex_index in triangle:
                    cells.InsertCellPoint(vertex_index)
            poly = vtk.vtkPolyData()
            poly.SetPoints(points)
            poly.SetPolys(cells)
            normals = vtk.vtkPolyDataNormals()
            normals.SetInputData(poly)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(normals.GetOutputPort())
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            if placed.id in emphasized:
                if palette.use_material_color:
                    actor.GetProperty().SetColor(*material[:3])
                else:
                    actor.GetProperty().SetColor(*palette.work_color)
                actor.GetProperty().SetOpacity(1.0)
            else:
                actor.GetProperty().SetColor(*palette.prior_color)
                actor.GetProperty().SetOpacity(palette.prior_opacity)
            if palette.edge_visibility:
                # Per-cell edges would draw tessellation triangles that read
                # as false joints; feature edges outline only real geometry
                # (boundaries and creases).
                feature = vtk.vtkFeatureEdges()
                feature.SetInputConnection(normals.GetOutputPort())
                feature.BoundaryEdgesOn()
                feature.FeatureEdgesOn()
                feature.SetFeatureAngle(35.0)
                feature.ManifoldEdgesOff()
                feature.NonManifoldEdgesOff()
                feature.ColoringOff()
                edge_mapper = vtk.vtkPolyDataMapper()
                edge_mapper.SetInputConnection(feature.GetOutputPort())
                edge_mapper.SetResolveCoincidentTopologyToPolygonOffset()
                edge_actor = vtk.vtkActor()
                edge_actor.SetMapper(edge_mapper)
                edge_actor.GetProperty().SetColor(*palette.edge_color)
                edge_actor.GetProperty().SetLineWidth(palette.edge_width)
                edge_actor.GetProperty().SetOpacity(
                    1.0 if placed.id in emphasized else palette.prior_opacity)
                renderer.AddActor(edge_actor)
            renderer.AddActor(actor)
    missing = visible - shown
    if missing:
        raise ValueError(
            f"panel {panel.index} names absent visible parts: {sorted(missing)!r}")

    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(*size)
    window.AddRenderer(renderer)
    temporary = None
    try:
        camera = renderer.GetActiveCamera()
        camera.SetPosition(*panel_camera(panel))
        camera.SetFocalPoint(0, 0, 0)
        camera.SetViewUp(0, 0, 1)
        renderer.ResetCamera()
        camera.Zoom(1.12)
        window.Render()

        grabber = vtk.vtkWindowToImageFilter()
        grabber.SetInput(window)
        grabber.Update()
        writer = vtk.vtkPNGWriter()
        with tempfile.NamedTemporaryFile(
            prefix=f".{key}.", suffix=".png", dir=output.parent, delete=False,
        ) as handle:
            temporary = Path(handle.name)
        writer.SetFileName(str(temporary))
        writer.SetInputConnection(grabber.GetOutputPort())
        writer.Write()
        _draw_overlay(
            temporary, detail=detail, panel=panel, renderer=renderer, vtk=vtk,
            size=size, key=key, callouts=callouts,
            callout_numbers=callout_numbers)
        if not _is_valid_cached_panel(temporary, key=key, size=size):
            raise RuntimeError(
                f"instruction panel {panel.index} did not produce a complete "
                "keyed PNG")
        temporary.replace(output)
        temporary = None
    finally:
        window.Finalize()
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return output


def render_frame_images(
    detail,
    panels_manual,
    frames,
    out_dir: str | Path,
    *,
    size: tuple[int, int] = DEFAULT_SIZE,
    style: str = "technical",
    callout_numbers=None,
) -> dict[str, "Path"]:
    """Render one scene per action frame with the frame's own focus set.

    Each frame re-uses its source panel's visibility (what exists at that
    point in the build) while emphasizing only the frame's parts. Hold-gate
    frames render nothing — their page is the unavoidable warning.
    """
    from dataclasses import replace as _replace

    panels_by_index = {panel.index: panel for panel in panels_manual.panels}
    result: dict[str, Path] = {}
    for frame in frames:
        if frame.is_hold_gate:
            continue
        if frame.illustration is None:
            raise ValueError(
                f"frame {frame.frame_id!r} has no illustration intent")
        panel = panels_by_index[frame.illustration.panel_index]
        pseudo = _replace(
            panel,
            focus_part_ids=frame.focus_part_ids,
            arrival_part_ids=(),
            stations=(),
        )
        result[frame.frame_id] = render_instruction_panel(
            detail, pseudo, out_dir, size=size, style=style,
            callout_numbers=callout_numbers)
    return result


def render_cover_image(
    detail,
    panels_manual,
    out_dir: str | Path,
    *,
    size: tuple[int, int] = DEFAULT_SIZE,
    style: str = "high_contrast",
) -> "Path":
    """Finished-product view: the last panel with every built part focused."""
    from dataclasses import replace as _replace

    last = panels_manual.panels[-1]
    pseudo = _replace(
        last,
        focus_part_ids=last.visible_part_ids,
        arrival_part_ids=(),
        stations=(),
    )
    return render_instruction_panel(
        detail, pseudo, out_dir, size=size, style=style, callouts=False)


def render_instruction_images(
    detail,
    manual,
    out_dir: str | Path,
    *,
    size: tuple[int, int] = DEFAULT_SIZE,
    style: str = "technical",
) -> dict[int, Path]:
    """Render every panel in manual order, keyed by 1-based panel index."""
    return {
        panel.index: render_instruction_panel(
            detail, panel, out_dir, size=size, style=style)
        for panel in manual.panels
    }
