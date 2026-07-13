"""Identity comparison fingerprint (INCR-2) — a per-member content signature
for reasoning about a change to a detail, R17-immune by construction.

Why this exists
---------------
Revision identity (``incr-design.md`` §3) asks a member-level question: between
the model *before* an edit and the model *after* it, did member M **persist**,
**move**, or **resize**? Answering it needs a signature of a member that is
stable under the one thing that must never register as a change — a last-ULP
float difference between two arithmetically-equivalent code paths (retro
**R17**, ``incr-design.md`` §3.3). A ``42.25"`` value that lands on
``1073.1500000000001`` mm on one build and ``1073.1499999999999`` mm on the
next is the *same* member, not a moved or resized one.

The two decisions this module encodes (``incr-design.md`` §3.4):

The content component is derived from the member's **complete instance-fact
surface** (``vars(component)`` minus two documented non-facts), NOT from
``params()`` — whose ``startswith("_")`` filter silently drops geometry/BOM
facts like ``DeckBoard._trunk_cut`` (cuts the solid) and ``Lumber._full_length``
(drives the BOM ``stub_of`` row that ``content_fingerprint`` hashes). Deriving
from ``vars`` keeps the signature sensitive to everything ``content_fingerprint``
is sensitive to at the member level, and a guard test fails if any float fact
becomes invisible.

1. **Pre-rounding comparison.** Every raw-float member fact — the transform's
   twelve components *and* ``length_mm`` *and* every dimensional fact, at any
   nesting depth (e.g. a ``Lumber``'s ``holes`` coordinates or a ``DeckBoard``'s
   ``_trunk_cut`` tuple) — is rounded to
   the 1e-6 mm grid (:func:`_round6`, a nanometre: far above the ≤2e-13 mm
   inch↔mm float residual, far below any real feature) and ``-0.0`` is folded
   to ``0.0`` before it enters the signature. This is the exact tolerance and
   fold that ``tests/baseline_lib._fmt`` applies to transforms — but note the
   watch item it *closes*: ``content_fingerprint`` emits ``length_mm`` **raw**
   (``baseline_lib.content_lines``), so a ULP-different cut length flips that
   hash; this module rounds ``length_mm`` on the same grid as the transform, so
   it does not.

2. **Transform kept SEPARATE from content.** A :class:`MemberSignature` carries
   the transform component and the content component as two independent strings
   so a revision diff (INCR-3) can read *moved* (transform changed, content
   equal) apart from *resized* (content changed) — see :func:`compare_present`.

Independence (INCR-2 scope): this module imports neither ``baseline_lib`` nor
``content_fingerprint``; it defines its own rounding so a change to one cannot
silently move the other. Every existing baseline, golden, and fingerprint stays
byte-stable because nothing here touches them. It is read-only over a compiled,
validated detail and keys its per-detail map on the plain-string ``Placed.id``;
mapping that to the insertion-stable authored id is INCR-1's bridge, consumed by
INCR-3 — this module is disjoint from both.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


# --------------------------------------------------------------------------- #
# Rounding — the R17 tolerance, defined independently of baseline_lib._fmt
# (same semantics on purpose; separate code so neither can perturb the other).
# --------------------------------------------------------------------------- #
def _round6(v: float) -> str:
    """Round a numeric member fact to the 1e-6 mm grid and fold ``-0.0`` to
    ``0.0``, as a fixed 6-decimal string. A last-ULP difference between two
    arithmetically-equivalent float paths cannot cross this grid, so it cannot
    split the signature (retro R17)."""
    return f"{round(float(v), 6) + 0.0:.6f}"


# Type-tagged canonical serialization. Every scalar carries a one-char type tag
# so an int ``1``, a float ``1.0``, and a str ``"1"`` never collide; floats go
# through _round6 at any nesting depth; dict keys are sorted; strings are
# JSON-quoted so a delimiter char inside a value can't fake structure. The
# result is a deterministic, byte-stable string — the fingerprint content.
def _canon(o) -> str:
    if isinstance(o, bool):            # before int: bool is a subclass of int
        return "B1" if o else "B0"
    if isinstance(o, float):
        return "F" + _round6(o)
    if isinstance(o, int):
        return "I" + str(o)
    if isinstance(o, str):
        return "S" + json.dumps(o, ensure_ascii=False)
    if o is None:
        return "N"
    if isinstance(o, (list, tuple)):
        return "L[" + ",".join(_canon(x) for x in o) + "]"
    if isinstance(o, dict):
        return "D{" + ",".join(f"{_canon(k)}={_canon(v)}"
                               for k, v in sorted(o.items())) + "}"
    return "R" + repr(o)


# --------------------------------------------------------------------------- #
# The per-member signature
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MemberSignature:
    """A member's identity comparison signature: two independent canonical
    strings. ``transform`` is the placement (origin + three axes, rounded);
    ``content`` is everything intrinsic to the member independent of where it
    sits (type, material, params, cut length — every float rounded). Equality
    of the whole dataclass means *persisted*; :func:`compare_present` reads the
    two components apart to separate *moved* from *resized*."""

    transform: str
    content: str

    @property
    def combined(self) -> str:
        """Both components joined by a record separator (0x1e cannot occur in
        the JSON-quoted / tagged encoding) — the full 'same member, same state'
        key."""
        return self.transform + "\x1e" + self.content

    def digest(self) -> str:
        """A short stable hash of the combined signature, for callers that want
        a fixed-width key rather than the full canonical string."""
        return hashlib.sha256(self.combined.encode()).hexdigest()


def _transform_component(placed) -> str:
    fr = placed.world_frame
    return _canon([list(fr.origin), list(fr.x_axis),
                   list(fr.y_axis), list(fr.z_axis)])


#: Instance attributes excluded from the content signature, each for a stated
#: reason — everything else in ``vars(component)`` is a member-identity fact and
#: is included (so the signature sees ``_full_length`` and ``_trunk_cut``, which
#: ``params()`` silently drops via its ``startswith("_")`` filter, ``base.py``):
#:
#: - ``_solid`` — the memoized built geometry (``Component._solid``). A DERIVED
#:   cache whose inputs are the sibling attributes (already in the signature),
#:   holding a non-deterministic cadquery object (its ``repr`` embeds an
#:   address). Hashing it would be redundant and unstable.
#: - ``name`` — the display label. Identity is name-independent by design
#:   (``incr-design.md`` §3.2 / Finding 1: ``Placed.id`` "never changes if
#:   ``component.name`` is edited"); ``cache_key`` and ``bom_group`` both
#:   exclude it too, so ``content_fingerprint`` is not sensitive to it. Including
#:   it would misread a pure display-rename as "resized".
#:
#: A new component that adds an underscore identity fact needs no change here (it
#: is in ``vars`` → in the signature); a new *cache*/non-fact attribute must be
#: added here deliberately — the guard test in ``tests/`` fails until it is, so
#: an invisible fact can never regress silently.
_EXCLUDED_FACT_ATTRS = frozenset({"_solid", "name"})


def _member_facts(component) -> dict:
    """The complete member-identity fact surface: every instance attribute
    except the documented exclusions. Underscore-prefixed geometry/BOM facts
    (``_full_length``, ``_trunk_cut``) are kept — they drive ``stub_of`` /
    ``cache_key`` and are hashed by ``content_fingerprint``, so the identity
    signature must see them."""
    return {k: v for k, v in vars(component).items()
            if k not in _EXCLUDED_FACT_ATTRS}


def _content_component(placed) -> str:
    c = placed.component
    material = getattr(getattr(c, "material", None), "name", None)
    return _canon({
        "type": type(c).__name__,
        "material": material,
        "length_mm": c.bom_length_mm(),
        "facts": _member_facts(c),
    })


def member_signature(placed) -> MemberSignature:
    """The identity comparison signature of one placed part. Reads only the
    member's world transform and its declared facts (``params`` / ``material``
    / ``bom_length_mm``); it never builds geometry, so it is cheap and
    side-effect free."""
    return MemberSignature(
        transform=_transform_component(placed),
        content=_content_component(placed),
    )


def detail_signatures(detail) -> dict[str, MemberSignature]:
    """Signatures for every part of a compiled detail, keyed on the plain
    ``Placed.id`` string. The revision diff (INCR-3) re-keys this on the
    insertion-stable authored id via INCR-1's bridge; keyed here on the id the
    assembly already carries so this module stands alone."""
    return {p.id: member_signature(p) for p in detail.assembly.parts}


def compare_present(before: MemberSignature, after: MemberSignature) -> str:
    """Classify a member that exists in BOTH revisions (the id was matched by
    the caller) as ``"persisted"`` / ``"moved"`` / ``"resized"``.

    A content change wins over a transform change: a resized member that also
    shifted reads as ``"resized"`` (its geometry changed), matching the design's
    verdict table (``incr-design.md`` §3.2). This is the move-vs-resize
    primitive the separation of the two components exists to enable; the full
    five-verdict revision diff — vanished/appeared over authored-id set logic
    and declared renames — is INCR-3, built on top of this."""
    if before.content != after.content:
        return "resized"
    if before.transform != after.transform:
        return "moved"
    return "persisted"
