"""Build provenance: single-sourced mesh tolerance + geometry content-hashes.

The tolerance constants live here (not in ``rendering/export.py``) so
``core`` stays free of any dependency on ``rendering``: ``rendering/export.py``
imports these constants and calls :func:`build_manifest`, while this module
never imports anything from ``rendering`` — ``rendering`` already depends on
``core`` transitively (via ``assemblies``), so the reverse direction would be
a circular import.

Re-running a detail and diffing two ``build_manifest()`` outputs *is* the
geometric-regression check: an unexpected hash change means the mesh moved.

The geometric acceptance thresholds a detail validates against
(``detailgen.core.config.Tolerances``) are a separate, per-detail-overridable
surface. The mesh tolerances below are deliberately NOT ``Tolerances``
fields: they control the tessellation ``geometry_hash`` hashes, so they must
stay a single fixed constant across every build and every detail — if they
varied per-detail like ``Tolerances`` does, identical geometry could hash
differently depending on which detail built it, and manifests would no
longer be comparable.

Per-part hashing (``build_manifest``) never tessellates a WORLD-transformed
solid or the assembly's fused compound. Each placed part's hash is
``H(local_geometry_digest, canonical_transform_digits)`` (see ``_part_hash``):
the local digest is ``geometry_hash`` of the component's LOCAL solid, memoized
per unique ``Component.cache_key()`` (``local_geometry_digest``) so N placed
instances of an equal component (identical fasteners, etc.) tessellate once
instead of once per placement; the transform digest is a cheap fixed-precision
serialization of the placed frame (``_transform_digest``) — no OCCT call at
all. ``assembly_hash`` combines the ordered per-part hashes
(``_combine_part_hashes``) rather than hashing the compound directly, which is
what made the old approach re-tessellate every world solid a second time (once
for its own part hash, once again as part of the fused compound).

Placement-sensitivity floor (exact, by design, and — unlike the old
world-vertex hash — independent of a part's size): ``_transform_digest``
rounds a frame's origin (translation, mm) at ``_HASH_ROUND_NDIGITS`` — the
same precision vertex hashing uses, so a uniform positional shift is
detected exactly as finely as it was before this change, regardless of part
size (a translation moves every vertex by the same amount, so there's no
lever-arm effect to begin with). Rotation is different: it rounds each
axis's unit-vector components at ``_HASH_ROT_ROUND_NDIGITS`` (much finer),
because the OLD approach hashed world vertex *positions*, where a rotation
by angle ``dtheta`` moves a vertex at lever arm ``L`` by ``~L * dtheta`` —
so its rotation sensitivity scaled with the part's reach (finer on bigger
parts, coarser near the rotation origin). Axis components carry no such
lever arm (they're unit vectors regardless of part size), so matching the
old approach's sensitivity at realistic part scales requires proportionally
finer rounding here. See ``_HASH_ROT_ROUND_NDIGITS`` for the exact floor and
the scale this was chosen to cover.
"""

from __future__ import annotations

import hashlib
import sys
from typing import Any

import cadquery as cq
from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
from OCP.BRepTools import BRepTools

from .diskcache import DiskCache, component_disk_key

#: Tessellation tolerances shared by every mesh exporter in ``rendering/``
#: (STL, PNG preview, GLB) and by geometry_hash below, so a hash computed
#: here is directly comparable to what got exported. Chosen as the finest of
#: the tolerances previously hardcoded per-call (STL 0.1, PNG preview 0.2,
#: GLB 0.1/0.15): a single conservative value preserves — and for the PNG
#: preview, improves — prior output quality everywhere.
MESH_TOL_LINEAR = 0.1
MESH_TOL_ANGULAR = 0.15

#: Vertex coordinates (mm) are rounded to this many decimal places before
#: hashing so float noise from repeated OCCT tessellation runs doesn't flap
#: the hash while still being far finer than anything visually meaningful.
#: ``_transform_digest`` also uses this for a frame's origin (translation,
#: mm) — a positional shift moves every vertex uniformly, so this is exactly
#: as sensitive to translation as the old world-vertex hash was.
_HASH_ROUND_NDIGITS = 6

#: Rounding precision for a frame's AXIS (rotation) components in
#: ``_transform_digest`` — deliberately much finer than
#: ``_HASH_ROUND_NDIGITS``. Axis components are unit-vector, so a rotation
#: by ``dtheta`` changes them by ``~dtheta`` regardless of part size; the
#: OLD world-vertex hash, by contrast, moved a vertex at lever arm ``L`` by
#: ``~L * dtheta``, so it could resolve angles as small as
#: ``~(0.5 * 10**-_HASH_ROUND_NDIGITS) / L`` radians on a part with reach
#: ``L`` — finer on bigger parts. At 12 decimal digits, this floor is
#: ``~0.5e-12`` rad (~2.9e-11 deg), which beats the old approach's
#: resolution even on a 20-meter part (``~1.4e-9`` deg) by roughly two
#: orders of magnitude — see
#: ``test_long_part_rotation_by_tiny_angle_changes_hash`` in
#: ``tests/test_reproducible_builds.py`` for the proof. This floor is exact
#: and, unlike the old approach, scale-independent: it neither improves for
#: large parts nor degrades for small ones.
_HASH_ROT_ROUND_NDIGITS = 12


def _shapes_of(workplane_or_solid: Any) -> list[cq.Shape]:
    """Normalize a Workplane or a bare Shape/Compound into a flat Shape list."""
    if isinstance(workplane_or_solid, cq.Workplane):
        return workplane_or_solid.vals()
    if isinstance(workplane_or_solid, cq.Shape):
        return [workplane_or_solid]
    raise TypeError(
        f"geometry_hash: expected a cq.Workplane or cq.Shape, got "
        f"{type(workplane_or_solid)!r}"
    )


def _norm_coord(c: float, ndigits: int = _HASH_ROUND_NDIGITS) -> float:
    """Round to ``ndigits`` and normalize negative zero (``round(-0.0, 6)``
    is a float that formats as ``"-0.0"``, not ``"0.0"`` — left alone, two
    geometrically-identical points/vectors straddling zero would hash
    differently depending on which side float error landed on)."""
    r = round(c, ndigits)
    return 0.0 if r == 0 else r


def _round_point(v: Any) -> tuple[float, float, float]:
    """Round a tessellation vertex's coordinates at ``_HASH_ROUND_NDIGITS``
    — see ``_norm_coord``."""
    return (_norm_coord(v.x), _norm_coord(v.y), _norm_coord(v.z))


def _round_vec3(
    v: tuple[float, float, float], ndigits: int = _HASH_ROUND_NDIGITS
) -> tuple[float, float, float]:
    """Same rounding/negative-zero normalization as ``_round_point``, for a
    plain ``(x, y, z)`` tuple (a ``Frame``'s ``origin``/axis properties)
    rather than a tessellation vertex object. ``ndigits`` defaults to
    ``_HASH_ROUND_NDIGITS`` (translation precision) but ``_transform_digest``
    passes ``_HASH_ROT_ROUND_NDIGITS`` for axis (rotation) components."""
    return (_norm_coord(v[0], ndigits), _norm_coord(v[1], ndigits),
            _norm_coord(v[2], ndigits))


def _rotate_to_min(tri: tuple[int, int, int]) -> tuple[int, int, int]:
    """Rotate a triangle's index tuple so it starts at its smallest index,
    preserving cyclic (winding) order — two listings of the same triangle
    starting from different vertices become equal, while a genuine winding
    flip (which flips the surface normal) still compares unequal."""
    i = tri.index(min(tri))
    return tri[i:] + tri[:i]


def _canonicalize(
    rounded_verts: list[tuple[float, float, float]],
    tris: list[tuple[int, int, int]],
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Reorder a tessellation's vertices and triangles into a form that
    depends only on the mesh's actual geometry, not on whatever order
    ``tessellate()`` happened to emit it in.

    Without this, geometry_hash's determinism rests entirely on OCCT
    happening to be order-stable release to release (or even call to call,
    e.g. under a future parallel mesher) — a silent, undetectable break.
    Vertices are sorted by their rounded coordinate tuple; triangles are
    remapped through the resulting old-index -> new-index table, each
    rotated to a canonical starting vertex (see ``_rotate_to_min``), and the
    triangle list itself is sorted so triangle *order* doesn't matter either.
    """
    order = sorted(range(len(rounded_verts)), key=lambda i: (rounded_verts[i], i))
    remap = {old: new for new, old in enumerate(order)}
    canon_verts = [rounded_verts[i] for i in order]
    canon_tris = sorted(
        _rotate_to_min(tuple(remap[i] for i in tri)) for tri in tris
    )
    return canon_verts, canon_tris


def geometry_hash(workplane_or_solid: Any) -> str:
    """sha256 hex digest of ``workplane_or_solid``'s tessellation at the fixed
    MESH_TOL_LINEAR/MESH_TOL_ANGULAR tolerance.

    Vertex coordinates are rounded before hashing (see
    ``_HASH_ROUND_NDIGITS``) and the whole mesh is run through
    ``_canonicalize`` so the digest is stable across repeated builds of
    identical geometry (including differently-ordered inputs, e.g. parts
    added to an assembly in a different order) but changes whenever the
    actual shape does (a parameter, a fillet, a placement). Triangle
    connectivity is hashed too, so a re-triangulation with the same vertices
    but different connectivity still flips the hash. STEP bytes are
    deliberately never hashed — they embed export timestamps and would make
    every build's hash unique regardless of geometry.

    Before tessellating, any cached triangulation on the shape is cleared
    (``BRepTools.Clean_s``). ``Shape.tessellate()`` calls OCCT's
    ``BRepMesh_IncrementalMesh`` in *relative*-deflection mode, and a prior
    mesh at any tolerance whose *actual* achieved deflection is finer than
    what MESH_TOL_LINEAR/ANGULAR would produce satisfies OCCT's "already
    meshed finely enough" check — so a shape tessellated by an exporter
    (e.g. GLB at tolerance 0.08) before ``geometry_hash`` runs on it would
    silently hash that stale mesh instead of a fresh one at the canonical
    tolerance, making the hash depend on export order/history rather than
    geometry alone. Clearing first forces every hash to remesh at exactly
    MESH_TOL_LINEAR/ANGULAR regardless of what ran on the shape earlier;
    the remesh cost is small and, since ``mesh()`` remeshes on demand
    whenever no cached triangulation satisfies the request, a later
    exporter simply remeshes at its own tolerance afterward — no export
    output is affected.

    ``Clean_s``+``tessellate`` run on a COPY of each shape
    (``BRepBuilderAPI_Copy``), never the caller's original — discovered
    while building S3c's persistent caches: meshing a shape can shift its
    OWN subsequent ``BoundingBox()`` (even the "exact",
    non-triangulation-based ``AddOptimal_s`` computation cadquery defaults
    to) by a real, non-negligible amount on borderline/tangent geometry —
    up to ~0.005 mm observed on a tangent beam-to-trunk case, orders of
    magnitude past this module's own rounding floors. That was always a
    latent hazard in this function, harmless only because, before S3c,
    nothing ever called ``geometry_hash`` earlier than RENDER time (after
    every validation/geometry read had already happened). S3c's verdict
    cache calls ``local_geometry_digest`` for a cache KEY during
    validation itself, and its solid cache can trigger a digest at BUILD
    time — both now earlier than any downstream bounding-box/boolean read
    on the same shape — so the mutation is no longer safe to leave in
    place. Tessellating a copy costs one extra (cheap) topology copy and
    leaves the original untouched; the digest is unaffected (the copy is
    geometrically identical to the original at the moment it's taken).
    """
    h = hashlib.sha256()
    for shape in _shapes_of(workplane_or_solid):
        copied = BRepBuilderAPI_Copy(shape.wrapped).Shape()
        BRepTools.Clean_s(copied)
        shape = cq.Shape.cast(copied)
        verts, tris = shape.tessellate(MESH_TOL_LINEAR, MESH_TOL_ANGULAR)
        rounded = [_round_point(v) for v in verts]
        canon_verts, canon_tris = _canonicalize(rounded, tris)
        h.update(len(canon_verts).to_bytes(8, "big"))
        for x, y, z in canon_verts:
            h.update(f"{x},{y},{z}\n".encode())
        h.update(len(canon_tris).to_bytes(8, "big"))
        for tri in canon_tris:
            h.update(f"{tri[0]},{tri[1]},{tri[2]}\n".encode())
    return h.hexdigest()


def _versions() -> dict[str, str]:
    versions = {
        "python": sys.version.split()[0],
        "cadquery": getattr(cq, "__version__", "unknown"),
    }
    try:
        import OCP

        versions["ocp"] = getattr(OCP, "__version__", "unknown")
    except ImportError:  # pragma: no cover - OCP always ships with cadquery
        pass
    return versions


#: Per-process memo of ``geometry_hash(component.solid)`` keyed by
#: ``Component.cache_key()``. Distinct from ``core.base._SOLID_CACHE`` (which
#: avoids redundant ``_build()`` calls): even where two placed parts already
#: share the identical built solid object, without this a naive per-part
#: ``geometry_hash`` call would still redo the Clean_s + tessellate +
#: canonicalize work for every placement of an otherwise-identical component.
_local_digest_cache: dict[tuple, str] = {}


def _reset_local_digest_cache() -> None:
    """Test helper: clear ``_local_digest_cache``. Only needed by tests that
    assert exact cache-hit counts; normal operation never invalidates this."""
    _local_digest_cache.clear()


#: Persistent (cross-run) tier of the digest memo above — S3c lever (b)'s
#: companion cache: ``core.base``'s solid cache persists BREP bytes only
#: (see its docstring for why NOT the digest too); this is where a
#: component's geometry digest gets persisted instead, the first time
#: ANY process actually computes one. Keyed identically to the solid
#: cache (``diskcache.component_disk_key``) so both tiers agree on "this
#: exact component" without duplicating that logic.
_DIGEST_DISK_CACHE = DiskCache("solid_digests")


def local_geometry_digest(component: Any) -> str:
    """``geometry_hash`` of ``component``'s LOCAL (untransformed) solid,
    memoized per unique ``component.cache_key()`` — the
    ``local_geometry_digest`` half of a part hash (see ``_part_hash``).
    Computed once per distinct component geometry no matter how many
    ``Placed`` parts in the assembly reference an equal component (e.g. 8
    identical washers tessellate once, not 8 times) — the in-run memo
    below (``_local_digest_cache``) is checked first, exactly as before
    S3c.

    Beneath that in-run memo, a persistent cross-run tier
    (``_DIGEST_DISK_CACHE``): on a miss there too, this calls
    ``geometry_hash(component.solid)`` (identical to pre-S3c behavior —
    same call, same timing, same cost) and persists the result, so every
    FUTURE process — cold or warm on ``core.base``'s solid cache either
    way — skips the tessellation entirely from then on.

    Why not compute+persist this at solid-cache WRITE time instead (in
    ``core.base``, alongside the BREP), closing the gap completely? Tried
    first; reverted. Two reasons: (1) it would force every build to
    tessellate, including the plain "assemble + validate, never render"
    CLI loop that today never pays that cost — a real regression for the
    scenario the whole S3 effort targets; (2) `geometry_hash` used to
    mutate its OWN input shape's later `BoundingBox()` on
    borderline/tangent geometry (fixed at the source in `geometry_hash`
    itself — tessellate a COPY, never the original — see that function's
    docstring), and calling it any earlier than the pre-existing pipeline
    did was what surfaced that bug in the first place while this cache was
    being built. Computing the digest here, at its ORIGINAL call site and
    timing, avoids re-introducing either risk.

    No round-trip gap: even when `component.solid` came from a BREP reload
    (`core.base`'s solid cache was warm) and this is the first time any
    process computes a digest for this component (digest cache cold),
    `geometry_hash` on the RELOADED shape equals `geometry_hash` on a fresh
    build, bit-for-bit. That was NOT true while the solid cache serialized
    ASCII BREP: an ASCII round trip drifted control points by ~1e-10 mm,
    occasionally tipping one mesh vertex across `_HASH_ROUND_NDIGITS`'s
    rounding boundary, so a digest derived from a reloaded shape could differ
    from the fresh one — the digest tier then memoized whichever was computed
    first and masked the divergence until the tiers desynced, at which point
    the persisted assembly_hash became a function of cache history (task #14 /
    R36). `core.diskcache.brep_dumps` now serializes BINARY BREP, which stores
    doubles exactly, so the round trip is tessellation-faithful; see
    tests/test_persistent_caches.py::test_solid_cache_round_trip and
    ::test_tree_attachment_assembly_hash_is_cache_history_independent."""
    key = component.cache_key()
    digest = _local_digest_cache.get(key)
    if digest is not None:
        return digest
    disk_key = component_disk_key(component)
    persisted = _DIGEST_DISK_CACHE.get(disk_key)
    if persisted is not None:
        try:
            digest = persisted.decode("ascii")
        except Exception:
            digest = None
    if digest is None:
        digest = geometry_hash(component.solid)
        try:
            _DIGEST_DISK_CACHE.put(disk_key, digest.encode("ascii"))
        except Exception:
            pass
    _local_digest_cache[key] = digest
    return digest


def _transform_digest(frame: Any) -> str:
    """Fixed-precision digest of a world ``Frame``: origin plus all three
    axes, which together fully determine the rigid transform. This is the
    ``canonical_transform_digits`` half of a part hash — cheap (no OCCT
    call, no tessellation) and, within the floors below, exact: any
    placement change at or above them always flips the part hash without
    re-tessellating anything.

    Two different precisions, deliberately: the origin (translation) is
    rounded at ``_HASH_ROUND_NDIGITS`` — matching vertex-hashing precision,
    since a translation shifts every vertex uniformly regardless of part
    size, so this exactly reproduces the old approach's translation
    sensitivity. The three axes (rotation) are rounded at the much finer
    ``_HASH_ROT_ROUND_NDIGITS`` instead, because axis components are
    unit-vector — a rotation changes them by an amount independent of part
    size, unlike the old world-vertex hash, whose rotation sensitivity
    scaled with a part's lever arm. See ``_HASH_ROT_ROUND_NDIGITS`` for the
    exact resulting angular floor (and why it beats the old approach even
    at realistic multi-meter part scales)."""
    h = hashlib.sha256()
    ox, oy, oz = _round_vec3(frame.origin)
    h.update(f"{ox},{oy},{oz}\n".encode())
    for vec in (frame.x_axis, frame.y_axis, frame.z_axis):
        x, y, z = _round_vec3(vec, _HASH_ROT_ROUND_NDIGITS)
        h.update(f"{x},{y},{z}\n".encode())
    return h.hexdigest()


def _part_hash(local_digest: str, frame: Any) -> str:
    """A placed part's identity hash: local geometry combined with its
    resolved world transform. Two parts with an equal component (same
    ``local_digest``) at different placements (different ``frame``) still
    get different part hashes; moving a part by at least
    ``_transform_digest``'s translation/rotation floor, or changing any
    parameter of its component, changes this."""
    h = hashlib.sha256()
    h.update(local_digest.encode())
    h.update(_transform_digest(frame).encode())
    return h.hexdigest()


def relative_transform_digest(frame_a: Any, frame_b: Any) -> str:
    """Digest of ``frame_a`` expressed in ``frame_b``'s local coordinates
    (``frame_b.inverse().compose(frame_a)``) — invariant under any
    SIMULTANEOUS rigid motion applied to both frames: composing both by
    the same motion ``M`` cancels algebraically,
    ``(M∘frame_b).inverse() ∘ (M∘frame_a) == frame_b.inverse() ∘ frame_a``.

    For ``validation.checks``'s persistent verdict cache (S3c lever d):
    use this key for a pairwise check whose result depends ONLY on the two
    parts' RELATIVE pose — a boolean-intersection volume or a true
    min-distance, both rigid-motion invariant — so a whole-assembly move
    that leaves a pair's relative placement untouched still hits. NEVER
    use this for a check that reads a WORLD-frame axis or coordinate
    directly (a bounding box computed against world X/Y/Z, or a push along
    a fixed world axis) — see :func:`world_part_digest` for those; each
    check function in ``validation.checks`` documents which one applies to
    it and why."""
    return _transform_digest(frame_b.inverse().compose(frame_a))


def world_part_digest(component: Any, frame: Any) -> str:
    """A placed part's full identity for a check that reads its ABSOLUTE
    world pose — the identical construction as a manifest part hash
    (``_part_hash``), exposed publicly here for ``validation.checks``'s
    verdict-cache keys (``check_contact``/``check_bearing``/
    ``check_through_hole`` — see :func:`relative_transform_digest` for why
    those specifically can't use a relative-only key)."""
    return _part_hash(local_geometry_digest(component), frame)


def _combine_part_hashes(part_hashes: list[str]) -> str:
    """Combine ordered per-part hashes into one assembly hash, independent of
    the order parts were added in. Sorting the hash STRINGS themselves
    (never a part's id/name, and never the parts list order) before
    combining is what gives this the same "insertion order doesn't matter"
    guarantee the old whole-compound approach got for free from
    ``geometry_hash``'s own mesh-level vertex/triangle canonicalization.
    Prefixing with the part count keeps multiplicity significant: two
    assemblies with the same set of distinct hash values but a different
    count (e.g. an accidental duplicate part) must not collide."""
    h = hashlib.sha256()
    h.update(len(part_hashes).to_bytes(8, "big"))
    for ph in sorted(part_hashes):
        h.update(ph.encode())
    return h.hexdigest()


def build_manifest(detail) -> dict:
    """Per-placed-part geometry hashes, a whole-assembly hash, and the
    toolchain versions the build ran under. ``detail`` is a
    ``DetailAssembly``.

    Each part hash is ``H(local_geometry_digest, canonical_transform)`` (see
    ``_part_hash``) instead of a fresh tessellation of that part's
    WORLD-transformed solid: the local digest is shared across every placed
    instance of an equal component (``local_geometry_digest``) and the
    transform digest is a cheap fixed-precision serialization
    (``_transform_digest``), so this never re-tessellates a world solid or
    the assembly's fused compound at all. ``assembly_hash`` is combined from
    the ordered per-part hashes (``_combine_part_hashes``), preserving the
    add-order independence the old compound-tessellation approach gave for
    free."""
    parts = []
    part_hashes = []
    for p in detail.parts:
        ph = _part_hash(local_geometry_digest(p.component), p.world_frame)
        parts.append({"name": p.name, "geometry_hash": ph})
        part_hashes.append(ph)
    return {
        "assembly_hash": _combine_part_hashes(part_hashes),
        "parts": parts,
        "versions": _versions(),
    }
