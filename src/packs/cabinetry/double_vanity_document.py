"""Self-contained reader surface for the DV72 coordination study."""

from __future__ import annotations

import html


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _mm(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f} mm"


def _part_group(project, role: str, body: str) -> str:
    part = project.model.part(role)
    return (
        f'<g class="model-part" data-part-id="{_e(part.part_id)}" '
        f'aria-label="{_e(part.name)}"><title>{_e(part.name)}</title>{body}</g>'
    )


def _overall_elevation(project) -> str:
    model = project.model
    vanity = model.section.vanity
    left, right = model.sink_bays
    left_local = left.sink_center_x_mm - vanity.x0_mm
    right_local = right.sink_center_x_mm - vanity.x0_mm
    shell = "".join((
        _part_group(project, "left_end", '<rect x="70" y="120" width="8" height="200"/>'),
        _part_group(project, "center_divider", '<rect x="426" y="120" width="8" height="200"/>'),
        _part_group(project, "right_end", '<rect x="782" y="120" width="8" height="200"/>'),
        _part_group(project, "drawer_front_left_upper", '<rect x="81" y="124" width="341" height="94"/>'),
        _part_group(project, "drawer_front_left_lower", '<rect x="81" y="222" width="341" height="94"/>'),
        _part_group(project, "drawer_front_right_upper", '<rect x="438" y="124" width="341" height="94"/>'),
        _part_group(project, "drawer_front_right_lower", '<rect x="438" y="222" width="341" height="94"/>'),
        _part_group(project, "rear_mounting_rail", '<path d="M78 151H782" class="hidden-rail"/>'),
    ))
    return f"""
<figure class="diagram" data-diagram="overall-elevation">
<figcaption><b>Overall elevation.</b> Four slab fronts, equal sink bays, and a continuous floating body. Sink dimensions name both the vanity-left datum and site-wall x so rough-ins cannot inherit the wrong coordinate system. Half-moon pulls and veneer sequencing remain unresolved.</figcaption>
<svg viewBox="0 0 860 380" role="img" aria-label="DV72 overall elevation">
<rect x="55" y="90" width="750" height="28" class="countertop"/>{shell}
<path d="M210 89q40-42 80 0M567 89q40-42 80 0" class="sink"/>
<path d="M236 171a18 18 0 0 1 36 0M593 171a18 18 0 0 1 36 0M236 269a18 18 0 0 1 36 0M593 269a18 18 0 0 1 36 0" class="pull"/>
<line x1="70" y1="346" x2="790" y2="346" class="dimension"/>
<text x="430" y="368">{_mm(vanity.width_mm)} overall</text>
<text x="250" y="66">vanity-local x = {_mm(left_local)}</text><text x="250" y="82">site-wall x = {_mm(left.sink_center_x_mm)}</text>
<text x="610" y="66">vanity-local x = {_mm(right_local)}</text><text x="610" y="82">site-wall x = {_mm(right.sink_center_x_mm)}</text>
</svg></figure>"""


def _overall_plan(project) -> str:
    model = project.model
    vanity = model.section.vanity
    wall_y = model.section.site.wall.plane_origin_mm[1]
    front_y = wall_y - vanity.body_depth_mm

    def sx(value: float) -> float:
        return 70 + (value - vanity.x0_mm) / vanity.width_mm * 720

    def sy(value: float) -> float:
        return 285 - (value - front_y) / vanity.body_depth_mm * 220

    fixtures = []
    services = []
    drains = []
    faucets = []
    for path in model.plumbing_paths:
        fixture = path.fixture_envelope
        x = sx(fixture.x0_mm)
        y = sy(fixture.y1_mm)
        width = sx(fixture.x1_mm) - x
        height = sy(fixture.y0_mm) - y
        fixtures.append(
            f'<rect data-fixture-envelope="{_e(path.bay_id)}" x="{x:.2f}" '
            f'y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
            'rx="18" class="fixture"/>'
        )
        service = path.service_envelope
        service_x = sx(service.x0_mm)
        service_y = sy(min(service.y1_mm, wall_y))
        service_width = sx(service.x1_mm) - service_x
        service_height = sy(max(service.y0_mm, front_y)) - service_y
        services.append(
            f'<rect data-service-envelope="{_e(path.bay_id)}" '
            f'x="{service_x:.2f}" y="{service_y:.2f}" '
            f'width="{service_width:.2f}" height="{service_height:.2f}" '
            'class="service"/>'
        )
        center_x = sx((fixture.x0_mm + fixture.x1_mm) / 2)
        center_y = sy((fixture.y0_mm + fixture.y1_mm) / 2)
        drains.append(
            f'<circle cx="{center_x:.2f}" cy="{center_y:.2f}" r="7" class="drain"/>'
        )
        faucets.append(
            f'<path d="M{center_x:.2f} 42V{max(50, y - 8):.2f}" class="faucet"/>'
        )
    return f"""
<figure class="diagram" data-diagram="overall-plan">
<figcaption><b>Plan coordination.</b> Provisional top/body, gross basin envelopes, wall-faucet targets, and rear clamp/service zone remain separate. The Kohler template—not these rectangles—controls a future cutout.</figcaption>
<svg viewBox="0 0 860 350" role="img" aria-label="DV72 plan coordination">
<rect x="55" y="55" width="750" height="230" class="countertop"/><rect x="70" y="65" width="720" height="220" class="case"/>
{''.join(fixtures)}{''.join(drains)}{''.join(faucets)}{''.join(services)}
<text x="255" y="326">body depth {_mm(vanity.body_depth_mm)}</text><text x="605" y="326">top depth {_mm(vanity.countertop_depth_mm)}</text>
</svg></figure>"""


def _bay_section(project) -> str:
    model = project.model
    upper = model.drawer("left", "upper")
    lower = model.drawer("left", "lower")
    return f"""
<figure class="diagram" data-diagram="bay-section">
<figcaption><b>Typical bay section.</b> Basin, trap service envelope, U-shaped upper drawer, shortened lower drawer, rear chase, wall rough-in, and rail are checked separately.</figcaption>
<svg viewBox="0 0 760 440" role="img" aria-label="Typical sink-bay section">
<rect x="90" y="55" width="520" height="30" class="countertop"/><path d="M250 86q100 160 200 0" class="fixture"/>
<path d="M350 204v38q0 30 42 30h55v-35" class="plumbing"/>
<rect x="145" y="140" width="150" height="72" class="drawer"/><rect x="405" y="140" width="150" height="72" class="drawer"/>
<text x="350" y="132">provisional U topology · cut dimensions held</text>
<rect x="145" y="280" width="300" height="82" class="drawer"/><rect x="445" y="280" width="110" height="82" class="service"/>
<text x="295" y="330">lower box stops ahead of services</text><text x="500" y="330">rear chase</text>
<rect x="610" y="80" width="18" height="282" class="wall"/><path d="M610 150H520" class="load-path"/>
</svg></figure>"""


def _bay_interaction(project, bay_id: str) -> str:
    model = project.model
    bay = next(item for item in model.sink_bays if item.bay_id == bay_id)
    path = next(item for item in model.plumbing_paths if item.bay_id == bay_id)
    upper = model.drawer(bay_id, "upper")
    lower = model.drawer(bay_id, "lower")
    return f"""
<figure class="diagram" data-diagram="{bay_id}-bay-interaction" data-plumbing-path="{_e(path.path_id)}">
<figcaption><b>{bay_id.title()} service bay.</b> One independently trapped lavatory, one upper U-shaped service drawer, and one shortened lower drawer. Removing both boxes exposes a shell-derived {_mm(bay.clear_opening_width_mm)} × {_mm(bay.clear_opening_height_mm)} opening; fitting/tool access is still unverified.</figcaption>
<svg viewBox="0 0 520 400" role="img" aria-label="{bay_id.title()} bay interaction">
<rect x="45" y="40" width="430" height="310" class="case"/><path d="M160 55q100 120 200 0" class="fixture"/><path d="M260 160v35q0 28 45 28h60" class="plumbing"/>
<path d="M90 145H190V270H90zM330 145H430V270H330z" class="drawer"/><rect x="90" y="285" width="270" height="50" class="drawer"/><rect x="360" y="285" width="70" height="50" class="service"/>
<text x="260" y="385">sink center {_mm(bay.sink_center_x_mm)}</text></svg>
<div class="study-facts">
<p data-drawer-study="{_e(upper.drawer_id)}"><b>upper U-shaped service drawer</b> — a ten-piece analytic box now expresses the basin/plumbing-derived notch with two floor wings, a front bridge, and two inner returns. Fabrication dimensions remain suppressed until fixture, rough-in, runner, and joinery release.</p>
<p data-drawer-study="{_e(lower.drawer_id)}"><b>shortened lower drawer</b> — its analytic rear plane derives from the provisional plumbing obstacles and stops ahead of the rear chase. Its cut depth and runner SKU remain suppressed.</p>
</div></figure>"""


def _wall_load_path(project) -> str:
    model = project.model
    anchors = ", ".join(model.anchor_stud_ids)
    vanity = model.section.vanity
    anchor_marks = []
    for stud_id in model.anchor_stud_ids:
        anchor = model.part(f"wall_anchor_{stud_id}")
        x = 110 + (anchor.at_mm[0] - vanity.x0_mm) / vanity.width_mm * 540
        anchor_marks.append(
            f'<path d="M{x:.2f} 40V103" class="load-path"/>'
            f'<circle data-anchor-stud="{_e(stud_id)}" cx="{x:.2f}" '
            'cy="103" r="7" class="anchor"/>'
        )
    return f"""
<figure class="diagram" data-diagram="wall-load-path">
<figcaption><b>Wall-mount representation—not capacity.</b> Candidate path: top/fixtures/contents → case → continuous rail → candidate fastener axes → surveyed framing. Study targets: {_e(anchors)}.</figcaption>
<svg viewBox="0 0 860 320" role="img" aria-label="Floating vanity candidate wall load path">
<rect x="80" y="55" width="600" height="170" class="case"/><rect x="110" y="80" width="540" height="45" class="rail"/><rect x="700" y="25" width="35" height="245" class="wall"/>
<path d="M110 103H735" class="load-path"/>{''.join(anchor_marks)}
<text x="380" y="300">{_mm(model.section.vanity.width_mm)} floating span · capacity UNKNOWN</text>
</svg></figure>"""


def _motion_states(project) -> str:
    model = project.model
    upper = model.drawer("left", "upper")
    opening = model.sink_bays[0].service_opening_smallest_mm
    states = (
        (
            "closed", "Closed",
            f"Provisional analytic obstacle margin: {_mm(upper.closed_clearance_mm or 0)}; not release evidence.",
            "The manufacturer-sized basin and provisional plumbing solids fit inside the analytic U target. Runner, joinery, tolerance, and rough-in remain unresolved.",
        ),
        (
            "full-extension", "Full extension", "UNKNOWN — dynamic gate open.",
            "Required swept-path check; unverified until the runner SKU, locking devices, box construction, loads, and actual services are selected.",
        ),
        (
            "removal", "Removal", "UNKNOWN — dynamic gate open.",
            "Required release/lift/removal check; no achieved clearance is claimed.",
        ),
        (
            "service", "Service",
            f"Static shell-opening smallest dimension: {_mm(opening)}.",
            "Both boxes are removed in the study; fitting, valve, hand, and tool paths remain unverified.",
        ),
    )
    cards = "".join(
        f'<article data-motion-state="{state}"><div class="state-pictogram state-{state}"></div><h3>{label}</h3><p>{text}</p><p class="metric">{metric}</p></article>'
        for state, label, metric, text in states
    )
    return f'<section><h2>Four required motion and service states</h2><div class="states">{cards}</div></section>'


def _facts_tables(project) -> str:
    model = project.model
    sink = model.sink
    faucet = model.faucet
    code = model.code_profile
    if code.profile_id == "nyc_2022":
        selected_trap_label = "NYC 2022"
        cross_trap_label = "IPC 2024"
        cross_trap_value = 24 * 25.4
    else:
        selected_trap_label = "IPC 2024"
        cross_trap_label = "NYC 2022"
        cross_trap_value = 48 * 25.4
    return f"""
<section><h2>Fixture, top, and faucet coordination</h2>
<div class="table-wrap"><table><thead><tr><th>System</th><th>Pinned study fact</th><th>Release boundary</th></tr></thead><tbody>
<tr><td>Kohler {sink.sku}</td><td>Gross {sink.overall_width_mm:.1f} × {sink.overall_depth_mm:.1f} × {sink.overall_height_mm:.1f} mm; bowl {sink.bowl_width_mm:.1f} × {sink.bowl_depth_mm:.1f} × {sink.bowl_height_mm:.1f} mm; drain {_mm(sink.drain_diameter_mm)}; tailpiece {_mm(sink.tailpiece_od_mm, 2)}</td><td>Current template {sink.cutout_template_id} and fabricator approval required; nominal bounds are not a cutout.</td></tr>
<tr><td>{faucet.trim_sku} + {faucet.valve_sku}</td><td>Nominal wall-to-drain {_mm(faucet.nominal_wall_to_drain_mm)}; reach {_mm(faucet.reach_range_mm[0])}–{_mm(faucet.reach_range_mm[1])}; spout/rim {_mm(faucet.spout_to_rim_range_mm[0])}–{_mm(faucet.spout_to_rim_range_mm[1])}</td><td>Final wall build-up, bores, water target, valve/service space, and top depth remain coupled.</td></tr>
<tr><td>Provisional top</td><td>{_mm(model.section.vanity.countertop_depth_mm)} deep × {_mm(model.section.vanity.countertop_thickness_mm)} thick</td><td>Material, web, reinforcement, clamps, reveal, sealant, and edge rules are unresolved.</td></tr>
</tbody></table></div></section>
<section><h2>Jurisdiction-scoped plumbing checkpoints</h2>
<p>This study selects <b>{_e(code.jurisdiction)} — {_e(code.edition)}</b>. Values are not universal. A Licensed Master Plumber must approve installed waste, vent, supplies, access, and fittings.</p>
<div class="table-wrap"><table><thead><tr><th>Checkpoint</th><th>Selected profile</th><th>Cross-check</th></tr></thead><tbody>
<tr><td>Lavatory center to side obstruction</td><td>{_mm(code.lavatory_side_clearance_mm)}</td><td>Study provides {_mm(18 * 25.4)} outer offsets</td></tr>
<tr><td>Lavatory center-to-center</td><td>{_mm(code.lavatory_center_spacing_mm)}</td><td>Study provides {_mm(36 * 25.4)}</td></tr>
<tr><td>Clear in front</td><td>{_mm(code.front_clearance_mm)}</td><td>Site survey gate</td></tr>
<tr><td>Outlet to trap-weir vertical maximum</td><td>{selected_trap_label} {_mm(code.outlet_to_trap_weir_vertical_max_mm)}</td><td>{cross_trap_label} {_mm(cross_trap_value)}; deliberate profile difference</td></tr>
<tr><td>Concealed slip-joint access</td><td>smallest dimension {_mm(code.concealed_access_min_mm)}</td><td>Shell opening smallest dimension {_mm(model.sink_bays[0].service_opening_smallest_mm)}; tool path still gated</td></tr>
</tbody></table></div>
<p>Primary profile sources: <a href="{_e(code.source_url)}">fixture spacing and access</a>; <a href="{_e(code.trap_source_url)}">trap topology and distances</a>.</p>
<p>Topology: <b>two independent P-traps</b>, one per lavatory; no S-trap or double-trap is emitted.</p>
<p><b>Alternative studied, not selected:</b> manufacturer-integrated <a href="https://www.geberit.com/en/insights/new-design-possibilities-at-the-washplace/">Geberit ONE</a> space-saving drain systems can eliminate a conventional trap cutout and preserve more drawer volume. They are a coupled fixture/drain system and are not interchangeable with the selected Kohler basin by assumption.</p></section>"""


def _release_gates(project) -> str:
    rows = []
    for finding in project.report.findings:
        if finding.rule.startswith("double_vanity.release."):
            rows.append(
                f'<tr data-release-rule="{_e(finding.rule)}"><td><code>{_e(finding.rule)}</code></td>'
                f'<td class="unknown">{_e(finding.verdict)}</td><td>{_e(finding.message)}</td></tr>'
            )
    return (
        '<section class="release-gates"><h2>Nine required release gates</h2>'
        '<p>Every row is required and UNKNOWN. Honest UNKNOWN blocks release; a complete-looking drawing cannot override it.</p>'
        '<div class="table-wrap"><table><thead><tr><th>Rule</th><th>Verdict</th><th>Evidence still required</th></tr></thead><tbody>'
        + "".join(rows) + '</tbody></table></div></section>'
    )


def _mount_and_workflow() -> str:
    return """
<section><h2>Reference installation patterns—not a DV72 prescription</h2>
<p>Two current Kohler wall-hung vanity guides provide useful comparison evidence. They require framing or continuous 2x6 backing, fastening through a back rail into the available framing, temporary support while the body is positioned, and level and plumb verification before the heavy top is installed. One guide calls for pilot holes at the rail ends and at all studs behind the rail. Its product-specific fastener and load language does not establish capacity for this different vanity.</p>
<div class="table-wrap"><table><thead><tr><th>Reference pattern</th><th>DV72 engine consequence</th><th>Authority</th></tr></thead><tbody>
<tr><td>Survey the wall and install 2x6 backing where framing is insufficient.</td><td>Record the actual framing/backing geometry; never manufacture a stud or anchor capacity from the photograph.</td><td><a href="https://resources.kohler.com/webassets/kpna/catalog/pdf/en/1527256-2.pdf">Kohler vanity installation guide 1527256-2</a></td></tr>
<tr><td>Use a temporary support, set the body level and plumb, then fasten the continuous rail into verified framing.</td><td>Derive support height, pilot holes, fastener count, spacing, edge distance, embedment, and installation torque only after structural release.</td><td><a href="https://techcomm.kohler.com/techcomm/pdf/1216526-2.pdf">Kohler wall-hung vanity guide 1216526-2</a></td></tr>
<tr><td>Install the heavy top only after the wall-hung body is secure and level.</td><td>The DV72 load calculation must include the accepted top, two fixtures, water, drawers, contents, and service loads.</td><td>Comparative manufacturer sequence; project calculation required</td></tr>
</tbody></table></div>
<h3>Release-dependent coordination workflow</h3>
<p>This sequence shows the dependencies the engine must eventually resolve; it <b>does not authorize field work</b>.</p>
<ol>
<li>Survey the finished wall/floor datums, framing/backing, room clearances, and both waste/supply locations.</li>
<li>Coordinate the two fixture templates, wall-faucet valves, top geometry, trap families, shutoffs, and service envelopes.</li>
<li>Re-derive both U-shaped upper boxes, both shortened lower boxes, runners, and removal/tool clearances from the accepted rough-in.</li>
<li>Release the case, rear rail, joinery, backing, fasteners, and temporary-support method through project-specific structural review.</li>
<li>Mount the empty body; verify rail engagement, level, plumb, anchor installation, and the accepted load path before installing the top.</li>
<li>Install the approved top, basins, faucets, supplies, drains, and two independent traps under the responsible trades' instructions.</li>
<li>Leak-test both independent plumbing paths before drawers return; then verify full travel, removal, loaded operation, and service access.</li>
</ol></section>"""


def _inventory(project) -> str:
    rows = "".join(
        f'<tr><td><code>{_e(item.part_id)}</code></td><td>{_e(item.description)}</td>'
        f'<td>{_mm(item.length_mm)} × {_mm(item.width_mm)} × {_mm(item.thickness_mm)}</td>'
        f'<td>{_e(item.material)}</td></tr>'
        for item in project.artifacts.cut_list
    )
    drawer_rows = []
    for drawer in project.model.drawers:
        if drawer.level == "upper":
            motion = (
                f"MOVENTO {drawer.runner.selected_sku}; "
                f"{drawer.runner.minimum_drawer_length_mm:.1f} mm minimum "
                "drawer length and 477.0 mm minimum inside-depth check pass "
                "for the analytic closed position; fixing, joinery, load, "
                "travel, removal, and actual-service checks remain gated"
            )
        else:
            motion = (
                "full-extension/soft-close performance required, but the lower "
                "runner family itself remains unselected because this short "
                "study envelope is below MOVENTO applicability"
            )
        drawer_rows.append(
            f'<li data-drawer-id="{_e(drawer.drawer_id)}"><b>{_e(drawer.drawer_id)}'
            f'</b>: {_e(drawer.kind)}, removable; {_e(motion)}. Cut dimensions '
            'and joinery withheld.</li>'
        )
    drawers = "".join(drawer_rows)
    return (
        '<section><h2>Model inventory and unresolved procurement</h2>'
        '<p>MOVENTO 763.4570S applies only to the upper U drawers. Lower '
        'hardware remains a performance requirement, not a selected catalog '
        'claim.</p><ul>' + drawers
        + '</ul><p>Four half-moon brass pulls, four runner/locking-device sets, drawer joinery, sheet product/SKU, veneer sequence, edge band, finish, top, sinks, clamps, faucet/valves, traps, supplies, shutoffs, sealants, backing, and structural fasteners remain procurement or coordination items. No quantity here authorizes purchase.</p>'
        + '<div class="table-wrap"><table><thead><tr><th>Model id</th><th>Canonical name</th><th>Provisional study size</th><th>Status</th></tr></thead><tbody>'
        + rows + '</tbody></table></div></section>'
    )


def _asset_boundary(project) -> str:
    rows = "".join(
        f'<tr><td><code>{_e(asset.asset_id)}</code></td><td>{_e(asset.manufacturer)} {_e(asset.sku)}</td>'
        f'<td>{_e(asset.asset_role)} / visual/reference only</td>'
        f'<td>{_e(asset.license_class)}; redistribution: {_e(asset.redistribution)}</td>'
        f'<td><a href="{_e(asset.source_page_url)}">official source</a></td></tr>'
        for asset in project.model.catalog_assets
    )
    return (
        '<section><h2>Public-model acceleration boundary</h2>'
        '<p>The external CAD cache is optional. Manufacturer/community geometry may speed visualization and gross-clash review, but it <b>cannot control cut lists, machining, plumbing, structure, or code</b>. Analytic adapters remain construction truth; the study is deterministic with the cache absent.</p>'
        '<div class="table-wrap"><table><thead><tr><th>Reference</th><th>Product</th><th>Authority</th><th>License policy</th><th>Source</th></tr></thead><tbody>'
        + rows + '</tbody></table></div></section>'
    )


def build_double_vanity_study_html(project) -> str:
    """Render one deterministic, self-contained, explicitly blocked study."""

    if project.pack_id != "vanity.double_sink":
        raise ValueError("double-vanity study renderer requires vanity.double_sink")
    if project.report.fabrication_ready:
        raise ValueError("DV72 v1 study unexpectedly crossed its fabrication gate")
    vanity = project.model.section.vanity
    css = """
:root{--ink:#24322d;--muted:#647069;--paper:#fcfaf5;--line:#c9c7bb;--wood:#a87345;--wood2:#cf9c6a;--stone:#ebe7dd;--warn:#8e2d24;--warnbg:#f9e8e4;--service:#f4c95d;--pipe:#3979a8}
*{box-sizing:border-box}body{margin:0;background:#e8e5de;color:var(--ink);font:15px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}.sheet{width:min(1500px,100%);margin:auto;background:var(--paper);padding:34px 40px 70px}header{display:grid;grid-template-columns:2fr 1fr;gap:24px;border-bottom:3px solid var(--ink);padding-bottom:22px}.eyebrow{font:800 12px/1.2 ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--warn)}h1{font-size:clamp(32px,5vw,62px);line-height:1;margin:.2em 0}h2{margin:40px 0 12px;border-bottom:1px solid var(--line);padding-bottom:7px}.hold{background:var(--warnbg);border:2px solid var(--warn);padding:16px;color:#6f211b}.visual-intent{background:#eee2d4;border-left:5px solid var(--wood);padding:14px 18px;margin:22px 0}.diagram-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.diagram{margin:0;border:1px solid var(--line);background:white;min-width:0}.diagram figcaption{padding:12px 14px;color:var(--muted)}svg{display:block;width:100%;height:auto;background:#faf8f2}svg text{font:13px ui-sans-serif,system-ui;fill:var(--ink);text-anchor:middle}.model-part rect,.model-part path,.case,.drawer{fill:var(--wood2);stroke:#61452f;stroke-width:2}.model-part:hover rect,.model-part:hover path{fill:#e2b37f}.countertop{fill:var(--stone);stroke:#8d8a82;stroke-width:2}.fixture,.sink{fill:#fff;stroke:#638a86;stroke-width:3}.pull{fill:none;stroke:#9a6d20;stroke-width:7}.hidden-rail{fill:none;stroke:#5a4232;stroke-width:8;stroke-dasharray:9 5}.dimension{stroke:#34433b;stroke-width:1}.drain{fill:var(--pipe)}.faucet,.plumbing{fill:none;stroke:var(--pipe);stroke-width:7}.service{fill:var(--service);fill-opacity:.4;stroke:#b28c25;stroke-dasharray:7 5}.wall{fill:#dad7ce;stroke:#74716a}.rail{fill:#7d5a3b}.load-path{fill:none;stroke:var(--warn);stroke-width:7}.anchor{fill:var(--warn)}.study-facts{padding:0 14px 14px}.states{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.states article{border:1px solid var(--line);background:#fff;padding:14px}.state-pictogram{height:80px;background:linear-gradient(90deg,var(--wood2) 0 55%,var(--service) 55% 76%,transparent 76%);border:1px solid var(--line)}.state-full-extension{transform:translateX(8px)}.state-removal{opacity:.55;transform:translateY(-8px)}.state-service{background:linear-gradient(90deg,transparent 0 35%,var(--service) 35% 70%,transparent 70%)}.metric{font:12px ui-monospace,monospace;color:var(--muted)}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid var(--line);padding:8px;vertical-align:top;text-align:left}th{background:#eeece5}.unknown{font-weight:900;color:var(--warn)}code{font:11px ui-monospace,monospace;overflow-wrap:anywhere}a{color:#76501e}.release-gates{border:2px solid var(--warn);padding:0 18px 18px;background:#fff9f7}footer{margin-top:45px;border-top:2px solid var(--ink);padding-top:15px;color:var(--muted)}
@media(max-width:800px){.sheet{padding:20px 14px 45px}header,.diagram-grid{grid-template-columns:1fr}.states{grid-template-columns:1fr 1fr}}@media(max-width:480px){.states{grid-template-columns:1fr}}
"""
    body = "".join((
        f'<header><div><div class="eyebrow">vanity.double_sink@1 · analytic coordination engine</div><h1>{_e(project.project_doc.name)}</h1><p>Photo-inspired floating vanity study with two sinks, four removable drawers, and independently modeled plumbing/service bays.</p></div><div class="hold"><b>DESIGN STUDY — NOT A BUILD DOCUMENT</b><p>Do not purchase, cut, drill, fabricate, or install from this study. All nine required release gates remain UNKNOWN.</p></div></header>',
        '<section class="visual-intent"><b>Reference photograph controls visual intent only.</b> It supports a warm figured-wood floating body, four slab fronts, dark reveals, half-moon brass pulls, a light stone top, and two broad rectangular sinks. It does not supply scale, fixture SKUs, plumbing, joinery, wall construction, capacity, or code evidence.</section>',
        f'<section><h2>Overall geometry</h2><p>{_mm(vanity.width_mm)} W × {_mm(vanity.body_height_mm)} body H × {_mm(vanity.body_depth_mm)} body D; {_mm(vanity.bottom_elevation_mm)} above floor datum. Two nominal {_mm(vanity.width_mm / 2)} bays.</p><div class="diagram-grid">',
        _overall_elevation(project), _overall_plan(project), _bay_section(project),
        _wall_load_path(project), '</div></section>',
        '<section><h2>Sink, plumbing, and drawer interaction by bay</h2><div class="diagram-grid">',
        _bay_interaction(project, "left"), _bay_interaction(project, "right"),
        '</div></section>', _motion_states(project), _facts_tables(project),
        _mount_and_workflow(), _release_gates(project), _inventory(project),
        _asset_boundary(project),
        '<footer>Generated from analytic pack facts and unchanged DetailSpec lowering. No imported mesh, reference photograph, or presentation literal may override fixture templates, plumbing/service envelopes, drawer derivation, structural review, or jurisdiction-scoped code evidence.</footer>',
    ))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,">
<title>{_e(project.project_doc.name)} — Coordination Study</title><style>{css}</style></head>
<body><main class="sheet">{body}</main></body></html>"""
