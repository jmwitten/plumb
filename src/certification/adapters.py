"""Production adapters that expose build evidence to generic certification."""

from __future__ import annotations

from hashlib import sha256
from typing import Protocol

from ..core.process_graph import (
    _fabrication_record_of,
    verify_assembly_fabrication,
)
from ..spec.compiler import compile_spec_file
from .model import (
    BomEvidence,
    CertificationContract,
    ConnectionEvidence,
    EvidenceSnapshot,
    FabricationEvidence,
    GovernanceEvidence,
    PartEvidence,
    ValidationEvidence,
    ValidationFindingEvidence,
)


class BuildAdapter(Protocol):
    kind: str

    def collect(self, contract: CertificationContract) -> EvidenceSnapshot:
        """Compile one fresh subject and return immutable production evidence."""


def _exception_text(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _source_fingerprint(contract: CertificationContract) -> str:
    return sha256(contract.subject.source.read_bytes()).hexdigest()


def _validation_evidence(report) -> ValidationEvidence:
    findings = tuple(
        ValidationFindingEvidence(
            check=row.check,
            subject=row.subject,
            verdict=row.verdict,
            detail=row.detail,
            passed=row.passed,
            blocking=row.blocking,
        )
        for row in report.findings
    )
    return ValidationEvidence(
        ok=report.ok,
        findings=findings,
        blocking=tuple(row for row in findings if row.blocking),
    )


def _part_evidence(placed) -> PartEvidence:
    shapes = tuple(placed.world_solid().vals())
    boxes = tuple(shape.BoundingBox() for shape in shapes)
    bounds = (
        min(box.xmin for box in boxes),
        min(box.ymin for box in boxes),
        min(box.zmin for box in boxes),
        max(box.xmax for box in boxes),
        max(box.ymax for box in boxes),
        max(box.zmax for box in boxes),
    )
    component = placed.component
    return PartEvidence(
        id=placed.id,
        name=placed.name,
        component=type(component).__name__,
        material=component.material.name,
        source=getattr(component, "source", "generated"),
        roles=(),
        solid_count=len(shapes),
        volume_mm3=sum(float(shape.Volume()) for shape in shapes),
        bounds_mm=bounds,
    )


def _connection_evidence(edge) -> ConnectionEvidence:
    return ConnectionEvidence(
        a=edge.a,
        b=edge.b,
        kind=edge.kind,
        connection=edge.connection,
    )


def _fabrication_evidence(placed) -> FabricationEvidence | None:
    record = _fabrication_record_of(placed.component)
    if record is None:
        return None
    return FabricationEvidence(
        part_id=placed.id,
        steps=tuple(step.kind for step in record.steps),
    )


def _bom_evidence(row: dict) -> BomEvidence:
    return BomEvidence(
        item=row["item"],
        quantity=int(row["qty"]),
        material=row["material"],
        dimensions=row["dimensions"],
        source=row["source"],
        source_ids=tuple(sorted(row["ids"])),
        length_mm=(
            None if row["length_mm"] is None else float(row["length_mm"])
        ),
    )


def _governance_evidence(detail) -> GovernanceEvidence:
    governance = getattr(detail, "design_governance", None)
    if governance is None:
        return GovernanceEvidence(present=False)
    return GovernanceEvidence(
        present=True,
        selected_concept=governance.selected_concept,
        modeling_ready=governance.modeling_ready,
        delivery_ready=governance.delivery_ready,
    )


class StandaloneSpecAdapter:
    """Collect evidence for one declarative standalone detail specification."""

    kind = "standalone_detail"

    def collect(self, contract: CertificationContract) -> EvidenceSnapshot:
        fingerprint = _source_fingerprint(contract)
        try:
            detail = compile_spec_file(contract.subject.source)
            report = detail.validate()
            assembly = detail.assembly
        except Exception as exc:
            return EvidenceSnapshot(
                slug=contract.slug,
                subject=contract.subject,
                source_fingerprint=fingerprint,
                compile_error=_exception_text(exc),
            )

        fabrication_error = ""
        try:
            verify_assembly_fabrication(assembly)
        except Exception as exc:
            fabrication_error = _exception_text(exc)

        try:
            parts = tuple(
                sorted(
                    (_part_evidence(part) for part in assembly.parts),
                    key=lambda item: item.id,
                )
            )
            connections = tuple(
                sorted(
                    (_connection_evidence(edge) for edge in detail.connection_edges),
                    key=lambda item: (
                        item.kind, item.a, item.b, item.connection,
                    ),
                )
            )
            fabrication = tuple(
                row
                for row in (
                    _fabrication_evidence(part)
                    for part in sorted(assembly.parts, key=lambda p: p.id)
                )
                if row is not None
            )
            bom = tuple(
                sorted(
                    (_bom_evidence(row) for row in detail.bom_table()),
                    key=lambda item: (
                        item.item, item.dimensions, item.source_ids,
                    ),
                )
            )
        except Exception as exc:
            return EvidenceSnapshot(
                slug=contract.slug,
                subject=contract.subject,
                source_fingerprint=fingerprint,
                collector_error=_exception_text(exc),
                fabrication_error=fabrication_error,
                validation=_validation_evidence(report),
                governance=_governance_evidence(detail),
            )

        return EvidenceSnapshot(
            slug=contract.slug,
            subject=contract.subject,
            source_fingerprint=fingerprint,
            fabrication_error=fabrication_error,
            validation=_validation_evidence(report),
            parts=parts,
            connections=connections,
            fabrication=fabrication,
            bom=bom,
            governance=_governance_evidence(detail),
        )
