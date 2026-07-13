"""Tests for the first-class Connection object (Wave 2, item 6).

Covers the task brief's non-negotiable negative cases (detached declared
pair fails, missing declared hardware fails, an install-order cycle is a
hard diagnostic, an unknown datum name is a hard diagnostic with
suggestions) plus the rock-anchor re-authoring's subsumption story: the
Connection-generated checks reproduce every hand-written bearing/overlap/
bond the old scattered lists produced, one-for-one.
"""

import pytest

from detailgen.core import IN
from detailgen.components import Washer, HexNut
from detailgen.assemblies import (
    BoltedClamp, Connection, ConnectionType, DetailAssembly,
    ThreadedRodEpoxyAnchor, compile_connections, merge_into_spec,
)
from detailgen.spec.compiler import compile_spec_file
from detailgen.validation import validate_assembly


# -- fixtures -----------------------------------------------------------------

def _two_washers(gap_mm: float = 0.0):
    """A tiny assembly: two washers stacked along Z, with an optional gap
    inserted between them (0.0 = truly flush contact)."""
    a = DetailAssembly("two washers")
    lo = a.add(Washer(0.5 * IN, name="lo"))
    hi = a.add(Washer(0.5 * IN, name="hi"), at=(0, 0, lo.component.thickness + gap_mm))
    return a, lo, hi


class _NoopType(ConnectionType):
    """A ConnectionType with every hook at its (empty) default — used where
    a test only needs a valid Connection to exist, not to derive anything."""
    label = "noop"


# -- negative test 1: detached declared pair FAILS validation ----------------
# (trolley review, Critical-class: a Connection must PROVE presence of
# declared contact, not merely permit overlap — see connection.py's module
# docstring.)

def test_flush_bearing_pair_passes():
    a, lo, hi = _two_washers(gap_mm=0.0)

    class _Bears(ConnectionType):
        label = "bears"
        def bearing_pairs(self, conn):
            return [(conn.parts[0], conn.parts[1], "Z", 1.0)]

    conn = Connection(kind=_Bears(), parts=[lo, hi])
    checks = conn.generate_checks(a)
    report = validate_assembly(a, bearings=checks.bearings)
    bearing_findings = [f for f in report.findings if f.check == "bearing"]
    assert len(bearing_findings) == 1
    assert bearing_findings[0].passed, bearing_findings[0]


def test_detached_bearing_pair_fails():
    """The wheel-off-cable class of bug: a Connection declares two parts
    must bear on each other, but they're placed with a real gap between
    them. This MUST fail — the pre-Connection ``expected_overlaps``
    mechanism could only permit overlap, never require contact."""
    a, lo, hi = _two_washers(gap_mm=5.0)  # 5mm gap, way past near_miss

    class _Bears(ConnectionType):
        label = "bears"
        def bearing_pairs(self, conn):
            return [(conn.parts[0], conn.parts[1], "Z", 1.0)]

    conn = Connection(kind=_Bears(), parts=[lo, hi])
    checks = conn.generate_checks(a)
    report = validate_assembly(a, bearings=checks.bearings)
    bearing_findings = [f for f in report.findings if f.check == "bearing"]
    assert len(bearing_findings) == 1
    assert not bearing_findings[0].passed
    assert not report.ok


# -- negative test 2: declared hardware missing from the assembly FAILS -----

def test_missing_declared_hardware_fails():
    a, lo, hi = _two_washers()
    other = DetailAssembly("other assembly")
    foreign_nut = other.add(HexNut(0.5 * IN, name="foreign nut"))

    conn = Connection(kind=_NoopType(), parts=[lo, hi], hardware=[foreign_nut])
    checks = conn.generate_checks(a)
    hw_findings = [f for f in checks.findings if f.check == "connection_hardware"]
    assert len(hw_findings) == 1
    assert not hw_findings[0].passed
    assert "not placed in this assembly" in hw_findings[0].detail


def test_present_declared_hardware_passes():
    a, lo, hi = _two_washers()
    real_nut = a.add(HexNut(0.5 * IN, name="real nut"))

    conn = Connection(kind=_NoopType(), parts=[lo, hi], hardware=[real_nut])
    checks = conn.generate_checks(a)
    hw_findings = [f for f in checks.findings if f.check == "connection_hardware"]
    assert len(hw_findings) == 1
    assert hw_findings[0].passed


# -- negative test 3: install-order cycle is a hard diagnostic --------------

def test_install_order_cycle_raises():
    a, lo, hi = _two_washers()

    class _Forward(ConnectionType):
        label = "forward"
        def edges(self, conn):
            from detailgen.assemblies import Edge
            return [Edge(conn.parts[0].id, conn.parts[1].id, "installed_before", "forward")]

    class _Backward(ConnectionType):
        label = "backward"
        def edges(self, conn):
            from detailgen.assemblies import Edge
            return [Edge(conn.parts[1].id, conn.parts[0].id, "installed_before", "backward")]

    c1 = Connection(kind=_Forward(), parts=[lo, hi], label="c1")
    c2 = Connection(kind=_Backward(), parts=[lo, hi], label="c2")

    with pytest.raises(ValueError, match="cycle"):
        compile_connections(a, [c1, c2])


# -- merge_into_spec: a dropped hand-written entry must be VISIBLE, not
# silently discarded (fix round: reviewer found a dual-declaration override
# left no trace in either the derivation log or the report) ----------------

def test_dual_declaration_override_is_recorded_not_silent():
    """A hand-written ``bearings`` entry for the same pair a Connection
    already covers must be dropped (generated wins) AND the drop must be
    auditable: a DerivedFact naming the winning connection, and a
    non-failing ``connection_override`` Finding, both appended to
    ``generated`` in place by ``merge_into_spec``."""
    a, lo, hi = _two_washers(gap_mm=0.0)

    class _Bears(ConnectionType):
        label = "bears"
        def bearing_pairs(self, conn):
            return [(conn.parts[0], conn.parts[1], "Z", 1.0)]

    conn = Connection(kind=_Bears(), parts=[lo, hi], label="the real connection")
    generated = compile_connections(a, [conn])
    before_derived = len(generated.derived)
    before_findings = len(generated.findings)

    # An absurd hand-written threshold for the SAME pair -- if this silently
    # won or silently vanished, that would be the bug the review caught.
    hand_spec = {"bearings": [(lo, hi, "Z", 999_999.0)]}
    merged = merge_into_spec(a, hand_spec, generated)

    # Generated wins: only the generated (1.0 mm^2) entry survives.
    assert merged["bearings"] == [(lo, hi, "Z", 1.0)]

    # The drop is recorded in the derivation log, naming the winner.
    new_derived = generated.derived[before_derived:]
    assert len(new_derived) == 1
    fact = new_derived[0]
    assert fact.connection == "the real connection"
    assert fact.rule == "merge_into_spec.dedup"
    assert "999999" in fact.fact or "999999.0" in fact.fact
    assert "the real connection" in fact.fact

    # The drop also surfaces as a non-failing Finding (visible in the report).
    new_findings = generated.findings[before_findings:]
    override_findings = [f for f in new_findings if f.check == "connection_override"]
    assert len(override_findings) == 1
    assert override_findings[0].passed
    assert "the real connection" in override_findings[0].detail


# -- negative test 4: unknown datum name is a hard diagnostic with suggestions

def test_unknown_datum_name_raises_with_suggestion():
    a, lo, hi = _two_washers()
    with pytest.raises(ValueError, match="did you mean"):
        Connection(kind=_NoopType(), parts=[lo, hi], surfaces={lo.id: "topp"})


def test_unknown_datum_name_lists_available_datums():
    a, lo, hi = _two_washers()
    with pytest.raises(ValueError) as exc_info:
        Connection(kind=_NoopType(), parts=[lo, hi], surfaces={lo.id: "nonexistent"})
    assert "base" in str(exc_info.value) and "top" in str(exc_info.value)


# -- defensive: fewer than 2 parts is rejected --------------------------------

def test_connection_requires_two_or_more_parts():
    a, lo, hi = _two_washers()
    with pytest.raises(ValueError, match="2\\+"):
        Connection(kind=_NoopType(), parts=[lo])


# -- rock anchor subsumption: generated checks reproduce the old
# hand-written lists one-for-one -------------------------------------------

def test_rock_anchor_connections_subsume_old_checks():
    from pathlib import Path
    details_dir = Path(__file__).resolve().parents[1] / "details"

    detail = compile_spec_file(details_dir / "rock_anchor.spec.yaml")
    report = detail.validate()
    assert report.ok, report

    bearing_findings = [f for f in report.findings if f.check == "bearing"]
    # Old ``_bearings()``: 6 per rod x 2 rods (leveling stack + angle-on-leg)
    # + 4 per bolt x 2 bolts (bolt/washer/angle clamp stack) = 20.
    assert len(bearing_findings) == 20
    assert all(f.passed for f in bearing_findings)

    hw_findings = [f for f in report.findings if f.check == "connection_hardware"]
    # 7 hardware items per rod x 2 rods + 4 per bolt x 2 bolts = 22.
    assert len(hw_findings) == 22
    assert all(f.passed for f in hw_findings)

    # Old ``_expected_overlaps()``: 3 per rod x 2 + 1 per bolt x 2 = 8.
    # Old ``_bonds()``: 5 per rod x 2 + 1 per bolt x 2 = 12.
    conns = detail.connections()
    total_overlaps = set()
    total_bonds = []
    for c in conns:
        checks = c.generate_checks(detail.assembly)
        total_overlaps |= checks.expected_overlaps
        total_bonds.extend(checks.bonds)
    assert len(total_overlaps) == 8
    assert len(total_bonds) == 12

    # Derivation log + Construction-Graph edges are populated and the
    # install-order graph across all 4 connections is acyclic (validate()
    # already proved this by not raising).
    assert len(detail.derivation_log) > 0
    assert len(detail.connection_edges) > 0
    order_edges = [e for e in detail.connection_edges if e.kind == "installed_before"]
    assert order_edges  # the chain edges are present
    load_path_edges = [e for e in detail.connection_edges
                        if e.kind in ("bears_on", "fastened_by", "transfers_load_to")]
    assert load_path_edges  # load-path annotations were generated
