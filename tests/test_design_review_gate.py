from dataclasses import replace
from pathlib import Path

import pytest

from detailgen.design_review import (
    Approval,
    DeliveryConfirmation,
    DesignReviewGateError,
    governance_for_review,
    load_design_review_file,
    model_fingerprint,
    selection_fingerprint,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures/design_review/valid.design-review.yaml"
)


@pytest.fixture
def valid_doc():
    return load_design_review_file(FIXTURE)


def approve(doc):
    digest = selection_fingerprint(doc)
    return replace(
        doc,
        modeling_approval=Approval(
            approved_by="Joel Witten",
            approved_on="2026-07-14",
            selection_fingerprint=digest,
        ),
    )


def approve_and_confirm(doc, spec_payload, selected_concept):
    applied = replace(
        doc,
        decision=replace(doc.decision, application="implemented"),
    )
    digest = selection_fingerprint(applied)
    return replace(
        applied,
        modeling_approval=Approval(
            approved_by="Joel Witten",
            approved_on="2026-07-14",
            selection_fingerprint=digest,
        ),
        delivery_confirmation=DeliveryConfirmation(
            approved_by="Joel Witten",
            approved_on="2026-07-14",
            selection_fingerprint=digest,
            model_fingerprint=model_fingerprint(
                spec_payload, selected_concept
            ),
        ),
    )


def test_valid_but_unapproved_review_cannot_be_promoted(valid_doc):
    governance = governance_for_review(
        valid_doc, selected_concept="concept_b"
    )

    with pytest.raises(DesignReviewGateError, match="modeling approval"):
        governance.require_modeling_approval()


def test_current_selection_approval_opens_modeling_gate(valid_doc):
    approved = approve(valid_doc)

    governance = governance_for_review(
        approved, selected_concept="concept_b"
    ).require_modeling_approval()

    assert governance.modeling_ready
    assert not governance.delivery_ready


def test_selected_concept_must_match_decision(valid_doc):
    approved = approve(valid_doc)

    with pytest.raises(DesignReviewGateError, match="selected concept"):
        governance_for_review(
            approved, selected_concept="concept_a"
        ).require_modeling_approval()


def test_stale_modeling_approval_fails(valid_doc):
    approved = approve(valid_doc)
    changed = replace(
        approved,
        brief=replace(
            approved.brief,
            use=approved.brief.use + " The changed use includes heavier books.",
        ),
    )

    with pytest.raises(DesignReviewGateError, match="stale selection"):
        governance_for_review(
            changed, selected_concept="concept_b"
        ).require_modeling_approval()


def test_delivery_requires_confirmation(valid_doc):
    approved = approve(valid_doc)
    governance = governance_for_review(
        approved,
        selected_concept="concept_b",
        spec_payload={"name": "example", "components": []},
    )

    with pytest.raises(DesignReviewGateError, match="recommendation_only"):
        governance.require_delivery_confirmation()


def test_delivery_requires_current_selection_and_model_hash(valid_doc):
    spec_payload = {"name": "example", "components": []}
    confirmed = approve_and_confirm(valid_doc, spec_payload, "concept_b")
    governance = governance_for_review(
        confirmed,
        selected_concept="concept_b",
        spec_payload=spec_payload,
    )

    assert governance.require_delivery_confirmation().delivery_ready

    changed = {**spec_payload, "type": "changed"}
    with pytest.raises(DesignReviewGateError, match="stale model"):
        governance_for_review(
            confirmed,
            selected_concept="concept_b",
            spec_payload=changed,
        ).require_delivery_confirmation()


def test_invalid_review_fails_before_approval(valid_doc):
    invalid = replace(valid_doc, concepts=valid_doc.concepts[:2])
    digest = selection_fingerprint(invalid)
    invalid = replace(
        invalid,
        modeling_approval=Approval(
            approved_by="Joel Witten",
            approved_on="2026-07-14",
            selection_fingerprint=digest,
        ),
    )

    with pytest.raises(DesignReviewGateError, match="incomplete"):
        governance_for_review(
            invalid, selected_concept="concept_b"
        ).require_modeling_approval()
