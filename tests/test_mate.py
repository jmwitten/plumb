"""Datum sanity + the mate API: a mate lands exactly where the equivalent
``add(at, rotate)`` puts it, and offset/rotate/flip modifiers do what they say.
"""

import pytest

from detailgen.core import IN, FT
from detailgen.core.frame import Frame
from detailgen.components import (
    Lumber, ConcretePier, Footing, Slab, LagScrew, HexBolt, HexNut, Washer,
    ThreadedRod, Boulder, Epoxy, JoistHanger, PostBase, AngleBracket,
    StructuralScrew,
)
from detailgen.assemblies import DetailAssembly


def bbox(placed):
    bb = placed.world_solid().val().BoundingBox()
    return (bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax)


def approx_bbox(a, b, tol=1e-6):
    for x, y in zip(a, b):
        assert x == pytest.approx(y, abs=tol), (a, b)


# -- datum sanity ------------------------------------------------------------

def _one_of_each():
    return [
        Lumber("2x6", 14 * IN, treated=True),
        ConcretePier(10 * IN, 54 * IN),
        Footing(2 * FT, 2 * FT, 8 * IN),
        Slab(3 * FT, 3 * FT),
        LagScrew(0.5 * IN, 4 * IN),
        StructuralScrew(0.25 * IN, 3 * IN),
        HexBolt(0.375 * IN, 2.5 * IN),
        HexNut(0.5 * IN),
        Washer(9 / 16 * IN),
        ThreadedRod(0.5 * IN, 10.75 * IN),
        Boulder(9 * IN, 12 * IN, 11 * IN, holes=[(0, 2 * IN, 0.6 * IN, 8 * IN)]),
        Epoxy(0.625 * IN, 0.5 * IN, 8 * IN),
        JoistHanger(1.5 * IN, 7.25 * IN),
        PostBase(5.5 * IN),
        AngleBracket(3 * IN, 3 * IN, 0.25 * IN, 3.5 * IN,
                     holes_base=[(0, 2.25 * IN, 0.6875 * IN)]),
    ]


def test_every_component_exposes_datums():
    for c in _one_of_each():
        d = c.datums
        assert "origin" in d, c
        assert len(d) >= 2, (c, list(d))   # origin + at least one named datum


def test_all_datum_frames_are_orthonormal():
    for c in _one_of_each():
        for name, f in c.datums.items():
            assert f.is_orthonormal(), (type(c).__name__, name)


def test_missing_datum_raises_helpful_error():
    with pytest.raises(KeyError, match="no datum"):
        HexNut(0.5 * IN).datum("nope")


# -- mate == add -------------------------------------------------------------

def test_mate_lands_where_add_would():
    """A lumber ``base`` mated onto a pier ``top`` lands exactly where the
    equivalent hand-computed add(at, rotate) puts it."""
    leg = Lumber("2x6", 14 * IN, name="leg")
    L, t = leg.length, leg.thickness

    # mate path
    d1 = DetailAssembly("mate")
    d1.add(ConcretePier(10 * IN, 54 * IN, name="pier"), at=(10, 20, 0))
    m = d1.place(Lumber("2x6", 14 * IN, name="leg"), "base").on("pier", "top")

    # hand-computed add: base-center (L/2, t/2, 0) must land at (10, 20, 0)
    d2 = DetailAssembly("add")
    a = d2.add(Lumber("2x6", 14 * IN, name="leg"),
               at=(10 - L / 2, 20 - t / 2, 0), rotate=[])

    approx_bbox(bbox(m), bbox(a))


def test_mate_by_placed_handle_and_by_name_agree():
    d = DetailAssembly("h")
    pier = d.add(ConcretePier(10 * IN, 54 * IN, name="pier"))
    by_handle = d.place(HexNut(0.5 * IN, name="n1"), "base").on(pier, "top")
    by_name = d.place(HexNut(0.5 * IN, name="n2"), "base").on("pier", "top")
    approx_bbox(bbox(by_handle), bbox(by_name))


# -- modifiers ---------------------------------------------------------------

def _seat(detail):
    detail.add(ConcretePier(10 * IN, 54 * IN, name="pier"), at=(10, 20, 0))
    return detail._resolve("pier").datum_world("top")


def test_offset_shifts_in_target_frame():
    d = DetailAssembly("off")
    seat = _seat(d)
    p = d.place(HexNut(0.5 * IN, name="n"), "base").on("pier", "top", offset=(0, 0, 5))
    expected = seat.compose(Frame.translation((0, 0, 5)))
    assert p.datum_world("base").approx_equal(expected, tol=1e-9)
    # dz opened a 5 mm standoff gap along +Z
    assert bbox(p)[2] == pytest.approx(5.0, abs=1e-6)


def test_rotate_spins_about_mate_normal():
    d = DetailAssembly("rot")
    seat = _seat(d)
    p = d.place(Lumber("2x6", 14 * IN, name="leg"), "base").on("pier", "top", rotate=90)
    expected = seat.compose(Frame.rotation(90, axis=(0, 0, 1)))
    assert p.datum_world("base").approx_equal(expected, tol=1e-9)


def test_flip_reverses_normal():
    d = DetailAssembly("flip")
    seat = _seat(d)
    p = d.place(Lumber("2x6", 14 * IN, name="leg"), "base").on("pier", "top", flip=True)
    # flip is a 180-deg turn about the seat's X axis — checked against the
    # full frame (all 3 axes), the same way offset/rotate are checked above,
    # so an implementation that flips about the wrong axis (e.g. Y instead
    # of X) can't hide behind a z_axis[2]-only check: both an X-flip and a
    # Y-flip of a (0,0,1) seat normal land on z_axis[2] == -1, but only the
    # true X-flip also reverses y_axis while leaving x_axis untouched.
    expected = seat.compose(Frame.rotation(180, axis=(1, 0, 0)))
    assert p.datum_world("base").approx_equal(expected, tol=1e-9)


def test_mate_coincides_datums_exactly():
    d = DetailAssembly("coincide")
    nut = d.add(HexNut(0.5 * IN, name="nut"), at=(3, -4, 7))
    washer = d.place(Washer(0.5 * IN, name="w"), "base").on("nut", "top")
    # washer base datum must coincide with the nut top datum in world
    assert washer.datum_world("base").approx_equal(nut.datum_world("top"), tol=1e-9)
