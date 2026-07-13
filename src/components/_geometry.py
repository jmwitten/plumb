"""Shared geometry helpers for detail-grade parts.

These build the manufacturing features that separate an engineering detail from
an envelope block: bent-angle profiles with a real bend radius, a cheap-but-
honest thread *representation*, hex washer-face chamfers, and edge easing with
graceful fallback. All lengths are millimeters (package convention).

Kept separate from any Component so the recipes can be unit-tested and reused
by fasteners, connectors and concrete alike.
"""
from __future__ import annotations

import math

import cadquery as cq


def hex_prism(across_flats: float, height: float, washer_face: bool = True) -> cq.Workplane:
    """Hex prism from Z=0 up, with 30-degree washer-face chamfers top and bottom.

    ``across_flats`` is the wrench size (distance between opposite flats). The
    chamfer is produced by intersecting with a double cone, which is far more
    robust than 3D-filleting the hex edges.
    """
    r_corner = across_flats / math.sqrt(3.0)          # circumscribed radius
    prism = cq.Workplane("XY").polygon(6, 2 * r_corner).extrude(height)
    if washer_face:
        r_flat = across_flats / 2.0
        big = r_corner * 1.05
        cone = (
            cq.Workplane("XY")
            .add(cq.Solid.makeCone(r_flat * 1.02, big, height / 2.0))
            .union(
                cq.Workplane("XY").add(
                    cq.Solid.makeCone(big, r_flat * 1.02, height / 2.0)
                    .translate(cq.Vector(0, 0, height / 2.0))
                )
            )
        )
        prism = prism.intersect(cone)
    return prism


def threaded_shaft(diameter: float, length: float, pitch: float,
                   zones: list[tuple[float, float]] | None = None,
                   depth_frac: float = 0.6) -> cq.Workplane:
    """A cylindrical shaft with V-groove thread *representation* built as ONE
    revolved zig-zag profile (not a helix, not N boolean cuts).

    Axis +Z from Z=0. ``zones`` are [(z0, z1)] bands that get threads; the rest
    stays a smooth cylinder. Thread pitch is typically exaggerated for render
    legibility — that is a stated representation, not a fabrication spec.
    """
    r = diameter / 2.0
    if zones is None:
        zones = [(0.0, length)]
    zones = sorted(zones)
    depth = 0.6134 * pitch * depth_frac

    def in_zone(z: float) -> bool:
        return any(z0 - 1e-9 <= z < z1 - 1e-9 for z0, z1 in zones)

    pts = [(0.0, 0.0), (r, 0.0)]
    z = 0.0
    while z < length - 1e-9:
        if in_zone(z):
            z_zone_end = min(z1 for z0, z1 in zones if z0 - 1e-9 <= z < z1)
            while z < z_zone_end - 1e-9 and z < length - 1e-9:
                z_mid = min(z + pitch / 2, length)
                z_end = min(z + pitch, length)
                pts.append((r - depth, z_mid))
                pts.append((r, z_end))
                z = z_end
        else:
            nxt = [z0 for z0, z1 in zones if z0 > z]
            z_next = min(nxt) if nxt else length
            pts.append((r, z_next))
            z = z_next
    pts.append((0.0, length))
    shaft = cq.Workplane("XZ").polyline(pts).close().revolve(360, (0, 0), (0, 1))
    if not shaft.val().isValid():
        raise ValueError("threaded_shaft produced an invalid solid")
    return shaft


def angle_profile(leg1: float, leg2: float, thickness: float,
                  bend_radius: float) -> cq.Sketch:
    """2D L-profile sketch (in the sketch XY plane) with a filleted inner bend
    (radius = ``bend_radius``), a concentric outer bend (radius + thickness),
    and broken toe corners. Extrude this along the member length.

    All rounding is done in 2D — 3D fillets across an extruded bend are the
    classic OpenCascade failure hotspot and are avoided entirely.
    """
    t = thickness
    pts = [(0.0, 0.0), (leg2, 0.0), (leg2, t), (t, t), (t, leg1), (0.0, leg1)]
    sk = cq.Sketch().polygon([*pts, pts[0]])
    sk = sk.vertices(cq.selectors.NearestToPointSelector((t, t))).fillet(bend_radius)
    sk = sk.reset().vertices(
        cq.selectors.NearestToPointSelector((0.0, 0.0))).fillet(bend_radius + t)
    sk = sk.reset().vertices(
        cq.selectors.NearestToPointSelector((leg2, t))).fillet(t / 2)
    sk = sk.reset().vertices(
        cq.selectors.NearestToPointSelector((t, leg1))).fillet(t / 2)
    return sk


def axis_cylinder(radius: float, length: float, base: tuple, direction: tuple) -> cq.Workplane:
    """A cylinder as an explicit solid on an arbitrary axis (deterministic —
    avoids workplane-orientation surprises when cutting holes)."""
    c = cq.Solid.makeCylinder(radius, length, cq.Vector(*base), cq.Vector(*direction))
    return cq.Workplane("XY").newObject([c])


def ease_edges(wp: cq.Workplane, selector: str, radius: float) -> cq.Workplane:
    """Cosmetic edge break with graceful degradation: fillet -> chamfer -> none.
    Never raises — an un-eased edge is acceptable; a failed build is not."""
    try:
        return wp.edges(selector).fillet(radius)
    except Exception:
        try:
            return wp.edges(selector).chamfer(radius * 0.7)
        except Exception:
            return wp
