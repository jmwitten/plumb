"""Reusable miter-crosscut fabrication vocabulary."""

import math

import pytest

from detailgen.core.process_graph import (
    ProcessRecord,
    ProcessStep,
    ProcessStepIdentityCollision,
    StockRef,
    assert_fabrication_fold_invariant,
    fold,
)
from detailgen.core.units import IN


PANEL_WIDTH = 5.5 * IN
PANEL_THICKNESS = 0.75 * IN
PANEL_LENGTH = 8.0 * IN
STOCK = StockRef(
    "3/4 in hardwood panel",
    "linear_stick",
    (PANEL_WIDTH, PANEL_THICKNESS),
    material_key="hardwood",
)


def _record(*miters: ProcessStep) -> ProcessRecord:
    return ProcessRecord(
        STOCK,
        (ProcessStep.crosscut(PANEL_LENGTH, "finished-length"), *miters),
        "test panel",
    )


def test_miter_steps_are_content_keyed_by_end():
    near = ProcessStep.miter_crosscut("near", 45, "top", "near-miter")
    far = ProcessStep.miter_crosscut("far", 45, "top", "far-miter")

    assert near.identity == ("miter_crosscut", "near")
    assert far.identity == ("miter_crosscut", "far")
    _record(near, far)

    with pytest.raises(ProcessStepIdentityCollision, match="miter_crosscut"):
        _record(near, ProcessStep.miter_crosscut("near", 30, "bottom"))


@pytest.mark.parametrize(
    "end, face, angle, message",
    [
        ("middle", "top", 45, "end must be 'near' or 'far'"),
        ("near", "side", 45, "long_face must be 'top' or 'bottom'"),
        ("near", "top", 0, "between 0 and 90"),
        ("near", "top", 90, "between 0 and 90"),
    ],
)
def test_miter_constructor_rejects_unrepresentable_parameters(
    end, face, angle, message
):
    with pytest.raises(ValueError, match=message):
        ProcessStep.miter_crosscut(end, angle, face)


def test_two_top_long_45_degree_miters_fold_to_the_authored_long_and_short_points():
    record = _record(
        ProcessStep.miter_crosscut("near", 45, "top", "near-miter"),
        ProcessStep.miter_crosscut("far", 45, "top", "far-miter"),
    )

    solid = record.installed_geometry()
    vertices = solid.val().Vertices()
    top_x = sorted({round(v.X, 6) for v in vertices if v.Z == pytest.approx(PANEL_THICKNESS)})
    bottom_x = sorted({round(v.X, 6) for v in vertices if v.Z == pytest.approx(0.0)})

    assert top_x == pytest.approx([0.0, PANEL_LENGTH])
    assert bottom_x == pytest.approx([PANEL_THICKNESS, PANEL_LENGTH - PANEL_THICKNESS])
    expected_volume = (
        PANEL_LENGTH * PANEL_WIDTH * PANEL_THICKNESS
        - PANEL_WIDTH * PANEL_THICKNESS**2
    )
    assert solid.val().Volume() == pytest.approx(expected_volume)
    assert_fabrication_fold_invariant("test panel", solid, record)


def test_miter_fold_uses_the_authored_angle_instead_of_hardcoding_45_degrees():
    angle = 30.0
    setback = PANEL_THICKNESS / math.tan(math.radians(angle))
    step = ProcessStep.miter_crosscut("near", angle, "top", "near-miter")
    solid = fold(STOCK, (ProcessStep.crosscut(PANEL_LENGTH), step))

    expected = (
        PANEL_LENGTH * PANEL_WIDTH * PANEL_THICKNESS
        - 0.5 * PANEL_WIDTH * PANEL_THICKNESS * setback
    )
    assert solid.val().Volume() == pytest.approx(expected)


def test_miter_fabrication_note_names_end_angle_and_long_face():
    record = _record(
        ProcessStep.miter_crosscut("near", 45, "top", "near-miter"),
        ProcessStep.miter_crosscut("far", 45, "top", "far-miter"),
    )

    note = record.fab_note()
    assert "near end" in note
    assert "far end" in note
    assert note.count("45") == 2
    assert note.count("top face long") == 2
