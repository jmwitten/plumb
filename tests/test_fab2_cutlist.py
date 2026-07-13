"""FAB-2 — the cut list / BOM / waste read one ProcessRecord (retire R28).

These are the acceptance tests for the consumer re-plumb: the authoritative cut
length is the crosscut step's ``to_length_mm``; the cut-list line NAMES the
operations the geometry folds (the trunk notch, in v1); and the doc build asserts
the fabrication-fold invariant so a "mystery cut" cannot ship.

CAT-1 (caught-past-failure, retro-index.md:65) is the acceptance bar: for the
trunk-crossing board, the rendered geometry, the cut-list line, the BOM length
and the waste all derive from ONE ``steps`` list — it is IMPOSSIBLE for the cut
list to say "plain 48in" while the geometry is notched, because both read the
same record. CAT-4 (fab-design §11) is the forward guard: a production doc build
over a component whose geometry carries an un-instructed cut fails LOUDLY.

The consolidated report is a script (not a package module), loaded by file path
exactly as ``test_cutplan_integration`` does.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

from detailgen.components.railing import DeckBoard
from detailgen.components._geometry import axis_cylinder
from detailgen.core.process_graph import (
    FabricationFoldError, ProcessRecord, ProcessStep, StockRef, fold)
from detailgen.core.units import IN

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cr():
    return _load("cr_fab2_test", REPO_ROOT / "scripts" / "consolidated_report.py")


@pytest.fixture(scope="module")
def details(cr):
    return cr.load_details()


# A board the trunk genuinely crosses — deck_3 in the shipped platform (the
# trunk is centred on this board's tree-face edge). trunk_cut = (cx, cy, r) in mm
# with cy=0 (centred) and r = 12" (the 20" trunk's radius + 2" growth gap).
def _crossing_board() -> DeckBoard:
    return DeckBoard(length=48 * IN, name="deck 3",
                     trunk_cut=(0.0, 0.0, 12 * IN))


# A board the trunk does NOT reach: the clearance cylinder falls entirely
# outside the board footprint (a geometric no-op, fab-design §6.2). No shipped
# platform board is like this — every one is scalloped — so the "plain board"
# case is exercised synthetically, honestly, here.
def _non_crossing_board() -> DeckBoard:
    return DeckBoard(length=48 * IN, name="deck far",
                     trunk_cut=(0.0, 500 * IN, 12 * IN))


def _volume(wp) -> float:
    return wp.val().Volume()


# --------------------------------------------------------------------------- #
# CAT-1 — the notched board tells ONE story (caught-past-failure, R28)
# --------------------------------------------------------------------------- #
def test_cat1_geometry_cutlength_note_and_waste_share_one_steps_list(cr):
    """retro-index.md:65. Every downstream fact about the crossing board is read
    from its ONE ProcessRecord: the BOM length is the crosscut step; the cut-list
    note is the notch step; the installed solid is fold(steps); the waste is the
    stock box minus that same crosscut length. Removing the notch step moves the
    geometry AND the cut list together — so the "geometry notched / cut list
    plain" divergence that shipped before cannot be constructed."""
    board = _crossing_board()
    record = board.fabrication_record()

    # One length, read three ways, all the crosscut step:
    assert board.bom_length_mm() == record.crosscut_length() == pytest.approx(48 * IN)

    # The geometry IS notched (removes material beyond the ease) and the cut note
    # NAMES the notch.
    note = cr._cutlist_fab_note(record)
    assert "notch" in note and '12"' in note and "trunk" in note

    # Now delete the notch step. The geometry recovers the un-notched volume AND
    # the note goes plain — LOCKED TOGETHER, because both read record.steps.
    # There is no state where one says notched and the other says plain. The
    # reference is a board AUTHORED with no trunk_cut (eased, un-notched), so the
    # recovered volume is a real independent target, not the stock box (the ease
    # legitimately removes material either way).
    plain_steps = tuple(s for s in record.steps if s.kind != "notch")
    plain_record = type(record)(record.stock, plain_steps, part_id=record.part_id)
    eased_only = DeckBoard(length=48 * IN, name="deck 3", trunk_cut=None)
    assert _volume(record.installed_geometry()) < _volume(plain_record.installed_geometry())
    assert _volume(plain_record.installed_geometry()) == pytest.approx(
        _volume(eased_only.fabrication_record().installed_geometry()))
    assert cr._cutlist_fab_note(plain_record) == ""


def test_cat1_real_deck3_cutline_names_the_notch(cr, details):
    """End of the real pipeline: compile the platform, aggregate the BOM, and
    render the cut plan — deck_3's rendered cut cell names the notch. The old
    golden said "48.00\" deck 3" plain; that WAS R28 (geometry notched, cut list
    plain). It cannot recur: the note is derived from the same record the length
    is."""
    purchased, _ = cr.combined_bom(details)
    notes = cr.cutlist_fab_notes(purchased, details)
    from detailgen.core.cutplan import pack
    html = cr.render_cutplan(pack(cr.lumber_cut_items(purchased, details)), notes)

    cells = [m.group(1) for m in re.finditer(r'<td class="item">(.*?)</td>', html)
             if "deck 3" in m.group(1)]
    assert cells, "expected a decking cut cell naming deck 3"
    assert any("notch" in c and "trunk" in c for c in cells)


# --------------------------------------------------------------------------- #
# AC1 — the crossing board names the notch; a non-crossing board does not
# --------------------------------------------------------------------------- #
def test_ac1_crossing_board_notes_the_notch_noncrossing_stays_plain(cr):
    crossing = cr._cutlist_fab_note(_crossing_board().fabrication_record())
    assert "notch" in crossing

    # No notch STEP -> plain cut line, truthfully (the absence of the op is the
    # fact), and the folded geometry carries no notch — byte-for-byte an
    # un-notched (eased-only) board, so the cut line and the solid agree.
    board = _non_crossing_board()
    record = board.fabrication_record()
    assert all(s.kind != "notch" for s in record.steps)
    assert cr._cutlist_fab_note(record) == ""
    eased_only = DeckBoard(length=48 * IN, name="deck far", trunk_cut=None)
    assert _volume(record.installed_geometry()) == pytest.approx(
        _volume(eased_only.fabrication_record().installed_geometry()))


def test_ac1_all_six_shipped_boards_are_genuinely_notched(details):
    """Honest divergence from the design's illustrative "only deck_3 crosses"
    framing: in the SHIPPED platform the 12" trunk clearance cylinder scallops
    every board's tree-face end (deck_3 deepest, at centre), so all 6 carry a
    real notch step. Rendering any of them "plain" would REINTRODUCE R28 — so the
    truthful cut list names the notch on all six. (FAB-1's report and its
    adversarial review found the same; the no-op branch is exercised
    synthetically above.)"""
    plat = details["platform"]
    boards = [p.component for p in plat.assembly.parts
              if type(p.component).__name__ == "DeckBoard"]
    assert len(boards) == 6
    for b in boards:
        assert any(s.kind == "notch" for s in b.fabrication_record().steps), b.name


# --------------------------------------------------------------------------- #
# AC4 — single source: deleting the record's data breaks all consumers together
# --------------------------------------------------------------------------- #
def test_ac4_deleting_the_crosscut_breaks_length_and_geometry_together(cr):
    """AC4. bom_length_mm reads the crosscut step, and fold needs the crosscut to
    establish the stick box — ONE datum, two consumers. Strip the crosscut and
    BOTH break: the length reads None (the cut item is dropped from the plan) and
    the geometry can no longer be folded. Neither computes the length
    independently, so neither can silently disagree with the other."""
    record = _crossing_board().fabrication_record()
    no_crosscut = tuple(s for s in record.steps if s.kind != "crosscut")
    stripped = type(record)(record.stock, no_crosscut, part_id=record.part_id)

    assert stripped.crosscut_length() is None          # BOM length: gone
    with pytest.raises(Exception):
        stripped.installed_geometry()                  # geometry: cannot fold


# --------------------------------------------------------------------------- #
# CAT-4 — a feature with no operation is rejected by the production build
# --------------------------------------------------------------------------- #
class _MysteryCutBoard(DeckBoard):
    """A board whose installed geometry carries a bored hole that NO ProcessStep
    describes — the reverse of R28 (a cut the drawing would show but no cut
    instruction explains). Its fabrication_record is the honest, notch-only
    record; its _build injects an un-instructed cut on top of the folded solid.
    The fabrication-fold invariant's material-balance clause must catch it."""

    def _build(self):
        wp = fold(self.fabrication_record().stock, self.fabrication_record().steps)
        # An un-declared 1" bore straight through the thickness — a mystery cut.
        return wp.cut(axis_cylinder(0.5 * IN, self.THICKNESS * 4,
                                    (24 * IN, 2.75 * IN, -self.THICKNESS),
                                    (0, 0, 1)))


class _FakePlaced:
    def __init__(self, pid, component):
        self.id = pid
        self.component = component


class _FakeAssembly:
    def __init__(self, parts):
        self.parts = parts


class _FakeDetail:
    def __init__(self, assembly):
        self.assembly = assembly


class _NoteRecord:
    def __init__(self, note):
        self._note = note

    def fab_note(self):
        return self._note


class _NamedFabPart:
    def __init__(self, name, note):
        self.name = name
        self._record = _NoteRecord(note)

    def bom_label(self):
        return "1x6 lumber"

    def fabrication_record(self):
        return self._record


class _NamedPlaced:
    def __init__(self, pid, component, reader_name):
        self.id = pid
        self.component = component
        self.reader_name = reader_name

    @property
    def name(self):
        return self.component.name


def test_cat4_production_build_rejects_a_mystery_cut(cr):
    """fab-design §11 CAT-4 + the FAB-1 review's FIX-FIRST obligation: the guard
    the doc build runs (assert_details_fabrication_sound) rejects a component
    whose geometry has an un-instructed cut, LOUDLY, naming the part. Enumeration
    is by capability (the part has a fabrication_record), not by type name, so a
    subclass the sweep never heard of is still covered."""
    mystery = _MysteryCutBoard(length=48 * IN, name="deck mystery",
                               trunk_cut=(0.0, 0.0, 12 * IN))
    details = {"platform": _FakeDetail(_FakeAssembly(
        [_FakePlaced("deck_mystery", mystery)]))}

    with pytest.raises(FabricationFoldError) as exc:
        cr.assert_details_fabrication_sound(details)
    assert "deck_mystery" in str(exc.value)


def test_cat4_production_build_passes_on_a_sound_board(cr):
    """The guard is not a blanket raise: a correctly-delegating board (installed
    geometry IS fold(record)) passes clean, so real details build."""
    board = _crossing_board()
    details = {"platform": _FakeDetail(_FakeAssembly(
        [_FakePlaced("deck_3", board)]))}
    cr.assert_details_fabrication_sound(details)  # no raise


def test_duplicate_reader_labels_keep_distinct_fabrication_notes(cr):
    """Machine-distinct cuts never associate notes through their display label."""
    parts = [
        _NamedPlaced(
            "rail-a",
            _NamedFabPart("registration rail +X", "drill the left registration holes"),
            "Registration rail",
        ),
        _NamedPlaced(
            "rail-b",
            _NamedFabPart("registration rail -X", "drill the right registration holes"),
            "Registration rail",
        ),
    ]
    details = {"fixture": _FakeDetail(_FakeAssembly(parts))}
    purchased = [
        {
            "item": "1x6 lumber",
            "length_mm": 24 * IN,
            "ids": ["rail-a"],
            "origin": {"fixture"},
        },
        {
            "item": "1x6 lumber",
            "length_mm": 36 * IN,
            "ids": ["rail-b"],
            "origin": {"fixture"},
        },
    ]

    items = cr.lumber_cut_items(purchased, details)
    notes = cr.cutlist_fab_notes(purchased, details)
    from detailgen.core.cutplan import pack
    plan = pack(items)["1x6 lumber"]
    cuts = [cut for stick in plan.sticks for cut in stick.cuts]
    html = cr.render_cutplan({"1x6 lumber": plan}, notes)

    assert len(cuts) == 2
    assert {cut.source_key for cut in cuts} == {
        ("fixture", "rail-a"),
        ("fixture", "rail-b"),
    }
    assert set(notes) == {
        ("1x6 lumber", ("fixture", "rail-a")),
        ("1x6 lumber", ("fixture", "rail-b")),
    }
    assert html.count("Registration rail (1 of 2)") == 1
    assert html.count("Registration rail (2 of 2)") == 1
    assert html.count("drill the left registration holes") == 1
    assert html.count("drill the right registration holes") == 1
    assert re.search(
        r"Registration rail \(1 of 2\) &mdash; drill the left registration holes",
        html,
    )
    assert re.search(
        r"Registration rail \(2 of 2\) &mdash; drill the right registration holes",
        html,
    )


def test_render_cutplan_keeps_legacy_source_text_note_keys(cr):
    """Callers that omit ``source_key`` retain the pre-identity note contract."""
    from detailgen.core.cutplan import CutItem, pack

    source = "legacy fixture: legacy rail"
    plan = pack([CutItem("1x6 lumber", 24 * IN, source)])["1x6 lumber"]
    html = cr.render_cutplan(
        {"1x6 lumber": plan},
        {("1x6 lumber", source): "legacy fabrication note"},
    )

    assert "legacy rail &mdash; legacy fabrication note" in html


# --------------------------------------------------------------------------- #
# FAB-2 follow-up (task #7): the note renderer shows the REAL radius, reads the
# feature noun off the step's own content, and falls back to an honest generic.
# --------------------------------------------------------------------------- #
def _one_notch_record(radius_mm: float, feature: str) -> ProcessRecord:
    """A minimal record carrying a single notch, for exercising the renderer's
    radius formatting / noun sourcing / generic fallback in isolation."""
    stock = StockRef("5/4x6 PT", "linear_stick",
                     (DeckBoard.WIDTH, DeckBoard.THICKNESS))
    return ProcessRecord(stock, (ProcessStep.crosscut(48 * IN),
                                 ProcessStep.notch(0.0, 0.0, radius_mm,
                                                   feature=feature)),
                         part_id="probe")


def test_radius_shows_the_real_value_not_a_whole_inch_roundoff(cr):
    """The old note rounded the radius to whole inches, so a 1.75\" cup-hole /
    fillet radius rendered a false "2\"". The note now shows the real value with
    trailing zeros trimmed — a fractional radius reads truthfully, a whole-inch
    radius still reads "12\"" (no "12.0\")."""
    fractional = cr._cutlist_fab_note(_one_notch_record(1.75 * IN, "trunk"))
    assert '1.75"' in fractional and '2"' not in fractional

    whole = cr._cutlist_fab_note(_one_notch_record(12 * IN, "trunk"))
    assert '12"' in whole and '12.0"' not in whole


def test_note_reads_the_feature_noun_off_the_step_content(cr):
    """The renderer names no domain itself: the noun in the note is exactly the
    notch's own ``feature`` content, so the platform deck's trunk cut reads
    "trunk" — truthful, and byte-identical to the shipped cut-plan golden line.
    (DRAWDIM appended the derived STATION to the same line — see
    test_material_removing_steps_carry_their_station; golden regenerated,
    insertion-only.)"""
    note = cr._cutlist_fab_note(_crossing_board().fabrication_record())
    assert note == ('notch: 12" R full-cylinder clearance pocket around the '
                    'trunk at the tree-face end, cut through the thickness'
                    ' — center 0" from one end (48" from the other), '
                    '0" from one edge')


def test_material_removing_steps_carry_their_station():
    """DRAWDIM class-closer (naive-builder review of the trebuchet doc): a
    bore/notch cut-plan line must carry its STATION — the derived board-local
    center as tape distances from BOTH stick ends — because a station-less
    bore note leaves the driller guessing which end (the trebuchet arm bored
    from the wrong end is a 1:4 arm that won't throw). Both distances are the
    step's own arithmetic (center + complement to the crosscut length), and a
    mid-width cut says so."""
    board = DeckBoard(length=48 * IN)
    board.apply_feature_cut(38.4 * IN, board.WIDTH / 2, 0.375 * IN,
                            noun="axle bore", step_kind="bore",
                            provenance="bore:axle_bore")
    note = board.fabrication_record().fab_note()
    assert 'center 38.4" from one end (9.6" from the other)' in note, note
    assert "on the width centerline" in note, note

    # The class rule, not the instance: EVERY in-board material-removing step
    # renders a station (a note that names a cut but no place to mark it is
    # the defect class this closes).
    for rec in (_crossing_board().fabrication_record(),
                board.fabrication_record()):
        for s in rec.steps:
            if s.kind in ("bore", "notch"):
                assert "from one end" in rec.fab_note(), rec.fab_note()


def test_offboard_notch_center_omits_the_station():
    """A tangential clearance notch whose CENTER lies outside the board's own
    footprint has no tape-markable station — a negative distance would be
    noise, not a mark. The phrase is honestly omitted; the qualitative member
    wording and the drawing locate that cut."""
    board = DeckBoard(length=48 * IN)
    # center 3in BEYOND the board end: the cylinder still bites the board.
    board.apply_feature_cut(51 * IN, board.WIDTH / 2, 6 * IN,
                            noun="trunk", step_kind="notch",
                            provenance="clearance_cut:trunk")
    note = board.fabrication_record().fab_note()
    assert "clearance pocket around the trunk" in note
    assert "from one end" not in note, note


def test_notch_with_no_usable_feature_noun_renders_the_honest_generic(cr):
    """When the step carries no usable feature noun, the renderer renders the
    honest generic ("clearance pocket (see drawing)") rather than GUESSING a
    domain noun — the never-guess rule. (The caddy's cup hole USED to hit this
    gap — it reused the deck notch and carried no "cup" noun; CL-2 closed it by
    making the cup hole a named ``bore`` FEATURE, so this test now covers only the
    genuinely-unnamed case, which must still render generic, never invent a noun.)"""
    generic = cr._cutlist_fab_note(_one_notch_record(1.75 * IN, "  "))
    assert "clearance pocket (see drawing)" in generic
    assert "trunk" not in generic and '1.75"' in generic
