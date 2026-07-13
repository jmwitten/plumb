"""Evidence vocabulary shared by cabinet validators and generated artifacts."""

from __future__ import annotations

from dataclasses import dataclass

EVIDENCE_LEVELS = frozenset({
    "derived",
    "calculated",
    "manufacturer_rated",
    "field_verified",
    "physically_tested",
    "certified",
    "assumed",
    "unknown",
})


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    subject: str
    level: str
    statement: str
    source: str = ""
    standard_ref: str = ""

    def __post_init__(self):
        if self.level not in EVIDENCE_LEVELS:
            raise ValueError(
                f"unknown evidence level {self.level!r}; known: "
                f"{sorted(EVIDENCE_LEVELS)}"
            )

