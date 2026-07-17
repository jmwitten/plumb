"""Versioned workflow commands consumed by Plumb orchestration."""

from __future__ import annotations

from copy import deepcopy


_WORKFLOW_CONTRACT: dict[str, object] = {
    "schema": "detailgen/workflow-contract/v1",
    "tests": {
        "product_inner": {
            "argv": [
                "pytest",
                "--detail-gate",
                "{slug}",
                "--detail-cadence",
                "inner",
                "-q",
            ],
            "normal_product_gate": True,
        },
        "product_release": {
            "argv": [
                "pytest",
                "--detail-gate",
                "{slug}",
                "--detail-cadence",
                "release",
                "-q",
            ],
            "normal_product_gate": True,
        },
        "platform_integration": {
            "argv": ["pytest", "--platform-tier", "integration", "-q"],
            "normal_product_gate": False,
        },
        "platform_audit": {
            "argv": ["pytest", "--platform-tier", "audit", "-q"],
            "normal_product_gate": False,
        },
        "repository_verification": {
            "argv": ["pytest", "-q", "-n", "4"],
            "normal_product_gate": False,
        },
    },
}


def build_workflow_contract() -> dict[str, object]:
    """Return an isolated deterministic copy of the public workflow contract."""
    return deepcopy(_WORKFLOW_CONTRACT)
