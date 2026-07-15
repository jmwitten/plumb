"""Schematic fastener proxies for the presentation explode scene (opt-in).

The compiled cabinetry pack represents every purchased connector as a typed
machining station plus a hardware-schedule line, never a 3D body — the
validated assembly holds only wood panels and the two modeled wall anchors. A
homeowner reading the interactive viewer therefore sees no screws where the
build actually joins. This module fills that gap for the PRESENTATION scene
only: it yields simple cylinder-and-head proxy bodies positioned exactly at the
typed machining stations, so the viewer/explode can show every modeled
connector location. Nothing here touches the validated assembly, the
construction process graph, the BOM, the cut list, the hardware schedule, or
any release gate — the proxies are added to a throwaway presentation
``DetailAssembly`` behind an opt-in flag, and each one is labelled, in its own
tooltip, as a schematic proxy placed from the machining schedule.

Honest positioning (no invented locations)
-------------------------------------------
Every proxy comes from ONE typed ``MachiningFeature`` row and nothing else. A
row names the machined part (``part_id``), the 2D station on a named face
(``location_mm`` in the face's own ``coordinate_system``), the fastener count
and pitch, and — for a driven joint — the receiving part. The station's WORLD
position is derived purely from that typed row plus the machined part's own
placed geometry:

  * the fastener axis is the machined panel's thickness axis (the face normal,
    read straight off the part's world frame);
  * the head sits on the named face; its world plane is that part's bounding-box
    extreme on the thickness axis, on the side the face's prose names
    (``outside``/``inside`` resolved against the cabinet centre, ``top`` up,
    ``front`` toward the room);
  * the in-face position maps the row's ``+X``/``+Y`` PHYSICAL directions
    (``up``, ``toward wall``, ``rearward``, ``right`` …) onto world axes, so a
    face whose origin corner or axis handedness differs from the panel's solid
    frame still lands on the true corner — never a mirrored guess.

Classes whose position AND drive axis cannot be honestly derived from the typed
row are SKIPPED, not guessed (see :data:`SKIPPED_KINDS` and the task report):
material-removal features (grooves, notches, hook bores), the locking-device
bores (empty ``location_mm``, angled template), and the stabilizer stock cuts
(a hardware-stock length on a non-placed id).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import cadquery as cq

from ...assemblies.assembly import DetailAssembly, Placed
from ...core.base import Component
from ...core.frame import Frame
from ...core.units import fmt_in
from ...rendering.part_labels import part_labels
from . import catalogs

#: Head-ward explode offset (mm) applied to every proxy along its drive axis.
#: A proxy "backs out the way its head faces" (the through-hole convention in
#: :mod:`detailgen.rendering.web_viewer.explode`), so the vector points along
#: the OUTWARD face normal — the opposite of the insertion direction. Sized to
#: clear the panel faces of the ~1.6 m case without colliding with neighbours.
PROXY_EXPLODE_MM = 120.0

#: Machining kinds represented by a proxy body, each mapped to its reader label.
#: These are exactly the connector classes whose station position AND drive axis
#: are derivable from the typed row (see the module docstring). ``confirmat`` and
#: the drawer-box confirmat share one physical product, hence one reader name.
_COVERED = {
    "confirmat_step_drill": "Confirmat screw",
    "drawer_box_confirmat_step_drill": "Confirmat screw",
    "toe_attachment_station": "Cabinet screw",
    "applied_front_attachment": "Front-attachment screw",
    "runner_fixing_station": "Runner mounting screw",
}

#: Machining kinds deliberately NOT proxied, with the honest reason. Surfaced in
#: the task report; kept here so the set is one source of truth for tests.
SKIPPED_KINDS = {
    "captured_back_groove": "material-removal groove, not a connector body",
    "drawer_bottom_groove": "material-removal groove, not a connector body",
    "runner_rear_notch": "material-removal notch, not a connector body",
    "runner_hook_bore": "runner-hook engagement bore, not a fastener body",
    "locking_device_bore": "empty location_mm on a 75° template — no derivable position",
    "stabilizer_gear_rack_cut": "hardware-stock cut length on a non-placed id",
    "stabilizer_linkage_rod_cut": "hardware-stock cut length on a non-placed id",
    "pull_bore": ("through-bore for the drawer pull — the pull is a handle, not a "
                  "fastener, and the mounting-screw insertion side is not fixed by "
                  "the typed row"),
}

#: Pre-slash physical direction word -> (world axis index, sign). A machining
#: row's ``+X``/``+Y`` face axis is stated as ``"<word>/cut-list …"``; the word
#: is an unambiguous world direction for these axis-aligned cabinet parts.
_DIR_MAP = {
    "up": (2, 1.0), "down": (2, -1.0),
    "top": (2, 1.0), "bottom": (2, -1.0),
    "right": (0, 1.0), "left": (0, -1.0),
    "rearward": (1, 1.0), "toward wall": (1, 1.0), "wall": (1, 1.0),
    "forward": (1, -1.0), "front": (1, -1.0),
}


class _FastenerProxy(Component):
    """A deliberately schematic connector body: a head disc above the bearing
    plane and a plain shank below it, sized from a typed catalog product. NO
    thread is modelled — this is a placeholder that marks a connector's location
    in the presentation scene, not a fabrication spec.

    Local frame: the head bearing sits at ``Z=0``; the head rises to ``+Z`` and
    the shank runs to ``-Z`` (the headed-fastener convention in
    :mod:`detailgen.components.fasteners`). Placement aligns local ``+Z`` with
    the OUTWARD face normal, so the head pokes out of the machined face and the
    shank drives into the joint.
    """

    material_key = "steel_zinc"

    def __init__(self, diameter: float, length: float, catalog: str,
                 name: str):
        super().__init__(name)
        self.diameter = float(diameter)
        self.length = float(length)
        self.catalog = str(catalog)

    def _build(self) -> cq.Workplane:
        r = self.diameter / 2.0
        head_r = 0.9 * self.diameter
        head_h = 0.6 * self.diameter
        shank = cq.Workplane("XY").circle(r).extrude(-self.length)
        head = cq.Workplane("XY").circle(head_r).extrude(head_h)
        return head.union(shank)

    def describe(self) -> str:
        return (f"{fmt_in(self.diameter)} dia × {fmt_in(self.length, 1)} "
                "(schematic proxy)")

    def assumptions(self) -> str:
        return (
            "Schematic fastener proxy — a plain cylinder-and-head placeholder "
            "positioned at the typed machining station, not a modelled thread. "
            "Shown for location only; it is not part of the validated assembly, "
            "the bill of materials, or the cut list.")

    def bom_group(self) -> str:
        return f"fastener_proxy|{self.catalog}"

    def bom_label(self) -> str:
        return "Fastener proxy"


@dataclass(frozen=True)
class ProxyStation:
    """One placed proxy: enough to append it to a scene and to test it against
    the machining row it came from."""

    name: str
    reader_name: str
    catalog: str
    diameter_mm: float
    length_mm: float
    world_point: tuple[float, float, float]
    world_frame: Frame
    explode: tuple[float, float, float]
    kind: str
    feature_id: str
    part_id: str


def _face_axis_sign(coordinate_system: str, label: str) -> tuple[int, float]:
    """The world (axis, sign) that a machining face's ``+X`` or ``+Y`` points
    along, read from the row's prose ``coordinate_system``."""
    match = re.search(rf"\+{label}=([^;]+)", coordinate_system)
    if match is None:
        raise ValueError(
            f"machining coordinate system has no +{label} axis: "
            f"{coordinate_system!r}")
    token = match.group(1).split("/")[0].strip().lower()
    try:
        return _DIR_MAP[token]
    except KeyError:
        raise ValueError(
            f"unmapped face-axis direction {token!r} in {coordinate_system!r}"
        ) from None


def _wbbox_center(bbox) -> tuple[float, float, float]:
    return ((bbox.xmin + bbox.xmax) / 2.0,
            (bbox.ymin + bbox.ymax) / 2.0,
            (bbox.zmin + bbox.zmax) / 2.0)


def _thickness_axis(placed: Placed) -> int:
    """The machined panel's thickness (face-normal) world axis — the axis its
    local Z maps to. The fastener drives along this axis."""
    z = placed.world_frame.z_axis
    return max(range(3), key=lambda k: abs(z[k]))


#: Covered classes whose machining ``source`` is a symbolic tag rather than a
#: catalog id: their fastener product is the one the hardware schedule assigns
#: to the named system kind, read from that typed BOM line.
_HARDWARE_SOURCED = {
    "applied_front_attachment": "applied_front_fastener_system",
}


def _resolve_product_id(project, row) -> str:
    """The catalog product id for a covered row's fastener. Most rows cite the
    id in ``source``; the applied-front row tags a symbolic source, so its
    product is read from the matching hardware-schedule line instead."""
    hardware_kind = _HARDWARE_SOURCED.get(row.kind)
    if hardware_kind is not None:
        for item in project.artifacts.hardware_schedule:
            if item.kind == hardware_kind:
                return item.product_id
        raise ValueError(
            f"no hardware-schedule line of kind {hardware_kind!r} to size the "
            f"{row.kind} proxy")
    return row.source


def _catalog_size(kind: str, product_id: str) -> tuple[float, float, str]:
    """(diameter mm, length mm, catalog product name) for a covered class's
    fastener, read from the typed catalog record."""
    if kind == "runner_fixing_station":
        runner = catalogs.get_drawer_runner(product_id)
        return (runner.installation_screw_diameter_mm,
                runner.installation_screw_length_mm,
                f"{runner.manufacturer} {runner.installation_screw_sku} "
                "runner-mounting screw")
    product = catalogs.get_assembly_fastener(product_id)
    return (product.diameter_mm, product.length_mm, product.product)


def proxy_stations(project, assembly: DetailAssembly) -> list[ProxyStation]:
    """Derive one :class:`ProxyStation` per individual fastener in the covered
    machining classes, positioned exactly at the typed stations of ``assembly``
    (the presentation scene). Pure: appends nothing, mutates nothing."""
    placed_by_name = {p.name: p for p in assembly.parts}
    name_by_id = {p.part_id: p.name for p in project.model.parts}
    bbox_cache: dict[str, object] = {}

    def wbbox(placed: Placed):
        cached = bbox_cache.get(placed.id)
        if cached is None:
            cached = placed.world_solid().val().BoundingBox()
            bbox_cache[placed.id] = cached
        return cached

    def placed_for(part_id: str) -> Placed | None:
        name = name_by_id.get(part_id)
        return placed_by_name.get(name) if name is not None else None

    base_parts = list(assembly.parts)
    asm_center = tuple(
        sum(_wbbox_center(wbbox(p))[k] for p in base_parts) / len(base_parts)
        for k in range(3)
    )

    stations: list[ProxyStation] = []
    counter = 0
    for row in project.model.machining:
        if row.kind not in _COVERED:
            continue
        machined = placed_for(row.part_id)
        if machined is None:
            # A covered class must reference a placed part; if it does not,
            # the honest choice is to skip rather than invent a body.
            continue
        bbox = wbbox(machined)
        mins = (bbox.xmin, bbox.ymin, bbox.zmin)
        maxs = (bbox.xmax, bbox.ymax, bbox.zmax)
        center = _wbbox_center(bbox)
        n = _thickness_axis(machined)

        if row.face == "top":
            outward_sign = 1.0
        elif row.face == "front":
            outward_sign = -1.0
        elif row.face == "outside":
            outward_sign = 1.0 if center[n] - asm_center[n] > 0 else -1.0
        elif row.face == "inside":
            outward_sign = -1.0 if center[n] - asm_center[n] > 0 else 1.0
        else:
            # A face this module does not know how to resolve — skip honestly.
            continue

        head_plane = maxs[n] if outward_sign > 0 else mins[n]
        (ax_x, sgn_x) = _face_axis_sign(row.coordinate_system, "X")
        (ax_y, sgn_y) = _face_axis_sign(row.coordinate_system, "Y")

        outward = [0.0, 0.0, 0.0]
        outward[n] = outward_sign
        outward = tuple(outward)
        explode = tuple(v * PROXY_EXPLODE_MM for v in outward)
        # local +Z (head-ward) aligns with the outward face normal.
        x_hint = (1.0, 0.0, 0.0) if n != 0 else (0.0, 0.0, 1.0)

        product_id = _resolve_product_id(project, row)
        diameter, length, catalog = _catalog_size(row.kind, product_id)
        reader = _COVERED[row.kind]

        loc_x0, loc_y0 = row.location_mm[0], row.location_mm[1]
        for k in range(max(1, row.count)):
            loc_x, loc_y = loc_x0, loc_y0
            if row.pitch_axis == "X":
                loc_x = loc_x0 + k * row.pitch_mm
            elif row.pitch_axis == "Y":
                loc_y = loc_y0 + k * row.pitch_mm

            point = [0.0, 0.0, 0.0]
            point[n] = head_plane
            point[ax_x] = (mins[ax_x] if sgn_x > 0 else maxs[ax_x]) + loc_x * sgn_x
            point[ax_y] = (mins[ax_y] if sgn_y > 0 else maxs[ax_y]) + loc_y * sgn_y
            point = tuple(point)

            counter += 1
            name = (f"{project.model.section.cabinets[0].cabinet_id} "
                    f"{reader} proxy {counter}")
            frame = Frame.from_origin_axes(point, x_hint, outward)
            stations.append(ProxyStation(
                name=name, reader_name=reader, catalog=catalog,
                diameter_mm=diameter, length_mm=length, world_point=point,
                world_frame=frame, explode=explode, kind=row.kind,
                feature_id=row.feature_id, part_id=row.part_id,
            ))
    return stations


def _proxy_payload_row(placed: Placed, station: ProxyStation,
                       label) -> dict:
    """The viewer tooltip row for one proxy, matching the schema
    :func:`detailgen.rendering.web_viewer.build_viewer_payload` emits per part."""
    component = placed.component
    return {
        "id": placed.id,
        "type": type(component).__name__,
        "reader_name": label.reader_name,
        "instance_index": label.index,
        "instance_count": label.count,
        "item": label.item,
        "dims": component.describe(),
        "fab": "",
        "material": component.material.name,
        "existing": False,
        "qty": 1,
        "group": component.bom_group(),
        "specs": [
            ["Diameter", _fmt_mm(station.diameter_mm)],
            ["Length", _fmt_mm(station.length_mm)],
            ["Catalog product", station.catalog],
            ["Placed from", f"machining station {station.feature_id}"],
        ],
        "assumptions": component.assumptions(),
        "explode": [float(v) for v in station.explode],
        "stub_of": None,
    }


def _fmt_mm(value: float) -> str:
    return f"{fmt_in(value)} ({value:.1f} mm)"


def append_fastener_proxies(project, assembly: DetailAssembly) -> dict[str, dict]:
    """Append every covered fastener proxy to ``assembly`` (the presentation
    scene) and return the viewer payload rows for them, keyed by proxy node name.

    Presentation-only: the caller passes a throwaway product-view assembly, so
    this never reaches the validated assembly, the process graph, or any release
    surface. The returned rows are merged into the viewer payload; the appended
    bodies flow into the shared GLB so the explode shows each connector.
    """
    stations = proxy_stations(project, assembly)
    placed_by_station: list[tuple[Placed, ProxyStation]] = []
    for station in stations:
        component = _FastenerProxy(
            diameter=station.diameter_mm, length=station.length_mm,
            catalog=station.catalog, name=station.name)
        placed = assembly._append(
            component, station.world_frame,
            at=station.world_frame.origin, rotate=[])
        placed.reader_name = station.reader_name
        placed_by_station.append((placed, station))

    labels = part_labels([placed for placed, _ in placed_by_station])
    rows: dict[str, dict] = {}
    for placed, station in placed_by_station:
        rows[placed.name] = _proxy_payload_row(placed, station, labels[placed.id])
    return rows
