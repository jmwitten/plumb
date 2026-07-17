from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

import pytest

import product_gate_integrity as integrity


@dataclass(frozen=True)
class _Finding:
    check: str
    subject: str
    verdict: str = "FAIL"
    detail: str = "faces do not meet"


class _Report:
    def __init__(self, *, ok=True, blocking=()):
        self.ok = ok
        self.blocking = list(blocking)


class _Detail:
    def __init__(self, report):
        self._report = report
        self.assembly = object()
        self.design_governance = None

    def validate(self):
        return self._report


class _ReleaseDetail(_Detail):
    def __init__(self):
        super().__init__(_Report())
        self.modeling_approval_calls = 0
        self.delivery_ready_calls = 0

    def require_modeling_approval(self):
        self.modeling_approval_calls += 1

    def require_delivery_ready(self):
        self.delivery_ready_calls += 1


def _write_contract(path: Path, source: str) -> None:
    path.write_text(
        "schema_version: 1\n"
        "subject:\n"
        "  kind: standalone_detail\n"
        f"  source: {source}\n",
        encoding="utf-8",
    )


def test_certification_subject_precedes_filename_fallback(tmp_path):
    details = tmp_path / "details"
    details.mkdir()
    fallback = details / "garden_shelf.spec.yaml"
    fallback.write_text("name: fallback\n", encoding="utf-8")
    selected = details / "selected_subject.spec.yaml"
    selected.write_text("name: selected\n", encoding="utf-8")
    _write_contract(details / "garden_shelf.cert.yaml", selected.name)

    resolved = integrity.resolve_product_subject(
        "garden_shelf", details, tmp_path
    )

    assert resolved == selected.resolve()


def test_hyphenated_owner_resolves_normalized_standalone_spec(tmp_path):
    details = tmp_path / "details"
    details.mkdir()
    spec = details / "garden_shelf.spec.yaml"
    spec.write_text("name: shelf\n", encoding="utf-8")

    resolved = integrity.resolve_product_subject(
        "garden-shelf", details, tmp_path
    )

    assert resolved == spec.resolve()


def test_legacy_alias_without_canonical_subject_remains_unbound(tmp_path):
    details = tmp_path / "details"
    details.mkdir()
    (details / "platform.spec.yaml").write_text(
        "name: platform\n", encoding="utf-8"
    )

    assert (
        integrity.resolve_product_subject("zipline-platform", details, tmp_path)
        is None
    )


def test_inner_integrity_returns_current_model_evidence(monkeypatch, tmp_path):
    spec = tmp_path / "product.spec.yaml"
    spec.write_text("name: product\n", encoding="utf-8")
    detail = _Detail(_Report())
    monkeypatch.setattr(integrity, "compile_spec_file", lambda path: detail)
    monkeypatch.setattr(
        integrity,
        "build_manifest",
        lambda assembly: {"assembly_hash": "a" * 64},
    )

    evidence = integrity.verify_inner_integrity("product", spec)

    assert evidence.detail is detail
    assert evidence.spec_path == spec.resolve()
    assert evidence.assembly_hash == "a" * 64
    assert evidence.selection_fingerprint is None
    assert evidence.model_fingerprint is None


@pytest.mark.parametrize(
    "report",
    (
        _Report(ok=False),
        _Report(
            ok=True,
            blocking=(_Finding("interference", "left joint"),),
        ),
    ),
)
def test_inner_integrity_rejects_any_blocking_validation(
    monkeypatch, tmp_path, report
):
    spec = tmp_path / "product.spec.yaml"
    spec.write_text("name: product\n", encoding="utf-8")
    monkeypatch.setattr(
        integrity,
        "compile_spec_file",
        lambda path: _Detail(report),
    )

    with pytest.raises(
        integrity.ProductGateIntegrityError,
        match=r"product.*product\.spec\.yaml.*validation",
    ) as caught:
        integrity.verify_inner_integrity("product", spec)

    if report.blocking:
        assert "interference" in str(caught.value)
        assert "left joint" in str(caught.value)


def test_inner_integrity_reports_compile_failure_with_gate_context(
    monkeypatch, tmp_path
):
    spec = tmp_path / "product.spec.yaml"
    spec.write_text("name: product\n", encoding="utf-8")

    def fail(_path):
        raise ValueError("bad placement")

    monkeypatch.setattr(integrity, "compile_spec_file", fail)

    with pytest.raises(
        integrity.ProductGateIntegrityError,
        match=r"product.*product\.spec\.yaml.*bad placement",
    ):
        integrity.verify_inner_integrity("product", spec)


def _release_evidence(spec: Path, detail: _ReleaseDetail):
    return integrity.CurrentProductEvidence(
        detail=detail,
        spec_path=spec.resolve(),
        assembly_hash="a" * 64,
        selection_fingerprint="selection-current",
        model_fingerprint="model-current",
    )


def _write_package(
    package: Path,
    spec: Path,
    *,
    release: str = "preview",
    manifest_updates: dict | None = None,
) -> dict:
    package.mkdir()
    artifact = package / "technical.html"
    artifact.write_text("current technical package", encoding="utf-8")
    payload = {
        "schema": "detailgen/package-manifest/v1",
        "spec": spec.name,
        "release": release,
        "assembly_hash": "a" * 64,
        "selection_fingerprint": "selection-current",
        "model_fingerprint": "model-current",
        "validation": {"ok": True, "blocking_count": 0},
        "holds": [],
        "tests": {
            "status": "not-run",
            "reason": "package generation does not execute tests",
        },
        "timings_seconds": {},
        "artifacts": [
            {
                "kind": "technical",
                "relative_path": "technical.html",
                "sha256": sha256(artifact.read_bytes()).hexdigest(),
                "media_type": "text/html",
                "source": "compiled-detail",
            }
        ],
    }
    if manifest_updates:
        payload.update(manifest_updates)
    (package / "package-manifest.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return payload


@pytest.mark.parametrize(
    ("release", "expected_modeling", "expected_delivery"),
    (("preview", 1, 0), ("delivery", 0, 1)),
)
def test_release_integrity_accepts_current_closed_package_and_lifecycle(
    monkeypatch,
    tmp_path,
    release,
    expected_modeling,
    expected_delivery,
):
    spec = tmp_path / "product.spec.yaml"
    spec.write_text("name: product\n", encoding="utf-8")
    package = tmp_path / "package"
    _write_package(package, spec, release=release)
    detail = _ReleaseDetail()
    monkeypatch.setattr(
        integrity,
        "verify_inner_integrity",
        lambda slug, path: _release_evidence(spec, detail),
    )

    integrity.verify_release_integrity("product", spec, package)

    assert detail.modeling_approval_calls == expected_modeling
    assert detail.delivery_ready_calls == expected_delivery


@pytest.mark.parametrize(
    ("updates", "message"),
    (
        ({"schema": "detailgen/package-manifest/v0"}, "schema"),
        ({"release": "draft"}, "release"),
        ({"spec": "stale.spec.yaml"}, "spec"),
        ({"assembly_hash": "b" * 64}, "assembly_hash"),
        ({"selection_fingerprint": "stale"}, "selection_fingerprint"),
        ({"model_fingerprint": "stale"}, "model_fingerprint"),
        ({"validation": {"ok": False, "blocking_count": 0}}, "validation.ok"),
        ({"validation": {"ok": True, "blocking_count": 1}}, "blocking_count"),
    ),
)
def test_release_integrity_rejects_stale_or_blocked_manifest(
    monkeypatch, tmp_path, updates, message
):
    spec = tmp_path / "product.spec.yaml"
    spec.write_text("name: product\n", encoding="utf-8")
    package = tmp_path / "package"
    _write_package(package, spec, manifest_updates=updates)
    detail = _ReleaseDetail()
    monkeypatch.setattr(
        integrity,
        "verify_inner_integrity",
        lambda slug, path: _release_evidence(spec, detail),
    )

    with pytest.raises(integrity.ProductGateIntegrityError, match=message):
        integrity.verify_release_integrity("product", spec, package)


def test_release_integrity_requires_manifest_and_valid_json(monkeypatch, tmp_path):
    spec = tmp_path / "product.spec.yaml"
    spec.write_text("name: product\n", encoding="utf-8")
    package = tmp_path / "package"
    package.mkdir()
    detail = _ReleaseDetail()
    monkeypatch.setattr(
        integrity,
        "verify_inner_integrity",
        lambda slug, path: _release_evidence(spec, detail),
    )

    with pytest.raises(integrity.ProductGateIntegrityError, match="generate.*package"):
        integrity.verify_release_integrity("product", spec, package)

    (package / "package-manifest.json").write_text("{", encoding="utf-8")
    with pytest.raises(integrity.ProductGateIntegrityError, match="valid JSON"):
        integrity.verify_release_integrity("product", spec, package)


@pytest.mark.parametrize("defect", ("extra", "missing", "bad-hash"))
def test_release_integrity_rejects_artifact_closure_or_digest_defect(
    monkeypatch, tmp_path, defect
):
    spec = tmp_path / "product.spec.yaml"
    spec.write_text("name: product\n", encoding="utf-8")
    package = tmp_path / "package"
    payload = _write_package(package, spec)
    if defect == "extra":
        (package / "stale.txt").write_text("stale", encoding="utf-8")
    elif defect == "missing":
        (package / "technical.html").unlink()
    else:
        payload["artifacts"][0]["sha256"] = "0" * 64
        (package / "package-manifest.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
    detail = _ReleaseDetail()
    monkeypatch.setattr(
        integrity,
        "verify_inner_integrity",
        lambda slug, path: _release_evidence(spec, detail),
    )

    with pytest.raises(
        integrity.ProductGateIntegrityError,
        match="artifact (closure|hash)",
    ):
        integrity.verify_release_integrity("product", spec, package)


@pytest.mark.parametrize("unsafe_path", ("../escape.txt", "/tmp/escape.txt"))
def test_release_integrity_rejects_unsafe_artifact_path(
    monkeypatch, tmp_path, unsafe_path
):
    spec = tmp_path / "product.spec.yaml"
    spec.write_text("name: product\n", encoding="utf-8")
    package = tmp_path / "package"
    payload = _write_package(package, spec)
    payload["artifacts"][0]["relative_path"] = unsafe_path
    (package / "package-manifest.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    detail = _ReleaseDetail()
    monkeypatch.setattr(
        integrity,
        "verify_inner_integrity",
        lambda slug, path: _release_evidence(spec, detail),
    )

    with pytest.raises(integrity.ProductGateIntegrityError, match="unsafe artifact"):
        integrity.verify_release_integrity("product", spec, package)


def test_release_integrity_rejects_duplicate_artifact_path(monkeypatch, tmp_path):
    spec = tmp_path / "product.spec.yaml"
    spec.write_text("name: product\n", encoding="utf-8")
    package = tmp_path / "package"
    payload = _write_package(package, spec)
    payload["artifacts"].append(dict(payload["artifacts"][0]))
    (package / "package-manifest.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    detail = _ReleaseDetail()
    monkeypatch.setattr(
        integrity,
        "verify_inner_integrity",
        lambda slug, path: _release_evidence(spec, detail),
    )

    with pytest.raises(integrity.ProductGateIntegrityError, match="duplicate artifact"):
        integrity.verify_release_integrity("product", spec, package)
