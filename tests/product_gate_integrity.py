"""Automatic integrity evidence for named standalone-product gates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from detailgen.certification import discover_contracts
from detailgen.core.buildinfo import build_manifest
from detailgen.spec import compile_spec_file


class ProductGateIntegrityError(AssertionError):
    """A canonical product cannot supply current authoritative evidence."""


@dataclass(frozen=True)
class CurrentProductEvidence:
    """Current model identity retained for release-package reconciliation."""

    detail: object
    spec_path: Path
    assembly_hash: str
    selection_fingerprint: str | None
    model_fingerprint: str | None


def resolve_product_subject(
    slug: str,
    details_dir: str | Path,
    repo_root: str | Path,
) -> Path | None:
    """Resolve a gate owner to its canonical standalone subject, if explicit."""
    details_dir = Path(details_dir)
    repo_root = Path(repo_root)
    contracts = {
        contract.slug: contract
        for contract in discover_contracts(details_dir, repo_root=repo_root)
    }
    contract = contracts.get(slug)
    if contract is not None:
        return contract.subject.source.resolve()

    names = (slug, slug.replace("-", "_"))
    for name in dict.fromkeys(names):
        candidate = details_dir / f"{name}.spec.yaml"
        if candidate.is_file():
            return candidate.resolve()
    return None


def _blocking_description(rows) -> str:
    descriptions = []
    for row in rows:
        check = getattr(row, "check", getattr(row, "family", "unknown-check"))
        subject = getattr(row, "subject", "unknown-subject")
        verdict = getattr(
            row,
            "verdict",
            getattr(row, "verdict_display", "BLOCKING"),
        )
        detail = getattr(row, "detail", "")
        descriptions.append(
            f"{check} on {subject} [{verdict}]"
            + (f": {detail}" if detail else "")
        )
    return "; ".join(descriptions) or "no blocking rows were reported"


def verify_inner_integrity(
    slug: str,
    spec_path: str | Path,
) -> CurrentProductEvidence:
    """Compile and require clean authoritative validation for one current spec."""
    spec_path = Path(spec_path).resolve()
    prefix = f"detail gate {slug!r} canonical subject {spec_path.name!r}"
    try:
        detail = compile_spec_file(spec_path)
        report = detail.validate()
    except Exception as exc:
        raise ProductGateIntegrityError(
            f"{prefix} could not compile and validate: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    blocking = tuple(report.blocking)
    if report.ok is not True or blocking:
        raise ProductGateIntegrityError(
            f"{prefix} failed authoritative validation "
            f"(ok={report.ok!r}, blocking_count={len(blocking)}): "
            f"{_blocking_description(blocking)}"
        )

    try:
        assembly_hash = build_manifest(detail.assembly)["assembly_hash"]
    except Exception as exc:
        raise ProductGateIntegrityError(
            f"{prefix} could not compute current model identity: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    governance = getattr(detail, "design_governance", None)
    return CurrentProductEvidence(
        detail=detail,
        spec_path=spec_path,
        assembly_hash=assembly_hash,
        selection_fingerprint=(
            governance.selection_digest if governance is not None else None
        ),
        model_fingerprint=(
            governance.model_digest if governance is not None else None
        ),
    )
