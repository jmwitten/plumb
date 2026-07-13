"""Regression: a mesh-emitting exporter must not mutate the shared solid cache.

The process-wide ``_SOLID_CACHE`` hands every instance the SAME built local
solid, and ``Placed.world_solid`` transforms it with ``.moved`` — which shares
the underlying OCCT ``TShape``. Before the fix, the tessellating exporters
(GLB via ``to_cq_assembly``, STL via ``compound``, PNG via ``solid.tessellate``)
meshed that shared ``TShape`` in place; the triangulation left behind shifted a
later EXACT ``BoundingBox()``/``Volume()`` read on the same cached solid — up to
~0.18 mm on the tree detail — so any frozen-transform oracle (1e-6/1e-3) that
ran in the same process AFTER an export drifted. That is the exact mechanism
behind the 5 order-dependent serial-suite failures documented on master
@afebae4 (rock_anchor, tree_attachment ×2, tree_attachment_spec,
trolley_launch_spec).

This test co-locates the two operations in one process on purpose: it reads a
detail's world-solid geometry fingerprint (the same bbox+volume the oracles
read), runs a COARSE export, then reads the fingerprint again from the same
cached solids. Pre-fix (commit 0a68346's parent, master @afebae4) the second
read drifted from the first and from frozen truth; post-fix (exporters mesh
``isolated_world_solids`` copies) it is byte-identical. The fingerprint is
also checked against the committed frozen truth so this can never be satisfied
by two equally-wrong reads.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from detailgen.core.base import _reset_solid_cache
from detailgen.spec.compiler import compile_spec
from detailgen.spec.loader import load_spec_file
from detailgen.rendering.export import export_glb, export_stl, export_png

ROOT = Path(__file__).resolve().parents[1]
DETAILS = ROOT / "details"
FROZEN_DIR = ROOT / "tests" / "baselines" / "frozen_truth"


def _fingerprint(detail) -> dict:
    """Per placed part: world origin + geometry fingerprint (volume, bbox) —
    identical to the frozen-transform oracles (test_tree_attachment_spec, etc.)."""
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


def _worst_delta(a: dict, b: dict) -> float:
    worst = 0.0
    for name in a:
        oa, va, ba = a[name]
        ob, vb, bb = b[name]
        for x, y in zip(oa, ob):
            worst = max(worst, abs(x - y))
        worst = max(worst, abs(va - vb))
        for x, y in zip(ba, bb):
            worst = max(worst, abs(x - y))
    return worst


def _frozen_fingerprint(name: str) -> dict:
    data = json.loads((FROZEN_DIR / f"{name}.json").read_text())["geom_fingerprint"]
    return {k: tuple(v) for k, v in data.items()}


def _export_glb(assembly, out):
    export_glb(assembly, out / "d.glb")


def _export_stl(assembly, out):
    export_stl(assembly, out / "d.stl")


def _export_png(assembly, out):
    export_png(assembly, out / "d.png", view="iso", size=(200, 150))


# tree_attachment shows the largest pre-fix drift (~0.18 mm) and is frozen at
# the tightest tolerance (1e-6); it is the sharpest witness for the whole class.
DETAIL = "tree_attachment"
FROZEN_TOL = 1e-6


@pytest.mark.parametrize("exporter", [_export_glb, _export_stl, _export_png],
                         ids=["glb", "stl", "png"])
def test_export_does_not_mutate_shared_cached_geometry(exporter, tmp_path):
    _reset_solid_cache()
    detail = compile_spec(load_spec_file(DETAILS / f"{DETAIL}.spec.yaml"))
    detail.validate()

    frozen = _frozen_fingerprint(DETAIL)
    before = _fingerprint(detail)
    # Sanity: we start AT frozen truth, so a post-export match is meaningful
    # (not two equally-wrong reads agreeing with each other).
    assert _worst_delta(frozen, before) <= FROZEN_TOL

    exporter(detail.assembly, tmp_path)

    after = _fingerprint(detail)
    # The contamination guard: an exporter that meshed the shared TShape would
    # make this read drift. It must be byte-identical to the pre-export read...
    assert _worst_delta(before, after) == 0.0, (
        f"{exporter.__name__} mutated shared cached geometry: "
        f"worst drift {_worst_delta(before, after)} mm")
    # ...and still exactly on frozen truth.
    assert _worst_delta(frozen, after) <= FROZEN_TOL
