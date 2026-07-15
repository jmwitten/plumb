"""Immutable values shared by build-certification adapters and consumers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class FindingState(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    NEEDS_DECISION = "NEEDS_DECISION"


@dataclass(frozen=True)
class CertificationFinding:
    rule_id: str
    state: FindingState
    subject: str
    detail: str
    evidence_fingerprint: str = ""


@dataclass(frozen=True)
class DecisionRecord:
    rule_id: str
    outcome: str
    rationale: str
    evidence_fingerprint: str


@dataclass(frozen=True)
class SubjectContract:
    kind: str
    source: Path


@dataclass(frozen=True)
class IntentSelector:
    component: str | None = None
    material: str | None = None
    role: str | None = None
    name: str | None = None
    name_contains: str | None = None
    kind: str | None = None


@dataclass(frozen=True)
class CountIntent:
    selector: IntentSelector
    exactly: int | None = None
    minimum: int | None = None
    maximum: int | None = None


@dataclass(frozen=True)
class FabricationIntent:
    selector: IntentSelector
    steps: tuple[str, ...]


@dataclass(frozen=True)
class NumericRange:
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class BomIntent:
    item: str
    quantity: int
    length_mm: NumericRange | None = None


@dataclass(frozen=True)
class GovernanceIntent:
    selected_concept: str | None = None
    modeling_ready: bool | None = None
    delivery_ready: bool | None = None


@dataclass(frozen=True)
class IntentContract:
    counts: tuple[CountIntent, ...] = ()
    forbidden: tuple[IntentSelector, ...] = ()
    connections: tuple[CountIntent, ...] = ()
    fabrication: tuple[FabricationIntent, ...] = ()
    bom: tuple[BomIntent, ...] = ()
    governance: GovernanceIntent = field(default_factory=GovernanceIntent)


@dataclass(frozen=True)
class CertificationContract:
    schema_version: int
    slug: str
    subject: SubjectContract
    intent: IntentContract
    deliverables: tuple[str, ...]
    decisions: tuple[DecisionRecord, ...]
    source_path: Path


@dataclass(frozen=True)
class ValidationFindingEvidence:
    check: str
    subject: str
    verdict: str
    detail: str
    passed: bool
    blocking: bool


@dataclass(frozen=True)
class ValidationEvidence:
    ok: bool
    findings: tuple[ValidationFindingEvidence, ...] = ()
    blocking: tuple[ValidationFindingEvidence, ...] = ()


@dataclass(frozen=True)
class PartEvidence:
    id: str
    name: str
    component: str
    material: str
    source: str
    roles: tuple[str, ...]
    solid_count: int
    volume_mm3: float
    bounds_mm: tuple[float, float, float, float, float, float]


@dataclass(frozen=True)
class ConnectionEvidence:
    a: str
    b: str
    kind: str
    connection: str


@dataclass(frozen=True)
class FabricationEvidence:
    part_id: str
    steps: tuple[str, ...]


@dataclass(frozen=True)
class BomEvidence:
    item: str
    quantity: int
    material: str
    dimensions: str
    source: str
    source_ids: tuple[str, ...]
    length_mm: float | None


@dataclass(frozen=True)
class GovernanceEvidence:
    present: bool
    selected_concept: str = ""
    modeling_ready: bool = False
    delivery_ready: bool = False


@dataclass(frozen=True)
class EvidenceSnapshot:
    slug: str
    subject: SubjectContract
    source_fingerprint: str
    compile_error: str = ""
    collector_error: str = ""
    fabrication_error: str = ""
    validation: ValidationEvidence = field(
        default_factory=lambda: ValidationEvidence(ok=False)
    )
    parts: tuple[PartEvidence, ...] = ()
    connections: tuple[ConnectionEvidence, ...] = ()
    fabrication: tuple[FabricationEvidence, ...] = ()
    bom: tuple[BomEvidence, ...] = ()
    governance: GovernanceEvidence = field(
        default_factory=lambda: GovernanceEvidence(present=False)
    )


@dataclass(frozen=True)
class CertificationResult:
    slug: str
    findings: tuple[CertificationFinding, ...]
    applied_decisions: tuple[DecisionRecord, ...] = ()

    @property
    def failed(self) -> bool:
        return any(row.state is FindingState.FAIL for row in self.findings)

    @property
    def needs_decision(self) -> bool:
        return any(
            row.state is FindingState.NEEDS_DECISION for row in self.findings
        )

    @property
    def releasable(self) -> bool:
        return not self.failed and not self.needs_decision
