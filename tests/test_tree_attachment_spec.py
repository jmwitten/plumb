"""Oracle for the clearance-era tree detail: the compiled
details/tree_attachment.spec.yaml reproduces the tree detail's FROZEN IMPERATIVE
TRUTH byte-identically — GEOMETRY + BOM + VALIDATION FINDINGS.

The reference side is ``tests/baselines/frozen_truth/tree_attachment.json`` — the
last testimony of the imperative ``details/tree_attachment.py``, captured at the
base SHA by ``scripts/capture_frozen_truth.py``. The same SPECPLAT discipline as
tests/test_platform_spec.py: the spec is the only path built here, and it must
reproduce the frozen truth.

The tree detail is a clearance close-up — a trunk context body plus two plain 2x6
beam stubs that stand a growth gap clear of the round trunk. It declares no
connectivity graph, so the finding set is just the pairwise interference checks
and the trunk-diameter dimension. The tests below assert the spec agrees with the
frozen truth on transforms (to 1e-6), on every BOM field, and on every finding,
and that the spec round-trips through YAML and JSON.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from detailgen.spec.loader import load_spec_file, load_spec_text
from detailgen.spec.serialize import dump_json, dump_yaml
from detailgen.spec.compiler import compile_spec

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "details" / "tree_attachment.spec.yaml"
FROZEN = ROOT / "tests" / "baselines" / "frozen_truth" / "tree_attachment.json"
TOL = 1e-6


def _frozen():
    return json.loads(FROZEN.read_text())


def _fingerprint(detail):
    """Per placed part, by name: world origin + a geometry fingerprint (volume,
    bbox) — API-agnostic and orientation-sensitive, so it proves the full
    transform, not just the translation (identical to test_platform_spec)."""
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


def test_spec_matches_frozen_transforms_to_1e_6():
    frozen = _frozen()
    spec_detail = _built()
    fs = _fingerprint(spec_detail)
    ff = frozen["geom_fingerprint"]
    assert set(ff) == set(fs), (
        f"part-name mismatch: only frozen={sorted(set(ff)-set(fs))}, "
        f"only spec={sorted(set(fs)-set(ff))}")
    assert len(fs) == frozen["counts"]["parts"]   # trunk + 2 plain beam stubs
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


def test_spec_bom_byte_identical():
    frozen = _frozen()
    spec_detail = _built()
    bs = spec_detail.bom_table()
    bf = frozen["bom"]
    assert len(bs) == len(bf) == frozen["counts"]["bom_rows"]   # PT 2x6 beam stubs + the context trunk
    for rs, rf in zip(bs, bf):
        for k in rf:
            if k == "length_mm" and rf[k] is not None and rs[k] is not None:
                assert abs(rs[k] - rf[k]) <= TOL
            else:
                assert rs[k] == rf[k], f"BOM field {k!r}: {rs[k]!r} != {rf[k]!r}"


def test_spec_findings_match_frozen():
    """FULL equivalence: every finding the spec emits is in the frozen imperative
    truth, and vice versa. A clearance close-up declares no connectivity graph, so
    the finding set is just the pairwise interference checks and the trunk-diameter
    dimension — no ground/floating finding and no bearings. The beams stand a
    growth gap clear of the trunk; that Y-clearance is proven in the platform
    detail as its growth-clearance invariant."""
    frozen = _frozen()
    spec_detail = _built()
    spec_c = Counter(
        (f.check, f.subject, bool(f.passed)) for f in spec_detail.report.findings)
    frozen_c = Counter(tuple(x) for x in frozen["findings"])
    assert spec_c == frozen_c, (spec_c - frozen_c, frozen_c - spec_c)
    assert not any(k[0] == "floating" for k in spec_c)  # no ground -> no floating check
    assert ("dimension", "trunk diameter: trunk", True) in spec_c


def test_spec_validates_clean_standalone():
    """The clearance fragment validates CLEAN on its own (trunk + two beam stubs
    that clear it; no collisions, trunk dimension holds) — require_clean passes."""
    spec_detail = compile_spec(load_spec_file(SPEC))
    assert spec_detail.validate().ok
    spec_detail.require_clean()


def test_spec_round_trips():
    doc = load_spec_file(SPEC)
    assert load_spec_text(dump_yaml(doc)) == doc
    assert load_spec_text(dump_json(doc), fmt="json") == doc
