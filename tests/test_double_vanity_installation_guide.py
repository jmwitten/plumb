"""Conditional field-installation projection for the DV72 cabinet."""

from dataclasses import replace
from html.parser import HTMLParser
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess

import pytest

from detailgen.packs import compile_project_file
from detailgen.packs.cabinetry.double_vanity import RAKKS_EH_1818_LV
from detailgen.packs.cabinetry.double_vanity_installation_guide import (
    build_double_vanity_installation_guide,
    installation_visible_extras,
    project_double_vanity_installation_manual,
)
from detailgen.rendering.consumer_pages import visible_instructional_words
from detailgen.rendering.instruction_panels import RelatedDocumentLink


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT / "tests/fixtures/cabinetry"
    / "floating_double_sink_four_drawer.project.yaml"
)


@pytest.fixture(scope="module")
def project():
    return compile_project_file(FIXTURE)


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []

    def handle_data(self, data):
        self.rows.append(data)


def _visible_text(html):
    parser = _VisibleText()
    parser.feed(html)
    return " ".join(parser.rows)


class _RenderedVisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"style", "script"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag):
        if tag in {"style", "script"}:
            self.hidden_depth -= 1

    def handle_data(self, data):
        if not self.hidden_depth:
            self.rows.append(data)


def _rendered_visible_text(html):
    parser = _RenderedVisibleText()
    parser.feed(html)
    return " ".join(parser.rows)


def test_guide_is_bounded_and_stop_precedes_actions(project):
    manual = project_double_vanity_installation_manual(
        project, related_documents=(),
    )
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    assert len(manual.pages) <= 8
    assert html.count('class="sheet ') == len(manual.pages)
    assert html.index('data-page-kind="hold"') < html.index(
        'data-action-illustration="true"'
    )
    assert visible_instructional_words(
        manual, extra_texts=installation_visible_extras(project),
    ) <= 1500
    assert "INSTALLATION HOLD" in html


def test_actual_rendered_guide_is_at_most_1500_visible_words(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    words = re.findall(r"\b[\w’'-]+\b", _rendered_visible_text(html))

    assert "EMPTY CABINET MOUNTED — FOLLOW-ON WORK HELD" in _rendered_visible_text(html)
    assert len(words) <= 1500


def test_guide_stops_at_empty_mounted_cabinet(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    assert "empty cabinet mounted" in html.lower()
    assert "STOP BEFORE COUNTERTOP" in html
    for forbidden in (
        "install the countertop", "install the sink", "connect the trap",
        "install the drawers", "load the vanity", "commission the vanity",
    ):
        assert forbidden not in html.lower()


def test_supports_and_rear_rail_are_typed(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    for support in project.model.support_layout.supports:
        assert f'data-support-id="{support.support_id}"' in html
        assert f'data-axis-mm="{support.x_axis_mm:.1f}"' in html
    assert "left end" in html
    assert "center divider" in html
    assert "right end" in html
    assert "zero gravity credit" in html


def test_mount_identity_and_revision_are_projected_without_duplicate_literal(project):
    import detailgen.packs.cabinetry.double_vanity_installation_guide as guide

    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    revision = project.model.mount_reference.adapter_id.rpartition("@")[2]
    assert project.model.mount_reference.sku in html
    assert revision in html
    assert "EH-1818-LV" not in inspect.getsource(guide)


def test_guide_does_not_invent_connection_hardware(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    assert "Structural fastener schedule: __________________" in html
    assert "Cabinet case/interface detail: __________________" in html
    assert "connection capacity remains unproved" in html


def test_load_case_is_typed_but_never_claims_connection_capacity(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    load = project.model.load_case
    assert f"{load.unfactored_total_lb:.1f} lb unfactored" in html
    assert f"{load.factored_total_lb:.1f} lb factored" in html
    assert "no connection capacity is assigned" in html


def test_held_actions_are_conditional(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    actions = re.findall(
        r'<article class="frame action".*?</article>', html, re.S,
    )
    assert actions
    assert all(
        "CONDITIONAL — RELEASE RECORD REQUIRED" in row
        for row in actions
    )


def test_post_hold_record_page_is_conditional(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    record = re.search(
        r'<section class="sheet record".*?</section>', html, re.S,
    )
    assert record
    assert "CONDITIONAL — RELEASE RECORD REQUIRED" in record.group()


@pytest.mark.parametrize(
    "href",
    (
        "file://review.html",
        "javascript:alert(1).html",
        "https://example.com/review.html",
        "../review.html",
        "subdir/review.html",
        "/tmp/review.html",
    ),
)
def test_related_documents_require_relative_html_basenames(project, href):
    with pytest.raises(ValueError, match="relative HTML basename"):
        project_double_vanity_installation_manual(
            project,
            related_documents=(RelatedDocumentLink("Review", href),),
        )


def test_guide_is_self_contained_and_hides_machine_identifiers(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    visible = _visible_text(html)
    assert "file://" not in html
    assert not re.search(r'<(?:script|img)[^>]+src=["\']https?://', html)
    assert not re.search(r'<link[^>]+href=["\']https?://', html)
    assert "@2022.1.0" not in visible
    for support in project.model.support_layout.supports:
        assert support.support_id not in visible


def test_inspection_record_contains_every_approved_field(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    for label in (
        "FIELD RELEASE — RELEASED / REJECTED",
        "STRUCTURAL RELEASE — RELEASED / REJECTED",
        "Structural fastener schedule",
        "Cabinet case/interface detail",
        "Tolerance / shim schedule",
        "Level",
        "Plumb",
        "Diagonal / square check",
        "Accepted interface contact / restraint",
        "Fastener witness record",
        "Handoff status",
        "Deviations",
        "Installer",
        "Reviewer",
        "Acceptance date",
    ):
        assert label in html


def test_print_layout_restores_two_column_record_and_fixed_footer(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    mobile_rule = html.index("@media(max-width:850px)")
    print_rule = html.index("@media print")
    print_css = html[print_rule:html.index("</style>", print_rule)]

    assert print_rule > mobile_rule
    assert ".record-grid{grid-template-columns:1fr 1fr}" in print_css
    assert ".hold-fields,.release-group{grid-template-columns:1fr 1fr}" in print_css
    assert "footer{position:absolute;margin-top:0}" in print_css


def test_placement_projects_owner_assumed_rough_ins_without_service_approval(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    for point in project.model.assumed_site.wastes + project.model.assumed_site.supplies:
        assert f'data-rough-in="{point.point_id}"' in html
        assert f'data-provenance="{point.provenance}"' in html
    assert 'data-service-envelope="' not in html
    assert 'data-drawer-envelope="' not in html


def test_drawer_clearance_mutation_does_not_become_service_approval(project):
    drawer = project.model.drawers[0]
    changed_drawer = replace(
        drawer, closed_clearance_mm=drawer.closed_clearance_mm + 6.0,
    )
    changed_project = replace(
        project,
        model=replace(
            project.model,
            drawers=(changed_drawer,) + project.model.drawers[1:],
        ),
    )
    baseline = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    changed = build_double_vanity_installation_guide(
        changed_project, related_documents=(),
    )
    assert baseline == changed
    assert "dynamic access remains separately held" in changed


def test_support_axis_mutation_fails_projection_coherence(project):
    layout = project.model.support_layout
    shifted = replace(
        layout.supports[1], x_axis_mm=layout.supports[1].x_axis_mm + 25.0,
    )
    changed = replace(
        project,
        model=replace(
            project.model,
            support_layout=replace(
                layout, supports=(layout.supports[0], shifted, layout.supports[2]),
            ),
        ),
    )
    with pytest.raises(ValueError, match="support axes"):
        build_double_vanity_installation_guide(
            changed, related_documents=(),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("bearing_z_mm", 25.0),
        ("wall_y_mm", 25.0),
        ("authority", "forged_authority"),
    ),
)
def test_every_support_envelope_fact_is_consumed_or_rejected(
    project, field, value,
):
    layout = project.model.support_layout
    changed_support = replace(layout.supports[0], **{
        field: (
            getattr(layout.supports[0], field) + value
            if isinstance(value, float) else value
        ),
    })
    changed = replace(
        project,
        model=replace(
            project.model,
            support_layout=replace(
                layout, supports=(changed_support,) + layout.supports[1:],
            ),
        ),
    )

    with pytest.raises(ValueError, match="support envelope facts"):
        build_double_vanity_installation_guide(
            changed, related_documents=(),
        )


def test_supports_project_typed_countertop_bearing_wall_and_authority(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )

    for support in project.model.support_layout.supports:
        assert f'data-bearing-z-mm="{support.bearing_z_mm:.1f}"' in html
        assert f'data-wall-y-mm="{support.wall_y_mm:.1f}"' in html
        assert f'data-authority="{support.authority}"' in html
    assert "countertop-underside / bracket-arm datum" in html
    assert "wall plane" in html
    assert "horizontal projection/depth" in html
    assert "fastening per accepted product revision" in html
    support_picture = re.search(
        r'<svg[^>]+data-support-layout="true".*?</svg>', html, re.S,
    ).group()
    assert "<circle" not in support_picture


def test_support_svg_projects_typed_load_path_without_capacity(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    support_picture = re.search(
        r'<svg[^>]+data-support-layout="true".*?</svg>', html, re.S,
    ).group()

    assert 'data-load-path="countertop-arm-diagonal-wall"' in support_picture
    assert 'class="load-arrow"' in support_picture
    assert "countertop support load" in support_picture
    assert "diagonal" in support_picture
    assert "wall fasteners / framing receive forces" in support_picture
    for forbidden in ("capacity", "reaction distribution", "hole pattern"):
        assert forbidden not in support_picture.lower()


def test_load_path_and_handling_copy_does_not_claim_bottom_bearing(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    lower = html.lower()

    assert "position the empty case below/around the accepted countertop-support arms" in lower
    assert "accepted case/interface detail" in lower
    assert "accepted-plan handling/support/restraint placeholder" in lower
    assert "protection / clearance" in lower
    assert "cabinet case/interface detail" in lower
    assert "cabinet-to-bracket detail" not in lower
    assert "comparison basis only—not allowable cabinet/installation load" in lower
    for forbidden in (
        "lift the protected empty cabinet onto",
        "seated on all three planes",
        "continuously supported at three planes",
        "two-person lift",
        "temporary restraint without",
        "three-plane support contact",
    ):
        assert forbidden not in lower


def test_prework_release_is_separate_and_controls_handling(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    hold = re.search(
        r'<section class="sheet hold".*?</section>', html, re.S,
    ).group()
    record = re.search(
        r'<section class="sheet record".*?</section>', html, re.S,
    ).group()

    for required in (
        "FIELD RELEASE — RELEASED / REJECTED",
        "STRUCTURAL RELEASE — RELEASED / REJECTED",
        "Reviewer / signature / date",
        "Document revision / attachment IDs",
        "Accepted product revision / document ID",
        "Cabinet case/interface detail ID",
        "Tolerance / shim schedule ID",
        "Actual empty-case handling weight",
        "Accepted lift / temporary-support / restraint plan",
        "Equipment / crew",
        "Attachment / removal / handoff criteria",
        "Wall construction",
        "Framing / blocking verification",
        "Utilities / rough-in verification",
    ):
        assert required in hold
    assert "FIELD RELEASE — RELEASED / REJECTED" not in record
    assert "pre-work release record governs" in hold
    assert "stop and obtain a superseding field and structural release" in hold


def test_required_release_findings_use_authority_aware_reader_copy(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    expected = (
        ("site_survey", "Site comparison", "PRE-WORK HOLD"),
        ("wall_mount", "Wall mount", "PRE-WORK HOLD"),
        ("dynamic_access", "Dynamic access", "FOLLOW-ON HOLD — not required for empty-cabinet mounting"),
        ("plumbing_approval", "Plumbing approval", "FOLLOW-ON HOLD — not required for empty-cabinet mounting"),
        ("drawer_derivation", "Drawer fabrication and access", "FOLLOW-ON HOLD — not required for empty-cabinet mounting"),
    )
    visible = _rendered_visible_text(html)
    for suffix, label, status in expected:
        finding = project.report.by_rule(f"double_vanity.release.{suffix}")
        assert f'data-release-rule="{finding.rule}"' in html
        assert f'data-verdict="{finding.verdict}"' in html
        assert label in visible
        assert status in visible
        assert finding.message not in visible
        assert suffix not in visible
    assert "prepared for review only" in visible
    assert "fabricator acceptance pending" in visible.lower()
    assert "conditionally released static cuts" not in visible.lower()
    assert "owner-assumed rough-in conflict comparison" in html
    assert "not service-access approval" in html
    assert "dynamic access remains separately held" in html
    assert "Both plumbing and drawer envelopes clear" not in html
    assert ">Service access<" not in html


def test_failed_required_release_finding_changes_guide(project):
    rule = "double_vanity.release.dynamic_access"
    findings = tuple(
        replace(finding, verdict="FAIL", message="Dynamic access conflict found.")
        if finding.rule == rule else finding
        for finding in project.report.findings
    )
    changed = replace(project, report=replace(project.report, findings=findings))

    html = build_double_vanity_installation_guide(
        changed, related_documents=(),
    )
    assert f'data-release-rule="{rule}"' in html
    assert 'data-verdict="FAIL"' in html
    visible = _rendered_visible_text(html)
    assert "Dynamic access conflict found." not in visible
    assert "FOLLOW-ON FAIL — STOP BEFORE FOLLOW-ON WORK" in visible
    assert "not required for empty-cabinet mounting" in visible


def test_field_datums_use_defined_origin_dual_units_and_practical_precision(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )

    assert "x = 0 at finished left end of assumed wall" in html
    assert "y = 0 at project datum 25 mm / 1 in in front of modeled vanity front" in html
    assert "y increases toward wall" in html
    assert "countertop top datum" in html
    assert "countertop-underside / bracket-arm datum" in html
    assert "30 mm / 1 3/16 in counter thickness" in html
    assert "619 mm / 24 3/8 in" in html
    assert "1,524 mm / 60 in" in html
    assert "2,429 mm / 95 5/8 in" in html
    assert "876.3 mm" not in html


def test_product_authority_package_handoff_and_mobile_svg_contract(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )

    assert "selected record: 2022.1.0" in html
    assert "current confirmation target: 2024.1.1" in html
    assert "confirmation target only—not approved until recorded" in html
    assert "toeing" not in html.lower()
    assert "Rakks_EH_Vanity_Support_Bracket_2022.1.0.pdf" in html
    assert "Rakks_EH_Vanity_Support_Bracket_2024.1.1.pdf" in html
    for name in (
        "dv72_review_installation.html",
        "dv72_assembly_service.html",
        "dv72_fabrication_coordination.html",
        "dv72_validation_sources.html",
        "dv72_installation_guide.html",
    ):
        assert name in html
    assert 'class="svg-scroll"' in html
    assert ".svg-scroll{overflow-x:auto}" in html
    assert ".svg-scroll svg{min-width:520px}" in html
    assert "Swipe/scroll horizontally to inspect the full diagram" in html
    assert "break-inside:avoid" in html
    assert ".record-row" in html and "min-height:.7in" in html
    assert ".frame.action{padding:.1in" in html
    assert ".frame.action svg{max-height:1.65in}" in html


def test_final_record_captures_acceptance_and_interface_evidence(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    record = re.search(
        r'<section class="sheet record".*?</section>', html, re.S,
    ).group()

    for required in (
        "Completion acceptance — ACCEPTED / REJECTED",
        "Authorized reviewer role",
        "Authorized reviewer signature",
        "Acceptance date",
        "FIELD release attachment ID",
        "STRUCTURAL release attachment ID",
        "Wall gaps",
        "Accepted interface contact / restraint",
        "Fastener count vs accepted schedule",
        "Cabinet restraint",
        "Observed rough-in conflict — YES / NO",
        "not service-access approval",
    ):
        assert required in record
    assert "service-access acceptance" not in record


def test_release_and_record_field_text_is_readable_and_print_not_clipped_by_css(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )

    assert re.search(r"\.release-findings\{[^}]*font-size:10px", html)
    assert re.search(r"\.hold-fields p\{[^}]*font-size:10px", html)
    print_css = html[html.index("@media print"):html.index("</style>")]
    assert re.search(r"\.sheet\{[^}]*overflow:visible", print_css)
    assert "overflow:hidden" not in print_css


def test_local_chrome_mobile_metrics_and_letter_pdf(project, tmp_path):
    chrome_candidates = (
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        *(
            Path(path)
            for name in ("google-chrome", "chromium", "chromium-browser")
            if (path := shutil.which(name))
        ),
    )
    chrome = next((path for path in chrome_candidates if path.exists()), None)
    if chrome is None:
        pytest.skip("local Google Chrome is unavailable")

    def run_chrome(*args):
        process = subprocess.Popen(
            [str(chrome), "--headless=new", "--disable-gpu", "--no-sandbox",
             "--no-first-run", "--disable-extensions", *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=12)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=5)
        if not timed_out and process.returncode:
            raise subprocess.CalledProcessError(
                process.returncode, process.args, stdout, stderr,
            )
        return stdout.decode("utf-8", errors="replace")

    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    guide_path = tmp_path / "guide.html"
    guide_path.write_text(html)
    metrics_script = r'''<script>
const clipped = element => element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1;
const critical = [...document.querySelectorAll('.hold,.hold-fields,.release-findings,.record-row,.final-stop')];
const cue = document.querySelector('.scroll-cue');
const result = {
  cssWidth: document.body.clientWidth,
  pageOverflow: document.body.scrollWidth > document.body.clientWidth + 1,
  criticalClipped: critical.filter(clipped).length,
  scrollCueVisible: cue ? getComputedStyle(cue).display !== 'none' : false,
  sheets: document.querySelectorAll('.sheet').length
};
const metrics = document.createElement('pre');
metrics.id = 'qa-metrics';
metrics.textContent = JSON.stringify(result);
document.body.append(metrics);
</script>'''
    mobile_path = tmp_path / "guide-mobile.html"
    mobile_path.write_text(
        html.replace(
            "</head>",
            "<style>html,body{width:390px;max-width:390px}</style></head>",
        ).replace("</body>", metrics_script + "</body>")
    )
    dump = run_chrome(
        f"--user-data-dir={tmp_path / 'chrome-mobile'}",
        "--hide-scrollbars", "--window-size=390,844",
        "--virtual-time-budget=1000", "--dump-dom",
        mobile_path.as_uri(),
    )
    match = re.search(r'<pre id="qa-metrics">(.*?)</pre>', dump, re.S)
    assert match, dump[-1000:]
    metrics = json.loads(match.group(1).replace("&quot;", '"'))
    assert metrics == {
        "cssWidth": 390,
        "pageOverflow": False,
        "criticalClipped": 0,
        "scrollCueVisible": True,
        "sheets": 7,
    }

    pdf_path = tmp_path / "guide.pdf"
    run_chrome(
        f"--user-data-dir={tmp_path / 'chrome-print'}",
        f"--print-to-pdf={pdf_path}", "--no-pdf-header-footer",
        guide_path.as_uri(),
    )
    pdfinfo = shutil.which("pdfinfo")
    assert pdfinfo, "Poppler pdfinfo is required when local Chrome is present"
    info = subprocess.run(
        [pdfinfo, str(pdf_path)], check=True, capture_output=True, text=True,
    ).stdout
    assert re.search(r"^Pages:\s+7$", info, re.M)
    size = re.search(
        r"^Page size:\s+([0-9.]+) x ([0-9.]+) pts \(letter\)$",
        info, re.M,
    )
    assert size
    assert float(size.group(1)) == pytest.approx(612, abs=0.5)
    assert float(size.group(2)) == pytest.approx(792, abs=0.5)


@pytest.mark.parametrize(
    ("mutate", "message"),
    (
        (
            lambda project: replace(
                project,
                model=replace(
                    project.model,
                    support_layout=replace(
                        project.model.support_layout,
                        supports=project.model.support_layout.supports[:2],
                    ),
                ),
            ),
            "exactly three supports",
        ),
        (
            lambda project: replace(
                project,
                model=replace(
                    project.model,
                    support_layout=replace(
                        project.model.support_layout,
                        rear_rail_gravity_credit_lb=1.0,
                    ),
                ),
            ),
            "zero gravity credit",
        ),
        (
            lambda project: replace(
                project,
                model=replace(
                    project.model,
                    mount_reference=replace(
                        RAKKS_EH_1818_LV,
                        adapter_id="rakks_eh_1818_lv@unsupported",
                    ),
                ),
            ),
            "Rakks identity/revision",
        ),
        (
            lambda project: replace(
                project,
                model=replace(
                    project.model,
                    assumed_site=replace(
                        project.model.assumed_site, field_verified=True,
                    ),
                ),
            ),
            "field-verification claim",
        ),
        (
            lambda project: replace(
                project,
                model=replace(
                    project.model,
                    release=replace(
                        project.model.release,
                        installation_status="PASS",
                    ),
                ),
            ),
            "installation authority",
        ),
    ),
)
def test_projection_rejects_incoherent_typed_authority(project, mutate, message):
    with pytest.raises(ValueError, match=message):
        project_double_vanity_installation_manual(
            mutate(project), related_documents=(),
        )


def test_projection_rejects_wrong_pack(project):
    wrong = replace(project, pack_id="vanity.floating")
    with pytest.raises(
        ValueError, match="DV72 installation guide requires vanity.double_sink",
    ):
        project_double_vanity_installation_manual(wrong, related_documents=())
