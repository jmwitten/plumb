"""Revision diff (INCR-3) — the five verdicts + declared renames.

Given two compiled revisions of a detail (or the composed site) — the model
*before* an edit and the model *after* it — this module says, member by member,
what the edit **persisted / moved / resized / vanished / appeared**, and reads a
declared rename as ``persisted (renamed)`` rather than a coincidental
vanish+appear. It is the third INCR piece and stands entirely on the two merged
below it (incr-design.md §3, §6 item 2, §10.3):

- **INCR-1** (:mod:`detailgen.spec.identity`) — the authored-id bridge. Identity
  keys on the **authored** spec id (``beam_pY``, ``joist_0``), which is stable
  under insertion, NOT the build-order ``Placed.id`` (``lumber-0``…), which
  renumbers (incr-design Finding 1/2). On the composed site a ``bind:``-merged
  member is one node under a **canonical** id plus retired aliases; the diff keys
  on the canonical id, so an aliased member is counted once, never twice.
- **INCR-2** (:mod:`detailgen.incremental.identity_fingerprint`) — the per-member
  comparison signature, ``{transform, content}``, both pre-rounded to the 1e-6 mm
  grid so a last-ULP float difference cannot register as a change (retro R17). Its
  :func:`~detailgen.incremental.identity_fingerprint.compare_present` reads *moved*
  (transform changed, content equal) apart from *resized* (content changed) for a
  member present in both revisions.

The verdicts, keyed on authored id (incr-design §3.2 table):

===========  ==========================================================
persisted    id in both revisions, whole signature equal
moved        id in both, transform changed, content equal
resized      id in both, content changed
vanished     id in the OLD revision, not the NEW
appeared     id in the NEW revision, not the OLD
===========  ==========================================================

**Rename is declared, never detected** (incr-design §3.2, §8 non-goal "no fuzzy
matching"). A member that re-keys ``old_id -> new_id`` would otherwise read as
``vanished(old_id) + appeared(new_id)``. Declaring ``was: <old_id>`` on the new
member (the surface INCR-3 added to :class:`~detailgen.spec.schema.ComponentSpec`)
maps the old identity forward, so the pair reads as one *persisted* (or *moved* /
*resized*) member with ``renamed[new_id] = old_id`` recording the trail. A
``was:`` that points at an id **still present** in the new revision, or one that
**never existed** in the old, is a teaching error — the compiler refuses to record
a rename the revisions contradict.

**Findings** carry no authored id (incr-design Finding 3), so they are keyed on
their id-free content signature ``(check, subject)`` and classified
persisted/changed/vanished/appeared, with ``(passed, detail, verdict)`` the
comparable content (a PASS→FAIL flip is the *same* finding, now *changed*). Two
findings that share ``(check, subject)`` in one revision are a **loud error** (P1
collision policy) — the diff refuses to guess which matches its counterpart.
Empirically vacuous on today's corpus; enforced so an ambiguity never resolves
silently. Derived/prose facts are deliberately NOT a separate identity axis: the
design computes identity over the source facts (authored declarations + geometry +
validation findings) and treats derived prose as a downstream *consequence*,
reported by a later consumer, never itself an identity signal (incr-design §3.4).

The output (:class:`RevisionDiff`) is a plain, JSON-serializable data object
(:meth:`RevisionDiff.to_dict`) — changed-authored-id sets by verdict — for the
INCR-4 affected-region computation to seed on. This module computes **no** region,
wires **no** consumer, and changes **no** baseline (design §10.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..spec.compiler import SpecCompileError
from ..spec.identity import AuthoredIdentity
from ..spec.schema import ComponentSpec, RepeatSpec
from .identity_fingerprint import MemberSignature, compare_present, member_signature


class RevisionDiffError(SpecCompileError):
    """A revision pair that cannot be diffed coherently — a ``was:`` rename the
    revisions contradict, or two findings sharing a ``(check, subject)`` signature
    in one revision (P1 collision). Names the offending ids and the fix, like every
    spec diagnostic."""


# A finding's identity signature (id-free) and its comparable content.
FindingSig = tuple[str, str]              # (check, subject)
_FindingContent = tuple[bool, str, str]   # (passed, detail, verdict)


@dataclass(frozen=True)
class MemberDiff:
    """The five-verdict member classification, keyed on authored id. ``persisted``
    / ``moved`` / ``resized`` hold the member's CURRENT (new-revision) id;
    ``vanished`` holds the OLD id it had; ``appeared`` holds the new id. ``renamed``
    maps ``new_id -> old_id`` for each declared rename — every renamed id also
    appears in exactly one of persisted/moved/resized (a rename is an identity
    move, orthogonal to whether the member also physically changed)."""

    persisted: tuple[str, ...]
    moved: tuple[str, ...]
    resized: tuple[str, ...]
    vanished: tuple[str, ...]
    appeared: tuple[str, ...]
    renamed: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "persisted": list(self.persisted),
            "moved": list(self.moved),
            "resized": list(self.resized),
            "vanished": list(self.vanished),
            "appeared": list(self.appeared),
            "renamed": dict(sorted(self.renamed.items())),
        }


@dataclass(frozen=True)
class FindingDiff:
    """The finding classification, keyed on the ``(check, subject)`` signature.
    Each bucket holds ``(check, subject)`` pairs. ``changed`` is a finding present
    in both revisions whose ``(passed, detail, verdict)`` content differs — most
    importantly a PASS→FAIL (or FAIL→PASS) flip: the same finding, now with a
    different verdict."""

    persisted: tuple[FindingSig, ...]
    changed: tuple[FindingSig, ...]
    vanished: tuple[FindingSig, ...]
    appeared: tuple[FindingSig, ...]

    def to_dict(self) -> dict:
        return {
            "persisted": [list(s) for s in self.persisted],
            "changed": [list(s) for s in self.changed],
            "vanished": [list(s) for s in self.vanished],
            "appeared": [list(s) for s in self.appeared],
        }


@dataclass(frozen=True)
class RevisionDiff:
    """The whole revision diff: member verdicts + finding verdicts. A plain data
    object; :meth:`to_dict` is JSON-serializable and :meth:`changed_authored_ids`
    is the seed set the INCR-4 affected-region computation walks the evidence graph
    from."""

    members: MemberDiff
    findings: FindingDiff

    def to_dict(self) -> dict:
        return {"members": self.members.to_dict(),
                "findings": self.findings.to_dict()}

    def changed_authored_ids(self) -> frozenset[str]:
        """The authored ids an edit physically touched — ``moved ∪ resized ∪
        vanished ∪ appeared``. A **persisted** member (including a pure rename with
        no geometry change) contributes nothing: nothing about it changed for the
        region to invalidate. Vanished ids are old-revision ids (resolved against
        the OLD graph by INCR-4); moved/resized/appeared are new-revision ids."""
        m = self.members
        return frozenset(m.moved) | frozenset(m.resized) \
            | frozenset(m.vanished) | frozenset(m.appeared)


# --------------------------------------------------------------------------- #
# Member side
# --------------------------------------------------------------------------- #
def _signatures_by_authored_id(detail) -> dict[str, MemberSignature]:
    """Every built part's comparison signature, keyed on its CANONICAL authored id
    (INCR-1). Aliases collapse onto the canonical member, so a ``bind:``-merged
    site member is one entry, not several. A part no declaration names (empty on
    today's corpus) has no insertion-stable key and is skipped — it cannot be
    diffed by identity, only by its unstable build-order id, which the design
    forbids as an identity key."""
    ident = AuthoredIdentity(detail)
    out: dict[str, MemberSignature] = {}
    for placed in detail.assembly.parts:
        aid = ident.try_authored_id_of(placed)
        if aid is not None:
            out[aid] = member_signature(placed)
    return out


def _rename_map(new_detail, old_ids: frozenset[str],
                new_ids: frozenset[str]) -> dict[str, str]:
    """Read the declared renames from the NEW revision's ``was:`` surface into a
    ``{old_id -> new_id}`` map, validating each against the design's teaching
    errors (incr-design §3.2). Raises on any contradiction so a rename the
    revisions do not support is never recorded.

    The ``was:`` surface is a DETAIL-level declaration (on
    :class:`~detailgen.spec.schema.ComponentSpec`). A composed site document
    (:class:`~detailgen.spec.site.SiteSpecDoc`) has no top-level ``components`` and
    declares no renames of its own — a re-keyed site member is honestly a
    vanish+appear (incr-design §3.2), and qualified-id site renames are out of the
    minimal v1 surface. So a doc without ``components`` yields no renames."""
    components = getattr(new_detail.doc, "components", None)
    if components is None:
        return {}
    old_to_new: dict[str, str] = {}
    for comp in _iter_components(components):
        was = getattr(comp, "was", "")
        if not was:
            continue
        new_id = comp.id
        if new_id not in new_ids:
            # The declaring component did not build an authored member (e.g. a
            # site-qualified id or a compile that dropped it). A rename must land
            # on a real, present member.
            raise RevisionDiffError(
                f"component {new_id!r} declares was: {was!r} but {new_id!r} is not "
                f"a present authored member in the new revision; a 'was:' rename "
                f"must be declared ON the renamed member, which must exist now")
        if was not in old_ids:
            raise RevisionDiffError(
                f"component {new_id!r} declares was: {was!r}, but no member {was!r} "
                f"existed in the old revision — nothing was renamed. Point 'was:' "
                f"at the id this member ACTUALLY carried before, or drop it "
                f"(a genuinely new member has no 'was:')")
        if was in new_ids:
            raise RevisionDiffError(
                f"component {new_id!r} declares was: {was!r}, but {was!r} is STILL "
                f"a present member in the new revision — that is not a rename, it "
                f"is two members. A rename retires the old id; keep 'was:' only "
                f"when {was!r} is gone")
        if was in old_to_new:
            raise RevisionDiffError(
                f"two members claim was: {was!r} ({old_to_new[was]!r} and "
                f"{new_id!r}); an old id renames to at most one new id — one of "
                f"these 'was:' declarations is wrong")
        old_to_new[was] = new_id

    # Id-reuse collision: a rename lands on an id that ALSO named a DIFFERENT
    # member in the old revision (one now removed, so the still-present guard
    # above — which keys on the OLD id `was` — does not fire). The new id then
    # denotes two members at once: old-<target> (which the edit removed) and the
    # renamed source. A string-keyed diff cannot carry both under one id, and the
    # exactly-one-bucket invariant would break (the target would land in a verdict
    # bucket AS the rename and, un-diverted, also match itself). This is the same
    # incoherent id-reuse the SWAP shape hits (rejected above as "STILL present");
    # rejected here too, for consistency and the P1 no-silent-ambiguity mandate.
    # A target that is ITSELF renamed away (in `old_to_new`) frees its id honestly
    # and is allowed.
    for src, target in old_to_new.items():
        if target in old_ids and target not in old_to_new:
            raise RevisionDiffError(
                f"component {target!r} declares was: {src!r}, reclaiming the id "
                f"{target!r} which ALSO named a different member in the old "
                f"revision (one this edit removed). The rename would silently "
                f"displace that old {target!r} — the diff will not guess which "
                f"member the new {target!r} is. Land the rename on a fresh id, or, "
                f"if you also renamed the old {target!r}, declare THAT rename too so "
                f"{target!r} is retired explicitly (a one-edit delete-and-reuse is "
                f"ambiguous; split it across two revisions)")
    return old_to_new


def _iter_components(entries):
    """Every :class:`ComponentSpec` in a components list, descending into
    ``repeat:`` bodies. A ``was:`` inside a repeat is refused: a repeat interpolates
    a FAMILY of ids from a bound index, so a single ``was:`` cannot say which
    instance it renames (incr-design R3 — repeat-aware renaming is deferred)."""
    for entry in entries:
        if isinstance(entry, RepeatSpec):
            for body in _iter_components(entry.body):
                if getattr(body, "was", ""):
                    raise RevisionDiffError(
                        f"component {body.id!r} declares was: inside a repeat: "
                        f"block; a repeat expands a family of interpolated ids, so "
                        f"a single 'was:' cannot name which instance renamed. "
                        f"Rename repeat members by adjusting the repeat, not 'was:' "
                        f"(repeat-aware renaming is deferred, incr-design R3)")
                yield body
        elif isinstance(entry, ComponentSpec):
            yield entry


def _diff_members(old_detail, new_detail) -> MemberDiff:
    old_sig = _signatures_by_authored_id(old_detail)
    new_sig = _signatures_by_authored_id(new_detail)
    old_ids = frozenset(old_sig)
    new_ids = frozenset(new_sig)
    old_to_new = _rename_map(new_detail, old_ids, new_ids)

    persisted: list[str] = []
    moved: list[str] = []
    resized: list[str] = []
    vanished: list[str] = []
    renamed: dict[str, str] = {}
    consumed_new: set[str] = set()
    bucket = {"persisted": persisted, "moved": moved, "resized": resized}

    for oid in old_ids:
        target = old_to_new.get(oid, oid)
        if target in new_ids:
            verdict = compare_present(old_sig[oid], new_sig[target])
            bucket[verdict].append(target)
            consumed_new.add(target)
            if target != oid:
                renamed[target] = oid
        else:
            # target != oid can't reach here: _rename_map already required a
            # rename's new id to be present. So an unmatched old id is a genuine
            # vanish of its own (un-renamed) id.
            vanished.append(oid)

    appeared = [nid for nid in new_ids if nid not in consumed_new]

    return MemberDiff(
        persisted=tuple(sorted(persisted)),
        moved=tuple(sorted(moved)),
        resized=tuple(sorted(resized)),
        vanished=tuple(sorted(vanished)),
        appeared=tuple(sorted(appeared)),
        renamed=dict(sorted(renamed.items())),
    )


# --------------------------------------------------------------------------- #
# Finding side
# --------------------------------------------------------------------------- #
def _finding_content_by_sig(detail) -> dict[FindingSig, _FindingContent]:
    """Map each finding's id-free signature ``(check, subject)`` to its comparable
    content ``(passed, detail, verdict)``. A repeated signature within one revision
    is a P1 collision — a loud error, never a silent last-wins overwrite."""
    _ensure_validated(detail)
    out: dict[FindingSig, _FindingContent] = {}
    for f in detail.report.findings:
        sig: FindingSig = (f.check, f.subject)
        content: _FindingContent = (bool(f.passed), f.detail, f.verdict)
        if sig in out:
            raise RevisionDiffError(
                f"two findings share the identity signature (check={f.check!r}, "
                f"subject={f.subject!r}) in one revision; the diff will not guess "
                f"which one matches its counterpart across revisions. Make the "
                f"subject distinguish them (P1 collision policy, incr-design "
                f"Finding 3)")
        out[sig] = content
    return out


def _diff_findings(old_detail, new_detail) -> FindingDiff:
    old_f = _finding_content_by_sig(old_detail)
    new_f = _finding_content_by_sig(new_detail)
    old_sigs = frozenset(old_f)
    new_sigs = frozenset(new_f)

    persisted: list[FindingSig] = []
    changed: list[FindingSig] = []
    for sig in old_sigs & new_sigs:
        (persisted if old_f[sig] == new_f[sig] else changed).append(sig)
    vanished = list(old_sigs - new_sigs)
    appeared = list(new_sigs - old_sigs)

    return FindingDiff(
        persisted=tuple(sorted(persisted)),
        changed=tuple(sorted(changed)),
        vanished=tuple(sorted(vanished)),
        appeared=tuple(sorted(appeared)),
    )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def _ensure_validated(detail) -> None:
    """Validate the detail if it has no report yet — the diff reads findings, which
    the validation sweep produces. The model need not be CLEAN: a diff over an edit
    that introduced a failure is exactly a case the diff must handle, so failing
    findings are diffed, not rejected."""
    if getattr(detail, "report", None) is None:
        detail.validate()


def revision_diff(old_detail, new_detail) -> RevisionDiff:
    """Diff two compiled revisions of the same detail (or the composed site). Both
    are built and validated if needed (read-only; no baseline touched). Returns the
    five-verdict member classification (keyed on authored id, moved-vs-resized from
    the INCR-2 signature, declared ``was:`` renames honored) and the finding
    classification (keyed on ``(check, subject)``). See the module docstring for the
    full semantics."""
    _ensure_validated(old_detail)
    _ensure_validated(new_detail)
    return RevisionDiff(
        members=_diff_members(old_detail, new_detail),
        findings=_diff_findings(old_detail, new_detail),
    )
