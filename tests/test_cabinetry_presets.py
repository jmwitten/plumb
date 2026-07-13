"""Versioned archetype expansion makes common authoring fast but still strict."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from detailgen.packs import ProjectSchemaError, compile_project, load_project_text

ROOT = Path(__file__).parent / "fixtures" / "cabinetry"
DETAILS = Path(__file__).parents[1] / "details"
BASE = ROOT / "frameless_base_cabinet.project.yaml"
VANITY = ROOT / "floating_vanity.project.yaml"


def _compile(raw: dict):
    return compile_project(load_project_text(yaml.safe_dump(raw, sort_keys=False)))


def _compact_base() -> dict:
    raw = yaml.safe_load(BASE.read_text())
    full = raw["cabinetry"]["cabinets"][0]
    raw["cabinetry"]["cabinets"] = [{
        "archetype": "base_two_door_30@1",
        "id": full["id"],
        "placement": full["placement"],
        "conditions": full["conditions"],
        "overrides": {
            "design_load_psf": full["interior"]["design_load_psf"],
        },
    }]
    return raw


def _compact_vanity() -> dict:
    raw = yaml.safe_load(VANITY.read_text())
    full = raw["vanity"]["cabinet"]
    raw["vanity"]["archetype"] = "floating_vanity_two_door@1"
    raw["vanity"]["overrides"] = {
        "height": full["height"],
        "depth": full["depth"],
    }
    raw["vanity"]["cabinet"] = {
        "id": full["id"],
        "width": full["width"],
        "bottom_elevation": full["bottom_elevation"],
        "placement": full["placement"],
    }
    return raw


def test_named_b30_preset_lowers_identically_to_full_authoring():
    full = _compile(yaml.safe_load(BASE.read_text()))
    compact = _compile(_compact_base())

    assert compact.lowered_doc == full.lowered_doc
    assert compact.report.findings == full.report.findings
    assert compact.manifest()["archetypes"] == ["base_two_door_30@1"]
    expanded = compact.manifest()["expanded_project"]
    assert expanded["cabinetry"]["cabinets"][0]["type"] == "base"
    assert "archetype" not in expanded["cabinetry"]["cabinets"][0]
    assert "overrides" not in expanded["cabinetry"]["cabinets"][0]
    replay = _compile(expanded)
    assert replay.lowered_doc == compact.lowered_doc


def test_width_parameterized_base_preset_requires_only_width_plus_project_context():
    raw = _compact_base()
    cabinet = raw["cabinetry"]["cabinets"][0]
    cabinet["archetype"] = "base_two_door@1"
    cabinet["width"] = 30

    project = _compile(raw)

    assert project.model.section.cabinets[0].width_mm == pytest.approx(30 * 25.4)
    assert project.model.section.cabinets[0].source_archetype == "base_two_door@1"


def test_straight_run_preset_derives_touching_placement_and_adjacency():
    raw = yaml.safe_load(BASE.read_text())
    raw["site"]["wall"]["studs"].extend([
        {"id": "stud_64", "position": 64, "verified": True},
        {"id": "stud_80", "position": 80, "verified": True},
    ])
    section = raw["cabinetry"]
    section.pop("cabinets")
    section.update({
        "archetype": "straight_base_run@1",
        "run": {
            "against": "north_wall",
            "origin": 24,
            "left_end": "exposed",
            "right_end": "exposed",
            "cabinets": [
                {"id": "B30", "width": 30},
                {"id": "B30R", "width": 30},
            ],
        },
        "overrides": {"design_load_psf": 15},
    })

    project = _compile(raw)
    cabinets = project.model.section.cabinets

    assert [item.from_left_datum_mm / 25.4 for item in cabinets] == pytest.approx(
        [24, 54]
    )
    assert [(item.left_end, item.right_end) for item in cabinets] == [
        ("exposed", "adjacent_cabinet"),
        ("adjacent_cabinet", "exposed"),
    ]
    assert project.manifest()["archetypes"] == ["straight_base_run@1"]


def test_floating_vanity_preset_lowers_identically_to_full_authoring():
    full = _compile(yaml.safe_load(VANITY.read_text()))
    compact = _compile(_compact_vanity())

    assert compact.lowered_doc == full.lowered_doc
    assert compact.report.findings == full.report.findings
    assert compact.manifest()["archetypes"] == ["floating_vanity_two_door@1"]
    expanded = compact.manifest()["expanded_project"]
    assert expanded["vanity"]["cabinet"]["type"] == "floating"
    assert "archetype" not in expanded["vanity"]
    assert "overrides" not in expanded["vanity"]
    replay = _compile(expanded)
    assert replay.lowered_doc == compact.lowered_doc


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda raw: raw["cabinetry"]["cabinets"][0].update(
            archetype="base_two_dor@1"), "unknown cabinet archetype.*did you mean"),
        (lambda raw: raw["cabinetry"]["cabinets"][0]["overrides"].update(
            design_load_psf_typo=20), "unknown override.*design_load_psf"),
    ],
)
def test_compact_cabinet_authoring_fails_loudly_on_typos(mutation, message):
    raw = _compact_base()
    mutation(raw)

    with pytest.raises(ProjectSchemaError, match=message):
        _compile(raw)


def test_vanity_preset_does_not_default_wall_loads_plumbing_or_engineering():
    raw = _compact_vanity()
    raw["vanity"].pop("mounting")

    with pytest.raises(ProjectSchemaError, match="mounting"):
        _compile(raw)


@pytest.mark.parametrize(
    "name",
    [
        "frameless_base_run.compact.project.yaml",
        "floating_vanity.compact.project.yaml",
    ],
)
def test_checked_in_compact_examples_compile(name):
    from detailgen.packs import compile_project_file

    project = compile_project_file(DETAILS / name)

    assert project.manifest()["archetypes"]
