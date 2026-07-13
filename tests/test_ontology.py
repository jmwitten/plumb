"""Construction ontology seed (task ONTOLOGY, P5): Role / LoadClass /
TransferCapability, the reserved-name teaching errors, and the honest coverage
posture (Load-path REPRESENTATION activated on the rock anchor; Structural
capacity UNKNOWN everywhere; platform untouched)."""

from __future__ import annotations

from pathlib import Path

import pytest

from detailgen.assemblies.connection import (
    BoltedClamp, FaceMountHanger, RailCapScrewed, ThreadedRodEpoxyAnchor,
    ToeScrewed,
)
from detailgen.core.ontology import (
    LOAD_CLASSES,
    ROLES,
    OntologyError,
    TransferClaim,
)
from detailgen.spec.compiler import compile_spec_file
from detailgen.validation.coverage import UNKNOWN, UNRESOLVED

_REPO = Path(__file__).resolve().parents[1]


def _compile(spec_name):
    """Compile a detail from its spec.yaml (the imperative mirrors are retired)."""
    return compile_spec_file(_REPO / "details" / spec_name)


# -- vocabulary tiers + teaching errors --------------------------------------


def test_provable_roles_and_load_classes_pass():
    for r in ("support", "connector", "ground"):
        assert ROLES.require(r) == r
    assert LOAD_CLASSES.require("downward_load") == "downward_load"


def test_reserved_role_is_a_teaching_error_not_unknown():
    with pytest.raises(OntologyError) as e:
        ROLES.require("barrier")
    msg = str(e.value)
    assert "reserved" in msg and "not yet provable" in msg
    assert "support" in msg and "connector" in msg  # names what IS provable


def test_reserved_load_class_names_the_provable_one():
    with pytest.raises(OntologyError, match="reserved"):
        LOAD_CLASSES.require("lateral_push")


def test_unknown_term_gets_a_did_you_mean_not_a_reserved_message():
    with pytest.raises(OntologyError) as e:
        ROLES.require("suport")  # typo
    msg = str(e.value)
    assert "unknown" in msg and "did you mean" in msg
    # NOT the reserved-term teaching phrasing (an unknown word isn't "reserved")
    assert "not yet provable" not in msg


def test_require_known_admits_reserved_but_not_unknown():
    # a transfer CLAIM may be about a reserved class (data), just not a typo
    assert LOAD_CLASSES.require_known("uplift") == "uplift"
    with pytest.raises(OntologyError, match="unknown"):
        LOAD_CLASSES.require_known("downwards_load")


# -- TransferClaim validation -------------------------------------------------


def test_transfer_claim_rejects_unknown_load_class():
    with pytest.raises(OntologyError):
        TransferClaim("gravity", True)


def test_transfer_claim_rejects_out_of_range_provenance():
    with pytest.raises(OntologyError):
        TransferClaim("downward_load", True, confidence="totally-sure")
    with pytest.raises(OntologyError):
        TransferClaim("downward_load", True, source_type="vibes")


# -- transfer claims are DATA on all 5 connection types ----------------------


def test_all_five_types_carry_honest_transfer_claims():
    types = [ThreadedRodEpoxyAnchor, BoltedClamp, FaceMountHanger, ToeScrewed,
             RailCapScrewed]
    for t in types:
        claims = t.transfer_claims
        assert claims, f"{t.__name__} should carry transfer claims"
        # every type carries the downward_load claim the path is proved over
        assert any(c.load_class == "downward_load" and c.transfers for c in claims)
        for c in claims:
            # honesty rule: NO invented official citations — a transfer claim is
            # never 'authoritative' (no code/manufacturer citation backs one yet)
            assert c.source_type != "authoritative"
            assert c.confidence in ("inferred", "placeholder")


def test_a_type_can_honestly_claim_does_not_transfer():
    # the plain face-mount hanger's uplift claim is an explicit does_not_transfer
    uplift = [c for c in FaceMountHanger.transfer_claims
              if c.load_class == "uplift"]
    assert uplift and uplift[0].transfers is False


# -- coverage posture (req 5): honest UNKNOWN where nothing ran ---------------


def test_rock_anchor_activates_load_path_but_not_capacity():
    detail = _compile("rock_anchor.spec.yaml")
    detail.validate()
    rows = {r.family: r for r in detail.coverage_matrix()}
    assert rows["Load-path representation"].verdict == "PASS"
    # Structural capacity is a DIFFERENT family; no check ran -> honest UNKNOWN
    assert rows["Structural capacity"].verdict == UNKNOWN
    assert rows["Code compliance"].verdict == UNKNOWN


def test_platform_load_path_unknown_capacity_unresolved_by_foundation():
    """The platform's Load-path family stays honestly UNKNOWN — NOT ANALYZED (no
    load_path finding). Its Structural capacity family, however, is now UNKNOWN —
    UNRESOLVED (blocking): FAB-3's foundation-capacity obligation RAN and honestly
    could not answer (uplift/lateral/soil are rung 4, out of scope by
    construction), which is distinct from NOT-ANALYZED and blocks a clean export."""
    detail = _compile("platform.spec.yaml")
    detail.validate()
    rows = {r.family: r for r in detail.coverage_matrix()}
    assert rows["Load-path representation"].verdict == UNKNOWN
    assert rows["Structural capacity"].verdict == UNRESOLVED


def test_declaring_a_reserved_role_on_a_detail_is_a_teaching_error():
    """A detail that declares a not-yet-provable role fails loudly (the check
    validates every declared role) — never a silent no-op."""
    from detailgen.validation.loadpath import load_path_findings
    detail = _compile("rock_anchor.spec.yaml")
    detail.validate()
    with pytest.raises(OntologyError, match="reserved"):
        load_path_findings(
            roles_by_name={"leg": "barrier"}, assembly=detail.assembly,
            connections=detail.connections(), edges=detail.connection_edges)


# -- evidence graph: ontology layer present (rock) / absent (platform) -------


def test_ontology_nodes_present_in_rock_anchor_graph():
    detail = _compile("rock_anchor.spec.yaml")
    detail.validate()
    g = detail.evidence_graph
    assert g.nodes_of_kind("role"), "roles should appear as graph nodes"
    assert g.nodes_of_kind("transfer_claim"), "transfer claims flow into the graph"
    lp = g.nodes_of_kind("load_path")
    assert lp and lp[0].attrs["represented"] is True
    # how_verified on the rod surfaces the whole represented chain (req 6)
    hv = g.how_verified("rod 0")
    assert hv["load_paths"] and hv["load_paths"][0]["represented"]
    assert "boulder" in hv["load_paths"][0]["chain"]


def test_platform_graph_carries_the_support_role_layer_but_no_load_path():
    """Task SUPPORT gave the platform a roles block; STRUCT task #19 extended it
    (boulder + the 3 pier blocks: ground; deck: walking_surface; trunk: existing —
    the CTXGROUND self-grounded context body). The graph carries exactly those role
    kinds and the connections' transfer-claim nodes — but NO load_path layer: the
    platform declares no `support`-role member, so the Load-path family stays
    honestly UNKNOWN (rung 2 not claimed; the rung-3 support check is what runs)."""
    detail = _compile("platform.spec.yaml")
    detail.validate()
    g = detail.evidence_graph
    role_labels = sorted(n.label for n in g.nodes_of_kind("role"))
    # distinct role kinds present (multiple ground bodies collapse to one label):
    assert set(role_labels) == {"ground", "walking_surface", "existing"}
    assert role_labels.count("ground") == 4  # boulder + 3 pier blocks
    assert not g.nodes_of_kind("load_path")
