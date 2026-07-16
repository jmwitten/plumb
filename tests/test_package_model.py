from pathlib import Path

import pytest

from detailgen.package import PackageArtifact, PackageRequest, PackageResult


def test_package_request_rejects_unknown_release_state(tmp_path):
    with pytest.raises(ValueError, match="release must be preview or delivery"):
        PackageRequest(Path("x.spec.yaml"), tmp_path, release="draft")


def test_package_request_requires_reason_when_tests_are_skipped(tmp_path):
    with pytest.raises(ValueError, match="skipped tests require a reason"):
        PackageRequest(
            Path("x.spec.yaml"),
            tmp_path,
            tests_status="skipped",
            tests_reason="  ",
        )


def test_manifest_keeps_skipped_distinct_and_orders_artifacts(tmp_path):
    request = PackageRequest(
        Path("x.spec.yaml"),
        tmp_path,
        tests_status="skipped",
        tests_reason="owner-request",
    )
    result = PackageResult(
        request=request,
        assembly_hash="a" * 64,
        selection_fingerprint=None,
        model_fingerprint=None,
        validation_ok=True,
        blocking_count=0,
        holds=("Structural capacity — UNKNOWN — NOT ANALYZED",),
        artifacts=(
            PackageArtifact(
                "manual",
                "z-manual.html",
                "c" * 64,
                "text/html",
                "compiled-detail",
            ),
            PackageArtifact(
                "technical",
                "technical.html",
                "b" * 64,
                "text/html",
                "compiled-detail",
            ),
        ),
        timings=(("compile_validate", 0.25),),
    )

    payload = result.manifest()

    assert payload["tests"] == {
        "status": "skipped",
        "reason": "owner-request",
    }
    assert [row["relative_path"] for row in payload["artifacts"]] == [
        "technical.html",
        "z-manual.html",
    ]
