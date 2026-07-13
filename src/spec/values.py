"""The DetailSpec **value language** — how a spec expresses a number.

A construction detail is a web of dimensions that reference each other
(``rod_len = rod_embed + rod_stick``; a bolt hole sits at ``bolt_z - flange_bot``).
The imperative rock anchor captured those relationships as Python arithmetic over
a bound block of locals; a spec must capture the same relationships *declaratively*
without becoming a frozen table of magic numbers the schema test forbids (a magic
``273.05`` is exactly a fact the compiler could have derived from
``rod_embed + rod_stick`` — so it is out of the spec). This module is that
derivation surface.

Grammar of a value
------------------
Anywhere a spec expects a value (a component param, a placement offset, a
through-hole radius, an element of a ``holes`` list), one of:

- **plain scalar** — ``true`` / ``false`` / a bare string / a bare number:
  passed through UNCHANGED and dimensionless. This is how non-length data is
  written: ``nominal: "2x6"``, ``treated: true``, ``label: "leveling nut"``,
  ``axis: Z``, a rotate angle ``-90``, a bearing area ``1800`` (mm², already
  internal). A bare number is NEVER unit-converted — it is a literal in the
  package's internal unit (mm). Lengths are written as directives instead, so a
  length can never be a silent bare number.
- **directive string** — always denotes a LENGTH, resolved to millimeters
  (the package-internal unit):
  - ``"$name"`` — the value of a param or derived dimension (authoring units).
  - ``"= <expr>"`` — arithmetic over params/derived (authoring units): ``+ - * /
    // % **`` and unary ``-``, numeric literals, and param/derived names. No
    calls, attributes, or subscripts (a deliberately small, auditable surface).
  - ``"<n> in"`` / ``"<n> mm"`` / ``"<n> ft"`` — an explicit quantity, converted
    absolutely (``8 in`` is 203.2 mm regardless of the doc's authoring unit).

Why "directives are always lengths": it removes the one genuine ambiguity a
units DSL has — *is this bare 8 inches or 8 millimeters or 8 of nothing?* A bare
number is internal units, full stop; a length is a directive, full stop. It also
means the resolver needs no per-field schema of which kwargs are lengths (the
components don't declare that): the author marks a length by writing it as a
directive. A future need for a *computed dimensionless* value is a documented
seam (a ``~expr`` directive), not a reinterpretation of these.

Every failure is a teaching diagnostic (:class:`SpecValueError`), mirroring
``core.registry``'s unknown-key style: an unknown name in an expression lists the
names in scope with did-you-mean suggestions; a disallowed expression construct
names what IS allowed.
"""

from __future__ import annotations

import ast
import difflib
import re
from dataclasses import dataclass

#: Authoring/quantity unit -> millimetre factor. Matches ``core.units`` (the
#: single source of the magnitudes) rather than re-deriving them, so a spec's
#: ``"8 in"`` and Python's ``8 * IN`` can never disagree.
from ..core.units import IN, FT, MM

UNIT_FACTORS: dict[str, float] = {"mm": MM, "in": IN, "ft": FT}

#: A quantity literal: a number then one of the unit words. Anchored, so a plain
#: string like ``"2x6"`` or ``"leveling nut"`` can never be mistaken for one.
_QUANTITY_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(mm|in|ft)\s*$")


class SpecValueError(ValueError):
    """A value could not be resolved — an unknown name, a malformed quantity,
    or a disallowed expression construct. Carries a ready-to-print message in
    the ``core.registry`` teaching style (what was wrong + what is valid)."""


def lookup(namespace: dict[str, float], name: str) -> float:
    """Resolve a dimension name against ``namespace`` (authoring-unit
    magnitudes), or raise :class:`SpecValueError` listing the names in scope
    with did-you-mean suggestions — the same loud style as ``core.registry``.
    Shared by the use-site :class:`Resolver` and the compiler's param/derived
    evaluation, so a typo fails identically wherever it appears."""
    try:
        return namespace[name]
    except KeyError:
        suggestions = difflib.get_close_matches(name, sorted(namespace), n=3)
        hint = f" — did you mean one of {suggestions}?" if suggestions else ""
        raise SpecValueError(
            f"unknown dimension {name!r}; in scope: {sorted(namespace)}{hint}"
        ) from None


def evaluate(expr: str, namespace: dict[str, float]) -> float:
    """Evaluate an arithmetic expression over ``namespace`` (authoring-unit
    magnitudes), returning an authoring-unit magnitude. The permitted surface
    is deliberately tiny (see the module docstring) — every other construct is
    a teaching diagnostic, not a silent Python eval."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise SpecValueError(f"could not parse expression {expr!r}: {e.msg}") from None
    return _eval_node(tree.body, lambda n: lookup(namespace, n), expr)


@dataclass(frozen=True)
class Resolver:
    """Resolves spec values against a fixed namespace of param/derived
    dimensions (authoring-unit magnitudes) plus an authoring unit factor.

    ``namespace`` maps a name to its magnitude *in the authoring unit* (e.g.
    ``rod_embed -> 8.0`` for a doc authored in inches) — exactly the raw
    numbers the imperative detail bound as locals before multiplying by ``IN``.
    ``unit_factor`` is that authoring unit's mm factor (``IN`` for an inch doc),
    applied when a ``$``/``=`` directive is turned into an internal-unit length.
    """

    namespace: dict[str, float]
    unit_factor: float

    def resolve(self, value):
        """Resolve one spec value (recursing into lists/dicts) to the concrete
        Python value the underlying constructor/API expects: a mm ``float`` for
        a length directive, the value unchanged for a plain scalar, a
        ``list``/``dict`` with every element resolved."""
        if isinstance(value, bool):
            return value
        if isinstance(value, (list, tuple)):
            return [self.resolve(v) for v in value]
        if isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}
        if isinstance(value, str):
            return self._resolve_str(value)
        # int/float: a bare number is an internal-unit (mm) / dimensionless
        # literal, passed through untouched (see the module docstring).
        return value

    def resolve_length(self, value) -> float:
        """Resolve a value that MUST be a length, to mm. A directive resolves
        normally; a bare number is taken as already-mm. Used for values whose
        length-ness is structural (a placement ``at`` coordinate), so a plain
        ``0`` there means 0 mm without forcing ``"0 in"``."""
        if isinstance(value, str):
            return float(self._resolve_str(value))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        raise SpecValueError(
            f"expected a length (a number or a $/=/unit directive), got {value!r}"
        )

    # -- internals ------------------------------------------------------------

    def _resolve_str(self, s: str):
        text = s.strip()
        if text.startswith("$"):
            return self._lookup(text[1:].strip()) * self.unit_factor
        if text.startswith("="):
            return self._eval(text[1:].strip()) * self.unit_factor
        m = _QUANTITY_RE.match(text)
        if m:
            return float(m.group(1)) * UNIT_FACTORS[m.group(2)]
        # A plain string (an enum axis, a nominal size, a BOM label): passthrough.
        return s

    def _lookup(self, name: str) -> float:
        return lookup(self.namespace, name)

    def _eval(self, expr: str) -> float:
        return evaluate(expr, self.namespace)


# Arithmetic the expression sublanguage permits — deliberately small and
# auditable (P1: the derivation surface must be inspectable, not a general eval).
_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
}
_UNARYOPS = {ast.UAdd: lambda a: +a, ast.USub: lambda a: -a}


def _dotted_name(node, expr: str) -> str:
    """Collapse an ``ast.Attribute`` chain (``a.b.c``) back into its dotted
    source text ``"a.b.c"``, so a qualified dimension name resolves as one
    namespace key. Only plain name/attribute chains are dotted names; anything
    else (a call, a subscript) is the same teaching diagnostic the general
    unsupported-construct branch gives."""
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        raise SpecValueError(
            f"expression {expr!r} uses an unsupported construct "
            f"({type(cur).__name__}); a qualified name must be plain "
            f"dotted identifiers like 'platform.leg_station'"
        )
    parts.append(cur.id)
    return ".".join(reversed(parts))


def _eval_node(node, lookup, expr: str) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise SpecValueError(
                f"expression {expr!r} contains a non-numeric literal "
                f"{node.value!r}; only numbers and dimension names are allowed"
            )
        return float(node.value)
    if isinstance(node, ast.Name):
        return lookup(node.id)
    if isinstance(node, ast.Attribute):
        # A dotted name (``platform.leg_station``) collapses to a single lookup
        # key. The SITE value namespace (task SITEMODEL) qualifies every
        # fragment's dimensions as ``<subsystem_id>.<name>`` and resolves a site
        # placement expressed in the OWNING fragment's numbers. For a detail
        # spec, whose param/derived names are identifiers, a stray ``a.b`` is
        # still a teaching error (``unknown dimension 'a.b'``) rather than the
        # older ``unsupported construct`` — same class of loud failure. (Only a
        # deliberately dotted param KEY would resolve; no current spec has one.)
        return lookup(_dotted_name(node, expr))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left = _eval_node(node.left, lookup, expr)
        right = _eval_node(node.right, lookup, expr)
        try:
            return _BINOPS[type(node.op)](left, right)
        except ZeroDivisionError:
            raise SpecValueError(
                f"expression {expr!r} divides by zero"
            ) from None
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
        return _UNARYOPS[type(node.op)](_eval_node(node.operand, lookup, expr))
    raise SpecValueError(
        f"expression {expr!r} uses an unsupported construct "
        f"({type(node).__name__}); allowed: + - * / // % **, unary -, numbers, "
        f"and dimension names"
    )
