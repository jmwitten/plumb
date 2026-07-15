"""Conditional, print-first cabinet installation guide for DV72.

The guide is a typed projection of the compiled double-vanity model.  It
deliberately stops at an empty, restrained cabinet and carries no authority
for structural fastener selection, cabinet-to-bracket attachment, stone,
fixtures, plumbing, drawers, loading, or commissioning.
"""

from __future__ import annotations

from dataclasses import replace
from html import escape

from ...rendering.action_frames import ActionFrame, FrameIllustration
from ...rendering.consumer_pages import ConsumerManual, compose_consumer_manual
from ...rendering.instruction_panels import (
    RecordField,
    RelatedDocumentLink,
    _relative_html_basename,
)
from .double_vanity import RAKKS_EH_1818_LV


_CONDITIONAL = "CONDITIONAL — RELEASE RECORD REQUIRED"

_INVENTORY_STATIC_TEXTS = (
    "Crew: two cabinet installers plus the named field and structural reviewers.",
    "Tools: laser or spirit level, plumb reference, tape, square, shims, temporary support, and the tools named by accepted schedules.",
    "Boundary: cabinet only. Countertop, sinks, plumbing, drawers, contents, loading, and use remain outside this guide.",
    "Structural fastener schedule: __________________",
    "Cabinet-to-bracket detail: __________________",
)

_FRAME_NOTES = {
    "layout_wall": (
        "WHY The finished-floor datum, counter datum, and case-member axes keep the field comparison tied to the compiled cabinet geometry.",
        "VERIFY Record the wall and floor comparison, backing limits, utilities, rough-ins, and all three accepted support stations.",
        "STOP Stop if any site measurement, backing condition, obstruction, utility, or rough-in differs from the accepted release record.",
    ),
    "install_supports": (
        "WHY The three Rakks envelopes are the modeled primary gravity path; the wall connection and reaction distribution are not proved here.",
        "VERIFY Check accepted product revision, count, station, projection, level, wall contact, backing, utilities, and schedule-controlled locations.",
        "STOP Stop if the product, wall, backing, pilot/toe method, fastener schedule, or any support station is not accepted in writing.",
    ),
    "place_cabinet": (
        "WHY An empty two-person lift limits handling risk and exposes contact at the left end, center divider, and right end.",
        "VERIFY Confirm the case is empty, protected, seated on all three planes, temporarily restrained, and clear of every service envelope.",
        "STOP Stop if the cabinet rocks, bridges a support, deforms, or conflicts with plumbing, drawer, wall, or tool-access envelopes.",
    ),
    "restrain_cabinet": (
        "WHY The accepted cabinet-to-support detail restrains the case; the rear rail provides positioning and lateral restraint only.",
        "VERIFY Apply only the signed detail and schedule. Confirm the continuous rear rail remains lateral-only with zero gravity credit.",
        "STOP Stop when a detail, location, substrate, tool path, or observed fit differs; connection capacity remains unproved.",
    ),
    "inspect_cabinet": (
        "WHY The signed record preserves the field comparison and the condition of the empty mounted cabinet before follow-on work.",
        "VERIFY Record level, plumb, square, three-plane contact, gaps, schedule witness marks/counts, restraint, access, deviations, installer, reviewer, and date.",
        "STOP STOP BEFORE COUNTERTOP, SINKS, PLUMBING, DRAWERS, LOADING, OR USE.",
    ),
}

_RECORD_FIELDS = (
    RecordField("Wall construction", "Observed condition and accepted basis"),
    RecordField("Framing / blocking", "Verified locations, extents, and evidence"),
    RecordField("Utilities", "Located, protected, and clear of accepted work"),
    RecordField("Rakks product revision", "Accepted revision and evidence"),
    RecordField("Structural fastener schedule", "Reference and approving reviewer"),
    RecordField("Cabinet-to-bracket detail", "Reference and approving reviewer"),
    RecordField("Responsible approvals", "Field, structural, and installation approvals"),
    RecordField("Level", "Reading and tolerance"),
    RecordField("Plumb", "Reading and tolerance"),
    RecordField("Diagonal / square check", "Both diagonals or accepted check"),
    RecordField("Three-plane support contact", "Left end / center divider / right end"),
    RecordField("Wall gaps", "Locations and accepted treatment"),
    RecordField("Fastener witness marks / counts", "Compared with approved schedule"),
    RecordField("Cabinet restraint", "Compared with approved detail"),
    RecordField("Service access", "Both plumbing and drawer envelopes clear"),
    RecordField("Deviations", "None, or attach accepted disposition"),
    RecordField("Installer", "Printed name and signature"),
    RecordField("Reviewer", "Printed name and signature"),
    RecordField("Date", "YYYY-MM-DD"),
)


def _validate_installation_projection(project) -> None:
    """Reject stale geometry or authority before rendering field guidance."""

    if project.pack_id != "vanity.double_sink":
        raise ValueError("DV72 installation guide requires vanity.double_sink")

    model = project.model
    layout = model.support_layout
    supports = layout.supports
    if len(supports) != 3:
        raise ValueError("DV72 installation guide requires exactly three supports")

    expected_axes = {
        role: model.part(role).at_mm[0] + model.part(role).thickness_mm / 2
        for role in ("left_end", "center_divider", "right_end")
    }
    if (
        {support.alignment_role for support in supports} != set(expected_axes)
        or len({support.support_id for support in supports}) != 3
        or any(
            abs(support.x_axis_mm - expected_axes[support.alignment_role]) > 1e-6
            for support in supports
        )
    ):
        raise ValueError(
            "DV72 support axes must match left end, center divider, and right end"
        )

    if layout.rear_rail_gravity_credit_lb != 0.0:
        raise ValueError("DV72 rear rail must retain zero gravity credit")

    mount = model.mount_reference
    if mount != RAKKS_EH_1818_LV:
        raise ValueError("DV72 guide has unsupported Rakks identity/revision")
    if any(
        support.vertical_leg_mm != mount.width_mm
        or support.horizontal_leg_mm != mount.depth_mm
        or support.required_screws != mount.required_screws_per_bracket
        for support in supports
    ):
        raise ValueError("DV72 support geometry does not match the Rakks record")

    if (
        model.assumed_site != model.section.assumed_site
        or model.assumed_site.field_verified
        or model.section.assumed_site.field_verified
        or model.assumed_site.provenance != "owner_assumed"
    ):
        raise ValueError("DV72 guide rejects false field-verification claims")

    release = model.release
    release_findings = {
        finding.rule: finding.verdict for finding in project.report.findings
        if finding.rule.startswith("double_vanity.release.")
    }
    if (
        release.installation_status != "HOLD_FIELD_VERIFY"
        or release.trade_status != "HOLD_RESPONSIBLE_TRADE_APPROVAL"
        or release.commissioning_status != "HOLD_COMMISSIONING"
        or release_findings.get("double_vanity.release.site_survey") != "UNKNOWN"
        or release_findings.get("double_vanity.release.wall_mount") != "UNKNOWN"
    ):
        raise ValueError("DV72 guide detected contradictory installation authority")

    if (
        {path.bay_id for path in model.plumbing_paths} != {"left", "right"}
        or len(model.plumbing_paths) != 2
        or any(
            path.service_envelope.authority != "provisional_study_target"
            for path in model.plumbing_paths
        )
        or len(model.drawers) != 4
        or {(drawer.bay_id, drawer.level) for drawer in model.drawers} != {
            ("left", "upper"), ("left", "lower"),
            ("right", "upper"), ("right", "lower"),
        }
        or any(drawer.dynamic_verified for drawer in model.drawers)
        or any(
            drawer.closed_clearance_mm is None
            or drawer.closed_clearance_mm <= 0.0
            or drawer.full_extension_clearance_mm is not None
            or drawer.removal_clearance_mm is not None
            for drawer in model.drawers
        )
    ):
        raise ValueError("DV72 guide detected contradictory service-envelope authority")

    if (
        layout.gravity_path != "rakks_eh_primary"
        or layout.rear_rail_role != "positioning_and_lateral_only"
        or layout.fastener_connection_capacity_lb is not None
        or layout.backing_verification != "UNKNOWN"
        or layout.product_revision_approval != "UNKNOWN"
        or layout.fastener_installation != "UNKNOWN"
        or layout.structural_approval != "UNKNOWN"
    ):
        raise ValueError("DV72 guide detected contradictory installation authority")


def _installation_frames(project) -> tuple[ActionFrame, ...]:
    model = project.model
    vanity = model.section.vanity
    support_count = len(model.support_layout.supports)
    frame_data = (
        (
            "layout_wall",
            "Compare the field wall with the assumed basis. Establish the finished-floor and finished-counter datums, then transfer the left-end, center-divider, and right-end support axes.",
            (model.part("left_end").part_id, model.part("center_divider").part_id, model.part("right_end").part_id),
        ),
        (
            "install_supports",
            f"Using the accepted structural schedule and current product record, place {support_count} support envelopes at the recorded axes and verify each horizontal arm, diagonal, and wall leg.",
            tuple(support.support_id for support in model.support_layout.supports),
        ),
        (
            "place_cabinet",
            "With two people, lift the protected empty cabinet onto the three support planes. Align the case members and apply temporary restraint without adding finish components.",
            tuple(model.part(role).part_id for role in ("left_end", "center_divider", "right_end")),
        ),
        (
            "restrain_cabinet",
            "Apply only the accepted cabinet-to-bracket detail. Use the continuous rear rail for positioning and lateral restraint; give it zero gravity credit.",
            (model.part("rear_mounting_rail").part_id,),
        ),
        (
            "inspect_cabinet",
            "Inspect and record the empty cabinet mounted level, plumb, square, continuously supported at three planes, restrained, accessible, and held before follow-on work.",
            tuple(model.part(role).part_id for role in ("left_end", "center_divider", "right_end", "rear_mounting_rail")),
        ),
    )
    frames = [ActionFrame(
        frame_id="installation_hold",
        caption=(
            "Do not begin field work until the site comparison, current product "
            "revision, structural fastener schedule, cabinet-to-bracket detail, "
            "and responsible approvals are recorded."
        ),
        source_step_ids=("double_vanity.release.site_survey", "double_vanity.release.wall_mount"),
        owned_events=(),
        focus_part_ids=(),
        hold="INSTALLATION HOLD — FIELD/STRUCTURAL RELEASE REQUIRED",
        warning="The owner-assumed site is not field verified; wall drilling and cabinet loading remain held.",
        is_hold_gate=True,
        show_picture_key=False,
    )]
    for index, (frame_id, caption, focus_ids) in enumerate(frame_data, 1):
        frames.append(ActionFrame(
            frame_id=frame_id,
            caption=caption,
            source_step_ids=(f"dv72.installation.{frame_id}",),
            owned_events=(),
            focus_part_ids=focus_ids,
            illustration=FrameIllustration(
                intent="operation_diagram", panel_index=index,
                diagram_id=frame_id,
            ),
            record_title=(
                "Signed empty-cabinet installation and hold record"
                if frame_id == "inspect_cabinet" else ""
            ),
            record_fields=(
                _RECORD_FIELDS if frame_id == "inspect_cabinet" else ()
            ),
        ))
    return tuple(frames)


def project_double_vanity_installation_manual(
    project,
    *,
    related_documents: tuple[RelatedDocumentLink, ...],
) -> ConsumerManual:
    if project.pack_id != "vanity.double_sink":
        raise ValueError("DV72 installation guide requires vanity.double_sink")
    _validate_installation_projection(project)
    related_documents = tuple(
        replace(
            link,
            href=_relative_html_basename(
                link.href, f"related_documents[{index}].href",
            ),
        )
        for index, link in enumerate(related_documents)
    )
    return compose_consumer_manual(
        frames=_installation_frames(project),
        title="DV72 — Cabinet Installation Guide",
        basename="dv72_installation_guide.html",
        letters=(),
        kit_gate="INSTALLATION HOLD — FIELD/STRUCTURAL RELEASE REQUIRED",
        cover_caption=(
            "Outcome: the empty cabinet is level, plumb, continuously "
            "supported at three accepted support planes, restrained "
            "against movement, recorded, and held before follow-on work."
        ),
        related_documents=related_documents,
    )


def installation_visible_extras(project) -> tuple[str, ...]:
    """Return renderer-only instructional text for the acceptance word count."""

    _validate_installation_projection(project)
    notes = tuple(
        text for frame_id in (
            "layout_wall", "install_supports", "place_cabinet",
            "restrain_cabinet", "inspect_cabinet",
        ) for text in _FRAME_NOTES[frame_id]
    )
    return _inventory_texts(project) + notes


def _inventory_texts(project) -> tuple[str, ...]:
    mount = project.model.mount_reference
    load = project.model.load_case
    revision = mount.adapter_id.rpartition("@")[2]
    product = (
        f"Product reference: {mount.manufacturer} {mount.sku} vanity support, "
        f"reference revision {revision}; confirm the accepted current revision "
        "before field work."
    )
    load_basis = (
        f"Load basis: {load.unfactored_total_lb:.1f} lb unfactored and "
        f"{load.factored_total_lb:.1f} lb factored model load; reaction "
        "distribution is unproved and no connection capacity is assigned."
    )
    return (
        _INVENTORY_STATIC_TEXTS[:2]
        + (product, load_basis)
        + _INVENTORY_STATIC_TEXTS[2:]
    )


def _sx(project, x_mm: float) -> float:
    vanity = project.model.section.vanity
    return 65.0 + 390.0 * (x_mm - vanity.x0_mm) / vanity.width_mm


def _cabinet_svg(project, *, action: bool = False) -> str:
    vanity = project.model.section.vanity
    width = 390.0
    height = 120.0
    attrs = ' data-action-illustration="true"' if action else ""
    members = "".join(
        f'<line x1="{_sx(project, project.model.part(role).at_mm[0] + project.model.part(role).thickness_mm / 2):.1f}" y1="90" '
        f'x2="{_sx(project, project.model.part(role).at_mm[0] + project.model.part(role).thickness_mm / 2):.1f}" y2="210" class="case-member"/>'
        for role in ("left_end", "center_divider", "right_end")
    )
    return (
        f'<svg viewBox="0 0 520 260" role="img" aria-label="Empty mounted cabinet"{attrs}>'
        '<title>Empty cabinet mounted on three support planes</title>'
        '<line x1="35" y1="220" x2="485" y2="220" class="wall"/>'
        f'<rect x="65" y="90" width="{width:.1f}" height="{height:.1f}" class="cabinet"/>{members}'
        '<text x="260" y="245" text-anchor="middle">EMPTY CABINET MOUNTED — FOLLOW-ON WORK HELD</text>'
        '</svg>'
    )


def _layout_svg(project) -> str:
    model = project.model
    vanity = model.section.vanity
    counter_top = vanity.bottom_elevation_mm + vanity.body_height_mm + vanity.countertop_thickness_mm
    supports = "".join(
        f'<g data-support-id="{escape(support.support_id, quote=True)}" data-axis-mm="{support.x_axis_mm:.1f}">'
        f'<line x1="{_sx(project, support.x_axis_mm):.1f}" y1="45" x2="{_sx(project, support.x_axis_mm):.1f}" y2="220" class="axis"/>'
        f'<text x="{_sx(project, support.x_axis_mm):.1f}" y="35" text-anchor="middle">{escape(support.alignment_role.replace("_", " "))}</text></g>'
        for support in model.support_layout.supports
    )
    return (
        '<svg viewBox="0 0 520 270" role="img" data-action-illustration="true">'
        '<title>Finished datums and three support axes</title>'
        '<line x1="35" y1="220" x2="485" y2="220" class="datum"/>'
        f'<text x="40" y="240">finished floor: {model.assumed_site.floor_elevation_mm:.1f} mm</text>'
        '<line x1="35" y1="75" x2="485" y2="75" class="datum"/>'
        f'<text x="40" y="68">finished counter datum: {counter_top:.1f} mm AFF</text>'
        f'{supports}</svg>'
    )


def _supports_svg(project) -> str:
    groups = "".join(
        f'<g transform="translate({70 + index * 150},25)" data-support-id="{escape(support.support_id, quote=True)}" data-axis-mm="{support.x_axis_mm:.1f}">'
        '<line x1="15" y1="15" x2="15" y2="175" class="bracket"/>'
        '<line x1="15" y1="35" x2="120" y2="35" class="bracket"/>'
        '<line x1="15" y1="150" x2="120" y2="35" class="bracket diagonal"/>'
        '<circle cx="15" cy="45" r="4"/><circle cx="15" cy="78" r="4"/>'
        '<circle cx="15" cy="112" r="4"/><circle cx="15" cy="145" r="4"/>'
        f'<text x="68" y="198" text-anchor="middle">{escape(support.alignment_role.replace("_", " "))}</text></g>'
        for index, support in enumerate(project.model.support_layout.supports)
    )
    return (
        '<svg viewBox="0 0 520 245" role="img" data-action-illustration="true">'
        '<title>Rakks horizontal arm, diagonal, wall leg, and schedule-controlled locations</title>'
        f'{groups}<path d="M260 52 V205" class="load-arrow"/>'
        '<text x="260" y="225" text-anchor="middle">modeled gravity path · accepted schedule controls locations</text></svg>'
    )


def _placement_svg(project) -> str:
    vanity = project.model.section.vanity
    z0 = vanity.bottom_elevation_mm
    z1 = vanity.bottom_elevation_mm + vanity.body_height_mm

    def sy(z_mm):
        return 210.0 - 120.0 * (z_mm - z0) / (z1 - z0)

    service_envelopes = "".join(
        f'<rect x="{_sx(project, path.service_envelope.x0_mm):.1f}" '
        f'y="{max(35.0, sy(path.service_envelope.z1_mm)):.1f}" '
        f'width="{_sx(project, path.service_envelope.x1_mm) - _sx(project, path.service_envelope.x0_mm):.1f}" '
        f'height="{min(190.0, sy(path.service_envelope.z0_mm)) - max(35.0, sy(path.service_envelope.z1_mm)):.1f}" '
        f'class="service-envelope" data-service-envelope="{escape(path.service_envelope.envelope_id, quote=True)}" '
        f'data-x0-mm="{path.service_envelope.x0_mm:.1f}" data-x1-mm="{path.service_envelope.x1_mm:.1f}"/>'
        for path in project.model.plumbing_paths
    )
    drawer_clearances = "".join(
        f'<g transform="translate({330 + (index % 2) * 90},{35 + (index // 2) * 45})">'
        f'<path d="M0 0 h{drawer.closed_clearance_mm * 3.0:.1f}" '
        f'class="drawer-clearance" data-drawer-envelope="{escape(drawer.drawer_id, quote=True)}" '
        f'data-closed-clearance-mm="{drawer.closed_clearance_mm:.1f}"/>'
        f'<text x="0" y="13">{escape(drawer.bay_id)} {escape(drawer.level)} closed clearance</text>'
        f'</g>'
        for index, drawer in enumerate(project.model.drawers)
    )
    cabinet = _cabinet_svg(project, action=False).replace(
        '<svg ', '<g transform="translate(0,-10)" '
    ).replace('</svg>', '</g>')
    return (
        '<svg viewBox="0 0 520 280" role="img" data-action-illustration="true">'
        '<title>Two-person placement of the empty cabinet</title>'
        f'{cabinet}{service_envelopes}<g aria-label="Typed closed-clearance facts, not verified travel envelopes">{drawer_clearances}</g>'
        '<circle cx="35" cy="105" r="14"/><path d="M35 120 V185 M35 140 L65 160 M35 185 L20 220 M35 185 L50 220" class="person"/>'
        '<circle cx="485" cy="105" r="14"/><path d="M485 120 V185 M485 140 L455 160 M485 185 L470 220 M485 185 L500 220" class="person"/>'
        '<path d="M80 75 V100 M440 75 V100" class="lift-arrow"/>'
        '<text x="260" y="268" text-anchor="middle">two-person lift · empty case · temporary restraint</text></svg>'
    )


def _restraint_svg(project) -> str:
    rail = project.model.part("rear_mounting_rail")
    return (
        '<svg viewBox="0 0 520 250" role="img" data-action-illustration="true">'
        '<title>Accepted-detail placeholder and lateral-only rear rail</title>'
        '<rect x="60" y="45" width="400" height="140" class="cabinet"/>'
        f'<rect x="75" y="75" width="370" height="22" class="rail" data-part-id="{escape(rail.part_id, quote=True)}"/>'
        '<rect x="145" y="115" width="230" height="45" class="placeholder"/>'
        '<text x="260" y="143" text-anchor="middle">ACCEPTED CABINET-TO-BRACKET DETAIL</text>'
        '<path d="M100 86 H420" class="lateral-arrow"/>'
        '<text x="260" y="215" text-anchor="middle">rear rail: positioning / lateral only · zero gravity credit</text></svg>'
    )


def _inspection_svg(project) -> str:
    return (
        '<svg viewBox="0 0 520 260" role="img" data-action-illustration="true">'
        '<title>Final level, plumb, square, and support-contact inspection</title>'
        '<rect x="70" y="55" width="380" height="145" class="cabinet"/>'
        '<line x1="100" y1="75" x2="420" y2="75" class="level"/>'
        '<line x1="90" y1="70" x2="90" y2="185" class="plumb"/>'
        '<line x1="70" y1="55" x2="450" y2="200" class="diagonal"/>'
        '<line x1="450" y1="55" x2="70" y2="200" class="diagonal"/>'
        + "".join(
            f'<circle cx="{_sx(project, support.x_axis_mm):.1f}" cy="205" r="8" data-support-id="{escape(support.support_id, quote=True)}" data-axis-mm="{support.x_axis_mm:.1f}"/>'
            for support in project.model.support_layout.supports
        )
        + '<text x="260" y="240" text-anchor="middle">level · plumb · square · three-plane contact · access</text></svg>'
    )


def _action_svg(project, frame_id: str) -> str:
    return {
        "layout_wall": _layout_svg,
        "install_supports": _supports_svg,
        "place_cabinet": _placement_svg,
        "restrain_cabinet": _restraint_svg,
        "inspect_cabinet": _inspection_svg,
    }[frame_id](project)


def _render_action(project, frame: ActionFrame, number: int) -> str:
    why, verify, stop = _FRAME_NOTES[frame.frame_id]
    return (
        f'<article class="frame action" data-frame-id="{escape(frame.frame_id, quote=True)}">'
        f'<header><span class="step-number">{number}</span>'
        f'<span class="conditional">{_CONDITIONAL}</span></header>'
        f'{_action_svg(project, frame.frame_id)}'
        f'<p class="caption">{escape(frame.caption)}</p>'
        f'<aside class="why"><b>WHY</b> {escape(why.removeprefix("WHY "))}</aside>'
        f'<aside class="verify"><b>VERIFY</b> {escape(verify.removeprefix("VERIFY "))}</aside>'
        f'<aside class="stop"><b>STOP</b> {escape(stop.removeprefix("STOP "))}</aside>'
        '</article>'
    )


def _render_record(page) -> str:
    rows = "".join(
        f'<div class="record-row"><b>{escape(field.label)}</b>'
        f'<span>{escape(field.guidance)}</span><i></i></div>'
        for field in page.record_fields
    )
    return f'<h2>{escape(page.record_title)}</h2><div class="record-grid">{rows}</div><div class="final-stop">STOP BEFORE COUNTERTOP, SINKS, PLUMBING, DRAWERS, LOADING, OR USE.</div>'


def _render_installation_manual(project, manual: ConsumerManual) -> str:
    action_number = 0
    sheets = []
    for page in manual.pages:
        content = ""
        if page.kind == "cover":
            links = "".join(
                f'<a href="{escape(link.href, quote=True)}">{escape(link.label)}</a>'
                for link in manual.related_documents
            )
            content = (
                f'<p class="eyebrow">{escape(manual.kit_gate)}</p>'
                f'<h1>{escape(manual.title)}</h1>{_cabinet_svg(project)}'
                f'<p class="cover-caption">{escape(manual.cover_caption)}</p>'
                f'<nav>{links}</nav>'
            )
        elif page.kind == "inventory":
            content = '<h2>People, tools, products, and boundaries</h2>' + "".join(
                f'<p class="inventory-row">{escape(text)}</p>'
                for text in _inventory_texts(project)
            )
        elif page.kind == "hold":
            frame = page.frames[0]
            content = (
                '<article class="frame hold" data-frame-id="installation_hold">'
                f'<p class="eyebrow">{escape(frame.hold)}</p>'
                '<h2>STOP — complete and accept the release record</h2>'
                f'<p class="caption">{escape(frame.caption)}</p>'
                f'<aside class="stop"><b>STOP</b> {escape(frame.warning)}</aside>'
                '<div class="hold-fields">'
                '<p>Wall construction / framing / blocking / utilities: __________________</p>'
                '<p>Rakks product revision and approval: __________________</p>'
                '<p>Structural fastener schedule: __________________</p>'
                '<p>Cabinet-to-bracket detail: __________________</p>'
                '<p>Field reviewer / structural reviewer / date: __________________</p>'
                '</div></article>'
            )
        elif page.kind == "frames":
            rows = []
            for frame in page.frames:
                action_number += 1
                rows.append(_render_action(project, frame, action_number))
            content = "".join(rows)
        elif page.kind == "record":
            content = (
                f'<p class="conditional">{_CONDITIONAL}</p>'
                f'{_render_record(page)}'
            )
        sheets.append(
            f'<section class="sheet {page.kind}" data-page-kind="{page.kind}">'
            f'{content}<footer>DV72 cabinet installation guide · {page.number} / {len(manual.pages)}</footer></section>'
        )

    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(manual.title)}</title><style>
@page{{size:Letter;margin:0}}*{{box-sizing:border-box}}body{{margin:0;background:#d7d7d7;color:#111;font:14px/1.35 Arial,sans-serif}}.sheet{{position:relative;width:8.5in;min-height:11in;margin:20px auto;padding:.5in;background:white;page-break-after:always;overflow:hidden}}h1{{font-size:34px;margin:.12in 0}}h2{{font-size:25px;margin:.05in 0 .22in}}.eyebrow,.conditional{{font-weight:800;letter-spacing:.04em}}.eyebrow{{color:#a21c13}}.frame{{border:4px solid #111;padding:.18in;margin-bottom:.18in}}.frame header{{display:flex;align-items:center;gap:.14in}}.step-number{{display:inline-grid;place-items:center;width:.42in;height:.42in;border:3px solid;border-radius:50%;font-size:22px;font-weight:bold}}.conditional{{font-size:12px;color:#a21c13}}svg{{display:block;width:100%;max-height:2.1in;margin:.06in 0;border:2px solid #111;background:#faf8f1}}svg text{{font:12px Arial,sans-serif;fill:#111}}.cabinet,.placeholder{{fill:none;stroke:#111;stroke-width:4}}.case-member,.wall,.datum,.axis,.bracket,.person,.rail,.level,.plumb,.diagonal{{fill:none;stroke:#111;stroke-width:4}}.axis{{stroke-dasharray:7 5;stroke:#a21c13}}.datum{{stroke:#23638c}}.bracket{{stroke-width:7}}.load-arrow,.lift-arrow,.lateral-arrow{{fill:none;stroke:#a21c13;stroke-width:5}}.rail{{fill:#ddd}}.placeholder{{stroke-dasharray:8 6}}.service-envelope{{fill:#4ba3c733;stroke:#23638c;stroke-width:2;stroke-dasharray:6 4}}.drawer-clearance{{fill:none;stroke:#8b5a2b;stroke-width:3}}.caption{{font-size:15px;font-weight:700}}aside{{margin-top:5px;padding:4px 7px;border-left:6px solid #23638c}}aside.stop{{border-color:#a21c13;background:#fff1ef}}.inventory-row{{border:2px solid #111;padding:12px;font-size:16px}}.hold{{margin-top:.35in;border-width:7px}}.hold-fields p{{padding:.08in;border-bottom:1px solid #777}}.record-grid{{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}}.record-row{{display:grid;grid-template-columns:1.35in 1fr;gap:6px;border-bottom:1px solid #777;padding:5px 0;min-height:.55in}}.record-row span{{font-size:10px;color:#444}}.record-row i{{grid-column:1/-1;border-bottom:1px solid #aaa}}.final-stop{{margin-top:.12in;padding:.1in;border:5px solid #a21c13;font-weight:900;font-size:16px}}nav a{{display:inline-block;margin-right:12px;color:#134f72}}footer{{position:absolute;left:.5in;right:.5in;bottom:.25in;border-top:1px solid;padding-top:5px;font-size:11px}}@media(max-width:850px){{.sheet{{width:100%;min-height:auto;margin:0 0 12px;padding:20px}}footer{{position:static;margin-top:20px}}.record-grid{{grid-template-columns:1fr}}}}@media print{{body{{background:white}}.sheet{{margin:0;width:8.5in;height:11in;min-height:11in}}.record-grid{{grid-template-columns:1fr 1fr}}footer{{position:absolute;margin-top:0}}}}
</style></head><body>{''.join(sheets)}</body></html>'''


def build_double_vanity_installation_guide(
    project,
    *,
    related_documents: tuple[RelatedDocumentLink, ...],
) -> str:
    manual = project_double_vanity_installation_manual(
        project, related_documents=related_documents,
    )
    return _render_installation_manual(project, manual)
