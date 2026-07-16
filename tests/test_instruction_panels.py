"""STEPDOC +presentation: pure panel-model acceptance tests.

These tests deliberately stop before VTK/HTML.  They pin the semantic seam:
one reader-step DAG, one valid panel linearization, typed human content, and no
machine vocabulary leaking into the manual register.
"""

from pathlib import Path

import pytest
import yaml

from detailgen.assemblies.event_graph import (
    ReaderStepProjectionError,
    derive_reader_steps,
)
from detailgen.spec.compiler import compile_spec_file
import detailgen.rendering.instruction_panels as instruction_panels_module
from detailgen.rendering.instruction_panels import (
    DisplayRow,
    JoinPresentation,
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


def _write_ungoverned_variant(path, text):
    raw = yaml.safe_load(text)
    raw.pop("design_review", None)
    path.write_text(yaml.safe_dump(raw, sort_keys=False))


def test_caddy_manual_is_a_separate_relative_companion(caddy):
    for bad in ("../technical.html", "/tmp/technical.html", "folder/doc.html",
                "technical.pdf"):
        with pytest.raises(ValueError, match="relative HTML basename"):
            build_instruction_manual(caddy, bad)

    manual = build_instruction_manual(
        caddy, "armchair_caddy_build_document.html")
    assert manual.technical_href == "armchair_caddy_build_document.html"
    assert manual.basename == "armchair_caddy_assembly_manual.html"


def test_manual_identity_and_proof_copy_are_detail_configurable(caddy):
    manual = build_instruction_manual(
        caddy,
        "technical.html",
        title="Custom model-backed manual",
        basename="custom_assembly_manual.html",
        lede=("Custom proof boundary with {declared_constraints} authored "
              "constraints."),
    )

    assert manual.title == "Custom model-backed manual"
    assert manual.basename == "custom_assembly_manual.html"
    assert manual.lede.startswith("Custom proof boundary")

    with pytest.raises(ValueError, match="relative HTML basename"):
        build_instruction_manual(caddy, basename="folder/manual.html")


def test_project_can_author_join_reader_copy_without_changing_graph(caddy):
    presentation = JoinPresentation(
        title="Bench work complete — stop before field placement",
        instructions=("Review the separate field-installation holds.",),
        honesty=("FIELD HOLD — site attachment is not represented.",),
        tools=(DisplayRow("fit", "Adult hold-point review"),),
    )

    manual = build_instruction_manual(caddy, join_presentation=presentation)
    join = next(panel for panel in manual.panels if panel.action == "join")

    assert join.title == presentation.title
    assert join.instructions == presentation.instructions
    assert join.honesty == presentation.honesty
    assert join.tools == presentation.tools


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


def test_caddy_has_four_semantic_cohorts_with_hard_process_and_join_breaks(caddy):
    manual = build_instruction_manual(
        caddy, "armchair_caddy_build_document.html")
    assert [panel.action for panel in manual.panels] == [
        "prepare", "bond", "cure", "join"]
    assert [len(panel.reader_step_indexes) for panel in manual.panels] == [
        1, 2, 2, 1]
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

    assert "Top panel" in rendered
    assert "Side panel (1 of 2)" in rendered
    assert "Side panel (2 of 2)" in rendered
    assert "Insert both corner keys" in rendered
    assert "45-degree miter" in rendered
    assert "full-cure/full-strength condition" in rendered
    assert "No generic duration is represented" in rendered

    for banned in ("+X", "-X", "lumber-", "install contract",
                   "connectiontype_default", "authored_process_fact",
                   "screw"):
        assert banned not in rendered


def test_repeated_connection_actions_name_the_specific_reader_parts(caddy):
    manual = build_instruction_manual(caddy)
    instructions = {
        panel.action: "\n".join(panel.instructions)
        for panel in manual.panels
    }

    for index in (1, 2):
        assert f"Side panel ({index} of 2)" in instructions["bond"]
    assert instructions["bond"].count("Insert both corner keys") == 2
    assert len(next(panel for panel in manual.panels
                    if panel.action == "cure").process_facts) == 2


def test_prepare_instructions_and_inventory_include_modeled_part_dimensions(caddy):
    manual = build_instruction_manual(caddy)
    prepare = next(panel for panel in manual.panels if panel.action == "prepare")
    instructions = "\n".join(prepare.instructions)
    inventory = "\n".join(row.label for row in manual.inventory)

    for dimensions in (
        '3/4 in hardwood, 8 x 5 1/2 in',
        '3/4 in hardwood, 7 3/4 x 5 1/2 in',
    ):
        assert dimensions in instructions
        assert dimensions in inventory
    assert '3/8 in hardwood dowel x 1 1/16 in finished' in inventory


def test_inventory_separates_nominal_stock_from_actual_finished_dimensions(
    caddy,
):
    manual = build_instruction_manual(caddy)
    inventory = "\n".join(row.label for row in manual.inventory)

    assert 'actual 3/4" × 5-1/2" × 7-3/4"' in inventory
    assert 'actual 3/4" × 5-1/2" × 8"' in inventory
    assert any(
        row.icon == "adhesive"
        and "required consumable" in row.label.lower()
        and "product selection required" in row.label.lower()
        for row in manual.inventory
    )


def test_prepare_instructions_derive_crosscuts_and_edge_easing(caddy):
    manual = build_instruction_manual(caddy)
    prepare = next(panel for panel in manual.panels if panel.action == "prepare")
    instructions = "\n".join(prepare.instructions)

    assert ('Crosscut Side panel (1 of 2) to '
            '3/4 in hardwood, 7 3/4 x 5 1/2 in.') in instructions
    assert ('Crosscut Top panel to '
            '3/4 in hardwood, 8 x 5 1/2 in.') in instructions
    assert ('Machine Side panel (2 of 2): miter crosscut: '
            'far end at 45°, top face long.') in instructions
    assert ('Ease the long edges of Side panel (1 of 2) '
            'to a 1/8" radius.') in instructions
    assert 'Ease the long edges of Top panel to a 1/8" radius.' in instructions
    assert "|X" not in instructions


def test_prepare_translates_the_cup_bore_into_shop_dimensions_without_jargon(
    caddy,
):
    manual = build_instruction_manual(caddy)
    prepare = next(panel for panel in manual.panels if panel.action == "prepare")
    instructions = "\n".join(prepare.instructions)

    assert '3-1/2" diameter (1-3/4" radius)' in instructions
    assert "cutter type is not represented" in instructions
    assert "full-cylinder" not in instructions


def test_titles_compose_from_current_reader_labels(tmp_path):
    variant_path = tmp_path / SPEC.name
    _write_ungoverned_variant(
        variant_path,
        SPEC.read_text().replace(
            "reader_name: Side panel",
            "reader_name: Locator panel",
        ),
    )
    detail = compile_spec_file(variant_path)
    detail.validate()

    manual = build_instruction_manual(detail)
    bond = next(panel for panel in manual.panels if panel.action == "bond")
    assert "Locator panel" in bond.title
    assert "side panel" not in bond.title.lower()


def test_hardware_label_uses_typed_keys_without_inventing_screws(caddy):
    manual = build_instruction_manual(caddy)
    inventory_label = next(
        row.label for row in manual.inventory
        if "Corner key" in row.label)

    assert "4 × Corner key" in inventory_label
    assert "3/8 in hardwood dowel" in inventory_label
    assert "1 1/16 in finished" in inventory_label
    assert "screw" not in inventory_label.lower()
    assert not [panel for panel in manual.panels if panel.action == "fasten"]


def test_bond_and_cure_print_the_authored_process_why(caddy):
    manual = build_instruction_manual(caddy)
    bond = next(panel for panel in manual.panels if panel.action == "bond")
    cure = next(panel for panel in manual.panels if panel.action == "cure")
    whys = {
        fact.why
        for fact in caddy._connection_checks.event_graph.process_facts.values()
    }

    assert whys
    assert all(why in bond.rationales for why in whys)
    assert all(why in cure.rationales for why in whys)


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


def test_derived_bond_cure_edges_need_no_cross_connection_claim(caddy):
    graph = caddy._connection_checks.event_graph
    assert graph.constraints == ()
    manual = build_instruction_manual(caddy)
    assert [panel.action for panel in manual.panels] == [
        "prepare", "bond", "cure", "join"]
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


def test_part_schedule_reveals_panels_then_keys_then_context(caddy):
    manual = build_instruction_manual(
        caddy, "armchair_caddy_build_document.html")
    schedule = panel_part_schedule(manual)
    labels = {p.id: p.name for p in caddy.assembly.parts}
    by_name = {labels[pid]: panel for pid, panel in schedule.items()}

    assert by_name["top panel"] == 1
    assert by_name["side panel +X"] == 1
    assert by_name["side panel -X"] == 1
    assert by_name["corner key +X front"] == 2
    assert by_name["corner key -X back"] == 2
    assert by_name["sofa arm"] == 4
    assert set(schedule) == {p.id for p in caddy.assembly.parts}
