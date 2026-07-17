from pathlib import Path

import pytest

from detailgen.components import Lumber
from detailgen.rendering.instruction_panels import build_instruction_manual
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
    placed = [triangle._by_id[name] for name in ("base", "right_side", "left_side")]
    members = [part.component for part in placed]
    assert all(isinstance(member, Lumber) for member in members)
    assert {member.nominal for member in members} == {"2x4"}
    assert {member.length_semantics for member in members} == {"long_point_to_long_point"}
    assert {round(member.length / 25.4, 6) for member in members} == {48.0}
    for member in members:
        steps = [step for step in member.fabrication_record("member").steps if step.kind == "miter_crosscut"]
        assert [step.param("miter_angle_degrees") for step in steps] == [60.0, 60.0]
        assert member.datum("cut_near") is not None
        assert member.datum("cut_far") is not None

    for first, second in ((placed[0], placed[1]), (placed[1], placed[2]), (placed[2], placed[0])):
        assert first.world_solid().val().intersect(second.world_solid().val()).Volume() == pytest.approx(0.0, abs=1e-6)
    assert placed[0].datum_world("cut_far").origin == pytest.approx(placed[1].datum_world("cut_near").origin)
    assert placed[1].datum_world("cut_far").origin == pytest.approx(placed[2].datum_world("cut_near").origin)
    assert placed[2].datum_world("cut_far").origin == pytest.approx(placed[0].datum_world("cut_near").origin)


@pytest.mark.detail_gate("2x4_triangle", contracts=("connections",))
def test_triangle_has_three_glued_joints_and_no_installation(triangle):
    connections = triangle.connections()
    assert len(connections) == 3
    assert {connection.kind.label for connection in connections} == {"glued"}
    text = SPEC.read_text(encoding="utf-8")
    assert "uninstalled" in text
    assert "foundations:" not in text


@pytest.mark.detail_gate(
    "2x4_triangle", contracts=("documents",), cadence="release"
)
def test_triangle_manual_join_panel_has_no_foreign_context_claims(triangle):
    triangle.validate()
    manual = build_instruction_manual(triangle)
    join = next(panel for panel in manual.panels if panel.action == "join")
    rendered = " ".join((join.title, *join.instructions, *join.honesty)).lower()

    assert join.title == "Complete 2x4 equilateral triangle bench assembly"
    assert join.instructions == (
        "Complete the 2x4 equilateral triangle as one bench assembly.",
    )
    assert join.honesty == ()
    assert "sofa" not in rendered
    assert "hot-drink" not in rendered


@pytest.mark.detail_gate("2x4_triangle", contracts=("documents",), cadence="release")
def test_triangle_package_contains_required_acceptance_artifacts():
    package = ROOT / "build" / "2x4_triangle"
    required = (
        "package-manifest.json", "assembly.html", "fabrication.html",
        "technical.html", "bom.csv", "cuts.csv", "model/detail.glb",
        "model/2x4_equilateral_triangle.step", "views/top.png", "views/iso.png",
    )
    assert all((package / relative).is_file() for relative in required)
