"""Pure ActionFrame layer: lettering, caption honesty, event ownership."""

import pytest

from detailgen.rendering.action_frames import (
    ActionFrame,
    FrameContractError,
    FrameHardware,
    FrameIllustration,
    HardwareLetter,
    assign_hardware_letters,
    validate_caption,
    validate_frame_ownership,
)


class _Item:
    """HardwareItem-shaped test double (matches packs.cabinetry.artifacts)."""

    def __init__(self, system_id, kind, product_id, quantity,
                 quantity_unit="piece", related_parts=()):
        self.system_id = system_id
        self.kind = kind
        self.product_id = product_id
        self.quantity = quantity
        self.quantity_unit = quantity_unit
        self.related_parts = tuple(related_parts)


def _labeler(kind, product_id, quantity_unit):
    labels = {
        "carcass_confirmat_system": ("Confirmat screw", "7 × 50 mm", "screw"),
        "drawer_runner_pair": ("Drawer runner", "left/right pair", "part"),
        "wall_anchor_system": ("Cabinet anchor screw", '8 × 3-1/8"', "screw"),
    }
    return labels[kind]


SCHEDULE = (
    _Item("hw.anchor", "wall_anchor_system", "grk_8x3_1_8@1", 2, "screw"),
    _Item("hw.confirmat", "carcass_confirmat_system",
          "hafele_confirmat_7x50@1", 26, "screw"),
    # per-drawer triplet: identical identity rows must merge into one letter
    _Item("hw.runner.1", "drawer_runner_pair", "blum_movento@1", 2,
          "handed piece"),
    _Item("hw.runner.2", "drawer_runner_pair", "blum_movento@1", 2,
          "handed piece"),
    _Item("hw.runner.3", "drawer_runner_pair", "blum_movento@1", 2,
          "handed piece"),
)


class TestHardwareLettering:
    def test_letters_are_deterministic_and_sorted_by_identity(self):
        letters = assign_hardware_letters(SCHEDULE, labeler=_labeler)
        assert [lt.letter for lt in letters] == ["A", "B", "C"]
        assert [lt.kind for lt in letters] == [
            "carcass_confirmat_system", "drawer_runner_pair",
            "wall_anchor_system",
        ]

    def test_input_order_does_not_change_letters(self):
        letters = assign_hardware_letters(SCHEDULE, labeler=_labeler)
        shuffled = assign_hardware_letters(
            tuple(reversed(SCHEDULE)), labeler=_labeler)
        assert letters == shuffled

    def test_identical_identity_rows_merge_and_sum_quantities(self):
        letters = assign_hardware_letters(SCHEDULE, labeler=_labeler)
        runner = next(lt for lt in letters if lt.kind == "drawer_runner_pair")
        assert runner.quantity_total == 6
        assert runner.source_system_ids == (
            "hw.runner.1", "hw.runner.2", "hw.runner.3")

    def test_new_identity_inserts_letter_deterministically(self):
        extra = SCHEDULE + (_Item(
            "hw.pull", "drawer_pull", "hafele_vogue@1", 3, "pull"),)

        def labeler(kind, product_id, quantity_unit):
            if kind == "drawer_pull":
                return ("Drawer pull", "155 mm", "part")
            return _labeler(kind, product_id, quantity_unit)

        letters = assign_hardware_letters(extra, labeler=labeler)
        assert [(lt.letter, lt.kind) for lt in letters] == [
            ("A", "carcass_confirmat_system"),
            ("B", "drawer_pull"),
            ("C", "drawer_runner_pair"),
            ("D", "wall_anchor_system"),
        ]

    def test_reader_label_and_sizes_come_from_labeler(self):
        letters = assign_hardware_letters(SCHEDULE, labeler=_labeler)
        anchor = next(lt for lt in letters if lt.kind == "wall_anchor_system")
        assert anchor.reader_label == "Cabinet anchor screw"
        assert anchor.size_text == '8 × 3-1/8"'
        assert anchor.product_id == "grk_8x3_1_8@1"

    def test_conflicting_quantity_units_for_one_identity_are_rejected(self):
        bad = (
            _Item("hw.a", "drawer_runner_pair", "blum_movento@1", 2, "handed piece"),
            _Item("hw.b", "drawer_runner_pair", "blum_movento@1", 1, "complete set"),
        )
        letters = assign_hardware_letters(bad, labeler=_labeler)
        # distinct quantity_unit = distinct selection identity = distinct letter
        assert len(letters) == 2

    def test_more_than_26_identities_get_double_letters(self):
        def labeler(kind, product_id, quantity_unit):
            return (f"Reader {kind}", "size", "part")
        items = tuple(
            _Item(f"hw.{i:02d}", f"kind_{i:02d}", f"prod_{i:02d}@1", 1)
            for i in range(28)
        )
        letters = assign_hardware_letters(items, labeler=labeler)
        assert letters[25].letter == "Z"
        assert letters[26].letter == "AA"
        assert letters[27].letter == "AB"


class TestCaptionValidation:
    def test_accepts_short_imperative_with_allowed_numbers(self):
        validate_caption(
            "Drive 8 Confirmat screws (A) through each side into the bottom.",
            allowed_numbers=frozenset({"8"}),
            forbidden_tokens=("side_left", "hafele_confirmat_7x50@1"),
        )

    def test_rejects_more_than_50_words(self):
        caption = " ".join(["word"] * 51)
        with pytest.raises(FrameContractError, match="50 words"):
            validate_caption(caption, allowed_numbers=frozenset(),
                             forbidden_tokens=())

    def test_accepts_exactly_50_words(self):
        validate_caption(" ".join(["word"] * 50),
                         allowed_numbers=frozenset(), forbidden_tokens=())

    def test_rejects_machine_id_tokens(self):
        with pytest.raises(FrameContractError, match="side_left"):
            validate_caption(
                "Stand side_left upright.",
                allowed_numbers=frozenset(),
                forbidden_tokens=("side_left",),
            )

    def test_rejects_numbers_not_backed_by_a_typed_fact(self):
        with pytest.raises(FrameContractError, match="9"):
            validate_caption(
                "Drive 9 screws.",
                allowed_numbers=frozenset({"8"}),
                forbidden_tokens=(),
            )

    def test_allowed_number_list_covers_fractions_and_decimals(self):
        validate_caption(
            "Bore at 37 mm and again at 261.5 mm from the bottom edge.",
            allowed_numbers=frozenset({"37", "261.5"}),
            forbidden_tokens=(),
        )

    def test_empty_caption_is_rejected(self):
        with pytest.raises(FrameContractError, match="empty"):
            validate_caption("  ", allowed_numbers=frozenset(),
                             forbidden_tokens=())


def _frame(frame_id, owned_events, **kwargs):
    defaults = dict(
        caption="Do the modeled work.",
        source_step_ids=("assembly.example",),
        focus_part_ids=("p1",),
        context_part_ids=(),
        hardware=(),
    )
    defaults.update(kwargs)
    return ActionFrame(frame_id=frame_id, owned_events=tuple(owned_events),
                       **defaults)


class _Panel:
    def __init__(self, source_events):
        self.source_events = tuple(source_events)


EV_A = ("presentation", "unit.toe", "place")
EV_B = ("process", "carcass.glue", "cure")
EV_C = ("presentation", "conn.back", "connect")


class TestFrameOwnership:
    def test_exact_partition_passes(self):
        panels = (_Panel((EV_A, EV_B)), _Panel((EV_C,)))
        frames = (_frame("f1", (EV_A,)), _frame("f2", (EV_B,)),
                  _frame("f3", (EV_C,)))
        validate_frame_ownership(panels, frames)

    def test_dropped_event_fails(self):
        panels = (_Panel((EV_A, EV_B)),)
        frames = (_frame("f1", (EV_A,)),)
        with pytest.raises(FrameContractError, match="unowned"):
            validate_frame_ownership(panels, frames)

    def test_duplicated_event_fails(self):
        panels = (_Panel((EV_A,)),)
        frames = (_frame("f1", (EV_A,)), _frame("f2", (EV_A,)))
        with pytest.raises(FrameContractError, match="owned more than once"):
            validate_frame_ownership(panels, frames)

    def test_unknown_event_fails(self):
        panels = (_Panel((EV_A,)),)
        frames = (_frame("f1", (EV_A,)), _frame("f2", (EV_C,)))
        with pytest.raises(FrameContractError, match="unknown"):
            validate_frame_ownership(panels, frames)


class TestActionFrameModel:
    def test_frame_is_immutable_and_carries_typed_fields(self):
        frame = ActionFrame(
            frame_id="assembly.carcass.1",
            caption="Fasten the left side to the bottom with 8 screws (A).",
            source_step_ids=("assembly.carcass",),
            owned_events=(EV_A,),
            focus_part_ids=("side_left", "bottom"),
            context_part_ids=("toe_front",),
            hardware=(FrameHardware(letter="A", quantity=8),),
            tool="Drill/driver with Confirmat bit",
            repeat=3,
            repeat_subject="per drawer",
            hold="Keep clamped until the selected label's full cure.",
            warning="",
            illustration=FrameIllustration(
                intent="assembly_scene", panel_index=2),
        )
        assert frame.repeat == 3
        assert frame.hardware[0].quantity == 8
        with pytest.raises(Exception):
            frame.caption = "mutated"

    def test_repeat_below_one_is_rejected(self):
        with pytest.raises(FrameContractError, match="repeat"):
            _frame("f1", (EV_A,), repeat=0)

    def test_hardware_quantity_must_be_positive(self):
        with pytest.raises(FrameContractError, match="quantity"):
            FrameHardware(letter="A", quantity=0)

    def test_illustration_intent_is_constrained(self):
        with pytest.raises(FrameContractError, match="intent"):
            FrameIllustration(intent="decorative", panel_index=1)
