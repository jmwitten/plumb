"""Construction ONTOLOGY seed (Wave 3, task ONTOLOGY, P5).

The platform is becoming "a semantic construction compiler that happens to emit
construction details". This module is the first small vocabulary of *what parts
mean structurally* — separate from the geometry (a solid) and the Construction
Graph (how solids connect). Three concepts, deliberately coarse:

- **Role** — what a part *is for* in the load system: ``support`` (a member
  that carries load down toward the ground), ``connector`` (a member/hardware
  that passes load from one member to the next), ``ground`` (the terminal
  Support — the earth, a boulder, a footing — where a load path ends). The
  wider construction vocabulary (``barrier``, ``access``, ``surface``) is
  RESERVED: named and documented, but not yet provable, so declaring one is a
  teaching error, not a silent no-op.
- **LoadClass** — a coarse *kind of load*, with NO direction yet:
  ``downward_load`` is the one class this task can actually prove a path for.
  ``lateral_push`` (the guard-rail case that motivates the live defect),
  ``pull_out``, ``uplift``, ``shear`` are RESERVED — knowable, claimable as
  transfer data, but not yet the subject of a reachability proof.
- **TransferCapability** — a provenance-tagged claim, attached to a
  :class:`~detailgen.assemblies.connection.ConnectionType`, that a joint of
  that class *transfers* or *does_not_transfer* a given LoadClass. This is the
  reusable knowledge the load-path proof stands on. Every claim carries a
  ``confidence``, a ``source_type`` (the KNOWLEDGE-STRATEGY tier) and an honest
  ``reference`` string — never an invented official citation.

Binding honesty rules (WAVE 3 SHAPE, user directive):

- The system may say a load path **is REPRESENTED** — a typed graph path from a
  support to ground exists. It must NEVER say a member is "safe"/"adequate":
  structural capacity is a different, UNKNOWN family. Nothing here does capacity
  math; there are no numbers in a Role or a LoadPath.
- Semantics are committed **one real bug at a time**. A term only leaves the
  RESERVED set when a check can actually prove or disprove something about it.
  Today that is ``downward_load`` over ``support``/``connector``/``ground``.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass


class OntologyError(ValueError):
    """A reserved-but-not-yet-provable term, or a truly unknown one, was used
    where the ontology expected a currently-provable term. The message teaches:
    it names what IS currently provable (for a reserved term) or offers a
    did-you-mean (for an unknown one) — never a bare KeyError."""


class Vocabulary:
    """A small, closed construction vocabulary in three tiers.

    - **provable** — terms an active check can currently prove/disprove
      something about (the committed semantics).
    - **reserved** — terms that are named and DOCUMENTED as future ontology
      vocabulary but carry no proof yet; using one where a provable term is
      required is a *teaching* error ("reserved … not yet provable; currently
      provable: …"), which is the point — it says "known, but the platform
      can't stand behind it yet", not "unknown".
    - everything else is genuinely **unknown** (a typo or an out-of-vocabulary
      word) and gets a did-you-mean.

    ``require`` gates a term that must be provable NOW (e.g. the load class a
    reachability proof runs over). ``require_known`` gates a term that only has
    to be real vocabulary (e.g. the load class a transfer *claim* is about — a
    hanger may honestly claim it does_not_transfer ``lateral_push`` even though
    no lateral proof exists yet)."""

    def __init__(self, kind: str, provable, reserved):
        self.kind = kind
        self.provable: tuple[str, ...] = tuple(provable)
        self.reserved: tuple[str, ...] = tuple(reserved)
        overlap = set(self.provable) & set(self.reserved)
        if overlap:
            raise ValueError(
                f"{kind}: {sorted(overlap)} are in both provable and reserved")

    @property
    def known(self) -> frozenset[str]:
        return frozenset(self.provable) | frozenset(self.reserved)

    def is_provable(self, name: str) -> bool:
        return name in self.provable

    def require(self, name: str) -> str:
        """Return ``name`` iff it is currently PROVABLE; else raise a teaching
        :class:`OntologyError`. A reserved term names what is provable today; an
        unknown term gets a did-you-mean."""
        if name in self.provable:
            return name
        if name in self.reserved:
            raise OntologyError(
                f"{self.kind} {name!r} is reserved for the construction "
                f"ontology, not yet provable; currently provable: "
                f"{', '.join(self.provable)}"
            )
        raise OntologyError(self._unknown_message(name))

    def require_known(self, name: str) -> str:
        """Return ``name`` iff it is real vocabulary (provable OR reserved);
        else raise a did-you-mean :class:`OntologyError`. Used for a term that
        only has to be *nameable* (a transfer claim's subject), not provable."""
        if name in self.known:
            return name
        raise OntologyError(self._unknown_message(name))

    def _unknown_message(self, name: str) -> str:
        hint = difflib.get_close_matches(name, sorted(self.known), n=3)
        tip = f" — did you mean one of {hint}?" if hint else ""
        return (f"unknown {self.kind} {name!r}; known {self.kind}s "
                f"(provable {list(self.provable)} + reserved "
                f"{list(self.reserved)}){tip}")


#: The Role vocabulary. ``support``/``connector``/``ground`` are the committed
#: load-system roles the load-path proof traverses (``ground`` is the terminal
#: Support). ``walking_surface`` is the first OCCUPIED-region role (task SUPPORT):
#: it carries a support/stability obligation the rung-3 support check proves —
#: "the compiler shouldn't know what a deck is; it should know what
#: responsibilities a walking_surface has" (owner directive). ``existing`` is a
#: PRE-EXISTING site feature (task CTXGROUND) — a living tree, a rock outcrop, an
#: existing wall — that the build works AROUND, not something it fabricates. It is
#: grounded earth-side in reality, OUTSIDE the constructed load path; declaring
#: ``grounded_by: site`` on it (only legal for this role) exempts it from the
#: constructed-connectivity floating check, so truthful clearance geometry (a real
#: growth gap around a tree) no longer needs a fake-tight contact bond to fake
#: connectivity. An ``existing`` body is NOT a foundation (see
#: :func:`is_foundation_role`): a support scheme still cannot route through it.
#: ``barrier``/``access``/``surface`` remain RESERVED — real construction roles (a
#: guard barrier, an access opening) whose invariants (lateral-load path,
#: circulation, fall protection) are future waves.
ROLES = Vocabulary(
    "role",
    provable=("support", "connector", "ground", "walking_surface", "existing"),
    reserved=("barrier", "access", "surface"),
)

#: The LoadClass vocabulary. ``downward_load`` is the only class a reachability
#: proof exists for today. The rest are RESERVED: claimable as transfer data,
#: but not yet provable as a path — ``lateral_push`` is exactly the guard-rail
#: load the live gravity-seated-rail defect is about.
LOAD_CLASSES = Vocabulary(
    "load class",
    provable=("downward_load",),
    reserved=("lateral_push", "pull_out", "uplift", "shear"),
)

#: The terminal role: a load path is REPRESENTED when it reaches a part with
#: this role (a Support/ground). Named once here so the check and the ontology
#: agree on the terminal. ``ground`` IS the FOUNDATION concept (task SUPPORT): a
#: boulder/pier/footing/grade — the earth a load path ends in. A structural
#: MEMBER (role ``support``/``connector``) is never a foundation; using one as a
#: ground terminal is the ``ground: leg_pY`` degeneracy the support family
#: forbids (see :func:`is_foundation_role`).
GROUND_ROLE = "ground"
#: The role that ORIGINATES a load path (a member carrying load down).
SUPPORT_ROLE = "support"
#: The occupied-region role that carries a support/stability obligation the
#: rung-3 support check proves (task SUPPORT).
WALKING_SURFACE_ROLE = "walking_surface"
#: The pre-existing-site-feature role (task CTXGROUND): a body grounded by the
#: site itself, outside the constructed load path (see the ROLES note).
EXISTING_ROLE = "existing"


def is_foundation_role(role: str) -> bool:
    """True iff ``role`` is a FOUNDATION — a body a load path may terminate in
    (the earth: boulder, pier block, footing, grade). Today only the ``ground``
    role qualifies. A structural member (``support``/``connector``) is NOT a
    foundation: naming one as a ground terminal is the degeneracy the support
    family rejects."""
    return role == GROUND_ROLE

#: Provenance tiers a transfer claim's ``confidence`` may take — reused verbatim
#: from the DerivedFact vocabulary so the two provenance surfaces line up.
CLAIM_CONFIDENCES = frozenset({"official", "inferred", "placeholder"})
#: KNOWLEDGE-STRATEGY tiers (mirrors evidence.SOURCE_TYPES). A transfer claim is
#: never ``authoritative`` today: no official code/manufacturer citation backs
#: one yet, so claims are reviewed heuristics or (never, today) llm hypotheses.
CLAIM_SOURCE_TYPES = frozenset(
    {"authoritative", "verified_heuristic", "llm_hypothesis"})


@dataclass(frozen=True)
class TransferClaim:
    """One TransferCapability claim: a joint of some ConnectionType
    ``transfers`` (or does_not_transfer) one :data:`LOAD_CLASSES` class, tagged
    with its provenance.

    - ``load_class`` — the LoadClass the claim is about (must be real
      vocabulary; a claim MAY be about a reserved class, e.g. a plain hanger
      does_not_transfer ``uplift``).
    - ``transfers`` — ``True`` (this joint carries that load onward) or
      ``False`` (an honest does_not_transfer — the load-path proof will NOT
      route a path through it for that class).
    - ``confidence`` — ``official`` | ``inferred`` | ``placeholder`` (the
      DerivedFact axis).
    - ``source_type`` — the KNOWLEDGE-STRATEGY tier. Never ``authoritative``
      here: these are ``verified_heuristic`` reviewed rules, not code citations.
    - ``reference`` — an HONEST provenance string. A "representative" catalog
      pointer is fine at inferred/placeholder confidence; an invented official
      citation is not (WAVE 3 SHAPE). Empty when no honest reference exists.

    Validated at construction: the load class must be real vocabulary and the
    provenance tags must be in range — a typo'd claim is a hard diagnostic, not
    silent bad knowledge."""

    load_class: str
    transfers: bool
    confidence: str = "inferred"
    source_type: str = "verified_heuristic"
    reference: str = ""

    def __post_init__(self) -> None:
        LOAD_CLASSES.require_known(self.load_class)
        if self.confidence not in CLAIM_CONFIDENCES:
            raise OntologyError(
                f"transfer claim confidence {self.confidence!r} not in "
                f"{sorted(CLAIM_CONFIDENCES)}")
        if self.source_type not in CLAIM_SOURCE_TYPES:
            raise OntologyError(
                f"transfer claim source_type {self.source_type!r} not in "
                f"{sorted(CLAIM_SOURCE_TYPES)}")

    @property
    def verb(self) -> str:
        return "transfers" if self.transfers else "does_not_transfer"

    def describe(self) -> str:
        ref = f" [{self.reference}]" if self.reference else ""
        return (f"{self.verb} {self.load_class} "
                f"({self.confidence}/{self.source_type}){ref}")
