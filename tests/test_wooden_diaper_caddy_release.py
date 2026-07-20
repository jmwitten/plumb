"""Release-document contract for the wooden diaper caddy package."""

from pathlib import Path

import pytest

from detailgen.package import PackageRequest
from detailgen.package.builder import build_package


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "details" / "wooden_diaper_caddy.spec.yaml"

pytestmark = pytest.mark.detail_gate(
    "wooden_diaper_caddy",
    contracts=("documents",),
    cadence="release",
)


def test_release_package_contains_complete_model_backed_reader_artifacts(tmp_path):
    out = tmp_path / "wooden_diaper_caddy"

    result = build_package(
        PackageRequest(SPEC, out, views=("iso", "front", "right", "top"))
    )

    assert result.validation_ok is True
    assert {
        "assembly.html",
        "bom.csv",
        "cuts.csv",
        "fabrication.html",
        "model/detail.glb",
        "model/wooden_diaper_caddy.step",
        "model/validation_report.md",
        "package-manifest.json",
        "review-manifest.json",
        "technical.html",
        "views/front.png",
        "views/iso.png",
        "views/right.png",
        "views/top.png",
    } <= {
        path.relative_to(out).as_posix()
        for path in out.rglob("*")
        if path.is_file()
    }

