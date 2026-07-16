"""Command-line interface for deterministic build certification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .contract import ContractError, load_contract
from .engine import CertificationUsageError, certify_contract


def _find_repo_root(contract_path: Path) -> Path:
    resolved = contract_path.resolve()
    for parent in (resolved.parent, *resolved.parents):
        if (parent / "pyproject.toml").is_file():
            return parent
    return Path.cwd().resolve()


def _load_and_certify(path: Path):
    contract_path = Path(path).resolve()
    contract = load_contract(
        contract_path,
        repo_root=_find_repo_root(contract_path),
    )
    return certify_contract(contract)


def result_payload(result) -> dict:
    return {
        "slug": result.slug,
        "releasable": result.releasable,
        "failed": result.failed,
        "needs_decision": result.needs_decision,
        "findings": [
            {
                "rule_id": row.rule_id,
                "state": row.state.value,
                "subject": row.subject,
                "detail": row.detail,
                "evidence_fingerprint": row.evidence_fingerprint,
            }
            for row in result.findings
        ],
        "applied_decisions": [
            {
                "rule": row.rule_id,
                "outcome": row.outcome,
                "rationale": row.rationale,
                "evidence_fingerprint": row.evidence_fingerprint,
            }
            for row in result.applied_decisions
        ],
    }


def format_result(result) -> str:
    lines = [
        f"[{row.state.value}] {row.rule_id}: {row.subject} — {row.detail}"
        for row in result.findings
    ]
    for decision in result.applied_decisions:
        lines.append(
            f"[DECISION] {decision.rule_id}: {decision.outcome} — "
            f"{decision.rationale}"
        )
    state = (
        "FAILED" if result.failed
        else "NEEDS DECISION" if result.needs_decision
        else "RELEASABLE"
    )
    lines.append(f"Certification: {state}")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m detailgen.certification",
        description="Certify one construction build from its declarative contract.",
    )
    parser.add_argument("contract", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        result = _load_and_certify(args.contract)
    except (ContractError, CertificationUsageError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 4

    if args.as_json:
        print(json.dumps(result_payload(result), sort_keys=True))
    else:
        print(format_result(result), end="")

    if result.failed:
        return 1
    if result.needs_decision:
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through main()
    raise SystemExit(main())
