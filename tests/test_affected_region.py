"""INCR-4 — the affected region (AC3 region-size + AC4 cross-detail isolation).

The heart of this suite is **soundness** (the brief's one non-negotiable, design §9
R2 / AC2): for a curated set of seeded edits against the real platform, the affected
region computed from INCR-3's diff must CONTAIN every part and every finding a
whole-world recompile would show changed. An under-claim — a changed finding left
outside the region — is a defect, so :func:`test_region_is_sound_against_whole_world`
is the load-bearing gate: it recompiles the whole model, diffs it by identity, and
asserts the region is a superset of the actual change. Over-claim is not gated (Q4 —
measured, not failed); :func:`test_single_member_region_is_a_small_fraction` records
the AC3 size metric instead.

Seeded edits ride the compiler's ``overrides=`` param family — the declarative twin
of editing the YAML and rebuilding — so each is a real recompile the diff reads, not
a synthetic construction. ``beam_len`` is the deliberate floor case: extending the
deck run flips two findings the evidence graph carries no ``concerns`` edge for
(``faces_away`` and ``support``), which the region can only catch through the
unattributed-findings floor — proven load-bearing in
:func:`test_floor_is_load_bearing`.
"""

from __future__ import annotations

import dataclasses as dc
import json

import pytest

from detailgen.spec.compiler import compile_spec, compile_spec_file
from detailgen.spec.identity import AuthoredIdentity
from detailgen.spec.loader import load_spec_file
from detailgen.spec.site import compile_site_file
from detailgen.validation import evidence as _ev
from detailgen.validation.evidence import EvidenceGraph
from detailgen.incremental.affected_region import (
    AffectedRegion,
    affected_region,
    edit_region,
)
from detailgen.incremental.revision_diff import revision_diff

_PLATFORM = "details/platform.spec.yaml"
_SITE = "details/site.spec.yaml"


def _platform(overrides=None):
    d = compile_spec_file(_PLATFORM, overrides=overrides)
    d.validate()
    return d


def _platform_one_sided():
    """Move beam -Y alone — its Y placement down 0.5", +Y untouched (the reviewer's
    asymmetric edit). Breaks the beam pair's mirror symmetry on ONE side, so the +Y
    twin is not co-seeded: the ``symmetric_about`` finding is reachable only through
    beam -Y's own ``concerns`` edge — the edge the ``about <plane>`` fix restores. A
    bilaterally symmetric edit (every param knob in the matrix below) can never expose
    this, because it always co-seeds the +Y twin."""
    doc = load_spec_file(_PLATFORM)
    comps = []
    for c in doc.components:
        if getattr(c, "id", None) == "beam_mY":
            at = list(c.place.at)
            assert at[1] == "= -outer_y", f"beam_mY Y placement moved: {at[1]!r}"
            at[1] = "= -outer_y - 0.5"
            c = dc.replace(c, place=dc.replace(c.place, at=tuple(at)))
        comps.append(c)
    d = compile_spec(dc.replace(doc, components=comps))
    d.validate()
    return d


# Compiled once — the unedited baseline every seeded edit diffs against.
_BASE = _platform()
_BASE_IDS = frozenset(AuthoredIdentity(_BASE).authored_ids())


def _direct_changed_findings(old, new):
    """The findings a whole-world recompile shows changed, computed DIRECTLY from the
    two validation reports — ``(check, subject)`` whose ``(passed, detail)`` differs,
    appeared, or vanished. Independent of ``revision_diff`` (the reviewer's rigor: the
    soundness gate must not be checked only through the very diff that seeds the
    region)."""
    def content(d):
        return {(f.check, f.subject): (bool(f.passed), f.detail)
                for f in d.report.findings}
    o, n = content(old), content(new)
    return {k for k in set(o) | set(n) if o.get(k) != n.get(k)}


def _actual_changed(diff):
    """The whole-world change a diff reports, as the two soundness sets: changed
    findings (by signature) and changed parts (by authored id)."""
    f = diff.findings
    findings = set(f.changed) | set(f.vanished) | set(f.appeared)
    m = diff.members
    parts = set(m.moved) | set(m.resized) | set(m.vanished) | set(m.appeared)
    return findings, parts


# --------------------------------------------------------------------------- #
# SOUNDNESS — the region contains every actual change (no missed line)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("overrides", [
    {"beam_len": 52.0},   # extends the deck run — the floor case (faces_away/support)
    {"bolt_dia": 0.5},    # fattens every leg-to-beam bolt — 36 bearing findings flip
    {"rail_height": 40.0},
    {"leg_gap": 1.0},
    {"n_steps": 3},       # adds a ladder rung + hardware — appeared members
    {"n_steps": 1},       # drops a rung + hardware — vanished members (old-graph seed)
])
def test_region_is_sound_against_whole_world(overrides):
    new = _platform(overrides)
    diff = revision_diff(_BASE, new)
    region = edit_region(_BASE, new, diff)

    # Findings: checked against the DIRECT whole-world diff (not via revision_diff).
    missed_findings = _direct_changed_findings(_BASE, new) - region.findings
    assert not missed_findings, f"UNSOUND: findings changed but outside region: {sorted(missed_findings)}"
    # Parts: every part the diff shows changed must be in the region.
    _, actual_parts = _actual_changed(diff)
    missed_parts = actual_parts - region.parts
    assert not missed_parts, f"UNSOUND: parts changed but outside region: {sorted(missed_parts)}"


def test_region_is_sound_for_a_one_sided_symmetric_edit():
    """The regression the review found: moving ONE side of a symmetric pair flips its
    ``symmetric_about`` verdict, and pre-fix that finding was attributed only to the
    +Y operand (the parser dropped ``beam -Y about XZ`` on the ``about <plane>``
    suffix), so a -Y-only edit escaped the region. Checked against the direct
    whole-world diff; the specific missed finding is now inside the region, and only
    beam -Y seeded it (the +Y twin did not change)."""
    new = _platform_one_sided()
    changed = _direct_changed_findings(_BASE, new)
    region = edit_region(_BASE, new)

    assert not (changed - region.findings), \
        f"UNSOUND (one-sided): {sorted(changed - region.findings)}"
    sym = ("symmetric_about", "beam +Y <-> beam -Y about XZ")
    assert sym in changed, "the one-sided move should flip the beam symmetry finding"
    assert sym in region.findings, "the flipped symmetry finding must be in the region"
    assert "beam_mY" in region.seeds and "beam_pY" not in region.seeds


def test_vanished_member_region_comes_from_the_old_graph():
    """A vanished member no longer exists in the new model, so its consequences can
    only be walked in the graph where it still existed. ``edit_region`` unions the
    old-graph region for the vanished ids — without which the removal's region would
    be silently empty (an under-claim)."""
    new = _platform({"n_steps": 1})
    diff = revision_diff(_BASE, new)
    assert diff.members.vanished, "expected the dropped rung + hardware to vanish"
    region = edit_region(_BASE, new, diff)
    assert set(diff.members.vanished) <= region.parts


# --------------------------------------------------------------------------- #
# AC3 — region-size metric
# --------------------------------------------------------------------------- #
def test_single_member_region_is_a_small_fraction():
    """A single-member edit's region is a small fraction of the model — the AC3 /
    AD#6.4 metric. Measured on the platform: the beam seeds ~35 revisit-neighbour
    parts and ~180 findings against 10,719 (≈1.7%). A region == whole model for a
    local edit would be a soundness bug surfacing as a size."""
    r = affected_region(_BASE, ["beam_pY"])
    m = r.metrics()
    assert m["seeds"] == 1
    assert 0 < m["findings"] < m["total_findings"]          # not the whole model
    assert m["finding_fraction"] < 0.05                     # a small fraction
    assert 0 < m["neighbors"] < 60                          # a bounded revisit set
    # some of the model is genuinely outside the region (soundness-as-size)
    assert _BASE_IDS - r.parts


def test_region_size_grows_with_the_edit_but_stays_bounded():
    """A broader edit (fatten every bolt) yields a larger region than a single beam,
    yet still under the whole model — the sweep it turns all-pairs into is
    touched-pairs, not no-op."""
    one = affected_region(_BASE, ["beam_pY"]).metrics()["findings"]
    new = _platform({"bolt_dia": 0.5})
    many = edit_region(_BASE, new).metrics()["findings"]
    assert one < many < 10_719


# --------------------------------------------------------------------------- #
# AC4 — cross-detail isolation
# --------------------------------------------------------------------------- #
def test_platform_edit_leaves_rock_anchor_region_empty():
    """A platform-only edit on the composed site yields a region empty of every
    other detail's ids — ``rock_anchor`` untouched, asserted exactly (the STRUCT
    lesson, design §5). This is what lets INCR-5 leave ``rock_anchor.json``
    unregenerated for a beam nudge."""
    site = compile_site_file(_SITE)
    site.validate()
    ident = AuthoredIdentity(site)
    rock = frozenset(a for a in ident.authored_ids() if a.startswith("rock_anchor/"))
    assert rock, "site must compose rock_anchor for this to mean anything"

    r = affected_region(site, ["platform/beam_pY"])
    assert r.parts.isdisjoint(rock)
    foreign = {a for a in r.parts if "/" in a and not a.startswith("platform/")}
    assert foreign == set(), f"platform edit leaked into other subsystems: {sorted(foreign)}"


def test_site_alias_seed_resolves_to_the_canonical_region():
    """A ``bind:``-merged site member is ONE node under a canonical id plus retired
    aliases. Seeding by an alias (``tree/beam_mY``) is the canonical node's region
    (``platform/beam_mY``) — identical parts and findings, and the reported seed is
    the canonical id, not the alias (no alias leakage, no missed propagation)."""
    site = compile_site_file(_SITE)
    site.validate()
    ident = AuthoredIdentity(site)
    canonical = "platform/beam_mY"
    aliases = ident.aliases_of(canonical)
    assert len(aliases) > 1, "expected a bound member with a retired alias"
    alias = aliases[1]

    r_can = affected_region(site, [canonical])
    r_ali = affected_region(site, [alias])
    assert r_ali.parts == r_can.parts
    assert r_ali.findings == r_can.findings
    assert r_can.seeds == r_ali.seeds == frozenset({canonical})


# --------------------------------------------------------------------------- #
# The unattributed-findings floor
# --------------------------------------------------------------------------- #
def test_floor_is_load_bearing():
    """Extending the deck run flips two findings the evidence graph carries no
    ``concerns`` edge for — a ``faces_away`` and a ``support`` finding. No changed
    part can reach them by any edge, so they are in the region ONLY via the floor;
    without it they would be a silent under-claim. Proven here by asserting the two
    changed findings are exactly the floor (unattributed) subset."""
    new = _platform({"beam_len": 52.0})
    diff = revision_diff(_BASE, new)
    region = edit_region(_BASE, new, diff)

    changed, _ = _actual_changed(diff)
    changed_via_floor = {s for s in changed if s in region.unattributed_findings}
    assert any(check == "faces_away" for check, _ in changed_via_floor)
    assert any(check == "support" for check, _ in changed_via_floor)
    # and everything in the floor subset is genuinely inside the region
    assert changed_via_floor <= region.findings


def test_floor_included_when_seed_nonempty_and_excluded_when_empty():
    """The floor is the sound safety net: every unattributed finding is revisited
    whenever the edit is non-empty, and none when it is empty. On the platform the
    floor is 45 — the 16 through-hole probes, the 14 toe-screw ``connection_hardware``
    findings whose ``A <-> B (type): hardware`` subject names three parts the parser
    cannot cleanly split (so it attributes none, all-or-nothing), the 3
    ``foundation_attachment`` + 3 ``foundation_capacity`` findings whose ``post ->
    block`` subject likewise names two parts (FAB-3; the embedment findings, named
    for their single block, DO attribute), the 6 CL-2 ``clearance`` findings whose
    ``deck N clears trunk …`` subject is a prose sentence the graph does not parse
    into a part link (so it joins the floor and is never missed — exactly the
    subject-shape-agnostic net this design promises), one each of the global
    no-floaters, faces-away, and walking-surface checks — and, since task
    INSTALL v1, the platform's 164 installability AXIS findings, floored
    DELIBERATELY: their verdicts depend on a geometric neighborhood (shank
    members, entry face, corridor blockers) that their fastener-naming
    subject cannot carry, so attributing them to the fastener alone would be
    the exact partial-attribution soundness hole this net closes (see
    EvidenceGraph._link_finding)."""
    r = affected_region(_BASE, ["beam_pY"])
    assert r.unattributed_findings <= r.findings
    assert len(r.unattributed_findings) == 45 + 164
    checks = {check for check, _ in r.unattributed_findings}
    assert checks == {"through_hole", "connection_hardware", "floating",
                      "faces_away", "support", "clearance",
                      "foundation_attachment", "foundation_capacity",
                      "install_termination", "install_access"}

    empty = affected_region(_BASE, [])
    assert empty.unattributed_findings == frozenset()
    assert empty.findings == frozenset()


def test_no_finding_is_partially_attributed():
    """Class-closer for the partial-attribution defect (the review's root cause): a
    finding whose subject the graph resolves to FEWER parts than it names is neither
    fully edge-attributed nor in the zero-attribution floor, so a change to a dropped
    operand escapes a region seeded elsewhere. Walk every finding in all four details
    and the composed site and assert the invariant that forecloses the class: a
    finding is EITHER in the floor (no ``concerns`` edge) OR every candidate operand
    token its subject yields resolves to a real part (whole attribution, never
    partial). A future check whose subject shape leaves an operand unresolved fails
    here loudly; the honest fallback for an unparseable subject is the floor."""
    names = ("platform", "rock_anchor", "tree_attachment", "trolley_launch")
    models = [compile_spec_file(f"details/{n}.spec.yaml") for n in names]
    models.append(compile_site_file(_SITE))
    for d in models:
        d.validate()
        g = EvidenceGraph.from_detail(d)
        name_to_id = _ev._name_to_id(d.assembly)
        for n in g.nodes_of_kind("finding"):
            subject = n.attrs["subject"]
            tokens = _ev._subject_name_tokens(subject)
            unresolved = [t for t in tokens if name_to_id.get(t) is None]
            in_floor = not any(e.kind == "concerns" for e in g.edges_from(n.id))
            assert not unresolved or in_floor, (
                f"PARTIAL ATTRIBUTION in {d}: finding {subject!r} yields "
                f"unresolved operand(s) {unresolved} but has concerns edges (not in "
                f"the floor) — a change to the dropped operand would escape the "
                f"region. Attribute every operand, or route the shape to the floor.")


# --------------------------------------------------------------------------- #
# Empty / persisted-only edits + output shape
# --------------------------------------------------------------------------- #
def test_empty_seed_is_an_empty_region():
    r = affected_region(_BASE, [])
    assert r.is_empty
    assert r.parts == frozenset()
    assert r.findings == frozenset()
    assert r.facts == frozenset()
    assert r.declarations == frozenset()


def test_persisted_only_edit_seeds_nothing():
    """A no-op rebuild changes no authored id, so the diff's seed is empty and the
    region is empty — nothing to revisit. (A pure rename is the same shape: it
    persists, so it seeds nothing — checked at the diff level in INCR-3.)"""
    new = _platform()
    diff = revision_diff(_BASE, new)
    assert diff.changed_authored_ids() == frozenset()
    region = edit_region(_BASE, new, diff)
    assert region.is_empty


def test_seed_absent_from_model_is_skipped_not_an_error():
    """A seed id that names no member of this model is silently skipped (the
    cross-graph case, where a vanished id is resolved against the other revision),
    never a hard error."""
    r = affected_region(_BASE, ["no_such_member_xyz"])
    assert r.is_empty


def test_to_dict_is_json_serializable_and_shaped():
    r = affected_region(_BASE, ["beam_pY"])
    blob = json.dumps(r.to_dict())          # must not raise
    d = json.loads(blob)
    assert set(d) == {
        "seeds", "parts", "declarations", "facts", "findings",
        "unattributed_findings", "total_findings", "metrics",
    }
    assert all(len(sig) == 2 for sig in d["findings"])
    assert d["metrics"]["findings"] == len(d["findings"])


def test_region_is_deterministic_across_builds():
    a = affected_region(_platform(), ["beam_pY"])
    b = affected_region(_platform(), ["beam_pY"])
    assert a.to_dict() == b.to_dict()
