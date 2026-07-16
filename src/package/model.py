"""Immutable request and result types for generic package generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class PackageRequest:
    spec_path: Path
    output_dir: Path
    release: str = "preview"
    views: tuple[str, ...] = ("iso", "front", "right", "top")
    tests_status: str = "not-run"
    tests_reason: str = "package generation does not execute tests"

    def __post_init__(self) -> None:
        if self.release not in {"preview", "delivery"}:
            raise ValueError("release must be preview or delivery")
        if self.tests_status not in {"not-run", "skipped", "passed", "failed"}:
            raise ValueError(
                "tests_status must be not-run, skipped, passed, or failed"
            )
        if self.tests_status == "skipped" and not self.tests_reason.strip():
            raise ValueError("skipped tests require a reason")


@dataclass(frozen=True)
class PackageArtifact:
    kind: str
    relative_path: str
    sha256: str
    media_type: str
    source: str


@dataclass(frozen=True)
class PackageResult:
    request: PackageRequest
    assembly_hash: str
    selection_fingerprint: str | None
    model_fingerprint: str | None
    validation_ok: bool
    blocking_count: int
    holds: tuple[str, ...]
    artifacts: tuple[PackageArtifact, ...]
    timings: tuple[tuple[str, float], ...]

    def manifest(self) -> dict[str, object]:
        """Return the deterministic, machine-readable package manifest."""
        artifacts = sorted(self.artifacts, key=lambda row: row.relative_path)
        return {
            "schema": "detailgen/package-manifest/v1",
            "spec": self.request.spec_path.name,
            "release": self.request.release,
            "assembly_hash": self.assembly_hash,
            "selection_fingerprint": self.selection_fingerprint,
            "model_fingerprint": self.model_fingerprint,
            "validation": {
                "ok": self.validation_ok,
                "blocking_count": self.blocking_count,
            },
            "holds": list(self.holds),
            "tests": {
                "status": self.request.tests_status,
                "reason": self.request.tests_reason,
            },
            "timings_seconds": {
                key: value for key, value in sorted(self.timings)
            },
            "artifacts": [asdict(row) for row in artifacts],
        }
