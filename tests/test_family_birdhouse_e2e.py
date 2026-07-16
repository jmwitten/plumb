"""End-to-end contract for the governed family cedar birdhouse."""

from pathlib import Path

import pytest

from detailgen.components import CedarPanel, ExteriorWoodScrew
from detailgen.core.process_graph import verify_assembly_fabrication
from detailgen.core.units import IN
from detailgen.spec import compile_spec_file


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "details/family_birdhouse.spec.yaml"


@pytest.fixture(scope="module")
def birdhouse():
    detail = compile_spec_file(SPEC)
    report = detail.validate()
    return detail, report


def _bbox(detail, part_id):
    return detail._by_id[part_id].world_solid().val().BoundingBox()


def _feature_steps(detail, part_id):
    record = detail._by_id[part_id].component.fabrication_record(part_id)
    return [step for step in record.steps if step.kind == "bore"]


def test_model_has_six_primary_cedar_parts_plus_the_mounting_cleat(birdhouse):
    detail, _report = birdhouse
    cedar = [p for p in detail.assembly.parts if isinstance(p.component, CedarPanel)]

    assert {p.name for p in cedar} == {
        "entrance front",
        "extended back",
        "fixed side",
        "pivoting cleanout side",
        "recessed floor",
        "sloped oversized roof",
        "pole mounting cleat",
    }
    assert len(cedar) == 7
    assert all(p.component.material_key == "cedar" for p in cedar)
    assert all("untreated" in p.component.assumptions().lower() for p in cedar)
    assert not any("perch" in p.name.lower() for p in detail.assembly.parts)


def test_entrance_vents_and_drains_are_distinct_fabrication_operations(birdhouse):
    detail, _report = birdhouse
    entrance = _feature_steps(detail, "front")
    fixed_vents = _feature_steps(detail, "side_fixed")
    cleanout_vents = _feature_steps(detail, "side_cleanout")
    drains = _feature_steps(detail, "floor")

    assert len(entrance) == 1
    assert entrance[0].param("radius") == pytest.approx(9 / 16 * IN)
    assert entrance[0].param("feature") == "1 1/8 inch entrance"
    assert len(fixed_vents) == len(cleanout_vents) == 2
    assert len(drains) == 4
    assert {s.provenance for s in drains} == {
        "drain_front_left",
        "drain_front_right",
        "drain_rear_left",
        "drain_rear_right",
    }
    assert sum(
        len(_feature_steps(detail, pid))
        for pid in ("front", "side_fixed", "side_cleanout", "floor")
    ) == 9


def test_compiled_geometry_preserves_cavity_floor_back_and_roof_contract(birdhouse):
    detail, _report = birdhouse
    floor = _bbox(detail, "floor")
    front = _bbox(detail, "front")
    back = _bbox(detail, "back")
    fixed = _bbox(detail, "side_fixed")
    cleanout = _bbox(detail, "side_cleanout")
    roof = _bbox(detail, "roof")

    assert (floor.xmin, floor.xmax, floor.ymin, floor.ymax) == pytest.approx(
        (0.75 * IN, 4.75 * IN, 0.75 * IN, 4.75 * IN), abs=0.02 * IN
    )
    assert (floor.zmin, floor.zmax) == pytest.approx(
        (0.25 * IN, 1.0 * IN), abs=0.02 * IN
    )
    assert (front.xlen, front.zlen) == pytest.approx((5.5 * IN, 8 * IN))
    assert (back.xlen, back.zlen) == pytest.approx((5.5 * IN, 11 * IN))
    assert back.zmin == pytest.approx(-2.5 * IN)
    assert back.zmax == pytest.approx(8.5 * IN)
    assert (fixed.ylen, fixed.zlen) == pytest.approx((4 * IN, 8 * IN))
    assert (cleanout.ylen, cleanout.zlen) == pytest.approx((4 * IN, 8 * IN))
    assert roof.xmin < front.xmin and roof.xmax > front.xmax
    assert roof.ymin < front.ymin and roof.ymax > back.ymax
    assert roof.zlen > 0.75 * IN
    roof_normal = detail._by_id["roof"].world_frame.z_axis
    assert abs(roof_normal[1]) > 0.05
    assert roof_normal[2] > 0.99


def test_cleanout_panel_is_pivoted_and_latched_never_fixed(birdhouse):
    detail, _report = birdhouse
    connections = detail.connections()
    service = [
        conn for conn in connections
        if conn.kind.label in {"pivot_screwed", "service_latch_screwed"}
    ]
    assert [conn.kind.label for conn in service].count("pivot_screwed") == 2
    assert [conn.kind.label for conn in service].count("service_latch_screwed") == 1
    assert all(conn.parts[1].id == detail._by_id["side_cleanout"].id for conn in service)

    fixed_connections = [
        conn for conn in connections
        if conn.kind.label in {"butt_screwed", "cleat_screwed"}
    ]
    assert all(
        detail._by_id["side_cleanout"] not in conn.parts
        for conn in fixed_connections
    )
    edges = detail._connection_checks.edges
    assert len([edge for edge in edges if edge.kind == "pivoted_by"]) == 2
    assert len([edge for edge in edges if edge.kind == "latched_by"]) == 1
    assert not any(
        edge.kind == "fastened_by"
        and detail._by_id["side_cleanout"].id in {edge.a, edge.b}
        for edge in edges
    )


def test_connections_use_only_ordinary_exterior_screws_and_fabrication_folds(birdhouse):
    detail, report = birdhouse
    screws = [
        p for p in detail.assembly.parts
        if isinstance(p.component, ExteriorWoodScrew)
    ]

    assert len(screws) == 21
    assert not any(type(p.component).__name__ == "StructuralScrew" for p in screws)
    assert all(p.component.material_key == "steel_galv" for p in screws)
    verify_assembly_fabrication(detail.assembly)
    assert report.ok, [str(finding) for finding in report.blocking]


def test_bom_and_spec_text_keep_family_tasks_and_installation_holds_explicit(birdhouse):
    detail, _report = birdhouse
    text = SPEC.read_text()
    bom = detail.bom_table()

    assert any(row["item"] == "3/4 in cedar panel" for row in bom)
    assert any(row["item"] == "Exterior wood screw" for row in bom)
    for phrase in (
        "ADULT-ONLY",
        "CHILD-SUITABLE",
        "no exterior perch",
        "rough interior",
        "FIELD HOLD — pole",
        "predator baffle",
        "soil",
        "utilities",
        "coating",
        "capacity NOT analyzed",
    ):
        assert phrase in text
