"""Strict authoring contract for the bounded three-drawer base archetype."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from detailgen.core.units import IN
from detailgen.packs import ProjectSchemaError, load_project_text
from detailgen.packs.cabinetry import FramelessCabinetryPack
from detailgen.packs.cabinetry.presets import expand_cabinetry_project


BASE = Path(__file__).parent / "fixtures/cabinetry/frameless_base_cabinet.project.yaml"


def compact_db40() -> dict:
    raw = yaml.safe_load(BASE.read_text())
    raw["name"] = "DB40 three-drawer clothing cabinet"
    raw["cabinetry"]["cabinets"] = [{
        "archetype": "drawer_base_three@1",
        "id": "DB40",
        "width": 40,
        "placement": {
            "against": "north_wall",
            "from_left_datum": 24,
        },
        "conditions": {"left_end": "exposed", "right_end": "exposed"},
    }]
    return raw


def _doc(raw: dict):
    return load_project_text(yaml.safe_dump(raw, sort_keys=False))


def test_compact_db40_expands_to_strict_progressive_clothing_bank():
    section = FramelessCabinetryPack().parse(_doc(compact_db40()))
    cabinet = section.cabinets[0]

    assert cabinet.cabinet_id == "DB40"
    assert cabinet.kind == "drawer_base"
    assert cabinet.width_mm == pytest.approx(40 * IN)
    assert cabinet.source_archetype == "drawer_base_three@1"
    assert cabinet.drawer_bank.sizing_policy_id == "progressive_clothing_3@1"
    assert cabinet.drawer_bank.runner_product_id == "blum_movento_763_5330s@2026.1"
    assert cabinet.drawer_bank.locking_device_product_id == (
        "blum_t51_7601_pair@2026.1"
    )
    assert cabinet.drawer_bank.stabilizer_product_id == "blum_zs7m686mu@2026.1"
    assert cabinet.drawer_bank.pull_product_id == "hafele_vogue_155_01_613@2026.1"
    assert [cell.cell_id for cell in cabinet.drawer_bank.cells] == [
        "top", "middle", "bottom"
    ]
    assert [cell.front_height_mm for cell in cabinet.drawer_bank.cells] == (
        pytest.approx([158.75, 254.0, 354.95])
    )
    assert [cell.box_height_mm for cell in cabinet.drawer_bank.cells] == (
        pytest.approx([101.6, 177.8, 254.0])
    )
    assert [cell.contents_load_lb for cell in cabinet.drawer_bank.cells] == [
        40.0, 40.0, 40.0
    ]


def test_expanded_drawer_record_is_strict_and_replayable():
    expanded, source = expand_cabinetry_project(_doc(compact_db40()))
    raw = expanded.sections["cabinetry"]["cabinets"][0]

    assert source == {"DB40": "drawer_base_three@1"}
    assert raw["type"] == "drawer_base"
    assert raw["drawer_bank"]["sizing_policy"] == "progressive_clothing_3@1"
    assert [cell["id"] for cell in raw["drawer_bank"]["cells"]] == [
        "top", "middle", "bottom"
    ]

    compact = FramelessCabinetryPack().parse(_doc(compact_db40())).cabinets[0]
    replay = FramelessCabinetryPack().parse(expanded).cabinets[0]

    assert replay == compact


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda raw: raw["cabinetry"]["cabinets"][0].update(
                archetype="drawer_base_tree@1"
            ),
            "unknown cabinet archetype.*drawer_base_three@1",
        ),
        (
            lambda raw: raw["cabinetry"]["cabinets"][0].update(drawers=3),
            "unknown key 'drawers'",
        ),
    ],
)
def test_compact_drawer_authoring_rejects_unknown_vocabulary(mutation, message):
    raw = compact_db40()
    mutation(raw)

    with pytest.raises(ProjectSchemaError, match=message):
        FramelessCabinetryPack().parse(_doc(raw))


def test_expanded_drawer_record_rejects_missing_cell_with_authoring_path():
    expanded, _ = expand_cabinetry_project(_doc(compact_db40()))
    expanded.sections["cabinetry"]["cabinets"][0]["drawer_bank"]["cells"].pop()

    with pytest.raises(
        ProjectSchemaError,
        match=r"cabinetry\.cabinets\[0\]\.drawer_bank\.cells.*exactly three",
    ):
        FramelessCabinetryPack().parse(expanded)
