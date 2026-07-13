"""Tests for the tree-clearance Detail (free-standing platform).

Contract for ``details/tree_attachment.spec.yaml`` (compiled via
``compile_spec_file``): the detail builds and validates CLEAN as a clearance
close-up — trunk context body + two plain 2x6 beam stubs (``stub_of`` the
platform's continuous run). Each beam inner face stands a growth gap clear of
the trunk (the real beam Y, trunk_dia/2 + growth_gap), so the standalone
diagram shows the true clearance — the beams stand OFF the trunk, not tangent to
it. Each stub carries ``stub_of`` metadata naming the platform's full run. The
SlottedBeamEnd component stays in the library (validated below via its own
stub_of contract), just unused by this detail. A fatter-trunk variant compiles
as a param-family member via ``overrides=`` (the compiled twin of the old
imperative ``TreeAttachment(trunk_dia=24)``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from detailgen.core import IN
from detailgen.spec.compiler import compile_spec_file
from detailgen.validation.checks import _min_distance
from detailgen.components.tree import SlottedBeamEnd

SPEC = Path(__file__).resolve().parents[1] / "details" / "tree_attachment.spec.yaml"


def _tree(**overrides):
    return compile_spec_file(SPEC, overrides=overrides or None)


def test_default_detail_is_clean():
    detail = _tree()
    report = detail.validate()
    assert report.ok, str(report)


def test_detail_is_trunk_plus_two_beam_stubs():
    """The reworked detail is exactly the trunk + two beam stubs — no lags,
    washers, or slots (the lag connection is retired)."""
    d = _tree()
    names = {p.name for p in d.assembly.parts}
    assert names == {"trunk", "beam +Y", "beam -Y"}


def test_beam_inner_face_clears_trunk_by_growth_gap():
    """TREEDOC: each beam stub sits at the REAL beam inner Y (trunk radius + the
    per-side growth gap), so the standalone diagram shows the true clearance — the
    beams stand OFF the trunk, they are NOT tangent to it. (Updated from the retired
    tangent-at-trunk-radius assumption: the free-standing platform clears the live
    tree; the tangent bond that once grounded the stubs is gone.)"""
    d = _tree()
    P = d.params
    inner_y = (P.trunk_dia / 2 + P.growth_gap) * IN
    beam = d["beam +Y"].world_solid().val().BoundingBox()
    assert beam.ymin == pytest.approx(inner_y, abs=1e-6)
    gap = _min_distance(d["beam +Y"], d["trunk"])
    assert gap == pytest.approx(P.growth_gap * IN, abs=1e-3)  # ~5" clearance, not tangent


def test_report_prose_has_no_lag_or_slot_tokens():
    """Prose-vs-model guard (the class guard for this defect): the rendered tree
    report — including the trunk's BOM assumption cell — must describe the
    free-standing clearance reality with NO 'lag'/'slotted' language. The detail no
    longer fastens to the tree, so those words describing it are a stale-prose bug.

    Renders the ``doc:`` report block directly via ``render_report`` (the same
    function the gated ``_document`` calls), NOT the full ``render()``: emitting
    only the report markdown, with no STEP/GLB geometry export, keeps this test
    off the tree detail's known OCCT bounding-box float wobble (a heavy export
    perturbs the shared solid/disk cache; see tests/test_trolley_launch_spec.py:26)."""
    from detailgen.spec.report import render_report

    d = _tree()
    d.validate()
    text = render_report(d, d.doc.doc).lower()
    for tok in ("lag", "slotted", "slot"):
        assert tok not in text, f"stale {tok!r} token in the tree clearance report:\n{text}"


def test_clearance_callout_value_equals_live_param_gap():
    """The clearance callout reports the per-side gap and it equals the live params'
    gap (beam inner face Y − trunk radius) AND the gap actually built into the
    geometry — so the dimension can never drift from the beam placement."""
    d = _tree()
    P = d.params
    param_gap = (P.trunk_dia / 2 + P.growth_gap) - P.trunk_dia / 2   # inner_y − radius
    callout = next(c for c in d.callouts() if c.param == "growth_gap")
    assert callout.value(P) == pytest.approx(param_gap)
    # ...and equals the true built clearance (beam inner face − trunk surface).
    R = P.trunk_dia / 2 * IN
    beam = d["beam +Y"].world_solid().val().BoundingBox()
    assert (beam.ymin - R) == pytest.approx(callout.value(P) * IN, abs=1e-6)


def test_variant_size_builds_and_validates_clean():
    """A fatter trunk still assembles and validates."""
    detail = _tree(trunk_dia=24.0)
    assert detail.validate().ok, str(detail.report)


def test_bom_line_items():
    labels = {r["item"]: r["qty"] for r in _tree().bom_table()}
    assert labels["PT 2x6 lumber"] == 2
    assert labels["Tree trunk (existing)"] == 1
    # the lag connection is retired — no lag screws / washers on the buy list
    assert not any("Lag" in item or "washer" in item.lower() for item in labels)


def test_default_detail_beams_carry_stub_of_matching_platform_beam_len():
    """The as-drawn TreeAttachment wires ``full_beam_len`` (default 60", BEAMFIX:
    the platform's own beam_len (48") + tree_overhang (12")) into both plain-Lumber
    beam stubs' stub_of."""
    d = _tree()
    for side in ("+Y", "-Y"):
        stub = d[f"beam {side}"].component.stub_of()
        assert stub is not None
        assert stub["full_dims"] == '2x6 x 60.0" (continuous run)'
        assert "platform detail" in stub["note"]


# -- SlottedBeamEnd component still lives in the library (retired from this detail,
#    but validated + reusable, per the TREEFREE brief) ---------------------------
def test_slotted_beam_end_stub_of_defaults_to_none_without_full_length():
    beam = SlottedBeamEnd("2x6", 24 * IN, name="probe-no-full-length")
    assert beam.stub_of() is None


def test_slotted_beam_end_stub_of_carries_full_dims_when_constructed_with_full_length():
    beam = SlottedBeamEnd("2x6", 24 * IN, name="probe-beam", full_length=48 * IN)
    stub = beam.stub_of()
    assert stub is not None
    assert stub["full_dims"] == '2x6 x 48.0" (continuous beam)'
    assert stub["modeled_dims"] == beam.describe()
    assert "trunk-end" in stub["note"]
    assert "platform detail" in stub["note"]
