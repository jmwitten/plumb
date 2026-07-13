"""``Frame`` — an immutable rigid-body coordinate frame (datum).

A ``Frame`` is a right-handed orthonormal coordinate system: an origin plus
three unit axes. Equivalently it is the rigid transform that carries a point
expressed in the frame's **local** coordinates into its **parent** coordinates
(``world_p = R @ local_p + origin``). There is no scale and no shear — a Frame
is pure rotation + translation, exactly the transform CadQuery applies when it
places a solid.

Why this type exists
--------------------
Components declare *named datum frames* in their own local coordinates (see
``Component.datums`` and each component class). The assembly then mates two
datums by making them coincide, which computes a part's world transform from
*construction vocabulary* ("the leg's ``base`` on the boulder's ``top``")
rather than from a hand-derived rotate/translate. Because a datum bakes in the
surface it names — origin *and* orientation — a sign error in placement becomes
unrepresentable instead of a silently-wrong-but-valid solid.

Conventions
-----------
- Distances are millimeters (package convention).
- A datum's **+Z** is its "assembly-up" axis: the direction the stack grows
  across that joint. Two mated datums are made to coincide, so their +Z agree
  and the parts stack along a shared axis. See ``DetailAssembly.place``.
- Angles in constructors are **degrees** (public APIs are imperial/human).

The transform is stored as an OpenCascade ``gp_Trsf`` so composition and
application are bit-identical to the transforms CadQuery performs on shapes;
this is what lets the datum/mate path reproduce the legacy ``add(at, rotate)``
placement exactly (see ``from_at_rotate``).
"""

from __future__ import annotations

import math

import cadquery as cq
from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

Vec3 = tuple[float, float, float]

_AXIS_DIR: dict[str, Vec3] = {"X": (1.0, 0.0, 0.0), "Y": (0.0, 1.0, 0.0),
                              "Z": (0.0, 0.0, 1.0)}


def _normalize(v: Vec3) -> Vec3:
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if n < 1e-12:
        raise ValueError(f"cannot normalize near-zero vector {v!r}")
    return (v[0] / n, v[1] / n, v[2] / n)


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


class Frame:
    """An immutable right-handed datum frame (origin + orthonormal axes).

    Construct via the classmethods (``identity``, ``translation``,
    ``rotation``, ``from_origin_axes``, ``from_at_rotate``); combine with
    ``compose``/``inverse``; read geometry with ``origin``/``x_axis``/… and
    map coordinates with ``transform_point``/``transform_direction``. Apply a
    frame to CadQuery geometry through its ``location``.
    """

    __slots__ = ("_trsf",)

    def __init__(self, trsf: gp_Trsf | None = None):
        # Private constructor: callers should prefer the classmethods. A copy
        # is taken so the frame is truly immutable even if the caller mutates.
        self._trsf = _copy_trsf(trsf) if trsf is not None else gp_Trsf()

    # -- constructors ---------------------------------------------------------

    @classmethod
    def identity(cls) -> "Frame":
        return cls()

    @classmethod
    def translation(cls, offset: Vec3) -> "Frame":
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(float(offset[0]), float(offset[1]), float(offset[2])))
        return cls(t)

    @classmethod
    def rotation(cls, angle_deg: float, axis: Vec3 = (0.0, 0.0, 1.0),
                 origin: Vec3 = (0.0, 0.0, 0.0)) -> "Frame":
        """Rotation by ``angle_deg`` (degrees, right-handed) about the line
        through ``origin`` in direction ``axis``."""
        ax = gp_Ax1(gp_Pnt(*(float(c) for c in origin)),
                    gp_Dir(*(float(c) for c in axis)))
        t = gp_Trsf()
        t.SetRotation(ax, math.radians(float(angle_deg)))
        return cls(t)

    @classmethod
    def from_origin_axes(cls, origin: Vec3, x_dir: Vec3, z_dir: Vec3) -> "Frame":
        """Build a frame from an origin, a desired X direction and a Z
        direction. ``x_dir`` is orthonormalized against ``z_dir`` (Gram-Schmidt)
        and Y is ``z × x`` so the result is always right-handed orthonormal."""
        z = _normalize(z_dir)
        x = (x_dir[0] - _dot(x_dir, z) * z[0],
             x_dir[1] - _dot(x_dir, z) * z[1],
             x_dir[2] - _dot(x_dir, z) * z[2])
        x = _normalize(x)
        y = _cross(z, x)
        # Columns of the rotation matrix are the local axes in world coords.
        t = gp_Trsf()
        t.SetValues(
            x[0], y[0], z[0], float(origin[0]),
            x[1], y[1], z[1], float(origin[1]),
            x[2], y[2], z[2], float(origin[2]),
        )
        return cls(t)

    @classmethod
    def from_at_rotate(cls, at: Vec3 = (0.0, 0.0, 0.0),
                       rotate: list[tuple[str, float]] | None = None) -> "Frame":
        """The world frame produced by the legacy ``add(at=, rotate=[...])``
        placement: rotations about the **global** axes applied in list order,
        then a translation. This is the low-level escape hatch; both this and
        the mate API resolve to the same ``Frame`` representation, so
        ``world_solid`` is identical either way."""
        f = cls.identity()
        for axis, angle in (rotate or []):
            key = axis.upper()
            if key not in _AXIS_DIR:
                raise ValueError(f"unknown rotate axis {axis!r} (use X/Y/Z)")
            # each rotation is applied after (outside) the ones already built,
            # matching wp.rotate(...).rotate(...) left-to-right accumulation.
            f = cls.rotation(angle, _AXIS_DIR[key]).compose(f)
        return cls.translation(tuple(float(v) for v in at)).compose(f)

    # -- algebra --------------------------------------------------------------

    def compose(self, other: "Frame") -> "Frame":
        """``self ∘ other`` — the frame that maps ``other``'s local coordinates
        through ``other`` and then through ``self``. If ``self`` is a parent
        frame in world and ``other`` is a child datum expressed in that parent,
        ``self.compose(other)`` is the child datum in world."""
        return Frame(self._trsf.Multiplied(other._trsf))

    def inverse(self) -> "Frame":
        """The frame that undoes this one (world→local)."""
        return Frame(self._trsf.Inverted())

    # -- coordinate mapping ---------------------------------------------------

    def transform_point(self, p: Vec3) -> Vec3:
        q = gp_Pnt(float(p[0]), float(p[1]), float(p[2]))
        q.Transform(self._trsf)
        return (q.X(), q.Y(), q.Z())

    def transform_direction(self, d: Vec3) -> Vec3:
        """Map a direction (rotation only — translation is ignored)."""
        v = gp_Vec(float(d[0]), float(d[1]), float(d[2]))
        v.Transform(self._trsf)
        return (v.X(), v.Y(), v.Z())

    # -- geometry read-outs ---------------------------------------------------

    @property
    def origin(self) -> Vec3:
        return self.transform_point((0.0, 0.0, 0.0))

    @property
    def x_axis(self) -> Vec3:
        return self.transform_direction((1.0, 0.0, 0.0))

    @property
    def y_axis(self) -> Vec3:
        return self.transform_direction((0.0, 1.0, 0.0))

    @property
    def z_axis(self) -> Vec3:
        return self.transform_direction((0.0, 0.0, 1.0))

    # -- CadQuery interop -----------------------------------------------------

    @property
    def location(self) -> cq.Location:
        """A ``cq.Location`` that places local geometry into this frame — apply
        with ``shape.moved(frame.location)``."""
        return cq.Location(_copy_trsf(self._trsf))

    # -- checks / debug -------------------------------------------------------

    def is_orthonormal(self, tol: float = 1e-9) -> bool:
        """True when the axes are unit-length, mutually perpendicular and
        right-handed (``z × x == y``)."""
        x, y, z = self.x_axis, self.y_axis, self.z_axis
        for v in (x, y, z):
            if abs(math.sqrt(_dot(v, v)) - 1.0) > tol:
                return False
        if abs(_dot(x, y)) > tol or abs(_dot(y, z)) > tol or abs(_dot(z, x)) > tol:
            return False
        cx = _cross(z, x)
        return all(abs(a - b) <= tol for a, b in zip(cx, y))

    def approx_equal(self, other: "Frame", tol: float = 1e-9) -> bool:
        """True when both frames map a probe basis to the same coordinates."""
        probes = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
        for p in probes:
            a, b = self.transform_point(p), other.transform_point(p)
            if any(abs(u - v) > tol for u, v in zip(a, b)):
                return False
        return True

    def __repr__(self) -> str:
        o = tuple(round(c, 4) for c in self.origin)
        z = tuple(round(c, 4) for c in self.z_axis)
        return f"Frame(origin={o}, z_axis={z})"


def _copy_trsf(t: gp_Trsf) -> gp_Trsf:
    """gp_Trsf has no copy constructor from a gp_Trsf; multiplying by identity
    yields an independent copy with identical values."""
    return t.Multiplied(gp_Trsf())
