"""Immutable values for precedent-first design selection records."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


SCHEMA_ID = "detailgen/design-review/v1"
SOURCE_KINDS = ("commercial_product", "build_instruction")
ASSESSMENTS = ("advantage", "neutral", "disadvantage", "unknown")
APPLICATION_STATES = ("recommendation_only", "implemented")
CRITERIA = (
    "strength",
    "part_count",
    "fasteners",
    "operations",
    "tooling",
    "tolerances",
    "material",
    "appearance",
    "builder_skill",
    "instruction_complexity",
)
SIGNATURE_FIELDS = (
    "load_path",
    "joint_family",
    "part_topology",
    "fastening_strategy",
    "visible_seam_strategy",
    "fit_strategy",
)


class DesignReviewSchemaError(ValueError):
    """A structural or closed-vocabulary error in a design review."""


@dataclass(frozen=True)
class Requirement:
    id: str
    text: str


@dataclass(frozen=True)
class Constraint:
    id: str
    text: str
    priority: int


@dataclass(frozen=True)
class DesignBrief:
    use: str
    loads: str
    fit_range: str
    appearance: str
    builder_skill: str
    tools: tuple[str, ...]
    required_features: tuple[Requirement, ...]
    constraints: tuple[Constraint, ...]


@dataclass(frozen=True)
class Precedent:
    id: str
    kind: str
    title: str
    publisher: str
    url: str
    accessed_on: str
    construction_pattern: str
    lessons: tuple[str, ...]


@dataclass(frozen=True)
class ArchitectureSignature:
    load_path: str
    joint_family: str
    part_topology: str
    fastening_strategy: str
    visible_seam_strategy: str
    fit_strategy: str


@dataclass(frozen=True)
class NoveltyException:
    rationale: str
    cost_or_risk: str
    alternatives_rejected: str
    approved_by: str
    approved_on: str


@dataclass(frozen=True)
class ConceptFeature:
    id: str
    description: str
    precedent_refs: tuple[str, ...]


@dataclass(frozen=True)
class PartPurpose:
    part_family: str
    purpose: str
    requirement_refs: tuple[str, ...]
    feature_refs: tuple[str, ...]
    joinery_replacement: str


@dataclass(frozen=True)
class Concept:
    id: str
    title: str
    summary: str
    signature: ArchitectureSignature
    features: tuple[ConceptFeature, ...]
    parts: tuple[PartPurpose, ...]


@dataclass(frozen=True)
class ComparisonCell:
    id: str
    concept: str
    criterion: str
    assessment: str
    explanation: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class Deviation:
    feature_ref: str
    forcing_requirement: str
    exception: NoveltyException | None


@dataclass(frozen=True)
class Decision:
    selected_concept: str
    rationale: str
    decisive_cells: tuple[str, ...]
    tradeoffs: tuple[str, ...]
    application: str


@dataclass(frozen=True)
class Approval:
    approved_by: str
    approved_on: str
    selection_fingerprint: str


@dataclass(frozen=True)
class DeliveryConfirmation:
    approved_by: str
    approved_on: str
    selection_fingerprint: str
    model_fingerprint: str


@dataclass(frozen=True)
class DesignReviewDoc:
    schema: str
    project_id: str
    title: str
    status: str
    brief: DesignBrief
    precedents: tuple[Precedent, ...]
    concepts: tuple[Concept, ...]
    comparison: tuple[ComparisonCell, ...]
    deviations: tuple[Deviation, ...]
    decision: Decision
    modeling_approval: Approval | None = None
    delivery_confirmation: DeliveryConfirmation | None = None
    source_path: Path | None = field(default=None, compare=False, repr=False)
