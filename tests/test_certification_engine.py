from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from detailgen.certification import (
    BomEvidence,
    CertificationContract,
    ConnectionEvidence,
    CountIntent,
    DecisionRecord,
    EvidenceSnapshot,
    FabricationEvidence,
    FindingState,
    GovernanceEvidence,
    GovernanceIntent,
    IntentContract,
    IntentSelector,
    PartEvidence,
    ValidationEvidence,
    ValidationFindingEvidence,
    load_contract,
)
from detailgen.certification.engine import (
    CertificationUsageError,
    certify_contract,
)
from detailgen.certification.rules import DEFAULT_RULES


ROOT = Path(__file__).resolve().parents[1]
TOY_CONTRACT = ROOT / "tests/fixtures/certification/toy_panel.cert.yaml"


class FakeAdapter:
    kind = "standalone_detail"

    def __init__(self, *snapshots):
        self.snapshots = list(snapshots)
        self.calls = 0

    def collect(self, _contract):
        row = self.snapshots[min(self.calls, len(self.snapshots) - 1)]
        self.calls += 1
        return row


@pytest.fixture
def contract() -> CertificationContract:
    return load_contract(TOY_CONTRACT, repo_root=ROOT)


@pytest.fixture
def clean_snapshot(contract) -> EvidenceSnapshot:
    part = PartEvidence(
        id="panel-0",
        name="panel",
        component="HardwoodPanel",
        material="Indoor hardwood",
        source="generated",
        roles=(),
        solid_count=1,
        volume_mm3=100.0,
        bounds_mm=(0.0, 0.0, 0.0, 10.0, 20.0, 5.0),
    )
    return EvidenceSnapshot(
        slug=contract.slug,
        subject=contract.subject,
        source_fingerprint="source-a",
        validation=ValidationEvidence(ok=True),
        parts=(part,),
        connections=(),
        fabrication=(FabricationEvidence("panel-0", ("crosscut",)),),
        bom=(
            BomEvidence(
                item="hardwood panel",
                quantity=1,
                material="Indoor hardwood",
                dimensions="10 x 20 x 5 mm",
                source="generated",
                source_ids=("panel-0",),
                length_mm=20.0,
            ),
        ),
        governance=GovernanceEvidence(present=False),
    )


def _certify(contract, primary, repeat=None):
    repeat = primary if repeat is None else repeat
    adapter = FakeAdapter(primary, repeat)
    result = certify_contract(
        contract,
        adapters={"standalone_detail": adapter},
    )
    assert adapter.calls == 2
    return result


def test_clean_snapshot_passes_every_mandatory_rule(contract, clean_snapshot):
    result = _certify(contract, clean_snapshot)

    assert result.releasable
    assert not result.failed
    assert {row.rule_id for row in result.findings} == {
        "compile.success",
        "validation.clean",
        "geometry.parts_valid",
        "connections.resolved",
        "fabrication.fold",
        "bom.source_ids",
        "governance.ready",
        "intent.matches",
        "determinism.evidence",
    }
    assert all(row.state is FindingState.PASS for row in result.findings)


def test_validation_failure_cannot_be_suppressed_by_decision(
    contract, clean_snapshot
):
    failure = ValidationFindingEvidence(
        check="interference",
        subject="panel <-> wall",
        verdict="FAIL",
        detail="unexpected overlap",
        passed=False,
        blocking=True,
    )
    dirty = replace(
        clean_snapshot,
        validation=ValidationEvidence(
            ok=False,
            findings=(failure,),
            blocking=(failure,),
        ),
    )
    decided = replace(
        contract,
        decisions=(
            DecisionRecord(
                rule_id="validation.clean",
                outcome="unknown_allowed",
                rationale="cannot waive a failure",
                evidence_fingerprint="anything",
            ),
        ),
    )

    result = _certify(decided, dirty)

    finding = next(row for row in result.findings if row.rule_id == "validation.clean")
    assert finding.state is FindingState.FAIL
    assert result.applied_decisions == ()


def test_unknown_critical_claim_requires_a_matching_decision(
    contract, clean_snapshot
):
    unknown = ValidationFindingEvidence(
        check="capacity",
        subject="panel",
        verdict="UNKNOWN",
        detail="capacity not analyzed",
        passed=False,
        blocking=True,
    )
    unresolved = replace(
        clean_snapshot,
        validation=ValidationEvidence(
            ok=False,
            findings=(unknown,),
            blocking=(unknown,),
        ),
    )

    first = _certify(contract, unresolved)
    finding = next(row for row in first.findings if row.rule_id == "validation.clean")
    assert finding.state is FindingState.NEEDS_DECISION
    assert finding.evidence_fingerprint

    decided = replace(
        contract,
        decisions=(
            DecisionRecord(
                rule_id="validation.clean",
                outcome="unknown_allowed",
                rationale="owner accepts honestly unknown capacity",
                evidence_fingerprint=finding.evidence_fingerprint,
            ),
        ),
    )
    result = _certify(decided, unresolved)

    resolved = next(row for row in result.findings if row.rule_id == "validation.clean")
    assert resolved.state is FindingState.WARN
    assert "UNKNOWN" in resolved.detail
    assert result.releasable
    assert result.applied_decisions == decided.decisions


def test_stale_decision_does_not_apply(contract, clean_snapshot):
    unknown = ValidationFindingEvidence(
        check="capacity",
        subject="panel",
        verdict="UNKNOWN",
        detail="capacity not analyzed",
        passed=False,
        blocking=True,
    )
    unresolved = replace(
        clean_snapshot,
        validation=ValidationEvidence(False, (unknown,), (unknown,)),
    )
    stale = replace(
        contract,
        decisions=(
            DecisionRecord(
                "validation.clean",
                "unknown_allowed",
                "old answer",
                "stale-fingerprint",
            ),
        ),
    )

    result = _certify(stale, unresolved)

    assert result.needs_decision
    assert result.applied_decisions == ()


def test_duplicate_bom_source_id_fails(contract, clean_snapshot):
    duplicate = replace(
        clean_snapshot,
        bom=clean_snapshot.bom + (
            replace(
                clean_snapshot.bom[0],
                item="duplicate row",
                source_ids=("panel-0",),
            ),
        ),
    )

    result = _certify(contract, duplicate)

    finding = next(row for row in result.findings if row.rule_id == "bom.source_ids")
    assert finding.state is FindingState.FAIL
    assert "more than one BOM row" in finding.detail


def test_unresolved_connection_reference_fails(contract, clean_snapshot):
    broken = replace(
        clean_snapshot,
        connections=(ConnectionEvidence("panel-0", "missing", "bonded_to", "joint"),),
    )

    result = _certify(contract, broken)

    finding = next(row for row in result.findings if row.rule_id == "connections.resolved")
    assert finding.state is FindingState.FAIL
    assert "missing" in finding.detail


def test_declared_component_count_and_forbidden_selector_are_enforced(
    contract, clean_snapshot
):
    intended = replace(
        contract,
        intent=IntentContract(
            counts=(
                CountIntent(
                    selector=IntentSelector(component="HardwoodPanel"),
                    exactly=2,
                ),
            ),
            forbidden=(IntentSelector(name_contains="panel"),),
        ),
    )

    result = _certify(intended, clean_snapshot)

    finding = next(row for row in result.findings if row.rule_id == "intent.matches")
    assert finding.state is FindingState.FAIL
    assert "expected exactly 2" in finding.detail
    assert "forbidden selector matched" in finding.detail


def test_governance_intent_is_checked(contract, clean_snapshot):
    governed = replace(
        contract,
        intent=IntentContract(
            governance=GovernanceIntent(
                selected_concept="approved_design",
                modeling_ready=True,
                delivery_ready=True,
            )
        ),
    )

    result = _certify(governed, clean_snapshot)

    finding = next(row for row in result.findings if row.rule_id == "intent.matches")
    assert finding.state is FindingState.FAIL
    assert "governance is absent" in finding.detail


def test_invalid_geometry_and_fabrication_drift_fail(contract, clean_snapshot):
    invalid = replace(
        clean_snapshot,
        parts=(replace(clean_snapshot.parts[0], volume_mm3=0.0),),
        fabrication_error="FabricationFoldError: installed geometry drifted",
    )

    result = _certify(contract, invalid)

    states = {row.rule_id: row.state for row in result.findings}
    assert states["geometry.parts_valid"] is FindingState.FAIL
    assert states["fabrication.fold"] is FindingState.FAIL


def test_repeat_evidence_mismatch_fails_determinism(contract, clean_snapshot):
    changed = replace(
        clean_snapshot,
        parts=(replace(clean_snapshot.parts[0], volume_mm3=101.0),),
    )

    result = _certify(contract, clean_snapshot, changed)

    finding = next(row for row in result.findings if row.rule_id == "determinism.evidence")
    assert finding.state is FindingState.FAIL


def test_optional_documents_are_not_in_default_rule_catalog():
    assert not any(rule.id.startswith("documents.") for rule in DEFAULT_RULES)


def test_unsupported_adapter_is_a_usage_error(contract):
    unsupported = replace(
        contract,
        subject=replace(contract.subject, kind="site"),
    )

    with pytest.raises(CertificationUsageError, match="unsupported.*site"):
        certify_contract(unsupported, adapters={})
