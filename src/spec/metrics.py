"""Specification-compression metrics (the north-star measure).

The whole point of DetailSpec is that the author writes intent and the platform
derives the rest; these functions quantify that from a compiled spec. The
headline is **specification compression** — derived facts : authored facts from
the derivation log (the same measure W2-6 reported, 2.4:1 for the validation
layer alone) — read directly off the compiler's provenance log by confidence:
an ``official`` fact is one the author declared as given, an ``inferred`` /
``placeholder`` fact is one a compiler rule produced.

HONEST HEADLINE (rev-specplat rec 2, tightened by rev-cleanup). Not every
"derived" fact is real inference; the headline numerator counts only GENUINE
derived construction knowledge, excluding two kinds of non-inference:

- **Escape-hatch facts** (``placeholder`` confidence): a ``spec.placement.raw``
  transform or a ``spec.component.imperative_hook`` — restating imperative input
  the author wrote out coordinate-by-coordinate. The platform inferred nothing.
- **Bookkeeping facts** (``BOOKKEEPING_RULES``): provenance-only records that
  restate the STRUCTURE of what the author wrote, not knowledge derived FROM it.
  ``spec.repeat.instance`` is the case: one fact per expanded part echoing its
  loop index (``joist_0 is repeat instance {k}=0``). It is essential for
  traceability but encodes no construction knowledge, and — the tell of a gamed
  metric — it scales with PART COUNT, not inference depth, so counting it would
  let a bigger loop inflate the ratio. It fails the escape-hatch rationale for
  the same reason placeholder facts do; a distinct bucket documents that it is a
  different flavor of non-inference (bookkeeping restates structure; an escape
  hatch restates geometry) and gives future provenance-only facts a home.

``spec.repeat.expand`` (the DERIVED iteration count of a repeat) is genuine
inference — the compiler worked out HOW MANY from a rule — and stays in the
numerator.

So the HEADLINE compression EXCLUDES escape-hatch AND bookkeeping facts, with
the raw-inclusive figure reported as a SECONDARY number. That keeps the visible
next-inference target (the raw escape hatches) honest rather than hidden inside
a bigger number.

Alongside it: the authored structural counts the brief asks for (explicit
placements / connections / validation declarations / dimensions) and the
spec-vs-imperative LOC.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .schema import DetailSpecDoc, MateSpec, RawSpec, RepeatSpec

#: Provenance/bookkeeping rules — facts that restate the STRUCTURE of what the
#: author wrote (not knowledge derived from it), excluded from the genuine-
#: derived compression numerator. ``spec.repeat.instance`` echoes each expanded
#: part's loop index; it scales with part count, so counting it as inference
#: would game the ratio (rev-cleanup ruling). A frozenset so future provenance-
#: only rules join here rather than sneaking into the numerator.
BOOKKEEPING_RULES: frozenset[str] = frozenset({"spec.repeat.instance"})


def _flatten(entries):
    """Yield the leaf specs (ComponentSpec/ConnectionSpec) of a components or
    connections list, descending into repeat bodies — so authored-block counts
    measure what the AUTHOR wrote (one joist template), not what it EXPANDS to
    (three joists). Also yields nothing for the repeat nodes themselves."""
    for e in entries:
        if isinstance(e, RepeatSpec):
            yield from _flatten(e.body)
        else:
            yield e


def _count_repeats(entries) -> int:
    return sum(1 + _count_repeats(e.body) for e in entries
               if isinstance(e, RepeatSpec))


def compute_metrics(doc: DetailSpecDoc, detail, *, spec_path: Path | None = None,
                    imperative_path: Path | None = None) -> dict:
    """Gather compression + authored-count metrics for a compiled ``detail``.
    Runs ``detail.derivation_report()`` (validating if needed) to read the log."""
    log = detail.derivation_report()
    by_conf = Counter(f.confidence for f in log)
    authored_facts = by_conf.get("official", 0)
    derived_facts = by_conf.get("inferred", 0) + by_conf.get("placeholder", 0)
    # Two kinds of non-inference are stripped from the genuine numerator:
    #  - escape-hatch facts (``placeholder``: a raw transform / imperative hook)
    #    restate imperative GEOMETRY input;
    #  - bookkeeping facts (``BOOKKEEPING_RULES``) restate the STRUCTURE of what
    #    the author wrote (repeat-instance loop indices) and scale with part
    #    count, not inference depth (rev-cleanup ruling).
    escape_hatch_facts = by_conf.get("placeholder", 0)
    bookkeeping_facts = sum(1 for f in log if f.rule in BOOKKEEPING_RULES)
    genuine_derived_facts = derived_facts - escape_hatch_facts - bookkeeping_facts

    component_leaves = list(_flatten(doc.components))
    connection_leaves = list(_flatten(doc.connections))
    mates = sum(1 for c in component_leaves if isinstance(c.place, MateSpec))
    raws = sum(1 for c in component_leaves if isinstance(c.place, RawSpec))
    identity = sum(1 for c in component_leaves if c.place is None)
    n_repeats = _count_repeats(doc.components) + _count_repeats(doc.connections)
    # Parts the compiler actually built (families expanded) — the numerator of
    # the authored-block -> built-part expansion the repeat construct buys.
    n_built = len(detail.assembly.parts)

    m = {
        "components": len(component_leaves),   # AUTHORED blocks, not expanded parts
        "built_parts": n_built,
        "repeat_blocks": n_repeats,
        "params": len(doc.params),
        "derived": len(doc.derived),
        "explicit_placements": mates + raws,
        "mates": mates,
        "raw_escape_hatches": raws,
        "identity_placements": identity,
        "connections": len(connection_leaves),
        "through_hole_checks": len(doc.validation.through_holes),
        "dimension_checks": len(doc.validation.dimensions),
        "ground_declared": doc.validation.ground is not None,
        "total_facts": len(log),
        "authored_facts": authored_facts,
        "derived_facts": derived_facts,
        "escape_hatch_facts": escape_hatch_facts,
        "bookkeeping_facts": bookkeeping_facts,
        "genuine_derived_facts": genuine_derived_facts,
        # HEADLINE (honest): genuine derivations : authored, escape hatches AND
        # bookkeeping out.
        "compression": (genuine_derived_facts / authored_facts)
                       if authored_facts else float("nan"),
        # SECONDARY: raw-inclusive (counts escape-hatch + bookkeeping as
        # "derived").
        "compression_raw_inclusive": (derived_facts / authored_facts)
                                     if authored_facts else float("nan"),
    }
    if spec_path is not None:
        m["spec_loc_total"], m["spec_loc_code"] = _count_loc(spec_path, comment="#")
    if imperative_path is not None and imperative_path.exists():
        m["imperative_loc_total"], m["imperative_loc_code"] = _count_loc(imperative_path, comment="#")
    return m


def format_metrics(m: dict) -> str:
    """A compact multi-line summary for the CLI and the report header."""
    lines = [
        f"Specification compression: **{m['genuine_derived_facts']}** genuine "
        f"derived : **{m['authored_facts']}** authored facts = "
        f"**{m['compression']:.1f}:1** (excluding {m['escape_hatch_facts']} raw "
        f"escape-hatch + {m['bookkeeping_facts']} bookkeeping facts; "
        f"{m['compression_raw_inclusive']:.1f}:1 raw-inclusive, "
        f"{m['total_facts']} total provenance facts).",
        f"Authored in the spec: {m['components']} component blocks "
        f"({m['repeat_blocks']} repeat) -> {m['built_parts']} built parts, "
        f"{m['explicit_placements']} explicit placements "
        f"({m['mates']} mates + {m['raw_escape_hatches']} raw escape hatches; "
        f"{m['identity_placements']} identity), {m['connections']} connections, "
        f"{m['params']} params + {m['derived']} derived dimensions, "
        f"{m['through_hole_checks']} through-hole + {m['dimension_checks']} "
        f"dimension checks.",
    ]
    if "spec_loc_total" in m:
        loc = f"Spec LOC: {m['spec_loc_total']} total / {m['spec_loc_code']} non-comment"
        if "imperative_loc_total" in m:
            loc += (f"; imperative baseline {m['imperative_loc_total']} total / "
                    f"{m['imperative_loc_code']} non-comment")
        lines.append(loc + ".")
    return "\n".join(lines)


def _count_loc(path: Path, comment: str = "#") -> tuple[int, int]:
    text = Path(path).read_text().splitlines()
    total = len(text)
    code = sum(1 for ln in text if ln.strip() and not ln.strip().startswith(comment))
    return total, code
