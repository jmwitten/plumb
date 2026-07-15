"""Deterministic explode-vector derivation for the interactive viewer.

A detail that authors no ``explode:`` block (the platform — see its spec's
"NO explode block" note — and the composed site that binds it) leaves the
viewer's explode slider a no-op. Rather than hand-author ~150 vectors, we
DERIVE each part's pull-apart direction from the model's OWN declared contacts
(bearings + fastener through-holes) — the same resolved contacts the validation
sweep runs on — falling back to a purely geometric radial direction only where
the contacts give no unambiguous answer.

THE RULE (deterministic — a pure function of the compiled geometry plus the
fixed constants below; ``build`` orders parts, and every tie is broken by part
name, so two runs over one model produce byte-identical vectors):

  For each part P:
    1. Collect an OUTWARD unit normal from every contact that involves P:
       - a BEARING (P bears on Q along an axis): the axis, signed AWAY from Q
         (sign = sign(center(P)[axis] - center(Q)[axis])); the reciprocal
         normal is added to Q, so both parties pull apart from each other.
       - a THROUGH-HOLE (P is the fastener passing through some plates): the
         hole axis, signed away from the plates' mean center — the bolt backs
         out the way its head faces.
       A contact whose two centers coincide on the axis (< EPS) contributes no
       normal: it has no honest sign, so it is silently skipped, never guessed.
    2. Sum those unit normals into N. A part clamped between two OPPOSED
       bearings (an interior joist held by both beams) sees them CANCEL — there
       is no single pull-apart along that axis, and the sum correctly collapses
       to ~0 instead of picking one beam to drive into.
    3. If |N| > EPS the direction is N normalized: every summed normal points
       away from a neighbor, so their sum can never point INTO the assembly.
       Otherwise, if the component declares an ``axis`` datum, transform that
       datum's +Z into world space and sign it away from the assembly centroid.
       This withdraws an embedded connector along its physical axis.
    4. If neither semantic source resolves a direction, fall back to the radial
       direction center(P) - center(assembly) (outward by construction); if
       that too is ~0 (a part at the centroid), +Z.
    5. Magnitude = BASE_STEP + GAIN * |radial displacement of P projected onto
       the chosen direction| — a floor so even a near-central part separates,
       plus a term that fans nested parts out proportionally to how far out
       they already sit.

No direction is ever a guess: it is either a real contact normal (summed) or
the radial-outward direction, both of which move a part toward open space. A
wrong (into-the-assembly) direction is impossible by construction — the
property that let us skip hand-authoring the residual entirely.

Vectors are in the model's millimetre frame, the units the viewer's explode
slider applies directly (``node.pos = orig + v * t``).
"""

from __future__ import annotations

import math

#: Minimum pull-apart distance (mm) so even a part sitting near the assembly
#: centroid visibly separates. Sized against the ~1.6 m platform.
BASE_STEP = 110.0
#: Fraction of a part's outward radial distance added on top of BASE_STEP, so
#: parts already far from centre fan out further than parts near it.
GAIN = 0.45
_EPS = 1e-6
_AXIS = {"X": 0, "Y": 1, "Z": 2}


def _center(placed) -> tuple[float, float, float]:
    """A part's world-space centre: the midpoint of its LOCAL bounding box
    mapped through its ``world_frame``. A representative centroid for direction
    work — cheaper than meshing the world solid and free of the in-place
    tessellation hazard ``Placed.world_solid`` warns about (the read is on the
    local cached solid)."""
    bb = placed.component.bounding_box()
    local_c = ((bb.xmin + bb.xmax) / 2.0,
               (bb.ymin + bb.ymax) / 2.0,
               (bb.zmin + bb.zmax) / 2.0)
    return placed.world_frame.transform_point(local_c)


def _unit(v):
    if not all(math.isfinite(c) for c in v):
        return None
    n = math.sqrt(sum(c * c for c in v))
    if n < _EPS:
        return None
    return tuple(c / n for c in v)


def _datum_axis_direction(placed, radial):
    datum = placed.component.datums.get("axis")
    if datum is None:
        return None
    direction = _unit(
        placed.world_frame.transform_direction(datum.z_axis)
    )
    if direction is None:
        return None
    projection = sum(
        radial[index] * direction[index] for index in range(3)
    )
    if projection < -_EPS:
        direction = tuple(-value for value in direction)
    return direction


def _sum_unit(normals):
    """Sum a list of unit normals and re-normalise, or ``None`` if they cancel
    (|sum| < EPS) — the interior-joist case, where opposed bearings collapse."""
    if not normals:
        return None
    s = [0.0, 0.0, 0.0]
    for n in normals:
        for k in range(3):
            s[k] += n[k]
    return _unit(s)


def _axis_normal(sign: float, i: int):
    n = [0.0, 0.0, 0.0]
    n[i] = sign
    return tuple(n)


def derive_explode_vectors(assembly, contacts: dict | None = None) -> dict:
    """Per-part explode offsets (mm), display-name-keyed (the key the viewer
    payload joins on). ``contacts`` is a resolved validation spec (the dict
    ``SpecDetail.validation_spec()`` returns: ``bearings`` as
    ``(a, b, axis, area)`` tuples, ``through_holes`` as
    ``(fastener, plates, axis, ...)`` tuples). Pass ``None`` for a bare view
    assembly with no contact data — every part then derives from the radial
    fallback. See the module docstring for the full rule."""
    parts = list(assembly.parts)
    if not parts:
        return {}
    centers = {p.name: _center(p) for p in parts}
    vals = list(centers.values())
    asm_c = tuple(sum(c[k] for c in vals) / len(vals) for k in range(3))

    # Existing/context bodies (the live trunk, the boulder) are the FIXED
    # reference frame the built parts pull away from — they must never explode,
    # or the view reads as a tree flying apart. Pinned at zero here, using the
    # SAME existing/context predicate the tooltip payload keys its EXISTING badge
    # on. (An authored explode vector still wins verbatim: it never reaches this
    # derivation — see build_viewer_payload._explode_for — so a spec that
    # deliberately explodes a context body keeps that choice.)
    from . import _existing

    normals: dict[str, list] = {p.name: [] for p in parts}
    if contacts:
        for entry in contacts.get("bearings", []):
            a, b, axis = entry[0], entry[1], entry[2]
            i = _AXIS.get(axis)
            if i is None:
                continue
            ca, cb = centers.get(a.name), centers.get(b.name)
            if ca is None or cb is None:
                continue
            d = ca[i] - cb[i]
            if abs(d) < _EPS:
                continue
            s = 1.0 if d > 0 else -1.0
            normals[a.name].append(_axis_normal(s, i))
            normals[b.name].append(_axis_normal(-s, i))
        for th in contacts.get("through_holes", []):
            fastener, plates, axis = th[0], th[1], th[2]
            i = _AXIS.get(axis)
            if i is None or fastener.name not in centers:
                continue
            pcs = [centers[pl.name] for pl in plates if pl.name in centers]
            if not pcs:
                continue
            mean_i = sum(pc[i] for pc in pcs) / len(pcs)
            d = centers[fastener.name][i] - mean_i
            if abs(d) < _EPS:
                continue
            normals[fastener.name].append(_axis_normal(1.0 if d > 0 else -1.0, i))

    out: dict = {}
    for p in sorted(parts, key=lambda p: p.name):
        name = p.name
        if _existing(p.component):
            out[name] = (0.0, 0.0, 0.0)
            continue
        c = centers[name]
        radial = tuple(c[k] - asm_c[k] for k in range(3))
        direction = (
            _sum_unit(normals[name])
            or _datum_axis_direction(p, radial)
            or _unit(radial)
            or (0.0, 0.0, 1.0)
        )
        proj = abs(sum(radial[k] * direction[k] for k in range(3)))
        mag = BASE_STEP + GAIN * proj
        out[name] = tuple(mag * direction[k] for k in range(3))
    return out


def derive_vertical_stack_explode(assembly, step: float = 95.0) -> dict:
    """Explode offsets for a small COAXIAL stack that pulls apart vertically —
    the pier-foundation zoom (Panel E): a precast block on grade, a standoff
    post base on the block, the leg seated in the base. These parts share an
    X/Y footprint and differ only in height, so their honest pull-apart axis is
    unambiguously Z, ranked by elevation. Ordering the parts by centre Z (ties
    broken by name) and spreading them ``step`` mm apart per rank about the
    stack midpoint shows the standoff air gap the whole panel exists to show.
    Deterministic: pure function of the parts' heights and ``step``."""
    parts = list(assembly.parts)
    if not parts:
        return {}
    centers = {p.name: _center(p) for p in parts}
    order = sorted(parts, key=lambda p: (centers[p.name][2], p.name))
    mid = (len(order) - 1) / 2.0
    return {p.name: (0.0, 0.0, (rank - mid) * step)
            for rank, p in enumerate(order)}
