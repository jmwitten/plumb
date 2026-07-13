"""The ``glued`` ConnectionType (task GLUE — the R-GLUE work order's plain
face-to-face adhesive bond, retired by owner directive from the caddy's
pocket-screw declaration).

Pins the type's semantics exactly as its docstring claims them:

- connectivity is a ``bonded_pairs`` bond + ONE ``bonded_to`` edge — the
  adhesive analog of ``fastened_by``, load-path-eligible and gated by the
  type's transfer claims like every other edge;
- NO gravity seat (no ``bears_on``, no ``bearing_pairs``), NO part-level
  ``installed_before`` edge, NO hardware (declaring any is a loud
  contradiction), exactly two members (a bond plane is pairwise); cure is a
  typed process fact rather than an assumption-parsed part edge;
- ``install_contract`` is the explicit ``()`` — "nothing to contract", never
  the base ``None`` ("cannot represent") — so the Fastener-installability
  machinery emits NOTHING for the joint: no contract, no NO-METHOD UNKNOWN,
  no axis findings;
- substrate is deliberately NOT in the type's claims (the R-SUBSTRATE
  lesson): the claims name only the adhesive-bond mechanism.

Ends with the synthetic two-board glued spec: compiles through the real spec
path and validates with ZERO findings from the Fastener-installability family
(the family row stays the honest ``UNKNOWN — NOT ANALYZED`` — there is no
fastener to install, which is not the same statement as "installable").
"""

from __future__ import annotations

import pytest

from detailgen.core import IN
from detailgen.components import Lumber, StructuralScrew
from detailgen.assemblies import DetailAssembly, Connection, connection_types
from detailgen.assemblies.connection import Glued
from detailgen.assemblies.event_graph import ProcessFact
from detailgen.spec.compiler import compile_spec
from detailgen.spec.loader import load_spec_text


# -- fixtures -----------------------------------------------------------------

def _two_boards():
    """A board with a second board stacked on top of it (edge on edge in the
    Lumber local frame — Z is the depth axis) — the minimal glued mating
    plane."""
    a = DetailAssembly("glue-up")
    lo = a.add(Lumber("2x4", 12 * IN, name="lower board"))
    hi = a.add(Lumber("2x4", 12 * IN, name="upper board"),
               at=(0, 0, lo.component.depth))
    return a, lo, hi


def _glued(lo, hi, assumptions=None):
    return Connection(
        kind=Glued(), parts=[lo, hi],
        assumptions=assumptions or [
            "Long-grain face-to-face bond; glue both faces, clamp, cure per "
            "the adhesive label; capacity NOT analyzed."],
        label="lower -> upper (glued)")


# -- registry + type semantics -------------------------------------------------

def test_glued_is_registered():
    assert connection_types.get("glued") is Glued


def test_glued_derives_bond_and_bonded_to_edge_only():
    """The joint's whole derived closure: one connectivity bond + one
    ``bonded_to`` edge. No bearings, no allowed intersections (the members
    meet at a touching plane), no install-order edges, no findings."""
    a, lo, hi = _two_boards()
    checks = _glued(lo, hi).generate_checks(a)

    assert checks.bonds == [(lo, hi)]
    assert checks.bearings == []
    assert checks.expected_overlaps == set()
    assert checks.findings == []          # no hardware -> no presence findings
    assert checks.installs == []          # nothing to contract (see below)

    assert len(checks.edges) == 1
    edge = checks.edges[0]
    assert (edge.a, edge.b, edge.kind) == (lo.id, hi.id, "bonded_to")
    assert edge.connection == "lower -> upper (glued)"
    assert not [e for e in checks.edges if e.kind == "installed_before"]
    assert not [e for e in checks.edges if e.kind == "bears_on"]


def test_glued_transfer_claims_mechanism_only_no_gravity_no_substrate():
    """pull_out + shear via the adhesive bond, placeholder confidence
    (capacity is never claimed); NO downward_load claim (no gravity seat);
    and NO substrate words in the type text — grain/face knowledge is
    per-connection (the R-SUBSTRATE lesson)."""
    claims = {c.load_class: c for c in Glued.transfer_claims}
    assert set(claims) == {"pull_out", "shear"}
    for c in claims.values():
        assert c.transfers is True
        assert c.confidence == "placeholder"
        assert "representative" in c.reference
    # the type never asserts what grain its consumers mate.
    for c in claims.values():
        assert "grain" not in c.reference.lower()
        assert "face-to-face" not in c.reference.lower()
    assert "downward_load" not in claims


def test_glued_bonded_to_is_load_path_eligible():
    """The bonded_to edge is a load-bearing edge kind — an adhesive bond
    carries load between its members exactly as a fastener does, gated by
    the connection's claims per class like every other edge."""
    from detailgen.validation.loadpath import LOAD_BEARING_EDGE_KINDS
    assert "bonded_to" in LOAD_BEARING_EDGE_KINDS


def test_glued_install_contract_is_explicit_empty_not_none():
    """The honest "nothing to contract" state: ``()`` — distinct from the
    base ``None`` ("cannot represent") — so no fastener-class hardware is
    ever flagged NO-METHOD on this type, and nothing is judged either."""
    a, lo, hi = _two_boards()
    conn = _glued(lo, hi)
    assert conn.kind.install_contract(conn) == ()
    assert conn.kind.install_contract(conn) is not None


def test_glued_supplies_safe_default_cure_and_preserves_authored_refinement():
    a, lo, hi = _two_boards()
    default_conn = _glued(lo, hi)
    assert default_conn.kind.supported_process_kinds() == frozenset({"cure"})
    (default,) = default_conn.kind.process_events(default_conn)
    assert default.provenance == "connectiontype_default"
    assert default.completion == "selected_label_full_cure"
    assert "actual shop conditions" in default.why

    authored = ProcessFact(
        kind="cure", instructions=("Clamp the selected glue-up.",),
        completion="selected_label_full_cure",
        why="The selected product governs this glue-up.",
        provenance="authored_process_fact")
    refined = _glued(lo, hi)
    refined.process = (authored,)
    assert refined.kind.process_events(refined) == (authored,)


def test_glued_rejects_hardware():
    """A glued joint declaring hardware is a contradiction — the adhesive IS
    the joint. Raised loudly at derivation time, never absorbed."""
    a, lo, hi = _two_boards()
    screw = a.add(StructuralScrew(0.19 * IN, 2 * IN, name="stray screw"))
    conn = Connection(kind=Glued(), parts=[lo, hi], hardware=[screw])
    with pytest.raises(ValueError, match="expected 0 hardware"):
        conn.generate_checks(a)


def test_glued_requires_exactly_two_members():
    """A bond plane is pairwise: a three-member glue-up is two declared
    joints, not one — a wrong-count declaration is a teaching error."""
    a, lo, hi = _two_boards()
    third = a.add(Lumber("2x4", 12 * IN, name="third board"),
                  at=(0, 0, 2 * lo.component.depth))
    conn = Connection(kind=Glued(), parts=[lo, hi, third])
    with pytest.raises(ValueError, match="EXACTLY two members"):
        conn.generate_checks(a)


# -- the synthetic two-board glued spec through the real pipeline --------------

_GLUED_SPEC = """
name: glued smoke
type: glued_smoke
units: in

params:
  board_len: 12.0

components:
  - id: lower
    type: lumber
    name: lower board
    params: {nominal: "2x4", length: "$board_len"}
  - id: upper
    type: lumber
    name: upper board
    params: {nominal: "2x4", length: "$board_len"}
    place: {raw: {at: [0, 0, "3.5 in"]}}

connections:
  - type: glued
    label: "lower -> upper (glued, edge to edge)"
    parts: [lower, upper]
    assumptions:
      - "Long-grain edge to long-grain edge — glue both mating faces, clamp, cure per the adhesive label; bond capacity NOT analyzed."

validation:
  bearings:
    - {a: upper, b: lower, axis: Z, area: 1000}   # the gravity seat, declared SEPARATELY from the bond
"""


def test_synthetic_glued_spec_compiles_clean_on_the_family():
    """The two-board glued spec through the REAL spec path: it validates with
    ZERO findings from the Fastener-installability family — no contract, no
    NO-METHOD UNKNOWN, no axis verdicts (there is no fastener to install) —
    and the family row stays the honest ``UNKNOWN — NOT ANALYZED``, never a
    PASS nothing proved. The declared bearing (the gravity seat the bond
    does NOT supply) passes, and the bond keeps the assembly connected."""
    detail = compile_spec(load_spec_text(_GLUED_SPEC))
    report = detail.validate()

    install_findings = [f for f in report.findings
                        if f.check.startswith("install_")]
    assert install_findings == []
    assert not [f for f in report.findings if not f.passed]
    assert report.ok

    matrix = {row.family: row for row in report.coverage_matrix()}
    fam = matrix["Fastener installability"]
    assert fam.verdict == "UNKNOWN — NOT ANALYZED"
    assert fam.checks_run == 0

    # the declared seat passes; the bond edge + bond connectivity are derived.
    bearing = [f for f in report.findings if f.check == "bearing"]
    assert len(bearing) == 1 and bearing[0].passed
    checks = detail._connection_checks
    assert [(e.kind) for e in checks.edges] == ["bonded_to"]
    assert len(checks.bonds) == 1
