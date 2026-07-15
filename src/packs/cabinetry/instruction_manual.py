"""Cabinetry content adapter for the shared CPG instruction-panel engine."""

from __future__ import annotations

from dataclasses import replace

from ...rendering.instruction_panels import (
    DiagramPrimitive,
    DisplayRow,
    InstructionManual,
    OperationDiagram,
    ProcedureLink,
    RecordField,
    RelatedDocumentLink,
    StopNotice,
    build_instruction_manual,
)
from ...rendering.part_labels import part_labels
from .validation import anchor_embedment_facts


_PANEL_TITLES = (
    "Build and square the toe-kick platform",
    "Assemble the open carcass",
    "Close the captured back and attach the toe platform",
    "Build and equip the three drawer boxes",
    "Fit, adjust, label, and remove the drawer fronts",
    "Install and commission the empty cabinet",
)

_INSTALL_HOLD_TITLE = "Installation HOLD — obtain clearance before anchoring"

_INSTALL_RECORD_FIELDS = (
    RecordField(
        "Clearance document / approving authority",
        "Document id, approving authority, scope, and approval date",
    ),
    RecordField(
        "Verified stud centers",
        "Actual centers from the wall-left datum; note verification method",
    ),
    RecordField(
        "High-floor and cabinet-top datum",
        "Measured high point and transferred level datum",
    ),
    RecordField(
        "Wall/floor deviations and shim-bearing locations",
        "Deviation map plus each stable shim location and thickness",
    ),
    RecordField(
        "Anchor product, count, and final locations",
        "Installed product/lot and as-built anchor coordinates",
    ),
    RecordField(
        "Level, plumb, diagonals, and drawer reveals",
        "Final measurements after unloaded drawer cycling",
    ),
    RecordField(
        "Corrections / exceptions",
        "Every field correction, substitution, unresolved exception, or none",
    ),
    RecordField(
        "Installer, signature, and date",
        "Printed name, signature, and completion date",
    ),
)

_PANEL_ACTIONS = (
    "fabricate", "assemble", "assemble", "equip", "fit", "install",
)

_PANEL_STEP_IDS = (
    ("assembly.toe_base",),
    ("assembly.carcass",),
    ("fab.toe_attachment", "assembly.back", "assembly.toe_attach"),
    ("fab.runner_fixing", "assembly.drawer_boxes", "assembly.drawer_hardware"),
    (
        "assembly.fronts_pulls", "shop.adjust_drawers",
        "ship.record_adjustment_identity", "ship.remove_drawers",
        "ship.empty_carcass",
    ),
    (
        "install.release_gate", "install.survey", "install.datum",
        "install.toe_base", "install.set_empty_carcass",
        "install.wall_anchor", "install.reinstall_by_identity",
        "install.commission_drawers", "install.countertop",
    ),
)

_PANEL_HARDWARE_KINDS = (
    ("carcass_confirmat_system",),
    ("carcass_confirmat_system", "wood_adhesive"),
    ("carcass_confirmat_system", "toe_base_attachment_system"),
    (
        "drawer_box_joinery_fastener", "drawer_runner_pair",
        "drawer_runner_installation_screw", "drawer_locking_device_pair",
        "drawer_locking_device_screw", "drawer_lateral_stabilizer",
    ),
    (
        "drawer_pull", "drawer_pull_mounting_screw",
        "applied_front_fastener_system",
    ),
    ("wall_anchor_system",),
)

_PANEL_PROCEDURE_KINDS = (
    _PANEL_HARDWARE_KINDS[0],
    _PANEL_HARDWARE_KINDS[1],
    _PANEL_HARDWARE_KINDS[2],
    _PANEL_HARDWARE_KINDS[3],
    (*_PANEL_HARDWARE_KINDS[4], "drawer_runner_pair", "drawer_locking_device_pair"),
    (*_PANEL_HARDWARE_KINDS[5], "drawer_runner_pair", "drawer_locking_device_pair"),
)

_PANEL_TOOLS = (
    (
        DisplayRow(
            "ppe",
            "Safety glasses, hearing protection, and dust extraction/respiratory "
            "protection appropriate to the selected panels",
        ),
        DisplayRow("fit", "Flat assembly surface, square, and diagonal check"),
        DisplayRow("driver", "Driver and the scheduled Confirmat tooling"),
    ),
    (
        DisplayRow("clamp", "Clamps within the selected adhesive open time"),
        DisplayRow("driver", "Driver aligned to the generated joinery rows"),
    ),
    (
        DisplayRow("clamp", "Square-up clamps and equal-diagonal check"),
        DisplayRow("driver", "Driver for the remaining Confirmats and toe screws"),
    ),
    (
        DisplayRow("fit", "Blum templates, depth stops, and paired-fit checks"),
        DisplayRow("driver", "#2 Phillips and the scheduled Confirmat drive"),
    ),
    (
        DisplayRow("clamp", "Front-alignment clamps and model-sized spacers"),
        DisplayRow("fit", "MOVENTO adjustment and identity-labeling supplies"),
    ),
    (
        DisplayRow("fit", "Level, plumb reference, verified stud locator, and shims"),
        DisplayRow("driver", "Drill/driver with the selected GRK drive bit"),
    ),
)


def _procurement_note(quantity: int, unit: str, item_count: int) -> str:
    if unit == "screw":
        return f"{quantity} individual screws"
    if unit == "handed piece" and quantity % 2 == 0:
        return f"{quantity} handed pieces = {quantity // 2} left/right pairs"
    if unit == "complete set":
        return f"{quantity} complete sets; one set per drawer"
    if unit == "pull":
        return f"{quantity} pulls; one pull per drawer"
    if item_count > 1:
        return f"{quantity} {unit}; consolidated from {item_count} released rows"
    return f"{quantity} {unit}"


def _hardware_rows(
    items,
    *,
    quantity_overrides=None,
    group_by_kind: bool = True,
) -> tuple[DisplayRow, ...]:
    quantity_overrides = quantity_overrides or {}
    groups = {}
    for item in items:
        key = (
            (item.kind, item.product_id, item.quantity_unit)
            if group_by_kind else
            (item.product_id, item.quantity_unit)
        )
        row = groups.setdefault(key, {"items": [], "parts": []})
        row["items"].append(item)
        row["parts"].extend(item.related_parts)

    result = []
    for key, grouped in groups.items():
        members = grouped["items"]
        kind = members[0].kind
        if group_by_kind:
            _kind_key, product_id, unit = key
        else:
            product_id, unit = key
        quantity = quantity_overrides.get(
            kind, sum(item.quantity for item in members)
        )
        if unit == "screw":
            icon = "screw"
        elif kind == "wood_adhesive":
            icon = "adhesive"
        else:
            icon = "part"
        if any(item.kind == "wood_adhesive" for item in members):
            procurement = "; ".join(dict.fromkeys(
                item.procurement_note for item in members
                if item.procurement_note
            ))
            label = f"Shop-supply line — {product_id}; {procurement}"
            count = None
        else:
            label = (
                f"{quantity} {unit} — {product_id}; "
                f"{_procurement_note(quantity, unit, len(members))}"
            )
            if kind == "drawer_lateral_stabilizer":
                label += (
                    "; per drawer: left/right pinion housings, two racks, "
                    "linkage rod, two adapters, and locking clips — verify "
                    "against the linked steps 1–9 before accepting delivery"
                )
            count = quantity
        result.append(DisplayRow(
            icon,
            label,
            count=count,
            source_part_ids=tuple(dict.fromkeys(grouped["parts"])),
        ))
    return tuple(result)


def _carcass_confirmat_panel_quantities(project) -> tuple[int, int, int]:
    rows = tuple(
        item for item in project.model.machining
        if item.kind == "confirmat_step_drill"
    )
    toe_targets = {
        project.model.part("toe_front").part_id,
        project.model.part("toe_rear").part_id,
    }
    open_target = project.model.part("left_end").part_id
    open_receivers = {
        project.model.part("bottom").part_id,
        project.model.part("front_stretcher").part_id,
    }
    toe = sum(item.count for item in rows if item.part_id in toe_targets)
    open_carcass = sum(
        item.count for item in rows
        if item.part_id == open_target
        and item.receiving_part_id in open_receivers
    )
    close_back = sum(item.count for item in rows) - toe - open_carcass
    return toe, open_carcass, close_back


def _hardware_row(item) -> DisplayRow:
    """Preserve the single-item helper for tests and simple callers."""

    return _hardware_rows((item,))[0]


def _procedure_links(items) -> tuple[ProcedureLink, ...]:
    grouped: dict[str, dict[str, object]] = {}
    for item in items:
        href = item.procedure_url or item.source_url
        if not href:
            continue
        kind = "procedure" if item.procedure_url else "product_reference"
        label = (item.procedure_label if item.procedure_url else
                 f"Manufacturer product/reference — {item.product_id}")
        group = grouped.setdefault(href, {
            "labels": [], "source_refs": [], "kind": kind,
        })
        if label not in group["labels"]:
            group["labels"].append(label)
        if item.system_id not in group["source_refs"]:
            group["source_refs"].append(item.system_id)
        if kind == "procedure":
            group["kind"] = "procedure"
    return tuple(
        ProcedureLink(
            label="; ".join(group["labels"]),
            href=href,
            source_ref=", ".join(group["source_refs"]),
            kind=group["kind"],
        )
        for href, group in grouped.items()
    )


def _inventory(project) -> tuple[DisplayRow, ...]:
    labels = part_labels(project.detail.assembly.parts)
    placed_by_name = {part.name: part for part in project.detail.assembly.parts}
    modeled_by_id = {part.part_id: part for part in project.model.parts}
    rows = []
    for item in project.artifacts.cut_list:
        modeled = modeled_by_id[item.part_id]
        placed = placed_by_name[modeled.name]
        rows.append(DisplayRow(
            "part",
            f"{item.quantity} × {labels[placed.id].display_name} — pre-band "
            f"{item.length_mm:.2f} × {item.width_mm:.2f} × "
            f"{item.thickness_mm:.2f} mm; {item.material}",
            count=item.quantity,
            source_part_ids=(placed.id,),
        ))
    net_edge_band_mm = sum(
        item.length_mm for item in project.artifacts.edge_banding
    )
    panel_thicknesses = sorted({
        item.thickness_mm for item in project.artifacts.cut_list
    })
    rows.extend((
        DisplayRow(
            "part",
            "Procurement HOLD — edge band: compiled net application "
            f"{net_edge_band_mm:.2f} mm at "
            f"{project.model.profile.edge_band_thickness_mm:g} mm finished "
            "thickness; select matching SKU, roll size, waste, and order "
            "allowance before purchase",
        ),
        DisplayRow(
            "part",
            "Procurement HOLD — sheet nesting: approve product/SKU, finish, "
            "grain direction, kerf, nesting, yield, and sheet count for "
            f"{_fmt_mm_values(panel_thicknesses)} mm panels before purchase",
        ),
        DisplayRow(
            "part",
            "Field/by-others HOLD — countertop and attachment, shims, fillers, "
            "packaging, and finish touch-up are excluded from this inventory",
        ),
    ))
    rows.extend(_hardware_rows(
        project.artifacts.hardware_schedule,
        group_by_kind=False,
    ))
    return tuple(rows)


def _mark(
    kind: str,
    *coords: float,
    role: str = "work",
    label: str = "",
    model_point_mm: tuple[float, ...] = (),
    fact_ref: str = "",
) -> DiagramPrimitive:
    return DiagramPrimitive(
        kind=kind,
        coords=tuple(float(value) for value in coords),
        role=role,
        label=label,
        model_point_mm=tuple(float(value) for value in model_point_mm),
        fact_ref=fact_ref,
    )


def _plot_point(
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
    *,
    pad: float = 8.0,
) -> tuple[float, float]:
    usable = 100.0 - 2.0 * pad
    return (
        pad + usable * x_mm / width_mm,
        100.0 - pad - usable * y_mm / height_mm,
    )


def _reader_values(values) -> str:
    """List register: tape fractions only when every value is clean."""
    from ...details.base import fmt_frac_in

    def clean(mm):
        inches = mm / 25.4
        return abs(inches - round(inches * 16) / 16) <= 1 / 64 + 1e-9

    values = tuple(float(v) for v in values)
    if values and all(clean(v) for v in values):
        return "/".join(fmt_frac_in(round(v / 25.4 * 16) / 16) for v in values)
    return _fmt_mm_values(values) + " mm"


def _machining(project, kind: str):
    return tuple(row for row in project.model.machining if row.kind == kind)


def _reader_len(mm: float) -> str:
    """Homeowner tape register for one length.

    The intended builder works from a tape measure, not a metric shop: a
    value on (or within 1/64 in of) a sixteenth reads as a plain tape
    fraction; anything else reads as ``≈`` the nearest sixteenth with the
    exact millimeter value alongside, so nothing is silently rounded away.
    The fabrication packet remains the mm-exact authority.
    """
    from ...details.base import fmt_frac_in

    inches = mm / 25.4
    sixteenths = round(inches * 16)
    nearest = sixteenths / 16
    if abs(inches - nearest) <= 1 / 64 + 1e-9:
        return fmt_frac_in(nearest)
    return f"≈{fmt_frac_in(nearest)} ({mm:g} mm)"


def _fmt_mm_values(values) -> str:
    return "/".join(f"{float(value):.3f}" for value in values)


def _fmt_mm_point(point) -> str:
    return "(" + ", ".join(f"{float(value):.3f}" for value in point) + ")"


def _drawer_hardware_instructions(project) -> tuple[str, ...]:
    """Embed the essential order from the selected Blum procedures."""

    bank = project.model.drawer_bank
    runner = bank.runner
    lock = bank.locking_device
    rack_lengths = {
        row.length_mm for row in project.model.machining
        if row.kind == "stabilizer_gear_rack_cut"
    }
    rod_lengths = {
        row.length_mm for row in project.model.machining
        if row.kind == "stabilizer_linkage_rod_cut"
    }
    if len(rack_lengths) != 1 or len(rod_lengths) != 1:
        raise ValueError(
            "drawer-hardware instructions require one common rack and linkage "
            "rod cut length across the drawer bank"
        )
    rack_length = next(iter(rack_lengths))
    rod_length = next(iter(rod_lengths))
    return (
        "1. Mount each handed T51.7601 locking device at its matching front "
        f"underside corner: {lock.left_sku} left and {lock.right_sku} right. "
        f"Use template {lock.template_sku}; seat each device flush and drive "
        f"{lock.installation_screw_quantity_per_device} × {lock.installation_screw_sku} "
        f"screws at the template-controlled {lock.installation_angle_deg:g}° angle.",
        "2. Attach the left and right pinion housings to their matching MOVENTO "
        "runners: insert the housing locating pins and press the orange locking "
        "clips until both housings are locked.",
        "3. Slide one gear rack into each pinion housing, install its locating "
        "tabs in the runner-bottom cut-outs, slide the rack backward to lock, "
        f"and cut/verify each rack at the compiled {rack_length:.3f} mm length.",
        "4. Install the left/right runner pair on its identity row at the "
        "generated cabinet-side stations; keep the cabinet-front datum, and "
        f"drive {runner.installation_screws_per_runner} "
        f"{runner.installation_screw_sku} screws per runner.",
        "5. With both runners closed, cut and verify the linkage rod at the "
        f"compiled {rod_length:.3f} mm length.",
        "6. Press one pinion adapter into each end of the cut linkage rod; keep "
        "the adapter pair oriented as shown in the selected stabilizer procedure.",
        "7. Slide the right adapter onto the right pinion, then slide the linkage "
        "assembly left onto the left pinion while both runners remain closed.",
        "8. Install both locking clips on the linkage adapters and verify that "
        "the rod cannot disengage before moving either runner.",
        "9. Extend both runners fully, set the identity-matched drawer onto the "
        "pair, and close it until both locking devices engage; verify the rear "
        "hooks, both front locks, and synchronized travel before fitting fronts.",
        "10. Adjust side-to-side, height, tilt, and depth only after the applied "
        "fronts are mounted in Panel 5; record the accepted setting before the "
        "drawer is removed for shipping.",
        "The linked current Blum manufacturer procedure controls the template "
        "angles, handed component orientation, clip engagement, and insertion/"
        "removal details; stop if the delivered hardware or instructions differ.",
    )


def _toe_platform_diagram(project) -> OperationDiagram:
    front = project.model.part("toe_front")
    sleeper = project.model.part("toe_left")
    width = front.length_mm
    depth = sleeper.length_mm + 2.0 * front.thickness_mm
    # The plan box keeps the platform's true proportions (canvas height
    # from the typed depth/width ratio) and spans the full canvas width so
    # a homeowner can actually read it; the four rail-end insets sit in a
    # row beneath it.
    box_x = 8.0
    box_w = 84.0
    box_h = box_w * depth / width
    rail_h = min(6.0, box_h / 4.0)
    sleeper_w = max(3.5, box_w * front.thickness_mm / width)
    setback = project.model.profile.toe_kick_setback_mm
    primitives = [
        _mark("rect", box_x, 8, box_w, rail_h, role="work",
              label="Rear toe rail",
              fact_ref=project.model.part("toe_rear").part_id),
        _mark("rect", box_x, 8 + box_h - rail_h, box_w, rail_h, role="work",
              label="Front toe rail", fact_ref=front.part_id),
        _mark("rect", box_x, 8 + rail_h, sleeper_w, box_h - 2.0 * rail_h,
              role="work", label="Left toe sleeper"),
        _mark("rect", box_x + box_w - sleeper_w, 8 + rail_h, sleeper_w,
              box_h - 2.0 * rail_h,
              role="work", label="Right toe sleeper"),
        _mark(
            "text", 50, 8 + box_h + 5, role="datum",
            label=f"FRONT / {_reader_len(setback)} setback",
            fact_ref="profile.toe_kick_setback_mm",
        ),
        _mark("text", 50, 4, role="datum", label="PLATFORM PLAN / REAR"),
        _mark("text", 50, 8 + box_h + 12, role="datum",
              label="FOUR RAIL-END FACES / 2 CONFIRMAT CENTERS PER END"),
    ]
    toe_rows = tuple(
        row for row in _machining(project, "confirmat_step_drill")
        if row.part_id in {front.part_id, project.model.part("toe_rear").part_id}
    )
    inset_top = 8 + box_h + 16
    inset_h = max(18.0, 96.0 - 6.0 - inset_top)
    inset_w = 12.0
    for row_index, row in enumerate(toe_rows):
        x0 = 14.0 + row_index * 20.0
        y0 = inset_top
        primitives.append(_mark(
            "rect", x0, y0, inset_w, inset_h, role="prior",
            label=f"{row.part_id.rsplit('.', 1)[-1]} outside face",
            fact_ref=row.part_id,
        ))
        for index in range(row.count):
            model_point = (
                row.location_mm[0],
                row.location_mm[1] + index * row.pitch_mm,
            )
            px = x0 + inset_w / 2.0
            py = y0 + inset_h - inset_h * model_point[1] / front.width_mm
            primitives.append(_mark(
                "circle", px, py, 1.25, role="station",
                label=(
                    "Toe-platform Confirmat center — rail-face local "
                    f"X {model_point[0]:.3f} mm, Y {model_point[1]:.3f} mm"
                ),
                model_point_mm=model_point,
                fact_ref=row.feature_id,
            ))
        primitives.append(_mark(
            "text", x0 + inset_w / 2.0, y0 + inset_h + 4, role="datum",
            label=("FRONT" if row.part_id == front.part_id else "REAR")
                  + (" L" if row_index % 2 == 0 else " R"),
            fact_ref=row.feature_id,
        ))
    return OperationDiagram(
        diagram_id="toe-platform-plan",
        title="Toe platform — plan view",
        caption=(
            f"Assemble the {_reader_len(width)} × {_reader_len(depth)} "
            "platform square; the four rail-end insets plot all eight "
            "generated Confirmat centers—two on each vertical rail end. "
            "Local rail-face height centers are "
            f"{_reader_len(toe_rows[0].location_mm[1])} and "
            f"{_reader_len(toe_rows[0].location_mm[1] + toe_rows[0].pitch_mm)}"
            " up from the rail bottom; end centers sit "
            f"{_reader_len(min(row.location_mm[0] for row in toe_rows))} in "
            "from the left end and the same in from the right end. Verify "
            "equal diagonals before proceeding."
        ),
        primitives=tuple(primitives),
        source_refs=tuple(row.feature_id for row in toe_rows),
    )


def _open_carcass_diagram(project) -> OperationDiagram:
    left = project.model.part("left_end")
    bottom = project.model.part("bottom")
    stretcher = project.model.part("front_stretcher")
    rows = tuple(
        row for row in _machining(project, "confirmat_step_drill")
        if row.part_id == left.part_id
        and row.receiving_part_id in {bottom.part_id, stretcher.part_id}
    )
    bottom_row = next(row for row in rows if row.receiving_part_id == bottom.part_id)
    stretcher_row = next(
        row for row in rows if row.receiving_part_id == stretcher.part_id)
    adhesive = next(
        item for item in project.artifacts.hardware_schedule
        if item.kind == "wood_adhesive"
    )
    primitives = [
        _mark("rect", 8, 8, 60, 84, role="prior",
              label="Left end — outside face / local machining datum",
              fact_ref=left.part_id),
        _mark("text", 38, 13, role="datum", label="LEFT SIDE — LYING FLAT",
              fact_ref=left.part_id),
        _mark("rect", 73, 50, 20, 23, role="work", label="Bottom — attach now",
              fact_ref=bottom.part_id),
        _mark("text", 83, 60, role="datum", label="BOTTOM",
              fact_ref=bottom.part_id),
        _mark("text", 83, 64.5, role="datum", label="ATTACH NOW",
              fact_ref="assembly.carcass"),
        _mark("rect", 73, 82, 20, 7, role="work",
              label="Front stretcher — attach now", fact_ref=stretcher.part_id),
        _mark("text", 80, 94.5, role="datum", label="FRONT STRETCHER",
              fact_ref=stretcher.part_id),
        _mark("arrow", 72, 62, 68, 62, role="motion",
              label="Bring bottom to left end", fact_ref="assembly.carcass"),
        _mark("arrow", 72, 85, 68, 85, role="motion",
              label="Bring front stretcher to left end", fact_ref="assembly.carcass"),
        _mark("rect", 73, 8, 20, 20, role="hold",
              label="Right end — KEEP OFF", fact_ref=project.model.part("right_end").part_id),
        _mark("text", 83, 18, role="hold", label="RIGHT SIDE",
              fact_ref=project.model.part("right_end").part_id),
        _mark("rect", 73, 31, 20, 7, role="hold",
              label="Rear stretcher — KEEP OFF", fact_ref=project.model.part("rear_stretcher").part_id),
        _mark("text", 83, 35.5, role="hold", label="REAR STRETCHER",
              fact_ref=project.model.part("rear_stretcher").part_id),
        _mark("text", 83, 45.5, role="hold", label="LEAVE OFF FOR NOW",
              fact_ref="assembly.carcass"),
        _mark("text", 38, 98, role="datum",
              label="DOTS = PRE-BORED SCREW HOLES",
              fact_ref=bottom_row.feature_id),
    ]
    for row in rows:
        for index in range(row.count):
            model_point = (
                row.location_mm[0],
                row.location_mm[1] + index * row.pitch_mm,
            )
            px, py = _plot_point(
                model_point[0], model_point[1], left.length_mm, left.width_mm,
            )
            primitives.append(_mark(
                "circle", 8 + (px - 8) * 60 / 84, py, 1.25,
                role="station",
                label=(
                    "Open-carcass Confirmat center — local X "
                    f"{model_point[0]:.3f} mm, Y {model_point[1]:.3f} mm"
                ),
                model_point_mm=model_point,
                fact_ref=row.feature_id,
            ))
    return OperationDiagram(
        diagram_id="open-carcass-sequence",
        title="Open-carcass glue-up — keep the back path open",
        caption=(
            "Lay the left side flat, outside face down. Glue and screw the "
            "cabinet bottom onto its long edge and the front stretcher at "
            "the front corner — the solid gray shapes, arrows showing where "
            f"they land. The dots are the {bottom_row.count + stretcher_row.count} "
            "screw holes already bored in the left side "
            f"({bottom_row.count} along the bottom row, {stretcher_row.count} "
            "at the stretcher); drive a Confirmat through each. The dashed "
            "right side and rear stretcher stay off for now so the cabinet "
            "back can slide in later."
        ),
        primitives=tuple(primitives),
        source_refs=(
            left.part_id, bottom.part_id, stretcher.part_id,
            *(row.feature_id for row in rows), adhesive.system_id,
            "assembly.carcass",
        ),
    )


def _close_back_diagram(project) -> OperationDiagram:
    back = project.model.part("captured_back")
    rear = project.model.part("rear_stretcher")
    right = project.model.part("right_end")
    anchor = project.model.part("anchor_strip")
    grooves = _machining(project, "captured_back_groove")
    groove = next(row for row in grooves if row.part_id == project.model.part("bottom").part_id)
    all_confirmats = _machining(project, "confirmat_step_drill")
    toe_targets = {
        project.model.part("toe_front").part_id,
        project.model.part("toe_rear").part_id,
    }
    open_left = project.model.part("left_end").part_id
    open_receivers = {
        project.model.part("bottom").part_id,
        project.model.part("front_stretcher").part_id,
    }
    close_rows = tuple(
        row for row in all_confirmats
        if row.part_id not in toe_targets
        and not (row.part_id == open_left
                 and row.receiving_part_id in open_receivers)
    )
    close_points = tuple(
        (row, (row.location_mm[0],
               row.location_mm[1] + index * row.pitch_mm))
        for row in close_rows for index in range(row.count)
    )
    primitives = [
        _mark("rect", 12, 18, 48, 62, role="prior", label="Open carcass"),
        _mark("rect", 17, 24, 38, 50, role="work", label="1 — Captured back",
              fact_ref=back.part_id),
        _mark("arrow", 36, 6, 36, 23, role="motion",
              label="1 — Slide back into grooves", fact_ref="assembly.back"),
        _mark("rect", 14, 15, 44, 7, role="work", label="2 — Rear stretcher",
              fact_ref=rear.part_id),
        _mark("arrow", 36, 9, 36, 15, role="motion",
              label="2 — Seat rear stretcher", fact_ref="assembly.back"),
        _mark("rect", 60, 18, 8, 62, role="work", label="3 — Right end",
              fact_ref=right.part_id),
        _mark("arrow", 75, 49, 68, 49, role="motion",
              label="3 — Add right end", fact_ref="assembly.back"),
        _mark("rect", 18, 28, 36, 6, role="receiver",
              label="4 — Anchor strip", fact_ref=anchor.part_id),
        _mark("text", 36, 96, role="datum",
              label="SQUARE BY EQUAL DIAGONALS BEFORE CURE",
              fact_ref="assembly.back"),
        _mark("rect", 77, 18, 17, 48, role="prior",
              label="Captured-groove section", fact_ref=groove.feature_id),
        _mark("rect", 82, 18, 4, 38, role="groove",
              label=(f"Groove {groove.width_mm:.3f} mm wide × "
                     f"{groove.depth_mm:.3f} mm deep"),
              fact_ref=groove.feature_id),
        _mark("rect", 82.5, 20, 3, 34, role="work",
              label=f"Captured back {back.thickness_mm:.3f} mm thick",
              fact_ref=back.part_id),
        _mark("text", 85.5, 72, role="datum",
              label=f"{_reader_len(back.thickness_mm)} BACK", fact_ref=back.part_id),
        _mark("text", 85.5, 77, role="datum",
              label=(f"{_reader_len(groove.width_mm)} W × "
                     f"{_reader_len(groove.depth_mm)} D GROOVE"),
              fact_ref=groove.feature_id),
        _mark("text", 40, 82, role="datum",
              label=f"{len(close_points)} CLOSE-OUT CONFIRMATS — COUNT EVERY MARK",
              fact_ref="assembly.back"),
    ]
    for index, (row, point) in enumerate(close_points):
        primitives.append(_mark(
            "circle", 10 + index * (60 / max(1, len(close_points) - 1)), 87,
            1.1, role="station",
            label=(f"Close-out Confirmat center — {project.model.part(row.part_id.rsplit('.', 1)[-1]).name}; "
                   f"local X {point[0]:.3f} mm, Y {point[1]:.3f} mm"),
            model_point_mm=point, fact_ref=row.feature_id,
        ))
    return OperationDiagram(
        diagram_id="captured-back-close",
        title="Close the captured-back grooves in this order",
        caption=(
            "First slide the back into the left-end and bottom grooves. Then "
            "seat the rear-stretcher groove over the top edge and add the right "
            "end to close the fourth groove. Then drive and count the "
            f"{len(close_points)} generated close-out Confirmat positions "
            "shown below; their exact part-local centers are in the compiled key."
        ),
        primitives=tuple(primitives),
        source_refs=(
            back.part_id, rear.part_id, right.part_id, anchor.part_id,
            *(row.feature_id for row in grooves), "assembly.back",
        ),
    )


def _toe_attachment_diagram(project) -> OperationDiagram:
    bottom = project.model.part("bottom")
    width = bottom.length_mm
    depth = bottom.width_mm
    rows = _machining(project, "toe_attachment_station")
    groove = next(
        row for row in _machining(project, "captured_back_groove")
        if row.part_id == bottom.part_id
    )
    # True-proportion plan box: canvas height derives from the typed
    # depth/width ratio (the bottom is a wide rectangle, not a square).
    box_w = 84.0
    box_h = box_w * depth / width

    def plot(x_mm: float, y_mm: float) -> tuple[float, float]:
        return (
            8.0 + box_w * x_mm / width,
            8.0 + box_h * (1.0 - y_mm / depth),
        )

    groove_a = plot(0, groove.location_mm[1])
    groove_b = plot(width, groove.location_mm[1] + groove.width_mm)
    groove_top = min(groove_a[1], groove_b[1])
    groove_height = abs(groove_a[1] - groove_b[1])
    primitives = [
        _mark("rect", 8, 8, box_w, box_h, role="prior",
              label="Cabinet bottom — plan view"),
        _mark(
            "rect", 8, groove_top, box_w, groove_height, role="groove",
            label=(
                "Captured-back groove — Y "
                f"{groove.location_mm[1]:.3f} to "
                f"{groove.location_mm[1] + groove.width_mm:.3f} mm; keep clear"
            ), fact_ref=groove.feature_id,
        ),
        _mark("text", 16, 8 + box_h + 6, role="datum",
              label="FRONT-LEFT DATUM"),
        _mark("text", 50, 5, role="datum", label="REAR / CAPTURED-BACK GROOVE"),
    ]
    for row in rows:
        y = row.location_mm[1]
        p0 = plot(0, y)
        p1 = plot(width, y)
        rail = "front" if row.receiving_part_id.endswith("toe_front") else "rear"
        primitives.append(_mark(
            "line", *p0, *p1, role="receiver",
            label=f"{rail.title()} toe-rail centerline — Y {y:.3f} mm",
            fact_ref=row.feature_id,
        ))
        for index in range(row.count):
            model_point = (
                row.location_mm[0] + index * row.pitch_mm,
                row.location_mm[1],
            )
            px, py = plot(*model_point)
            primitives.append(_mark(
                "circle", px, py, 1.5, role="station",
                label=(
                    "Toe attachment screw center — X "
                    f"{model_point[0]:.3f} mm, Y {model_point[1]:.3f} mm"
                ),
                model_point_mm=model_point,
                fact_ref=row.feature_id,
            ))
    return OperationDiagram(
        diagram_id="toe-attachment-pattern",
        title="Six bottom-to-toe attachment centers — plan view",
        caption=(
            "Mark all six centers from the cabinet-bottom front-left datum, "
            "directly over the two toe-rail centerlines. The blue rear band is "
            "the captured-back groove: no screw path may enter it. These are "
            "layout centers, not claimed pilot holes; pilot diameter/depth, "
            "installation torque, and connection capacity remain unclaimed."
        ),
        primitives=tuple(primitives),
        source_refs=(groove.feature_id, *(row.feature_id for row in rows)),
    )


def _drawer_box_diagram(project) -> OperationDiagram:
    rows = _machining(project, "drawer_box_confirmat_step_drill")
    groove_rows = _machining(project, "drawer_bottom_groove")
    bottom_parts = tuple(
        project.model.part(f"drawer_{identity}_bottom")
        for identity in ("top", "middle", "bottom")
    )
    primitives = [
        _mark("rect", 27, 10, 46, 24, role="prior",
              label="12 mm captured drawer bottom", fact_ref=bottom_parts[0].part_id),
        _mark("rect", 22, 6, 56, 6, role="work", label="Drawer back"),
        _mark("rect", 22, 32, 56, 6, role="work", label="Drawer box front"),
        _mark("rect", 18, 6, 7, 32, role="work", label="Left drawer side"),
        _mark("rect", 75, 6, 7, 32, role="work", label="Right drawer side"),
        _mark("arrow", 50, 24, 50, 13, role="motion",
              label="Seat the 12 mm bottom in all four grooves",
              fact_ref="assembly.drawer_boxes"),
        _mark("text", 50, 43, role="datum",
              label="EQUAL DIAGONALS / 8 CONFIRMATS PER DRAWER",
              fact_ref="assembly.drawer_boxes"),
    ]
    identities = ("top", "middle", "bottom")
    for identity_index, identity in enumerate(identities):
        for hand_index, hand in enumerate(("left", "right")):
            part = project.model.part(f"drawer_{identity}_side_{hand}")
            part_rows = tuple(row for row in rows if row.part_id == part.part_id)
            groove = next(row for row in groove_rows if row.part_id == part.part_id)
            x0 = 3.0 + identity_index * 32.5
            y0 = 49.0 + hand_index * 23.0
            w, h = 29.0, 17.0
            primitives.append(_mark(
                "rect", x0, y0, w, h, role="prior",
                label=f"{identity.title()} {hand} drawer side — outside face",
                fact_ref=part.part_id,
            ))
            groove_y = y0 + h - h * (
                groove.location_mm[1] + groove.width_mm / 2
            ) / part.width_mm
            primitives.append(_mark(
                "line", x0, groove_y, x0 + w, groove_y, role="groove",
                label=(
                    f"Captured-bottom groove — Y {groove.location_mm[1]:.3f} mm, "
                    f"width {groove.width_mm:.3f} mm, depth {groove.depth_mm:.3f} mm"
                ), fact_ref=groove.feature_id,
            ))
            for row in part_rows:
                for index in range(row.count):
                    model_point = (
                        row.location_mm[0],
                        row.location_mm[1] + index * row.pitch_mm,
                    )
                    px = x0 + w * model_point[0] / part.length_mm
                    py = y0 + h - h * model_point[1] / part.width_mm
                    primitives.append(_mark(
                        "circle", px, py, 1.0, role="station",
                        label=(
                            f"{identity.title()} {hand} side Confirmat center — "
                            f"local X {model_point[0]:.3f} mm, "
                            f"Y {model_point[1]:.3f} mm"
                        ),
                        model_point_mm=model_point,
                        fact_ref=row.feature_id,
                    ))
            primitives.append(_mark(
                "text", x0 + w / 2, y0 + h + 4, role="datum",
                label=f"{identity.upper()} {hand.upper()}", fact_ref=part.part_id,
            ))
    x_centers = sorted({
        row.location_mm[0] for row in rows
    })
    y_centers = {
        identity: sorted({
            row.location_mm[1] + index * row.pitch_mm
            for row in rows if f"drawer_{identity}_" in row.part_id
            for index in range(row.count)
        })
        for identity in ("top", "middle", "bottom")
    }
    groove_widths = sorted({row.width_mm for row in groove_rows})
    groove_depths = sorted({row.depth_mm for row in groove_rows})
    bottom_thicknesses = sorted({part.thickness_mm for part in bottom_parts})
    return OperationDiagram(
        diagram_id="drawer-box-joinery",
        title="One drawer box — captured bottom and eight corner screws",
        caption=(
            "The six lower views plot both side panels for all three drawer "
            f"identities. Each has front/rear X centers at {_reader_values(x_centers)}; "
            f"the two Y centers are top {_reader_values(y_centers['top'])}, middle "
            f"{_reader_values(y_centers['middle'])}, and bottom "
            f"{_reader_values(y_centers['bottom'])}. Fully seat each "
            f"{_reader_values(bottom_thicknesses)} bottom in all four "
            f"{_reader_values(groove_widths)} × {_reader_values(groove_depths)} grooves, drive the eight "
            "generated corner Confirmats, and verify equal diagonals."
        ),
        primitives=tuple(primitives),
        source_refs=tuple(row.feature_id for row in (*rows, *groove_rows)),
    )


def _runner_pattern_diagram(project) -> OperationDiagram:
    left = project.model.part("left_end")
    rows = tuple(
        row for row in _machining(project, "runner_fixing_station")
        if row.part_id == left.part_id
    )
    depth = left.width_mm
    height = left.length_mm
    primitives = [
        _mark("rect", 8, 8, 84, 84, role="prior", label="Left cabinet side — inside face"),
        _mark("text", 50, 97, role="datum",
              label="CABINET FRONT / LOWER-LEFT DATUM", fact_ref=left.part_id),
    ]
    for row in rows:
        px, py = _plot_point(*row.location_mm, depth, height)
        primitives.append(_mark(
            "circle", px, py, 1.25, role="station",
            label=(
                "Runner fixing station — X "
                f"{row.location_mm[0]:.3f} mm, Z {row.location_mm[1]:.3f} mm"
            ),
            model_point_mm=row.location_mm,
            fact_ref=row.feature_id,
        ))
    for elevation in sorted({row.location_mm[1] for row in rows}):
        p0 = _plot_point(0, elevation, depth, height)
        p1 = _plot_point(max(row.location_mm[0] for row in rows), elevation,
                         depth, height)
        primitives.append(_mark(
            "line", *p0, *p1, role="receiver",
            label=f"Runner identity row — Z {elevation:.3f} mm",
            fact_ref=next(
                row.feature_id for row in rows
                if row.location_mm[1] == elevation
            ),
        ))
    stations = sorted({row.location_mm[0] for row in rows})
    identity_elevations = {
        identity: next(
            row.location_mm[1] for row in rows
            if f".{identity}." in row.feature_id
        )
        for identity in ("top", "middle", "bottom")
    }
    return OperationDiagram(
        diagram_id="runner-fixing-pattern",
        title="Runner fixing stations — one cabinet side, inside face",
        caption=(
            f"Plot {len(stations)} source-backed stations on each runner row at "
            f"{_reader_values(stations)} from the cabinet front. The compiled "
            f"row elevations are top {_reader_len(identity_elevations['top'])}, middle "
            f"{_reader_len(identity_elevations['middle'])}, and bottom "
            f"{_reader_len(identity_elevations['bottom'])}. Repeat the identical "
            "local-coordinate pattern on the right inside face—do not reverse "
            "the front datum—and keep top/middle/bottom identities. The model "
            "does not claim a pilot depth."
        ),
        primitives=tuple(primitives),
        source_refs=tuple(row.feature_id for row in rows),
    )


def _drawer_hardware_diagram(project) -> OperationDiagram:
    back_rows = tuple(
        row for row in project.model.machining
        if "drawer_bottom_back" in row.part_id
        and row.kind in {"runner_rear_notch", "runner_hook_bore"}
    )
    locking = tuple(
        row for row in _machining(project, "locking_device_bore")
        if "drawer_bottom_front" in row.part_id
    )
    hardware_refs = tuple(
        item.system_id for item in project.artifacts.hardware_schedule
        if item.kind in {
            "drawer_locking_device_pair", "drawer_lateral_stabilizer",
            "drawer_runner_pair",
        }
    )
    back = project.model.part("drawer_bottom_back")
    rack = next(
        row for row in _machining(project, "stabilizer_gear_rack_cut")
        if ".bottom." in row.feature_id
    )
    rod = next(
        row for row in _machining(project, "stabilizer_linkage_rod_cut")
        if ".bottom." in row.feature_id
    )
    primitives = [
        _mark("rect", 7, 5, 86, 30, role="prior",
              label="Drawer-back rear face", fact_ref=back.part_id),
        _mark("text", 50, 3, role="datum", label="REAR-FACE PREPARATION",
              fact_ref=back.part_id),
    ]
    for row in back_rows:
        x = 7 + 86 * row.location_mm[0] / back.length_mm
        y = 35 - 30 * row.location_mm[1] / back.width_mm
        if row.kind == "runner_rear_notch":
            w = 86 * row.width_mm / back.length_mm
            h = 30 * row.depth_mm / back.width_mm
            primitives.append(_mark(
                "rect", x, 35 - h, w, h, role="groove",
                label=(
                    f"Rear runner notch — {row.width_mm:.1f} × "
                    f"{row.depth_mm:.1f} mm at local {row.location_mm}"
                ), model_point_mm=row.location_mm, fact_ref=row.feature_id,
            ))
        else:
            primitives.append(_mark(
                "circle", x, y, 1.4, role="station",
                label=(
                    f"Runner hook bore — Ø{row.diameter_mm:.1f} × "
                    f"{row.depth_mm:.1f} mm at local {row.location_mm}"
                ), model_point_mm=row.location_mm, fact_ref=row.feature_id,
            ))
    locking_product = project.model.drawer_bank.locking_device
    bottom_locking = tuple(locking)
    primitives.extend((
        _mark("rect", 12, 44, 76, 46, role="prior",
              label="Drawer underside relationship", fact_ref=back.part_id),
        _mark("line", 12, 90, 88, 90, role="datum", label="FRONT"),
        _mark("rect", 13, 79, 10, 8, role="hardware",
              label="Left handed locking device — use T65.1600.01 template",
              fact_ref=locking[0].feature_id),
        _mark("rect", 77, 79, 10, 8, role="hardware",
              label="Right handed locking device — use T65.1600.01 template",
              fact_ref=locking[-1].feature_id),
        _mark("text", 50, 96, role="datum",
              label=(
                  f"{locking_product.pilot_bores_per_device} × Ø"
                  f"{locking_product.pilot_bore_diameter_mm:g} × "
                  f"{locking_product.pilot_bore_depth_mm:g} mm AT "
                  f"{locking_product.installation_angle_deg:g}° PER SIDE — TEMPLATE ONLY"
              ),
              fact_ref=locking[0].feature_id),
        _mark("line", 18, 51, 18, 76, role="hardware",
              label=f"Left gear rack — cut {rack.length_mm:.1f} mm",
              fact_ref=rack.feature_id),
        _mark("line", 82, 51, 82, 76, role="hardware",
              label=f"Right gear rack — cut {rack.length_mm:.1f} mm",
              fact_ref=rack.feature_id),
        _mark("line", 18, 55, 82, 55, role="hardware",
              label=f"Linkage rod — cut {rod.length_mm:.1f} mm",
              fact_ref=rod.feature_id),
        _mark("text", 50, 42, role="datum",
              label=(
                  f"RACKS {rack.length_mm:.1f} mm / LINKAGE ROD "
                  f"{rod.length_mm:.1f} mm"
              ), fact_ref=rod.feature_id),
        _mark("arrow", 50, 92, 50, 88, role="motion",
              label="Engage drawer toward the two rear hooks",
              fact_ref="assembly.drawer_hardware"),
    ))
    for index, row in enumerate(bottom_locking):
        left = index < len(bottom_locking) / 2
        local_index = index % locking_product.pilot_bores_per_device
        primitives.append(_mark(
            "circle", (17 if left else 83) + (local_index * 3 - 1.5), 83,
            1.0, role="fastener",
            label=(f"Template-controlled locking-device screw {index + 1} of "
                   f"{len(bottom_locking)} on this drawer"),
            fact_ref=row.feature_id,
        ))
    notches = tuple(row for row in back_rows if row.kind == "runner_rear_notch")
    bores = tuple(row for row in back_rows if row.kind == "runner_hook_bore")
    notch_sizes = sorted({(row.width_mm, row.depth_mm) for row in notches})
    bore_sizes = sorted({(row.diameter_mm, row.depth_mm) for row in bores})
    bore_points = sorted({row.location_mm for row in bores})
    drawer_count = len(project.model.drawer_bank.cells)
    return OperationDiagram(
        diagram_id="drawer-hardware-plan",
        title="MOVENTO hardware relationship — underside plan",
        caption=(
            "Fit the handed locking devices at the two front corners, rear "
            f"hooks through the {_fmt_mm_point(notch_sizes[0])} mm rear notches, "
            f"with Ø{_fmt_mm_point(bore_sizes[0])} mm hook bores at "
            f"{' and '.join(_fmt_mm_point(point) for point in bore_points)} mm. "
            f"There are {len(bottom_locking)} template-controlled screws per "
            f"drawer × {drawer_count} drawers = "
            f"{len(bottom_locking) * drawer_count}; count the four visible marks "
            "for each repeated drawer. Fit the lateral-stabilizer racks, pinions, "
            "and cut linkage rod as one drawer set. Use the linked Blum pages and "
            "steps for preparation, fitting, removal, and adjustment; this "
            "schematic does not replace its templates."
        ),
        primitives=tuple(primitives),
        source_refs=(
            *(row.feature_id for row in (*back_rows, *locking)),
            rack.feature_id, rod.feature_id, *hardware_refs,
        ),
    )


def _stabilizer_sequence_diagram(project) -> OperationDiagram:
    """Redraw the selected Blum stabilizer's nine essential operations."""

    rack = next(
        row for row in _machining(project, "stabilizer_gear_rack_cut")
        if ".bottom." in row.feature_id
    )
    rod = next(
        row for row in _machining(project, "stabilizer_linkage_rod_cut")
        if ".bottom." in row.feature_id
    )
    steps = (
        "1 HOUSINGS", "2 INSERT RACKS", "3 LOCK TO RUNNERS",
        "4 CUT RACKS", "5 INSTALL RUNNERS", "6 CUT ROD",
        "7 PRESS ADAPTERS", "8 ENGAGE BOTH", "9 LOCKING CLIPS",
    )
    primitives = []
    for index, label in enumerate(steps):
        row, column = divmod(index, 3)
        x = 4.0 + column * 32.0
        y = 5.0 + row * 31.0
        primitives.append(_mark(
            "rect", x, y, 28.0, 22.0, role="hardware",
            label=label,
            fact_ref=project.model.drawer_bank.stabilizer.product_id,
        ))
        primitives.append(_mark(
            "text", x + 14.0, y + 12.0, role="datum", label=label,
            fact_ref=project.model.drawer_bank.stabilizer.product_id,
        ))
        if column < 2:
            primitives.append(_mark(
                "arrow", x + 28.5, y + 11.0, x + 31.0, y + 11.0,
                role="motion", label=f"Continue after {label}",
                fact_ref=project.model.drawer_bank.stabilizer.product_id,
            ))
        elif row < 2:
            primitives.append(_mark(
                "arrow", x + 14.0, y + 22.5, x + 14.0, y + 29.0,
                role="motion", label=f"Continue after {label}",
                fact_ref=project.model.drawer_bank.stabilizer.product_id,
            ))
    return OperationDiagram(
        diagram_id="stabilizer-install-sequence",
        title="Lateral stabilizer — nine-operation installation order",
        caption=(
            "Repeat this left/right sequence for each drawer set. The selected "
            f"gear racks are {rack.length_mm:.3f} mm and the linkage rod is "
            f"{rod.length_mm:.3f} mm. Keep both runners closed for rod engagement; "
            "the selected Blum instruction remains controlling for component "
            "orientation, clip engagement, and removal."
        ),
        primitives=tuple(primitives),
        source_refs=(
            rack.feature_id,
            rod.feature_id,
            project.model.drawer_bank.stabilizer.product_id,
        ),
    )


def _applied_front_diagram(project) -> OperationDiagram:
    fronts = (
        ("top", project.model.part("drawer_front_top"),
         project.model.part("drawer_top_front")),
        ("middle", project.model.part("drawer_front_middle"),
         project.model.part("drawer_middle_front")),
        ("bottom", project.model.part("drawer_front_bottom"),
         project.model.part("drawer_bottom_front")),
    )
    bank = project.model.drawer_bank
    primitives = [
        _mark("text", 50, 3, role="datum",
              label=(
                  f"DECORATIVE FACES — {_reader_len(bank.front_edge_reveal_mm)} "
                  f"PERIMETER REVEAL / {_reader_len(bank.front_gap_mm)} GAPS"
              ), fact_ref="drawer_bank.front_reveals"),
        _mark("text", 50, 51, role="datum",
              label="BOX-FRONT INSIDE FACES — FOUR CLEARANCE HOLES EACH",
              fact_ref="fab.fronts_and_pulls"),
    ]
    refs = []
    for identity_index, (identity, applied, box_front) in enumerate(fronts):
        x0 = 3.0 + identity_index * 32.5
        w = 29.0
        face_y0, face_h = 7.0, 36.0
        box_y0, box_h = 57.0, 34.0
        primitives.append(_mark(
            "rect", x0, face_y0, w, face_h, role="work",
            label=f"{identity.title()} applied front",
            fact_ref=applied.part_id,
        ))
        primitives.append(_mark(
            "rect", x0, box_y0, w, box_h, role="prior",
            label=f"{identity.title()} box-front inside face",
            fact_ref=box_front.part_id,
        ))
        attachment_rows = tuple(
            row for row in _machining(project, "applied_front_attachment")
            if row.part_id == box_front.part_id
        )
        pull_rows = tuple(
            row for row in _machining(project, "pull_bore")
            if row.part_id == applied.part_id
        )
        for row in attachment_rows:
            x = x0 + w * row.location_mm[0] / box_front.length_mm
            y = box_y0 + box_h - box_h * row.location_mm[1] / box_front.width_mm
            primitives.append(_mark(
                "circle", x, y, 1.15, role="fastener",
                label=(
                    f"{identity.title()} box-front inside clearance hole — "
                    f"local {row.location_mm}; drive short screw outward into, "
                    "not through, the decorative front"
                ),
                model_point_mm=row.location_mm,
                fact_ref=row.feature_id,
            ))
        for row in pull_rows:
            x = x0 + w * row.location_mm[0] / applied.length_mm
            y = face_y0 + face_h - face_h * row.location_mm[1] / applied.width_mm
            primitives.append(_mark(
                "circle", x, y, 1.15, role="hardware",
                label=(
                    f"{identity.title()} decorative-front pull bore — Ø"
                    f"{row.diameter_mm:.1f} mm at local {row.location_mm}"
                ),
                model_point_mm=row.location_mm,
                fact_ref=row.feature_id,
            ))
        primitives.append(_mark(
            "text", x0 + w / 2, 47, role="datum",
            label=identity.upper(), fact_ref=applied.part_id))
        primitives.append(_mark(
            "text", x0 + w / 2, 96, role="datum",
            label=f"{identity.upper()} / INSIDE",
            fact_ref=box_front.part_id))
        refs.extend(row.feature_id for row in (*attachment_rows, *pull_rows))
    front_widths = sorted({applied.length_mm for _, applied, _ in fronts})
    front_heights = {
        identity: applied.width_mm for identity, applied, _ in fronts
    }
    attachment_rows_by_identity = {
        identity: tuple(
            row for row in _machining(project, "applied_front_attachment")
            if row.part_id == box_front.part_id
        )
        for identity, _applied, box_front in fronts
    }
    pull_rows_by_identity = {
        identity: tuple(
            row for row in _machining(project, "pull_bore")
            if row.part_id == applied.part_id
        )
        for identity, applied, _box_front in fronts
    }
    attachment_x = sorted({
        row.location_mm[0]
        for rows in attachment_rows_by_identity.values() for row in rows
    })
    attachment_y = {
        identity: sorted({row.location_mm[1] for row in rows})
        for identity, rows in attachment_rows_by_identity.items()
    }
    pull_x = sorted({
        row.location_mm[0]
        for rows in pull_rows_by_identity.values() for row in rows
    })
    pull_diameter = next(
        row.diameter_mm for rows in pull_rows_by_identity.values() for row in rows
    )
    attachment_diameter = next(
        row.diameter_mm
        for rows in attachment_rows_by_identity.values() for row in rows
    )
    return OperationDiagram(
        diagram_id="applied-front-pattern",
        title="Front attachment and pull-bore patterns — finished-face view",
        caption=(
            f"The upper row shows only the two Ø{pull_diameter:g} mm, "
            f"{bank.pull_product.hole_spacing_mm:g} mm-center pull bores on the "
            f"{_reader_values(front_widths)}-wide finished decorative faces "
            f"(top {_reader_len(front_heights['top'])}, middle "
            f"{_reader_len(front_heights['middle'])}, bottom "
            f"{_reader_len(front_heights['bottom'])} high). The lower row is a separate "
            f"inside-box-front view for the four Ø{attachment_diameter:g} mm "
            f"through-clearance holes. Their X centers are "
            f"{_fmt_mm_values(attachment_x)} mm; Y pairs are top "
            f"{_fmt_mm_values(attachment_y['top'])}, middle "
            f"{_fmt_mm_values(attachment_y['middle'])}, and bottom "
            f"{_fmt_mm_values(attachment_y['bottom'])} mm. Pull-bore X centers "
            f"are {_fmt_mm_values(pull_x)} mm. "
            "Drive the four short screws outward into—not through—the applied "
            "front; never copy those four holes onto the decorative face."
        ),
        primitives=tuple(primitives),
        source_refs=tuple(refs),
    )


def _wall_anchor_diagram(project) -> OperationDiagram:
    anchors = tuple(
        part for part in project.model.parts
        if part.role.startswith("wall_anchor_")
    )
    studs = tuple(
        part for part in project.model.parts
        if part.role.startswith("wall_stud_")
    )
    anchor_strip = project.model.part("anchor_strip")
    shell = project.model.shell
    x0 = shell.x0_mm
    x1 = x0 + shell.cabinet.width_mm
    z0 = shell.base_z_mm
    z1 = z0 + shell.cabinet.height_mm
    stack, embedment, minimum, _ = anchor_embedment_facts(project.model)
    primitives = [
        _mark("rect", 7, 8, 70, 76, role="prior", label="Empty cabinet carcass",
              fact_ref=shell.cabinet.cabinet_id),
        _mark("rect", 7, 18, 70, 9, role="receiver", label="Anchor strip",
              fact_ref=anchor_strip.part_id),
        _mark("rect", 7, 84, 70, 6, role="prior", label="Toe platform",
              fact_ref=project.model.part("toe_front").part_id),
    ]
    for stud in studs:
        x = 7 + 70 * (stud.at_mm[0] - x0) / (x1 - x0)
        primitives.append(_mark(
            "rect", x - 1.5, 4, 3, 89, role="receiver",
            label=f"Verified existing stud — {stud.name}",
            fact_ref=stud.part_id,
        ))
    for anchor in anchors:
        local_x = anchor.at_mm[0] - x0
        elevation = anchor.at_mm[2] - z0
        x = 7 + 70 * local_x / (x1 - x0)
        y = 84 - 76 * elevation / (z1 - z0)
        primitives.append(_mark(
            "circle", x, y, 1.8, role="station",
            label=(
                f"Wall anchor center — cabinet-local X {local_x:.2f} mm, "
                f"Z {elevation:.2f} mm; through strip into {anchor.name}"
            ),
            model_point_mm=(local_x, elevation),
            fact_ref=anchor.part_id,
        ))
    primitives.extend((
        _mark("arrow", 42, 97, 42, 90, role="motion",
              label="After hold clears, set attached empty cabinet/toe unit",
              fact_ref="install.set_empty_carcass"),
        _mark("text", 42, 2, role="datum", label="FRONT VIEW / VERIFIED STUDS",
              fact_ref=shell.cabinet.wall_id),
        _mark("rect", 82, 11, 13, 72, role="prior",
              label="Wall-anchor side/path section",
              fact_ref=project.model.wall_anchor.product_id),
        _mark("line", 84, 24, 93, 24, role="hardware",
              label=(
                  f"{project.model.wall_anchor.length_mm / 25.4:.3f} in anchor "
                  f"through {stack / 25.4:.3f} in modeled stack"
              ), fact_ref="derived.anchor_embedment"),
        _mark("line", 89, 24, 93, 24, role="receiver",
              label=(
                  f"{embedment / 25.4:.3f} in modeled stud embedment; "
                  f"pack minimum {minimum / 25.4:.2f} in"
              ), fact_ref="derived.anchor_embedment"),
        _mark("text", 88.5, 89, role="datum",
              label=(
                  f"STACK {stack / 25.4:.3f} in / "
                  f"EMBED {embedment / 25.4:.3f} in"
              ), fact_ref="derived.anchor_embedment"),
        _mark("text", 42, 94, role="datum",
              label=(
                  f"TOE SETBACK {project.model.profile.toe_kick_setback_mm:.1f} mm / "
                  "ANCHOR EMPTY CARCASS FIRST"
              ), fact_ref="profile.toe_kick_setback_mm"),
    ))
    return OperationDiagram(
        diagram_id="wall-anchor-path",
        title="Installation planning HOLD — front view of the anchor path",
        caption=(
            "Do not perform these site operations until a project-specific "
            "review qualifies the complete cabinet, toe, and anti-tip load path. "
            "After that hold clears, set and level the empty cabinet with its "
            "attached toe platform and drive only the reviewed wall anchors "
            "through the strip into the two verified stud paths. Reinstall the "
            "drawers by identity for an unloaded fit check only. Loading, use, "
            "and countertop attachment remain on hold until their evidence is "
            "accepted."
        ),
        primitives=tuple(primitives),
        source_refs=(
            anchor_strip.part_id,
            *(part.part_id for part in anchors),
            *(part.part_id for part in studs),
            "install.wall_anchor",
        ),
    )


def _operation_diagrams(project) -> tuple[tuple[OperationDiagram, ...], ...]:
    return (
        (_toe_platform_diagram(project),),
        (_open_carcass_diagram(project),),
        (_close_back_diagram(project), _toe_attachment_diagram(project)),
        (
            _drawer_box_diagram(project),
            _runner_pattern_diagram(project),
            _drawer_hardware_diagram(project),
            _stabilizer_sequence_diagram(project),
        ),
        (_applied_front_diagram(project),),
        (_wall_anchor_diagram(project),),
    )


def build_cabinetry_instruction_manual(
    project,
    *,
    technical_href: str,
    basename: str,
    related_documents: tuple[RelatedDocumentLink, ...] = (),
) -> InstructionManual:
    """Enrich canonical CPG panels with the compiled cabinetry artifacts."""

    if not hasattr(project.model, "drawer_bank"):
        raise ValueError("cabinetry consumer manual currently requires a drawer bank")
    if project.base_report is None or not project.fabrication_ready:
        raise ValueError(
            "cabinetry instruction manual requires a fabrication-released project"
        )
    policy = project.report.installation_use_policy
    if policy is None:
        raise ValueError("drawer-cabinet manual requires an installation/use policy")

    excluded_names = {
        part.name for part in project.model.parts
        if part.role.startswith("wall_stud_")
    }
    excluded = tuple(
        part.id for part in project.detail.assembly.parts
        if part.name in excluded_names
    )
    manual = build_instruction_manual(
        project.detail,
        technical_href,
        title=f"{project.project_doc.name} — Illustrated Assembly Manual",
        basename=basename,
        related_documents=related_documents,
        excluded_part_ids=excluded,
        lede=(
            "This is the shop-assembly and installation-planning companion to the technical "
            "build document. Its six milestones are consecutive steps of the "
            "validated construction process graph; presentation adds no order "
            "edges. Cut-list dimensions are pre-band blanks and the compiled "
            "geometry is finished model size after the declared 0.5 mm band. "
            "Hardware quantities and instructions come from the model-gated pack "
            f"artifacts. {policy.reader_notice(released=project.installation_use_ready)}"
        ),
    )
    if len(manual.panels) != len(_PANEL_TITLES):
        raise ValueError(
            f"DB40 manual expected {len(_PANEL_TITLES)} canonical panels, got "
            f"{len(manual.panels)}"
        )

    step_by_id = {
        step.step_id: step
        for group in (
            project.artifacts.fabrication_steps,
            project.artifacts.assembly_steps,
            project.artifacts.installation_steps,
        )
        for step in group
    }
    stages = project.lowered_doc.sequence.stages
    hardware = project.artifacts.hardware_schedule
    confirmat_panel_quantities = _carcass_confirmat_panel_quantities(project)
    operation_diagrams = _operation_diagrams(project)
    panels = []
    for index, panel in enumerate(manual.panels):
        instructions = tuple(
            step_by_id[step_id].instruction
            for step_id in _PANEL_STEP_IDS[index]
        )
        if index == 0:
            instructions = (
                "Before assembly, complete and sign the purchasing/cutting "
                "release record plus every pre-band cut, edge-band, machining, "
                "and material row in the fabrication packet.",
                *instructions,
            )
        elif index == 3:
            instructions = (*instructions[:2], *_drawer_hardware_instructions(project))
        quantity_overrides = (
            {"carcass_confirmat_system": confirmat_panel_quantities[index]}
            if index < 3 else {}
        )
        panel_hardware = _hardware_rows(
            tuple(item for item in hardware
                  if item.kind in _PANEL_HARDWARE_KINDS[index]),
            quantity_overrides=quantity_overrides,
        )
        panel_hardware_items = tuple(
            item for item in hardware
            if item.kind in _PANEL_HARDWARE_KINDS[index]
        )
        panel_procedure_items = tuple(
            item for item in hardware
            if item.kind in _PANEL_PROCEDURE_KINDS[index]
        )
        honesty = panel.honesty
        if index == 5:
            if project.installation_use_ready:
                honesty = (policy.reader_notice(released=True),)
            else:
                honesty = (
                    "The pack checks geometry, hardware compatibility, anchor path, "
                    "and declared clothing load, but whole-cabinet structural "
                    "capacity remains unqualified. The declared clothing load is an "
                    "input, not permission to test or use the cabinet. "
                    + policy.reader_notice(released=False),
                )
        if index == 5 and not project.installation_use_ready:
            action = "hold"
            title = _INSTALL_HOLD_TITLE
            stop_notice = StopNotice(
                "DO NOT ANCHOR / INSTALL / LOAD",
                "Installation/use release is HOLD. Obtain and identify signed, "
                "project-specific clearance for the cabinet, toe, anchor, "
                "countertop, and service-load path before staging anchors or "
                "performing any site installation or commissioning action.",
            )
        else:
            action = _PANEL_ACTIONS[index]
            title = _PANEL_TITLES[index]
            stop_notice = None
        panels.append(replace(
            panel,
            action=action,
            title=title,
            instructions=instructions,
            rationales=(stages[index].why,),
            honesty=honesty,
            hardware=panel_hardware,
            tools=_PANEL_TOOLS[index],
            procedure_links=_procedure_links(panel_procedure_items),
            diagrams=operation_diagrams[index],
            stop_notice=stop_notice,
            record_title=(
                "Signed installation and fit record" if index == 5 else ""
            ),
            record_fields=_INSTALL_RECORD_FIELDS if index == 5 else (),
        ))

    return replace(manual, panels=tuple(panels), inventory=_inventory(project))
