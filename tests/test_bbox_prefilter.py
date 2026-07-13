"""Equivalence tests for the bbox prefilter in the pairwise interference
sweep (`validate_assembly` / `src/validation/checks.py`, directive #8 lever
c). The prefilter must never change what the sweep reports — only how much
work it does to get there — so every test here compares a prefiltered run
against an unfiltered ground truth (a bare loop calling `check_interference`
on every pair, exactly what the sweep used to do before the prefilter
existed) rather than asserting a canned expected result.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import cadquery as cq
import pytest

from detailgen.assemblies import DetailAssembly
from detailgen.components import Lumber
from detailgen.core import DEFAULT, IN, Component
from detailgen.spec.compiler import compile_spec_file
from detailgen.validation import validate_assembly
from detailgen.validation.checks import check_interference

DETAILS_DIR = Path(__file__).resolve().parents[1] / "details"


def _gapped_pair(gap: float):
    """Two 6"-long 2x4s, 'a' at the origin and 'b' offset ``gap`` mm beyond
    exact Y-face contact (ylen of a 2x4 is 1.5in) — so the true AABB gap
    between them is exactly ``gap``. Same construction as
    test_config.py's helper of the same name."""
    detail = DetailAssembly("gap-test")
    a = detail.add(Lumber("2x4", 6 * IN, name="a"))
    b = detail.add(Lumber("2x4", 6 * IN, name="b"), at=(0, 1.5 * IN + gap, 0))
    return detail, a, b


def _unfiltered_interference_findings(assembly, expected_overlaps=frozenset(), tol=DEFAULT):
    """Ground truth: every pair through the exact boolean check, no skip —
    the sweep's behavior before the prefilter existed."""
    allowed = {
        frozenset((assembly._resolve(a).id, assembly._resolve(b).id))
        for a, b in expected_overlaps
    }
    return [
        check_interference(a, b, allowed=frozenset((a.id, b.id)) in allowed, tol=tol)
        for a, b in combinations(assembly.parts, 2)
    ]


def _interference_findings(report):
    return [f for f in report.findings if f.check == "interference"]


def _full_expected_overlaps(detail):
    """The complete ``expected_overlaps`` set the real sweep checks against:
    hand-written ``validation_spec()`` merged with any declared
    ``Connection``s' generated overlaps — exactly what ``Detail.validate()``
    itself computes before calling ``validate_assembly``. A detail whose
    Connections declare an overlap ``validation_spec()`` alone doesn't know
    about (e.g. the platform's face-mount-hanger flange embedding one gauge
    into its header, a fact `FaceMountHanger.allowed_intersections`
    generates) needs this merged set, not the bare hand-written half, for
    an independent 'unfiltered' recomputation to agree with the real sweep."""
    from detailgen.assemblies.connection import compile_connections, merge_into_spec
    hand_spec = detail.validation_spec()
    conns = detail.connections()
    if not conns:
        return hand_spec.get("expected_overlaps", frozenset())
    generated = compile_connections(detail.assembly, conns)
    merged = merge_into_spec(detail.assembly, hand_spec, generated)
    return merged["expected_overlaps"]


class _TwoSolidComponent(Component):
    """A synthetic multi-solid part: `_build()` returns a Workplane holding
    TWO disjoint boxes, `far` (index 0) and `near` (index 1), each placed at
    an explicit world offset (this component is always added at the
    assembly's origin, so its local offsets ARE its world coordinates).

    `far` is listed FIRST specifically so `.vals()[0]` / `.val()` would
    silently pick only it if the single-solid `.val().BoundingBox()` bug
    (the one this fixture regression-tests) were reintroduced — a bbox built
    from `far` alone sits millions of mm from anything else in these tests,
    so such a regression would prefilter every pair this part is in,
    regardless of how close `near` really is to something."""

    def __init__(self, name, near_offset, far_offset=(1.0e6, 0.0, 0.0), size=1 * IN):
        super().__init__(name)
        self.near_offset = near_offset
        self.far_offset = far_offset
        self.size = size

    def _build(self):
        far = cq.Solid.makeBox(self.size, self.size, self.size, cq.Vector(*self.far_offset))
        near = cq.Solid.makeBox(self.size, self.size, self.size, cq.Vector(*self.near_offset))
        return cq.Workplane("XY").newObject([far, near])


# -- threshold boundary --------------------------------------------------------

def test_gap_just_under_threshold_is_not_prefiltered():
    """DEFAULT.bbox_prefilter_gap == near_miss == 0.15mm. A 0.1mm true AABB
    gap is under that, so the pair must go through the real boolean check —
    not be skipped — even though the outcome (no overlap) is the same
    either way."""
    assert DEFAULT.bbox_prefilter_gap == pytest.approx(0.15)
    detail, a, b = _gapped_pair(0.1)

    report = validate_assembly(detail)

    assert report.pairs_total == 1
    assert report.pairs_prefiltered == 0
    assert report.pairs_fully_checked == 1

    [finding] = _interference_findings(report)
    ground_truth = check_interference(a, b, tol=DEFAULT)
    assert (finding.check, finding.subject, finding.passed, finding.detail) == (
        ground_truth.check, ground_truth.subject, ground_truth.passed, ground_truth.detail,
    )


def test_gap_just_over_threshold_is_prefiltered_and_agrees_with_unfiltered():
    """A 0.2mm true AABB gap is over the 0.15mm threshold, so the sweep
    skips the boolean check entirely — but an unfiltered run of the same
    pair must independently agree there's no finding, and the fabricated
    Finding must be identical to what the full check would have produced."""
    detail, a, b = _gapped_pair(0.2)

    report = validate_assembly(detail)

    assert report.pairs_total == 1
    assert report.pairs_prefiltered == 1
    assert report.pairs_fully_checked == 0
    assert report.prefilter_threshold_mm == pytest.approx(DEFAULT.bbox_prefilter_gap)

    [finding] = _interference_findings(report)
    ground_truth = check_interference(a, b, tol=DEFAULT)  # unfiltered, for comparison only
    assert ground_truth.passed
    assert (finding.check, finding.subject, finding.passed, finding.detail) == (
        ground_truth.check, ground_truth.subject, ground_truth.passed, ground_truth.detail,
    )


def test_pair_counts_are_conserved():
    """prefiltered + fully_checked == total, for every pair, always — the
    auditability invariant (directive #8's honesty rule, P1)."""
    detail = DetailAssembly("count-test")
    for i in range(5):
        detail.add(Lumber("2x4", 6 * IN, name=f"p{i}"), at=(0, i * 6 * IN, 0))

    report = validate_assembly(detail)

    n = 5
    assert report.pairs_total == n * (n - 1) // 2
    assert report.pairs_prefiltered + report.pairs_fully_checked == report.pairs_total
    assert len(_interference_findings(report)) == report.pairs_total


# -- multi-solid parts: the prefilter's box must cover EVERY solid, not just
# the first (`.val()`) — regression coverage for a reviewer-flagged honesty
# gap: a part whose bbox is built from only one of its solids could get a
# box that's NOT a conservative superset of what `check_interference`
# actually intersects against, letting a real finding be silently skipped. --

def test_multi_solid_part_near_solid_within_threshold_is_not_prefiltered():
    """`multi`'s `near` solid sits 0.05mm (under the 0.15mm prefilter
    threshold) from `other`; its `far` solid sits ~1,000,000mm away. A
    bbox built from only the first solid (`far`, per the old bug) would
    see a huge gap and wrongly prefilter this pair. The correct box (union
    of both solids) must NOT prefilter it."""
    detail = DetailAssembly("multi-solid-boundary")
    other = detail.add(Lumber("2x4", 6 * IN, name="other"))  # y in [0, 1.5in], x in [0,6in]
    multi = detail.add(_TwoSolidComponent(
        "multi", near_offset=(0.0, 1.5 * IN + 0.05, 0.0)))

    report = validate_assembly(detail)

    assert report.pairs_total == 1
    assert report.pairs_prefiltered == 0
    assert report.pairs_fully_checked == 1

    [finding] = _interference_findings(report)
    ground_truth = check_interference(other, multi, tol=DEFAULT)  # combinations() order: other, multi
    assert (finding.check, finding.subject, finding.passed, finding.detail) == (
        ground_truth.check, ground_truth.subject, ground_truth.passed, ground_truth.detail,
    )


def test_multi_solid_part_near_solid_overlap_is_caught_not_hidden():
    """Same fixture, but `near` now genuinely overlaps `other` — the kind of
    real modeling bug the sweep exists to catch. With only `far`'s bbox (the
    old bug), this pair would be prefiltered and the overlap would be
    silently reported as "no overlap" — exactly the honesty violation
    flagged in review. The fix must find the real failure, matching an
    unfiltered run."""
    detail = DetailAssembly("multi-solid-overlap")
    other = detail.add(Lumber("2x4", 6 * IN, name="other"))
    multi = detail.add(_TwoSolidComponent(
        "multi", near_offset=(0.0, 0.5 * IN, 0.0)))  # sits inside other's y-span

    report = validate_assembly(detail)

    assert report.pairs_prefiltered == 0
    assert report.pairs_fully_checked == 1

    [finding] = _interference_findings(report)
    assert not finding.passed  # the real overlap must be caught, not hidden
    ground_truth = check_interference(other, multi, tol=DEFAULT)  # combinations() order: other, multi
    assert (finding.check, finding.subject, finding.passed, finding.detail) == (
        ground_truth.check, ground_truth.subject, ground_truth.passed, ground_truth.detail,
    )


# -- full-detail equivalence: prefilter ON (validate_assembly) vs OFF
# (unfiltered ground truth), identical findings ------------------------------

def test_rock_anchor_prefilter_agrees_with_unfiltered():
    detail = compile_spec_file(DETAILS_DIR / "rock_anchor.spec.yaml")
    spec = detail.validation_spec()
    tol = spec.get("tol", DEFAULT)

    report = detail.validate()
    assert report.ok, str(report)
    assert report.pairs_prefiltered > 0  # prove the prefilter actually fired

    prefiltered = _interference_findings(report)
    unfiltered = _unfiltered_interference_findings(
        detail.assembly, _full_expected_overlaps(detail), tol)

    assert len(prefiltered) == len(unfiltered) == report.pairs_total
    assert [(f.check, f.subject, f.passed, f.detail) for f in prefiltered] == [
        (f.check, f.subject, f.passed, f.detail) for f in unfiltered
    ]


def test_platform_prefilter_agrees_with_unfiltered():
    """Platform is the biggest detail (124 parts, 7626 pairs, post-RAILFASTEN
    — the 4 rail-to-post/leg RailCapScrewed Connections added 8 more screws
    on top of the ladder/end-joist/hanger-fastener hardware) — the one the
    brief calls out by name as the other required full-detail comparison,
    since it's where the prefilter's savings scale the most."""
    detail = compile_spec_file(DETAILS_DIR / "platform.spec.yaml")
    vspec = detail.validation_spec()
    tol = vspec.get("tol", DEFAULT)

    report = detail.validate()
    # STRUCT task #19: the platform validates CLEAN (the support family is a PASS —
    # deck tree end supported by design). The interference prefilter this test
    # exercises is unaffected by that.
    assert [f.check for f in report.failures] == [], str(report)
    assert report.pairs_prefiltered > 0

    prefiltered = _interference_findings(report)
    unfiltered = _unfiltered_interference_findings(
        detail.assembly, _full_expected_overlaps(detail), tol)

    assert len(prefiltered) == len(unfiltered) == report.pairs_total
    assert [(f.check, f.subject, f.passed, f.detail) for f in prefiltered] == [
        (f.check, f.subject, f.passed, f.detail) for f in unfiltered
    ]
