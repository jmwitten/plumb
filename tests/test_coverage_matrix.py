"""Coverage matrix + UNKNOWN/NOT-ANALYZED verdicts (Wave 3-1, task W31).

The matrix makes every report honest: a family with no check that ran is
UNKNOWN, never a silent PASS. See ``detailgen.validation.coverage``.
"""

from pathlib import Path

import pytest

from detailgen.core import IN
from detailgen.spec.compiler import compile_spec_file
from detailgen.validation import Finding, ValidationReport
from detailgen.validation.coverage import (
    INVARIANT_FAMILIES,
    KIND_TO_FAMILY,
    PROVENANCE_ONLY_KINDS,
    PASS,
    FAIL,
    UNKNOWN,
    STANDING_NOTE,
    FamilyCoverage,
    UnmappedCheckKind,
    coverage_matrix,
    family_of,
    render_coverage_matrix_md,
)

ROOT = Path(__file__).resolve().parent.parent
DETAILS = ROOT / "details"


def _report(*findings: Finding) -> ValidationReport:
    r = ValidationReport("test")
    for f in findings:
        r.add(f)
    return r


def _find(kind: str, passed: bool = True) -> Finding:
    return Finding(kind, f"{kind} subject", passed, "detail")


# -- the canonical families, fixed order ---------------------------------

def test_families_are_the_canonical_set_in_fixed_order():
    # Task SUPPORT adds the eighth family, "Support/Stability representation",
    # placed at rung 3 of the epistemic ladder — after Load-path representation
    # (rung 2) and before Structural capacity (rung 4), so the report order reads
    # weakest-to-strongest support claim.
    # Task INSTALL adds the ninth family, "Fastener installability", placed
    # immediately after Construction completeness — it is that invariant's
    # installability rung (owner amendment #4: hardware that exists and
    # penetrates the right members is not construction-complete without a
    # represented, checkable installation method), with its own ladder
    # REPRESENTED < GEOMETRY-PROVEN < SEQUENCE-PROVEN (guardrail #6).
    assert INVARIANT_FAMILIES == (
        "Physical geometry",
        "Spatial intent",
        "Construction completeness",
        "Fastener installability",
        "Functional use",
        "Load-path representation",
        "Support/Stability representation",
        "Structural capacity",
        "Code compliance",
    )


def test_matrix_always_has_a_row_per_family_in_order():
    rows = coverage_matrix(_report(_find("interference")))
    assert [r.family for r in rows] == list(INVARIANT_FAMILIES)


# -- data-driven family mapping ------------------------------------------

def test_family_of_maps_every_kind_data_driven():
    assert family_of("interference") == "Physical geometry"
    assert family_of("dimension") == "Physical geometry"
    assert family_of("bearing") == "Construction completeness"
    assert family_of("contact") == "Construction completeness"
    assert family_of("through_hole") == "Construction completeness"
    assert family_of("floating") == "Construction completeness"
    # Connection-GENERATED checks inherit their family by KIND, so a
    # Connection can wire a new check without touching connection.py.
    assert family_of("connection_hardware") == "Construction completeness"
    # INSTALL v1: the three installability kinds — pinned positively so a
    # KIND_TO_FAMILY drift fails HERE, loudly, not just via UnmappedCheckKind
    # at whatever call site happens to run first.
    assert family_of("install_method") == "Fastener installability"
    assert family_of("install_termination") == "Fastener installability"
    assert family_of("install_access") == "Fastener installability"


def test_unmapped_kind_is_a_loud_error_not_a_silent_escape():
    # An unmapped check kind must not silently vanish from the matrix.
    with pytest.raises(UnmappedCheckKind, match="totally_new_kind"):
        family_of("totally_new_kind")


def test_every_kind_emitted_by_the_four_details_is_mapped():
    """No check kind any shipped detail can emit may escape the matrix: each
    is either mapped to a family or explicitly a provenance-only exclusion."""
    kinds = set()
    for fname in ("rock_anchor", "tree_attachment", "trolley_launch", "platform"):
        rep = compile_spec_file(DETAILS / f"{fname}.spec.yaml").validate()
        kinds |= {f.check for f in rep.findings}
    unaccounted = kinds - set(KIND_TO_FAMILY) - PROVENANCE_ONLY_KINDS
    assert not unaccounted, f"unaccounted check kinds escape the coverage matrix: {unaccounted}"


def test_mapped_and_provenance_only_are_disjoint():
    assert not (set(KIND_TO_FAMILY) & PROVENANCE_ONLY_KINDS)


# -- provenance-only findings (connection_override) excluded from the matrix

def test_provenance_only_kind_does_not_crash_or_certify_a_family():
    """``connection_override`` is a passed=True bookkeeping marker emitted by
    merge_into_spec's dedup (the supported incremental-Connection-adoption
    path), NOT an invariant check. It must NOT raise UnmappedCheckKind, and it
    must NOT inflate any family's checks_run — it carries no verdict."""
    assert "connection_override" in PROVENANCE_ONLY_KINDS
    rows = {r.family: r for r in coverage_matrix(
        _report(_find("interference", True), _find("connection_override", True)))}
    # Physical still PASS from the real interference check.
    assert rows["Physical geometry"].verdict == PASS
    assert rows["Physical geometry"].checks_run == 1
    # Construction is NOT certified by a provenance marker — it stays UNKNOWN.
    assert rows["Construction completeness"].verdict == UNKNOWN
    assert rows["Construction completeness"].checks_run == 0
    # The override kind appears in no family's ran_kinds.
    for r in rows.values():
        assert "connection_override" not in dict(r.ran_kinds)


def test_real_dedup_override_scenario_drives_through_coverage_matrix():
    """End-to-end: a hand-written bearings entry for the same pair a
    Connection generates → dedup fires → a real ``connection_override``
    Finding lands in report.findings (as it would via Detail.validate). The
    coverage matrix must handle it without crashing."""
    from detailgen.assemblies import (
        Connection, ConnectionType, DetailAssembly, compile_connections,
        merge_into_spec,
    )
    from detailgen.components import Washer

    a = DetailAssembly("two washers")
    lo = a.add(Washer(0.5 * IN, name="lo"))
    hi = a.add(Washer(0.5 * IN, name="hi"), at=(0, 0, lo.component.thickness))

    class _Bears(ConnectionType):
        label = "bears"
        def bearing_pairs(self, conn):
            return [(conn.parts[0], conn.parts[1], "Z", 1.0)]

    conn = Connection(kind=_Bears(), parts=[lo, hi], label="the real connection")
    generated = compile_connections(a, [conn])
    hand_spec = {"bearings": [(lo, hi, "Z", 999_999.0)]}
    spec = merge_into_spec(a, hand_spec, generated)

    from detailgen.validation import validate_assembly
    report = validate_assembly(a, **spec)
    for f in generated.findings:  # what Detail.validate does
        report.add(f)
    assert any(f.check == "connection_override" for f in report.findings)

    # Must not raise, and the override must not be counted as a check.
    rows = {r.family: r for r in report.coverage_matrix()}
    assert "connection_override" not in dict(rows["Construction completeness"].ran_kinds)


# -- verdict rules --------------------------------------------------------

def test_family_passes_only_when_a_check_ran_and_all_passed():
    rows = {r.family: r for r in coverage_matrix(_report(_find("interference", True)))}
    phys = rows["Physical geometry"]
    assert phys.verdict == PASS
    assert phys.checks_run >= 1


def test_family_fails_if_any_check_in_it_failed():
    rows = {r.family: r for r in coverage_matrix(
        _report(_find("interference", True), _find("dimension", False)))}
    assert rows["Physical geometry"].verdict == FAIL
    assert rows["Physical geometry"].failures == 1


def test_support_kind_maps_to_the_support_family():
    assert family_of("support") == "Support/Stability representation"


def test_support_fail_makes_the_family_fail():
    rows = {r.family: r for r in coverage_matrix(_report(_find("support", False)))}
    assert rows["Support/Stability representation"].verdict == FAIL


def test_support_unknown_finding_makes_the_family_unresolved_not_pass():
    """A support check that RAN but returned UNKNOWN (task SUPPORT) rolls the
    family up as UNKNOWN — UNRESOLVED (analyzed, not determinable, blocking) —
    never PASS and never NOT-ANALYZED. This is the honesty crux of the family."""
    from detailgen.validation.coverage import UNRESOLVED
    unknown = Finding("support", "walking surface deck: b", False,
                      "cannot determine", verdict="UNKNOWN")
    rows = {r.family: r for r in coverage_matrix(_report(unknown))}
    row = rows["Support/Stability representation"]
    assert row.verdict == UNRESOLVED
    assert row.verdict != UNKNOWN          # distinct from NOT-ANALYZED
    assert "not determinable" in row.note


def test_family_with_no_check_that_ran_is_unknown_not_pass():
    rows = {r.family: r for r in coverage_matrix(_report(_find("interference", True)))}
    for fam in ("Spatial intent", "Functional use", "Load-path representation",
                "Structural capacity", "Code compliance"):
        assert rows[fam].verdict == UNKNOWN, fam
        assert rows[fam].checks_run == 0


# -- ANTI-FAKE INVARIANT: removing every check of a family flips PASS->UNKNOWN

def test_removing_every_check_of_a_family_flips_pass_to_unknown():
    """The permits-vs-requires lesson applied to reporting. A family that
    PASSES today MUST become UNKNOWN — never silently stay PASS — once no
    check of that family runs. Proven by dropping the family's findings."""
    with_checks = _report(_find("interference", True), _find("bearing", True))
    before = {r.family: r for r in coverage_matrix(with_checks)}
    assert before["Physical geometry"].verdict == PASS

    # Remove every Physical-geometry check (no interference/dimension ran).
    phys_kinds = {k for k, v in KIND_TO_FAMILY.items() if v == "Physical geometry"}
    without = _report(*[f for f in with_checks.findings if f.check not in phys_kinds])
    after = {r.family: r for r in coverage_matrix(without)}
    assert after["Physical geometry"].verdict == UNKNOWN
    # Construction completeness (bearing) still ran and still passes.
    assert after["Construction completeness"].verdict == PASS


# -- provenance (P1/P4): each verdict carries which checks ran ------------

def test_verdict_carries_provenance_of_which_checks_ran():
    rows = {r.family: r for r in coverage_matrix(
        _report(_find("bearing", True), _find("through_hole", True),
                _find("through_hole", True)))}
    con = rows["Construction completeness"]
    ran = dict(con.ran_kinds)
    assert ran["bearing"] == 1
    assert ran["through_hole"] == 2
    assert con.note  # a human-readable derivation note


# -- wording rule + standing note ----------------------------------------

def test_standing_note_carries_the_not_analyzed_honesty():
    assert "NOT ANALYZED" in STANDING_NOTE
    assert "REPRESENTED" in STANDING_NOTE
    # never asserts safety
    assert "is safe" not in STANDING_NOTE.lower()


def test_rendered_markdown_contains_unknown_rows_and_not_analyzed_wording():
    md = render_coverage_matrix_md(_report(_find("interference", True)))
    assert "Coverage matrix" in md
    assert "NOT ANALYZED" in md
    # every family named
    for fam in INVARIANT_FAMILIES:
        assert fam in md
    # the six unanalyzed families render UNKNOWN (an interference-only report
    # analyses Physical geometry alone; even Construction completeness rows
    # here carry checks, leaving six families UNKNOWN incl. installability)
    assert md.count("UNKNOWN") >= 6
    assert STANDING_NOTE in md


# -- serialization (machine-readable payload) ----------------------------

def test_coverage_payload_is_json_serializable_and_ordered():
    import json
    payload = _report(_find("interference", True)).coverage_payload()
    assert [row["family"] for row in payload] == list(INVARIANT_FAMILIES)
    json.dumps(payload)  # must not raise
    phys = next(r for r in payload if r["family"] == "Physical geometry")
    assert phys["verdict"] == PASS
    assert phys["checks_run"] >= 1


# -- per-detail render surface (lifecycle) -------------------------------

def _load_detail(fname, cls):
    """Zero-arg factory compiling the detail's spec.yaml (the imperative mirrors
    are retired; ``cls`` retained for call-site parity)."""
    return lambda: compile_spec_file(DETAILS / f"{fname}.spec.yaml")


def test_rendered_detail_report_carries_the_matrix(tmp_path):
    """A generated per-detail report contains the UNKNOWN rows and the
    NOT-ANALYZED wording — the whole matrix rides on every render, at the
    lifecycle level, so no detail can ship a report without it."""
    d = _load_detail("trolley_launch", "TrolleyLaunch")()
    out = d.render(tmp_path / "trolley")
    report_md = (out / "validation_report.md").read_text()
    assert "Coverage matrix" in report_md
    assert "NOT ANALYZED" in report_md
    assert STANDING_NOTE in report_md
    # the six families with no check show UNKNOWN (the trolley declares no
    # fastener contracts, so Fastener installability is honestly among them)
    assert report_md.count("UNKNOWN") >= 6
    # machine-readable payload written alongside
    import json
    payload = json.loads((out / "coverage_matrix.json").read_text())
    assert [r["family"] for r in payload] == list(INVARIANT_FAMILIES)


def test_detail_lifecycle_exposes_coverage_matrix():
    d = _load_detail("trolley_launch", "TrolleyLaunch")()
    rows = d.coverage_matrix()
    by_fam = {r.family: r for r in rows}
    assert by_fam["Physical geometry"].verdict == PASS
    assert by_fam["Construction completeness"].verdict == PASS
    assert by_fam["Structural capacity"].verdict == UNKNOWN
    assert by_fam["Code compliance"].verdict == UNKNOWN


def test_declared_order_clears_carry_the_marker_on_every_summary_surface():
    """Declared-trust visibility (task CPGCORE, STEPDOC owner amendment 3 —
    a PRODUCT requirement, not a doc footnote): a family counting a
    declared-order clear as resolved must carry the declared marker on
    EVERY surface its verdict renders — the note, the verdict cell of the
    markdown and HTML matrices, and both headline forms — so "resolved"
    never reads as "proved". The pure ``verdict`` token stays unmarked for
    programmatic consumers (CSS classes, gating)."""
    from detailgen.validation.coverage import (
        coverage_matrix, render_coverage_matrix_html,
        render_coverage_matrix_md, render_headline_html,
        render_headline_line)

    rep = ValidationReport("marker")
    rep.add(Finding(
        "install_access", "j: screw", True,
        "clear tool corridor (geometry proven at the DECLARED build order "
        "— declared, not sequence-proven)", declared_order=True))
    rows = coverage_matrix(rep)
    row = next(r for r in rows if r.family == "Fastener installability")
    assert row.verdict == PASS               # the algebra token is unmarked
    assert row.declared == 1
    marker = "resolved on paper, declared, not sequence-proven"
    assert marker in row.note
    assert marker in row.verdict_display
    assert marker in render_coverage_matrix_md(rep)
    assert marker in render_coverage_matrix_html(rep)
    assert "resolved, not proved" in render_headline_line(rows)
    assert marker in render_headline_html(rows)
    # a family with NO declared-order lean renders its bare verdict —
    # and the count is keyed on the STRUCTURED flag (review F-2), so even
    # a finding whose TEXT happens to contain the marker wording does not
    # count without the flag (re-wording the rung sentence can never
    # silently move the summaries).
    bare = ValidationReport("bare")
    bare.add(Finding("install_access", "j: screw", True,
                     "clear tool corridor (GEOMETRY-PROVEN)"))
    bare.add(Finding("install_access", "j: screw 2", True,
                     "text mentioning at the DECLARED build order only"))
    row2 = next(r for r in coverage_matrix(bare)
                if r.family == "Fastener installability")
    assert row2.declared == 0 and row2.verdict_display == PASS
