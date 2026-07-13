"""SPECPLAT oracle: the compiled details/platform.spec.yaml reproduces the
platform's FROZEN IMPERATIVE TRUTH exactly — every part transform <=1e-6, every
validation finding identical, and the BOM identical (modulo a documented inch->mm
float-conversion-ordering residual on real lengths).

The reference side is ``tests/baselines/frozen_truth/platform.json`` — the last
testimony of the imperative ``details/platform.py``, captured at the base SHA by
``scripts/capture_frozen_truth.py`` while both paths still existed. The spec is
the only path this test builds; it asserts the spec reproduces that frozen truth,
so the oracle keeps its full teeth after the imperative detail is removed."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from detailgen.spec.loader import load_spec_file, load_spec_text
from detailgen.spec.serialize import dump_json, dump_yaml
from detailgen.spec.compiler import compile_spec

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "details" / "platform.spec.yaml"
FROZEN = ROOT / "tests" / "baselines" / "frozen_truth" / "platform.json"
TOL = 1e-6


def _frozen():
    return json.loads(FROZEN.read_text())


def _fingerprint(detail):
    """Per placed part, by name: world origin + a geometry fingerprint (volume,
    bbox) — API-agnostic, and (via bbox) sensitive to orientation, so it proves
    the full transform, not just the translation. Matches the shape frozen in the
    corpus (origin list, volume, bbox 6-list)."""
    out = {}
    for p in detail.assembly.parts:
        wp = p.world_solid()
        solids = wp.vals()
        vol = sum(s.Volume() for s in solids)
        bb = (wp.combine().objects[0].BoundingBox() if len(solids) > 1
              else solids[0].BoundingBox())
        out[p.name] = (
            list(p.world_frame.origin),
            vol,
            [bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax],
        )
    return out


@pytest.fixture(scope="module")
def built():
    frozen = _frozen()
    spec_detail = compile_spec(load_spec_file(SPEC))
    spec_report = spec_detail.validate()
    return frozen, spec_detail, spec_report


def test_spec_matches_frozen_transforms_to_1e_6(built):
    frozen, spec_detail, _ = built
    fs = _fingerprint(spec_detail)
    ff = frozen["geom_fingerprint"]
    assert set(ff) == set(fs), (
        f"part-name mismatch: only frozen={sorted(set(ff)-set(fs))[:5]}, "
        f"only spec={sorted(set(fs)-set(ff))[:5]}")
    assert len(fs) == frozen["counts"]["parts"] == 148  # FAB-3: +3 post bases (one per pier foundation)
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


def test_spec_findings_match_frozen_truth(built):
    frozen, _, spec_report = built
    # A2 RE-FREEZE: the corpus is the CURRENT spec path, so the spec's findings
    # match it EXACTLY. FAB-3 (retire R29) declared the three pier foundation
    # systems: the rung-3 attachment + embedment obligations PASS (each leg now
    # has a real post base fastening it to its block), but uplift/lateral/soil
    # CAPACITY is an honest, BLOCKING UNKNOWN by construction — so the platform is
    # NO LONGER clean (a foundation shown is not a foundation silently designed).
    assert not frozen["ok"]  # blocked by the foundation-capacity UNKNOWN (rung 4)
    support = [f for f in spec_report.findings if f.check == "support"]
    assert len(support) == 1 and support[0].passed
    assert support[0].subject.startswith("walking surface deck:")
    # The three foundation systems: attachment + embedment REPRESENTED (rung 3),
    # capacity UNKNOWN (rung 4, blocking) — never a FAIL, never a number.
    fnd = Counter((f.check, f.verdict) for f in spec_report.findings
                  if f.check.startswith("foundation"))
    assert fnd == Counter({("foundation_attachment", "PASS"): 3,
                           ("foundation_embedment", "PASS"): 3,
                           ("foundation_capacity", "UNKNOWN"): 3})
    assert [f.check for f in spec_report.failures] == []  # UNKNOWN != FAIL
    # Blocking set: the three capacity UNKNOWNs. The two INSTALL v1
    # toe-screw access UNKNOWNs were resolved on merit by task CPGCORE
    # (authored toe-before-bolts sequence -- declared-order clears).
    assert Counter(f.check for f in spec_report.blocking) == Counter(
        {"foundation_capacity": 3})
    # by-kind and the full (check, subject, passed) multiset match the corpus.
    assert Counter(f.check for f in spec_report.findings) == Counter(frozen["by_kind"])
    spec_multiset = Counter(
        (f.check, f.subject, bool(f.passed)) for f in spec_report.findings)
    frozen_multiset = Counter(tuple(x) for x in frozen["findings"])
    assert spec_multiset == frozen_multiset


def test_spec_bom_equivalent(built):
    frozen, spec_detail, _ = built
    bs = spec_detail.bom_table()
    bf = frozen["bom"]
    assert len(bs) == len(bf) == 20  # FAB-3: +1 post base row (3 identical piers -> one qty-3 group)
    for rs, rf in zip(bs, bf):
        for k in rf:
            if k == "length_mm" and rf[k] is not None and rs[k] is not None:
                # a real length: identical to the SAME 1e-6 geometric bar the
                # transforms use (raw floats differ by <=2e-13 mm from inch->mm
                # conversion ordering — this is GEOMETRY, still tolerance-equal).
                assert abs(rs[k] - rf[k]) <= TOL
            else:
                # dimension DISPLAY strings are byte-equal: fmt_in snaps to 1e-6"
                # before display rounding, so the <=2e-13 mm residual can no longer
                # tip the boulder-16.75" / mesh-42.25" knife-edges to different
                # strings. No adjacent-rounding tolerance needed.
                assert rs[k] == rf[k], f"BOM field {k!r}: {rs[k]!r} != {rf[k]!r}"


def test_platform_spec_round_trips():
    doc = load_spec_file(SPEC)
    assert load_spec_text(dump_yaml(doc)) == doc
    assert load_spec_text(dump_json(doc), fmt="json") == doc
