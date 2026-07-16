"""Governance binding for the selected pivot-side birdhouse."""

from pathlib import Path

import pytest

from detailgen.design_review import (
    DesignReviewGateError,
    load_design_review_file,
    validate_design_review,
)
from detailgen.spec import compile_spec_file


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "details/family_birdhouse.spec.yaml"
REVIEW = ROOT / "details/family_birdhouse.design-review.yaml"
SELECTION_FP = "b7f91b653c95270ebf35968478b2d3a686cf49e356c35482f3e2c2aed4b8e1ff"

pytestmark = pytest.mark.detail_gate(
    "family_birdhouse", contracts=("governance",)
)


def test_review_remains_complete_and_compares_three_access_architectures():
    doc = load_design_review_file(REVIEW)

    assert validate_design_review(doc).ok
    assert {concept.id for concept in doc.concepts} == {
        "pivot_side_classic",
        "hinged_roof_access",
        "removable_front_access",
    }
    assert len(doc.comparison) == 30


def test_selected_concept_is_implemented_and_bound_to_owner_modeling_approval():
    doc = load_design_review_file(REVIEW)

    assert doc.decision.selected_concept == "pivot_side_classic"
    assert doc.decision.application == "implemented"
    assert doc.modeling_approval is not None
    assert doc.modeling_approval.approved_by == "Joel Witten"
    assert doc.modeling_approval.selection_fingerprint == SELECTION_FP
    assert doc.delivery_confirmation is None


def test_spec_opts_in_and_production_is_ready_but_delivery_remains_gated():
    detail = compile_spec_file(SPEC)

    assert detail.design_governance is not None
    assert detail.design_governance.selected_concept == "pivot_side_classic"
    assert detail.require_modeling_approval() is detail
    with pytest.raises(DesignReviewGateError, match="delivery confirmation"):
        detail.require_delivery_ready()
