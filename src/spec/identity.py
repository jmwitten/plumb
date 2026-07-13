"""INCR-1 (incr-design.md §2 Finding 2, §6 item 1): the authored-id bridge.

The compiler already threads the FORWARD map — a spec-local authored id
(``beam_pY``, ``joist_0``) to the built :class:`~detailgen.assemblies.assembly.Placed`
it produced — as ``SpecDetail._by_id`` (compiler.py) and its public reader
``_resolve_part``. This module adds the REVERSE direction and the evidence-graph
bridge that INCR-1 owns:

    authored id  <->  Placed  <->  evidence-graph ``part:`` node

so a built part is addressable by its **insertion-stable authored id** rather
than the build-order ``Placed.id`` (``lumber-0``, ``lumber-1``…), which renumbers
whenever a part is inserted earlier in build order (incr-design Finding 1). The
authored id survives insertion and reordering, which is exactly why revision
identity keys on it.

Nothing here mutates ``Placed.id``, the evidence graph, or any baseline. It only
reads ``_by_id`` and derives the graph part-node id via the same key the graph
itself uses (``evidence._part_nid``), replicated as the pure function
:func:`graph_part_nid` so this module imports no validation logic (INCR-1 touches
no validation).

**Ambiguity is a loud teaching error, never a guess (P1).** Two distinct
declarations that collapse onto one built node — without the site's declared
``bind:``/``dedup:`` retirement to say which is the real member — raise rather
than resolve arbitrarily. A built part that no declaration names gets an explicit
"no authored id" answer (:class:`NoAuthoredId`), never a fabricated one.

Site semantics (incr-design "composed site"): a ``bind:``-merged or ``dedup:``-ed
member is ONE node addressed by several qualified ids — the real member's id plus
the retired stub/context-copy ids (site.py). The **canonical** identity is the
real member (the one id NOT retired); the retired ids are recorded as aliases and
round-trip *to* the canonical. So ``platform/leg_pY`` wins over its stub
``rock_anchor/leg`` and its context restatement ``trolley/far_post``.
"""

from __future__ import annotations

import difflib
from collections import defaultdict

from .compiler import SpecCompileError


def graph_part_nid(placed_id: str) -> str:
    """The evidence-graph part-node id for a ``Placed.id`` — byte-identical to
    ``detailgen.validation.evidence._part_nid``, replicated here as a pure key
    derivation so the bridge needs no import from the validation layer. Idempotent
    on an already-prefixed id."""
    return placed_id if placed_id.startswith("part:") else f"part:{placed_id}"


class SpecIdentityError(SpecCompileError):
    """A built model whose authored ids cannot be bridged coherently — two live
    declarations collapsed onto one node without a declared retirement (P1
    ambiguity). Names the offending ids and the fix, like every spec diagnostic."""


class NoAuthoredId(KeyError):
    """A built :class:`Placed` that no spec declaration names — the explicit
    "no authored id" answer for a part synthesized outside a declaration. Carries
    the part's ``Placed.id`` so the caller can still report it by its build-order
    handle. (Empirically vacuous on today's corpus: every platform and site part
    is authored — but the honest answer exists rather than a fabricated id.)"""

    def __str__(self) -> str:  # a bare KeyError repr-wraps its message in quotes
        return self.args[0] if self.args else super().__str__()


class AuthoredIdentity:
    """The read-only authored-id bridge over one already-compiled detail or site.

    Built once from ``detail._by_id`` (forward) + ``detail._retired_ids()`` (which
    ids are aliases for another member's identity). Exposes the reverse map and
    the round-trip ``authored id -> Placed -> graph node -> authored id`` the
    revision-identity layer stands on. All lookups are O(1); construction is
    O(parts) and raises on any P1 ambiguity so an unsound bridge never silently
    exists.
    """

    def __init__(self, detail):
        detail.build()
        forward = dict(detail._by_id)  # authored id -> Placed
        retired = frozenset(detail._retired_ids())

        by_placed: dict[object, list[str]] = defaultdict(list)
        for aid, placed in forward.items():
            by_placed[placed].append(aid)

        canonical: dict[object, str] = {}      # Placed -> its one canonical id
        aliases: dict[object, tuple] = {}      # Placed -> (canonical, *retired aliases)
        for placed, ids in by_placed.items():
            live = [a for a in ids if a not in retired]
            if len(live) == 1:
                (only,) = live
            elif not live:
                # A node reachable only through retired aliases: a retirement
                # resolves to a REAL member, which carries its own live id, so
                # this cannot happen for a coherent site. Loud rather than a guess.
                raise SpecIdentityError(
                    f"built part {placed.id!r} is addressed only by retired ids "
                    f"{sorted(ids)} and has no canonical (non-retired) authored "
                    f"id; a bind:/dedup: retirement must resolve to a REAL member "
                    f"that carries its own id (site.py) — this model retired every "
                    f"id that names the part")
            else:
                # Two+ live declarations on one built node with NO declared
                # bind:/dedup: to say which is the real member — the silent
                # single-node merge the identity layer must never resolve by
                # guessing (P1). Only a declared retirement makes a shared node
                # honest.
                raise SpecIdentityError(
                    f"built part {placed.id!r} is named by {len(live)} independent "
                    f"live declarations {sorted(live)} with no bind:/dedup: to "
                    f"declare which is the real member; the authored-id bridge "
                    f"will not choose one by guessing. Retire the stub/context "
                    f"copies with 'bind:'/'dedup:' (site.py) so exactly one id is "
                    f"canonical")
            canonical[placed] = only
            aliases[placed] = (only,) + tuple(a for a in ids if a != only)

        self._forward = forward
        self._canonical = canonical
        self._aliases = aliases
        # graph part-node id -> canonical authored id (the reverse bridge)
        self._by_nid = {
            graph_part_nid(placed.id): aid for placed, aid in canonical.items()
        }
        # Every built part, and those a declaration never named (verify: none today).
        self._parts = list(detail.assembly.parts)
        self._unbridged = [p for p in self._parts if p not in canonical]

    # -- forward (authored id -> ...) -----------------------------------------

    def authored_ids(self) -> list[str]:
        """Every canonical authored id, sorted — one per built part (retired
        aliases excluded; query :meth:`aliases_of` for those)."""
        return sorted(self._canonical.values())

    def placed_of(self, authored_id: str):
        """The :class:`Placed` an authored id names — canonical OR a retired
        alias (an alias resolves to the same real member, by identity). Loud
        teaching error (did-you-mean) on an unknown id."""
        try:
            return self._forward[authored_id]
        except KeyError:
            raise self._unknown_id(authored_id) from None

    def graph_nid_of(self, authored_id: str) -> str:
        """The evidence-graph ``part:`` node id for an authored id (canonical or
        alias). Aliases share the real member's node — that is the single-node
        guarantee."""
        return graph_part_nid(self.placed_of(authored_id).id)

    # -- reverse (Placed / graph node -> authored id) -------------------------

    def authored_id_of(self, placed) -> str:
        """The canonical authored id of a built :class:`Placed`. Raises
        :class:`NoAuthoredId` (naming the part's build-order id) if no declaration
        names it — the explicit "no authored id" answer, never a fabricated one."""
        try:
            return self._canonical[placed]
        except KeyError:
            raise NoAuthoredId(
                f"built part {getattr(placed, 'id', placed)!r} has no authored id "
                f"— it was synthesized outside any spec declaration, so it has no "
                f"insertion-stable identity key (its build-order Placed.id is the "
                f"only handle it carries)") from None

    def try_authored_id_of(self, placed) -> str | None:
        """Non-raising :meth:`authored_id_of`: the canonical id, or ``None`` for a
        part no declaration names."""
        return self._canonical.get(placed)

    def authored_id_of_graph_nid(self, nid: str) -> str:
        """The canonical authored id for an evidence-graph part node id (``part:…``
        or a bare ``Placed.id``). Loud teaching error on an unknown node — the
        node must be a ``part`` node in this model's graph."""
        key = graph_part_nid(nid)
        try:
            return self._by_nid[key]
        except KeyError:
            known = sorted(self._by_nid)
            hint = difflib.get_close_matches(key, known, n=3)
            tip = f" — did you mean one of {hint}?" if hint else ""
            raise SpecIdentityError(
                f"evidence-graph node {nid!r} (part key {key!r}) is not a bridged "
                f"part node in this model{tip}; only 'part:' nodes for authored "
                f"members are addressable by authored id (findings/facts/"
                f"declarations key on content, not authored id — incr-design "
                f"Finding 3)") from None

    # -- aliases / coverage ---------------------------------------------------

    def aliases_of(self, authored_id: str) -> tuple:
        """Every authored id addressing the same built node as ``authored_id``,
        canonical first (``(canonical, *retired)``). A member with no alias
        returns a 1-tuple of itself."""
        return self._aliases[self.placed_of(authored_id)]

    def reverse_by_id(self) -> dict:
        """The reverse of ``detail._by_id``: ``{Placed: canonical authored id}``.
        The stable reverse accessor that pairs with the forward ``_by_id`` — one
        entry per built part, retired aliases collapsed onto the real member."""
        return dict(self._canonical)

    def parts_without_authored_id(self) -> list:
        """Built parts no declaration names (each an explicit "no authored id").
        Empty on today's corpus; the honest surface exists so a future synthesized
        part is reported, not fabricated an id."""
        return list(self._unbridged)

    def _unknown_id(self, authored_id: str) -> SpecIdentityError:
        known = sorted(self._forward)
        hint = difflib.get_close_matches(str(authored_id), known, n=3)
        tip = f" — did you mean one of {hint}?" if hint else ""
        return SpecIdentityError(
            f"unknown authored id {authored_id!r}{tip}; an authored id is a "
            f"spec-local component id (or, in a site, a '<subsystem>/<id>' "
            f"qualified id, including a retired stub/dedup alias)")


def authored_identity(detail) -> AuthoredIdentity:
    """Build the :class:`AuthoredIdentity` bridge for a compiled detail or site.
    Convenience entry point; equivalent to ``AuthoredIdentity(detail)``."""
    return AuthoredIdentity(detail)
