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


def test_instruction_manual_has_nine_readable_progressive_panels():
    from detailgen.rendering.instruction_panels import build_instruction_manual
    from detailgen.rendering.instruction_render import (
        panel_callout_ids,
        panel_fastener_ids,
    )
    from detailgen.spec.compiler import compile_spec_file

    detail = compile_spec_file(SPEC)
    detail.validate()
    manual = build_instruction_manual(detail)
    fastening_panels = tuple(
        panel for panel in manual.panels if panel.action == "fasten"
    )
    readability = (
        len(manual.panels),
        max(len(panel.connections) for panel in fastening_panels),
    )

    assert readability[0] == 9 and readability[1] <= 3, readability
    for panel in manual.panels:
        callout_ids = set(panel_callout_ids(detail, panel))
        fastener_ids = set(panel_fastener_ids(detail, panel))
        assert fastener_ids.isdisjoint(callout_ids)
        assert len(callout_ids) <= 4
