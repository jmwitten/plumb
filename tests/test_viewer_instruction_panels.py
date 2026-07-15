"""Optional instruction-panel contract for the interactive 3D viewer."""

from dataclasses import replace
from pathlib import Path

import pytest

from detailgen.rendering.instruction_panels import build_instruction_manual
from detailgen.rendering.web_viewer import build_viewer_payload, viewer_css, viewer_js
from detailgen.spec.compiler import compile_spec_file


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "details" / "armchair_caddy.spec.yaml"


@pytest.fixture(scope="module")
def caddy_and_manual():
    detail = compile_spec_file(SPEC)
    detail.validate()
    return detail, build_instruction_manual(detail)


def test_viewer_payload_adds_panel_schedule_only_when_explicitly_supplied(
        caddy_and_manual):
    detail, manual = caddy_and_manual
    legacy = build_viewer_payload(detail)
    staged = build_viewer_payload(detail, instruction_manual=manual)

    assert "instruction_panels" not in legacy
    assert all("first_panel" not in row for row in legacy["parts"].values())

    assert [panel["number"] for panel in staged["instruction_panels"]] == [
        1, 2, 3, 4]
    assert [panel["action"] for panel in staged["instruction_panels"]] == [
        "prepare", "bond", "cure", "join"]
    assert staged["parts"]["side panel +X"]["first_panel"] == 1
    assert staged["parts"]["top panel"]["first_panel"] == 1
    assert staged["parts"]["corner key +X front"]["first_panel"] == 2
    assert staged["parts"]["sofa arm"]["first_panel"] == 4
    key = "corner key +X front"
    assert legacy["parts"][key]["dims"] == \
        "3/8 in hardwood dowel x 1 1/16 in finished"
    assert staged["parts"][key]["dims"] == \
        "3/8 in hardwood dowel x 1 1/16 in finished"

    assert set(staged["instruction_panels"][0]["arrivals"]) == {
        "side panel +X", "side panel -X", "top panel",
    }
    assert len(staged["instruction_panels"][1]["arrivals"]) == 4
    assert staged["instruction_panels"][3]["arrivals"] == ["sofa arm"]


@pytest.mark.parametrize("mutation, message", [
    (lambda rows: rows[:-1], "omits part ids"),
    (lambda rows: (*rows, ("not-a-real-part", 2)), "unknown part ids"),
    (lambda rows: (*rows, rows[0]), "more than once"),
])
def test_viewer_payload_rejects_incomplete_unknown_or_duplicate_schedule_ids(
        caddy_and_manual, mutation, message):
    detail, manual = caddy_and_manual
    broken = replace(manual, part_schedule=tuple(mutation(manual.part_schedule)))

    with pytest.raises(ValueError, match=message):
        build_viewer_payload(detail, instruction_manual=broken)


def test_viewer_source_creates_integer_panel_control_only_for_panel_metadata():
    js = viewer_js()
    css = viewer_css()

    assert "payload.instruction_panels" in js
    assert 'assembly.type = "range"' in js
    assert 'assembly.min = "1"' in js
    assert 'assembly.step = "1"' in js
    assert "payload.instruction_panels.length" in js
    assert "first_panel <= currentPanel" in js
    assert "arrivalNames" in js
    assert "applyAssemblyPanel" in js
    assert ".v-assembly-current" in css


def test_panel_input_changes_visibility_without_changing_explode_value():
    js = viewer_js()

    assert 'assembly.addEventListener("input"' in js
    assert "entry.tops" in js and ".visible =" in js
    assert "explode.value" not in js[js.index(
        'assembly.addEventListener("input"'):js.index(
            'assembly.addEventListener("input"') + 700]
    assert 'explode.addEventListener("input"' in js


def test_hidden_future_parts_cannot_be_picked_or_leak_pinned_tooltips():
    js = viewer_js()

    assert "function objectIsVisible" in js
    assert "function isPartVisible" in js
    assert "if (!objectIsVisible(hits[i].object)) continue;" in js
    assert "if (partName && isPartVisible(partName)) return partName;" in js
    assert "if (!pinned || !pinnedPoint || !isPartVisible(pinned))" in js
    assert "renderPinnedTooltip();" in js
    assert "if (hovered && !isPartVisible(hovered))" in js
