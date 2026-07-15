"""DB40 consumer-manual adapter: typed-fact action frames over CPG panels.

Every count, dimension, and condition in a caption is interpolated from a
typed artifact/model fact and re-audited by the caption contract
(:func:`detailgen.rendering.action_frames.validate_caption`): a number that
stops matching its typed source fails the build instead of shipping stale.
Captions restate the released work-step content in the consumer register;
they never add motion, counts, tightening states, or warnings that the
steps and policy do not carry.
"""

from __future__ import annotations

import re

from ...rendering.action_frames import (
    FrameHardware,
    FrameSpec,
    HardwareLetter,
    assign_hardware_letters,
    project_action_frames,
)
from ...rendering.consumer_pages import (
    ConsumerManual,
    compose_consumer_manual,
)
from ...rendering.instruction_panels import RelatedDocumentLink
from ...rendering.part_labels import part_labels
from . import catalogs
from .instruction_manual import (
    _carcass_confirmat_panel_quantities,
    build_cabinetry_instruction_manual,
)


_NUMBER_TOKEN = re.compile(r"\d+(?:[./]\d+)*")

_KIT_GATE = (
    "Begin only with the prepared kit: every part cut, edge-banded, bored, "
    "and labeled per the fabrication packet, with the signed "
    "purchasing/cutting release record complete. Parts — including handed "
    "left/right pieces — are identified by their fabrication labels; stop "
    "and re-label from the packet before assembling any unlabeled part. "
    "This manual repeats no fabrication work."
)


class _MergedHardware:
    """One physical hardware identity across its released schedule roles."""

    def __init__(self, kind, product_id, quantity, quantity_unit, system_id,
                 related_parts, kinds):
        self.kind = kind
        self.product_id = product_id
        self.quantity = quantity
        self.quantity_unit = quantity_unit
        self.system_id = system_id
        self.related_parts = related_parts
        self.kinds = kinds


def _screw_reference(product_id: str):
    """Resolve a dependent installation screw from its typed parent product."""
    for parent in catalogs._DRAWER_RUNNERS.values():
        if parent.installation_screw_product_id == product_id:
            return (
                f"{parent.manufacturer} {parent.installation_screw_sku} "
                "installation screw",
                f"{round(parent.installation_screw_diameter_mm, 1):g} × "
                f"{round(parent.installation_screw_length_mm, 1):g} mm",
            )
    for parent in catalogs._DRAWER_PULLS.values():
        if parent.mounting_screw_product_id == product_id:
            return (
                f"{parent.manufacturer} pull mounting screw",
                f"{parent.thread} × {parent.mounting_screw_length_mm:g} mm",
            )
    return None


def _catalog_label(product_id: str) -> tuple[str, str]:
    """Reader label and selection identity from the typed catalog record."""
    for getter, size in (
        (catalogs.get_assembly_fastener,
         lambda p: f"{p.diameter_mm:g} × {p.length_mm:g} mm, {p.drive}"),
        (catalogs.get_wall_anchor_product,
         lambda p: f"{p.gauge} × {p.length_mm / 25.4:g} in, {p.drive}"),
        (catalogs.get_adhesive, lambda p: f"SKU {p.sku}"),
        (catalogs.get_drawer_runner,
         lambda p: f"{p.nominal_length_mm:g} mm nominal, SKU {p.sku}"),
        (catalogs.get_drawer_locking_device,
         lambda p: f"SKUs {p.left_sku} / {p.right_sku}"),
        (catalogs.get_lateral_stabilizer, lambda p: f"SKU {p.sku}"),
        (catalogs.get_drawer_pull,
         lambda p: f"{p.hole_spacing_mm:g} mm centers, SKU {p.sku}"),
    ):
        try:
            product = getter(product_id)
        except (KeyError, ValueError):
            continue
        return product.product, size(product)
    reference = _screw_reference(product_id)
    if reference is not None:
        return reference
    raise ValueError(
        f"hardware {product_id!r} has no typed catalog record to label the "
        "consumer kit card")


def _labeler(kind, product_id, quantity_unit):
    reader_label, size_text = _catalog_label(product_id)
    icon = "screw" if quantity_unit == "screw" else (
        "adhesive" if kind == "wood_adhesive" else "part")
    return reader_label, size_text, icon


def consumer_hardware_letters(hardware_schedule) -> tuple[HardwareLetter, ...]:
    """Deterministic A/B/C… lettering of physical hardware identities.

    Schedule rows are merged by physical identity ``(product_id,
    quantity_unit)`` — one letter per thing the builder can hold, even when
    the release schedule tracks it under several roles.
    """
    groups: dict[tuple[str, str], list] = {}
    for item in hardware_schedule:
        groups.setdefault((item.product_id, item.quantity_unit),
                          []).append(item)
    merged = []
    for (product_id, unit), members in groups.items():
        members = sorted(members, key=lambda item: item.system_id)
        kinds = tuple(sorted({item.kind for item in members}))
        merged.append(_MergedHardware(
            kind=kinds[0],
            product_id=product_id,
            quantity=sum(item.quantity for item in members),
            quantity_unit=unit,
            system_id=members[0].system_id,
            related_parts=tuple(
                pid for item in members for pid in item.related_parts),
            kinds=kinds,
        ))
    return assign_hardware_letters(merged, labeler=_labeler)


def _letter_index(hardware_schedule,
                  letters: tuple[HardwareLetter, ...]) -> dict[str, str]:
    """Map every released hardware kind to its merged letter."""
    by_identity = {}
    for item in hardware_schedule:
        by_identity.setdefault(
            (item.product_id, item.quantity_unit), set()).add(item.kind)
    index = {}
    for letter in letters:
        for kind in by_identity[(letter.product_id, letter.quantity_unit)]:
            index[kind] = letter.letter
    return index


def consumer_forbidden_tokens(project) -> tuple[str, ...]:
    """Machine vocabulary that must never reach a consumer frame."""
    labels = part_labels(project.detail.assembly.parts)
    tokens = []
    for part in project.detail.assembly.parts:
        tokens.append(part.id)
        tokens.append(labels[part.id].machine_name)
    for item in project.artifacts.hardware_schedule:
        tokens.append(item.product_id)
        tokens.append(item.system_id)
    for stud_id in project.model.anchor_stud_ids:
        tokens.append(stud_id)
    return tuple(dict.fromkeys(tokens))


def _per_drawer_quantity(schedule, kind: str) -> int:
    quantities = sorted({item.quantity for item in schedule
                         if item.kind == kind})
    if len(quantities) != 1:
        raise ValueError(
            f"hardware kind {kind!r} has non-uniform per-drawer quantities "
            f"{quantities!r}; the consumer caption cannot state one count")
    return quantities[0]


def _total_quantity(schedule, kind: str) -> int:
    return sum(item.quantity for item in schedule if item.kind == kind)


def _q(value) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)


def _nums(*values) -> frozenset[str]:
    tokens = set()
    for value in values:
        tokens.update(_NUMBER_TOKEN.findall(_q(value)))
    return frozenset(tokens)


def consumer_action_frames(
    panels_manual,
    project,
    *,
    hardware_schedule=None,
    drawer_count: int | None = None,
    confirmat_per_panel: tuple[int, int, int] | None = None,
    letters: tuple[HardwareLetter, ...] | None = None,
    _test_caption_override: tuple[str, str] | None = None,
):
    """Project the six DB40 panels into consumer action frames.

    Every quantity is read from the typed hardware schedule, the compiled
    drawer bank, and the released work steps; the caption contract re-audits
    each one. Mutating any of those inputs changes the frames with no
    hand-written fix.
    """
    schedule = (project.artifacts.hardware_schedule
                if hardware_schedule is None else hardware_schedule)
    drawers = (len(project.model.drawer_bank.cells)
               if drawer_count is None else drawer_count)
    confirmats = (confirmat_per_panel
                  if confirmat_per_panel is not None
                  else _carcass_confirmat_panel_quantities(project))
    if letters is None:
        letters = consumer_hardware_letters(schedule)
    letter_of = _letter_index(schedule, letters)

    bank = project.model.drawer_bank
    stations_per_runner = len(bank.runner.required_fixing_stations_mm)
    screws_per_runner = bank.runner.installation_screws_per_runner
    screws_per_locking_device = (
        bank.locking_device.installation_screw_quantity_per_device)
    locking_devices_per_drawer = bank.locking_device.quantity_per_drawer
    reveal_mm = bank.front_edge_reveal_mm
    gap_mm = bank.front_gap_mm

    toe_screws = _total_quantity(schedule, "toe_base_attachment_system")
    anchors = _total_quantity(schedule, "wall_anchor_system")
    box_screws = _per_drawer_quantity(schedule, "drawer_box_joinery_fastener")
    runner_screws = _per_drawer_quantity(
        schedule, "drawer_runner_installation_screw")
    locking_screws = _per_drawer_quantity(
        schedule, "drawer_locking_device_screw")
    front_screws = _per_drawer_quantity(
        schedule, "applied_front_fastener_system")
    pull_screws = _per_drawer_quantity(
        schedule, "drawer_pull_mounting_screw")

    confirmat = letter_of["carcass_confirmat_system"]
    toe_screw = letter_of["toe_base_attachment_system"]
    front_screw = letter_of["applied_front_fastener_system"]
    runner = letter_of["drawer_runner_pair"]
    runner_screw = letter_of["drawer_runner_installation_screw"]
    locking = letter_of["drawer_locking_device_pair"]
    locking_screw = letter_of["drawer_locking_device_screw"]
    stabilizer = letter_of["drawer_lateral_stabilizer"]
    pull = letter_of["drawer_pull"]
    pull_screw = letter_of["drawer_pull_mounting_screw"]
    adhesive = letter_of["wood_adhesive"]
    anchor = letter_of["wall_anchor_system"]

    hold_panel = panels_manual.panels[5]
    if hold_panel.stop_notice is None:
        raise ValueError(
            "consumer manual requires the typed installation stop notice")

    specs = (
        FrameSpec(
            frame_id="assembly.toe_base.frame",
            detail_diagram_ids=("toe-platform-plan",),
            panel_index=1,
            caption=(
                f"Fasten the toe-kick rails and both returns square on a "
                f"flat surface with {confirmats[0]} Confirmat screws "
                f"({confirmat}). Check that both diagonals match before "
                "moving on."),
            source_step_ids=("assembly.toe_base",),
            owned_event_keys=("*",),
            hardware=(FrameHardware(confirmat, confirmats[0]),),
            tool="Drill and driver with the scheduled Confirmat step bit",
            allowed_numbers=_nums(confirmats[0]),
        ),
        FrameSpec(
            frame_id="assembly.carcass.open.frame",
            detail_diagram_ids=("open-carcass-sequence",),
            panel_index=2,
            caption=(
                "Glue and fasten the left side, cabinet bottom, and front "
                f"stretcher with {confirmats[1]} Confirmat screws "
                f"({confirmat}) and wood glue ({adhesive}). Work within the "
                "glue's open time and do not over-drive."),
            source_step_ids=("assembly.carcass",),
            owned_event_keys=("*",),
            hardware=(FrameHardware(confirmat, confirmats[1]),
                      FrameHardware(adhesive, 1)),
            tool="Driver, glue spreader, and clamps within open time",
            allowed_numbers=_nums(confirmats[1]),
        ),
        FrameSpec(
            frame_id="assembly.carcass.close.frame",
            detail_diagram_ids=("captured-back-close",),
            panel_index=3,
            caption=(
                "Slide the captured back into its open grooves, add the "
                "right side and rear stretcher, and fasten the wall anchor "
                f"strip — {confirmats[2]} Confirmat screws ({confirmat}) in "
                "all. Pull the cabinet square until the diagonals match."),
            source_step_ids=("assembly.back",),
            owned_event_keys=(
                "place:plywood_panel-1", "place:plywood_panel-3",
                "place:plywood_panel-5", "place:plywood_panel-6"),
            hardware=(FrameHardware(confirmat, confirmats[2]),),
            tool="Driver and square-up clamps",
            allowed_numbers=_nums(confirmats[2]),
        ),
        FrameSpec(
            frame_id="assembly.toe_attach.frame",
            detail_diagram_ids=("toe-attachment-pattern",),
            panel_index=3,
            caption=(
                "Seat the cabinet on the leveled toe platform, align the "
                f"marked screw rows, and drive {toe_screws} cabinet screws "
                f"({toe_screw}) up through the bottom."),
            source_step_ids=("assembly.toe_attach",),
            owned_event_keys=(),
            focus_part_ids=(
                "plywood_panel-2", "plywood_panel-25", "plywood_panel-26"),
            hardware=(FrameHardware(toe_screw, toe_screws),),
            tool="Driver with the star drive bit",
            warning="Keep these screws out of the captured-back groove.",
            allowed_numbers=_nums(toe_screws),
        ),
        FrameSpec(
            frame_id="assembly.drawer_boxes.frame",
            detail_diagram_ids=("drawer-box-joinery",),
            panel_index=4,
            caption=(
                f"Assemble each drawer box square with {box_screws} "
                f"Confirmat screws ({confirmat}) — never glue alone — with "
                "the drawer bottom fully seated in all four grooves and "
                "equal diagonals. Keep the rear notches clear."),
            source_step_ids=("assembly.drawer_boxes",),
            owned_event_keys=("*",),
            hardware=(FrameHardware(confirmat, box_screws),),
            tool="Driver with the scheduled Confirmat step bit",
            repeat=drawers,
            repeat_subject="per drawer",
            allowed_numbers=_nums(box_screws),
        ),
        FrameSpec(
            frame_id="assembly.drawer_runners.frame",
            detail_diagram_ids=("runner-fixing-pattern",),
            panel_index=4,
            caption=(
                f"Clip the stabilizer set's ({stabilizer}) pinion housings "
                "and gear racks in place, then screw one runner pair "
                f"({runner}) to the cabinet at the {stations_per_runner} "
                f"marked stations — {screws_per_runner} screws "
                f"({runner_screw}) per runner — and close the runners."),
            source_step_ids=("assembly.drawer_hardware",),
            owned_event_keys=(),
            focus_part_ids=("plywood_panel-0", "plywood_panel-1"),
            hardware=(FrameHardware(runner, 2),
                      FrameHardware(runner_screw, runner_screws),
                      FrameHardware(stabilizer, 1)),
            tool="#2 Phillips driver and the maker's drilling template",
            repeat=drawers,
            repeat_subject="per drawer",
            allowed_numbers=_nums(stations_per_runner, screws_per_runner, 2),
        ),
        FrameSpec(
            frame_id="assembly.drawer_lockdevices.frame",
            detail_diagram_ids=("stabilizer-install-sequence",),
            panel_index=4,
            caption=(
                f"Fit the set's ({stabilizer}) cut linkage rod, pinion "
                "adapters, and locking clips, then fix both handed locking "
                f"devices ({locking}) flush to the drawer-box bottom — "
                f"{screws_per_locking_device} screws ({locking_screw}) each "
                "— at the template-controlled angle."),
            source_step_ids=("assembly.drawer_hardware",),
            owned_event_keys=(),
            focus_part_ids=(
                "plywood_panel-7", "plywood_panel-8", "plywood_panel-11"),
            hardware=(
                FrameHardware(locking, locking_devices_per_drawer),
                FrameHardware(locking_screw, locking_screws),
            ),
            tool="#2 Phillips driver and the maker's locking-device template",
            repeat=drawers,
            repeat_subject="per drawer",
            allowed_numbers=_nums(screws_per_locking_device, 2),
        ),
        FrameSpec(
            frame_id="assembly.fronts_pulls.frame",
            detail_diagram_ids=("applied-front-pattern",),
            panel_index=5,
            caption=(
                "Clamp each front level on its spacers, drive "
                f"{front_screws} screws ({front_screw}) from inside the box "
                f"into — not through — the front, then mount the pull "
                f"({pull}) with {pull_screws} screws ({pull_screw}), "
                "hand-tight without bottoming."),
            source_step_ids=("assembly.fronts_pulls",),
            owned_event_keys=("*",),
            hardware=(FrameHardware(front_screw, front_screws),
                      FrameHardware(pull, 1),
                      FrameHardware(pull_screw, pull_screws)),
            tool="Front-alignment clamps, spacers, and a driver",
            repeat=drawers,
            repeat_subject="per drawer",
            allowed_numbers=_nums(front_screws, pull_screws),
        ),
        FrameSpec(
            frame_id="shop.adjust.frame",
            panel_index=5,
            caption=(
                f"Install all {drawers} drawers and use the runner "
                "side-to-side, height, tilt, and depth adjustments to set "
                f"even {_q(reveal_mm)} mm edge reveals and {_q(gap_mm)} mm "
                "gaps between fronts, flush faces, and free full-extension "
                "travel."),
            source_step_ids=("shop.adjust_drawers",),
            owned_event_keys=(),
            allowed_numbers=_nums(drawers, reveal_mm, gap_mm),
        ),
        FrameSpec(
            frame_id="ship.prepare.frame",
            panel_index=5,
            caption=(
                "Label every adjusted drawer, front, and hardware bag with "
                "its position, release the locking devices, remove the "
                "drawers, and pack the empty cabinet with its toe platform "
                "as one braced unit."),
            source_step_ids=(
                "ship.record_adjustment_identity", "ship.remove_drawers",
                "ship.empty_carcass"),
            owned_event_keys=(),
            allowed_numbers=frozenset(),
        ),
        FrameSpec(
            frame_id="install.hold.frame",
            panel_index=6,
            caption=(
                "Stop here. Anchoring, installation, countertop work, and "
                "loading stay on hold until the signed project-specific "
                "clearance in the installation record exists."),
            source_step_ids=("install.release_gate",),
            owned_event_keys=(),
            warning=(f"{hold_panel.stop_notice.heading} — "
                     f"{hold_panel.stop_notice.body}"),
            is_hold_gate=True,
            allowed_numbers=frozenset(),
        ),
        FrameSpec(
            frame_id="install.survey.frame",
            panel_index=6,
            caption=(
                "Field-verify both stud centers, wall flatness, "
                "obstructions, and the highest floor point; transfer a "
                "level cabinet-top line from that high point and record the "
                "wall and floor deviations."),
            source_step_ids=("install.survey", "install.datum"),
            owned_event_keys=(),
            focus_part_ids=("plywood_panel-6",),
            tool="Level, plumb reference, and a verified stud locator",
            allowed_numbers=frozenset(),
        ),
        FrameSpec(
            frame_id="install.set.frame",
            panel_index=6,
            caption=(
                "Set the empty cabinet with its attached toe platform at "
                "the marked setback, shim only over stable bearing points, "
                "and bring it level and plumb with equal diagonals; then "
                f"recheck all {toe_screws} toe screws."),
            source_step_ids=("install.toe_base", "install.set_empty_carcass"),
            owned_event_keys=(),
            focus_part_ids=(
                "plywood_panel-25", "plywood_panel-26", "plywood_panel-2"),
            tool="Level and shims at the toe members",
            allowed_numbers=_nums(toe_screws),
        ),
        FrameSpec(
            frame_id="install.anchor.frame",
            detail_diagram_ids=("wall-anchor-path",),
            panel_index=6,
            caption=(
                f"Drive {anchors} cabinet anchor screws ({anchor}) through "
                "the wall anchor strip into the field-verified studs; seat "
                "each washer head snug without crushing the strip."),
            source_step_ids=("install.wall_anchor",),
            owned_event_keys=(
                "place:structural_screw-0", "place:structural_screw-1"),
            hardware=(FrameHardware(anchor, anchors),),
            tool="Drill and driver with the star drive bit",
            warning=("Never substitute drywall anchors or rely on gypsum "
                     "board; the screws must reach the verified studs."),
            allowed_numbers=_nums(anchors),
        ),
        FrameSpec(
            frame_id="install.commission.frame",
            panel_index=6,
            caption=(
                "Reinstall each drawer at its labeled position, engage both "
                "locking devices, and cycle it through full extension — "
                "unloaded checks only. Verify quiet soft-close, even "
                "reveals, and every fastener's seating; enter results in "
                "the signed record."),
            source_step_ids=(
                "install.reinstall_by_identity", "install.commission_drawers",
                "install.countertop"),
            owned_event_keys=(),
            warning=(
                "Countertop attachment stays on hold until the "
                "project-specific load-path review and countertop selection "
                "are complete. Do not load or use the cabinet."),
            repeat=drawers,
            repeat_subject="per drawer",
            record_title=hold_panel.record_title,
            record_fields=hold_panel.record_fields,
            allowed_numbers=frozenset(),
        ),
    )

    if _test_caption_override is not None:
        step_id, caption = _test_caption_override
        specs = tuple(
            spec if spec.source_step_ids[0] != step_id
            else FrameSpec(**{**spec.__dict__, "caption": caption})
            for spec in specs
        )

    return project_action_frames(
        panels_manual, specs, letters=letters,
        forbidden_tokens=consumer_forbidden_tokens(project))


def build_cabinetry_consumer_manual(
    project,
    *,
    basename: str,
    technical_href: str = "frameless_three_drawer_40_build_document.html",
    assembly_manual_href: str = (
        "frameless_three_drawer_40_assembly_manual.html"),
    related_documents: tuple[RelatedDocumentLink, ...] = (),
) -> ConsumerManual:
    """Compose the DB40 consumer manual from one compiled project."""
    panels_manual = build_cabinetry_instruction_manual(
        project,
        technical_href=technical_href,
        basename=assembly_manual_href,
    )
    letters = consumer_hardware_letters(project.artifacts.hardware_schedule)
    frames = consumer_action_frames(panels_manual, project, letters=letters)
    return compose_consumer_manual(
        frames=frames,
        title=f"{project.project_doc.name} — Assembly Manual",
        basename=basename,
        letters=letters,
        kit_gate=_KIT_GATE,
        cover_caption=(
            "Shop assembly and installation companion. Technical evidence, "
            "fabrication data, and the review trace live in the linked "
            "documents."),
        related_documents=related_documents,
    )


def consumer_part_rows(project, panels_manual=None):
    """Kit-card part rows: count × reader name plus the typed cut size.

    With ``panels_manual`` supplied, rows are ordered by first use in the
    build sequence (the panel schedule), so kit-card numbering follows the
    instruction order — part 1 is the first part the builder touches.

    Cut sizes come from the released cut list (pre-band blank sizes — the
    numbers a builder would actually cut to); material, grain, and finish
    data stay in the fabrication packet. Fastener-shaped components are
    already on the lettered hardware card, so the parts card lists panels
    and assemblies only.
    """
    from ...rendering.instruction_panels import DisplayRow

    labels = part_labels(project.detail.assembly.parts)
    roles = project.detail.roles()
    cut_by_description = {
        item.description: item for item in project.artifacts.cut_list}

    def _inches(mm: float) -> str:
        # Tape-measure register: a construction fraction only when the
        # compiled size actually lands on a sixteenth; otherwise honest
        # decimal inches (the fabrication packet keeps mm precision).
        from ...details.base import fmt_frac_in

        inches = mm / 25.4
        sixteenths = round(inches * 16)
        if abs(inches - sixteenths / 16) < 1e-6:
            return fmt_frac_in(inches)
        return f'{inches:.2f}"'

    def _cut_text(part) -> str:
        # Panel sizes read in inches (owner preference); metric-native
        # hardware keeps mm on the lettered hardware card.
        item = cut_by_description.get(part.name)
        if item is None:
            return ""
        dims = " × ".join(
            _inches(value)
            for value in (item.length_mm, item.width_mm, item.thickness_mm))
        return f" — {dims}"

    parts = list(project.detail.assembly.parts)
    if panels_manual is not None:
        from ...rendering.instruction_panels import panel_part_schedule

        schedule = panel_part_schedule(panels_manual)
        parts.sort(key=lambda part: (
            schedule.get(part.id, len(panels_manual.panels) + 1),
            project.detail.assembly.parts.index(part)))
    grouped: dict[str, list[str]] = {}
    for part in parts:
        if roles.get(part.name) == "existing":
            continue
        if hasattr(part.component, "head_height"):
            continue
        key = f"{labels[part.id].reader_name}{_cut_text(part)}"
        grouped.setdefault(key, []).append(part.id)
    return tuple(
        DisplayRow("part",
                   (f"{len(ids)} × {label}" if len(ids) > 1
                    else f"1 × {label}"),
                   count=len(ids),
                   source_part_ids=tuple(ids))
        for label, ids in grouped.items()
    )


def consumer_part_numbers(project, panels_manual=None) -> dict[str, int]:
    """One global part number per kit-card row, keyed by part id.

    The number order is the kit card's row order — build order when
    ``panels_manual`` is supplied — so scene callouts, picture keys, and
    the parts list all cite the same number for the same part.
    """
    numbers: dict[str, int] = {}
    rows = consumer_part_rows(project, panels_manual)
    for index, row in enumerate(rows, start=1):
        for part_id in row.source_part_ids:
            numbers[part_id] = index
    return numbers


def consumer_diagrams(panels_manual) -> dict:
    """Typed operation diagrams keyed by id, for frame detail rendering."""
    return {
        diagram.diagram_id: diagram
        for panel in panels_manual.panels
        for diagram in panel.diagrams
    }


def consumer_panels_manual(project):
    """The panel manual whose imagery backs the consumer frames."""
    return build_cabinetry_instruction_manual(
        project,
        technical_href="frameless_three_drawer_40_build_document.html",
        basename="frameless_three_drawer_40_assembly_manual.html",
    )
