"""Lifecycle gates for approved design selection and model conformance."""

from __future__ import annotations

from dataclasses import dataclass

from .fingerprint import model_fingerprint, selection_fingerprint
from .schema import DesignReviewDoc
from .validation import DesignReviewResult, validate_design_review


class DesignReviewGateError(RuntimeError):
    """A governed project cannot cross the requested lifecycle boundary."""


@dataclass(frozen=True)
class DesignGovernance:
    review: DesignReviewDoc
    result: DesignReviewResult
    selected_concept: str
    selection_digest: str
    model_digest: str | None = None

    @property
    def modeling_ready(self) -> bool:
        approval = self.review.modeling_approval
        return bool(
            self.result.ok
            and self.selected_concept == self.review.decision.selected_concept
            and approval is not None
            and approval.approved_by.strip()
            and approval.approved_on.strip()
            and approval.selection_fingerprint == self.selection_digest
        )

    @property
    def delivery_ready(self) -> bool:
        confirmation = self.review.delivery_confirmation
        return bool(
            self.modeling_ready
            and self.review.decision.application == "implemented"
            and self.model_digest is not None
            and confirmation is not None
            and confirmation.approved_by.strip()
            and confirmation.approved_on.strip()
            and confirmation.selection_fingerprint == self.selection_digest
            and confirmation.model_fingerprint == self.model_digest
        )

    def require_modeling_approval(self) -> "DesignGovernance":
        if not self.result.ok:
            summary = "; ".join(
                f"{finding.code} at {finding.path}"
                for finding in self.result.blocking
            )
            raise DesignReviewGateError(
                f"design review is incomplete and cannot be promoted: {summary}"
            )
        if self.selected_concept != self.review.decision.selected_concept:
            raise DesignReviewGateError(
                f"selected concept {self.selected_concept!r} does not match "
                f"the review decision {self.review.decision.selected_concept!r}"
            )
        approval = self.review.modeling_approval
        if approval is None or not (
            approval.approved_by.strip() and approval.approved_on.strip()
        ):
            raise DesignReviewGateError(
                "modeling approval is missing; a named owner must approve the "
                "current selection fingerprint before production promotion"
            )
        if approval.selection_fingerprint != self.selection_digest:
            raise DesignReviewGateError(
                "stale selection approval: the design review changed after "
                "modeling approval"
            )
        return self

    def require_delivery_confirmation(self) -> "DesignGovernance":
        self.require_modeling_approval()
        if self.review.decision.application != "implemented":
            raise DesignReviewGateError(
                f"decision is {self.review.decision.application}; governed "
                "delivery requires the selected concept to be implemented"
            )
        if self.model_digest is None:
            raise DesignReviewGateError(
                "delivery confirmation cannot be checked without a canonical "
                "model fingerprint"
            )
        confirmation = self.review.delivery_confirmation
        if confirmation is None or not (
            confirmation.approved_by.strip() and confirmation.approved_on.strip()
        ):
            raise DesignReviewGateError(
                "delivery confirmation is missing; a named owner must confirm "
                "the implemented model"
            )
        if confirmation.selection_fingerprint != self.selection_digest:
            raise DesignReviewGateError(
                "stale selection in delivery confirmation: the design review "
                "changed after confirmation"
            )
        if confirmation.model_fingerprint != self.model_digest:
            raise DesignReviewGateError(
                "stale model in delivery confirmation: the governed DetailSpec "
                "changed after confirmation"
            )
        return self


def governance_for_review(
    doc: DesignReviewDoc,
    *,
    selected_concept: str,
    spec_payload: dict | None = None,
) -> DesignGovernance:
    return DesignGovernance(
        review=doc,
        result=validate_design_review(doc),
        selected_concept=selected_concept,
        selection_digest=selection_fingerprint(doc),
        model_digest=(
            None
            if spec_payload is None
            else model_fingerprint(spec_payload, selected_concept)
        ),
    )
