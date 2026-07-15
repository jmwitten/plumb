"""Pure Letter-size print-sheet compositor for consumer manuals."""

import pytest

from detailgen.rendering.action_frames import (
    ActionFrame,
    FrameContractError,
    FrameHardware,
    HardwareLetter,
)
from detailgen.rendering.consumer_pages import (
    ConsumerManual,
    ConsumerManualPage,
    compose_consumer_manual,
    visible_instructional_words,
)
from detailgen.rendering.instruction_panels import (
    RecordField,
    RelatedDocumentLink,
)


def _frame(frame_id, caption="Do the modeled work now.", **kwargs):
    defaults = dict(
        source_step_ids=("assembly.example",),
        owned_events=(("place", frame_id, ""),),
        focus_part_ids=("p1",),
    )
    defaults.update(kwargs)
    return ActionFrame(frame_id=frame_id, caption=caption, **defaults)


LETTERS = (HardwareLetter(
    letter="A", kind="k", product_id="p@1", reader_label="Wood screw",
    size_text="7 × 50 mm", quantity_total=8, quantity_unit="screw",
    icon="screw", source_system_ids=("s1",),
),)


def _compose(frames, **kwargs):
    defaults = dict(
        title="Test Consumer Manual",
        basename="test_consumer_manual.html",
        letters=LETTERS,
        kit_gate="All parts cut, edged, bored, labeled, and released.",
        cover_caption="Finished product.",
        related_documents=(
            RelatedDocumentLink("Technical", "technical.html"),),
    )
    defaults.update(kwargs)
    return compose_consumer_manual(frames=tuple(frames), **defaults)


class TestPagePacking:
    def test_cover_then_inventory_then_frames(self):
        manual = _compose([_frame("f1"), _frame("f2"), _frame("f3")])
        kinds = [page.kind for page in manual.pages]
        assert kinds[:2] == ["cover", "inventory"]
        assert set(kinds[2:]) == {"frames"}

    def test_two_frames_per_page_maximum_in_order(self):
        frames = [_frame(f"f{i}") for i in range(5)]
        manual = _compose(frames)
        frame_pages = [p for p in manual.pages if p.kind == "frames"]
        assert [len(p.frames) for p in frame_pages] == [2, 2, 1]
        flat = [f.frame_id for p in frame_pages for f in p.frames]
        assert flat == [f"f{i}" for i in range(5)]

    def test_page_numbers_are_contiguous_from_one(self):
        manual = _compose([_frame("f1"), _frame("f2"), _frame("f3")])
        assert [page.number for page in manual.pages] == list(
            range(1, len(manual.pages) + 1))

    def test_every_frame_appears_on_exactly_one_page(self):
        frames = [_frame(f"f{i}") for i in range(7)]
        manual = _compose(frames)
        placed = [f.frame_id for p in manual.pages for f in p.frames]
        assert sorted(placed) == sorted(f.frame_id for f in frames)
        assert len(placed) == len(set(placed))


class TestHoldIsolation:
    def test_hold_page_is_unavoidable_and_precedes_actions(self):
        hold = ActionFrame(
            frame_id="release_hold",
            caption="Stop until the field and structural record is accepted.",
            source_step_ids=("release_hold",), owned_events=(),
            focus_part_ids=(), is_hold_gate=True,
        )
        action = ActionFrame(
            frame_id="layout_wall",
            caption="Lay out the accepted support axes.",
            source_step_ids=("layout_wall",), owned_events=(),
            focus_part_ids=(),
        )
        manual = compose_consumer_manual(
            frames=(hold, action), title="DV72 installation",
            basename="dv72_installation_guide.html", letters=(),
            kit_gate="Field release required",
            cover_caption="Empty cabinet only",
        )
        assert [page.kind for page in manual.pages] == [
            "cover", "inventory", "hold", "frames",
        ]

    def test_hold_frame_gets_its_own_page(self):
        frames = [
            _frame("f1"), _frame("f2"), _frame("f3"),
            _frame("hold", caption="Stop. Obtain signed clearance first.",
                   is_hold_gate=True,
                   warning="Do not anchor, install, or load."),
            _frame("f4"), _frame("f5"),
        ]
        manual = _compose(frames)
        hold_pages = [p for p in manual.pages if p.kind == "hold"]
        assert len(hold_pages) == 1
        assert [f.frame_id for f in hold_pages[0].frames] == ["hold"]
        # neighbors never share the hold page
        for page in manual.pages:
            if page.kind != "hold":
                assert all(not f.is_hold_gate for f in page.frames)

    def test_frame_after_hold_starts_a_fresh_page(self):
        frames = [_frame("f1"),
                  _frame("hold", is_hold_gate=True),
                  _frame("f2")]
        manual = _compose(frames)
        kinds = [page.kind for page in manual.pages]
        hold_at = kinds.index("hold")
        assert kinds[hold_at + 1] == "frames"
        after = manual.pages[hold_at + 1]
        assert [f.frame_id for f in after.frames] == ["f2"]


class TestRecordPage:
    def test_record_fields_get_their_own_record_page(self):
        frames = [
            _frame("f1"),
            _frame("close", record_title="Signed installation and fit record",
                   record_fields=(RecordField("Installer", "Name and date"),)),
        ]
        manual = _compose(frames)
        record_pages = [p for p in manual.pages if p.kind == "record"]
        assert len(record_pages) == 1
        assert record_pages[0] is manual.pages[-1]
        assert record_pages[0].record_title == (
            "Signed installation and fit record")
        assert record_pages[0].record_fields[0].label == "Installer"


class TestWordBudget:
    def test_counts_caption_warning_hold_tool_words_on_frame_pages(self):
        frames = [
            _frame("f1", caption="One two three."),          # 3
            _frame("f2", caption="Four five.",               # 2
                   warning="Six seven.",                     # 2
                   hold="Eight.",                            # 1
                   tool="Nine ten."),                        # 2
        ]
        manual = _compose(frames, cover_caption="Cover words here.")  # 3
        assert visible_instructional_words(manual) == 13

    def test_inventory_and_record_pages_are_excluded(self):
        frames = [
            _frame("f1", caption="One two."),
            _frame("close",
                   caption="Three four.",
                   record_title="Record",
                   record_fields=(RecordField(
                       "A very long record field label",
                       "with even longer guidance text that must not count"),
                   )),
        ]
        manual = _compose(
            frames,
            kit_gate="Kit gate words that must not count either.",
            cover_caption="")
        assert visible_instructional_words(manual) == 4


class TestContracts:
    def test_empty_frames_are_rejected(self):
        with pytest.raises(FrameContractError, match="frame"):
            _compose([])

    def test_basename_must_be_relative_html(self):
        with pytest.raises(ValueError, match="relative HTML basename"):
            _compose([_frame("f1")], basename="/abs/path.html")
