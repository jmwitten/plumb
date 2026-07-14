"""Focused linked reader documents for the DV72 analytic vanity model."""

from __future__ import annotations

from . import double_vanity_document as study


FILENAMES = (
    "dv72_review_installation.html",
    "dv72_assembly_service.html",
    "dv72_fabrication_coordination.html",
    "dv72_validation_sources.html",
)

_LABELS = {
    FILENAMES[0]: "Review & installation",
    FILENAMES[1]: "Assembly & service",
    FILENAMES[2]: "Fabrication coordination",
    FILENAMES[3]: "Validation & sources",
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


def _shell(title: str, current: str, purpose: str, body: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,">
<title>DV72 — {title}</title><style>{_CSS}</style></head><body><main class="sheet">
<header><div><div class="eyebrow">DV72 · vanity.double_sink@1</div><h1>{title}</h1><p>{purpose}</p></div>
<div class="hold"><b>DESIGN HOLD</b><p>Coordination geometry only. Do not purchase, cut, drill, fabricate, load, or install until the named release gates are closed.</p></div></header>
{_nav(current)}{body}{_nav(current)}<footer>One analytic model; four reader projections. UNKNOWN is a release hold, never a concealed approval.</footer>
<p class="metric">Issue date: 2026-07-14 · Revision: 1 · Status: DESIGN HOLD · Model: vanity.double_sink@1.0.0</p>
</main></body></html>"""


def _dual(mm: float) -> str:
    return f"{mm:.1f} mm / {mm / 25.4:.2f} in"


def _system_section(project) -> str:
    """One model-labelled bay section showing every coordination system."""

    model = project.model
    vanity = model.section.vanity
    path = model.plumbing_paths[0]
    upper = model.drawer("left", "upper")
    lower = model.drawer("left", "lower")
    counter_top = vanity.bottom_elevation_mm + vanity.body_height_mm + vanity.countertop_thickness_mm
    return f"""
<section><h2>Sink, plumbing, drawers, counter, and wall mount</h2>
<p>Representative section through one of two symmetric bays. Yellow is the removable service envelope, not storage. Dimensions are model facts; the accepted field rough-in must re-derive the drawer voids before fabrication.</p>
<p><b>Field vertical targets—not release dimensions:</b> cabinet bottom {_dual(vanity.bottom_elevation_mm)} AFF; counter top {_dual(counter_top)} AFF. The site-wall zero datum is the left end of the surveyed wall run; verify it, the floor datum, wall flatness, framing, and every plumbing centerline before release.</p>
<figure class="diagram"><figcaption>Bay section · counter top {_dual(counter_top)} AFF · upper box {study._mm(upper.box_depth_mm)} deep · lower box {study._mm(lower.box_depth_mm)} deep · rear service chase {study._mm(model.service_chase_depth_mm)}</figcaption>
<svg viewBox="0 0 900 520" role="img" aria-label="Section through sink, drain, trap, drawers, counter, rear rail, wall and anchors">
<rect data-section-system="wall" x="790" y="25" width="55" height="455" class="wall"/><rect data-section-system="rear-rail" x="730" y="178" width="60" height="42" class="rail"/>
<rect data-section-system="countertop" x="90" y="55" width="700" height="32" class="countertop"/><path data-section-system="fixture" d="M260 87h360l-35 116H295z" class="fixture"/>
<path data-section-system="drain" d="M440 203v65" class="pipe"/><path data-section-system="p-trap" d="M440 268v48q0 45 52 45t52-45v-8h185" class="pipe"/>
<rect data-section-system="service-envelope" x="335" y="188" width="400" height="205" class="service"/>
<path data-section-system="upper-drawer" d="M110 248h205v145h420v-42H355V248z" class="drawer"/><rect data-section-system="lower-drawer" x="110" y="402" width="430" height="68" class="drawer"/>
<circle data-section-system="candidate-anchor" cx="807" cy="199" r="8" fill="#8e2d24"/><text x="450" y="505">proposed service-access concept; hand and tool paths remain unverified.</text>
</svg></figure></section>
<section><h2>Drawer-removal service sequence</h2><p><b>Proposed sequence—conditional on runner validation.</b> This is not a current service instruction.</p><ol><li>If runner validation proves the removal motion and locking-device access, empty and remove the upper U drawer.</li><li>If the selected lower runner proves removable, remove the lower drawer when rear-wall, rail, or anchor access is required.</li><li>Place a pan below each independent P-trap; service the cleanout/slip joints and both shutoffs only after field verification proves the proposed hand and tool paths.</li><li>Leak-test supplies, overflow drain, tailpiece, trap, and trap arm before either drawer returns.</li><li>Reinstall only under the validated hardware procedure, adjust reveals, cycle closed/full-extension/removal states, and record commissioning.</li></ol></section>
"""


def build_double_vanity_review_html(project) -> str:
    body = "".join((
        '<section><h2>Reference-image intent</h2><p><code>IMG_7670.HEIC</code> controls visual intent only: warm figured wood, four flush slab fronts with dark reveals, brass half-moon pulls, a pale substantial counter, broad rectangular sinks, and a clean floating shadow line. It has no dimensional, structural, plumbing, or fabrication authority.</p></section>',
        _system_section(project),
        '<section><h2>Overall review geometry</h2><div class="diagram-grid">',
        study._overall_elevation(project), study._overall_plan(project),
        study._wall_load_path(project), "</div></section>",
        study._mount_and_workflow(),
    ))
    return _shell(
        "Review & installation", FILENAMES[0],
        "Primary fit, serviceability, field-survey, and unloaded installation review.",
        body,
    )


def build_double_vanity_assembly_html(project) -> str:
    body = "".join((
        '<section><h2>Proposed shell assembly</h2><p>After fabrication release, square the two-bay shell around the center divider and continuous rear rail. Drawer dimensions remain coordination targets until the accepted trap, rough-in, runner SKU, and service sweeps close their gates.</p></section>',
        '<section><h2>Bay-by-bay plumbing and drawer interaction</h2><div class="diagram-grid">',
        study._bay_interaction(project, "left"),
        study._bay_interaction(project, "right"), "</div></section>",
        study._motion_states(project),
        _system_section(project),
    ))
    return _shell(
        "Assembly & service", FILENAMES[1],
        "Removable-drawer, independent-plumbing, and future-service sequence.",
        body,
    )


def build_double_vanity_fabrication_html(project) -> str:
    body = "".join((
        '<section><h2>Fabrication authority</h2><p><b>No cut authorization is issued.</b> The case inventory is useful for stock, grain, finish, and joinery coordination; drawer cut dimensions and machining remain withheld until the accepted plumbing and hardware derivation is replayed.</p></section>',
        study._inventory(project),
        '<section><h2>Fabrication prerequisites</h2><ol><li>Approve sheet product, face veneer, grain sequence, edge band, finish, adhesives, and joinery.</li><li>Accept current sink templates and countertop web/reinforcement details.</li><li>Accept both trap/rough-in layouts, runner SKUs, U-void geometry, dynamic travel, and service sweeps.</li><li>Release the rear rail, case joinery, backing, anchors, and temporary support through project-specific structural review.</li></ol></section>',
    ))
    return _shell(
        "Fabrication coordination", FILENAMES[2],
        "Model inventory and the exact evidence required before a shop cut list can be released.",
        body,
    )


def _all_findings(project) -> str:
    rows = "".join(
        f'<tr><td><code>{study._e(f.rule)}</code></td><td class="{study._e(f.verdict.lower())}">{study._e(f.verdict)}</td><td>{study._e(f.message)}</td></tr>'
        for f in project.report.findings
        if not f.rule.startswith("double_vanity.release.")
    )
    return '<section><h2>Analyzed invariants</h2><div class="table-wrap"><table><thead><tr><th>Rule</th><th>Verdict</th><th>Scope</th></tr></thead><tbody>' + rows + '</tbody></table></div></section>'


def _product_evidence(project) -> str:
    model = project.model
    drain = model.drain
    trap = model.trap
    runner = model.drawer("left", "upper").runner
    mount = model.mount_reference
    return f"""
<section><h2>Pinned product evidence</h2><div class="table-wrap"><table>
<thead><tr><th>System</th><th>Verified manufacturer fact</th><th>Authority in DV72</th><th>Source</th></tr></thead><tbody>
<tr><td>Kohler {study._e(drain.sku)}</td><td>1-1/4 in overflow drain; {drain.body_height_mm:.1f} mm nominal body below flange</td><td>Product dimensions; final finish, availability, and installation still coordinated with fixture and trap.</td><td><a href="{study._e(drain.specification_url)}">Kohler specification</a></td></tr>
<tr><td>Kohler {study._e(trap.sku)}</td><td>{trap.overall_length_mm:.1f} × {trap.overall_height_mm:.1f} mm gross; 1-1/4 in inlet/outlet; slip joint and cleanout</td><td>Envelope and service candidate. Licensed-plumber layout and installed code compliance remain UNKNOWN.</td><td><a href="{study._e(trap.specification_url)}">Kohler product/CAD record</a></td></tr>
<tr><td>Blum MOVENTO {study._e(runner.selected_sku)}</td><td>18-in full-extension BLUMOTION candidate; {runner.minimum_drawer_length_mm:.1f} mm box and {runner.minimum_inside_depth_mm:.1f} mm inside-depth checks</td><td>Upper drawers only; actual fixing, locking devices, loads, travel, removal, and service sweeps remain gated.</td><td><a href="{study._e(runner.source_url)}">Blum 2026 planning data</a></td></tr>
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
            f'<td class="unknown">{study._e(finding.verdict)}</td><td>{study._e(finding.message)}</td></tr>'
        )
    postinstall = ""
    if commissioning is not None:
        postinstall = (
            '<section class="release-gates"><h2>Post-install commissioning hold</h2>'
            '<p>This hold does not block an installation released by the eight pre-install gates; it blocks use and closeout until testing is recorded.</p>'
            '<div class="table-wrap"><table><tbody>'
            f'<tr data-commissioning-rule="{study._e(commissioning.rule)}"><td><code>{study._e(commissioning.rule)}</code></td>'
            f'<td class="unknown">{study._e(commissioning.verdict)}</td><td>{study._e(commissioning.message)}</td></tr>'
            '</tbody></table></div></section>'
        )
    return (
        '<section class="release-gates"><h2>Eight pre-install release gates</h2>'
        '<p>Every row is required and UNKNOWN. Close all eight before purchase, fabrication, loading, or installation.</p>'
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
        "Complete finding trace, manufacturer evidence, code profile, CAD authority boundary, and release holds.",
        body,
    )


def build_double_vanity_document_set(project) -> dict[str, str]:
    """Project one compiled model into four ordered, linked documents."""

    if project.pack_id != "vanity.double_sink":
        raise ValueError("DV72 document set requires vanity.double_sink")
    return {
        FILENAMES[0]: build_double_vanity_review_html(project),
        FILENAMES[1]: build_double_vanity_assembly_html(project),
        FILENAMES[2]: build_double_vanity_fabrication_html(project),
        FILENAMES[3]: build_double_vanity_validation_html(project),
    }
