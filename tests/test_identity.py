"""Stable part identity + typed references.

``Placed.id`` is a slug derived from the component's *type*, ordinal within
that type, assigned at placement time — independent of the display ``name``.
Validation specs (``expected_overlaps``, ``contacts``, ``bearings``, ``bonds``,
``ground``, ``through_holes``) accept the ``Placed`` handles ``add()``/
``place().on()`` already return, and key on ``id`` internally so a rename
can't silently break an allowlist entry or drop a part from the floating-part
graph. String names remain accepted for convenience but must resolve loudly —
a bad name or a foreign handle raises a clear error listing known parts,
never a raw ``KeyError`` that leaves you guessing.
"""

import pytest

from detailgen.core import IN
from detailgen.components import Lumber, HexNut
from detailgen.assemblies import DetailAssembly, load_step
from detailgen.validation import validate_assembly


# -- id scheme -----------------------------------------------------------

def test_id_is_type_derived_ordinal_independent_of_name():
    d = DetailAssembly("ids")
    a = d.add(HexNut(0.5 * IN, name="zzz"))
    b = d.add(HexNut(0.5 * IN, name="aaa"))
    assert a.id != b.id
    assert a.id.startswith("hex_nut")
    assert b.id.startswith("hex_nut")

    # Deterministic for the same build sequence, regardless of display name.
    d2 = DetailAssembly("ids2")
    a2 = d2.add(HexNut(0.5 * IN, name="totally different a"))
    b2 = d2.add(HexNut(0.5 * IN, name="totally different b"))
    assert a.id == a2.id
    assert b.id == b2.id


def test_id_survives_rename():
    d = DetailAssembly("rename")
    nut = d.add(HexNut(0.5 * IN, name="original"))
    original_id = nut.id
    nut.component.name = "renamed"
    assert nut.id == original_id


# -- resolution: handles and names, loud failure -------------------------

def test_resolve_by_handle_unaffected_by_rename():
    d = DetailAssembly("resolve-handle")
    nut = d.add(HexNut(0.5 * IN, name="original"))
    nut.component.name = "renamed"
    assert d._resolve(nut) is nut
    assert d._resolve("renamed") is nut


def test_unknown_name_reference_raises_helpful_error():
    d = DetailAssembly("bad-name")
    d.add(Lumber("2x4", 6 * IN, name="a"))
    with pytest.raises(KeyError, match="known parts"):
        validate_assembly(d, contacts=[("a", "nope")])


def test_foreign_handle_reference_raises_helpful_error():
    d1 = DetailAssembly("d1")
    foreign = d1.add(Lumber("2x4", 6 * IN, name="a"))
    d2 = DetailAssembly("d2")
    d2.add(Lumber("2x4", 6 * IN, name="a"))
    with pytest.raises(KeyError, match="not a part of assembly"):
        validate_assembly(d2, contacts=[(foreign, "a")])


def test_duplicate_display_name_still_rejected_with_clear_error():
    """Controller's resolution of req 6: duplicate display names stay
    rejected at add() (ids alone don't disambiguate validation reports)."""
    d = DetailAssembly("dup")
    d.add(Lumber("2x4", 6 * IN, name="a"))
    with pytest.raises(ValueError, match="Duplicate part name 'a'"):
        d.add(Lumber("2x4", 6 * IN, name="a"))


# -- validation specs accept handles directly -----------------------------
# (test_validation_spec_accepts_placed_handles_directly dropped as redundant:
# its entire body was a verbatim subset of the "before" half of the test
# below, which additionally checks findings stay identical after rename.)

def test_rename_after_placement_does_not_change_handle_based_verdicts():
    d = DetailAssembly("rename-validate")
    a = d.add(Lumber("2x4", 6 * IN, name="a"))
    b = d.place(Lumber("2x4", 6 * IN, name="b"), "base").on(a, "top")

    before = validate_assembly(d, contacts=[(a, b)], ground=a, bonds=[(a, b)])
    assert before.ok, str(before)

    b.component.name = "renamed-b"
    after = validate_assembly(d, contacts=[(a, b)], ground=a, bonds=[(a, b)])
    assert after.ok, str(after)
    assert [f.passed for f in before.findings] == [f.passed for f in after.findings]


def test_expected_overlaps_accept_handles_and_key_on_id():
    d = DetailAssembly("overlap-handles")
    a = d.add(Lumber("2x4", 6 * IN, name="a"))
    b = d.add(Lumber("2x4", 6 * IN, name="b"), at=(0, 0.5 * IN, 0))  # overlapping
    report = validate_assembly(d, expected_overlaps={(a, b)})
    assert report.ok, str(report)

    # Renaming a part doesn't invalidate a handle-based allowlist entry.
    b.component.name = "b-renamed"
    report2 = validate_assembly(d, expected_overlaps={(a, b)})
    assert report2.ok, str(report2)


# -- BOM: id-traceable, name-independent aggregation ----------------------

def test_bom_table_aggregates_by_type_not_name_and_lists_ids():
    d = DetailAssembly("bom-ids")
    a = d.add(HexNut(0.5 * IN, name="nut-left"))
    b = d.add(HexNut(0.5 * IN, name="nut-right"))
    rows = d.bom_table()
    assert len(rows) == 1
    assert rows[0]["qty"] == 2
    assert set(rows[0]["ids"]) == {a.id, b.id}


def test_bom_rows_include_part_id():
    d = DetailAssembly("bom-flat")
    a = d.add(HexNut(0.5 * IN, name="nut"))
    rows = d.bom()
    assert rows[0]["id"] == a.id


# -- load_step source labeling (req 5) ------------------------------------

def test_load_step_reports_imported_source(monkeypatch):
    part = load_step("assets/manufacturer/does_not_exist.step", "fake bracket")
    monkeypatch.setattr(type(part), "_build",
                        lambda self: Lumber("2x4", 6 * IN).solid)
    d = DetailAssembly("step-source")
    d.add(part)
    rows = d.bom_table()
    assert rows[0]["source"] == "imported STEP"
