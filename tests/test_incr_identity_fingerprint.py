"""INCR-2 — identity comparison fingerprint.

Proves the design's member-level guarantees (``incr-design.md`` §3.3–3.4):

* **AC5 — R17 immunity.** A *genuinely* ULP-different-but-arithmetically-equal
  rebuild — the ``(a+b)*IN`` vs ``a*IN+b*IN`` class, on the transform, on
  ``length_mm``, and on a nested ``holes`` coordinate — produces an IDENTICAL
  signature (``persisted``, never ``moved``/``resized``). The seeds are guarded
  to be real ULP differences, not no-ops.
* **move vs resize** is distinguished because the transform and content
  components are kept separate.
* Byte-stability of every existing surface is preserved by construction (this
  suite adds only new files and imports neither ``baseline_lib`` mechanics into,
  nor out of, the identity module); the full-suite run is the proof.
"""

from __future__ import annotations

import pytest

from detailgen.incremental.identity_fingerprint import (
    MemberSignature,
    _EXCLUDED_FACT_ATTRS,
    _canon,
    _content_component,
    _round6,
    compare_present,
    detail_signatures,
    member_signature,
)
from detailgen.assemblies.assembly import Placed
from detailgen.components.lumber import Lumber
from detailgen.components.railing import DeckBoard
from detailgen.core.frame import Frame

IN = 25.4

# A guarded genuine-ULP pair: (A+B)*IN and A*IN+B*IN are arithmetically equal
# but land on different floats (the retro-R17 42.25" class). Every AC5 test
# feeds a value built these two ways and asserts the signature does not split.
_A, _B = 0.1, 42.25


def _two_ulp_values() -> tuple[float, float]:
    x = (_A + _B) * IN
    y = _A * IN + _B * IN
    return x, y


# --------------------------------------------------------------------------- #
# The seed is real (no-op guard)
# --------------------------------------------------------------------------- #
def test_seed_is_a_genuine_ulp_difference():
    x, y = _two_ulp_values()
    assert x != y, "seed collapsed to a no-op — pick a genuinely ULP-different pair"
    assert abs(x - y) < 1e-6, "seed must be below the 1e-6 mm grid to model R17"


# --------------------------------------------------------------------------- #
# Rounding + canonicalization primitives
# --------------------------------------------------------------------------- #
def test_round6_folds_negative_zero():
    assert _round6(-0.0) == "0.000000"
    assert _round6(-0.0) == _round6(0.0)


def test_round6_absorbs_the_ulp_seed():
    x, y = _two_ulp_values()
    assert _round6(x) == _round6(y)


def test_canon_type_tags_prevent_scalar_collision():
    # int 1, float 1.0, str "1", bool True must all serialize distinctly.
    assert len({_canon(1), _canon(1.0), _canon("1"), _canon(True)}) == 4


def test_canon_rounds_floats_at_any_depth():
    x, y = _two_ulp_values()
    assert _canon({"holes": [[x, 1.0], [2.0, x]]}) == \
        _canon({"holes": [[y, 1.0], [2.0, y]]})


# --------------------------------------------------------------------------- #
# Fixtures — lightweight real members (no geometry is built)
# --------------------------------------------------------------------------- #
def _placed(component, origin=(0.0, 0.0, 0.0), pid="m-0") -> Placed:
    return Placed(component, Frame.translation(tuple(float(c) for c in origin)),
                  at=tuple(float(c) for c in origin), rotate=[], id=pid)


# --------------------------------------------------------------------------- #
# AC5 — R17 immunity on each raw-float surface
# --------------------------------------------------------------------------- #
def test_transform_ulp_immunity():
    x, y = _two_ulp_values()
    a = _placed(Lumber("2x6", 1524.0), origin=(x, 0.0, 0.0))
    b = _placed(Lumber("2x6", 1524.0), origin=(y, 0.0, 0.0))
    sig_a, sig_b = member_signature(a), member_signature(b)
    assert sig_a.transform == sig_b.transform
    assert sig_a == sig_b
    assert compare_present(sig_a, sig_b) == "persisted"


def test_length_mm_ulp_immunity():
    # The watch item: content_fingerprint emits length_mm RAW, so this exact
    # ULP-different cut length would flip that hash; the identity content
    # component rounds it, so it does not split.
    x, y = _two_ulp_values()
    assert x != y
    a = _placed(Lumber("2x6", x))
    b = _placed(Lumber("2x6", y))
    assert a.component.bom_length_mm() != b.component.bom_length_mm()  # raw differ
    sig_a, sig_b = member_signature(a), member_signature(b)
    assert sig_a.content == sig_b.content
    assert compare_present(sig_a, sig_b) == "persisted"


def test_nested_holes_ulp_immunity():
    x, y = _two_ulp_values()
    a = _placed(Lumber("2x6", 1524.0, holes=[(x, 69.85, 10.033)]))
    b = _placed(Lumber("2x6", 1524.0, holes=[(y, 69.85, 10.033)]))
    assert a.component.holes != b.component.holes  # raw nested floats differ
    assert member_signature(a).content == member_signature(b).content


# --------------------------------------------------------------------------- #
# Move vs resize separation
# --------------------------------------------------------------------------- #
def test_move_is_transform_only():
    lum = Lumber("2x6", 1524.0)
    a = _placed(lum, origin=(0.0, 0.0, 0.0))
    b = _placed(lum, origin=(100.0, 0.0, 0.0))  # 100 mm >> 1e-6 grid
    sig_a, sig_b = member_signature(a), member_signature(b)
    assert sig_a.content == sig_b.content
    assert sig_a.transform != sig_b.transform
    assert compare_present(sig_a, sig_b) == "moved"


def test_resize_is_content_change():
    a = _placed(Lumber("2x6", 1524.0))
    b = _placed(Lumber("2x6", 1829.0))  # length changed → resized
    sig_a, sig_b = member_signature(a), member_signature(b)
    assert sig_a.transform == sig_b.transform
    assert sig_a.content != sig_b.content
    assert compare_present(sig_a, sig_b) == "resized"


def test_resize_wins_when_both_change():
    a = _placed(Lumber("2x6", 1524.0), origin=(0.0, 0.0, 0.0))
    b = _placed(Lumber("2x6", 1829.0), origin=(100.0, 0.0, 0.0))
    assert compare_present(member_signature(a), member_signature(b)) == "resized"


def test_nominal_change_is_content():
    a = _placed(Lumber("2x6", 1524.0))
    b = _placed(Lumber("2x8", 1524.0))
    assert member_signature(a).content != member_signature(b).content


# --------------------------------------------------------------------------- #
# Enumeration completeness — underscore-prefixed identity facts (the review
# blocker: params() drops these, so they were invisible to the signature).
# --------------------------------------------------------------------------- #
def test_full_length_change_is_content():
    # Lumber._full_length drives stub_of() → the BOM stub_of row, which
    # content_fingerprint hashes; it is underscore-prefixed so params() drops
    # it. Two stubs of the SAME modeled length but different continuous runs
    # (63.5" vs 78.7") must NOT read as persisted.
    a = _placed(Lumber("2x6", 1524.0, full_length=1613.0))
    b = _placed(Lumber("2x6", 1524.0, full_length=2000.0))
    assert compare_present(member_signature(a), member_signature(b)) == "resized"
    # a stub vs a non-stub of equal modeled length is also a content change
    non_stub = _placed(Lumber("2x6", 1524.0, full_length=None))
    assert compare_present(member_signature(a), member_signature(non_stub)) == "resized"


def test_trunk_cut_change_is_content():
    # DeckBoard._trunk_cut cuts the real solid (cache_key folds it in) and is
    # underscore-prefixed. Notched vs unnotched, and two notch positions, are
    # different geometry — content changes, never persisted.
    plain = _placed(DeckBoard(1524.0, trunk_cut=None))
    notched = _placed(DeckBoard(1524.0, trunk_cut=(100.0, 50.0, 60.0)))
    moved_notch = _placed(DeckBoard(1524.0, trunk_cut=(200.0, 50.0, 60.0)))
    assert compare_present(member_signature(plain), member_signature(notched)) == "resized"
    assert compare_present(member_signature(notched), member_signature(moved_notch)) == "resized"


def test_display_name_change_is_persisted():
    # Identity is name-independent (design §3.2); content_fingerprint / cache_key
    # / bom_group all exclude the display name, so the signature must too — a
    # pure rename is persisted, not resized.
    a = _placed(Lumber("2x6", 1524.0, name="beam +Y"))
    b = _placed(Lumber("2x6", 1524.0, name="a completely different label"))
    assert compare_present(member_signature(a), member_signature(b)) == "persisted"


def test_building_the_solid_cache_does_not_change_the_signature():
    # _solid (the memoized cadquery geometry) is excluded: computing it must not
    # move the signature, and no cadquery object may leak into the content.
    lum = Lumber("2x6", 1524.0)
    p = _placed(lum)
    before = member_signature(p)
    _ = lum.solid  # force-build → populates vars()['_solid'] with a Workplane
    after = member_signature(p)
    assert before == after
    assert "object at 0x" not in after.content


# --------------------------------------------------------------------------- #
# THE class-closing guard: over the WHOLE corpus, every float-bearing member
# fact — public or underscore, at any nesting depth — must influence the
# content signature. If a future component adds a float attribute that
# content_fingerprint reacts to but the signature does not, this fails. This
# closes the enumeration class, not just the two known instances.
# --------------------------------------------------------------------------- #
_BUMP = 1000.0  # >> the 1e-6 mm grid, so a rounded change is guaranteed


def _bump_floats(v):
    """Return ``v`` with every float leaf increased by ``_BUMP``; ``None`` if
    ``v`` contains no float leaf at all (bool is not a float here)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, float):
        return v + _BUMP
    if isinstance(v, (list, tuple)):
        parts = [_bump_floats(x) for x in v]
        if all(p is None for p in parts):
            return None
        merged = [p if p is not None else orig for p, orig in zip(parts, v)]
        return type(v)(merged)
    return None


@pytest.fixture(scope="module")
def corpus_parts():
    from detailgen.spec.compiler import compile_spec
    from detailgen.spec.loader import load_spec_file
    from detailgen.spec.site import compile_site_file
    from pathlib import Path
    d = Path(__file__).resolve().parents[1] / "details"
    parts = []
    for n in ("platform", "rock_anchor", "tree_attachment", "trolley_launch"):
        det = compile_spec(load_spec_file(d / f"{n}.spec.yaml"))
        det.validate()
        parts.extend(det.assembly.parts)
    site = compile_site_file(d / "site.spec.yaml")
    site.validate()
    parts.extend(site.assembly.parts)
    return parts


def test_no_float_member_fact_is_invisible_to_signature(corpus_parts):
    checked_attrs: set[tuple[str, str]] = set()
    for p in corpus_parts:
        c = p.component
        base = _content_component(p)
        for k, v in list(vars(c).items()):
            if k in _EXCLUDED_FACT_ATTRS:
                continue
            bumped = _bump_floats(v)
            if bumped is None:
                continue  # no float leaf under this attribute
            setattr(c, k, bumped)
            try:
                assert _content_component(p) != base, (
                    f"{type(c).__name__}.{k} carries a float member fact that is "
                    f"INVISIBLE to the identity signature — content_fingerprint "
                    f"would move but the diff would say 'persisted' (silent stale "
                    f"golden). Fold it into the content signature.")
            finally:
                setattr(c, k, v)
            checked_attrs.add((type(c).__name__, k))
    # sanity: the sweep actually ran, and it covered the two underscore facts
    # the review flagged (proves the guard exercises the real blind spot).
    assert checked_attrs, "guard swept no float facts — fixture or bump broke"
    assert ("Lumber", "_full_length") in checked_attrs
    assert ("DeckBoard", "_trunk_cut") in checked_attrs


def test_no_cache_object_leaks_into_any_corpus_signature(corpus_parts):
    for p in corpus_parts:
        sig = member_signature(p)
        assert "object at 0x" not in sig.content
        assert "object at 0x" not in sig.transform


def test_material_change_is_content():
    a = _placed(Lumber("2x6", 1524.0, treated=False))
    b = _placed(Lumber("2x6", 1524.0, treated=True))  # material_key + material flip
    assert member_signature(a).content != member_signature(b).content


def test_signature_is_hashable_and_digest_is_stable():
    sig = member_signature(_placed(Lumber("2x6", 1524.0)))
    assert isinstance(sig, MemberSignature)
    assert sig.digest() == member_signature(_placed(Lumber("2x6", 1524.0))).digest()
    _ = {sig}  # frozen dataclass → hashable


# --------------------------------------------------------------------------- #
# On the real platform detail
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def platform():
    from detailgen.spec.compiler import compile_spec
    from detailgen.spec.loader import load_spec_file
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    det = compile_spec(load_spec_file(repo / "details" / "platform.spec.yaml"))
    det.validate()
    return det


def test_detail_signatures_cover_every_part(platform):
    sigs = detail_signatures(platform)
    assert set(sigs) == {p.id for p in platform.assembly.parts}
    assert len(sigs) == len(platform.assembly.parts)


def test_detail_compared_to_itself_is_all_persisted(platform):
    before = detail_signatures(platform)
    after = detail_signatures(platform)
    assert before == after
    assert all(compare_present(before[k], after[k]) == "persisted" for k in before)
