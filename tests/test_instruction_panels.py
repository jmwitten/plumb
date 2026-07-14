"""STEPDOC +presentation: pure panel-model acceptance tests.

These tests deliberately stop before VTK/HTML.  They pin the semantic seam:
one reader-step DAG, one valid panel linearization, typed human content, and no
machine vocabulary leaking into the manual register.
"""

from pathlib import Path

import pytest

from detailgen.assemblies.event_graph import (
    ReaderStepProjectionError,
    derive_reader_steps,
)
from detailgen.spec.compiler import compile_spec_file
import detailgen.rendering.instruction_panels as instruction_panels_module
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


def test_panel_steps_are_consecutive_canonical_runs(caddy):
    manual = build_instruction_manual(
        caddy, "armchair_caddy_build_document.html")

    for panel in manual.panels:
        indexes = panel.reader_step_indexes
        assert indexes == tuple(range(indexes[0], indexes[-1] + 1))
    assert tuple(index for panel in manual.panels
                 for index in panel.reader_step_indexes) == tuple(
                     range(len(derive_reader_steps(
                         caddy._connection_checks.event_graph))))


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


def test_panel_event_ownership_delegates_duplicate_detection_to_core(caddy):
    graph = caddy._connection_checks.event_graph
    steps = derive_reader_steps(graph)

    with pytest.raises(ReaderStepProjectionError, match="multiple steps"):
        instruction_panels_module._step_event_map(
            graph, (steps[0], *steps))


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


def test_titles_compose_from_current_reader_labels(tmp_path):
    variant_path = tmp_path / SPEC.name
    variant_path.write_text(SPEC.read_text().replace(
        "reader_name: Registration rail",
        "reader_name: Locator batten",
        1,
    ))
    detail = compile_spec_file(variant_path)
    detail.validate()

    manual = build_instruction_manual(detail)
    bond = next(panel for panel in manual.panels if panel.action == "bond")
    assert "Locator batten" in bond.title
    assert "both registration rails" not in bond.title.lower()


def test_hardware_label_uses_typed_geometry_without_inventing_a_gauge(caddy):
    manual = build_instruction_manual(caddy)
    label = next(panel for panel in manual.panels
                 if panel.action == "fasten").hardware[0].label

    assert "3/16\" dia" in label
    assert "1-1/4\"" in label
    assert "#10" not in label


def test_cure_and_fasten_both_print_each_authored_constraint_why(caddy):
    manual = build_instruction_manual(caddy)
    cure = next(panel for panel in manual.panels if panel.action == "cure")
    fasten = next(panel for panel in manual.panels if panel.action == "fasten")
    whys = tuple(claim.why
                 for claim in caddy._connection_checks.event_graph.constraints)

    assert whys
    assert all(why in cure.rationales for why in whys)
    assert all(why in fasten.rationales for why in whys)


def test_manual_hardware_and_inventory_reconcile_to_the_model(caddy):
    manual = build_instruction_manual(caddy)
    fastener_ids = {
        fastener_id
        for install in caddy._connection_checks.installs
        for fastener_id in install.fasteners
    }
    non_context_ids = {
        part.id for part in caddy.assembly.parts
        if part.id not in caddy._connection_checks.event_graph.context_parts
    }

    assert sum(row.count or 0 for panel in manual.panels
               for row in panel.hardware) == len(fastener_ids)
    assert sum(row.count or 0 for row in manual.inventory) == len(non_context_ids)
    bond = next(panel for panel in manual.panels if panel.action == "bond")
    cure = next(panel for panel in manual.panels if panel.action == "cure")
    assert any(row.icon == "adhesive" and row.count is None
               for row in bond.hardware)
    assert any(row.icon == "clamp" and row.count is None
               for row in cure.tools)


def test_retired_hand_typed_caption_literals_do_not_return():
    source = (ROOT / "src" / "rendering" / "instruction_panels.py").read_text()
    for retired in (
        "Prepare and dry-fit the five wood parts",
        "Glue both registration rails to the top underside",
        "Dry-fit the cut wood parts on the actual sofa arm",
        "#10-class",
        "Lift the completed five-piece caddy",
    ):
        assert retired not in source


def test_context_is_absent_from_every_bench_panel(caddy):
    manual = build_instruction_manual(caddy)
    arm_id = next(part.id for part in caddy.assembly.parts
                  if part.reader_name == "Sofa arm")

    for panel in manual.panels[:-1]:
        assert arm_id not in panel.visible_part_ids
        assert arm_id not in panel.arrival_part_ids
        assert arm_id not in panel.focus_part_ids
        assert "sofa arm" not in " ".join(panel.instructions).lower()


def test_deleting_cross_rail_cure_claim_reverts_to_seven_canonical_panels(
    tmp_path,
):
    text = SPEC.read_text()
    text = text.replace(
        '        - cure: "rail +X -> top underside (glued)"\n'
        '        - cure: "rail -X -> top underside (glued)"',
        '        - cure: "rail +X -> top underside (glued)"',
        1,
    )
    second = text.index(
        '    - connection: "rail -X -> side -X inner face')
    before, after = text[:second], text[second:]
    after = after.replace(
        '        - cure: "rail +X -> top underside (glued)"\n', "", 1)
    variant_path = tmp_path / SPEC.name
    variant_path.write_text(before + after)
    detail = compile_spec_file(variant_path)
    detail.validate()

    manual = build_instruction_manual(detail)
    assert [panel.action for panel in manual.panels] == [
        "prepare", "bond", "cure", "fasten", "cure", "fasten", "join"]
    assert all(panel.reader_step_indexes == tuple(range(
        panel.reader_step_indexes[0], panel.reader_step_indexes[-1] + 1))
        for panel in manual.panels)


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
