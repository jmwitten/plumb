"""Automatic integrity evidence for named standalone-product gates."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from pathlib import PurePosixPath

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


def _manifest_error(slug: str, message: str) -> ProductGateIntegrityError:
    return ProductGateIntegrityError(
        f"detail gate {slug!r} release package manifest {message}"
    )


def _load_manifest(slug: str, package_dir: Path) -> dict:
    manifest_path = package_dir / "package-manifest.json"
    if not manifest_path.is_file():
        raise _manifest_error(
            slug,
            "is missing; generate the current package at "
            f"{package_dir} before running the release gate",
        )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _manifest_error(
            slug,
            f"must be valid JSON: {type(exc).__name__}: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise _manifest_error(slug, "must contain a JSON object")
    return payload


def _artifact_rows(slug: str, payload: dict, package_dir: Path):
    raw_rows = payload.get("artifacts")
    if not isinstance(raw_rows, list):
        raise _manifest_error(slug, "artifacts must be a list")
    package_root = package_dir.resolve()
    rows = []
    seen = set()
    for index, row in enumerate(raw_rows):
        if not isinstance(row, dict):
            raise _manifest_error(slug, f"artifact[{index}] must be an object")
        relative = row.get("relative_path")
        if not isinstance(relative, str) or not relative:
            raise _manifest_error(
                slug, f"artifact[{index}] relative_path must be non-empty"
            )
        logical = PurePosixPath(relative)
        resolved = (package_dir / relative).resolve()
        if (
            logical.is_absolute()
            or logical.as_posix() in {"", "."}
            or ".." in logical.parts
            or "\\" in relative
            or not resolved.is_relative_to(package_root)
        ):
            raise _manifest_error(slug, f"has unsafe artifact path {relative!r}")
        normalized = logical.as_posix()
        if normalized in seen:
            raise _manifest_error(
                slug, f"has duplicate artifact path {normalized!r}"
            )
        digest = row.get("sha256")
        if not isinstance(digest, str):
            raise _manifest_error(
                slug, f"artifact {normalized!r} sha256 must be a string"
            )
        rows.append((normalized, resolved, digest))
        seen.add(normalized)
    return tuple(rows)


def _verify_artifact_closure(slug: str, payload: dict, package_dir: Path) -> None:
    rows = _artifact_rows(slug, payload, package_dir)
    declared = {relative for relative, _path, _digest in rows}
    actual = {
        path.relative_to(package_dir).as_posix()
        for path in package_dir.rglob("*")
        if path.is_file() and path != package_dir / "package-manifest.json"
    }
    missing = sorted(declared - actual)
    undeclared = sorted(actual - declared)
    if missing or undeclared:
        raise _manifest_error(
            slug,
            "artifact closure failed: "
            f"missing={missing}; undeclared={undeclared}",
        )
    for relative, path, expected in rows:
        actual_digest = sha256(path.read_bytes()).hexdigest()
        if actual_digest != expected:
            raise _manifest_error(
                slug,
                f"artifact hash mismatch for {relative!r}: "
                f"manifest={expected!r}, current={actual_digest!r}",
            )


def verify_release_integrity(
    slug: str,
    spec_path: str | Path,
    package_dir: str | Path,
) -> None:
    """Require a closed, current package for a named product release gate."""
    spec_path = Path(spec_path).resolve()
    package_dir = Path(package_dir).resolve()
    evidence = verify_inner_integrity(slug, spec_path)
    payload = _load_manifest(slug, package_dir)

    if payload.get("schema") != "detailgen/package-manifest/v1":
        raise _manifest_error(
            slug,
            "schema must be 'detailgen/package-manifest/v1', observed "
            f"{payload.get('schema')!r}",
        )
    release = payload.get("release")
    if release not in {"preview", "delivery"}:
        raise _manifest_error(
            slug, f"release must be 'preview' or 'delivery', observed {release!r}"
        )
    if payload.get("spec") != evidence.spec_path.name:
        raise _manifest_error(
            slug,
            f"spec identity is stale: manifest={payload.get('spec')!r}, "
            f"current={evidence.spec_path.name!r}",
        )

    validation = payload.get("validation")
    if not isinstance(validation, dict):
        raise _manifest_error(slug, "validation must be an object")
    if validation.get("ok") is not True:
        raise _manifest_error(
            slug, f"validation.ok must be true, observed {validation.get('ok')!r}"
        )
    blocking_count = validation.get("blocking_count")
    if (
        not isinstance(blocking_count, int)
        or isinstance(blocking_count, bool)
        or blocking_count != 0
    ):
        raise _manifest_error(
            slug, f"validation.blocking_count must be 0, observed {blocking_count!r}"
        )

    current_fields = {
        "assembly_hash": evidence.assembly_hash,
        "selection_fingerprint": evidence.selection_fingerprint,
        "model_fingerprint": evidence.model_fingerprint,
    }
    for field, current in current_fields.items():
        if payload.get(field) != current:
            raise _manifest_error(
                slug,
                f"{field} is stale: manifest={payload.get(field)!r}, "
                f"current={current!r}",
            )

    try:
        if release == "delivery":
            evidence.detail.require_delivery_ready()
        else:
            approval = getattr(evidence.detail, "require_modeling_approval", None)
            if approval is not None:
                approval()
    except Exception as exc:
        raise _manifest_error(
            slug,
            f"{release} lifecycle gate failed: {type(exc).__name__}: {exc}",
        ) from exc

    _verify_artifact_closure(slug, payload, package_dir)
