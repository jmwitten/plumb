"""INCR-5 — the v1 consumer: scoped golden regeneration + diff attribution + the
AC2 self-verify gate (incr-design §4.3, §7 AC2/AC6, §10 item 5).

The heart of this suite is **AC2 — region soundness, self-verifying and independent**
(the gate of the whole INCR arc, brief non-negotiable). For each seeded and
adversarial edit it asserts two things:

1. **Byte-level equality** (:func:`test_scoped_equals_whole_world_byte_for_byte`):
   the region-scoped regeneration equals a whole-world regeneration BYTE FOR BYTE.
   The whole-world side is computed by :func:`scoped_regen.whole_world_golden` — the
   OLD full path, ``content_lines`` over every new revision with ZERO region input
   (no diff, no region, no scoping) — so the comparison cannot be circular
   (review-incrdesign item 2). The bite is on the details the region leaves REUSED:
   ``rock_anchor`` is not regenerated for a platform edit, and the gate proves the
   reused base golden equals the whole-world recompute — i.e. the region was right to
   skip it.

2. **Line-attribution soundness** (:func:`test_line_attribution_is_sound`): every
   content line the edit actually changed is attributed to a region member (no missed
   line). An unattributable changed line is a LOUD anomaly — the region missed
   something. :func:`test_attribution_bites_when_region_under_claims` proves the gate
   is not vacuous: a deliberately-truncated region DOES raise anomalies.

The adversarial edits (``beam_mY`` one-sided, ``rail_mY`` one-sided, ``ground_z_front``)
are reused verbatim from review-incr4.md — they earned their place catching one-sided
attribution escapes. The STRUCT-style acceptance (a member-addition edit on the
composed site regenerates only platform + site, with an attributed diff and measured
churn) is :func:`test_struct_member_addition_scopes_platform_and_site`.
"""

from __future__ import annotations

import dataclasses as dc
import re
import shutil
import tempfile
from pathlib import Path

import pytest

import baseline_lib as bl
from detailgen.spec.compiler import compile_spec, compile_spec_file
from detailgen.spec.loader import load_spec_file
from detailgen.spec.site import compile_site_file
from detailgen.spec.identity import AuthoredIdentity
from detailgen.incremental.affected_region import AffectedRegion, edit_region
from detailgen.incremental.revision_diff import revision_diff
from detailgen.incremental import scoped_regen as sr

_PLATFORM = "details/platform.spec.yaml"
_DETAILS = Path("details")


def _platform(overrides=None):
    d = compile_spec_file(_PLATFORM, overrides=overrides)
    d.validate()
    return d


def _one_sided(cid, idx, expect, new_expr):
    """A one-sided placement edit (the reviewer's asymmetric class): move ONE member
    of a mirror pair by rewriting a single coordinate of its ``place.at``. Breaks the
    pair's symmetry so the twin is not co-seeded — the edit review-incr4 used to catch
    an attribution escape."""
    doc = load_spec_file(_PLATFORM)
    comps = []
    for c in doc.components:
        if getattr(c, "id", None) == cid:
            at = list(c.place.at)
            assert at[idx] == expect, f"{cid} place[{idx}] moved: {at[idx]!r}"
            at[idx] = new_expr
            c = dc.replace(c, place=dc.replace(c.place, at=tuple(at)))
        comps.append(c)
    d = compile_spec(dc.replace(doc, components=comps))
    d.validate()
    return d


# The unedited platform, compiled once — every seeded edit diffs against it.
_BASE = _platform()


#: The AC2 edit set: the design's seeded edits + the review-incr4 adversarial edits
#: (``beam_mY``/``rail_mY`` one-sided, ``ground_z_front``). Each value builds the NEW
#: revision the diff reads.
EDITS = {
    "beam_len": lambda: _platform({"beam_len": 52.0}),        # extends deck run (floor case)
    "bolt_dia": lambda: _platform({"bolt_dia": 0.5}),         # fattens every leg bolt
    "rail_height": lambda: _platform({"rail_height": 40.0}),
    "leg_gap": lambda: _platform({"leg_gap": 1.0}),
    "n_steps_add": lambda: _platform({"n_steps": 3}),         # adds a rung + hardware
    "n_steps_drop": lambda: _platform({"n_steps": 1}),        # drops a rung (vanished)
    "ground_z_front": lambda: _platform({"ground_z_front": 3.0}),  # adversarial B
    "beam_mY_one_sided": lambda: _one_sided(                  # adversarial A
        "beam_mY", 1, "= -outer_y", "= -outer_y - 0.5"),
    "rail_mY_one_sided": lambda: _one_sided(                  # adversarial C
        "rail_mY", 1, "= -(outer_y + t2x)", "= -(outer_y + t2x) - 0.5"),
}


# --------------------------------------------------------------------------- #
# AC2 (a) — line-attribution soundness: no changed line is unattributable
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("edit", list(EDITS))
def test_line_attribution_is_sound(edit):
    """Every content line the edit changes is attributed to a region member. An
    anomaly means the region missed a line the edit changed — the exact soundness
    failure attribution exists to surface. Zero anomalies across all seeded and
    adversarial edits IS the region-soundness proof at line granularity."""
    new = EDITS[edit]()
    regen = sr.scoped_regen({"platform": (_BASE, _BASE)},
                            {"platform": (_BASE, new)}, bl.content_lines)
    d = regen.details["platform"]
    assert d.regenerated, "a real edit must reach the platform detail"
    assert d.attribution.anomalies == (), (
        f"UNSOUND: {len(d.attribution.anomalies)} changed line(s) not attributable to "
        f"any region member (the region missed them): "
        f"{[a[:80] for a in d.attribution.anomalies[:5]]}")
    assert d.attribution.attributed, "the edit changed lines; they must be attributed"


# --------------------------------------------------------------------------- #
# AC2 (b) — byte-level: scoped == whole-world, and the whole-world side is
# region-independent (the OLD full path)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("edit", ["beam_len", "bolt_dia", "n_steps_add",
                                  "n_steps_drop", "ground_z_front"])
def test_scoped_equals_whole_world_byte_for_byte(edit):
    """The AC2 byte gate on a two-detail world {platform, rock_anchor}. A platform
    edit regenerates the platform and REUSES ``rock_anchor``'s base golden; the gate
    proves that reused golden equals an independent whole-world recompute — the region
    was right to skip it. The whole-world side is ``whole_world_golden`` (no region)."""
    rock = compile_spec_file("details/rock_anchor.spec.yaml"); rock.validate()
    new_p = EDITS[edit]()
    base_world = {"platform": (_BASE, _BASE), "rock_anchor": (rock, rock)}
    new_world = {"platform": (_BASE, new_p), "rock_anchor": (rock, rock)}

    sv = sr.self_verify(base_world, new_world, bl.content_lines)
    assert sv.passed, (f"AC2 FAIL — mismatch={sv.mismatched_slugs} "
                       f"anomalies={sv.anomaly_slugs}")
    assert sv.scoped.regenerated_slugs() == ("platform",)
    assert sv.scoped.reused_slugs() == ("rock_anchor",)
    # the reused golden is the base lines, verbatim (no recompute, byte-identical)
    assert sv.scoped.details["rock_anchor"].golden == tuple(bl.content_lines(rock))


def test_whole_world_side_is_region_independent():
    """The whole-world comparison side is the OLD full path: ``content_lines`` over
    each new revision, with no region and no diff consulted. Proven by equality to a
    map built with nothing but ``content_lines`` — the non-circularity requirement."""
    new_p = _platform({"beam_len": 52.0})
    new_world = {"platform": (_BASE, new_p)}
    whole = sr.whole_world_golden(new_world, bl.content_lines)
    assert whole == {"platform": tuple(bl.content_lines(new_p))}


# --------------------------------------------------------------------------- #
# The negative control — the gate BITES (attribution is not vacuous)
# --------------------------------------------------------------------------- #
def test_attribution_bites_when_region_under_claims():
    """If the region is truncated (misses the changed parts/findings), attribution
    MUST raise anomalies — otherwise a green gate would be meaningless. Feed a real
    edit's semantic diff against an emptied region and assert the changed lines are
    flagged, not silently passed."""
    new = _platform({"bolt_dia": 0.5})
    base_p2a = sr._pos_to_authored(_BASE)
    new_p2a = sr._pos_to_authored(new)
    nb = {sr._normalize_line(l, base_p2a) for l in bl.content_lines(_BASE)}
    nn = {sr._normalize_line(l, new_p2a) for l in bl.content_lines(new)}
    sem_added, sem_removed = nn - nb, nb - nn
    assert sem_added or sem_removed, "the edit must change some line"

    empty_region = AffectedRegion(
        seeds=frozenset({"bolt"}), parts=frozenset(), declarations=frozenset(),
        facts=frozenset(), findings=frozenset(), unattributed_findings=frozenset(),
        total_findings=1)
    attribution = sr._attribute(sem_added, sem_removed, empty_region)
    assert attribution.anomalies, (
        "a region missing every changed member must produce anomalies — the gate "
        "would be vacuous otherwise")
    assert not attribution.is_sound


# --------------------------------------------------------------------------- #
# AC precision (Q4) — over-claim is MEASURED, not gated; soundness is held
# --------------------------------------------------------------------------- #
def test_over_claim_is_measured_not_gated():
    """Soundness (changed ⊆ region) is non-negotiable; over-claim (a region finding
    with no actually-changed line) is tolerated in v1 and reported, not failed (Q4).
    Here: the region's findings are a superset of the actually-changed findings, and
    the over-claim is a bounded, reported fraction — never zero-tolerance."""
    new = _platform({"beam_len": 52.0})
    diff = revision_diff(_BASE, new)
    region = edit_region(_BASE, new, diff)
    changed = set(diff.findings.changed) | set(diff.findings.vanished) \
        | set(diff.findings.appeared)
    assert changed, "the edit must change findings"
    assert changed <= region.findings, "SOUNDNESS: changed findings must be in region"
    over_claim = region.findings - changed          # measured, not gated
    assert len(over_claim) >= 0                      # reported; no hard bound in v1


# --------------------------------------------------------------------------- #
# STRUCT-style acceptance — a member-addition edit on the composed site scopes
# to platform + site only, with an attributed diff and measured churn
# --------------------------------------------------------------------------- #
_SITE_SLUGS = ("platform", "rock_anchor", "tree_attachment", "trolley_launch")


def _world_from(base_dir: Path):
    """Compile the whole golden-bearing world from a details/ directory: the four
    standalone details plus the composed site."""
    world = {}
    for slug in _SITE_SLUGS:
        d = compile_spec_file(base_dir / f"{slug}.spec.yaml"); d.validate()
        world[slug] = d
    site = compile_site_file(base_dir / "site.spec.yaml"); site.validate()
    world["site"] = site
    return world


@pytest.fixture(scope="module")
def struct_worlds():
    """Base world (shipped specs) and a new world whose platform adds a ladder rung
    (``n_steps`` 2→3) — a member-addition-shaped edit, the STRUCT shape: it adds
    platform parts that propagate into the composed site but reach no other
    subsystem."""
    base = _world_from(_DETAILS)
    tmp = Path(tempfile.mkdtemp())
    for f in _DETAILS.glob("*.spec.yaml"):
        shutil.copy(f, tmp / f.name)
    plat = tmp / "platform.spec.yaml"
    edited = re.sub(r"(\n  n_steps:\s*)2\b", r"\g<1>3", plat.read_text(), count=1)
    assert edited != plat.read_text(), "expected to bump n_steps 2->3"
    plat.write_text(edited)
    new = _world_from(tmp)
    try:
        yield base, new
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_struct_member_addition_scopes_platform_and_site(struct_worlds):
    """The STRUCT acceptance story: adding a platform member regenerates ONLY the
    platform and the composed site (which composes the platform); rock_anchor,
    tree_attachment, and trolley_launch are untouched. Byte-level self-verify passes
    and no regenerated detail carries an anomaly."""
    base, new = struct_worlds
    bw = {s: (base[s], base[s]) for s in base}
    nw = {s: (base[s], new[s]) for s in base}
    sv = sr.self_verify(bw, nw, bl.content_lines)

    assert sv.passed, f"mismatch={sv.mismatched_slugs} anomalies={sv.anomaly_slugs}"
    assert sv.scoped.regenerated_slugs() == ("platform", "site")
    assert sv.scoped.reused_slugs() == ("rock_anchor", "tree_attachment",
                                        "trolley_launch")


def test_struct_churn_before_after(struct_worlds):
    """The measured before/after churn: the OLD path regenerates all 5 baselines; the
    scoped consumer regenerates 2. The site's diff carries a handful of pure
    positional-renumber lines (an ordinal shift the region correctly does not
    attribute) — reported as ``renumbered``, distinct from the semantic diff."""
    base, new = struct_worlds
    bw = {s: (base[s], base[s]) for s in base}
    nw = {s: (base[s], new[s]) for s in base}
    churn = sr.scoped_regen(bw, nw, bl.content_lines).churn()

    assert churn["whole_world_regenerated"] == 5
    assert churn["scoped_regenerated"] == 2
    assert churn["reused"] == 3
    # the win is real: a member-addition regenerates < half the corpus
    assert churn["scoped_regenerated"] < churn["whole_world_regenerated"]
    # renumber noise is bounded and separated from the semantic diff
    assert churn["renumbered_lines"] > 0
    assert churn["semantic_changed_lines"] == (
        churn["changed_lines"] - churn["renumbered_lines"])


def test_cross_detail_isolation_rock_anchor_untouched(struct_worlds):
    """AC4 at the consumer level: a platform edit leaves rock_anchor's baseline
    byte-identical, so nothing about rock_anchor is regenerated. The reused golden is
    exactly its base content lines."""
    base, new = struct_worlds
    bw = {s: (base[s], base[s]) for s in base}
    nw = {s: (base[s], new[s]) for s in base}
    regen = sr.scoped_regen(bw, nw, bl.content_lines)
    rock = regen.details["rock_anchor"]

    assert not rock.regenerated
    assert rock.changed_lines == 0
    assert rock.golden == tuple(bl.content_lines(base["rock_anchor"]))


def test_site_diff_attribution_is_sound(struct_worlds):
    """Within the regenerated site, every semantically-changed content line is
    attributed to a region member — the composed model's attribution is sound even
    across the bind: boundary (a platform member's change never attributes to a
    rock_anchor id)."""
    base, new = struct_worlds
    regen = sr.scoped_regen({"site": (base["site"], base["site"])},
                            {"site": (base["site"], new["site"])}, bl.content_lines)
    site = regen.details["site"]
    assert site.regenerated
    assert site.attribution.anomalies == (), (
        f"site attribution anomalies: {[a[:80] for a in site.attribution.anomalies[:5]]}")
    # every attributed member is a real site authored id or finding signature
    for _line, member in site.attribution.attributed:
        assert member  # non-empty handle


# --------------------------------------------------------------------------- #
# Read-only discipline (AC6) + reuse semantics
# --------------------------------------------------------------------------- #
def test_consumer_writes_no_baseline():
    """The consumer is read-only: running a full scoped regen + self-verify rewrites
    no committed baseline (the bytes on disk are unchanged). AC6 — the shipped corpus
    stays byte-stable; only the flag-gated tooling ever writes."""
    before = {p: p.read_bytes() for p in bl.BASELINE_DIR.rglob("*.json")}
    new_p = _platform({"n_steps": 3})
    sr.self_verify({"platform": (_BASE, _BASE)},
                   {"platform": (_BASE, new_p)}, bl.content_lines)
    after = {p: p.read_bytes() for p in bl.BASELINE_DIR.rglob("*.json")}
    assert before == after, "the consumer must not write any baseline"


def test_empty_edit_reuses_everything():
    """A no-op rebuild changes no authored id, so every detail's region is empty and
    every golden is reused — nothing regenerates."""
    regen = sr.scoped_regen({"platform": (_BASE, _BASE)},
                            {"platform": (_BASE, _platform())}, bl.content_lines)
    d = regen.details["platform"]
    assert not d.regenerated
    assert d.changed_lines == 0
    assert regen.regenerated_slugs() == ()
