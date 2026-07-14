"""DB40 consumer manual: action frames, lettering, budgets, mutation."""

from dataclasses import replace
from pathlib import Path

import pytest

from detailgen.packs import compile_project_file
from detailgen.packs.cabinetry.consumer_manual import (
    build_cabinetry_consumer_manual,
    consumer_action_frames,
    consumer_forbidden_tokens,
    consumer_hardware_letters,
)
from detailgen.packs.cabinetry.instruction_manual import (
    build_cabinetry_instruction_manual,
)
from detailgen.rendering.action_frames import (
    FrameContractError,
    validate_frame_ownership,
)
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
    return build_cabinetry_instruction_manual(
        project,
        technical_href="frameless_three_drawer_40_build_document.html",
        basename="frameless_three_drawer_40_assembly_manual.html",
    )


@pytest.fixture(scope="module")
def consumer(project):
    return build_cabinetry_consumer_manual(
        project, basename="frameless_three_drawer_40_consumer_manual.html")


def _frames(consumer_manual):
    return tuple(frame for page in consumer_manual.pages
                 for frame in page.frames)


class TestBudgets:
    def test_at_most_12_printed_letter_pages(self, consumer):
        assert len(consumer.pages) <= 12

    def test_at_most_1500_visible_instructional_words(self, consumer):
        assert visible_instructional_words(consumer) <= 1500

    def test_page_kinds_cover_the_required_surfaces(self, consumer):
        kinds = [page.kind for page in consumer.pages]
        assert kinds[0] == "cover"
        assert kinds[1] == "inventory"
        assert "hold" in kinds
        assert kinds[-1] == "record"


class TestProvenance:
    def test_every_panel_event_is_owned_exactly_once(self, panels_manual,
                                                     consumer):
        validate_frame_ownership(panels_manual.panels, _frames(consumer))

    def test_every_frame_is_traceable(self, project, consumer):
        step_ids = {
            step.step_id
            for group in (project.artifacts.fabrication_steps,
                          project.artifacts.assembly_steps,
                          project.artifacts.installation_steps)
            for step in group
        }
        for frame in _frames(consumer):
            assert frame.owned_events or frame.source_step_ids, frame.frame_id
            for step_id in frame.source_step_ids:
                assert step_id in step_ids, (frame.frame_id, step_id)

    def test_no_fabrication_step_becomes_an_assembly_frame(self, consumer):
        for frame in _frames(consumer):
            for step_id in frame.source_step_ids:
                assert not step_id.startswith("fab."), (
                    f"{frame.frame_id} repeats fabrication work "
                    f"({step_id}) inside the assembly manual")

    def test_kit_gate_states_the_prepared_kit_boundary(self, consumer):
        text = consumer.kit_gate.lower()
        for token in ("cut", "edge", "bored", "labeled"):
            assert token in text


class TestReaderRegister:
    def test_no_machine_or_catalog_tokens_in_frame_text(self, project,
                                                        consumer):
        forbidden = consumer_forbidden_tokens(project)
        assert forbidden  # the scan must actually cover something
        for frame in _frames(consumer):
            for text in (frame.caption, frame.tool, frame.hold,
                         frame.warning, frame.repeat_subject):
                for token in forbidden:
                    assert token not in text, (frame.frame_id, token, text)

    def test_frame_hardware_letters_resolve(self, consumer):
        letters = {lt.letter for lt in consumer.letters}
        for frame in _frames(consumer):
            for row in frame.hardware:
                assert row.letter in letters

    def test_captions_stay_within_50_words(self, consumer):
        for frame in _frames(consumer):
            assert len(frame.caption.split()) <= 50, frame.frame_id


class TestHoldAndRecord:
    def test_installation_hold_frame_is_unavoidable(self, consumer):
        holds = [f for f in _frames(consumer) if f.is_hold_gate]
        assert len(holds) == 1
        assert "DO NOT ANCHOR" in holds[0].warning
        hold_page = next(p for p in consumer.pages if p.kind == "hold")
        assert hold_page.frames == (holds[0],)

    def test_signed_installation_record_is_kept(self, consumer):
        record = next(p for p in consumer.pages if p.kind == "record")
        assert record.record_title == "Signed installation and fit record"
        assert len(record.record_fields) == 8


class TestLettering:
    def test_letters_are_deterministic(self, project):
        first = consumer_hardware_letters(project.artifacts.hardware_schedule)
        second = consumer_hardware_letters(
            tuple(reversed(project.artifacts.hardware_schedule)))
        assert first == second

    def test_per_drawer_identities_merge_with_summed_totals(self, project):
        letters = consumer_hardware_letters(
            project.artifacts.hardware_schedule)
        runner = next(lt for lt in letters
                      if lt.kind == "drawer_runner_pair")
        assert runner.quantity_total == 6  # 3 drawers × 1 handed pair (2 pieces)

    def test_reader_labels_come_from_typed_catalog_products(self, project):
        letters = consumer_hardware_letters(
            project.artifacts.hardware_schedule)
        confirmat = next(lt for lt in letters
                         if lt.kind == "carcass_confirmat_system")
        assert "Confirmat" in confirmat.reader_label
        assert "7" in confirmat.size_text and "50" in confirmat.size_text


class TestMutation:
    """Counts must update from typed inputs with no hand-written fixes."""

    def test_drawer_count_mutation_changes_repetition_badges(
            self, project, panels_manual):
        frames3 = consumer_action_frames(
            panels_manual, project, drawer_count=3)
        frames2 = consumer_action_frames(
            panels_manual, project, drawer_count=2)
        boxes3 = next(f for f in frames3 if "box" in f.frame_id)
        boxes2 = next(f for f in frames2 if "box" in f.frame_id)
        assert boxes3.repeat == 3
        assert boxes2.repeat == 2
        adjust3 = next(f for f in frames3 if "adjust" in f.frame_id)
        adjust2 = next(f for f in frames2 if "adjust" in f.frame_id)
        assert "all 3 drawers" in adjust3.caption
        assert "all 2 drawers" in adjust2.caption

    def test_fastener_quantity_mutation_changes_captions_and_hardware(
            self, project, panels_manual):
        mutated = tuple(
            replace(item, quantity=item.quantity * 2)
            if item.kind == "drawer_box_joinery_fastener" else item
            for item in project.artifacts.hardware_schedule)
        frames = consumer_action_frames(
            panels_manual, project, hardware_schedule=mutated)
        boxes = next(f for f in frames if "box" in f.frame_id)
        assert any(row.quantity == 16 for row in boxes.hardware)
        assert "16" in boxes.caption

    def test_letter_totals_follow_the_mutated_schedule(self, project):
        mutated = tuple(
            replace(item, quantity=item.quantity * 2)
            if item.kind == "wall_anchor_system" else item
            for item in project.artifacts.hardware_schedule)
        letters = consumer_hardware_letters(mutated)
        anchor = next(lt for lt in letters
                      if lt.kind == "wall_anchor_system")
        assert anchor.quantity_total == 4

    def test_confirmat_split_mutation_flows_into_the_toe_frame(
            self, project, panels_manual):
        frames = consumer_action_frames(
            panels_manual, project, confirmat_per_panel=(9, 5, 13))
        toe = next(f for f in frames if "toe" in f.frame_id
                   and f.source_step_ids == ("assembly.toe_base",))
        assert any(row.quantity == 9 for row in toe.hardware)
        assert "9" in toe.caption

    def test_stale_hand_written_count_would_fail_loudly(
            self, project, panels_manual):
        # A caption number that no longer matches any typed fact must raise,
        # proving there is no silent hand-written count on this surface.
        with pytest.raises(FrameContractError, match="not backed"):
            consumer_action_frames(
                panels_manual, project, confirmat_per_panel=(8, 5, 13),
                _test_caption_override=(
                    "assembly.toe_base", "Drive 99 screws (A)."))


@pytest.fixture(scope="module")
def rendered(project, consumer, tmp_path_factory):
    from PIL import Image

    from detailgen.rendering.consumer_manual_html import (
        render_consumer_manual_html,
    )

    image_dir = tmp_path_factory.mktemp("consumer_frames")
    image_paths = {}
    for page in consumer.pages:
        for frame in page.frames:
            path = image_dir / f"{frame.frame_id}.png"
            Image.new("RGB", (4, 3), "white").save(path)
            image_paths[frame.frame_id] = path
    cover = image_dir / "cover.png"
    Image.new("RGB", (4, 3), "white").save(cover)
    return render_consumer_manual_html(
        project.detail, consumer, image_paths, cover_image=cover)


def _visible_text(html_text: str) -> str:
    import re
    text = re.sub(r"<style.*?</style>", " ", html_text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return text


class TestRenderedHtml:
    def test_one_sheet_per_composed_page(self, consumer, rendered):
        assert rendered.count('class="sheet') == len(consumer.pages)

    def test_at_most_two_frames_per_sheet(self, rendered):
        import re
        for sheet in re.split(r'(?=<section class="sheet)', rendered):
            assert sheet.count('<article class="frame"') <= 2

    def test_hold_alert_precedes_any_hold_imagery(self, rendered):
        import re
        hold = next(s for s in re.split(r'(?=<section class="sheet)', rendered)
                    if 'sheet hold' in s[:60])
        alert = hold.index('role="alert"')
        image = hold.index("<img") if "<img" in hold else len(hold)
        assert alert < image

    def test_every_image_is_a_data_uri(self, rendered):
        import re
        for src in re.findall(r'<img[^>]+src="([^"]+)"', rendered):
            assert src.startswith("data:image/png;base64,")

    def test_no_machine_tokens_in_visible_text(self, project, rendered):
        text = _visible_text(rendered)
        for token in consumer_forbidden_tokens(project):
            assert token not in text, token

    def test_letter_chips_and_repeat_badges_render(self, consumer, rendered):
        frames = _frames(consumer)
        repeated = next(f for f in frames if f.repeat > 1)
        assert f"{repeated.repeat}&times;" in rendered
        lettered = next(f for f in frames if f.hardware)
        row = lettered.hardware[0]
        assert f"<b>{row.letter}</b> &times;{row.quantity}" in rendered

    def test_print_pagination_css_is_declared(self, rendered):
        assert "@page" in rendered
        assert "size: Letter" in rendered
        assert "break-inside: avoid" in rendered
        assert "break-after: page" in rendered

    def test_mobile_containment_css_is_declared(self, rendered):
        assert "@media" in rendered
        assert "max-width: 100%" in rendered

    def test_hardware_letter_card_lists_every_letter(self, consumer,
                                                     rendered):
        for letter in consumer.letters:
            assert f'data-letter="{letter.letter}"' in rendered

    def test_unknown_frame_image_fails_closed(self, project, consumer,
                                              tmp_path):
        from detailgen.rendering.consumer_manual_html import (
            render_consumer_manual_html,
        )
        with pytest.raises(Exception, match="image"):
            render_consumer_manual_html(
                project.detail, consumer, {}, cover_image=tmp_path / "x.png")


class TestGeneratorScript:
    def test_end_to_end_build_writes_a_contained_consumer_manual(
            self, tmp_path):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            from cabinetry_consumer_manual import (
                build_cabinetry_consumer_document,
            )
        finally:
            sys.path.remove(str(ROOT / "scripts"))

        result = build_cabinetry_consumer_document(
            tmp_path, image_size=(420, 320))
        path = Path(result["consumer_path"])
        assert path.name == "frameless_three_drawer_40_consumer_manual.html"
        assert path.is_file()
        assert result["page_count"] <= 12
        assert result["visible_instructional_words"] <= 1500
        html_text = path.read_text(encoding="utf-8")
        assert html_text.count('class="sheet') == result["page_count"]
        assert "data:image/png;base64," in html_text
        # the accepted four-document set is not rewritten by this script
        assert not (tmp_path / "frameless_three_drawer_40_assembly_manual"
                    ".html").exists()


@pytest.mark.skipif(
    __import__("os").environ.get("DETAILGEN_PRINT_QA") != "1",
    reason="print-break QA needs headless Chrome; set DETAILGEN_PRINT_QA=1",
)
class TestPrintBreaks:
    def test_printed_pdf_page_count_matches_composed_pages(
            self, consumer, tmp_path):
        import re
        import subprocess

        chrome = ("/Applications/Google Chrome.app/Contents/MacOS/"
                  "Google Chrome")
        document = (ROOT / "outputs/frameless_three_drawer_40/"
                    "frameless_three_drawer_40_consumer_manual.html")
        if not Path(chrome).exists() or not document.exists():
            pytest.skip("chrome or generated manual not available")
        pdf = tmp_path / "consumer.pdf"
        subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--no-first-run", "--virtual-time-budget=25000",
             "--timeout=40000", f"--user-data-dir={tmp_path}/profile",
             f"--print-to-pdf={pdf}", "--no-pdf-header-footer",
             f"file://{document}"],
            check=True, capture_output=True, timeout=120)
        data = pdf.read_bytes()
        counts = [int(c) for c in re.findall(
            rb"/Type\s*/Pages[^>]*?/Count\s+(\d+)", data)]
        assert counts, "no page tree found in printed PDF"
        # one printed Letter page per composed sheet: no frame splits/spill
        assert max(counts) == len(consumer.pages)
