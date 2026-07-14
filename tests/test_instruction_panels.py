"""STEPDOC +presentation: pure panel-model acceptance tests.

These tests deliberately stop before VTK/HTML.  They pin the semantic seam:
one reader-step DAG, one valid panel linearization, typed human content, and no
machine vocabulary leaking into the manual register.
"""

from pathlib import Path

import pytest

from detailgen.assemblies.event_graph import derive_reader_steps
from detailgen.spec.compiler import compile_spec_file
from detailgen.rendering.instruction_panels import (
    build_instruction_manual,
    panel_part_schedule,
)


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "details" / "armchair_caddy.spec.yaml"


@pytest.fixture(scope="module")
def caddy():
    detail = compile_spec_file(SPEC)
    detail.validate()
    return detail


def _text(manual) -> str:
    rows = []
    for panel in manual.panels:
        rows.extend((panel.title, *panel.instructions, *panel.rationales,
                     *panel.honesty))
        rows.extend(row.label for row in panel.hardware)
        rows.extend(row.label for row in panel.tools)
    return "\n".join(rows)


def test_caddy_manual_is_a_separate_relative_companion(caddy):
    for bad in ("../technical.html", "/tmp/technical.html", "folder/doc.html",
                "technical.pdf"):
        with pytest.raises(ValueError, match="relative HTML basename"):
            build_instruction_manual(caddy, bad)

    manual = build_instruction_manual(
        caddy, "armchair_caddy_build_document.html")
    assert manual.technical_href == "armchair_caddy_build_document.html"
    assert manual.basename == "armchair_caddy_assembly_manual.html"


def test_caddy_panels_cover_each_reader_step_once(caddy):
    manual = build_instruction_manual(
        caddy, "armchair_caddy_build_document.html")
    covered = tuple(i for panel in manual.panels
                    for i in panel.reader_step_indexes)
    count = len(derive_reader_steps(caddy._connection_checks.event_graph))
    assert sorted(covered) == list(range(count))
    assert len(covered) == len(set(covered))


def test_caddy_has_five_semantic_cohorts_with_hard_process_and_join_breaks(caddy):
    manual = build_instruction_manual(
        caddy, "armchair_caddy_build_document.html")
    assert [panel.action for panel in manual.panels] == [
        "prepare", "bond", "cure", "fasten", "join"]
    assert [len(panel.reader_step_indexes) for panel in manual.panels] == [
        1, 2, 2, 2, 1]
    cure = manual.panels[2]
    assert cure.process_kind == "cure"
    assert len(cure.process_facts) == 2
    assert manual.panels[-1].joins == ("whole detail",)


def test_panel_order_is_a_valid_projection_of_the_event_graph(caddy):
    manual = build_instruction_manual(
        caddy, "armchair_caddy_build_document.html")
    panel_of_step = {
        step: panel.index
        for panel in manual.panels
        for step in panel.reader_step_indexes
    }
    assert all(a < b for a, b in manual.step_edges)
    assert all(panel_of_step[a] < panel_of_step[b]
               for a, b in manual.step_edges)


def test_caddy_panel_text_uses_reader_vocabulary_and_typed_facts(caddy):
    manual = build_instruction_manual(
        caddy, "armchair_caddy_build_document.html")
    rendered = _text(manual)

    assert "Registration rail (1 of 2)" in rendered
    assert "Registration rail (2 of 2)" in rendered
    assert "Side board (1 of 2)" in rendered
    assert "Side board (2 of 2)" in rendered
    assert "8 × Rail-to-side screw" in rendered
    assert "1-1/4\"" in rendered
    assert "full-cure/full-strength condition" in rendered
    assert "No generic duration is represented" in rendered
    assert "not a universal glue-before-screws rule" in rendered

    for banned in ("+X", "-X", "lumber-", "install contract",
                   "connectiontype_default", "authored_process_fact"):
        assert banned not in rendered


def test_only_real_rationales_get_why_boxes(caddy):
    manual = build_instruction_manual(
        caddy, "armchair_caddy_build_document.html")
    by_action = {panel.action: panel for panel in manual.panels}
    assert by_action["prepare"].rationales == ()
    assert by_action["bond"].rationales
    assert by_action["cure"].rationales
    assert by_action["fasten"].rationales
    assert by_action["join"].rationales


def test_join_carries_declared_trust_and_named_analysis_gaps(caddy):
    manual = build_instruction_manual(
        caddy, "armchair_caddy_build_document.html")
    join = manual.panels[-1]
    text = " ".join(join.honesty)
    assert "DECLARED TRUST" in text
    for gap in ("insertion travel", "stability", "sliding resistance",
                "structural capacity", "hot-drink use"):
        assert gap in text


def test_part_schedule_reveals_wood_then_screws_then_context(caddy):
    manual = build_instruction_manual(
        caddy, "armchair_caddy_build_document.html")
    schedule = panel_part_schedule(manual)
    labels = {p.id: p.name for p in caddy.assembly.parts}
    by_name = {labels[pid]: panel for pid, panel in schedule.items()}

    assert by_name["top board"] == 1
    assert by_name["side board +X"] == 1
    assert by_name["registration rail -X"] == 1
    assert by_name["rail-side screw +X upper 0"] == 4
    assert by_name["rail-side screw -X lower 1"] == 4
    assert by_name["sofa arm"] == 5
    assert set(schedule) == {p.id for p in caddy.assembly.parts}
