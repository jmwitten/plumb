"""Conditional field-installation projection for the DV72 cabinet."""

from dataclasses import replace
from html.parser import HTMLParser
import inspect
from pathlib import Path
import re

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
    assert "Cabinet-to-bracket detail: __________________" in html
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
        "Wall construction",
        "Framing / blocking",
        "Utilities",
        "Rakks product revision",
        "Structural fastener schedule",
        "Cabinet-to-bracket detail",
        "Responsible approvals",
        "Level",
        "Plumb",
        "Diagonal / square check",
        "Three-plane support contact",
        "Wall gaps",
        "Fastener witness marks / counts",
        "Cabinet restraint",
        "Service access",
        "Deviations",
        "Installer",
        "Reviewer",
        "Date",
    ):
        assert label in html


def test_placement_projects_typed_service_and_drawer_envelopes(project):
    html = build_double_vanity_installation_guide(
        project, related_documents=(),
    )
    for path in project.model.plumbing_paths:
        envelope = path.service_envelope
        assert f'data-service-envelope="{envelope.envelope_id}"' in html
        assert f'data-x0-mm="{envelope.x0_mm:.1f}"' in html
        assert f'data-x1-mm="{envelope.x1_mm:.1f}"' in html
    for drawer in project.model.drawers:
        assert f'data-drawer-envelope="{drawer.drawer_id}"' in html
        assert f'data-closed-clearance-mm="{drawer.closed_clearance_mm:.1f}"' in html


def test_drawer_clearance_mutation_moves_service_imagery(project):
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
    pattern = re.compile(
        rf'<path[^>]+data-drawer-envelope="{re.escape(drawer.drawer_id)}"[^>]+>'
    )
    assert pattern.search(baseline)
    assert pattern.search(changed)
    assert pattern.search(baseline).group() != pattern.search(changed).group()


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
