"""INCR-3 — the revision diff (five verdicts + declared renames).

This is the AC1 acceptance suite (``incr-design.md`` §6, §7): on a curated set of
seeded edits against a REAL detail, the diff must produce the EXACT five-verdict
member classification, and a declared ``was:`` rename must read as ``persisted
(renamed)`` — never a coincidental vanish+appear.

The seeded edits are built by editing the compiled ``rock_anchor`` detail's spec
document in memory (``dataclasses.replace``) and recompiling — the declarative
twin of hand-editing the YAML and rebuilding. Every structural edit operates on
one SYNTHETIC INDEPENDENT LEAF (a ``lumber`` placed by the ``raw:`` escape hatch,
far from the real geometry, mated onto by nothing and referenced by no
connection). That isolation is what makes the expected sets EXACT: editing the
leaf can never move, resize, or unbuild any of the detail's 26 real members, so
they must all read ``persisted`` on every edit — the property each test asserts.

The diff reads two validated models; it does not require them CLEAN (an edit that
introduces a failing finding is exactly a case the diff must handle), so the leaf
overlapping real geometry is fine and is used deliberately to exercise a PASS→FAIL
finding flip.
"""

from __future__ import annotations

import dataclasses as dc
import json
import types

import pytest

from detailgen.spec.compiler import compile_spec
from detailgen.spec.identity import AuthoredIdentity
from detailgen.spec.loader import load_spec_file, load_spec_text
from detailgen.spec.schema import ComponentSpec, RawSpec, SpecSchemaError
from detailgen.spec.site import compile_site_file
from detailgen.validation.checks import Finding
from detailgen.incremental.revision_diff import (
    RevisionDiffError,
    _diff_members,
    _finding_content_by_sig,
    revision_diff,
)

_DETAILS = "details"
_SPEC = f"{_DETAILS}/rock_anchor.spec.yaml"

# The real detail's authored member ids — every one must read `persisted` on every
# leaf-only edit. Captured once from a plain compile.
_BASE_DOC = load_spec_file(_SPEC)
_REAL_IDS = frozenset(AuthoredIdentity(compile_spec(_BASE_DOC)).authored_ids())


def _with(components) -> object:
    return dc.replace(_BASE_DOC, components=list(components))


def _probe(**overrides) -> ComponentSpec:
    """A synthetic independent leaf: a lumber block placed by ``raw:`` far from the
    real geometry (mated onto by nothing, named by no connection). ``overrides``
    replace fields to seed each edit."""
    base = ComponentSpec(
        id="probe_block", type="lumber", name="probe_block",
        params={"nominal": "2x6", "length": "12 in", "treated": True},
        place=RawSpec(at=(1000.0, 1000.0, 1000.0)),
    )
    return dc.replace(base, **overrides)


def _base_plus(probe: ComponentSpec) -> object:
    return _with(list(_BASE_DOC.components) + [probe])


def _compile_base() -> object:
    return compile_spec(_BASE_DOC)


def _all_real_persisted(md) -> None:
    """Every real member persisted, and the probe is the ONLY thing that ever
    appears in a non-persisted bucket."""
    assert _REAL_IDS <= set(md.persisted), (
        "a real member fell out of `persisted` on a leaf-only edit — "
        "the edit was not isolated to the synthetic leaf"
    )


# --------------------------------------------------------------------------- #
# AC1 — the five verdicts, exact sets
# --------------------------------------------------------------------------- #
def test_pure_move():
    old = compile_spec(_base_plus(_probe()))
    new = compile_spec(_base_plus(_probe(place=RawSpec(at=(1200.0, 1000.0, 1000.0)))))
    md = revision_diff(old, new).members
    assert md.moved == ("probe_block",)
    assert md.resized == ()
    assert md.appeared == ()
    assert md.vanished == ()
    assert md.renamed == {}
    _all_real_persisted(md)


def test_pure_resize():
    old = compile_spec(_base_plus(_probe()))
    new = compile_spec(_base_plus(
        _probe(params={"nominal": "2x6", "length": "18 in", "treated": True})))
    md = revision_diff(old, new).members
    assert md.resized == ("probe_block",)
    assert md.moved == ()
    assert md.appeared == ()
    assert md.vanished == ()
    _all_real_persisted(md)


def test_rename_with_was_reads_persisted_not_vanish_appear():
    old = compile_spec(_base_plus(_probe()))
    new = compile_spec(_base_plus(
        _probe(id="probe_renamed", name="probe_renamed", was="probe_block")))
    md = revision_diff(old, new).members
    assert "probe_renamed" in md.persisted
    assert md.renamed == {"probe_renamed": "probe_block"}
    # The whole point: NOT a vanish+appear.
    assert md.vanished == ()
    assert md.appeared == ()
    assert md.moved == () and md.resized == ()
    _all_real_persisted(md)


def test_rename_without_was_is_honest_vanish_appear():
    old = compile_spec(_base_plus(_probe()))
    new = compile_spec(_base_plus(_probe(id="probe_renamed", name="probe_renamed")))
    md = revision_diff(old, new).members
    assert md.vanished == ("probe_block",)
    assert md.appeared == ("probe_renamed",)
    assert md.renamed == {}
    _all_real_persisted(md)


def test_add():
    old = _compile_base()
    new = compile_spec(_base_plus(_probe()))
    md = revision_diff(old, new).members
    assert md.appeared == ("probe_block",)
    assert md.moved == () and md.resized == () and md.vanished == ()
    _all_real_persisted(md)


def test_remove():
    old = compile_spec(_base_plus(_probe()))
    new = _compile_base()
    md = revision_diff(old, new).members
    assert md.vanished == ("probe_block",)
    assert md.appeared == ()
    _all_real_persisted(md)


def test_ulp_rebuild_all_persisted():
    """A rebuild with no authored change: every member persists, nothing moves,
    resizes, vanishes, or appears."""
    md = revision_diff(_compile_base(), _compile_base()).members
    assert set(md.persisted) == _REAL_IDS
    assert md.moved == () and md.resized == ()
    assert md.vanished == () and md.appeared == ()


def test_ulp_subgrid_perturbation_still_persisted():
    """A placement that differs by less than the 1e-6 mm identity grid (1e-9 in ≈
    0.025 nm) is R17 — the same member, not a moved one. The diff inherits INCR-2's
    pre-rounding, so the perturbed leaf reads `persisted`, never `moved`."""
    p_a = 1000.0
    p_b = 1000.000000001  # 1e-9 in below the grid; a genuine, distinct float
    assert p_a != p_b, "seed collapsed — pick a genuinely distinct float"
    old = compile_spec(_base_plus(_probe(place=RawSpec(at=(p_a, 1000.0, 1000.0)))))
    new = compile_spec(_base_plus(_probe(place=RawSpec(at=(p_b, 1000.0, 1000.0)))))
    md = revision_diff(old, new).members
    assert "probe_block" in md.persisted
    assert md.moved == () and md.resized == ()


# --------------------------------------------------------------------------- #
# Renames — the teaching errors (a rename the revisions contradict)
# --------------------------------------------------------------------------- #
def test_was_still_present_is_loud():
    old = compile_spec(_base_plus(_probe()))
    # `probe_block` is kept AND a second member claims was: probe_block.
    dup = _probe(id="probe_copy", name="probe_copy", was="probe_block")
    new = compile_spec(_with(list(_BASE_DOC.components) + [_probe(), dup]))
    with pytest.raises(RevisionDiffError, match="STILL"):
        revision_diff(old, new)


def test_was_never_existed_is_loud():
    old = compile_spec(_base_plus(_probe()))
    new = compile_spec(_base_plus(_probe(was="never_here")))
    with pytest.raises(RevisionDiffError, match="no member"):
        revision_diff(old, new)


def test_two_members_claim_same_was_is_loud():
    old = compile_spec(_base_plus(_probe()))
    a = _probe(id="probe_a", name="probe_a", was="probe_block")
    b = _probe(id="probe_b", name="probe_b", was="probe_block")
    new = compile_spec(_with(list(_BASE_DOC.components) + [a, b]))
    with pytest.raises(RevisionDiffError, match="renames to at most one"):
        revision_diff(old, new)


def test_was_inside_repeat_is_loud():
    """A `was:` inside a `repeat:` cannot name which interpolated instance renamed;
    the diff refuses it (repeat-aware renaming is deferred, incr-design R3)."""
    spec = (
        "name: t\n"
        "components:\n"
        "  - repeat: {var: k, count: 2}\n"
        "    body:\n"
        "      - {id: 'blk_{k}', type: lumber, name: 'blk {k}', was: old_blk,\n"
        "         params: {nominal: '2x6', length: '12 in'},\n"
        "         place: {raw: {at: ['= k*100', 0, 0]}}}\n"
    )
    old = _compile_base()
    new = compile_spec(load_spec_text(spec))
    with pytest.raises(RevisionDiffError, match="repeat"):
        revision_diff(old, new)


def test_id_reuse_rename_is_loud():
    """Id-reuse: the old revision has two members {aa, bb}; the new revision keeps
    only {aa}, whose `was: bb` renames bb onto aa's just-freed id (old aa removed).
    The still-present guard keys on the OLD id (bb, now gone) and does not fire — so
    without this guard the new `aa` would be double-classified (matched both as
    surviving-aa and as renamed-bb) and old aa would silently disappear. Because the
    string-keyed diff cannot carry `aa` denoting two members at once, this is refused
    loudly — the same incoherence the SWAP shape is already rejected for."""
    aa = _probe(id="probe_aa", name="probe_aa", place=RawSpec(at=(1000.0, 1000.0, 1000.0)))
    bb = _probe(id="probe_bb", name="probe_bb", place=RawSpec(at=(1500.0, 1000.0, 1000.0)))
    old = compile_spec(_with(list(_BASE_DOC.components) + [aa, bb]))
    # new: old `probe_aa` removed; `probe_bb` renamed onto the freed id `probe_aa`.
    reused = _probe(id="probe_aa", name="probe_aa", was="probe_bb",
                    place=RawSpec(at=(1500.0, 1000.0, 1000.0)))
    new = compile_spec(_with(list(_BASE_DOC.components) + [reused]))
    with pytest.raises(RevisionDiffError, match="reclaiming the id"):
        revision_diff(old, new)


def test_id_reuse_is_expressible_as_two_clean_revisions():
    """The honest path the guard steers toward: split the delete-and-reuse across two
    revisions. Removing old `aa` (rev1) and renaming `bb`→`aa` onto the now-free id
    (rev2) each diff unambiguously — a positive control that the constraint is
    workable, not a dead end."""
    aa = _probe(id="probe_aa", name="probe_aa", place=RawSpec(at=(1000.0, 1000.0, 1000.0)))
    bb = _probe(id="probe_bb", name="probe_bb", place=RawSpec(at=(1500.0, 1000.0, 1000.0)))
    rev1 = compile_spec(_with(list(_BASE_DOC.components) + [aa, bb]))
    rev2 = compile_spec(_with(list(_BASE_DOC.components) + [bb]))  # old aa removed
    d12 = revision_diff(rev1, rev2).members
    assert d12.vanished == ("probe_aa",)
    assert d12.appeared == () and d12.renamed == {}
    # rev3: bb renamed onto the now-free id aa.
    reused = _probe(id="probe_aa", name="probe_aa", was="probe_bb",
                    place=RawSpec(at=(1500.0, 1000.0, 1000.0)))
    rev3 = compile_spec(_with(list(_BASE_DOC.components) + [reused]))
    d23 = revision_diff(rev2, rev3).members
    assert d23.renamed == {"probe_aa": "probe_bb"}
    assert "probe_aa" in d23.persisted
    assert d23.vanished == () and d23.appeared == ()


def test_was_equals_own_id_rejected_at_load():
    """The one rename check that needs only the new revision — a member naming
    ITSELF as its prior id — is a loader teaching error (identity is kept by keeping
    the id, not by declaring `was:`)."""
    with pytest.raises(SpecSchemaError, match="DIFFERENT prior"):
        load_spec_text(
            "name: t\ncomponents:\n  - {id: a, type: lumber, name: a, was: a}\n")


# --------------------------------------------------------------------------- #
# Findings — (check, subject) identity, changed content, P1 collision
# --------------------------------------------------------------------------- #
def test_finding_flip_reads_changed_not_vanish_appear():
    """Moving the leaf into the real geometry flips its interference findings
    PASS→FAIL. Same (check, subject) signature, different content → `changed`."""
    old = compile_spec(_base_plus(_probe()))
    new = compile_spec(_base_plus(_probe(place=RawSpec(at=(0.0, 0.0, 0.0)))))
    fd = revision_diff(old, new).findings
    changed_probe = [s for s in fd.changed if "probe_block" in s[1]]
    assert changed_probe, "an interference finding on the moved leaf should flip"
    # A flipped finding is the SAME finding (still in both revisions), never a
    # vanish+appear pair.
    for sig in changed_probe:
        assert sig not in fd.vanished and sig not in fd.appeared


def test_finding_diff_is_symmetric():
    """Diffing new→old must mirror old→new: `persisted` and `changed` are the same
    set, and `vanished`/`appeared` swap. This pins the finding-diff logic to a
    string-free structural invariant (independent of which domain findings a
    particular edit happens to move)."""
    old = _compile_base()
    new = compile_spec(_base_plus(_probe()))
    fwd = revision_diff(old, new).findings
    rev = revision_diff(new, old).findings
    assert set(fwd.appeared) == set(rev.vanished)
    assert set(fwd.vanished) == set(rev.appeared)
    assert set(fwd.changed) == set(rev.changed)
    assert set(fwd.persisted) == set(rev.persisted)
    # And adding the leaf really does introduce its own interference findings.
    assert any("probe_block" in subj for _, subj in fwd.appeared)


def test_finding_signature_collision_is_loud():
    """Two findings sharing a (check, subject) signature in one revision is a P1
    collision — a loud error, never a silent last-wins overwrite. Vacuous on the
    real corpus, so it is exercised with a hand-built colliding report."""
    stub = types.SimpleNamespace(report=types.SimpleNamespace(findings=[
        Finding("interference", "a <-> b", True),
        Finding("interference", "a <-> b", False),
    ]))
    with pytest.raises(RevisionDiffError, match="share the identity signature"):
        _finding_content_by_sig(stub)


# --------------------------------------------------------------------------- #
# Output shape (for INCR-4) + site canonicalization
# --------------------------------------------------------------------------- #
def test_to_dict_is_json_serializable_and_complete():
    old = compile_spec(_base_plus(_probe()))
    new = compile_spec(_base_plus(_probe(place=RawSpec(at=(1200.0, 1000.0, 1000.0)))))
    d = revision_diff(old, new)
    blob = json.dumps(d.to_dict())          # must not raise
    round = json.loads(blob)
    assert set(round) == {"members", "findings"}
    assert set(round["members"]) == {
        "persisted", "moved", "resized", "vanished", "appeared", "renamed"}
    assert set(round["findings"]) == {
        "persisted", "changed", "vanished", "appeared"}


def test_changed_authored_ids_is_the_geometry_seed():
    # A move seeds the region on the moved id.
    old = compile_spec(_base_plus(_probe()))
    moved = compile_spec(_base_plus(_probe(place=RawSpec(at=(1200.0, 1000.0, 1000.0)))))
    assert revision_diff(old, moved).changed_authored_ids() == {"probe_block"}
    # A PURE rename physically changed nothing → it seeds NOTHING (persisted).
    ren = compile_spec(_base_plus(
        _probe(id="probe_renamed", name="probe_renamed", was="probe_block")))
    assert revision_diff(old, ren).changed_authored_ids() == frozenset()


def test_site_aliases_are_not_double_counted():
    """On the composed site a `bind:`-merged member is ONE node under several
    qualified ids; the diff keys on the CANONICAL id (INCR-1), so an identity
    rebuild reads every member once — persisted count == canonical-id count, and
    nothing spuriously vanishes or appears. (Member diff only; it needs `build`,
    not the site's O(n²) validation sweep.)"""
    s1 = compile_site_file(f"{_DETAILS}/site.spec.yaml")
    s2 = compile_site_file(f"{_DETAILS}/site.spec.yaml")
    canonical = frozenset(AuthoredIdentity(s1).authored_ids())
    md = _diff_members(s1, s2)
    assert set(md.persisted) == canonical
    assert len(md.persisted) == len(s1.assembly.parts)  # one entry per built node
    assert md.moved == () and md.resized == ()
    assert md.vanished == () and md.appeared == ()
