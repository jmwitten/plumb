from __future__ import annotations

from dataclasses import dataclass
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
