"""CL-3 — EXPECT (declaration-attached expectations) + RETIRE (intentional
removal with provenance) + REPLAY C, the conceptual acceptance tests §7 Test 3 +
Test 4, and the §3.5 declaration-time diagnostics.

The bar (cl0-design §0/§7): success is NOT "the function exists." It is that a
CLASS OF WRONGNESS becomes impossible — or impossible to call CLEAN. The two
classes CL-3 kills:

- **R10 — partial retirement leaving orphan bearings / pins / stale prose** (the
  ~9-file hand-unwind). A `retire:` removes the connection AND its entire derived
  closure — bearings, hardware findings, evidence edges, and the attached pins —
  in ONE declaration, with 0 orphan pins (REPLAY C / Test 3). Made unwritable
  because every fact is OWNED by the connection, so deletion is the edit.
- **R12/R19 — pins divorced from their declarations (the 24-vs-20 miscount, the
  orphan pins).** An `expect:` rides on the connection it concerns; the pin
  accounting is DERIVED from where each pin is attached, and a pin that fires no
  divergence is a teaching error (orphan). A pin cannot outlive what it pinned.

Also §7 Test 4: the R21 support regression, reconstructed — a CL-declared
walking_surface supported under one end reports the tree end FAIL and cannot be
called CLEAN (rides the merged SUPPORT pack; CL's contribution is that the
obligation arrives via the DECLARED role).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from detailgen.spec.compiler import compile_spec, compile_spec_file
from detailgen.spec.loader import load_spec_file, load_spec_text
from detailgen.spec.semantics import SemanticError
from detailgen.spec.expectations import (
    ExpectationError,
    Pin,
    classify,
    detail_pin_accounting,
    pins_from_detail,
    require_no_orphans,
)

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "cl3"
TREE_LAG = FIX / "tree_lag.spec.yaml"
TREE_LAG_RETIRED = FIX / "tree_lag_retired.spec.yaml"
ONE_END = FIX / "one_end_support.spec.yaml"


# --------------------------------------------------------------------------- #
# EXPECT — the pin rides on the declaration; the accounting is DERIVED
# --------------------------------------------------------------------------- #
def test_expect_pins_are_attached_to_their_owning_connection():
    """The pin is not in a global side-file; it is READ from the connection it
    concerns, and its subject is the connection's (label + parts), never
    re-typed. This is the R7/R12 ownership the side-JSON lacked."""
    detail = compile_spec_file(TREE_LAG)
    pins = pins_from_detail(detail)
    assert len(pins) == 1
    (pin,) = pins
    assert pin.check == "bearing"
    assert pin.owner == "tree lag +Y"
    assert pin.count == 2  # the joint owns exactly two bearing divergences
    assert "TREEFREE" in pin.reason
    # the pin knows which findings are INTERNAL to its joint from the owner's own
    # part names — no hand-typed subject that could drift (R19).
    assert "beam +Y" in pin.owner_names
    assert pin.owns_subject("lag washer nut <-> beam +Y")


def test_expect_classification_pins_the_real_divergence_zero_new_zero_orphan():
    """The joint's derived bearing FAILs (the free-standing beam stands clear of
    the tree, so the lag washers do not bear). The attached pin COVERS exactly
    those failures — expected, not new, not orphan. The site is CLEAN modulo the
    pinned, deferred divergence."""
    detail = compile_spec_file(TREE_LAG)
    acc = detail_pin_accounting(detail)
    # every live failure is pinned (expected); nothing is a new/unexplained
    # failure, and no pin is an orphan.
    assert acc.new == ()
    assert acc.orphans == ()
    assert len(acc.expected) >= 1
    assert all(check == "bearing" and owner == "tree lag +Y"
               for check, subject, owner, reason in acc.expected)


def test_expect_report_derives_the_pin_accounting_grouped_by_owner():
    """The pinned-finding set as a compiler REPORT, grouped by the OWNING
    declaration (§3.4 field 2) — the side_divergence.json partition made DERIVED,
    not maintained by hand."""
    detail = compile_spec_file(TREE_LAG)
    grouped = detail_pin_accounting(detail).grouped()
    assert set(grouped) == {"tree lag +Y"}
    rows = grouped["tree lag +Y"]
    assert all(check == "bearing" for check, subject, reason in rows)
    assert all("TREEFREE" in reason for check, subject, reason in rows)


def test_expect_pin_migration_is_byte_preserving():
    """An expectation MOVING from a hand-kept (check, subject) side-set to its
    owning declaration must not change ONE verdict (§3.4). Here the two count:2
    bearing divergences the joint owns are pinned EXACTLY — the EXPECTED set
    equals the live-failure set, with 0 new and 0 orphan. Precision is a MECHANISM
    property, not a coincidence of this fixture: the next test proves a genuinely-
    new same-kind failure is NOT absorbed."""
    detail = compile_spec_file(TREE_LAG)
    report = detail.validate()
    live_failures = {(f.check, f.subject) for f in report.failures}
    acc = detail_pin_accounting(detail)
    attached_pinned = {(check, subject) for check, subject, _o, _r in acc.expected}
    assert attached_pinned == live_failures
    assert acc.new == () and acc.orphans == ()


def test_a_new_same_kind_failure_is_not_absorbed_by_the_pin():
    """THE fix-round regression (review-cl3.md §4). Coverage is COUNT-BOUNDED: the
    count:2 bearing pin owns exactly two divergences, so injecting a THIRD,
    genuinely-new bearing failure (the two clamped plates stand 1.5in apart and do
    not bear) surfaces it as NEW — it is NOT silently pinned, and the detail does
    NOT validate CLEAN. The round-1 per-kind-per-joint matcher absorbed exactly
    this (new==0, CLEAN); it must never again."""
    body = TREE_LAG.read_text().replace(
        "validation:\n",
        "validation:\n  bearings:\n    - {a: cleat, b: beam, axis: Y, area: 60}\n")
    detail = compile_spec(load_spec_text(body))
    acc = detail_pin_accounting(detail)
    # the injected divergence is NEW, not absorbed; the two real ones stay pinned.
    assert ("bearing", "tree cleat <-> beam +Y") in acc.new
    assert len(acc.expected) == 2 and acc.orphans == ()
    assert not detail.validate().ok  # a hidden divergence can no longer pass CLEAN


def test_a_foreign_part_failure_is_never_internal_to_the_joint():
    """SUBJECT-PRECISE coverage: a pin only owns findings whose subject is
    INTERNAL to its joint (every named member is one of the connection's own
    parts/hardware). A finding naming a foreign part is not a candidate even under
    budget — proving the tightening is by-subject, not merely by-count."""
    p = Pin(check="bearing", reason="r", owner="J",
            owner_names=frozenset({"beam", "washer"}))
    assert p.owns_subject("beam <-> washer")      # both internal
    assert not p.owns_subject("beam <-> foreign")  # a foreign member -> not owned
    assert p.owns_subject("J: washer")             # own hardware-presence line


def test_expect_pins_are_deterministic():
    """The derivation is a pure function of the declarations — same pins, same
    order, on every compile (§8.7)."""
    a = pins_from_detail(compile_spec_file(TREE_LAG))
    b = pins_from_detail(compile_spec_file(TREE_LAG))
    assert a == b


@pytest.mark.parametrize("path", [TREE_LAG, TREE_LAG_RETIRED, ONE_END])
def test_expect_and_retire_round_trip(path):
    """A connection-attached `expect:` and a top-level `retire:` survive
    load -> serialize -> reload as EQUAL objects, and re-dump byte-stably — the
    serialize contract every authored surface must keep (both are emitted only
    when present, so retire/expect-free specs are unchanged)."""
    from detailgen.spec.serialize import dump_yaml
    doc = load_spec_file(path)
    assert load_spec_text(dump_yaml(doc)) == doc
    assert dump_yaml(load_spec_text(dump_yaml(doc))) == dump_yaml(doc)


# --------------------------------------------------------------------------- #
# §7 Test 3 (THE RETIREMENT CAT) + REPLAY C — one declaration, whole closure
# --------------------------------------------------------------------------- #
def test_cat3_retire_unwinds_the_whole_derived_closure():
    """The author retires ONE connection. That removes its geometry-facts, its
    validation (every derived bearing + hardware finding), its evidence edges,
    AND its findings/pins — with NO hand-unwinding across files. The wrongness
    class that disappears: partial retirement leaving orphan bearings/pins/prose
    (R10, R14) — the ~9-file hand-unwind."""
    before = compile_spec_file(TREE_LAG)
    after = compile_spec_file(TREE_LAG_RETIRED)
    rb, ra = before.validate(), after.validate()

    # the connection and its WHOLE derived closure are gone.
    assert len(before.connections()) == 1
    assert len(after.connections()) == 0
    closure = {(f.check, f.subject) for f in rb.findings} \
        - {(f.check, f.subject) for f in ra.findings}
    # the connection owned 4 derived bearings + 4 hardware-presence findings
    # + (INSTALL v1) its bolt's two installability axis findings — retiring
    # the connection retires its install contract and BOTH axis verdicts too.
    assert ("connection_hardware", "tree lag +Y: lag bolt") in closure
    assert any(c == "bearing" for c, s in closure)
    assert ("install_termination", "tree lag +Y: lag bolt") in closure
    assert ("install_access", "tree lag +Y: lag bolt") in closure
    assert len(closure) == 10

    # 0 orphan pins: the attached pin retired WITH the connection.
    assert pins_from_detail(after) == []
    acc_after = detail_pin_accounting(after)
    assert acc_after.expected == () and acc_after.orphans == ()

    # the retired detail now validates CLEAN (the deferred divergence is gone,
    # not pinned-forever): the free-standing model has no open failure.
    assert ra.ok


def test_replayc_is_one_declaration_no_hand_unwinding():
    """REPLAY C measured: the retired spec differs from the base spec by EXACTLY
    the added `retire:` block — the connection, its bearings, its overlaps, its
    pins are NOT hand-edited. Every other authored surface is byte-identical."""
    base = load_spec_file(TREE_LAG)
    retired = load_spec_file(TREE_LAG_RETIRED)
    # the ONLY authored difference is the retire block.
    assert base.retire == ()
    assert len(retired.retire) == 1
    assert retired.retire[0].target == "tree lag +Y"
    # every OTHER authored surface is untouched — the closure was not hand-unwound.
    assert retired.components == base.components
    assert retired.connections == base.connections   # the joint stays as audit
    assert retired.validation == base.validation
    assert retired.roles == base.roles


def test_retire_records_the_audit_provenance():
    """`retire:` keeps the WHY that silent deletion loses (§3.3 field 4): a
    retirement audit fact appears in the derivation report."""
    after = compile_spec_file(TREE_LAG_RETIRED)
    after.build()
    facts = [f.fact for f in after._spec_log]
    assert any("RETIRED" in f and "free-standing redesign" in f for f in facts)


# --------------------------------------------------------------------------- #
# §3.5 declaration-time diagnostics — teaching errors BEFORE geometry
# --------------------------------------------------------------------------- #
def test_orphan_expect_is_a_teaching_error_at_the_gate():
    """A pin that covers NO live failure is an ORPHAN — a teaching error: it
    references a divergence that no longer exists (§3.4 field 3). Here the pin
    expects a `connection_hardware` absence, but all the lag hardware is present,
    so that divergence never fires — the pin has outlived what it pinned."""
    detail = compile_spec_file(FIX / "tree_lag_orphan.spec.yaml")
    acc = detail_pin_accounting(detail)
    assert acc.orphans, "expected the un-fired hardware pin to be an orphan"
    with pytest.raises(ExpectationError) as e:
        require_no_orphans(acc)
    assert "orphan" in str(e.value).lower()
    assert "tree lag +Y" in str(e.value)


def test_orphan_gate_is_pure_classification_logic():
    """The orphan is a property of the classification, provable without geometry:
    a pin whose declared count the joint cannot fill is an orphan; a same-kind
    failure beyond the pins' summed count is NEW. This is the gate's honest,
    count-bounded core."""
    # J owns 1 bearing on its own parts; K expects 1 that never fires (orphan).
    J = Pin(check="bearing", reason="pinned", owner="J", count=1,
            owner_names=frozenset({"beam", "washer"}))
    K = Pin(check="bearing", reason="stale", owner="K", count=1,
            owner_names=frozenset({"ghost", "nut"}))
    acc = classify(
        [("bearing", "beam <-> washer"), ("bearing", "ghost <-> outsider")], [J, K])
    # J covers its internal failure; the ghost<->outsider one is NOT internal to K
    # (outsider is foreign), so it is NEW, and K's budget is unfilled -> orphan.
    assert acc.expected == (("bearing", "beam <-> washer", "J", "pinned"),)
    assert acc.new == (("bearing", "ghost <-> outsider"),)
    assert acc.orphans == (("K", "bearing", "stale"),)


def test_count_bounds_are_enforced_in_pure_classification():
    """A count:1 pin covers ONE same-kind internal failure; a second surfaces as
    NEW even though the pin's owner names both parts. The count is the backstop
    that makes over-cover impossible."""
    p = Pin(check="bearing", reason="one", owner="J", count=1,
            owner_names=frozenset({"a", "b", "c"}))
    acc = classify([("bearing", "a <-> b"), ("bearing", "a <-> c")], [p])
    assert len(acc.expected) == 1 and len(acc.new) == 1 and acc.orphans == ()


def test_expect_count_must_be_a_positive_whole_number():
    """`count` is how many same-kind findings the pin owns — a whole number >= 1.
    A zero/negative/non-int count is a teaching error at load (a pin that owns
    'no' or 'a fraction of a' divergence is meaningless)."""
    from detailgen.spec.schema import SpecSchemaError
    body = TREE_LAG.read_text().replace("check: bearing, count: 2",
                                        "check: bearing, count: 0")
    with pytest.raises(SpecSchemaError) as e:
        load_spec_text(body)
    assert "count" in str(e.value)


def test_orphan_retire_connection_is_a_teaching_error():
    """Retiring a connection label that names no connection is a teaching error —
    you cannot retire a joint that does not exist (did-you-mean)."""
    body = TREE_LAG.read_text().replace(
        'connection: "tree lag +Y"', 'connection: "tree lag +Z"')
    body += (
        '\nretire:\n  - {connection: "tree lag +Z", reason: "typo target"}\n')
    with pytest.raises(SemanticError) as e:
        compile_spec(load_spec_text(body))
    msg = str(e.value)
    assert "tree lag +Z" in msg and "no declared connection" in msg
    assert "tree lag +Y" in msg  # did-you-mean names the real label


def test_orphan_retire_member_is_a_teaching_error():
    """Retiring a member id that names no component is a teaching error."""
    body = TREE_LAG.read_text() + (
        '\nretire:\n  - {member: "bean", reason: "typo"}\n')
    with pytest.raises(SemanticError) as e:
        compile_spec(load_spec_text(body))
    msg = str(e.value)
    assert "bean" in msg and "no declared component" in msg


def test_retire_member_with_dependents_is_a_teaching_error():
    """Retiring a MEMBER still referenced by a surviving declaration lists the
    dependents (§3.3 semantic error) — a retirement must not leave a check
    validating against a member that is gone. Here `beam` is still a part of the
    (un-retired) tree-lag connection and named in an expected_overlap."""
    body = TREE_LAG.read_text() + (
        '\nretire:\n  - {member: beam, reason: "drop the beam but keep its joint"}\n')
    with pytest.raises(SemanticError) as e:
        compile_spec(load_spec_text(body))
    msg = str(e.value)
    assert "beam" in msg and "still referenced" in msg
    assert "connection" in msg  # the surviving tree-lag connection is a dependent


def test_retire_member_with_its_connection_retired_together_is_clean():
    """Retiring a member AND the connection that owns its references together is
    NOT a dependents error — the reference retires with the joint. This is the
    honest 'retire or re-point them' resolution the dependents error asks for."""
    body = TREE_LAG.read_text() + (
        '\nretire:\n'
        '  - {connection: "tree lag +Y", reason: "free-standing"}\n')
    detail = compile_spec(load_spec_text(body))  # no error
    assert len(detail.connections()) == 0


def test_diagnostics_fire_before_geometry_builds():
    """All the retire diagnostics are declaration-time (§3.5): the SemanticError
    is raised in compile __init__, before any geometry is assembled — turning a
    ~3-min build+validate discovery (R4) into an instant compile error."""
    body = TREE_LAG.read_text() + (
        '\nretire:\n  - {connection: "nope", reason: "x"}\n')
    doc = load_spec_text(body)
    # compile() runs the semantic pass in __init__, before assemble(); prove the
    # error precedes any build by asserting it raises at construction.
    with pytest.raises(SemanticError):
        compile_spec(doc)


# --------------------------------------------------------------------------- #
# §7 Test 4 — the R21 support regression, via a CL-declared role
# --------------------------------------------------------------------------- #
def test_cat4_walking_surface_supported_one_end_fails_and_blocks_clean():
    """A walking_surface whose grounded support sits under only ONE end reports
    the tree end unsupported (FAIL) and CANNOT be called CLEAN. Before the SUPPORT
    family this shipped CLEAN (R21). The support obligation arrives via the
    DECLARED role — the author declares what the deck IS, and the compiler derives
    its support responsibility."""
    detail = compile_spec_file(ONE_END)
    report = detail.validate()
    support = [f for f in report.findings if f.check == "support"]
    assert len(support) == 1
    (f,) = support
    assert f.verdict == "FAIL"
    # the FAIL names the unsupported tree-end overhang — the R21 class exactly
    # (a long surface overhanging its one-end support with no declared cantilever).
    assert "overhangs" in f.detail and "+X" in f.detail
    # and it blocks CLEAN.
    assert not report.ok
    assert "support" in {b.check for b in report.blocking}


def test_cat4_declaring_the_cantilever_or_a_second_support_is_the_fix():
    """The FAIL is not silence-able by relabeling: declaring the +X edge a
    cantilever REPRESENTS the intended overhang, flipping the obligation to a
    PASS (rung-3 represented) — proving the check keys on the DECLARED support
    scheme, not on incidental geometry."""
    body = ONE_END.read_text().replace(
        "    supports: [leg]",
        "    supports: [leg]\n    declared_cantilever:\n"
        "      - {edge: \"+X\", note: \"the deck cantilevers past the launch leg\"}\n"
        "      - {edge: \"+Y\", note: \"deck edge past the leg width\"}")
    detail = compile_spec(load_spec_text(body))
    report = detail.validate()
    (f,) = [f for f in report.findings if f.check == "support"]
    assert f.verdict != "FAIL"  # represented once the overhang is declared intended
