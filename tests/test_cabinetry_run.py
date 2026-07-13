"""Multi-cabinet run composition over the proven single-box compiler."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from detailgen.packs import ProjectSchemaError, compile_project_file, load_project_text
from detailgen.packs.cabinetry import FramelessCabinetryPack

FIXTURE = (
    Path(__file__).parent / "fixtures" / "cabinetry"
    / "frameless_base_cabinet.project.yaml"
)


def _run_raw() -> dict:
    raw = yaml.safe_load(FIXTURE.read_text())
    first = raw["cabinetry"]["cabinets"][0]
    first["conditions"]["right_end"] = "adjacent_cabinet"
    second = yaml.safe_load(yaml.safe_dump(first))
    second["id"] = "B30R"
    second["placement"]["from_left_datum"] = 54
    second["conditions"] = {
        "left_end": "adjacent_cabinet",
        "right_end": "exposed",
    }
    raw["cabinetry"]["cabinets"].append(second)
    raw["site"]["wall"]["studs"].extend([
        {"id": "stud_64", "position": 64, "verified": True},
        {"id": "stud_80", "position": 80, "verified": True},
    ])
    return raw


def _parse(raw: dict):
    doc = load_project_text(yaml.safe_dump(raw, sort_keys=False))
    return FramelessCabinetryPack().parse(doc)


def test_two_touching_cabinets_form_one_ordered_run():
    section = _parse(_run_raw())

    assert [cabinet.cabinet_id for cabinet in section.cabinets] == ["B30", "B30R"]
    assert [cabinet.from_left_datum_mm for cabinet in section.cabinets] == sorted(
        cabinet.from_left_datum_mm for cabinet in section.cabinets
    )


@pytest.mark.parametrize("second_offset", [50, 58])
def test_run_rejects_overlap_and_unresolved_gap(second_offset):
    raw = _run_raw()
    raw["cabinetry"]["cabinets"][1]["placement"]["from_left_datum"] = second_offset

    with pytest.raises(ProjectSchemaError, match="run.*overlap|run.*gap"):
        _parse(raw)


def test_adjacent_conditions_must_agree_on_both_cabinets():
    raw = _run_raw()
    raw["cabinetry"]["cabinets"][1]["conditions"]["left_end"] = "exposed"

    with pytest.raises(ProjectSchemaError, match="adjacent conditions.*B30.*B30R"):
        _parse(raw)


def test_real_two_cabinet_run_compiles_to_one_base_detail(tmp_path):
    path = tmp_path / "run.project.yaml"
    path.write_text(yaml.safe_dump(_run_raw(), sort_keys=False))

    project = compile_project_file(path)
    project.require_release()

    assert project.release_ready
    assert {part.part_id.split(".")[1] for part in project.model.parts
            if part.part_id.startswith("cabinetry.")} == {"B30", "B30R"}
    assert len(project.artifacts.cut_list) == 28
    assert {item.part_id.split(".")[1] for item in project.artifacts.cut_list} == {
        "B30", "B30R"
    }
    assert any(
        step.step_id == "run.join_cabinets"
        for step in project.artifacts.installation_steps
    )
    by_id = {
        step.step_id: step.phase for step in project.artifacts.installation_steps
    }
    assert by_id["B30.install.set_cabinet"] < by_id["run.join_cabinets"]
    assert by_id["B30R.install.set_cabinet"] < by_id["run.join_cabinets"]
    assert by_id["run.join_cabinets"] < by_id["B30.install.wall_anchor"]
    assert by_id["run.join_cabinets"] < by_id["B30R.install.wall_anchor"]

    sequence = project.lowered_doc.sequence.stages
    assert [stage.name for stage in sequence] == [
        "set_neighboring_cases", "join_neighboring_cases", "anchor_run_to_wall"
    ]
    assert sequence[0].parts
    assert sequence[1].parts
    assert sequence[2].parts
    connector_ids = set(sequence[1].parts)
    assert connector_ids <= {part.part_id for part in project.model.parts}
    overlaps = {
        (item.a, item.b) for item in project.lowered_doc.validation.expected_overlaps
    }
    assert all(sum(1 for a, _ in overlaps if a == connector_id) == 2
               for connector_id in connector_ids)
