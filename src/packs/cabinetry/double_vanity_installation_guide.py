"""Conditional, print-first cabinet installation guide for DV72.

The guide is a typed projection of the compiled double-vanity model.  It
deliberately stops at an empty, restrained cabinet and carries no authority
for structural fastener selection, cabinet case/interface attachment, stone,
fixtures, plumbing, drawers, loading, or commissioning.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from html import escape
from math import gcd

from ...rendering.action_frames import ActionFrame, FrameIllustration
from ...rendering.consumer_pages import ConsumerManual, compose_consumer_manual
from ...rendering.instruction_panels import (
    RecordField,
    RelatedDocumentLink,
    _relative_html_basename,
)
from .double_vanity import RAKKS_EH_1818_LV


_CONDITIONAL = "CONDITIONAL — RELEASE RECORD REQUIRED"

@dataclass(frozen=True)
class ReleaseRuleReader:
    label: str
    phase: str
    reader_copy: str


_REQUIRED_RELEASE_RULES: dict[str, ReleaseRuleReader] = {
    "double_vanity.release.site_survey": ReleaseRuleReader(
        "Site comparison", "PRE-WORK",
        "Record and accept the field wall, floor, backing, utilities, and rough-in comparison before empty-cabinet mounting.",
    ),
    "double_vanity.release.wall_mount": ReleaseRuleReader(
        "Wall mount", "PRE-WORK",
        "Record and accept the product revision, wall construction, framing/blocking, structural schedule, and cabinet case/interface detail before empty-cabinet mounting.",
    ),
    "double_vanity.release.dynamic_access": ReleaseRuleReader(
        "Dynamic access", "FOLLOW-ON",
        "Drawer travel, removal, and service access remain unresolved for later work; this is not service-access approval.",
    ),
    "double_vanity.release.plumbing_approval": ReleaseRuleReader(
        "Plumbing approval", "FOLLOW-ON",
        "Licensed-plumber fitting, waste, vent, supply, slope, access, and jurisdiction approval remains unresolved for later work.",
    ),
    "double_vanity.release.drawer_derivation": ReleaseRuleReader(
        "Drawer fabrication and access", "FOLLOW-ON",
        "Static drawer geometry and later runner, travel, removal, and service work remain governed by their separate fabrication and access authority.",
    ),
}

_INVENTORY_STATIC_TEXTS = (
    "Crew, equipment, lift, temporary support, and restraint: only as named by the accepted handling plan.",
    "Tools and methods: only those named by the accepted product, structural, tolerance, shim, and cabinet-interface records.",
    "Boundary: cabinet only. Countertop, sinks, plumbing, drawers, contents, loading, and use remain outside this guide.",
    "Structural fastener schedule: __________________",
    "Cabinet case/interface detail: __________________",
)

_FRAME_NOTES = {
    "layout_wall": (
        "WHY Defined floor, countertop-top, bracket-arm, wall, and x-origin datums keep the field comparison tied to the compiled geometry.",
        "VERIFY Compare wall, floor, backing, utilities, owner-assumed rough-ins, and all three stations against the accepted field and structural releases.",
        "STOP Stop if a site fact differs from the accepted records or if either FIELD or STRUCTURAL release is rejected or incomplete.",
    ),
    "install_supports": (
        "WHY The three Rakks envelopes are the modeled primary gravity path; the wall connection and reaction distribution are not proved here.",
        "VERIFY Check accepted product/document revision, count, station, arm datum, projection, wall plane, backing, and schedule-controlled fastener pattern.",
        "STOP Stop if any product, wall, backing, schedule, or support fact differs from the accepted records.",
    ),
    "place_cabinet": (
        "WHY The accepted handling and case/interface records control how the empty case passes below and around the countertop-support arms.",
        "VERIFY Follow only the accepted weight, crew/equipment, lift, temporary-support, restraint, attachment, removal, and handoff criteria.",
        "STOP Stop if the accepted plan cannot be followed or the owner-assumed rough-in conflict comparison differs; this is not service-access approval.",
    ),
    "restrain_cabinet": (
        "WHY The accepted cabinet case/interface detail restrains the case; the rear rail provides positioning and lateral restraint only.",
        "VERIFY Apply only the signed interface detail, fastener schedule, and tolerance/shim schedule. Confirm the continuous rear rail remains lateral-only with zero gravity credit.",
        "STOP Stop when a detail, location, substrate, tool path, or observed fit differs; connection capacity remains unproved.",
    ),
    "inspect_cabinet": (
        "WHY The post-install record preserves the empty mounted cabinet after work authorized by the separate pre-work releases.",
        "VERIFY Record level, plumb, square, accepted interface attachment, tolerance/shim results, deviations, handoff, installer, reviewer, and date.",
        "STOP STOP BEFORE COUNTERTOP, SINKS, PLUMBING, DRAWERS, LOADING, OR USE.",
    ),
}

_RECORD_FIELDS = (
    RecordField("Completion acceptance — ACCEPTED / REJECTED", "Select one; rejected work remains held"),
    RecordField("Level", "Reading and accepted tolerance"),
    RecordField("Plumb", "Reading and accepted tolerance"),
    RecordField("Diagonal / square check", "Both diagonals or accepted check"),
    RecordField("Wall gaps", "Record locations and accepted disposition"),
    RecordField("Accepted interface contact / restraint", "Compared with accepted cabinet case/interface detail"),
    RecordField("Tolerance / shim result", "Compared with accepted schedules"),
    RecordField("Fastener count vs accepted schedule", "Actual count and accepted schedule count"),
    RecordField("Fastener witness record", "Compared with accepted structural schedule"),
    RecordField("Cabinet restraint", "Compared with accepted cabinet case/interface detail"),
    RecordField("Observed rough-in conflict — YES / NO", "Field observation only; not service-access approval"),
    RecordField("FIELD release attachment ID", "Link to accepted pre-work FIELD record"),
    RecordField("STRUCTURAL release attachment ID", "Link to accepted pre-work STRUCTURAL record"),
    RecordField("Deviations", "None, or attach accepted disposition"),
    RecordField("Handoff status", "Empty mounted cabinet; follow-on work held"),
    RecordField("Installer", "Printed name and signature"),
    RecordField("Authorized reviewer role", "Role with acceptance authority"),
    RecordField("Authorized reviewer signature", "Printed name and signature"),
    RecordField("Acceptance date", "YYYY-MM-DD"),
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
    vanity = model.section.vanity
    expected_bearing_z = vanity.bottom_elevation_mm + vanity.body_height_mm
    expected_wall_y = model.section.site.wall.plane_origin_mm[1]
    if any(
        abs(support.bearing_z_mm - expected_bearing_z) > 1e-6
        or abs(support.wall_y_mm - expected_wall_y) > 1e-6
        or support.authority
        != "manufacturer_nominal_envelope_provisional_placement"
        for support in supports
    ):
        raise ValueError(
            "DV72 support envelope facts must match the countertop underside, "
            "wall plane, and provisional manufacturer authority"
        )

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
        if finding.rule in _REQUIRED_RELEASE_RULES
    }
    if (
        release.installation_status != "HOLD_FIELD_VERIFY"
        or release.trade_status != "HOLD_RESPONSIBLE_TRADE_APPROVAL"
        or release.commissioning_status != "HOLD_COMMISSIONING"
        or set(release_findings) != set(_REQUIRED_RELEASE_RULES)
        or any(verdict not in {"UNKNOWN", "FAIL"} for verdict in release_findings.values())
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
            "Compare the field wall with the assumed basis. Establish the finished-floor, countertop-top, bracket-arm, wall-plane, and x-origin datums, then transfer the three support axes.",
            (model.part("left_end").part_id, model.part("center_divider").part_id, model.part("right_end").part_id),
        ),
        (
            "install_supports",
            f"Using the accepted structural schedule and current product record, place {support_count} support envelopes with their arms at the recorded countertop-underside datum and wall plane.",
            tuple(support.support_id for support in model.support_layout.supports),
        ),
        (
            "place_cabinet",
            "Follow the accepted handling plan to position the empty case below/around the accepted countertop-support arms per accepted case/interface detail; do not add finish components.",
            tuple(model.part(role).part_id for role in ("left_end", "center_divider", "right_end")),
        ),
        (
            "restrain_cabinet",
            "Apply only the accepted cabinet case/interface detail. Use the continuous rear rail for positioning and lateral restraint; give it zero gravity credit.",
            (model.part("rear_mounting_rail").part_id,),
        ),
        (
            "inspect_cabinet",
            "Inspect and record the empty cabinet mounted level, plumb, square, attached and restrained per the accepted case/interface detail, and held before follow-on work.",
            tuple(model.part(role).part_id for role in ("left_end", "center_divider", "right_end", "rear_mounting_rail")),
        ),
    )
    frames = [ActionFrame(
        frame_id="installation_hold",
        caption=(
            "Do not begin field work until separate FIELD and STRUCTURAL releases "
            "accept the site comparison, product record, structural schedule, "
            "case/interface detail, handling plan, and tolerance/shim schedule."
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
            "Outcome: the empty cabinet is mounted and restrained through the "
            "accepted cabinet case/interface detail, recorded, and held before "
            "countertop, fixtures, plumbing, drawers, loading, or use."
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
    selected_revision = mount.adapter_id.rpartition("@")[2]
    current_filename = mount.current_specification_url.rsplit("/", 1)[-1]
    current_revision = current_filename.removesuffix(".pdf").rsplit("_", 1)[-1]
    product = (
        f"Product reference: {mount.manufacturer} {mount.sku} vanity support, "
        f"selected record: {selected_revision} "
        f"({mount.specification_url.rsplit('/', 1)[-1]}); current confirmation "
        f"target: {current_revision} ({current_filename}) — confirmation target "
        "only—not approved until recorded. Record the accepted product "
        "revision/document ID before field work."
    )
    load_basis = (
        f"Model load comparison basis only—not allowable cabinet/installation "
        f"load: {load.unfactored_total_lb:.1f} lb unfactored and "
        f"{load.factored_total_lb:.1f} lb factored. Reaction distribution is "
        "unproved and no connection capacity is assigned."
    )
    package = (
        "Required package location: same directory, issue 2026-07-14 / Rev 1: "
        "dv72_review_installation.html; dv72_assembly_service.html; "
        "dv72_fabrication_coordination.html; dv72_validation_sources.html; "
        "dv72_installation_guide.html. Printed work requires the accepted "
        "release attachments and exact document IDs listed on sheet 3."
    )
    return (
        _INVENTORY_STATIC_TEXTS[:2]
        + (product, load_basis, package)
        + _INVENTORY_STATIC_TEXTS[2:]
    )


def _field_dual(mm: float) -> str:
    rounded_mm = round(mm)
    sixteenths = round(mm / 25.4 * 16)
    whole, numerator = divmod(sixteenths, 16)
    if numerator:
        divisor = gcd(numerator, 16)
        inches = f"{whole} {numerator // divisor}/{16 // divisor}"
    else:
        inches = str(whole)
    return f"{rounded_mm:,} mm / {inches} in"


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
        '<title>Empty cabinet mounted through accepted case/interface detail</title>'
        f'<rect x="65" y="90" width="{width:.1f}" height="{height:.1f}" class="cabinet"/>{members}'
        '<text x="260" y="245" text-anchor="middle">EMPTY CABINET MOUNTED — FOLLOW-ON WORK HELD</text>'
        '</svg>'
    )


def _layout_svg(project) -> str:
    model = project.model
    vanity = model.section.vanity
    counter_top = (
        vanity.bottom_elevation_mm + vanity.body_height_mm
        + vanity.countertop_thickness_mm
    )
    bearing = vanity.bottom_elevation_mm + vanity.body_height_mm
    front_datum_offset = (
        model.section.site.wall.plane_origin_mm[1] - vanity.body_depth_mm
    )
    supports = "".join(
        f'<g data-support-id="{escape(support.support_id, quote=True)}" data-axis-mm="{support.x_axis_mm:.1f}" '
        f'data-bearing-z-mm="{support.bearing_z_mm:.1f}" data-wall-y-mm="{support.wall_y_mm:.1f}" '
        f'data-authority="{escape(support.authority, quote=True)}">'
        f'<line x1="{_sx(project, support.x_axis_mm):.1f}" y1="45" x2="{_sx(project, support.x_axis_mm):.1f}" y2="220" class="axis"/>'
        f'<text x="{_sx(project, support.x_axis_mm):.1f}" y="35" text-anchor="middle">{escape(_field_dual(support.x_axis_mm))}</text></g>'
        for support in model.support_layout.supports
    )
    return (
        '<svg viewBox="0 0 520 270" role="img" data-action-illustration="true">'
        '<title>Defined wall, floor, countertop, bracket-arm, and support-axis datums</title>'
        '<line x1="35" y1="220" x2="485" y2="220" class="datum"/>'
        f'<text x="40" y="240">finished floor: {_field_dual(model.assumed_site.floor_elevation_mm)}</text>'
        '<line x1="35" y1="75" x2="485" y2="75" class="datum"/>'
        f'<text x="40" y="68">countertop top datum: {_field_dual(counter_top)} AFF</text>'
        '<line x1="35" y1="88" x2="485" y2="88" class="datum"/>'
        f'<text x="40" y="105">countertop-underside / bracket-arm datum: {_field_dual(bearing)} AFF</text>'
        f'{supports}<text x="40" y="247">x = 0 at finished left end of assumed wall · wall plane y = {_field_dual(model.section.site.wall.plane_origin_mm[1])}</text>'
        f'<text x="40" y="263">y = 0 at project datum {_field_dual(front_datum_offset)} in front of modeled vanity front · y increases toward wall</text>'
        f'<text x="310" y="118">{_field_dual(vanity.countertop_thickness_mm)} counter thickness</text></svg>'
    )


def _supports_svg(project) -> str:
    groups = "".join(
        f'<g transform="translate({70 + index * 150},25)" data-support-id="{escape(support.support_id, quote=True)}" data-axis-mm="{support.x_axis_mm:.1f}" '
        f'data-bearing-z-mm="{support.bearing_z_mm:.1f}" data-wall-y-mm="{support.wall_y_mm:.1f}" '
        f'data-authority="{escape(support.authority, quote=True)}">'
        '<line x1="15" y1="15" x2="15" y2="175" class="bracket"/>'
        '<line x1="15" y1="35" x2="120" y2="35" class="bracket"/>'
        '<path d="M75 3 V31" class="load-arrow" data-load-path="countertop-arm-diagonal-wall"/>'
        '<line x1="15" y1="150" x2="120" y2="35" class="bracket diagonal" data-load-transfer="arm-to-diagonal-to-wall-leg"/>'
        f'<text x="68" y="198" text-anchor="middle">{escape(support.alignment_role.replace("_", " "))}</text></g>'
        for index, support in enumerate(project.model.support_layout.supports)
    )
    support = project.model.support_layout.supports[0]
    return (
        '<svg viewBox="0 0 520 270" role="img" data-action-illustration="true" data-support-layout="true">'
        '<title>Rakks nominal envelopes at typed countertop underside and wall plane</title>'
        f'{groups}<text x="260" y="214" text-anchor="middle">countertop support load ↓ arm · transfer along diagonal to wall leg</text>'
        '<text x="260" y="231" text-anchor="middle">wall fasteners / framing receive forces · accepted structural record governs</text>'
        f'<text x="260" y="248" text-anchor="middle">arm datum {_field_dual(support.bearing_z_mm)} AFF · wall plane {_field_dual(support.wall_y_mm)}</text>'
        f'<text x="260" y="265" text-anchor="middle">horizontal projection/depth {_field_dual(support.horizontal_leg_mm)} · fastening per accepted product revision + structural schedule</text></svg>'
    )


def _placement_svg(project) -> str:
    rough_ins = project.model.assumed_site.wastes + project.model.assumed_site.supplies
    rough_in_marks = "".join(
        f'<g data-rough-in="{escape(point.point_id, quote=True)}" '
        f'data-x-mm="{point.x_mm:.1f}" data-y-mm="{point.y_mm:.1f}" data-z-mm="{point.z_mm:.1f}" '
        f'data-provenance="{escape(point.provenance, quote=True)}">'
        f'<rect x="{_sx(project, point.x_mm) - 4:.1f}" y="160" width="8" height="8" class="service-envelope"/>'
        f'</g>' for point in rough_ins
    )
    arms = "".join(
        f'<path d="M{_sx(project, support.x_axis_mm):.1f} 48 v35 h35" class="bracket" '
        f'data-support-id="{escape(support.support_id, quote=True)}"/>'
        for support in project.model.support_layout.supports
    )
    cabinet = _cabinet_svg(project, action=False).replace(
        '<svg ', '<g transform="translate(0,5)" '
    ).replace('</svg>', '</g>')
    return (
        '<svg viewBox="0 0 520 280" role="img" data-action-illustration="true">'
        '<title>Accepted-plan placement below and around countertop-support arms</title>'
        '<rect x="48" y="35" width="424" height="205" class="placeholder"/>'
        f'{arms}{cabinet}{rough_in_marks}'
        '<text x="260" y="18" text-anchor="middle">accepted-plan handling/support/restraint placeholder</text>'
        '<text x="260" y="238" text-anchor="middle">protection / clearance · arm alignment · cabinet case/interface relationship</text>'
        '<text x="260" y="255" text-anchor="middle">owner-assumed rough-in conflict comparison only · not service-access approval</text>'
        '<text x="260" y="271" text-anchor="middle">dynamic access remains separately held · follow accepted handling/support/restraint plan</text></svg>'
    )


def _restraint_svg(project) -> str:
    rail = project.model.part("rear_mounting_rail")
    return (
        '<svg viewBox="0 0 520 250" role="img" data-action-illustration="true">'
        '<title>Accepted cabinet case/interface detail placeholder and lateral-only rear rail</title>'
        '<rect x="60" y="45" width="400" height="140" class="cabinet"/>'
        f'<rect x="75" y="75" width="370" height="22" class="rail" data-part-id="{escape(rail.part_id, quote=True)}"/>'
        '<rect x="145" y="115" width="230" height="45" class="placeholder"/>'
        '<text x="260" y="143" text-anchor="middle">ACCEPTED CABINET CASE/INTERFACE DETAIL</text>'
        '<path d="M100 86 H420" class="lateral-arrow"/>'
        '<text x="260" y="215" text-anchor="middle">rear rail: positioning / lateral only · zero gravity credit</text></svg>'
    )


def _inspection_svg(project) -> str:
    return (
        '<svg viewBox="0 0 520 260" role="img" data-action-illustration="true">'
        '<title>Final level, plumb, square, interface-attachment, and hold inspection</title>'
        '<rect x="70" y="55" width="380" height="145" class="cabinet"/>'
        '<line x1="100" y1="75" x2="420" y2="75" class="level"/>'
        '<line x1="90" y1="70" x2="90" y2="185" class="plumb"/>'
        '<line x1="70" y1="55" x2="450" y2="200" class="diagonal"/>'
        '<line x1="450" y1="55" x2="70" y2="200" class="diagonal"/>'
        + '<text x="260" y="240" text-anchor="middle">level · plumb · square · accepted interface attachment · follow-on hold</text></svg>'
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
        '<p class="scroll-cue">Swipe/scroll horizontally to inspect the full diagram</p>'
        f'<div class="svg-scroll">{_action_svg(project, frame.frame_id)}</div>'
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


def _release_findings_html(project) -> str:
    groups = []
    for phase, heading in (
        ("PRE-WORK", "PRE-WORK GATES — required before empty-cabinet mounting"),
        ("FOLLOW-ON", "FOLLOW-ON HOLDS — unresolved for later work"),
    ):
        rows = []
        for rule, reader in _REQUIRED_RELEASE_RULES.items():
            if reader.phase != phase:
                continue
            finding = project.report.by_rule(rule)
            if finding.verdict == "FAIL":
                status = (
                    "PRE-WORK FAIL — STOP"
                    if phase == "PRE-WORK"
                    else "FOLLOW-ON FAIL — STOP BEFORE FOLLOW-ON WORK — not required for empty-cabinet mounting"
                )
            else:
                status = (
                    "PRE-WORK HOLD — release required before empty-cabinet mounting"
                    if phase == "PRE-WORK"
                    else "FOLLOW-ON HOLD — not required for empty-cabinet mounting"
                )
            copy = (
                _drawer_release_reader_copy(project)
                if rule == "double_vanity.release.drawer_derivation"
                else reader.reader_copy
            )
            rows.append(
                f'<article data-release-rule="{escape(rule, quote=True)}" '
                f'data-verdict="{escape(finding.verdict, quote=True)}" '
                f'data-release-phase="{phase}"><b>{escape(reader.label)} — '
                f'{escape(status)}</b><span>{escape(copy)}</span></article>'
            )
        groups.append(
            f'<h3>{escape(heading)}</h3><div class="release-group">'
            f'{"".join(rows)}</div>'
        )
    return f'<div class="release-findings">{"".join(groups)}</div>'


def _drawer_release_reader_copy(project) -> str:
    status = project.model.release.fabrication_status
    if status == "HOLD_PRODUCT_GEOMETRY":
        return (
            "Drawer product geometry and static cuts are held. Runner machining, "
            "travel, removal, and service access remain separately held for later work."
        )
    if status == "HOLD_FABRICATOR_ACCEPTANCE":
        return (
            "Static drawer geometry is prepared for review only; fabricator "
            "acceptance pending. Runner machining, travel, removal, and service "
            "access remain separately held for later work."
        )
    return (
        "Recorded fabricator acceptance governs static drawer cuts only. Runner "
        "machining, travel, removal, and service access remain separately held "
        "for later work."
    )


def _prework_release_fields() -> str:
    fields = (
        "FIELD RELEASE — RELEASED / REJECTED",
        "FIELD Reviewer / signature / date",
        "FIELD Document revision / attachment IDs",
        "STRUCTURAL RELEASE — RELEASED / REJECTED",
        "STRUCTURAL Reviewer / signature / date",
        "STRUCTURAL Document revision / attachment IDs",
        "Accepted product revision / document ID",
        "Structural fastener schedule ID",
        "Cabinet case/interface detail ID",
        "Tolerance / shim schedule ID",
        "Actual empty-case handling weight",
        "Accepted lift / temporary-support / restraint plan",
        "Equipment / crew",
        "Attachment / removal / handoff criteria",
        "Wall construction",
        "Framing / blocking verification",
        "Utilities / rough-in verification",
    )
    rows = "".join(f'<p>{escape(field)}: __________________</p>' for field in fields)
    return f'<div class="hold-fields">{rows}</div>'


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
                f'{_release_findings_html(project)}'
                '<p class="precedence"><b>Precedence:</b> the accepted pre-work '
                'release record governs. If it conflicts with this guide or any '
                'package document, stop and obtain a superseding field and '
                'structural release before work.</p>'
                f'{_prework_release_fields()}</article>'
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
@page{{size:Letter;margin:0}}
*{{box-sizing:border-box}}
body{{margin:0;background:#d7d7d7;color:#111;font:14px/1.35 Arial,sans-serif}}
.sheet{{position:relative;width:8.5in;min-height:11in;margin:20px auto;padding:.5in;background:white;page-break-after:always;overflow:hidden}}
h1{{font-size:34px;margin:.12in 0}}h2{{font-size:25px;margin:.05in 0 .22in}}h3{{font-size:13px;margin:4px 0 2px}}
.eyebrow,.conditional{{font-weight:800;letter-spacing:.04em}}.eyebrow{{color:#a21c13}}
.frame{{break-inside:avoid;border:4px solid #111;padding:.18in;margin-bottom:.18in}}.frame header{{display:flex;align-items:center;gap:.14in}}
.step-number{{display:inline-grid;place-items:center;width:.42in;height:.42in;border:3px solid;border-radius:50%;font-size:22px;font-weight:bold}}
.conditional{{font-size:12px;color:#a21c13}}.scroll-cue{{display:none;margin:3px 0;font-size:11px;font-weight:700;color:#23638c}}
svg{{display:block;width:100%;max-height:2.1in;margin:.06in 0;border:2px solid #111;background:#faf8f1}}svg text{{font:12px Arial,sans-serif;fill:#111}}
.cabinet,.placeholder{{fill:none;stroke:#111;stroke-width:4}}.case-member,.wall,.datum,.axis,.bracket,.person,.rail,.level,.plumb,.diagonal{{fill:none;stroke:#111;stroke-width:4}}
.axis{{stroke-dasharray:7 5;stroke:#a21c13}}.datum{{stroke:#23638c}}.bracket{{stroke-width:7}}.load-arrow,.lift-arrow,.lateral-arrow{{fill:none;stroke:#a21c13;stroke-width:5}}
.rail{{fill:#ddd}}.placeholder{{stroke-dasharray:8 6}}.service-envelope{{fill:#4ba3c733;stroke:#23638c;stroke-width:2;stroke-dasharray:6 4}}.drawer-clearance{{fill:none;stroke:#8b5a2b;stroke-width:3}}
.caption{{font-size:15px;font-weight:700}}aside{{margin-top:5px;padding:4px 7px;border-left:6px solid #23638c}}aside.stop{{border-color:#a21c13;background:#fff1ef}}
.inventory-row{{border:2px solid #111;padding:12px;font-size:16px}}.hold{{margin-top:.12in;border-width:7px}}
.release-findings{{display:grid;grid-template-columns:1fr;gap:3px;font-size:10px}}.release-group{{display:grid;grid-template-columns:1fr 1fr;gap:3px 8px}}.release-findings article{{display:grid;gap:2px;border:1px solid #777;padding:3px}}
.precedence{{font-size:10px;margin:4px 0}}.hold-fields{{display:grid;grid-template-columns:1fr 1fr;gap:0 8px}}.hold-fields p{{padding:3px;border-bottom:1px solid #777;font-size:10px;margin:0;min-height:.3in}}
.record-grid{{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}}.record-row{{display:grid;grid-template-columns:1.55in 1fr;gap:6px;border-bottom:1px solid #777;padding:5px 0;min-height:.7in}}
.record-row span{{font-size:10px;color:#444}}.record-row i{{grid-column:1/-1;border-bottom:1px solid #aaa}}.final-stop{{margin-top:.12in;padding:.1in;border:5px solid #a21c13;font-weight:900;font-size:16px}}
nav a{{display:inline-block;margin-right:12px;color:#134f72}}footer{{position:absolute;left:.5in;right:.5in;bottom:.25in;border-top:1px solid;padding-top:5px;font-size:11px}}
@media(max-width:850px){{.sheet{{width:100%;min-height:auto;margin:0 0 12px;padding:20px}}footer{{position:static;margin-top:20px}}.record-grid,.hold-fields,.release-group{{grid-template-columns:1fr}}.scroll-cue{{display:block}}.svg-scroll{{overflow-x:auto}}.svg-scroll svg{{min-width:520px}}}}
@media print{{body{{background:white}}.sheet{{margin:0;width:8.5in;height:11in;min-height:11in;overflow:visible}}.record-grid{{grid-template-columns:1fr 1fr}}.hold-fields,.release-group{{grid-template-columns:1fr 1fr}}.scroll-cue{{display:none}}.svg-scroll{{overflow:visible}}.svg-scroll svg{{min-width:0}}.frame.action{{padding:.1in;margin-bottom:.1in;font-size:12px;line-height:1.2}}.frame.action svg{{max-height:1.65in}}.frame.action .caption{{font-size:13px;margin:3px 0}}.frame.action aside{{margin-top:2px;padding:2px 5px;font-size:10.5px}}footer{{position:absolute;margin-top:0}}}}
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
