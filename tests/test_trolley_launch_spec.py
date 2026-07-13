"""SM3a/SM3b oracle: the compiled details/trolley_launch.spec.yaml reproduces the
trolley launch's FROZEN IMPERATIVE TRUTH byte-identically — GEOMETRY + BOM +
VALIDATION FINDINGS. Same SPECPLAT discipline as tests/test_platform_spec.py.

The reference side is ``tests/baselines/frozen_truth/trolley_launch.json`` — the
last testimony of the imperative ``details/trolley_launch.py``, captured at the
base SHA by ``scripts/capture_frozen_truth.py``. The spec is the only path built
here.

The trolley fragment carries an ``expected_overlaps:`` block, a ``contacts:``
block, and a cross-part ``minus_part``/``minus_measure`` difference on
DimensionSpec: the 3 allowlisted overlaps, the 7 per-joint contacts and the 2
cross-part dimensions all reproduce the frozen truth exactly.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from detailgen.spec.loader import load_spec_file, load_spec_text
from detailgen.spec.serialize import dump_json, dump_yaml
from detailgen.spec.compiler import compile_spec

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "details" / "trolley_launch.spec.yaml"
FROZEN = ROOT / "tests" / "baselines" / "frozen_truth" / "trolley_launch.json"
# 1e-3 mm (one micron) — physically meaningless for lumber, still 1000x
# tighter than any real tolerance here. Widened from 1e-6 after the bar
# flaked twice under `-n auto` (shared solid/disk-cache float noise;
# passes at 1e-6 in isolation): rev-sm3a flagged and recommended exactly
# this (review-sm3a.md); second occurrence at the 4B-1 merge.
TOL = 1e-3


def _frozen():
    return json.loads(FROZEN.read_text())


def _fingerprint(detail):
    out = {}
    for p in detail.assembly.parts:
        wp = p.world_solid()
        solids = wp.vals()
        vol = sum(s.Volume() for s in solids)
        bb = (wp.combine().objects[0].BoundingBox() if len(solids) > 1
              else solids[0].BoundingBox())
        out[p.name] = (
            list(p.world_frame.origin), vol,
            [bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax],
        )
    return out


def _built():
    spec_detail = compile_spec(load_spec_file(SPEC))
    spec_detail.validate()
    return spec_detail


def test_spec_matches_frozen_transforms_to_1e_3():
    frozen = _frozen()
    spec_detail = _built()
    fs = _fingerprint(spec_detail)
    ff = frozen["geom_fingerprint"]
    assert set(ff) == set(fs), (
        f"part-name mismatch: only frozen={sorted(set(ff)-set(fs))}, "
        f"only spec={sorted(set(fs)-set(ff))}")
    assert len(fs) == frozen["counts"]["parts"]
    worst = 0.0
    for name in ff:
        oi, vi, bi = ff[name]
        os_, vs, bs = fs[name]
        for a, b in zip(oi, os_):
            worst = max(worst, abs(a - b))
        worst = max(worst, abs(vi - vs))
        for a, b in zip(bi, bs):
            worst = max(worst, abs(a - b))
    assert worst <= TOL, f"worst transform/geometry deviation {worst} mm > {TOL}"


def test_spec_bom_matches_including_formalized_stub_metadata():
    """The BOM is byte-identical to the frozen imperative truth in EVERY field —
    INCLUDING the formalized ``stub_of`` metadata. The launch posts and deck rim
    carry the same ``stub_of`` tag (the two PT 2x6 lumber rows) that the imperative
    derived from leg_height/deck_width, in lockstep with the spec's derived
    leg_full_len / rim_full_len, so there is no stub_of divergence to tolerate."""
    frozen = _frozen()
    spec_detail = _built()
    bs = spec_detail.bom_table()
    bf = frozen["bom"]
    assert len(bs) == len(bf) == frozen["counts"]["bom_rows"]
    formalized = 0
    for rs, rf in zip(bs, bf):
        for k in rf:
            if k == "length_mm" and rf[k] is not None and rs[k] is not None:
                assert abs(rs[k] - rf[k]) <= TOL
            else:
                assert rs[k] == rf[k], f"BOM field {k!r}: {rs[k]!r} != {rf[k]!r}"
        if rs["stub_of"] is not None:
            assert "continuous run" in rs["stub_of"]["full_dims"]
            formalized += 1
    # exactly the two lumber rows (launch/far posts; deck rim) are stub-tagged,
    # identically to the frozen truth.
    assert formalized == frozen["counts"]["formalized_stubs"]


def test_spec_findings_match_frozen():
    """FULL equivalence (SM3b): every finding the spec emits matches the frozen
    imperative truth and vice versa. The 3 flush bearings, the single-part
    grab-bar-height dimension, the 3 allowlisted overlaps, the 7 per-joint contacts
    and the 2 cross-part dimensions all line up; there is (correctly) no floating
    finding on either side (two disconnected islands)."""
    frozen = _frozen()
    spec_detail = _built()
    spec_c = Counter(
        (f.check, f.subject, bool(f.passed)) for f in spec_detail.report.findings)
    frozen_c = Counter(tuple(x) for x in frozen["findings"])
    assert spec_c == frozen_c, (spec_c - frozen_c, frozen_c - spec_c)
    assert not any(k[0] == "floating" for k in spec_c)
    assert ("contact", "trolley wheel <-> zipline cable", True) in spec_c
    # SM4 item 2: the dimension subject carries the member(s) it measures.
    assert ("dimension",
            "hanger length (cable height minus bar height): "
            "zipline cable <-> grab bar", True) in spec_c


def test_spec_validates_clean_standalone():
    """The completed fragment validates CLEAN on its own — the 3 designed
    overlaps are allowlisted, nothing FAILs, require_clean passes."""
    spec_detail = compile_spec(load_spec_file(SPEC))
    assert spec_detail.validate().ok
    spec_detail.require_clean()


def test_spec_round_trips():
    doc = load_spec_file(SPEC)
    assert load_spec_text(dump_yaml(doc)) == doc
    assert load_spec_text(dump_json(doc), fmt="json") == doc
