"""Load-path REPRESENTATION check (task ONTOLOGY, P5).

Written mutation-style (the permits-vs-requires discipline applied to the load
path): the FIRST and load-bearing test is the NEGATIVE one — the gravity-seated
defect class, proven on rock-anchor geometry. A support that only RESTS on its
chain, with no connection that transfers the load, must FAIL with the break
named; the identical geometry with the transfer claim intact must be REPRESENTED.
A check that only ever passed on good data would not prove the guard has teeth.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from detailgen.spec.compiler import compile_spec_file

from detailgen.assemblies import Edge
from detailgen.core.ontology import OntologyError
from detailgen.validation.coverage import UNKNOWN
from detailgen.validation.loadpath import (
    check_load_path,
    load_path_findings,
    transfers_by_connection,
)


# A minimal rock-anchor-shaped load graph: the leg (support) reaches the boulder
# (ground) only THROUGH the anchor connection (leg-angle-rod-boulder). This is
# the real rock anchor's connectivity, in miniature, so the defect is proven on
# rock-anchor geometry without rebuilding CadQuery.
_ROLES = {"leg": "support", "angle": "connector", "rod": "connector",
          "boulder": "ground"}
_EDGES = [
    Edge("angle", "leg", "bears_on", "anchor"),
    Edge("rod", "angle", "transfers_load_to", "anchor"),
    Edge("rod", "boulder", "fastened_by", "anchor"),
]


# -- THE NEGATIVE TEST (gravity-seated defect class), first ------------------


def test_gravity_seated_support_has_no_represented_load_path():
    """The live defect: a member merely RESTS on its chain — the connection
    does_not_transfer the downward load (a gravity seat with no load-carrying
    fastener). The support must reach no ground and the check must FAIL, naming
    the break. THEN the identical geometry with the transfer intact must be
    REPRESENTED — that contrast is the teeth."""
    broken = check_load_path(
        load_class="downward_load", roles=_ROLES, edges=_EDGES,
        transfers={"anchor": False})  # does_not_transfer -> edges drop out
    assert len(broken.findings) == 1
    f = broken.findings[0]
    assert not f.passed
    assert "REPRESENTED" not in f.detail
    assert "leg" in f.subject and "BROKEN" in f.detail
    assert not broken.paths[0].represented

    intact = check_load_path(
        load_class="downward_load", roles=_ROLES, edges=_EDGES,
        transfers={"anchor": True})
    assert intact.findings[0].passed
    assert "downward-load path REPRESENTED" in intact.findings[0].detail
    assert intact.paths[0].chain == ("leg", "angle", "rod", "boulder")


def test_no_transfer_claim_also_breaks_the_path():
    """Unknown (no claim) is not assumed: a connection with no transfer claim
    for the class drops out exactly like an explicit does_not_transfer."""
    r = check_load_path(load_class="downward_load", roles=_ROLES, edges=_EDGES,
                        transfers={})  # anchor makes no claim -> None
    assert not r.findings[0].passed
    assert "no transfer claim" in r.findings[0].detail


def test_missing_ground_role_is_broken_not_crash():
    roles = {"leg": "support", "angle": "connector"}  # no ground
    r = check_load_path(load_class="downward_load", roles=roles, edges=_EDGES,
                        transfers={"anchor": True})
    assert not r.findings[0].passed
    assert "ground" in r.findings[0].detail


def test_reserved_load_class_is_a_teaching_error():
    """A reachability proof only exists for a PROVABLE load class; asking for a
    reserved one is a teaching error, not a silent empty result."""
    with pytest.raises(OntologyError, match="reserved"):
        check_load_path(load_class="lateral_push", roles=_ROLES, edges=_EDGES,
                        transfers={"anchor": True})


def test_findings_are_deterministic_per_support():
    roles = {"legA": "support", "legB": "support", "g": "ground"}
    edges = [Edge("legA", "g", "bears_on", "c"), Edge("legB", "g", "bears_on", "c")]
    r = check_load_path(load_class="downward_load", roles=roles, edges=edges,
                        transfers={"c": True})
    subjects = [f.subject for f in r.findings]
    assert subjects == sorted(subjects)  # support-id order


# -- rock anchor integration: real detail, both authoring paths --------------

_REPO = Path(__file__).resolve().parents[1]


# Factory keeping the ``RockAnchor()`` call syntax; compiles the detail's
# spec.yaml (the imperative mirror is retired).
def RockAnchor():
    return compile_spec_file(_REPO / "details" / "rock_anchor.spec.yaml")


def test_rock_anchor_transfer_claims_gate_the_path():
    """The anchor's real ThreadedRodEpoxyAnchor claim carries downward_load; the
    per-connection transfer verdicts come from the type's claims, not a stub."""
    detail = RockAnchor()
    verdicts = transfers_by_connection(detail.connections(), "downward_load")
    assert all(v is True for v in verdicts.values())
    # and no claim exists for a reserved class the anchor doesn't characterise
    assert transfers_by_connection(detail.connections(), "shear") == {
        c.label: None for c in detail.connections()}


def test_rock_anchor_downward_load_path_is_represented():
    detail = RockAnchor()
    report = detail.validate()
    lp = [f for f in report.findings if f.check == "load_path"]
    assert len(lp) == 1
    assert lp[0].passed
    assert "downward-load path REPRESENTED" in lp[0].detail
    # the represented chain runs from the leg (support) to the boulder (ground)
    assert "leg" in lp[0].detail and "boulder" in lp[0].detail


def test_rock_anchor_coverage_flips_loadpath_to_analyzed():
    detail = RockAnchor()
    detail.validate()
    rows = {r.family: r for r in detail.coverage_matrix()}
    assert rows["Load-path representation"].verdict != UNKNOWN
    assert rows["Load-path representation"].verdict == "PASS"
    # capacity is a DIFFERENT family and stays honestly UNKNOWN
    assert rows["Structural capacity"].verdict == UNKNOWN


def test_rock_anchor_spec_and_imperative_emit_identical_load_path():
    """Equivalence (req 7): both authoring paths declare the same roles and must
    produce byte-identical load-path findings."""
    from detailgen.spec import compile_spec, load_spec_file
    imp = RockAnchor()
    spec = compile_spec(load_spec_file(_REPO / "details" / "rock_anchor.spec.yaml"))
    imp_lp = [(f.check, f.subject, f.passed, f.detail)
              for f in imp.validate().findings if f.check == "load_path"]
    spec_lp = [(f.check, f.subject, f.passed, f.detail)
               for f in spec.validate().findings if f.check == "load_path"]
    assert imp_lp and imp_lp == spec_lp
