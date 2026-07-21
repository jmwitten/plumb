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
    expected_cohorts = (
        (
            "fasten",
            ("bottom -> near long wall", "bottom -> far long wall"),
        ),
        (
            "fasten",
            (
                "bottom -> left raised end",
                "near wall -> left raised end",
                "far wall -> left raised end",
            ),
        ),
        (
            "fasten",
            (
                "bottom -> right raised end",
                "near wall -> right raised end",
                "far wall -> right raised end",
            ),
        ),
        (
            "fasten",
            (
                "bottom -> center divider",
                "near wall -> center divider",
                "far wall -> center divider",
            ),
        ),
        ("prepare", ()),
        (
            "bond",
            (
                "left raised end -> handle adhesive bond",
                "right raised end -> handle adhesive bond",
            ),
        ),
        ("cure", ()),
        (
            "fasten",
            (
                "left raised end -> handle end",
                "right raised end -> handle end",
            ),
        ),
        ("join", ()),
    )
    fastening_panels = tuple(
        panel for panel in manual.panels if panel.action == "fasten"
    )
    readability = (
        len(manual.panels),
        max(len(panel.connections) for panel in fastening_panels),
    )

    assert readability[0] == 9 and readability[1] <= 3, readability
    assert tuple(
        (panel.action, panel.connections) for panel in manual.panels
    ) == expected_cohorts

    installs = detail.resolved_installations
    assert len(installs) == 13
    assert sum(len(install.fasteners) for install in installs) == 27
    assert all(
        install.contract.head == "flush_countersunk" for install in installs
    )
    assert all(
        install.provenance_map["head"] == "authored_override"
        for install in installs
    )
    assert all(
        "seat each head flush in its countersink" in instruction
        for panel in fastening_panels
        for instruction in panel.instructions
    )

    graph = detail.construction_event_graph
    glue_connections = (
        "left raised end -> handle adhesive bond",
        "right raised end -> handle adhesive bond",
    )
    screw_connections = (
        "left raised end -> handle end",
        "right raised end -> handle end",
    )
    cure_screw_prerequisites = {
        (glue, screw)
        for glue in glue_connections
        for screw in screw_connections
        if graph.precedes(
            next(event for event in graph.processes_of[glue]
                 if event.group == "cure"),
            graph.drives_of[screw][0],
        )
    }
    assert cure_screw_prerequisites == {
        (glue, screw)
        for glue in glue_connections
        for screw in screw_connections
    }

    for panel in manual.panels:
        callout_ids = set(panel_callout_ids(detail, panel))
        fastener_ids = set(panel_fastener_ids(detail, panel))
        assert fastener_ids.isdisjoint(callout_ids)
        assert len(callout_ids) <= 4


def test_single_handle_fasteners_use_singular_action_grammar():
    from detailgen.rendering.instruction_panels import build_instruction_manual
    from detailgen.spec.compiler import compile_spec_file

    detail = compile_spec_file(SPEC)
    detail.validate()
    manual = build_instruction_manual(detail)
    handle_instructions = tuple(
        instruction
        for panel in manual.panels
        if panel.connections == (
            "left raised end -> handle end",
            "right raised end -> handle end",
        )
        for instruction in panel.instructions
    )

    assert len(handle_instructions) == 2
    assert all("drive 1 screw through" in text for text in handle_instructions)
    assert all("drive 1 screws" not in text for text in handle_instructions)
