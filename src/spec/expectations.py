"""EXPECT — the derivation of pin accounting from declaration-attached
expectations (CL-3, cl0-design.md §3.4; retro R7/R12/R19/R20).

An ``expect:`` rides on the connection it concerns (schema
:class:`~detailgen.spec.schema.ExpectSpec`), never in a global side-file
divorced from its subject. From those attachments this module DERIVES the two
things the design promises:

- **the pin-accounting REPORT** (:func:`classify`) — the pinned-finding set,
  grouped by the OWNING declaration, with each pin's justification inline. This
  is the ``site_divergence.json`` accounting made *derived* from where each pin
  is attached, not maintained by hand in a separate file (the R12 ownership-drift
  / 24-vs-20 miscount class).
- **the classification GATE** — every live FAILURE is partitioned into
  ``expected`` (a pin covers it), ``new`` (no pin covers it — it blocks CLEAN),
  and the pins into ``orphans`` (a pin whose declared count the joint cannot
  fill). An orphan is a teaching error (:func:`require_no_orphans`).

**Coverage is SUBJECT-PRECISE and COUNT-BOUNDED** (the CL-3 fix-round tightening,
review-cl3.md §4 — the round-1 mechanism over-covered per-kind-per-joint, silently
absorbing every same-kind finding on the joint, which hid genuinely-new failures).
A pin covers a live failure only when BOTH hold:

1. **internal subject** — every part the failure's subject names is one of the
   owning connection's OWN parts/hardware (or the failure is the joint's own
   ``connection_hardware`` line). A failure that pulls in a foreign part is NEVER
   absorbed — it surfaces as NEW.
2. **within count** — the pin declares how many same-kind findings it owns
   (``count``, default 1). Among the joint's internal same-kind failures, the
   pins of that kind cover exactly their summed ``count``; ANY same-kind internal
   failure beyond that budget is NEW and surfaces loudly (the safe direction —
   one more divergence than declared is unexplained). A budget the joint cannot
   fill (fewer such failures than declared) leaves an ORPHAN.

This recovers the exact-set discipline the old ``site_divergence.json`` had (a new
same-kind failure was a set mismatch = a reviewed new pin) on the attached form:
the pinned set is exactly what the pins enumerate, never "every same-kind finding."
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

_SEP = " <-> "


class ExpectationError(ValueError):
    """A declaration-attached expectation problem, in the teaching style — an
    ORPHAN pin (its declared ``count`` exceeds the divergences that actually fire,
    so it references divergences that no longer exist) names itself and how to fix
    it."""


@dataclass(frozen=True)
class Pin:
    """One derived pin: the ``check`` it expects, its justification ``reason``,
    the ``owner`` connection label, how many same-kind findings it owns
    (``count``), and ``owner_names`` — the joint's own part/hardware display
    names, used to decide whether a failure's subject is INTERNAL to this joint."""

    check: str
    reason: str
    owner: str
    count: int = 1
    owner_names: frozenset = field(default_factory=frozenset)

    def owns_subject(self, subject: str) -> bool:
        """True when ``subject`` is internal to this joint: its own
        ``connection_hardware`` line (``"<label>: <part>"``) or a contact whose
        every named member is one of the joint's own parts/hardware."""
        if subject.startswith(f"{self.owner}:"):
            return True
        parts = subject.split(_SEP)
        return len(parts) >= 2 and all(p in self.owner_names for p in parts)


@dataclass(frozen=True)
class PinAccounting:
    """The derived pin-accounting report. ``expected`` are the pinned (covered)
    failures — ``(check, subject, owner, reason)``; ``new`` are the uncovered
    failures ``(check, subject)`` that block CLEAN; ``orphans`` are the unfilled
    pin budgets ``(owner, check, reason)``."""

    expected: tuple
    new: tuple
    orphans: tuple

    def grouped(self) -> dict:
        """The pinned failures grouped by owning connection label — the
        ``site_divergence.json`` partition, DERIVED from attachment."""
        out: dict[str, list] = {}
        for check, subject, owner, reason in self.expected:
            out.setdefault(owner, []).append((check, subject, reason))
        return out


def pins_from_detail(detail) -> list[Pin]:
    """Every pin a compiled detail carries — one per ``expect:`` on a
    NON-RETIRED connection. Retired connections are already absent from
    ``detail.connections()`` (their closure, pins included, unwound), so this
    reads the built connections and re-attaches each one's spec ``expect:`` by
    label — proving the pin retires WITH its owner (no orphans left behind)."""
    expects_by_label = _spec_expects_by_label(detail.doc)
    pins: list[Pin] = []
    for conn in detail.connections():
        expects = expects_by_label.get(conn.label)
        if not expects:
            continue
        owner_names = frozenset(p.name for p in (*conn.parts, *conn.hardware))
        for e in expects:
            pins.append(Pin(check=e.check, reason=e.reason, owner=conn.label,
                            count=e.count, owner_names=owner_names))
    return pins


def classify(failures, pins) -> PinAccounting:
    """Partition ``failures`` (an iterable of ``(check, subject)``) against
    ``pins`` with SUBJECT-PRECISE, COUNT-BOUNDED coverage. Deterministic."""
    failures = list(failures)
    groups: dict[tuple, list] = defaultdict(list)   # (owner, check) -> [Pin]
    for p in pins:
        groups[(p.owner, p.check)].append(p)

    covered: set[int] = set()
    expected: list = []
    orphans: list = []
    for (owner, check), gpins in sorted(groups.items()):
        onames: frozenset = frozenset().union(*(p.owner_names for p in gpins))
        probe = Pin(check, "", owner, owner_names=onames)
        # internal same-kind failures this joint owns, deterministically ordered.
        cands = sorted(
            (i for i, (c, s) in enumerate(failures)
             if c == check and i not in covered and probe.owns_subject(s)),
            key=lambda i: failures[i][1])
        # the reasons this group budgets, one slot per declared count.
        slots = [p.reason for p in gpins for _ in range(p.count)]
        take = cands[:len(slots)]
        for slot_reason, i in zip(slots, take):
            covered.add(i)
            expected.append((failures[i][0], failures[i][1], owner, slot_reason))
        # a budget the joint could not fill -> orphan slots (pins outliving their
        # divergence). One orphan row per unfilled slot's reason.
        for slot_reason in slots[len(take):]:
            orphans.append((owner, check, slot_reason))

    new = [failures[i] for i in range(len(failures)) if i not in covered]
    return PinAccounting(
        expected=tuple(sorted(expected)),
        new=tuple(sorted(new)),
        orphans=tuple(sorted(orphans)),
    )


def require_no_orphans(accounting: PinAccounting) -> None:
    """Raise a teaching :class:`ExpectationError` if any pin budget went unfilled
    (§3.4 field 3). An orphan pin declared more same-kind divergences than
    actually fire — retire the pin (or lower its ``count``), or fix the
    declaration so the expected finding occurs. Called by the site/detail gate so
    an orphan can never sit silently green."""
    if not accounting.orphans:
        return
    listed = "; ".join(
        f"{owner!r} expects a {check!r} divergence ({reason})"
        for owner, check, reason in accounting.orphans)
    raise ExpectationError(
        f"{len(accounting.orphans)} orphan expectation(s): {listed}. Each declares "
        f"a same-kind divergence that does NOT fire — the pin has outlived what it "
        f"described. Remove the expect: (the divergence was resolved), lower its "
        f"'count', or fix the declaration so the expected finding actually occurs. "
        f"A pin can never sit green over a divergence that no longer exists.")


def detail_pin_accounting(detail) -> PinAccounting:
    """The whole EXPECT derivation for one compiled detail: build the pins from
    its attached expectations, run the live report through the classifier."""
    report = detail.validate()
    failures = [(f.check, f.subject) for f in report.failures]
    return classify(failures, pins_from_detail(detail))


# -- internals ---------------------------------------------------------------
def _spec_expects_by_label(doc) -> dict:
    """label -> tuple[ExpectSpec] for every connection spec carrying expects
    (recursing repeats). A retired connection's expects are still read here but
    its built connection is absent, so they never produce a pin — they retire
    with the joint."""
    from .schema import ConnectionSpec, RepeatSpec

    out: dict[str, tuple] = {}

    def walk(entries):
        for e in entries:
            if isinstance(e, ConnectionSpec):
                if e.expect and e.label:
                    out[e.label] = e.expect
            elif isinstance(e, RepeatSpec):
                walk(e.body)

    walk(doc.connections)
    return out
