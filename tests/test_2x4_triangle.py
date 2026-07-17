from pathlib import Path

import pytest

from detailgen.components import Lumber
from detailgen.spec import compile_spec_file


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "details" / "2x4_triangle.spec.yaml"


@pytest.fixture(scope="module")
def triangle():
    detail = compile_spec_file(SPEC)
    detail.build()
    return detail


@pytest.mark.detail_gate(
    "2x4_triangle",
    contracts=("compile", "geometry", "validation", "fabrication", "bom", "governance", "intent", "determinism"),
)
def test_triangle_has_three_equal_mitered_2x4_members(triangle):
    members = [triangle._by_id[name].component for name in ("base", "right_side", "left_side")]
    assert all(isinstance(member, Lumber) for member in members)
    assert {member.nominal for member in members} == {"2x4"}
    assert {member.length_semantics for member in members} == {"long_point_to_long_point"}
    assert {round(member.length / 25.4, 6) for member in members} == {48.0}
    for member in members:
        steps = [step for step in member.fabrication_record("member").steps if step.kind == "miter_crosscut"]
        assert [step.param("miter_angle_degrees") for step in steps] == [30.0, 30.0]
        assert member.datum("cut_near") is not None
        assert member.datum("cut_far") is not None


@pytest.mark.detail_gate("2x4_triangle", contracts=("connections",))
def test_triangle_has_three_glued_joints_and_no_installation(triangle):
    connections = triangle.connections()
    assert len(connections) == 3
    assert {connection.kind.label for connection in connections} == {"glued"}
    text = SPEC.read_text(encoding="utf-8")
    assert "uninstalled" in text
    assert "foundations:" not in text


@pytest.mark.detail_gate("2x4_triangle", contracts=("documents",), cadence="release")
def test_triangle_package_contains_required_acceptance_artifacts():
    package = ROOT / "build" / "2x4_triangle"
    required = (
        "package-manifest.json", "assembly.html", "fabrication.html",
        "technical.html", "bom.csv", "cuts.csv", "model/detail.glb",
        "model/2x4_equilateral_triangle.step", "views/top.png", "views/iso.png",
    )
    assert all((package / relative).is_file() for relative in required)
