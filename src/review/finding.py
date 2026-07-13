"""The :class:`VisualReviewFinding` model — one adversarial visual suspicion as a
first-class, always-valid value.

Shape follows the owner directive (visual-review-directive.md, "required
fields"): subject, suspected issue, severity, visual evidence (which render +
what was seen), possible violated invariant family, recommended next action, and
a resolution status that is exactly one of the resolution outcomes — or the
legal, persistent ``unresolved`` state.

Validation lives in ``__post_init__`` so a finding can NEVER exist in an invalid
state, whichever path builds it (the store loader or a direct call). The
messages are in this codebase's teaching style — what was wrong plus what is
valid / an example — the same contract the spec loaders keep
(:class:`detailgen.spec.schema.SpecSchemaError`); we mirror that style rather
than import their private helpers, keeping this subsystem's ownership disjoint.

BINDING: a finding is a SUSPICION, never proof (directive). The model records a
*possible* violated invariant family and a *recommended* action; it asserts no
verdict and can flip none. Resolution into "new formal invariant" / "existing
invariant covers it" is where a suspicion becomes (or defers to) real, compiler
enforced truth — this model only tracks that that resolution happened.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field, replace


class ReviewSchemaError(ValueError):
    """A structural or vocabulary problem in a visual-review finding: an unknown
    severity/family/resolution value, a missing required field, or a resolution
    that omits its required evidence. Message is in the teaching style (what was
    wrong + what is valid / an example)."""


#: Severity vocabulary, most-to-least urgent. A visual smell test grades how
#: alarming the *appearance* is, not structural capacity — the label never
#: certifies anything, it only ranks suspicions for triage.
SEVERITIES: tuple[str, ...] = ("CRITICAL", "HIGH", "MEDIUM", "LOW")

#: The legal, persistent open state. A finding sits here until a reviewer
#: resolves it into one of the four outcomes; it NEVER silently expires
#: (directive: "Unresolved suspicions are open work items").
UNRESOLVED = "unresolved"

#: A suspicion that was a REAL defect and has been removed by REVISING THE DESIGN
#: (a spec revision). Distinct from ``documented-assumption-or-unknown`` (the
#: appearance is accepted / intentional, nothing changed) and from
#: ``dismissed-false-positive`` (it was never a defect): here the defect was real
#: and the model changed so it no longer exists. It names the mechanism the
#: compiler already models — a revision — and a finding closes ON that revision,
#: per the vocabulary-gap directive ("the finding closes on the revision"). Like
#: every resolved state its note is REQUIRED; the note must cite the revision that
#: fixed it (the commit / the changed spec).
FIXED_BY_REVISION = "fixed-by-revision"

#: A finding's resolution status is exactly one of these. ``unresolved`` is the
#: legal, persistent open state; the next four are the directive's invariant-framed
#: outcomes; ``fixed-by-revision`` is the design-change outcome — added when the
#: first real design fix (caddy D1) had no honest home among the invariant-framed
#: four (it was neither a new/covering invariant, nor an accepted assumption, nor a
#: false positive — the design was revised to remove a real defect).
RESOLUTION_STATES: tuple[str, ...] = (
    UNRESOLVED,
    "new-formal-invariant",           # discovered a MISSING invariant — the point
    "covered-by-existing-invariant",  # an existing compiler invariant already flags it
    "documented-assumption-or-unknown",  # intentional / out of scope / honestly UNKNOWN
    "dismissed-false-positive",       # not a real issue — REQUIRES evidence
    FIXED_BY_REVISION,                # real defect, removed by a design revision
)

#: The one resolution that CANNOT be asserted on the reviewer's word alone: a
#: dismissal must carry the evidence that the suspicion is not a real issue,
#: else a real defect is closed by fiat (the exact failure a smell test guards
#: against). Enforced in :meth:`Resolution.__post_init__`.
_DISMISSED = "dismissed-false-positive"

#: Sentinel family value: the suspicion may not map to ANY existing invariant
#: family — a candidate for a NEW one. This is the discovery case the directive
#: prizes ("Its value is DISCOVERING MISSING INVARIANTS"), kept legal and
#: explicit rather than forced into an ill-fitting family.
UNKNOWN_FAMILY = "UNKNOWN"


def known_invariant_families() -> tuple[str, ...]:
    """The canonical invariant-family names a finding's ``invariant_family`` is
    validated against, read LIVE from the validation subsystem
    (:data:`detailgen.validation.coverage.INVARIANT_FAMILIES`) so this subsystem
    never keeps a second, drifting copy of that list — and so a family the
    SUPPORT work adds is picked up automatically. Read-only: VISREV never edits
    the validation package."""
    from detailgen.validation.coverage import INVARIANT_FAMILIES

    return tuple(INVARIANT_FAMILIES)


@dataclass(frozen=True)
class RenderRef:
    """A content-addressed pointer to ONE render this finding reviewed.

    ``path`` is repo-root-relative (the same key the review manifest uses), so a
    finding and the manifest name the same file the same way. ``content_hash``
    is the SHA-256 of the render's bytes AT REVIEW TIME: it is what makes
    staleness detectable — when the build regenerates that render, the manifest's
    hash changes and the mismatch is surfaced as "render changed since review",
    never silently ignored.

    ``content_hash`` is optional. A finding filed before a manifest existed (the
    seeded interim findings) references renders by path with no captured hash;
    that is honestly reported as "staleness unverifiable — no hash captured",
    NOT treated as current. A reviewer filing against a live manifest should
    always capture the hash."""

    path: str
    content_hash: str | None = None

    def __post_init__(self):
        if not isinstance(self.path, str) or not self.path.strip():
            raise ReviewSchemaError(
                "RenderRef: 'path' must be a non-empty repo-root-relative render "
                "path (e.g. 'outputs/consolidated/renders/platform/platform_front.png'), "
                f"got {self.path!r}"
            )
        if self.content_hash is not None and (
            not isinstance(self.content_hash, str) or not self.content_hash.strip()
        ):
            raise ReviewSchemaError(
                f"RenderRef {self.path!r}: 'content_hash' must be a non-empty hex "
                "SHA-256 string or omitted entirely (omitted = hash not captured, "
                f"staleness unverifiable), got {self.content_hash!r}"
            )


@dataclass(frozen=True)
class Resolution:
    """A finding's resolution: one of :data:`RESOLUTION_STATES` plus a note.

    The note is REQUIRED for every resolved state (a resolution with no words is
    not a resolution — it must name the new invariant, the covering invariant,
    the documented assumption, or the dismissal evidence). ``dismissed-false-
    positive`` carries the sharpest requirement: its note IS the evidence that
    the suspicion is not a real issue, and its absence is a teaching error — a
    reviewer may not dismiss a suspicion on their word alone."""

    status: str = UNRESOLVED
    note: str = ""

    def __post_init__(self):
        if self.status not in RESOLUTION_STATES:
            hint = difflib.get_close_matches(str(self.status), RESOLUTION_STATES, n=2)
            tip = f" — did you mean one of {hint}?" if hint else ""
            raise ReviewSchemaError(
                f"resolution status {self.status!r} is not one of "
                f"{list(RESOLUTION_STATES)}{tip}. '{UNRESOLVED}' is the legal open "
                "state; the other four are the outcomes a suspicion resolves into."
            )
        note = (self.note or "").strip()
        if self.status == _DISMISSED and not note:
            raise ReviewSchemaError(
                f"resolution '{_DISMISSED}' REQUIRES evidence: set 'note' to the "
                "evidence that this visual suspicion is NOT a real issue (e.g. the "
                "invariant/measurement that proves it, or why the appearance is "
                "intended). A visual smell test may not be dismissed on assertion "
                "alone."
            )
        if self.status != UNRESOLVED and not note:
            raise ReviewSchemaError(
                f"resolution {self.status!r} REQUIRES a 'note' saying HOW it "
                "resolves — name the new/covering invariant, the documented "
                "assumption, or the dismissal evidence. Only "
                f"'{UNRESOLVED}' may have an empty note."
            )

    @property
    def is_open(self) -> bool:
        return self.status == UNRESOLVED


@dataclass(frozen=True)
class VisualReviewFinding:
    """One adversarial visual suspicion about a rendered image.

    All fields but ``notes`` are required and non-empty. ``invariant_family`` is
    validated against :func:`known_invariant_families` plus the explicit
    :data:`UNKNOWN_FAMILY` sentinel. ``renders`` is the content-addressed set of
    images the suspicion is grounded in (used for staleness). A finding is
    immutable; :meth:`resolved_as` returns a new finding with an updated
    resolution."""

    id: str
    subject: str
    suspected_issue: str
    severity: str
    #: Free text: WHAT was seen in the render(s) that raised the suspicion.
    visual_evidence: str
    #: The specific render(s) reviewed, content-addressed (see :class:`RenderRef`).
    renders: tuple[RenderRef, ...]
    #: A known invariant family or :data:`UNKNOWN_FAMILY` — the *possible* family
    #: this suspicion belongs to. Possible, never asserted.
    invariant_family: str
    recommended_action: str
    resolution: Resolution = field(default_factory=Resolution)
    #: Optional context that is NOT a resolution — e.g. "KNOWN, in-fix on branch
    #: sdd/struct". A known-in-fix suspicion is still OPEN until formally
    #: resolved; this field records the context without pretending it is closed.
    notes: str = ""

    _REQUIRED_TEXT = (
        ("id", "a short stable id (e.g. 'F1')"),
        ("subject", "what the finding is about (e.g. 'platform support at grade')"),
        ("suspected_issue", "the suspicion in one or two sentences"),
        ("visual_evidence", "what was seen in the render(s)"),
        ("recommended_action", "the recommended next action"),
    )

    def __post_init__(self):
        for name, example in self._REQUIRED_TEXT:
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ReviewSchemaError(
                    f"VisualReviewFinding: '{name}' is required and must be a "
                    f"non-empty string — {example}; got {value!r}"
                )
        if self.severity not in SEVERITIES:
            hint = difflib.get_close_matches(str(self.severity), SEVERITIES, n=2)
            tip = f" — did you mean one of {hint}?" if hint else ""
            raise ReviewSchemaError(
                f"finding {self.id!r}: severity {self.severity!r} is not one of "
                f"{list(SEVERITIES)}{tip}"
            )
        families = known_invariant_families()
        if self.invariant_family not in families and self.invariant_family != UNKNOWN_FAMILY:
            hint = difflib.get_close_matches(str(self.invariant_family),
                                             list(families), n=2)
            tip = f" — did you mean one of {hint}?" if hint else ""
            raise ReviewSchemaError(
                f"finding {self.id!r}: invariant_family {self.invariant_family!r} "
                f"is not a known family {list(families)}{tip}. Use one of those, or "
                f"'{UNKNOWN_FAMILY}' if the suspicion may need a NEW family (the "
                "discovery case — an honest UNKNOWN, not a forced fit)."
            )
        if not isinstance(self.renders, tuple) or not self.renders:
            raise ReviewSchemaError(
                f"finding {self.id!r}: 'renders' must list at least one RenderRef — "
                "a visual suspicion with no render it was seen in can't be reviewed "
                "for staleness or pointed at."
            )
        for r in self.renders:
            if not isinstance(r, RenderRef):
                raise ReviewSchemaError(
                    f"finding {self.id!r}: every 'renders' entry must be a RenderRef, "
                    f"got {type(r).__name__}"
                )
        if not isinstance(self.resolution, Resolution):
            raise ReviewSchemaError(
                f"finding {self.id!r}: 'resolution' must be a Resolution, got "
                f"{type(self.resolution).__name__}"
            )

    @property
    def is_open(self) -> bool:
        """True while the suspicion is unresolved (open work that never expires)."""
        return self.resolution.is_open

    def resolved_as(self, status: str, note: str = "") -> "VisualReviewFinding":
        """Return a copy with a new resolution (validated by :class:`Resolution`)."""
        return replace(self, resolution=Resolution(status=status, note=note))
