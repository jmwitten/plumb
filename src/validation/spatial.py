"""Spatial-intent invariants (task SPATIAL, P6) — the first activation of the
coverage matrix's ``Spatial intent`` family.

A spatial invariant is a DECLARED redundancy about *where* and *which-way* parts
sit, checked against the compiled geometry. It is VALIDATION-ONLY: it never moves
a part or solves for a placement (computed placement stays canonical). Its whole
reason to exist is that it survives the raw-transform escape hatch — the place
both motivating real bugs lived:

* **SymmetricAbout** (subsumes a bare MirrorPair): declared part pairs — or a
  name selector that discovers them — must be mirror images about a coordinate
  plane. Would have caught the RAILFIX defect (a ``-Y`` rail left as an
  unmirrored copy of its ``+Y`` twin, overhanging the wrong world side).
* **FacesToward / FacesAway**: a part's declared facing (a world axis, or a
  body-fixed datum's axis) must point toward / away from a target part or a
  world direction. The ladder-at-wrong-end class (a Wave-1 step-placement miss).

Parallel / Perpendicular / AlignedWith are RESERVED NAMES only (documented
planned vocabulary + a teaching error) — a parse-and-noop stub would be a FAKE
invariant, letting a CLEAN report imply a proof that never ran. See
:data:`RESERVED_SPATIAL_NAMES` / :func:`reserved_name_error`.

What SymmetricAbout PROVES, precisely (P1 honesty): the two parts' world
axis-aligned bounding boxes are reflections of each other across the plane
(every min/max on every axis, so it is strictly stronger than a centroid test —
it sees extent, hence a part rotated within its footprint). What it does NOT
prove: the full SE(3) orientation is a true (improper) reflection — a part that
happens to fill the reflected AABB via a proper rotation is indistinguishable to
an AABB test. That is the honest, cheap (frame/bbox arithmetic, no boolean ops)
generalization of the mutation-proven 20-pair RAILFIX audit, and it catches the
same defect that audit does.

What FacesToward/FacesAway PROVES: the sign of the projection of the declared
facing onto the direction to the target (a positive/negative dot product). With
a world-axis facing and a PART target it is position-sensitive (catches a part
translated to the wrong end, because the direction to the target flips); with a
datum facing and a DIRECTION target it is orientation-sensitive (catches a part
spun to face the wrong way). It does NOT prove any angular magnitude beyond the
sign, nor that the part is reachable/accessible (that is Functional intent, a
separate later layer).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .checks import Finding

#: The finding kinds this module emits — each maps to ``Spatial intent`` in
#: :data:`detailgen.validation.coverage.KIND_TO_FAMILY`. The reserved planned
#: vocabulary + its teaching error live in :mod:`detailgen.spec.schema`
#: (``RESERVED_SPATIAL_NAMES`` / ``reserved_spatial_error``) so the CadQuery-free
#: spec loader can raise it without importing this geometry module.
SPATIAL_KINDS = frozenset({"symmetric_about", "faces_toward", "faces_away"})

#: Plane -> the axis index its reflection negates (the plane's normal axis).
#: "XZ" is the plane containing X and Z (i.e. Y = 0); reflecting across it
#: negates Y. This is the platform's launch-deck centerline plane.
_PLANE_NORMAL_AXIS = {"XY": 2, "YZ": 0, "XZ": 1}


# -- geometry helpers (cheap: bbox + frame arithmetic, no boolean ops) --------

def _aabb(placed):
    bb = placed.world_solid().val().BoundingBox()
    return (bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax)


def _center(placed):
    xmin, ymin, zmin, xmax, ymax, zmax = _aabb(placed)
    return ((xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2)


def _reflect_aabb(box, axis: int):
    """Reflect an AABB ``(xmin,ymin,zmin,xmax,ymax,zmax)`` across the coordinate
    plane whose normal is ``axis``: that coordinate's [min,max] becomes
    [-max,-min] (reflection flips the interval and swaps the extremes), the
    other two axes are unchanged."""
    lo = list(box[:3])
    hi = list(box[3:])
    lo[axis], hi[axis] = -hi[axis], -lo[axis]
    return (*lo, *hi)


def _normalize(v):
    n = math.sqrt(sum(c * c for c in v))
    if n < 1e-12:
        return None
    return tuple(c / n for c in v)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


# -- the two checks (pure functions on resolved Placed parts) -----------------

def check_symmetric_about(a, b, plane: str, tol: float) -> Finding:
    """``a`` and ``b`` must be mirror images about ``plane`` — their world AABBs
    reflections of each other within ``tol`` (mm). Position- and extent-aware
    (see module docstring for exactly what this proves and does not)."""
    subject = f"{a.name} <-> {b.name} about {plane}"
    axis = _PLANE_NORMAL_AXIS.get(plane.upper())
    if axis is None:
        return Finding("symmetric_about", subject, False,
                       f"unknown plane {plane!r}; use one of "
                       f"{sorted(_PLANE_NORMAL_AXIS)}")
    reflected = _reflect_aabb(_aabb(a), axis)
    box_b = _aabb(b)
    dev = max(abs(r - c) for r, c in zip(reflected, box_b))
    if dev <= tol:
        return Finding("symmetric_about", subject, True,
                       f"AABBs mirror-symmetric about {plane} "
                       f"(max dev {dev:.4f} mm <= {tol:g})")
    return Finding("symmetric_about", subject, False,
                   f"NOT mirror-symmetric about {plane}: AABB deviates "
                   f"{dev:.3f} mm > {tol:g} — a {b.name!r} placement that did "
                   f"not mirror {a.name!r} across {plane}")


def check_faces(part, facing_world, target_dir, sense: str, target_desc: str,
                tol: float = 0.0) -> Finding:
    """The part's ``facing_world`` (an already-world-space direction) must point
    ``sense`` (``"toward"``/``"away"``) ``target_dir`` (an already-world-space
    direction toward the target). Passes when the signed projection clears
    ``tol`` on the correct side of zero."""
    kind = f"faces_{sense}"
    subject = f"{part.name} faces {sense} {target_desc}"
    f = _normalize(facing_world)
    d = _normalize(target_dir)
    if f is None or d is None:
        return Finding(kind, subject, False,
                       "degenerate facing or target direction (zero-length)")
    proj = _dot(f, d)
    ok = proj > tol if sense == "toward" else proj < -tol
    verdict = "points" if ok else "does NOT point"
    return Finding(kind, subject, ok,
                   f"facing {verdict} {sense} {target_desc} "
                   f"(projection {proj:+.4f})")


# -- declarations (the imperative surface; the spec compiler builds the same) --

@dataclass(frozen=True)
class SymmetricAbout:
    """Declare that part pairs are mirror-symmetric about ``plane`` (one of
    ``XY``/``YZ``/``XZ``). Supply pairs one of two ways (both allowed at once):

    * ``pairs`` — explicit ``((a, b), ...)`` references (names or handles);
    * ``mirror`` — a ``(plus, minus)`` name-substitution selector (e.g.
      ``("+Y", "-Y")``) that DISCOVERS every pair whose names differ only by
      that substitution. This is the direct generalization of the RAILFIX
      20-pair +Y/-Y audit.

    ``tol`` (mm) overrides the tolerance (default: ``tol.dimension_tolerance``).
    """

    plane: str
    pairs: tuple = ()
    mirror: tuple | None = None
    tol: float | None = None

    def evaluate(self, assembly, default_tol) -> list[Finding]:
        tol = self.tol if self.tol is not None else default_tol
        pairs = self._resolved_pairs(assembly)
        if not pairs:
            # A declared invariant that resolves to ZERO pairs proves nothing —
            # a mirror selector whose substitution matches no real part names,
            # or an empty declaration. Emitting no finding would let it read as
            # declared-and-proven (invisible in a CLEAN report), the exact
            # fake-invariant failure this family exists to prevent. Emit ONE
            # loud FAILING finding instead so the Spatial family cannot pass on
            # a selector that never ran (see module docstring on RESERVED_NAMES
            # — same honesty rule).
            return [self._zero_match_finding()]
        return [check_symmetric_about(a_ref, b_ref, self.plane, tol)
                for a_ref, b_ref in pairs]

    def _zero_match_finding(self) -> Finding:
        if self.mirror is not None:
            src = (f"mirror selector {self.mirror!r} matched no part-name pairs")
        elif not self.pairs:
            src = "no explicit pairs and no mirror selector declared"
        else:  # unreachable in practice: explicit refs resolve or raise
            src = "explicit pairs resolved to nothing"
        return Finding(
            "symmetric_about", f"symmetric_about about {self.plane}: {src}",
            False,
            f"declared SymmetricAbout invariant resolved to ZERO part pairs "
            f"({src}) — a declared invariant that proves nothing must not read "
            f"as proven. Check the mirror substitution matches real part names, "
            f"or remove the declaration.")

    def _resolved_pairs(self, assembly):
        pairs = [(assembly._resolve(a), assembly._resolve(b))
                 for a, b in self.pairs]
        if self.mirror is not None:
            pairs.extend(_discover_mirror_pairs(assembly, self.mirror))
        return pairs


@dataclass(frozen=True)
class _Faces:
    """Shared base for :class:`FacesToward` / :class:`FacesAway`. ``facing`` is
    either a world-axis 3-tuple or a datum-name string (the part's named datum's
    world +Z). ``target`` is either a reference (name/handle → a part, whose
    centroid gives the direction) or a world-direction 3-tuple. ``tol`` is the
    projection margin about zero (default 0)."""

    part: object
    facing: object
    target: object
    tol: float = 0.0

    _sense = ""  # set by subclasses

    def evaluate(self, assembly, default_tol) -> list[Finding]:
        part = assembly._resolve(self.part)
        facing_world = _facing_world(part, self.facing)
        target_dir, target_desc = _target_direction(assembly, part, self.target)
        return [check_faces(part, facing_world, target_dir, self._sense,
                            target_desc, tol=self.tol)]


@dataclass(frozen=True)
class FacesToward(_Faces):
    _sense = "toward"


@dataclass(frozen=True)
class FacesAway(_Faces):
    _sense = "away"


def _facing_world(part, facing):
    """Resolve a facing spec to a world-space direction: a 3-tuple is taken as a
    world axis; a string names a body-fixed datum whose world +Z is the
    facing."""
    if isinstance(facing, str):
        return part.datum_world(facing).z_axis
    return tuple(float(c) for c in facing)


def _target_direction(assembly, part, target):
    """Resolve a target to (world direction, human description). A 3-tuple is a
    world direction; anything else is a part reference and the direction is
    part-centroid → target-centroid."""
    if isinstance(target, (tuple, list)) and len(target) == 3 and all(
            isinstance(c, (int, float)) for c in target):
        return tuple(float(c) for c in target), f"direction {tuple(target)}"
    tgt = assembly._resolve(target)
    pc = _center(part)
    tc = _center(tgt)
    return (tc[0] - pc[0], tc[1] - pc[1], tc[2] - pc[2]), tgt.name


def _discover_mirror_pairs(assembly, mirror):
    """Find every part pair whose names differ only by the ``(plus, minus)``
    substitution — the RAILFIX +Y/-Y audit as a reusable selector. Sorted by the
    ``plus`` part's name for a deterministic finding order."""
    plus, minus = mirror
    by_name = {p.name: p for p in assembly.parts}
    out = []
    for name, part in by_name.items():
        if plus in name:
            other = name.replace(plus, minus)
            if other in by_name:
                out.append((part, by_name[other]))
    out.sort(key=lambda pair: pair[0].name)
    return out
