"""Task 5 — reproducible builds: geometry content-hashes + Blender texture
seeding.

Covers: identical builds hash identically, a parameter change flips the
hash, build_manifest's structure, and (since _blender_render.py runs INSIDE
Blender and can't be imported here) a static source-parse check that every
procedural texture node is seeded.
"""

import inspect
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

from detailgen.core import IN
from detailgen.core import buildinfo as buildinfo_mod
from detailgen.core.base import _reset_solid_cache
from detailgen.core.buildinfo import (
    MESH_TOL_LINEAR,
    MESH_TOL_ANGULAR,
    _canonicalize,
    _reset_local_digest_cache,
    _round_point,
    build_manifest,
    geometry_hash,
)
from detailgen.components import Lumber
from detailgen.components.fasteners import Washer
from detailgen.components.tree import TreeTrunk
from detailgen.assemblies import DetailAssembly
from detailgen.rendering import export as export_mod
from detailgen.rendering.export import export_manifest, export_glb

BLENDER_SCRIPT = (
    Path(__file__).resolve().parents[1] / "src" / "rendering" / "_blender_render.py"
)
#: W2-8 split the ShaderNodeTex* node-tree builders out of BLENDER_SCRIPT
#: into `_blender_materials.py` (so the material-tag dispatch is testable
#: without a Blender install — see that module's docstring); the seeding
#: rule below binds wherever those builders actually live now.
BLENDER_MATERIALS_SCRIPT = BLENDER_SCRIPT.with_name("_blender_materials.py")


def test_geometry_hash_is_stable_across_rebuilds():
    """Building the same component twice yields identical hashes — the hash
    must depend only on geometry, not object identity or build order.
    ``_reset_solid_cache`` forces the second build to be a genuinely
    independent ``_build()`` call: without it, ``core.base``'s process-wide
    solid cache makes two equal-params ``Lumber(...)`` instances share the
    literal same solid object (``a.val().wrapped is b.val().wrapped`` would
    be ``True``), so the test would only prove ``hash(x) == hash(x)``."""
    a = Lumber("2x4", length=2 * IN).solid
    _reset_solid_cache()
    b = Lumber("2x4", length=2 * IN).solid
    assert a.val().wrapped is not b.val().wrapped  # genuinely independent builds
    assert geometry_hash(a) == geometry_hash(b)


def test_geometry_hash_changes_with_parameter():
    base = Lumber("2x4", length=2 * IN).solid
    changed = Lumber("2x4", length=3 * IN).solid
    assert geometry_hash(base) != geometry_hash(changed)


def test_mesh_tolerance_constants_are_single_sourced():
    """Every exporter in rendering/export.py must default to the EXACT same
    constant objects this module hashes geometry at — not just some positive
    number — so a disconnected copy defined in export.py can't silently
    drift from the canonical constants. ``is`` (not just ``==``) catches
    that: a redefined ``MESH_TOL_LINEAR = 0.1`` in export.py would equal
    this module's value without being the same imported object."""
    assert MESH_TOL_LINEAR > 0
    assert MESH_TOL_ANGULAR > 0
    assert export_mod.MESH_TOL_LINEAR is MESH_TOL_LINEAR
    assert export_mod.MESH_TOL_ANGULAR is MESH_TOL_ANGULAR

    for fn_name in ("export_stl", "export_png", "export_glb"):
        params = inspect.signature(getattr(export_mod, fn_name)).parameters
        linear = next(p for p in params.values() if "linear" in p.name.lower()
                      or p.name in ("tolerance", "mesh_tolerance"))
        angular = next(p for p in params.values() if "angular" in p.name.lower())
        assert linear.default is MESH_TOL_LINEAR, fn_name
        assert angular.default is MESH_TOL_ANGULAR, fn_name


def test_build_manifest_structure():
    detail = DetailAssembly("hash test")
    detail.add(Lumber("2x4", length=2 * IN, name="a"))
    detail.add(Lumber("2x4", length=3 * IN, name="b"), at=(0, 2 * IN, 0))

    manifest = build_manifest(detail)

    assert set(manifest) == {"assembly_hash", "parts", "versions"}
    assert isinstance(manifest["assembly_hash"], str) and manifest["assembly_hash"]
    assert [p["name"] for p in manifest["parts"]] == ["a", "b"]
    for part in manifest["parts"]:
        assert isinstance(part["geometry_hash"], str) and part["geometry_hash"]
    # two different-length parts must not collide
    assert manifest["parts"][0]["geometry_hash"] != manifest["parts"][1]["geometry_hash"]
    assert manifest["versions"]["python"]
    assert manifest["versions"]["cadquery"]


def test_canonicalize_is_invariant_under_vertex_and_triangle_permutation():
    """Hand-built proof that _canonicalize produces identical output for two
    encodings of the *same* triangle, listed starting from a DIFFERENT
    vertex of the winding (winding preserved) — this is what makes
    geometry_hash independent of whatever order a future OCCT tessellate()
    happens to emit, rather than relying on today's OCCT being order-stable
    by accident.

    The 3 points are chosen already sorted in ascending coordinate order
    (v0 < v1 < v2), so ``_canonicalize``'s own vertex-sort produces the
    IDENTITY remap for both encodings below — the only thing exercised is
    ``_rotate_to_min`` itself. This matters: a hand-picked example whose
    winding happens to already start at vertex 0 (as the file's original
    A/B/C example did) never calls into ``_rotate_to_min`` at all, since
    its remapped tuple already starts at its minimum — neutering that
    helper to a no-op still passes such an example. Starting the SAME
    winding at v1 here (v1,v2,v0) forces a real rotation to line up with
    the v0-first encoding (v0,v1,v2)."""
    v0, v1, v2 = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)
    verts = [v0, v1, v2]

    tris_start_at_v0 = [(0, 1, 2)]  # v0 -> v1 -> v2
    tris_start_at_v1 = [(1, 2, 0)]  # v1 -> v2 -> v0, same winding, different start

    assert _canonicalize(verts, tris_start_at_v0) == _canonicalize(verts, tris_start_at_v1)


def test_canonicalize_distinguishes_reversed_winding():
    """Sanity check the helper isn't accidentally order-blind altogether —
    reversing a triangle's winding (which flips its surface normal) must
    still change the canonical form."""
    a, b, c = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
    verts = [a, b, c]
    forward = _canonicalize(verts, [(0, 1, 2)])
    reversed_ = _canonicalize(verts, [(0, 2, 1)])
    assert forward != reversed_


def test_round_point_normalizes_negative_zero():
    """round(-0.0, 6) is a float that formats as '-0.0', not '0.0' — without
    normalizing it, two geometrically-identical points straddling zero would
    hash differently depending on which side of zero float error landed on.
    Tuple equality alone can't catch a missing normalization: Python's
    ``-0.0 == 0.0``, so ``(-0.0, ...) == (0.0, ...)`` is True either way —
    the sign bit must be checked directly with ``math.copysign``."""

    class _V:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z

    result = _round_point(_V(-0.0, 1.0, -0.0))
    assert result == (0.0, 1.0, 0.0)
    assert math.copysign(1.0, result[0]) == 1.0, "x came back as -0.0"
    assert math.copysign(1.0, result[2]) == 1.0, "z came back as -0.0"


def test_assembly_hash_is_independent_of_part_add_order():
    """Two assemblies with the same parts added in a different order must
    hash identically — a real-world stand-in for "OCCT tessellates a
    differently-ordered compound differently", which canonicalization must
    absorb."""
    forward = DetailAssembly("order-forward")
    forward.add(Lumber("2x4", length=2 * IN, name="a"))
    forward.add(Lumber("2x4", length=3 * IN, name="b"), at=(0, 2 * IN, 0))

    backward = DetailAssembly("order-backward")
    backward.add(Lumber("2x4", length=3 * IN, name="b"), at=(0, 2 * IN, 0))
    backward.add(Lumber("2x4", length=2 * IN, name="a"))

    assert geometry_hash(forward.compound()) == geometry_hash(backward.compound())


def test_build_manifest_is_reproducible():
    detail = DetailAssembly("repro")
    detail.add(Lumber("2x4", length=2 * IN, name="a"))
    first = build_manifest(detail)

    detail2 = DetailAssembly("repro")
    detail2.add(Lumber("2x4", length=2 * IN, name="a"))
    second = build_manifest(detail2)

    assert first["assembly_hash"] == second["assembly_hash"]
    assert first["parts"][0]["geometry_hash"] == second["parts"][0]["geometry_hash"]


def test_geometry_hash_is_independent_of_prior_tessellation_tolerance():
    """OCCT caches a shape's triangulation on the underlying TopoDS_Shape, and
    ``BRepMesh_IncrementalMesh``'s relative-deflection mode means a shape
    meshed once at a *finer* effective tolerance (e.g. 0.08, matching the
    details' GLB export) than ``geometry_hash``'s
    canonical MESH_TOL_LINEAR/ANGULAR (0.1/0.15) is never remeshed — the
    stale finer mesh gets reused instead of a fresh 0.1/0.15 one, making the
    hash depend on whatever tessellated the shape earlier in the process. A
    flat-faced solid (e.g. Lumber) can't reproduce this: box faces
    triangulate identically at any tolerance. A large-diameter cylinder
    (TreeTrunk, a plain context body) can, at a size representative of
    tree_attachment's real 20" trunk."""
    trunk = TreeTrunk(diameter=20 * IN, height=6 * IN).solid.val()

    untouched_hash = geometry_hash(trunk)

    # Mesh at a finer tolerance than geometry_hash uses, simulating a prior
    # GLB export (tolerance=0.08) running before the hash is computed.
    trunk.tessellate(0.08, 0.12)

    assert geometry_hash(trunk) == untouched_hash


def test_assembly_hash_survives_glb_export(tmp_path):
    """Integration-level version of the unit test above: export_glb meshes
    at 0.08 (the details' GLB export tolerance), which must not leave the
    assembly's compound hashing differently
    afterward than it did before the export ran."""
    detail = DetailAssembly("hash-survives-glb")
    detail.add(TreeTrunk(diameter=20 * IN, height=6 * IN, name="trunk"))

    before = geometry_hash(detail.compound())
    export_glb(detail, tmp_path / "detail.glb", tolerance=0.08, angular_tolerance=0.12)
    after = geometry_hash(detail.compound())

    assert before == after


def test_export_manifest_rejects_reserved_build_key(tmp_path):
    detail = DetailAssembly("guard-test")
    detail.add(Lumber("2x4", length=2 * IN, name="a"))
    with pytest.raises(ValueError, match="build"):
        export_manifest(detail, tmp_path / "guard.manifest.json", extra={"build": "clobber"})


def test_export_manifest_carries_registered_rgba(tmp_path):
    detail = DetailAssembly("material-color-manifest")
    placed = detail.add(Lumber("2x4", length=2 * IN, name="color probe"))

    path = export_manifest(detail, tmp_path / "detail.manifest.json")
    part = json.loads(path.read_text())["parts"][0]

    assert part["material"] == placed.component.material_key
    assert part["rgba"] == list(placed.component.material.rgba)


#: ShaderNodeTex* types known to need no seed: ShaderNodeTexCoord emits
#: coordinates (not a procedural pattern) and ShaderNodeTexImage samples a
#: fixed image file, so neither has run-to-run stability to lose. Every
#: other ShaderNodeTex* type found in the file must be seeded — this is an
#: allowlist, not a blocklist, so a brand-new procedural texture type fails
#: loudly until someone makes a conscious call about it.
_NO_SEED_NEEDED = {"ShaderNodeTexCoord", "ShaderNodeTexImage"}


def test_every_procedural_texture_in_blender_script_is_seeded():
    """_blender_render.py runs INSIDE Blender (imports bpy) so it can't be
    imported or executed in this test environment. This is a static
    source-parse check instead: every ShaderNodeTex* node created by the
    material builders (now in _blender_materials.py — see BLENDER_MATERIALS_
    SCRIPT's comment) must either be passed through _seed_texture() or be in
    the explicit _NO_SEED_NEEDED allowlist above, so re-renders stay
    pixel-stable (item 3 of the task-5 brief) and adding a new texture type
    can't silently slip past this check unseeded."""
    source = BLENDER_SCRIPT.read_text() + "\n" + BLENDER_MATERIALS_SCRIPT.read_text()
    creations = re.findall(r'(\w+)\s*=\s*nt\.nodes\.new\("(ShaderNodeTex\w+)"\)', source)

    assert creations, "expected to find texture node creations to check"
    for var, node_type in creations:
        if node_type in _NO_SEED_NEEDED:
            continue
        assert re.search(rf"_seed_texture\(\s*{re.escape(var)}\b", source), (
            f"{var} ({node_type}) in {BLENDER_SCRIPT.name}/"
            f"{BLENDER_MATERIALS_SCRIPT.name} has no _seed_texture() call and "
            f"is not in _NO_SEED_NEEDED — either seed it or add it to the "
            f"allowlist as a conscious decision"
        )


# -- Task S3b — hash restructure (H(local_digest, transform)) + dedup -----
#
# build_manifest no longer tessellates a part's WORLD-transformed solid or
# the assembly's fused compound (see core/buildinfo.py's module docstring);
# each part hash is H(local_geometry_digest, canonical_transform_digits) and
# assembly_hash combines the ordered per-part hashes. These tests are the
# semantics proof the task brief requires: everything the old
# compound-tessellation approach was sensitive to must still flip the hash,
# and the new caching must be provably exercised (not just assumed safe).


def test_moving_a_part_changes_its_hash_and_assembly_hash():
    stationary = DetailAssembly("move-stationary")
    stationary.add(Lumber("2x4", length=2 * IN, name="a"))
    moved = DetailAssembly("move-moved")
    moved.add(Lumber("2x4", length=2 * IN, name="a"), at=(0, 1 * IN, 0))

    m1, m2 = build_manifest(stationary), build_manifest(moved)
    assert m1["parts"][0]["geometry_hash"] != m2["parts"][0]["geometry_hash"]
    assert m1["assembly_hash"] != m2["assembly_hash"]


def test_changing_one_component_param_changes_its_hash_and_assembly_hash():
    base = DetailAssembly("param-base")
    base.add(Lumber("2x4", length=2 * IN, name="a"))
    changed = DetailAssembly("param-changed")
    changed.add(Lumber("2x4", length=3 * IN, name="a"))

    m1, m2 = build_manifest(base), build_manifest(changed)
    assert m1["parts"][0]["geometry_hash"] != m2["parts"][0]["geometry_hash"]
    assert m1["assembly_hash"] != m2["assembly_hash"]


def test_adding_or_removing_a_part_changes_assembly_hash():
    one_part = DetailAssembly("count-one")
    one_part.add(Lumber("2x4", length=2 * IN, name="a"))

    two_parts = DetailAssembly("count-two")
    two_parts.add(Lumber("2x4", length=2 * IN, name="a"))
    two_parts.add(Lumber("2x4", length=2 * IN, name="b"), at=(0, 2 * IN, 0))

    assert (build_manifest(one_part)["assembly_hash"]
            != build_manifest(two_parts)["assembly_hash"])


def test_duplicate_part_multiplicity_changes_assembly_hash():
    """Real coverage for the count-prefix multiplicity-collision guard in
    ``_combine_part_hashes``, which the test above doesn't actually exercise:
    its two assemblies differ by hash VALUE (different placements), so
    removing the count-prefix entirely still leaves them different. This
    test isolates multiplicity as the ONLY difference — one part, and the
    exact same part duplicated at the exact same placement (so both part
    hashes are byte-identical) — the accidental-duplicate-part scenario the
    count-prefix exists to catch."""
    one = DetailAssembly("dup-one")
    one.add(Lumber("2x4", length=2 * IN, name="a"))

    two_identical = DetailAssembly("dup-two")
    two_identical.add(Lumber("2x4", length=2 * IN, name="a"))
    two_identical.add(Lumber("2x4", length=2 * IN, name="a2"))  # same params, same placement

    m1, m2 = build_manifest(one), build_manifest(two_identical)
    assert (m1["parts"][0]["geometry_hash"]
            == m2["parts"][0]["geometry_hash"]
            == m2["parts"][1]["geometry_hash"])
    assert m1["assembly_hash"] != m2["assembly_hash"]


def test_identical_components_at_different_placements_share_local_digest():
    """Two placed washers with equal params must tessellate their shared
    local solid exactly once (the lever-(a)/hash-restructure dedup this task
    exists to deliver) while still getting different part hashes, since
    their placements differ. Reset both process-wide caches first so an
    earlier test's Washer(0.5*IN) construction can't produce a false
    zero-calls result here."""
    _reset_solid_cache()
    _reset_local_digest_cache()

    calls = []
    original = buildinfo_mod.geometry_hash

    def counting_geometry_hash(x):
        calls.append(x)
        return original(x)

    buildinfo_mod.geometry_hash = counting_geometry_hash
    try:
        d = DetailAssembly("dedup-washers")
        d.add(Washer(0.5 * IN, name="w1"))
        d.add(Washer(0.5 * IN, name="w2"), at=(0, 1 * IN, 0))
        manifest = build_manifest(d)
    finally:
        buildinfo_mod.geometry_hash = original

    assert len(calls) == 1, (
        "expected the local solid shared by two identical washers to be "
        f"tessellated once, not {len(calls)} times"
    )
    assert (manifest["parts"][0]["geometry_hash"]
            != manifest["parts"][1]["geometry_hash"])


def test_build_manifest_assembly_hash_independent_of_part_add_order():
    """S2 guaranteed geometry_hash(compound) doesn't depend on add order;
    this is the same guarantee at the build_manifest/assembly_hash level,
    which is what actually gates outputs/consolidated's reuse cache
    (scripts/consolidated_report.py::process_detail)."""
    forward = DetailAssembly("bm-order-forward")
    forward.add(Lumber("2x4", length=2 * IN, name="a"))
    forward.add(Lumber("2x4", length=3 * IN, name="b"), at=(0, 2 * IN, 0))

    backward = DetailAssembly("bm-order-backward")
    backward.add(Lumber("2x4", length=3 * IN, name="b"), at=(0, 2 * IN, 0))
    backward.add(Lumber("2x4", length=2 * IN, name="a"))

    assert (build_manifest(forward)["assembly_hash"]
            == build_manifest(backward)["assembly_hash"])


def test_assembly_hash_is_stable_across_processes():
    """The hash-gated reuse cache in scripts/consolidated_report.py compares
    a freshly computed assembly_hash against one stored on disk from a
    PRIOR process invocation — so the hash must be stable not just within
    one process (test_build_manifest_is_reproducible already covers that)
    but across two independent, freshly-started interpreters."""
    script = (
        "from detailgen.core import IN\n"
        "from detailgen.assemblies import DetailAssembly\n"
        "from detailgen.components import Lumber\n"
        "from detailgen.core.buildinfo import build_manifest\n"
        "d = DetailAssembly('cross-process')\n"
        "d.add(Lumber('2x4', length=2 * IN, name='a'))\n"
        "d.add(Lumber('2x4', length=3 * IN, name='b'), at=(0, 2 * IN, 0))\n"
        "print(build_manifest(d)['assembly_hash'])\n"
    )
    runs = [
        subprocess.run([sys.executable, "-c", script], capture_output=True,
                       text=True, timeout=60)
        for _ in range(2)
    ]
    for r in runs:
        assert r.returncode == 0, r.stderr
    hashes = [r.stdout.strip() for r in runs]
    assert hashes[0] and hashes[0] == hashes[1]


def test_long_part_rotation_by_tiny_angle_changes_hash():
    """Code-review-flagged rotation-sensitivity floor: ``_transform_digest``
    hashes axis (rotation) UNIT-VECTOR components rather than world vertex
    positions, so its angular resolution is fixed and doesn't depend on a
    part's lever arm — unlike the old world-vertex hash, which could
    resolve rotations only as finely as ``~(rounding step) / L`` radians on
    a part with reach ``L`` (finer on bigger parts, coarser on small ones).
    ``_HASH_ROT_ROUND_NDIGITS`` (12) was chosen so this still beats the old
    approach's resolution even at a realistic large-part scale (~20m reach
    — see that constant's docstring for the exact numbers). Proved directly
    here: a ~20m-long Lumber rotated by an angle far smaller than anything a
    real build would ever need to distinguish (1e-5 degrees) still flips
    both the part hash and the assembly hash."""
    LONG_MM = 20_000.0  # ~20m: the reach this task's precision was sized for

    unrotated = DetailAssembly("rot-unrotated")
    unrotated.add(Lumber("2x4", length=LONG_MM, name="a"))

    rotated = DetailAssembly("rot-rotated")
    rotated.add(Lumber("2x4", length=LONG_MM, name="a"), rotate=[("Z", 1e-5)])

    m1, m2 = build_manifest(unrotated), build_manifest(rotated)
    assert m1["parts"][0]["geometry_hash"] != m2["parts"][0]["geometry_hash"]
    assert m1["assembly_hash"] != m2["assembly_hash"]
