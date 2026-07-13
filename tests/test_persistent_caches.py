"""S3c — persistent cross-run caches: BREP solid cache (lever b) and
per-pair validation-verdict cache (lever d).

Layout:
1. BREP round-trip fidelity (the mechanism ``core.diskcache.brep_dumps``/
   ``brep_loads`` — no ``Component``/cache-tier involvement yet).
2. Solid cache (``core.base.Component.solid``, tier 2): hit/miss counts,
   param-change invalidation, geometry-code-fingerprint invalidation,
   corrupt-entry-is-a-miss.
3. Verdict cache (``validation.checks``): per-check cacheability — which
   checks are relative-transform-invariant (interference, the floating
   connectivity link) vs. world-position-dependent (contact, bearing,
   through_hole) — proven by actually moving the WHOLE pair together and
   asserting hit vs. miss accordingly, not just asserted in prose.
4. Whole-detail equivalence: for all 4 shipped details, cache-warm findings
   == ``DETAILGEN_NO_CACHE=1`` findings, element by element.
"""

from __future__ import annotations

import json
from pathlib import Path

import cadquery as cq
import pytest

from detailgen.spec.compiler import compile_spec_file
from detailgen.assemblies import DetailAssembly
from detailgen.components import Lumber, TreeTrunk
from detailgen.components.fasteners import Washer
from detailgen.core import DEFAULT, IN, Component
from detailgen.core import base as base_mod
from detailgen.core import buildinfo as buildinfo_mod
from detailgen.core.base import _reset_solid_cache
from detailgen.core.buildinfo import _reset_local_digest_cache, geometry_hash
from detailgen.core.diskcache import DiskCache, brep_dumps, brep_loads
from detailgen.core.frame import Frame
from detailgen.validation import checks as checks_mod
from detailgen.validation.checks import (
    ValidationReport,
    check_bearing,
    check_contact,
    check_interference,
    check_no_floaters,
    validate_assembly,
)

DETAILS_DIR = Path(__file__).resolve().parents[1] / "details"


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Every test in this file gets its own empty on-disk cache root and
    fresh in-run memo caches, so tests can't see each other's entries and
    can't be polluted by whatever the real ``outputs/cache`` holds."""
    monkeypatch.setenv("DETAILGEN_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("DETAILGEN_NO_CACHE", raising=False)
    _reset_solid_cache()
    _reset_local_digest_cache()
    yield
    _reset_solid_cache()
    _reset_local_digest_cache()


# --------------------------------------------------------------------------- #
# 1. BREP round-trip fidelity
# --------------------------------------------------------------------------- #

#: The reviewer's named cases (review-visrevstores.md §1): a solid whose
#: ASCII-BREP round trip re-tessellated to a DIFFERENT geometry_hash than the
#: fresh build (the trunk cylinder + cut lumber from tree_attachment), plus the
#: original Lumber+holes+ease piece that first surfaced the drift. Every one
#: must now round-trip hash-faithfully through brep_dumps/brep_loads.
_ROUND_TRIP_CASES = [
    ("trunk_cylinder", lambda: TreeTrunk(20.0, 96.0)),
    ("cut_beam", lambda: Lumber("2x6", 24 * IN, full_length=60 * IN,
                                holes=[(0, 0, 10.0)])),
    ("lumber_holes_ease", lambda: Lumber("2x4", 6 * IN, ease_radius=1.0,
                                         holes=[(0, 0, 10.0)])),
]


@pytest.mark.parametrize("label,make", _ROUND_TRIP_CASES,
                         ids=[c[0] for c in _ROUND_TRIP_CASES])
def test_solid_cache_round_trip(label, make):
    """A solid serialized and reloaded through the cache's BREP primitive must
    re-tessellate to the IDENTICAL geometry_hash as the freshly-built solid —
    the tessellation-faithfulness contract the persistent cache stands on.

    Each of these shapes broke that contract under the old ASCII BREP writer:
    the reload's curve/surface control points differed by ~1e-10 mm, occasionally
    tipping one mesh vertex across geometry_hash's 6-decimal rounding boundary, so
    the reloaded geometry_hash != the fresh one (review-visrevstores.md §1, task
    #14). Binary BREP stores doubles exactly, so the round trip is now bit-faithful.
    Asserting the hash directly (not just volume/bbox/vertex COUNTS) is the point:
    counts matching while the hash flips is exactly the failure mode that masked
    the defect for so long."""
    original = make().solid
    fresh_hash = geometry_hash(original)

    data = brep_dumps(original.vals())
    reloaded = cq.Workplane("XY").newObject(brep_loads(data))

    # Faithful all the way down: exact geometry_hash, plus the volume/bbox/count
    # invariants the older assertion settled for.
    assert geometry_hash(reloaded) == fresh_hash
    assert reloaded.val().Volume() == pytest.approx(original.val().Volume(), rel=1e-9)
    bb_o, bb_r = original.val().BoundingBox(), reloaded.val().BoundingBox()
    for attr in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"):
        assert getattr(bb_r, attr) == pytest.approx(getattr(bb_o, attr), abs=1e-6)
    verts_o, tris_o = original.val().tessellate(0.1, 0.15)
    verts_r, tris_r = reloaded.val().tessellate(0.1, 0.15)
    assert len(verts_r) == len(verts_o)
    assert len(tris_r) == len(tris_o)


def test_solid_cache_digest_is_stable_across_a_cold_cache_cycle():
    """The system-level guarantee build_manifest/consolidated_report rely
    on: local_geometry_digest for a component must be IDENTICAL whether
    the persistent solid cache was cold or warm for it -- proven directly
    against a fresh (never-cached) build, not merely asserted.

    Goes through local_geometry_digest (not a bare geometry_hash call) on
    BOTH sides, matching the real API contract: local_geometry_digest is
    what persists a digest the first time any process computes one (see
    its docstring) -- a bare geometry_hash call on a fresh build doesn't
    write anything to the persistent digest tier, so it wouldn't exercise
    the guarantee this test is actually checking."""
    from detailgen.core.buildinfo import local_geometry_digest

    fresh = Lumber("2x4", 6 * IN, ease_radius=1.0, holes=[(0, 0, 10.0)])
    canonical_digest = local_geometry_digest(fresh)  # cold: builds + persists digest

    _reset_solid_cache()
    _reset_local_digest_cache()
    reloaded_component = Lumber("2x4", 6 * IN, ease_radius=1.0, holes=[(0, 0, 10.0)])
    reloaded_component.solid  # warm: loads BREP from disk (no digest recompute)

    assert local_geometry_digest(reloaded_component) == canonical_digest


def _tree_attachment_assembly_hash():
    """assembly_hash of the freshly-recompiled tree_attachment detail, with the
    in-run memo tiers cleared so the on-disk cache state alone decides the
    build path. Left to whatever DETAILGEN_CACHE_DIR the caller set up."""
    from detailgen.core.buildinfo import build_manifest

    _reset_solid_cache()
    _reset_local_digest_cache()
    detail = compile_spec_file(DETAILS_DIR / "tree_attachment.spec.yaml")
    return build_manifest(detail.assembly)["assembly_hash"]


def test_tree_attachment_assembly_hash_is_cache_history_independent(tmp_path, monkeypatch):
    """The reproduced defect (review-visrevstores.md §1): tree_attachment's
    persisted assembly_hash was `8953…` cold but `fe34…` once the solid cache was
    warm and the digest tier had been rebuilt from a reloaded solid — the hash
    became a function of cache HISTORY, silently corrupting warm-cache doc builds.

    Same cache dir throughout (the autouse fixture points DETAILGEN_CACHE_DIR at
    tmp_path); only the cache STATE varies. All three build paths must agree, and
    must agree with the cold/no-cache truth — a fix that made warm==cold by
    changing the cold value would be caught by the DETAILGEN_NO_CACHE anchor."""
    import shutil

    cold = _tree_attachment_assembly_hash()  # empty cache: build + persist

    warm = _tree_attachment_assembly_hash()  # solid + digest both warm

    # Desync: force the digest tier to recompute from a BREP-reloaded solid while
    # the solid tier stays warm — the exact mixed state the reviewer isolated.
    shutil.rmtree(tmp_path / "solid_digests", ignore_errors=True)
    desync = _tree_attachment_assembly_hash()

    monkeypatch.setenv("DETAILGEN_NO_CACHE", "1")
    no_cache = _tree_attachment_assembly_hash()
    monkeypatch.delenv("DETAILGEN_NO_CACHE", raising=False)

    assert warm == cold
    assert desync == cold, (
        "digest tier rebuilt from a reloaded solid diverged from the fresh build "
        "— the persistent cache is not tessellation-faithful"
    )
    assert no_cache == cold


def test_digest_tier_desync_cannot_mask_an_unfaithful_reload(tmp_path):
    """The masking path, caught loudly and directly at the mechanism level: a
    single component's local_geometry_digest must be the SAME whether computed
    from a fresh build or from a BREP round trip. The old ASCII cache made these
    differ; the digest tier then memoized whichever was computed first, hiding
    the divergence until the tiers desynced. Comparing the two derivations head
    to head is what that memo was hiding."""
    from detailgen.core.buildinfo import local_geometry_digest

    beam = Lumber("2x6", 24 * IN, full_length=60 * IN, holes=[(0, 0, 10.0)])
    fresh_digest = geometry_hash(beam._build())  # never touches disk / reload

    reloaded = cq.Workplane("XY").newObject(brep_loads(brep_dumps(beam._build().vals())))
    assert geometry_hash(reloaded) == fresh_digest

    # And through the real memoized API on a cold cache (which builds fresh here):
    _reset_solid_cache()
    _reset_local_digest_cache()
    assert local_geometry_digest(
        Lumber("2x6", 24 * IN, full_length=60 * IN, holes=[(0, 0, 10.0)])
    ) == fresh_digest


def test_old_ascii_cache_format_is_not_reused_after_the_binary_bump(tmp_path):
    """The _SERIALIZATION_FORMAT bump (brep2): a component_disk_key written under
    the old ASCII regime must not be READ back after the switch to binary BREP —
    otherwise a warm cache would keep serving the ASCII-poisoned digest strings
    (a valid ASCII string decodes fine; nothing fails on it) and the fix would
    not reach an already-warm cache. Proven by writing an entry under a key with
    the format token stripped and showing the live key misses it."""
    from detailgen.core import buildinfo as buildinfo_mod
    from detailgen.core.diskcache import (
        _SERIALIZATION_FORMAT,
        component_disk_key,
    )

    beam = Lumber("2x6", 24 * IN, full_length=60 * IN)
    live_key = component_disk_key(beam)
    assert live_key.startswith(f"{_SERIALIZATION_FORMAT}|")

    # Simulate a pre-bump entry: same key with the format token removed, holding
    # a poisoned digest value that must never be served under the new key.
    old_style_key = live_key[len(_SERIALIZATION_FORMAT) + 1:]
    buildinfo_mod._DIGEST_DISK_CACHE.put(old_style_key, b"poisoned-old-digest")

    _reset_solid_cache()
    _reset_local_digest_cache()
    got = buildinfo_mod.local_geometry_digest(
        Lumber("2x6", 24 * IN, full_length=60 * IN)
    )
    assert got != "poisoned-old-digest"
    assert got == geometry_hash(beam._build())


def test_brep_round_trip_preserves_multi_solid_count_and_order():
    """A component whose local solid is >1 shape (none of the 4 shipped
    details currently produce one, per checks.py's _part_bbox docstring,
    but the cache must not silently assume single-solid)."""
    far = cq.Solid.makeBox(5, 5, 5, cq.Vector(0, 0, 0))
    near = cq.Solid.makeBox(3, 3, 3, cq.Vector(20, 0, 0))
    data = brep_dumps([far, near])
    reloaded = brep_loads(data)

    assert len(reloaded) == 2
    assert reloaded[0].Volume() == pytest.approx(125.0)
    assert reloaded[1].Volume() == pytest.approx(27.0)


def test_brep_loads_of_garbage_bytes_raises_not_silently_wrong():
    """brep_loads itself is allowed to raise (it's the LOW-level primitive);
    the solid cache's caller is what must convert this into a miss — see
    test_solid_cache_corrupt_entry_is_a_miss below."""
    with pytest.raises(Exception):
        brep_loads(b"not a brep file")


# --------------------------------------------------------------------------- #
# 2. Solid cache (persistent tier of Component.solid)
# --------------------------------------------------------------------------- #

def test_solid_cache_persists_across_simulated_fresh_process():
    """First build writes the persistent cache; a fresh Component instance
    (in-run cache cleared, simulating a new process) with the SAME params
    loads from disk instead of calling _build()."""
    a = Lumber("2x4", 6 * IN, name="a")
    built = a.solid  # miss -> builds, persists to disk
    hits_before = base_mod._SOLID_DISK_CACHE.hits

    _reset_solid_cache()  # simulate a fresh process: in-run tier gone
    b = Lumber("2x4", 6 * IN, name="b")  # same params -> same cache_key()
    loaded = b.solid

    assert base_mod._SOLID_DISK_CACHE.hits == hits_before + 1
    assert geometry_hash(loaded) == geometry_hash(built)


def test_solid_cache_param_change_is_a_miss():
    Lumber("2x4", 6 * IN, name="a").solid
    _reset_solid_cache()
    misses_before = base_mod._SOLID_DISK_CACHE.misses

    Lumber("2x4", 7 * IN, name="b").solid  # different length -> different cache_key()

    assert base_mod._SOLID_DISK_CACHE.misses == misses_before + 1


def test_solid_cache_geometry_code_change_invalidates(monkeypatch):
    """Simulates a component-geometry source edit (e.g. lumber.py changed)
    by monkeypatching the shared fingerprint constant directly (in
    core.diskcache, where both the solid AND digest caches read it from)
    -- proves the key is code-version-salted without needing to actually
    edit a source file mid-test."""
    import detailgen.core.diskcache as diskcache_mod

    Lumber("2x4", 6 * IN, name="a").solid
    _reset_solid_cache()
    monkeypatch.setattr(diskcache_mod, "COMPONENT_GEOMETRY_FINGERPRINT", "pretend-code-changed")
    misses_before = base_mod._SOLID_DISK_CACHE.misses

    Lumber("2x4", 6 * IN, name="b").solid  # same params, "different code"

    assert base_mod._SOLID_DISK_CACHE.misses == misses_before + 1


def test_solid_cache_corrupt_entry_is_a_miss_not_a_crash():
    from detailgen.core.diskcache import component_disk_key

    a = Lumber("2x4", 6 * IN, name="a")
    a.solid
    disk_key = component_disk_key(a)
    # Corrupt the persisted entry directly.
    base_mod._SOLID_DISK_CACHE.put(disk_key, b"not a valid brep file at all")

    _reset_solid_cache()
    b = Lumber("2x4", 6 * IN, name="b")
    rebuilt = b.solid  # must recover by rebuilding, not raise

    assert geometry_hash(rebuilt) == geometry_hash(a._solid)


# --------------------------------------------------------------------------- #
# 3. Verdict cache: per-check cacheability, proven by moving the pair
# --------------------------------------------------------------------------- #

def _two_lumber(gap_mm: float = 5.0):
    detail = DetailAssembly("verdict-cache-test")
    a = detail.add(Lumber("2x4", 6 * IN, name="a"))
    b = detail.add(Lumber("2x4", 6 * IN, name="b"), at=(0, 1.5 * IN + gap_mm, 0))
    return detail, a, b


def _rigidly_move_whole_pair(detail, shift=(1000.0, 2000.0, 500.0), angle_deg=37.0):
    """Apply the SAME rigid motion (rotation about Z then translation) to
    EVERY part in the assembly -- simulates moving the whole sub-assembly
    in the world without changing anything about the pair's geometry or
    relative pose. A relative-transform-invariant check must still HIT its
    cache after this; a world-position-dependent check must MISS."""
    motion = Frame.rotation(angle_deg, axis=(0, 0, 1)).compose(Frame.translation(shift))
    for p in detail.parts:
        p.world_frame = motion.compose(p.world_frame)


def test_interference_cache_hits_after_moving_the_whole_pair_together():
    """check_interference's result only depends on a/b's RELATIVE pose (a
    boolean-intersection volume is invariant to a shared rigid motion) --
    the cache key must reflect that, so this MUST be a hit."""
    detail, a, b = _two_lumber(gap_mm=-5.0)  # overlapping
    check_interference(a, b, allowed=True, tol=DEFAULT)
    hits_before = checks_mod._VERDICT_CACHE.hits

    _rigidly_move_whole_pair(detail)
    finding = check_interference(a, b, allowed=True, tol=DEFAULT)

    assert checks_mod._VERDICT_CACHE.hits == hits_before + 1
    assert finding.passed is True


def test_interference_cache_misses_when_relative_pose_changes():
    detail, a, b = _two_lumber(gap_mm=5.0)
    check_interference(a, b, tol=DEFAULT)
    misses_before = checks_mod._VERDICT_CACHE.misses

    b.world_frame = Frame.translation((0, 100.0, 0)).compose(b.world_frame)
    check_interference(a, b, tol=DEFAULT)

    assert checks_mod._VERDICT_CACHE.misses == misses_before + 1


def test_contact_cache_misses_after_moving_the_whole_pair_together():
    """check_contact reads a WORLD axis-aligned bounding box for each part
    -- NOT invariant to rotating the whole pair together (the box itself
    changes shape under world rotation) -- so, unlike interference, this
    MUST miss."""
    detail, a, b = _two_lumber(gap_mm=0.1)
    check_contact(a, b, tol=DEFAULT)
    misses_before = checks_mod._VERDICT_CACHE.misses

    _rigidly_move_whole_pair(detail)
    check_contact(a, b, tol=DEFAULT)

    assert checks_mod._VERDICT_CACHE.misses == misses_before + 1


def test_contact_cache_hits_on_an_unchanged_repeat_call():
    detail, a, b = _two_lumber(gap_mm=0.1)
    f1 = check_contact(a, b, tol=DEFAULT)
    hits_before = checks_mod._VERDICT_CACHE.hits
    f2 = check_contact(a, b, tol=DEFAULT)

    assert checks_mod._VERDICT_CACHE.hits == hits_before + 1
    assert f2.passed == f1.passed
    assert f2.detail == f1.detail


def test_bearing_cache_misses_after_moving_the_whole_pair_together():
    """check_bearing pushes along a FIXED WORLD axis ('Z' etc, see
    checks._AXV) -- also world-position-dependent, same reasoning as
    contact."""
    detail = DetailAssembly("bearing-cache-test")
    a = detail.add(Lumber("2x8", 12 * IN, name="a"))
    b = detail.add(Lumber("2x8", 12 * IN, name="b"),
                    at=(0, 0, 7.25 * IN))  # flush on top, 2x8 actual depth
    check_bearing(a, b, axis="Z", tol=DEFAULT)
    misses_before = checks_mod._VERDICT_CACHE.misses

    _rigidly_move_whole_pair(detail)
    check_bearing(a, b, axis="Z", tol=DEFAULT)

    assert checks_mod._VERDICT_CACHE.misses == misses_before + 1


def test_bearing_cache_hits_on_an_unchanged_repeat_call():
    detail = DetailAssembly("bearing-cache-test-2")
    a = detail.add(Lumber("2x8", 12 * IN, name="a"))
    b = detail.add(Lumber("2x8", 12 * IN, name="b"), at=(0, 0, 7.25 * IN))
    f1 = check_bearing(a, b, axis="Z", tol=DEFAULT)
    hits_before = checks_mod._VERDICT_CACHE.hits
    f2 = check_bearing(a, b, axis="Z", tol=DEFAULT)

    assert checks_mod._VERDICT_CACHE.hits == hits_before + 1
    assert f2.passed == f1.passed == True  # noqa: E712 -- flush contact expected


def test_floating_link_cache_hits_after_moving_the_whole_pair_together():
    """The internal bearing/bond link test inside check_no_floaters uses a
    true min-distance (BRepExtrema) -- relative-invariant, like
    interference -- so it must hit after a shared rigid motion, same as
    interference."""
    detail = DetailAssembly("floating-cache-test")
    ground = detail.add(Lumber("2x8", 12 * IN, name="ground"))
    beam = detail.add(Lumber("2x8", 12 * IN, name="beam"), at=(0, 0, 7.25 * IN))
    findings = check_no_floaters(detail, bearings=[(ground, beam, "Z", 1.0)],
                                 bonds=[], ground=ground, tol=DEFAULT)
    assert findings[0].passed is True  # sanity: they do bear on each other
    hits_before = checks_mod._VERDICT_CACHE.hits

    _rigidly_move_whole_pair(detail)
    check_no_floaters(detail, bearings=[(ground, beam, "Z", 1.0)],
                      bonds=[], ground=ground, tol=DEFAULT)

    assert checks_mod._VERDICT_CACHE.hits == hits_before + 1


def test_verdict_cache_code_change_invalidates(monkeypatch):
    detail, a, b = _two_lumber(gap_mm=5.0)
    check_interference(a, b, tol=DEFAULT)
    monkeypatch.setattr(checks_mod, "_CHECKS_FP", "pretend-checks-code-changed")
    misses_before = checks_mod._VERDICT_CACHE.misses

    check_interference(a, b, tol=DEFAULT)

    assert checks_mod._VERDICT_CACHE.misses == misses_before + 1


def test_verdict_cache_tolerance_change_invalidates_bearing():
    from dataclasses import replace

    detail = DetailAssembly("tol-change-test")
    a = detail.add(Lumber("2x8", 12 * IN, name="a"))
    b = detail.add(Lumber("2x8", 12 * IN, name="b"), at=(0, 0, 7.25 * IN))
    check_bearing(a, b, axis="Z", tol=DEFAULT)
    misses_before = checks_mod._VERDICT_CACHE.misses

    loose = replace(DEFAULT, base=DEFAULT.base * 10)
    check_bearing(a, b, axis="Z", tol=loose)

    assert checks_mod._VERDICT_CACHE.misses == misses_before + 1


def test_corrupt_verdict_entry_is_a_miss_not_a_crash():
    detail, a, b = _two_lumber(gap_mm=5.0)
    finding = check_interference(a, b, tol=DEFAULT)
    key = checks_mod._interference_key(a, b, False, None, DEFAULT)
    checks_mod._VERDICT_CACHE.put(key, b"{not: valid json")

    recovered = check_interference(a, b, tol=DEFAULT)  # must recompute, not raise
    assert recovered.passed == finding.passed
    assert recovered.detail == finding.detail


def test_validation_report_tracks_pairs_from_cache():
    detail, a, b = _two_lumber(gap_mm=5.0)
    r1 = validate_assembly(detail)
    assert r1.pairs_from_cache == 0  # first run: nothing on disk yet

    r2 = validate_assembly(detail)
    assert r2.pairs_from_cache == r1.pairs_fully_checked  # everything now hits


def test_kill_switch_forces_full_recompute(monkeypatch):
    detail, a, b = _two_lumber(gap_mm=5.0)
    validate_assembly(detail)

    monkeypatch.setenv("DETAILGEN_NO_CACHE", "1")
    r = validate_assembly(detail)
    assert r.pairs_from_cache == 0


# --------------------------------------------------------------------------- #
# 4. Whole-detail equivalence (the non-negotiable rule from the brief)
# --------------------------------------------------------------------------- #

def _load_detail(name: str, filename: str, clsname: str):
    """Return a zero-arg factory compiling the detail's spec.yaml (the imperative
    mirrors are retired; ``name`` / ``clsname`` retained for call-site parity)."""
    return lambda: compile_spec_file(DETAILS_DIR / filename)


DETAIL_SPECS = [
    ("rock_anchor", "rock_anchor.spec.yaml", "RockAnchor"),
    ("tree_attachment", "tree_attachment.spec.yaml", "TreeAttachment"),
    ("trolley_launch", "trolley_launch.spec.yaml", "TrolleyLaunch"),
    ("platform", "platform.spec.yaml", "Platform"),
]


@pytest.mark.parametrize("name,filename,clsname", DETAIL_SPECS)
def test_cache_warm_findings_equal_no_cache_findings(name, filename, clsname, monkeypatch):
    cls = _load_detail(name, filename, clsname)

    # Pass 1: empty cache (writes it). Pass 2: warm cache (reads it).
    d1 = cls()
    d1.build()
    warm_report = d1.validate()  # populates the disk cache
    d2 = cls()
    d2.build()
    warm_report = d2.validate()  # now actually warm

    monkeypatch.setenv("DETAILGEN_NO_CACHE", "1")
    d3 = cls()
    d3.build()
    nocache_report = d3.validate()

    assert len(warm_report.findings) == len(nocache_report.findings)
    for f_warm, f_nc in zip(warm_report.findings, nocache_report.findings):
        assert f_warm.check == f_nc.check
        assert f_warm.subject == f_nc.subject
        assert f_warm.passed == f_nc.passed
        assert f_warm.detail == f_nc.detail
    # All shipped details are clean except the platform, whose sole failure is the
    # task-SUPPORT acceptance proof (deck unsupported at the tree end); the cache
    # reproduces it identically (asserted element-wise above).
    assert all(f.check == "support" for f in warm_report.failures)
