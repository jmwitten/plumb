"""DB40 cutting guide: fab-step coverage, tape register, mutation."""

import re
from dataclasses import replace
from types import SimpleNamespace

from pathlib import Path

import pytest

from detailgen.packs import compile_project_file
from detailgen.packs.cabinetry.consumer_manual import (
    consumer_forbidden_tokens,
)
from detailgen.packs.cabinetry.cutting_guide import (
    build_cabinetry_cutting_guide,
    cutting_action_frames,
    cutting_guide_diagrams,
    cutting_kit_groups,
    cutting_panels_manual,
)
from detailgen.rendering.action_frames import FrameContractError
from detailgen.rendering.consumer_pages import visible_instructional_words

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "tests/fixtures/cabinetry/frameless_three_drawer_40.project.yaml"


@pytest.fixture(scope="module")
def project():
    compiled = compile_project_file(PROJECT)
    compiled.require_fabrication_release()
    return compiled


@pytest.fixture(scope="module")
def panels_manual(project):
    return cutting_panels_manual(project)


@pytest.fixture(scope="module")
def guide(project):
    return build_cabinetry_cutting_guide(
        project, basename="frameless_three_drawer_40_cutting_guide.html")


def _frames(manual):
    return tuple(frame for page in manual.pages for frame in page.frames)


def _proxy(project, *, machining=None, cut_list=None):
    """A stand-in project with mutated typed inputs, everything else live."""
    model = project.model
    proxy_model = SimpleNamespace(
        machining=(model.machining if machining is None else machining),
        part=model.part,
        parts=model.parts,
        drawer_bank=model.drawer_bank,
        profile=model.profile,
        hardware=model.hardware,
        anchor_stud_ids=model.anchor_stud_ids,
        section=model.section,
    )
    artifacts = project.artifacts
    if cut_list is not None:
        artifacts = replace(artifacts, cut_list=cut_list)
    return SimpleNamespace(
        model=proxy_model,
        artifacts=artifacts,
        detail=project.detail,
        project_doc=project.project_doc,
    )


class TestBudgets:
    def test_at_most_12_printed_letter_pages(self, guide):
        assert len(guide.pages) <= 12

    def test_at_most_1500_visible_instructional_words(self, guide,
                                                      panels_manual):
        # Diagram titles and captions are reader-visible prose and count;
        # the dense dimension notes are layout data and are excluded.
        diagrams = cutting_guide_diagrams(panels_manual)
        words = visible_instructional_words(
            guide,
            extra_texts=tuple(
                text
                for frame in _frames(guide)
                for diagram_id in frame.detail_diagram_ids
                for text in (diagrams[diagram_id].title,
                             diagrams[diagram_id].caption)))
        assert words <= 1500


class TestSurfaceShape:
    def test_page_kinds_cover_the_required_surfaces(self, guide):
        kinds = [page.kind for page in guide.pages]
        assert kinds[0] == "cover"
        assert kinds[1] == "inventory"
        assert kinds[-1] == "record"
        assert set(kinds[2:-1]) == {"frames"}

    def test_no_hold_page_in_fabrication(self, guide):
        assert all(page.kind != "hold" for page in guide.pages)
        assert not any(frame.is_hold_gate for frame in _frames(guide))

    def test_release_record_closes_the_guide(self, guide, project):
        record = guide.pages[-1]
        assert record.record_title == "Purchasing and cutting release record"
        groups = cutting_kit_groups(project)
        # One product/lot line per purchased thickness family plus the
        # face/grain, label, and approval closers.
        assert len(record.record_fields) == len(groups) + 3

    def test_every_released_fab_step_is_covered(self, guide, project):
        covered = sorted({step_id for frame in _frames(guide)
                          for step_id in frame.source_step_ids})
        released = sorted(step.step_id
                          for step in project.artifacts.fabrication_steps)
        assert covered == released

    def test_only_fabrication_steps_appear(self, guide):
        for frame in _frames(guide):
            for step_id in frame.source_step_ids:
                assert step_id.startswith("fab.")

    def test_no_machine_or_catalog_tokens_in_frame_text(self, project,
                                                        guide):
        tokens = consumer_forbidden_tokens(project)
        for frame in _frames(guide):
            for text in (frame.caption, frame.tool, frame.warning,
                         frame.hold):
                for token in tokens:
                    assert token not in text

    def test_captions_stay_within_50_words(self, guide):
        for frame in _frames(guide):
            assert len(frame.caption.split()) <= 50

    def test_no_hardware_letters_on_this_surface(self, guide):
        assert guide.letters == ()
        assert all(frame.hardware == () for frame in _frames(guide))


class TestKitGroups:
    def test_every_cut_part_appears_exactly_once(self, project):
        groups = cutting_kit_groups(project)
        listed = [pid for _heading, rows in groups
                  for row in rows for pid in row.source_part_ids]
        assert len(listed) == len(set(listed))
        assert len(listed) == len(project.artifacts.cut_list)

    def test_group_headings_keep_native_sheet_units(self, project):
        headings = [heading for heading, _rows in cutting_kit_groups(project)]
        assert any("3/4 in" in heading for heading in headings)
        assert any("16 mm plywood" in heading for heading in headings)

    def test_float_noise_cannot_split_a_thickness_family(self, project):
        # The compiled 19.05 and 19.049999... blanks must land together.
        groups = cutting_kit_groups(project)
        duraply = [heading for heading, _rows in groups
                   if "3/4 in" in heading]
        assert len(duraply) == 1
        assert "13 parts" in duraply[0]

    def test_clean_sixteenth_reads_as_a_tape_fraction(self, project):
        rows = [row.label for _heading, rows in cutting_kit_groups(project)
                for row in rows]
        strip = next(label for label in rows if "anchor strip" in label)
        assert '38-1/2"' in strip
        assert "mm" not in strip

    def test_off_tape_size_carries_exact_millimeters(self, project):
        rows = [row.label for _heading, rows in cutting_kit_groups(project)
                for row in rows]
        side = next(label for label in rows if "box — left side" in label)
        assert "≈" in side and "(533 mm)" in side

    def test_kit_rows_follow_a_mutated_cut_list(self, project):
        mutated = tuple(
            replace(item, length_mm=item.length_mm + 25.4)
            if "anchor_strip" in item.part_id else item
            for item in project.artifacts.cut_list)
        rows = [row.label
                for _heading, rows in
                cutting_kit_groups(_proxy(project, cut_list=mutated))
                for row in rows]
        strip = next(label for label in rows if "anchor strip" in label)
        assert '39-1/2"' in strip

    def test_thickness_mutation_regroups_the_family(self, project):
        mutated = tuple(
            replace(item, thickness_mm=9.0,
                    material="9 mm plywood — test mutation")
            if item.part_id.endswith("captured_back") else item
            for item in project.artifacts.cut_list)
        headings = [heading for heading, _rows in
                    cutting_kit_groups(_proxy(project, cut_list=mutated))]
        assert any(heading.startswith("9 mm plywood") for heading in headings)
        assert not any(heading.startswith("6.35 mm") for heading in headings)


class TestDiagramHonesty:
    def test_runner_stations_plot_every_compiled_center(self, project,
                                                        panels_manual):
        diagrams = cutting_guide_diagrams(panels_manual)
        diagram = diagrams["cut-runner-stations"]
        left = project.model.part("left_end").part_id
        expected = sorted(
            (round(row.location_mm[0], 3), round(row.location_mm[1], 3))
            for row in project.model.machining
            if row.kind == "runner_fixing_station" and row.part_id == left)
        plotted = sorted(
            (round(mark.model_point_mm[0], 3),
             round(mark.model_point_mm[1], 3))
            for mark in diagram.primitives
            if mark.kind == "circle")
        assert plotted == expected

    def test_every_plotted_mark_cites_a_machining_row(self, project,
                                                      panels_manual):
        feature_ids = {row.feature_id for row in project.model.machining}
        diagrams = cutting_guide_diagrams(panels_manual)
        for diagram in diagrams.values():
            for mark in diagram.primitives:
                if mark.kind in ("circle",) or mark.role in ("groove",
                                                             "hold"):
                    assert mark.fact_ref in feature_ids

    def test_end_symmetry_claim_fails_when_ends_diverge(self, project):
        left = project.model.part("left_end").part_id
        moved = False
        mutated = []
        for row in project.model.machining:
            if (not moved and row.kind == "runner_fixing_station"
                    and row.part_id == left):
                mutated.append(replace(
                    row, location_mm=(row.location_mm[0] + 5.0,
                                      row.location_mm[1])))
                moved = True
            else:
                mutated.append(row)
        with pytest.raises(ValueError, match="differ between ends"):
            cutting_panels_manual(_proxy(project, machining=tuple(mutated)))

    def test_common_setup_claim_fails_when_grooves_diverge(self, project):
        mutated = tuple(
            replace(row, width_mm=row.width_mm + 1.0)
            if row.kind == "drawer_bottom_groove"
            and row.part_id.endswith("drawer_top_front") else row
            for row in project.model.machining)
        with pytest.raises(ValueError, match="disagree"):
            cutting_panels_manual(_proxy(project, machining=tuple(mutated)))


class TestSelfContainment:
    """Every machining number the builder needs is printed in the guide.

    Round 1 of the naive-builder read failed because six operations
    deferred their centers to the fabrication packet; these tests keep
    that regression from returning.
    """

    def _all_notes(self, panels_manual) -> str:
        diagrams = cutting_guide_diagrams(panels_manual)
        return " | ".join(
            mark.label for diagram in diagrams.values()
            for mark in diagram.primitives if mark.kind == "text")

    def test_no_step_defers_to_the_fabrication_packet(self, guide,
                                                      panels_manual):
        for frame in _frames(guide):
            assert "packet" not in frame.caption.lower()
        diagrams = cutting_guide_diagrams(panels_manual)
        for diagram in diagrams.values():
            assert "packet" not in diagram.caption.lower()
        assert "PACKET" not in self._all_notes(panels_manual)

    def test_back_groove_positions_printed_for_all_parts(self, project,
                                                         panels_manual):
        notes = self._all_notes(panels_manual)
        for row in project.model.machining:
            if row.kind == "captured_back_groove":
                assert f"{row.location_mm[1]:g}" in notes

    def test_end_panel_centers_printed(self, panels_manual):
        notes = self._all_notes(panels_manual)
        assert "BOTTOM ROW" in notes and "ANCHOR PAIR" in notes
        assert "290.512" in notes and "565.1" in notes

    def test_pull_heights_printed_for_every_front(self, project,
                                                  panels_manual):
        notes = self._all_notes(panels_manual)
        for row in project.model.machining:
            if row.kind == "pull_bore":
                assert f"{round(row.location_mm[1], 3):g}" in notes

    def test_toe_rail_and_toe_center_values_printed(self, panels_manual):
        notes = self._all_notes(panels_manual)
        assert "30.48 / 71.12" in notes
        assert "244.475 / 488.95 / 733.425" in notes

    def test_band_edges_named_on_the_wood_list(self, project):
        labels = [row.label for _heading, rows in cutting_kit_groups(project)
                  for row in rows]
        assert any("band all 4 edges" in label for label in labels)
        assert any("band top edge" in label for label in labels)
        assert any("band front edge" in label for label in labels)


class TestMutation:
    def test_caption_counts_follow_mutated_machining(self, project):
        mutated = tuple(
            replace(row, count=2)
            if row.kind == "toe_attachment_station" else row
            for row in project.model.machining)
        proxy = _proxy(project, machining=mutated)
        manual = cutting_panels_manual(proxy)
        frames = cutting_action_frames(manual, proxy)
        toe = next(frame for frame in frames
                   if frame.frame_id == "cut.toe_attachment.frame")
        assert "all 4 toe screw centers" in toe.caption

    def test_diagram_titles_follow_mutated_machining(self, project):
        # Review C1: diagram titles/captions are reader prose; their counts
        # must move with the model exactly like frame captions.
        mutated = tuple(
            replace(row, count=2)
            if row.kind == "toe_attachment_station" else row
            for row in project.model.machining)
        manual = cutting_panels_manual(_proxy(project, machining=mutated))
        diagrams = cutting_guide_diagrams(manual)
        toe = diagrams["cut-toe-centers"]
        assert toe.title.startswith("4 bottom-to-toe")
        assert "all 4 centers" in toe.caption

    def test_zero_count_machining_row_fails_loudly(self, project):
        mutated = tuple(
            replace(row, count=0)
            if row.kind == "toe_attachment_station"
            and row.receiving_part_id.endswith("toe_front") else row
            for row in project.model.machining)
        with pytest.raises(ValueError, match="count"):
            cutting_panels_manual(_proxy(project, machining=mutated))

    def test_floating_notch_fails_loudly(self, project):
        mutated = tuple(
            replace(row, location_mm=(row.location_mm[0], 5.0))
            if row.kind == "runner_rear_notch"
            and row.location_mm[0] == 0.0 else row
            for row in project.model.machining)
        with pytest.raises(ValueError, match="bottom edge"):
            cutting_panels_manual(_proxy(project, machining=mutated))

    def test_per_part_uniformity_guard_fires_on_divergent_counts(
            self, project):
        # Review I1: "each of the N fronts gets K holes" must fail loudly
        # when one part diverges, not keep quoting the representative.
        dropped = [False]

        def drop_one_pull(rows):
            out = []
            for row in rows:
                if (row.kind == "pull_bore" and not dropped[0]
                        and row.part_id.endswith("drawer_front_bottom")):
                    dropped[0] = True
                    continue
                out.append(row)
            return tuple(out)

        proxy = _proxy(project,
                       machining=drop_one_pull(project.model.machining))
        with pytest.raises(ValueError, match="disagree"):
            cutting_panels_manual(proxy)

    def test_toe_diagram_fails_loudly_without_both_rail_rows(self, project):
        mutated = tuple(
            row for row in project.model.machining
            if not (row.kind == "toe_attachment_station"
                    and row.receiving_part_id.endswith("toe_front")))
        with pytest.raises(ValueError, match="front and one rear"):
            cutting_panels_manual(_proxy(project, machining=mutated))

    def test_stale_hand_written_count_would_fail_loudly(self, project,
                                                        panels_manual):
        with pytest.raises(FrameContractError, match="not backed"):
            cutting_action_frames(
                panels_manual, project,
                _test_caption_override=(
                    "cut.toe_attachment.frame",
                    "Mark all 99 toe screw centers."))


@pytest.fixture(scope="module")
def rendered(project, guide, panels_manual, tmp_path_factory):
    from PIL import Image

    from detailgen.rendering.consumer_manual_html import (
        render_consumer_manual_html,
    )

    image_dir = tmp_path_factory.mktemp("cutting_frames")
    image_paths = {}
    for frame in _frames(guide):
        path = image_dir / f"{frame.frame_id}.png"
        Image.new("RGB", (4, 3), "white").save(path)
        image_paths[frame.frame_id] = path
    cover = image_dir / "cover.png"
    Image.new("RGB", (4, 3), "white").save(cover)
    return render_consumer_manual_html(
        project.detail, guide, image_paths, cover_image=cover,
        inventory_groups=cutting_kit_groups(project),
        parts_heading="Wood list — pre-band cut sizes",
        diagrams=cutting_guide_diagrams(panels_manual))


def _visible_text(html_text: str) -> str:
    text = re.sub(r"<style.*?</style>", " ", html_text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return text


class TestRenderedHtml:
    def test_one_sheet_per_composed_page(self, guide, rendered):
        assert rendered.count('class="sheet') == len(guide.pages)

    def test_thickness_groups_render_as_sections(self, rendered):
        assert rendered.count("<h3>") == 4
        assert "3/4 in" in rendered

    def test_no_hardware_card_without_letters(self, rendered):
        assert "<h2>Hardware</h2>" not in rendered

    def test_no_machine_tokens_in_visible_text(self, project, rendered):
        text = _visible_text(rendered)
        for token in consumer_forbidden_tokens(project):
            assert token not in text

    def test_release_record_renders_with_blank_entries(self, rendered):
        assert "Purchasing and cutting release record" in rendered
        assert "blank fields do not constitute approval" in rendered

    def test_every_image_is_a_data_uri(self, rendered):
        for match in re.finditer(r'<img src="([^"]{0,40})', rendered):
            assert match.group(1).startswith("data:image/")
