"""Canonical fingerprints for design selection and modeled conformance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from .schema import DesignReviewDoc


def selection_payload(doc: DesignReviewDoc) -> dict:
    """Return only the design content an owner selection approves."""
    return {
        "brief": asdict(doc.brief),
        "precedents": [asdict(item) for item in doc.precedents],
        "concepts": [asdict(item) for item in doc.concepts],
        "comparison": [asdict(item) for item in doc.comparison],
        "deviations": [asdict(item) for item in doc.deviations],
        "decision": asdict(doc.decision),
    }


def _digest(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def selection_fingerprint(doc: DesignReviewDoc) -> str:
    return _digest(selection_payload(doc))


def model_fingerprint(spec_payload: dict, selected_concept: str) -> str:
    return _digest({
        "selected_concept": selected_concept,
        "spec": spec_payload,
    })
