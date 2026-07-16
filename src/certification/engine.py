"""Public orchestration API for generic construction-build certification."""

from __future__ import annotations

from dataclasses import replace

from .adapters import StandaloneSpecAdapter
from .model import (
    CertificationContext,
    CertificationContract,
    CertificationFinding,
    CertificationResult,
    FindingState,
)
from .rules import DEFAULT_RULES


class CertificationUsageError(ValueError):
    """A request cannot select a supported certification subject."""


DEFAULT_ADAPTERS = {"standalone_detail": StandaloneSpecAdapter()}


def _apply_decisions(
    contract: CertificationContract,
    findings: tuple[CertificationFinding, ...],
) -> tuple[tuple[CertificationFinding, ...], tuple]:
    decisions = {
        (row.rule_id, row.evidence_fingerprint): row
        for row in contract.decisions
    }
    applied = []
    resolved = []
    for finding in findings:
        decision = decisions.get((finding.rule_id, finding.evidence_fingerprint))
        if (
            finding.state is FindingState.NEEDS_DECISION
            and decision is not None
            and decision.outcome == "unknown_allowed"
        ):
            resolved.append(replace(
                finding,
                state=FindingState.WARN,
                detail=f"UNKNOWN accepted by owner decision: {finding.detail}",
            ))
            applied.append(decision)
        else:
            resolved.append(finding)
    return tuple(resolved), tuple(applied)


def certify_contract(
    contract: CertificationContract,
    *,
    adapters=None,
    rules=DEFAULT_RULES,
) -> CertificationResult:
    registry = DEFAULT_ADAPTERS if adapters is None else adapters
    try:
        adapter = registry[contract.subject.kind]
    except KeyError:
        raise CertificationUsageError(
            f"unsupported certification adapter {contract.subject.kind!r}"
        ) from None

    primary = adapter.collect(contract)
    repeat = adapter.collect(contract)
    context = CertificationContext(primary=primary, repeat=repeat, contract=contract)
    findings = []
    for rule in rules:
        try:
            findings.append(rule.evaluate(context))
        except Exception as exc:
            findings.append(CertificationFinding(
                rule_id=rule.id,
                state=FindingState.FAIL,
                subject=contract.slug,
                detail=f"rule raised {type(exc).__name__}: {exc}",
            ))
    resolved, applied = _apply_decisions(contract, tuple(findings))
    return CertificationResult(
        slug=contract.slug,
        findings=resolved,
        applied_decisions=applied,
    )
