"""Focused linked reader documents for the DV72 analytic vanity model."""

from __future__ import annotations

import re

from ...rendering.instruction_panels import RelatedDocumentLink
from . import double_vanity_document as study
from .double_vanity_installation_guide import (
    _REQUIRED_RELEASE_RULES,
    build_double_vanity_installation_guide,
)


FILENAMES = (
    "dv72_review_installation.html",
    "dv72_assembly_service.html",
    "dv72_fabrication_coordination.html",
    "dv72_validation_sources.html",
    "dv72_installation_guide.html",
)

_LABELS = {
    FILENAMES[0]: "Review & installation",
    FILENAMES[1]: "Assembly & service",
    FILENAMES[2]: "Fabrication coordination",
    FILENAMES[3]: "Validation & sources",
    FILENAMES[4]: "Cabinet installation guide",
}

_FINDING_ROUTING = {
    "double_vanity.code.fixture_spacing": (
        "Design coordinator", "design validation",
    ),
    "double_vanity.drawer.runner_applicability": (
        "Cabinet fabricator", "runner machining and assembly",
    ),
    "double_vanity.geometry.fixture_plumbing_drawer": (
        "Design coordinator", "design validation",
    ),
    "double_vanity.geometry.service_openings": (
        "Cabinet fabricator", "runner machining and assembly",
    ),
    "double_vanity.geometry.two_bays": (
        "Design coordinator", "design validation",
    ),
    "double_vanity.mount.layout": (
        "Structural reviewer", "wall drilling and loading",
    ),
    "double_vanity.mount.representation": (
        "Structural reviewer", "wall drilling and loading",
    ),
    "double_vanity.plumbing.independent_traps": (
        "Licensed Master Plumber", "trade coordination",
    ),
    "double_vanity.release.commissioning": (
        "General contractor and responsible trades", "commissioning",
    ),
    "double_vanity.release.countertop_fabricator": (
        "Countertop fabricator", "stone fabrication",
    ),
    "double_vanity.release.drawer_derivation": (
        "Cabinet fabricator", "runner machining and assembly",
    ),
    "double_vanity.release.dynamic_access": (
        "Cabinet fabricator", "runner machining and assembly",
    ),
    "double_vanity.release.faucet": (
        "Licensed Master Plumber", "trade coordination",
    ),
    "double_vanity.release.fixture_template": (
        "Countertop fabricator", "stone fabrication",
    ),
    "double_vanity.release.plumbing_approval": (
        "Licensed Master Plumber", "trade coordination",
    ),
    "double_vanity.release.site_survey": (
        "Field surveyor", "field verification",
    ),
    "double_vanity.release.wall_mount": (
        "Structural reviewer", "wall drilling and loading",
    ),
}

_CSS = """
:root{--ink:#27332e;--muted:#66716b;--paper:#fcfaf5;--line:#c9c7bb;--wood:#cf9c6a;--stone:#ebe7dd;--warn:#8e2d24;--warnbg:#f9e8e4;--service:#f4c95d;--pipe:#3979a8}
*{box-sizing:border-box}body{margin:0;background:#e8e5de;color:var(--ink);font:15px/1.5 Inter,system-ui,sans-serif}.sheet{width:min(1180px,100%);margin:auto;background:var(--paper);padding:30px 38px 60px}header{display:grid;grid-template-columns:2fr 1fr;gap:20px;border-bottom:3px solid var(--ink);padding-bottom:20px}.eyebrow{font:800 12px ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--warn)}h1{font-size:clamp(30px,5vw,54px);line-height:1.05;margin:.2em 0}h2{margin:36px 0 12px;border-bottom:1px solid var(--line);padding-bottom:7px}h3{margin-top:26px}.hold{background:var(--warnbg);border:2px solid var(--warn);padding:14px;color:#6f211b}.nav{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}.nav a{border:1px solid var(--line);padding:6px 9px;background:white;color:#76501e}.nav a[aria-current=page]{border-color:var(--ink);font-weight:800}.diagram-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.diagram{margin:0;border:1px solid var(--line);background:white;min-width:0}.diagram figcaption{padding:11px;color:var(--muted)}svg{display:block;width:100%;height:auto;background:#faf8f2}svg text{font:13px system-ui;fill:var(--ink);text-anchor:middle}.case,.drawer{fill:var(--wood);stroke:#61452f;stroke-width:2}.countertop{fill:var(--stone);stroke:#8d8a82;stroke-width:2}.fixture{fill:#fff;stroke:#638a86;stroke-width:3}.pipe{fill:none;stroke:var(--pipe);stroke-width:8}.service{fill:var(--service);fill-opacity:.35;stroke:#b28c25;stroke-dasharray:7 5}.wall{fill:#dad7ce;stroke:#74716a}.rail{fill:#7d5a3b}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid var(--line);padding:8px;vertical-align:top;text-align:left}th{background:#eeece5}.unknown{font-weight:900;color:var(--warn)}code{font:11px ui-monospace,monospace;overflow-wrap:anywhere}a{color:#76501e}.release-gates{border:2px solid var(--warn);padding:0 16px 16px;background:#fff9f7}.states{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.states article{border:1px solid var(--line);background:white;padding:12px}.state-pictogram{height:56px;background:linear-gradient(90deg,var(--wood) 0 55%,var(--service) 55% 76%,transparent 76%);border:1px solid var(--line)}.metric{font:12px ui-monospace,monospace;color:var(--muted)}footer{margin-top:38px;border-top:2px solid var(--ink);padding-top:12px;color:var(--muted)}
@media(max-width:760px){.sheet{padding:20px 14px 40px}header,.diagram-grid{grid-template-columns:1fr}.states{grid-template-columns:1fr 1fr}}@media(max-width:460px){.states{grid-template-columns:1fr}}
"""


def _nav(current: str) -> str:
    return '<nav class="nav" aria-label="DV72 documents">' + "".join(
        f'<a href="{name}"'
        + (' aria-current="page"' if name == current else "")
        + f'>{_LABELS[name]}</a>'
        for name in FILENAMES
    ) + "</nav>"


def _shell(
    title: str,
    current: str,
    purpose: str,
    release_status: str,
    status: str,
    status_content: str,
    body: str,
) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,">
<title>DV72 — {title}</title><style>{_CSS}</style></head><body><main class="sheet">
<header><div><div class="eyebrow">DV72 · vanity.double_sink@1</div><h1>{title}</h1><p>{purpose}</p></div>
<div class="hold" data-release-status="{study._e(release_status)}"><b>{status}</b><p>{status_content}</p></div></header>
{_nav(current)}{body}{_nav(current)}<footer>One analytic model; five reader projections. UNKNOWN is a release hold, never a concealed approval.</footer>
<p class="metric">Issue date: 2026-07-14 · Revision: 1 · Status: {status} · Model: vanity.double_sink@1.0.0</p>
</main></body></html>"""


def _dual(mm: float) -> str:
    return f"{mm:.1f} mm / {mm / 25.4:.2f} in"


def _fabrication_status(project) -> tuple[bool, str]:
    model = project.model
    if not model.fabrication_basis_is_coherent():
        raise ValueError("DV72 fabrication basis contradicts model geometry")
    complete = model.fabrication_acceptance.complete_for(
        model.fabrication_basis
    )
    contract_ready = model.fabrication_release_contract()[0]
    drawer_geometry_ready = all(
        project.report.by_rule(rule).verdict == "PASS"
        for rule in (
            "double_vanity.geometry.fixture_plumbing_drawer",
            "double_vanity.drawer.runner_applicability",
        )
    )
    expected_status = (
        "CONDITIONAL_FABRICATION_RELEASE" if complete
        else "HOLD_PRODUCT_GEOMETRY" if not drawer_geometry_ready
        else "HOLD_FABRICATOR_ACCEPTANCE"
    )
    audit = project.artifacts.fabrication_audit
    expected_audit = {
        "basis_id": model.fabrication_basis.basis_id,
        "basis_version": model.fabrication_basis.version,
        "basis_digest": model.fabrication_basis.digest(),
        "acceptance_status": model.fabrication_acceptance.status,
        "accepted_by": model.fabrication_acceptance.accepted_by,
        "accepted_on": model.fabrication_acceptance.accepted_on,
        "evidence_revision": model.fabrication_acceptance.evidence_revision,
    }
    if (
        model.release.fabrication_status != expected_status
        or project.artifacts.fabrication_ready != contract_ready
        or project.artifacts.release_contract
        != "typed_fabrication_acceptance/v1"
        or audit is None
        or any(
            getattr(audit, key, None) != value
            for key, value in expected_audit.items()
        )
    ):
        raise ValueError("DV72 fabrication authority state is inconsistent")
    status = project.model.release.fabrication_status
    if complete:
        return True, "FABRICATOR ACCEPTANCE RECORDED"
    if status == "HOLD_PRODUCT_GEOMETRY":
        return False, "FABRICATION HOLD — PRODUCT GEOMETRY"
    if status == "HOLD_FABRICATOR_ACCEPTANCE":
        return False, "FABRICATION HOLD — FABRICATOR ACCEPTANCE PENDING"
    raise ValueError(f"unsupported DV72 fabrication status {status!r}")


def _system_section(project) -> str:
    """One model-labelled bay section showing every coordination system."""

    model = project.model
    vanity = model.section.vanity
    path = model.plumbing_paths[0]
    upper = model.drawer("left", "upper")
    lower = model.drawer("left", "lower")
    counter_top = vanity.bottom_elevation_mm + vanity.body_height_mm + vanity.countertop_thickness_mm
    fabrication_released, _ = _fabrication_status(project)
    if fabrication_released:
        dimension_scope = (
            "Cabinet and drawer dimensions are conditionally released model "
            "facts; accepted field rough-ins remain required before runner "
            "machining, stone work, trade work, or installation."
        )
    elif project.model.release.fabrication_status == "HOLD_PRODUCT_GEOMETRY":
        dimension_scope = (
            "Product geometry is held; displayed coordination geometry does "
            "not authorize cabinet, drawer, runner, or stone fabrication."
        )
    else:
        dimension_scope = (
            "Cabinet and drawer dimensions are a prepared non-production "
            "schedule; signed acceptance of the exact fabrication-basis digest "
            "is required before any production cut."
        )
    return f"""
<section><h2>Sink, plumbing, drawers, counter, and wall mount</h2>
<p>Representative section through one of two symmetric bays. Yellow is the removable service envelope, not storage. {dimension_scope}</p>
<p><b>Field vertical targets—not release dimensions:</b> cabinet bottom {_dual(vanity.bottom_elevation_mm)} AFF; counter top {_dual(counter_top)} AFF. Release requires a recorded comparison of the site-wall zero datum, floor datum, wall flatness, framing, and every plumbing centerline.</p>
<figure class="diagram"><figcaption>Bay section · counter top {_dual(counter_top)} AFF · upper box {study._mm(upper.box_depth_mm)} deep · lower box {study._mm(lower.box_depth_mm)} deep · rear service chase {study._mm(model.service_chase_depth_mm)}</figcaption>
<svg viewBox="0 0 900 520" role="img" aria-label="Section through sink, drain, trap, drawers, counter, rear rail, wall and anchors">
<rect data-section-system="wall" x="790" y="25" width="55" height="455" class="wall"/><rect data-section-system="rear-rail" x="730" y="178" width="60" height="42" class="rail"/>
<rect data-section-system="countertop" x="90" y="55" width="700" height="32" class="countertop"/><path data-section-system="fixture" d="M260 87h360l-35 116H295z" class="fixture"/>
<path data-section-system="drain" d="M440 203v65" class="pipe"/><path data-section-system="p-trap" d="M440 268v48q0 45 52 45t52-45v-8h185" class="pipe"/>
<rect data-section-system="service-envelope" x="335" y="188" width="400" height="205" class="service"/>
<path data-section-system="upper-drawer" d="M110 248h205v145h420v-42H355V248z" class="drawer"/><rect data-section-system="lower-drawer" x="110" y="402" width="430" height="68" class="drawer"/>
<circle data-section-system="candidate-anchor" cx="807" cy="199" r="8" fill="#8e2d24"/><text x="450" y="505">proposed service-access concept; hand and tool paths remain unverified.</text>
</svg></figure></section>
<section><h2>Held service sequence</h2><p><b>Sequence concept only—installation and service remain held.</b> This is not an installation instruction.</p><ol><li>Future validated runner procedure: upper U-drawer emptying, release, and removal.</li><li>Future validated runner procedure: lower-drawer release and removal for rear-wall, rail, or anchor access.</li><li>Future plumbing procedure: pan placement and access to each independent P-trap, cleanout/slip joint, and shutoff.</li><li>Future commissioning record: supply, overflow drain, tailpiece, trap, and trap-arm leak tests.</li><li>Future closeout record: drawer return, reveal adjustment, closed/full-extension/removal cycles, and commissioning sign-off.</li></ol></section>
"""


def _assumption_schedule(project) -> str:
    assumed = project.model.assumed_site
    code = project.model.code_profile
    rows = [
        ("wall_length", assumed.wall_length_mm, "site wall run"),
        ("wall_height", assumed.wall_height_mm, "site wall height"),
        ("vanity_left", assumed.vanity_left_mm, "vanity-left datum"),
        ("floor_elevation", assumed.floor_elevation_mm, "floor datum"),
        ("finish_thickness", assumed.finish_thickness_mm, "wall finish"),
    ]
    schedule = "".join(
        f'<tr><td><code>{name}</code></td><td>{_dual(value)}</td>'
        f'<td>{label}</td><td><code>{study._e(assumed.provenance)}</code>; not field verified</td></tr>'
        for name, value, label in rows
    )
    schedule += (
        '<tr><td><code>backing</code></td>'
        f'<td colspan="2">{study._e(assumed.backing)}</td>'
        f'<td><code>{study._e(assumed.provenance)}</code>; not field verified</td></tr>'
    )
    qualitative_rows = (
        (
            "coordinate_axes",
            f"x = 0 at the finished left end of the assumed "
            f"{assumed.wall_length_mm / 25.4:.2f} in wall and x increases right "
            "along the wall; y = 0 at the project datum plane, "
            f"{(project.model.section.site.wall.plane_origin_mm[1] - project.model.section.vanity.body_depth_mm) / 25.4:.2f} in "
            "in front of the modeled finished vanity-front plane at y = "
            f"{_dual(project.model.section.site.wall.plane_origin_mm[1] - project.model.section.vanity.body_depth_mm)}, "
            "and y increases toward the wall; z = 0 at the assumed finished-floor "
            "datum and z increases upward",
            "field-coordinate convention",
        ),
        ("wall_geometry", "straight, flat, and plumb wall", "case-fit basis"),
        ("faucet_target", "4.50 in above the finished counter", "spout-center height target"),
        ("room_clearance", f"{code.front_clearance_mm / 25.4:.2f} in clear room depth in front", "selected-code-profile coordination target"),
    )
    schedule += "".join(
        f'<tr><td><code>{name}</code></td><td>{value}</td><td>{scope}</td>'
        f'<td><code>owner_assumed</code>; not field verified</td></tr>'
        for name, value, scope in qualitative_rows
    )
    for point in assumed.wastes + assumed.supplies:
        schedule += (
            f'<tr data-rough-in="{study._e(point.point_id)}"><td><code>{study._e(point.point_id)}</code></td>'
            f'<td>x {_dual(point.x_mm)}; y {_dual(point.y_mm)}; z {_dual(point.z_mm)}</td>'
            f'<td>{study._e(point.kind)}</td><td><code>{study._e(point.provenance)}</code>; not field verified</td></tr>'
        )
    rough_in_count = len(assumed.wastes) + len(assumed.supplies)
    return (
        '<section><h2>Owner-assumed site and rough-in schedule</h2>'
        '<p>Every value below has <code>owner_assumed</code> provenance and is <b>not field verified</b>. It supports coordination only and confers no drilling, loading, trade, or installation authority.</p>'
        '<div class="table-wrap"><table><thead><tr><th>Assumption</th><th>Model value</th><th>Scope</th><th>Provenance</th></tr></thead><tbody>'
        + schedule + '</tbody></table></div></section>'
        '<section><h2>Field comparison checklist</h2>'
        '<p>Required acceptance record before installation release:</p><ul>'
        '<li>Wall and floor datums, vanity span, wall finish, flatness, and front clearance compared with the schedule.</li>'
        '<li>Backing extent and each support axis exposed or otherwise verified by the responsible reviewer.</li>'
        f'<li>Waste, hot, and cold centerlines compared point-by-point with the {rough_in_count} owner-assumed coordinates.</li>'
        '<li>Obstructions, shutoffs, fitting envelopes, hand/tool paths, and drawer sweeps recorded for both bays.</li>'
        '</ul><p><b>Do not install, drill, load, or connect trades from the owner-assumed schedule.</b></p></section>'
    )


def _support_and_load_hold(project) -> str:
    layout = project.model.support_layout
    load = project.model.load_case
    supports = ", ".join(
        f'{support.support_id} at x {_dual(support.x_axis_mm)} ({support.alignment_role})'
        for support in layout.supports
    )
    load_rows = "".join(
        f'<tr data-load-component="{study._e(name)}"><td>{study._e(name.replace("_", " "))}</td>'
        f'<td>{value:.1f} lb</td><td>model-derived allowance</td></tr>'
        for name, value in load.component_weights_lb().items()
    )
    return f"""
<section><h2>Held support and loading basis</h2>
<p>{len(layout.supports)} provisional support envelopes: {supports}. Authority: <code>{study._e(layout.supports[0].authority)}</code>. Backing: <code>{study._e(layout.backing_authority)}</code>; <code>owner_assumed</code>; not field verified.</p>
<div class="table-wrap"><table><thead><tr><th>Load component</th><th>Model value</th><th>Basis</th></tr></thead><tbody>{load_rows}<tr><th>Unfactored total</th><th>{load.unfactored_total_lb:.1f} lb</th><th>sum of seven model-derived components</th></tr><tr><th>Factored total</th><th>{load.factored_total_lb:.1f} lb</th><th>{load.load_factor:.2f} model factor; reaction distribution unproved</th></tr></tbody></table></div>
<p>Rear-rail gravity credit: {layout.rear_rail_gravity_credit_lb:.1f} lb. Fastener connection capacity is unassigned.</p>
<p><b>Wall drilling, cabinet loading, installation, and use remain held</b> pending field verification, current-product acceptance, fastener/connection design, cabinet-to-support attachment, and structural approval.</p></section>"""


def _rough_in_section(project) -> str:
    assumed = project.model.assumed_site
    rows = "".join(
        f'<tr data-rough-in="{study._e(point.point_id)}"><td><code>{study._e(point.point_id)}</code></td>'
        f'<td>{study._e(point.kind)}</td><td>x {_dual(point.x_mm)}; y {_dual(point.y_mm)}; z {_dual(point.z_mm)}</td>'
        f'<td><code>{study._e(point.provenance)}</code>; not field verified</td></tr>'
        for point in assumed.wastes + assumed.supplies
    )
    return (
        '<section><h2>Exact owner-assumed rough-ins</h2>'
        '<p>These product-driving endpoints are model inputs, not field observations. Every row remains not field verified.</p>'
        '<div class="table-wrap"><table><thead><tr><th>Point</th><th>Kind</th><th>Project coordinates</th><th>Provenance</th></tr></thead><tbody>'
        + rows + '</tbody></table></div></section>'
    )


def build_double_vanity_review_html(project) -> str:
    body = "".join((
        '<section><h2>Reference-image intent</h2><p><code>IMG_7670.HEIC</code> controls visual intent only: warm figured wood, four flush slab fronts with dark reveals, brass half-moon pulls, a pale substantial counter, broad rectangular sinks, and a clean floating shadow line. Veneer sequence is conditionally selected owner_assumed pending written cabinet-fabricator acceptance. Half-moon brass pulls remain unresolved. The image has no dimensional, structural, plumbing, or fabrication authority.</p></section>',
        _assumption_schedule(project),
        _system_section(project),
        '<section><h2>Overall review geometry</h2><div class="diagram-grid">',
        study._overall_elevation(project), study._overall_plan(project),
        study._wall_load_path(project), "</div></section>",
        _support_and_load_hold(project),
    ))
    return _shell(
        "Review & installation", FILENAMES[0],
        "Primary fit, serviceability, field-survey, and unloaded installation review.",
        project.model.release.installation_status,
        "INSTALLATION HOLD — FIELD VERIFY",
        "Owner-assumed conditions are not field verified. Do not install, drill, load, or connect trades until the named reviewers accept the comparison record.",
        body,
    )


def build_double_vanity_assembly_html(project) -> str:
    fabrication_released, _ = _fabrication_status(project)
    drawers = "".join(
        f'<tr data-drawer-study="{study._e(drawer.drawer_id)}"><td>{study._e(drawer.drawer_id)}</td>'
        f'<td>{study._e(drawer.runner.selected_sku)}</td><td>{study._mm(drawer.box_width_mm)} × '
        f'{study._mm(drawer.box_depth_mm)} × {study._mm(drawer.box_height_mm)}</td>'
        f'<td>{study._mm(drawer.u_void_width_mm)} × {study._mm(drawer.u_void_depth_mm)}</td>'
        f'<td><code>{study._e(drawer.runner.machining_authority)}</code></td></tr>'
        for drawer in project.model.drawers
    )
    if fabrication_released:
        drawer_section = (
            '<section><h2>Released drawer geometry and held assembly authority</h2><p>The conditional fabrication release covers the modeled cabinet and drawer inventory. Runner mounting and machining, plumbing assembly, field drilling, loading, and installation remain held.</p><div class="table-wrap"><table><thead><tr><th>Drawer</th><th>Runner</th><th>Released box W × D × H</th><th>Released U void W × D</th><th>Machining authority</th></tr></thead><tbody>'
            + drawers
            + '</tbody></table></div><p><b>Runner machining remains withheld</b> under the manufacturer-template-controlled authority stored on each drawer.</p></section>'
        )
        status_content = (
            "Cabinet and drawer parts are conditionally released; runner "
            "machining, plumbing assembly, field drilling, loading, and "
            "installation remain held."
        )
    elif project.model.release.fabrication_status == "HOLD_PRODUCT_GEOMETRY":
        drawer_section = (
            '<section><h2>Withheld drawer geometry and assembly authority</h2>'
            '<p>Product geometry is held. Cabinet and drawer cut dimensions, '
            'runner machining, plumbing assembly, field drilling, loading, '
            'and installation remain withheld.</p></section>'
        )
        status_content = (
            "Product geometry, runner machining, plumbing assembly, field "
            "drilling, loading, and installation remain held."
        )
    else:
        drawer_section = (
            '<section><h2>Prepared drawer geometry and held assembly authority</h2>'
            '<p>This non-production schedule is available for fabricator review. '
            'Fabricator acceptance is PENDING; production cuts, runner machining, '
            'plumbing assembly, field drilling, loading, and installation remain held.</p>'
            '<div class="table-wrap"><table><thead><tr><th>Drawer</th><th>Runner</th>'
            '<th>Prepared box W × D × H</th><th>Prepared U void W × D</th>'
            '<th>Machining authority</th></tr></thead><tbody>' + drawers
            + '</tbody></table></div><p><b>Runner machining remains withheld</b> '
            'under the manufacturer-template-controlled authority stored on each drawer.</p></section>'
        )
        status_content = (
            "Prepared non-production drawer geometry awaits fabricator acceptance; "
            "runner machining, assembly, drilling, loading, and installation remain held."
        )
    body = "".join((
        drawer_section,
        _rough_in_section(project),
        '<section><h2>Bay-by-bay plumbing and drawer interaction</h2><div class="diagram-grid">',
        study._bay_interaction(project, "left"),
        study._bay_interaction(project, "right"), "</div></section>",
        study._motion_states(project),
        _system_section(project),
    ))
    return _shell(
        "Assembly & service", FILENAMES[1],
        "Removable-drawer, independent-plumbing, and future-service sequence.",
        project.model.release.installation_status,
        "ASSEMBLY HOLD — MACHINING & INSTALLATION",
        status_content,
        body,
    )


def _fabrication_inventory(project) -> str:
    fabrication_released, _ = _fabrication_status(project)
    product_geometry_held = (
        project.model.release.fabrication_status == "HOLD_PRODUCT_GEOMETRY"
    )
    if product_geometry_held:
        return (
            '<section><h2>Withheld cabinet and drawer inventory</h2>'
            '<p>Product geometry is held. No cabinet or drawer dimensions are '
            'published for fabrication use.</p></section>'
        )
    rows = "".join(
        f'<tr data-cut-list-row="{study._e(item.part_id)}"><td><code>{study._e(item.part_id)}</code></td>'
        f'<td>{study._e(item.description)}</td><td>{study._mm(item.length_mm)} × {study._mm(item.width_mm)} × {study._mm(item.thickness_mm)}</td>'
        f'<td>{study._e(item.material)}; <code>{study._e(project.model.fabrication_basis.provenance)}</code>; not field verified</td></tr>'
        for item in project.artifacts.cut_list
    )
    return (
        '<section><h2>' + (
            'Accepted cabinet and drawer production inventory' if fabrication_released
            else 'Prepared cabinet and drawer inventory — non-production'
        ) + '</h2>'
        f'<p><b>{len(project.artifacts.cut_list)} prepared parts.</b> '
        + ('' if fabrication_released else 'Fabricator acceptance is PENDING; these model outputs are not authorized for production cutting. ')
        + 'Runner drilling/templates, locking-device setup, stone cutting, procurement, wall work, loading, trade work, and installation remain outside this scope.</p>'
        '<div class="table-wrap"><table><thead><tr><th>Part id</th><th>Canonical name</th><th>Prepared size</th><th>Material assumption</th></tr></thead><tbody>'
        + rows + '</tbody></table></div></section>'
    )


def _fabrication_boundaries(project) -> str:
    model = project.model
    fabrication_released, _ = _fabrication_status(project)
    if model.release.fabrication_status == "HOLD_PRODUCT_GEOMETRY":
        return """
<section><h2>Held fabrication boundaries</h2>
<p>Cabinet/drawer product geometry, stone cutting, runner mounting and machining, wall drilling, loading, trade work, and installation remain held. Material, joinery, and finish inputs are <code>owner_assumed</code> and not field verified.</p></section>"""
    upper = model.drawer("left", "upper")
    lower = model.drawer("left", "lower")
    vanity = model.section.vanity
    shop_rows = model.fabrication_basis.shop_schedule()
    shop_schedule = "".join(
        f'<tr><td>{value}</td><td>owner_assumed; not field verified</td></tr>'
        for value in shop_rows
    )
    return f"""
<section><h2>Release boundaries and assumptions</h2>
<div class="table-wrap"><table><thead><tr><th>Scope</th><th>Model fact</th><th>Authority</th></tr></thead><tbody>
<tr><td>Upper runner</td><td>{study._e(upper.runner.selected_sku)}; prepared {study._mm(upper.box_depth_mm)} box depth</td><td><code>{study._e(upper.runner.machining_authority)}</code></td></tr>
<tr><td>Lower runner</td><td>{study._e(lower.runner.selected_sku)}; prepared {study._mm(lower.box_depth_mm)} box depth</td><td><code>{study._e(lower.runner.machining_authority)}</code></td></tr>
<tr><td>Countertop</td><td>{model.fabrication_basis.countertop_structural_thickness_mm:.1f} mm {study._e(model.fabrication_basis.countertop_material)} structural slab and {model.fabrication_basis.countertop_visual_edge_mm:.1f} mm visual edge are controlling owner_assumed case-height and load inputs; substitutions require full model regeneration before stone cut. K-20000 template {study._e(model.countertop.cutout_template_id)} remains controlling for future cutout work.</td><td><code>{study._e(model.countertop.stone_cut_authority)}</code>; not field verified</td></tr>
</tbody></table></div>
<h3>Selected material, joinery, finish, and tolerance schedule</h3><p>Every row is an explicit shop-basis selection, not a product record. The fabricator must accept or replace the complete basis before use; accepted replacements require regeneration of affected cut authority.</p><div class="table-wrap"><table><thead><tr><th>Selected shop basis</th><th>Provenance</th></tr></thead><tbody>{shop_schedule}</tbody></table></div>
<h3>Model-derived sink web and support-zone coordination</h3><p>{study._e(model.fabrication_basis.shop_schedule()[-1])}. The current template and final stone authority remains with the countertop fabricator.</p>
<p><b>Stone cutting remains fabricator-controlled.</b> Runner mounting and machining remain manufacturer-template-controlled. Wall drilling, loading, trade work, and installation remain held.</p></section>"""


def build_double_vanity_fabrication_html(project) -> str:
    fabrication_released, visible_status = _fabrication_status(project)
    if fabrication_released:
        acceptance = project.model.fabrication_acceptance
        evidence = (
            f"Accepted by {study._e(acceptance.accepted_by)} on "
            f"{study._e(acceptance.accepted_on)}; evidence revision "
            f"{study._e(acceptance.evidence_revision)}; exact basis digest "
            f"<code>{study._e(acceptance.basis_digest)}</code>."
        )
        authority = '<section><h2>Fabrication authority</h2><p><b>Cabinet and drawer production inventory is authorized under the recorded typed acceptance.</b> ' + evidence + ' Stone, runner machining, wall work, loading, trade work, and installation remain outside this release.</p></section>'
        status_content = evidence + " Cabinet and drawer production inventory is authorized; stone cutting, runner machining, wall drilling, loading, trade work, and installation remain held."
    elif project.model.release.fabrication_status == "HOLD_PRODUCT_GEOMETRY":
        authority = '<section><h2>Fabrication authority</h2><p><b>Product geometry is held.</b> No cabinet, drawer, stone, runner-machining, wall-work, loading, trade-work, or installation authority is issued.</p></section>'
        status_content = "Product geometry is held. Cabinet, drawer, stone, runner machining, wall drilling, loading, trade work, and installation remain withheld."
    else:
        authority = '<section><h2>Fabrication authority</h2><p><b>Prepared schedule only — non-production.</b> Fabricator acceptance is PENDING. Production cuts require complete signed acceptance of the exact fabrication-basis digest.</p></section>'
        status_content = "Fabricator acceptance is PENDING. The cabinet and drawer schedule is prepared for review only and is not released for production."
    body = "".join((
        authority, _fabrication_inventory(project),
        _fabrication_boundaries(project),
    ))
    return _shell(
        "Fabrication coordination", FILENAMES[2],
        "Scoped cabinet/drawer cut authority, model inventory, and held fabrication boundaries.",
        project.model.release.fabrication_status,
        visible_status,
        status_content,
        body,
    )


def _finding_routing(rule: str) -> tuple[str, str]:
    try:
        return _FINDING_ROUTING[rule]
    except KeyError:
        raise ValueError(f"unmapped DV72 finding rule {rule!r}") from None


def _visible_finding_message(project, finding) -> str:
    fabrication_released, _ = _fabrication_status(project)
    if (
        project.model.release.fabrication_status == "HOLD_PRODUCT_GEOMETRY"
        and finding.rule == "double_vanity.release.drawer_derivation"
    ):
        return (
            "Product geometry hold withholds static drawer-box cuts; restore "
            "the corrected product checks before separately proving runner "
            "drilling/templates, locking-device setup, and dynamic/service access."
        )
    if (
        not fabrication_released
        and finding.rule == "double_vanity.release.drawer_derivation"
    ):
        return (
            "Static drawer-box cuts are prepared for review only; signed "
            "fabricator acceptance of the exact basis digest is required before "
            "production. Runner drilling/templates, locking-device setup, and "
            "dynamic/service access remain separately held."
        )
    return finding.message


def _all_findings(project) -> str:
    rows = []
    for finding in project.report.findings:
        party, phase = _finding_routing(finding.rule)
        rows.append(
            f'<tr data-finding-rule="{study._e(finding.rule)}" '
            f'data-responsible-party="{study._e(party)}" data-blocking-phase="{study._e(phase)}">'
            f'<td><code>{study._e(finding.rule)}</code></td><td class="{study._e(finding.verdict.lower())}">{study._e(finding.verdict)}</td>'
            f'<td>{study._e(party)}</td><td>{study._e(phase)}</td><td>{study._e(_visible_finding_message(project, finding))}</td></tr>'
        )
    return '<section><h2>Validation findings and evidence-request routing</h2><p><b>Coordination routing only.</b> This table routes evidence requests only; approval and release authority is established outside this renderer. PASS does not override a separate UNKNOWN hold.</p><div class="table-wrap"><table><thead><tr><th>Rule</th><th>Verdict</th><th>Evidence request route</th><th>Blocking phase</th><th>Scope</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div></section>'


def _product_evidence(project) -> str:
    model = project.model
    drain = model.drain
    trap = model.trap
    upper_runner = model.drawer("left", "upper").runner
    lower_runner = model.drawer("left", "lower").runner
    mount = model.mount_reference
    fabrication_released, _ = _fabrication_status(project)
    if fabrication_released:
        upper_authority = (
            "Static upper drawer cuts are conditionally released; drilling/templates, "
            "locking-device setup, travel, removal, and service remain held."
        )
        lower_authority = (
            "Static lower drawer cuts are conditionally released; drilling/templates, "
            "locking-device setup, travel, removal, and service remain held."
        )
    elif project.model.release.fabrication_status == "HOLD_PRODUCT_GEOMETRY":
        upper_authority = (
            "Product geometry hold withholds upper drawer cuts; drilling/templates, "
            "locking-device setup, travel, removal, and service also remain held."
        )
        lower_authority = (
            "Product geometry hold withholds lower drawer cuts; drilling/templates, "
            "locking-device setup, travel, removal, and service also remain held."
        )
    else:
        upper_authority = (
            "Static upper drawer cuts are prepared, non-production, and pending "
            "fabricator acceptance; drilling/templates and dynamic access remain held."
        )
        lower_authority = (
            "Static lower drawer cuts are prepared, non-production, and pending "
            "fabricator acceptance; drilling/templates and dynamic access remain held."
        )
    return f"""
<section><h2>Pinned product evidence</h2><div class="table-wrap"><table>
<thead><tr><th>System</th><th>Verified manufacturer fact</th><th>Authority in DV72</th><th>Source</th></tr></thead><tbody>
<tr><td>Kohler {study._e(drain.sku)}</td><td>1-1/4 in overflow drain; {drain.body_height_mm:.1f} mm nominal body below flange</td><td>Product dimensions; final finish, availability, and installation still coordinated with fixture and trap.</td><td><a href="{study._e(drain.specification_url)}">Kohler specification</a></td></tr>
<tr><td>Kohler {study._e(trap.sku)}</td><td>{trap.overall_length_mm:.1f} × {trap.overall_height_mm:.1f} mm gross; 1-1/4 in inlet/outlet; slip joint and cleanout</td><td>Envelope and service candidate. Licensed-plumber layout and installed code compliance remain UNKNOWN.</td><td><a href="{study._e(trap.specification_url)}">Kohler product/CAD record</a></td></tr>
<tr><td>Blum MOVENTO {study._e(upper_runner.selected_sku)}</td><td>18-in full-extension BLUMOTION; {upper_runner.drawer_length_mm:.1f} mm drawer length, opening minus {upper_runner.inside_drawer_width_deduction_mm:.1f} mm inside drawer width, and {upper_runner.minimum_inside_depth_mm:.1f} mm minimum inside-depth check</td><td>{upper_authority}</td><td><a href="{study._e(upper_runner.source_url)}">Blum 2026 planning data, page 15</a></td></tr>
<tr><td>Blum MOVENTO {study._e(lower_runner.selected_sku)}</td><td>12-in full-extension BLUMOTION; {lower_runner.drawer_length_mm:.1f} mm drawer length, opening minus {lower_runner.inside_drawer_width_deduction_mm:.1f} mm inside drawer width, and {lower_runner.minimum_inside_depth_mm:.1f} mm minimum inside-depth check</td><td>{lower_authority}</td><td><a href="{study._e(lower_runner.source_url)}">Blum 2026 planning data, page 15</a></td></tr>
<tr><td>Rakks {study._e(mount.sku)}</td><td>{mount.static_capacity_lb:.0f} lb evenly distributed static load; four secured screws per bracket, up to 48 in spacing under the guide conditions</td><td>comparative reference only; it does not establish DV72 capacity and is not silently combined with the modeled rail/GRK candidate path.</td><td><a href="{study._e(mount.specification_url)}">Rakks installation guide</a></td></tr>
</tbody></table></div></section>"""


def _phased_release_gates(project) -> str:
    preinstall = []
    commissioning = None
    for finding in project.report.findings:
        if not finding.rule.startswith("double_vanity.release."):
            continue
        if finding.rule == "double_vanity.release.commissioning":
            commissioning = finding
            continue
        preinstall.append(
            f'<tr data-release-rule="{study._e(finding.rule)}"><td><code>{study._e(finding.rule)}</code></td>'
            f'<td class="unknown">{study._e(finding.verdict)}</td><td>{study._e(_visible_finding_message(project, finding))}</td></tr>'
        )
    postinstall = ""
    preinstall_count = len(preinstall)
    fabrication_released, _ = _fabrication_status(project)
    if fabrication_released:
        gate_scope = (
            "These UNKNOWN gates block installation, stone, runner machining, "
            "trade work, and use as applicable. They do not revoke the "
            "conditionally released cabinet and drawer cuts."
        )
    elif project.model.release.fabrication_status == "HOLD_PRODUCT_GEOMETRY":
        gate_scope = (
            "These UNKNOWN gates include cabinet and drawer product geometry "
            "and block fabrication, installation, stone, runner machining, "
            "trade work, and use as applicable. No cut authority is issued."
        )
    else:
        gate_scope = (
            "The cabinet and drawer schedule is prepared for review only. Signed "
            "fabricator acceptance of the exact basis digest is required before "
            "production; the remaining UNKNOWN gates continue to block installation, "
            "stone, runner machining, trade work, and use."
        )
    if commissioning is not None:
        postinstall = (
            '<section class="release-gates"><h2>Post-install commissioning hold</h2>'
            f'<p>This hold does not block an installation released by the {preinstall_count} pre-install gates; it blocks use and closeout until testing is recorded.</p>'
            '<div class="table-wrap"><table><tbody>'
            f'<tr data-commissioning-rule="{study._e(commissioning.rule)}"><td><code>{study._e(commissioning.rule)}</code></td>'
            f'<td class="unknown">{study._e(commissioning.verdict)}</td><td>{study._e(commissioning.message)}</td></tr>'
            '</tbody></table></div></section>'
        )
    return (
        f'<section class="release-gates"><h2>{preinstall_count} pre-install release gates</h2>'
        f'<p>{gate_scope}</p>'
        '<div class="table-wrap"><table><thead><tr><th>Rule</th><th>Verdict</th><th>Evidence still required</th></tr></thead><tbody>'
        + "".join(preinstall) + '</tbody></table></div></section>' + postinstall
    )


def build_double_vanity_validation_html(project) -> str:
    body = "".join((
        _product_evidence(project), _all_findings(project),
        _phased_release_gates(project),
        study._facts_tables(project), study._asset_boundary(project),
    ))
    return _shell(
        "Validation & sources", FILENAMES[3],
        "Finding trace and evidence for held installation, stone, runner-machining, trade, and use scopes; cabinet/drawer cut authority remains separately stated.",
        project.model.release.trade_status,
        "TRADE HOLD — RESPONSIBLE APPROVAL",
        "Evidence requests are coordination-routed to named parties and phases. Approval and release authority is established outside this renderer.",
        body,
    )


def build_double_vanity_document_set(project) -> dict[str, str]:
    """Project one compiled model into five ordered, linked documents."""

    if project.pack_id != "vanity.double_sink":
        raise ValueError("DV72 document set requires vanity.double_sink")
    related_documents = tuple(
        RelatedDocumentLink(_LABELS[name], name) for name in FILENAMES
    )
    documents = {
        FILENAMES[0]: build_double_vanity_review_html(project),
        FILENAMES[1]: build_double_vanity_assembly_html(project),
        FILENAMES[2]: build_double_vanity_fabrication_html(project),
        FILENAMES[3]: build_double_vanity_validation_html(project),
        FILENAMES[4]: build_double_vanity_installation_guide(
            project, related_documents=related_documents,
        ),
    }
    _audit_document_set(project, documents)
    return documents


def _audit_document_set(project, documents: dict[str, str]) -> None:
    """Fail closed when the five reader projections contradict typed authority."""

    if tuple(documents) != FILENAMES:
        raise ValueError("DV72 semantic audit requires the ordered five-file package")

    forbidden_authority = (
        r"\bINSTALLATION\s+(?:PASS|APPROVED)\b",
        r"\bINSTALLATION\s+RELEASED(?!\s+BY\b)",
        r"\bUNCONDITIONAL.{0,30}(?:LOAD|INSTALLATION|STRUCTURAL).{0,20}AUTHORITY\b",
        r"\b(?:LOAD|INSTALLATION|STRUCTURAL).{0,20}AUTHORITY.{0,20}UNCONDITIONAL\b",
    )
    for name, html in documents.items():
        upper = html.upper()
        if any(re.search(pattern, upper, re.S) for pattern in forbidden_authority):
            raise ValueError(
                f"DV72 semantic audit rejected unconditional authority in {name}"
            )

    fabrication_released, fabrication_banner = _fabrication_status(project)
    expected_scopes = {
        FILENAMES[0]: (
            "<h1>Review & installation</h1>",
            "INSTALLATION HOLD — FIELD VERIFY",
            f'data-release-status="{project.model.release.installation_status}"',
        ),
        FILENAMES[1]: (
            "<h1>Assembly & service</h1>",
            "ASSEMBLY HOLD — MACHINING & INSTALLATION",
            f'data-release-status="{project.model.release.installation_status}"',
        ),
        FILENAMES[2]: (
            "<h1>Fabrication coordination</h1>",
            fabrication_banner,
            f'data-release-status="{project.model.release.fabrication_status}"',
        ),
        FILENAMES[3]: (
            "<h1>Validation & sources</h1>",
            "TRADE HOLD — RESPONSIBLE APPROVAL",
            f'data-release-status="{project.model.release.trade_status}"',
        ),
        FILENAMES[4]: (
            "<h1>DV72 — Cabinet Installation Guide</h1>",
            "INSTALLATION HOLD — FIELD/STRUCTURAL RELEASE REQUIRED",
            "STOP BEFORE COUNTERTOP",
        ),
    }
    for name, tokens in expected_scopes.items():
        if any(token not in documents[name] for token in tokens):
            raise ValueError(
                f"DV72 semantic audit rejected authority banner/document scope in {name}"
            )

    assembly = documents[FILENAMES[1]].lower()
    if not (
        "installation remain held" in assembly
        or "installation remain withheld" in assembly
    ):
        raise ValueError("DV72 semantic audit rejected assembly installation hold")

    fabrication = documents[FILENAMES[2]]
    validation = documents[FILENAMES[3]]
    guide = documents[FILENAMES[4]]

    if fabrication_released:
        agreement_tokens = (
            (fabrication, "FABRICATOR ACCEPTANCE RECORDED"),
            (validation, "conditionally released"),
            (guide, "Recorded fabricator acceptance governs static drawer cuts only"),
        )
    else:
        agreement_tokens = (
            (fabrication, "Prepared schedule only — non-production"),
            (validation, "prepared for review only"),
            (guide, "Static drawer geometry is prepared for review only"),
        )
    if any(token not in html for html, token in agreement_tokens):
        raise ValueError(
            "DV72 semantic audit rejected fabrication/validation authority agreement"
        )
    if (
        "conditionally released static cuts" in guide.lower()
        or re.search(r"drawer cuts.{0,40}conditionally released", guide, re.I | re.S)
    ):
        raise ValueError("DV72 semantic audit rejected drawer-cut authority contradiction")

    for support in project.model.support_layout.supports:
        facts = (
            f'data-support-id="{support.support_id}" '
            f'data-axis-mm="{support.x_axis_mm:.1f}" '
            f'data-bearing-z-mm="{support.bearing_z_mm:.1f}" '
            f'data-wall-y-mm="{support.wall_y_mm:.1f}" '
            f'data-authority="{support.authority}"'
        )
        if guide.count(facts) != 2:
            raise ValueError("DV72 semantic audit rejected support bearing/wall facts")

    for rule in _REQUIRED_RELEASE_RULES:
        finding = project.report.by_rule(rule)
        token = (
            f'data-release-rule="{rule}" '
            f'data-verdict="{finding.verdict}"'
        )
        if token not in guide:
            raise ValueError("DV72 semantic audit rejected release verdicts")

    if (
        "rear rail: positioning / lateral only · zero gravity credit"
        not in guide
    ):
        raise ValueError("DV72 semantic audit rejected rear-rail zero gravity")
    if (
        "not service-access approval" not in guide
        or "dynamic access remains separately held" not in guide
        or "Both plumbing and drawer envelopes clear" in guide
    ):
        raise ValueError("DV72 semantic audit rejected held service access")
    if (
        "EMPTY CABINET MOUNTED — FOLLOW-ON WORK HELD" not in guide
        or "STOP BEFORE COUNTERTOP" not in guide
        or "continuously supported at three" in guide
    ):
        raise ValueError("DV72 semantic audit rejected empty-cabinet endpoint scope")
