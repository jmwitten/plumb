"""DB40 homeowner-first cutting guide: fab WorkSteps as action frames.

The primary preparation surface for the builder who buys the sheet goods
and cuts every part himself with a tape measure. The 13 released ``fab.*``
WorkSteps project through the ActionFrame layer; every caption number is
interpolated from a typed artifact/model fact and re-audited by the
caption contract, machining diagrams are drawn only from machining-
schedule rows (each mark keeps its ``model_point_mm`` and ``fact_ref``),
and the per-thickness wood list reads in the tape register. The mm-exact
fabrication packet remains the shop-register authority and is linked as
the alternate copy.
"""

from __future__ import annotations

from ...rendering.action_frames import (
    FrameSpec,
    project_action_frames,
    validate_caption,
)
from ...rendering.consumer_pages import (
    ConsumerManual,
    compose_consumer_manual,
)
from ...rendering.instruction_panels import (
    DisplayRow,
    InstructionManual,
    InstructionPanel,
    OperationDiagram,
    RecordField,
    RelatedDocumentLink,
)
from ...rendering.part_labels import part_labels
from .consumer_manual import _nums, consumer_forbidden_tokens
from .instruction_manual import (
    _machining,
    _mark,
    _reader_len,
)

_KIT_GATE = (
    "This guide is the buying and cutting path: every cabinet part, "
    "groove, hole, and edge band, ending at the signed release record. "
    "Wood list sizes are pre-band blanks; a size written with ≈ is "
    "not on a tape mark, so cut to the exact millimeter value printed "
    "beside it. Sheet count and cutting layout are not calculated — plan "
    "your own nesting from the wood list before buying. Buy the hardware "
    "kit from the assembly manual's kit card FIRST: the drilling and "
    "cutting steps below use the makers' templates, the matching stepped "
    "bit, and the stabilizer rack and rod stock from that kit. The linked "
    "fabrication packet is the same content in exact millimeters for a "
    "machine shop — an alternate copy, not required here."
)

_COVER_CAPTION = (
    "Prepare every part before assembly: buy the sheet goods, cut each "
    "blank to the wood list, machine the grooves and holes, band the "
    "edges, and label every part. Assembly continues in the assembly "
    "manual, which begins where this guide ends."
)

_GUIDE_LEDE = (
    "Homeowner-register projection of the released fabrication work "
    "steps; the fabrication packet keeps the mm-exact shop tables."
)


# ---------------------------------------------------------------------------
# Typed lookups


def _assembly_ids(project) -> dict[str, str]:
    """Map every modeled cabinetry part id to its compiled assembly id."""
    placed = {part.name: part.id for part in project.detail.assembly.parts}
    ids = {}
    for part in project.model.parts:
        assembly_id = placed.get(part.name)
        if assembly_id is None:
            raise ValueError(
                f"modeled part {part.part_id!r} is absent from the compiled "
                "assembly used by the cutting guide")
        ids[part.part_id] = assembly_id
    return ids


def _reader_names(project) -> dict[str, str]:
    """Reader display name per modeled part id, from the compiled labels."""
    labels = part_labels(project.detail.assembly.parts)
    return {
        model_id: labels[assembly_id].display_name
        for model_id, assembly_id in _assembly_ids(project).items()
    }


def _cut_items(project) -> dict[str, object]:
    return {item.part_id: item for item in project.artifacts.cut_list}


def _uniform(values, *, what: str):
    """The single common value, or a loud failure when the claim is false."""
    distinct = sorted(set(values))
    if len(distinct) != 1:
        raise ValueError(
            f"cutting guide states one common {what}, but the compiled rows "
            f"disagree: {distinct!r}")
    return distinct[0]


# ---------------------------------------------------------------------------
# Generic machining plan diagram (the toe/attachment pattern, generalized)


_PLAN_BOUNDS_TOLERANCE_MM = 1.0


def _axis_mapping(rows):
    """Read the rows' typed coordinate system into a plotting plane.

    Every machining row declares its +X/+Y axes against the cut-list blank
    (``+X=rearward/cut-list width; +Y=up/cut-list length`` and similar).
    The plan diagram plots the declared "up" axis vertically so the drawn
    blank matches the caption's physical words, and refuses coordinate
    systems it cannot read — a new convention must fail loudly, never plot
    garbage.
    """
    def resolve(system: str):
        clauses = {}
        for clause in system.split(";"):
            clause = clause.strip()
            if clause.startswith("+X="):
                clauses["X"] = clause
            elif clause.startswith("+Y="):
                clauses["Y"] = clause
        if "X" not in clauses or "Y" not in clauses:
            raise ValueError(
                f"machining coordinate system {system!r} does not declare "
                "the +X/+Y axes the plan diagram needs")

        def blank_dim(clause: str) -> str:
            if "cut-list length" in clause:
                return "length"
            if "cut-list width" in clause:
                return "width"
            raise ValueError(
                f"axis clause {clause!r} does not name a cut-list dimension")

        x_dim = blank_dim(clauses["X"])
        y_dim = blank_dim(clauses["Y"])
        if x_dim == y_dim:
            raise ValueError(
                f"coordinate system {system!r} maps both axes to the blank "
                f"{x_dim}; the plan diagram cannot orient it")
        return x_dim, y_dim, "up" in clauses["X"]

    mappings = {resolve(system) for system in
                {row.coordinate_system for row in rows}}
    if len(mappings) != 1:
        raise ValueError(
            "one plan diagram cannot mix machining rows whose coordinate "
            f"systems resolve to different plot mappings: {sorted(mappings)!r}")
    return mappings.pop()


def _machining_plan_diagram(
    project,
    *,
    diagram_id: str,
    title: str,
    caption: str,
    part_id: str,
    kinds: tuple[str, ...],
    outline_label: str,
    notes: tuple[str, ...] = (),
    allowed_numbers: frozenset[str] = frozenset(),
) -> OperationDiagram:
    """Plot one blank's machining rows: grooves, bores, and corner notches.

    Everything drawn comes from the machining schedule; every plotted mark
    keeps the compiled coordinate in ``model_point_mm`` and cites its row's
    ``feature_id``, so the illustration cannot become a second source of
    truth. Axis orientation is read from the rows' typed coordinate
    system, and every mark is bounds-checked against the blank so a
    convention mismatch fails the build instead of drawing off the part.
    ``notes`` are caller-typed dimension rows printed under the box.
    """
    # The diagram title and caption are reader-visible prose exactly like
    # frame captions, so they pass the same honesty contract: every digit
    # must arrive as an interpolated typed value, and machine identifiers
    # are forbidden. (The dense dimension NOTES under the box are layout
    # data by the owner's dense-coordinate rule and stay outside the word
    # audit — their values are interpolated from machining rows above.)
    forbidden = consumer_forbidden_tokens(project)
    for text in (title, caption):
        validate_caption(text, allowed_numbers=allowed_numbers,
                         forbidden_tokens=forbidden)

    item = _cut_items(project)[part_id]
    rows = tuple(row for row in project.model.machining
                 if row.part_id == part_id and row.kind in kinds)
    if not rows:
        raise ValueError(
            f"cutting-guide diagram {diagram_id!r} has no machining rows of "
            f"kinds {kinds!r} on part {part_id!r}")
    x_dim, y_dim, x_is_vertical = _axis_mapping(rows)
    dims = {"length": float(item.length_mm), "width": float(item.width_mm)}
    x_extent, y_extent = dims[x_dim], dims[y_dim]
    if x_is_vertical:
        h_extent, v_extent = y_extent, x_extent

        def to_plane(x_mm: float, y_mm: float) -> tuple[float, float]:
            return (y_mm, x_mm)
    else:
        h_extent, v_extent = x_extent, y_extent

        def to_plane(x_mm: float, y_mm: float) -> tuple[float, float]:
            return (x_mm, y_mm)

    def check_bounds(x_mm: float, y_mm: float, feature_id: str) -> None:
        tol = _PLAN_BOUNDS_TOLERANCE_MM
        if not (-tol <= x_mm <= x_extent + tol
                and -tol <= y_mm <= y_extent + tol):
            raise ValueError(
                f"machining row {feature_id!r} plots ({x_mm:g}, {y_mm:g}) "
                f"mm outside the {x_extent:g} x {y_extent:g} mm blank; its "
                "coordinate system does not match the plan mapping")

    pad, top = 8.0, 12.0
    # Reserve real room for every note row so nothing clips below the
    # canvas: the drawn box shrinks before a note line ever would.
    notes_h = 9.0 + 5.2 * max(len(notes), 1) + 2.0
    box_w = 100.0 - 2.0 * pad
    box_h = box_w * v_extent / h_extent
    max_h = 100.0 - top - notes_h
    if box_h > max_h:
        box_w *= max_h / box_h
        box_h = max_h

    def plot(x_mm: float, y_mm: float) -> tuple[float, float]:
        h_mm, v_mm = to_plane(x_mm, y_mm)
        h_mm = min(max(h_mm, 0.0), h_extent)
        v_mm = min(max(v_mm, 0.0), v_extent)
        return (
            pad + box_w * h_mm / h_extent,
            top + box_h * (1.0 - v_mm / v_extent),
        )

    def plot_rect(x0: float, y0: float, x1: float, y1: float):
        (ha, va), (hb, vb) = plot(x0, y0), plot(x1, y1)
        left, right = min(ha, hb), max(ha, hb)
        upper, lower = min(va, vb), max(va, vb)
        return left, upper, right - left, lower - upper

    primitives = [
        _mark("rect", pad, top, box_w, box_h, role="prior",
              label=outline_label),
        _mark("text", 50.0, top + box_h + 4.5, role="note",
              label="MEASURE FROM THE LOWER-LEFT CORNER"),
    ]
    source_refs = []
    for row in rows:
        source_refs.append(row.feature_id)
        if row.width_mm > 0 and row.length_mm > 0 and row.diameter_mm == 0:
            # Groove band running along the blank's +X machining axis.
            x0, y0 = row.location_mm[0], row.location_mm[1]
            x1, y1 = x0 + row.length_mm, y0 + row.width_mm
            check_bounds(x0, y0, row.feature_id)
            check_bounds(x1, y1, row.feature_id)
            primitives.append(_mark(
                "rect", *plot_rect(x0, y0, x1, y1), role="groove",
                label=(f"Groove {row.width_mm:g} mm wide x "
                       f"{row.depth_mm:g} mm deep"),
                model_point_mm=tuple(row.location_mm),
                fact_ref=row.feature_id,
            ))
        elif row.width_mm > 0 and row.diameter_mm == 0:
            # Corner notch cut into the blank's bottom edge. The drawn rect
            # assumes the notch starts AT that edge; a row that floats
            # above it is a different feature and must not be mis-drawn.
            if row.location_mm[1] != 0.0:
                raise ValueError(
                    f"notch row {row.feature_id!r} does not start at the "
                    "blank's bottom edge; the plan diagram cannot draw it "
                    "as an edge notch")
            x0, y0 = row.location_mm[0], row.location_mm[1]
            x1, y1 = x0 + row.width_mm, y0 + row.depth_mm
            check_bounds(x0, y0, row.feature_id)
            check_bounds(x1, y1, row.feature_id)
            primitives.append(_mark(
                "rect", *plot_rect(x0, y0, x1, y1), role="hold",
                label=(f"Notch {row.width_mm:g} x {row.depth_mm:g} mm"),
                model_point_mm=tuple(row.location_mm),
                fact_ref=row.feature_id,
            ))
        else:
            # Bore stations: location plus pitched repeats along an axis.
            # A row is only drawable if the schedule says it has stations;
            # inventing a mark for count=0 would draw a hole that does not
            # exist.
            if row.count < 1:
                raise ValueError(
                    f"machining row {row.feature_id!r} has count "
                    f"{row.count}; the plan diagram cannot plot it")
            for index in range(row.count):
                offset = index * row.pitch_mm
                point = (
                    row.location_mm[0] + (offset if row.pitch_axis == "X"
                                          else 0.0),
                    row.location_mm[1] + (offset if row.pitch_axis == "Y"
                                          else 0.0),
                )
                check_bounds(point[0], point[1], row.feature_id)
                px, py = plot(*point)
                primitives.append(_mark(
                    "circle", px, py, 1.5, role="station",
                    label=(f"Bore center X {point[0]:.3f} mm, "
                           f"Y {point[1]:.3f} mm"),
                    model_point_mm=point,
                    fact_ref=row.feature_id,
                ))
    for index, note in enumerate(notes):
        primitives.append(_mark(
            "text", 50.0, top + box_h + 9.0 + 5.2 * index, role="note",
            label=note))
    return OperationDiagram(
        diagram_id=diagram_id,
        title=title,
        caption=caption,
        primitives=tuple(primitives),
        source_refs=tuple(dict.fromkeys(source_refs)),
        view_height=min(top + box_h + notes_h, 100.0),
    )


# ---------------------------------------------------------------------------
# Step diagrams (all typed values, reader register where tape-markable)


def _model_part_id(project, role_suffix: str) -> str:
    return project.model.part(role_suffix).part_id


def _back_groove_diagram(project) -> OperationDiagram:
    rows = _machining(project, "captured_back_groove")
    width = _uniform((row.width_mm for row in rows),
                     what="captured-back groove width")
    depth = _uniform((row.depth_mm for row in rows),
                     what="captured-back groove depth")
    names = _reader_names(project)
    start_of = {names[row.part_id].upper(): row.location_mm[1]
                for row in rows}
    if len(start_of) != len(rows):
        raise ValueError(
            "captured-back groove rows share a reader name; the per-part "
            "position list would be ambiguous")
    starts = sorted(start_of.items())
    return _machining_plan_diagram(
        project,
        diagram_id="cut-back-grooves",
        title=f"Captured-back groove — {len(rows)} grooved parts, "
              "positions printed below",
        caption=(
            f"One straight groove, {_reader_len(width)} wide by "
            f"{_reader_len(depth)} deep, on each of the {len(rows)} grooved "
            "parts — same blade width and depth. The box shows the left "
            "cabinet side; every part's own band position, measured up "
            "from its lower-left corner as drawn, is printed below."),
        allowed_numbers=_nums(len(rows), _reader_len(width),
                              _reader_len(depth)),
        part_id=_model_part_id(project, "left_end"),
        kinds=("captured_back_groove",),
        outline_label="Left cabinet side — inside face up",
        notes=(
            f"GROOVE {_reader_len(width)} WIDE x {_reader_len(depth)} DEEP",
            "BAND POSITION, UP AS DRAWN (mm):",
            " - ".join(f"{name} {start:g}" for name, start in starts[:2]),
            " - ".join(f"{name} {start:g}" for name, start in starts[2:]),
        ),
    )


def _toe_centers_diagram(project) -> OperationDiagram:
    part_id = _model_part_id(project, "bottom")
    rows = tuple(row for row in _machining(project, "toe_attachment_station")
                 if row.part_id == part_id)
    centers = sorted({
        round(row.location_mm[0] + index * row.pitch_mm, 3)
        for row in rows for index in range(row.count)})
    row_of = {}
    for row in rows:
        rail = ("FRONT" if row.receiving_part_id.endswith("toe_front")
                else "REAR")
        row_of[rail] = row.location_mm[1]
    if set(row_of) != {"FRONT", "REAR"}:
        raise ValueError(
            "toe-center diagram expects one front and one rear toe-rail "
            f"row; the machining schedule provides {sorted(row_of)!r}")
    total = sum(row.count for row in rows)
    return _machining_plan_diagram(
        project,
        diagram_id="cut-toe-centers",
        title=f"{total} bottom-to-toe screw centers — cabinet bottom, "
              "plan view",
        caption=(
            f"Mark all {total} centers on the cabinet bottom from its "
            "lower-left corner as drawn, using the printed values. The "
            "black band is the captured-back groove: no screw may enter "
            "it. Layout centers only — pilot size, torque, and connection "
            "capacity remain unclaimed."),
        allowed_numbers=_nums(total),
        part_id=part_id,
        kinds=("toe_attachment_station", "captured_back_groove"),
        outline_label="Cabinet bottom — plan view",
        notes=(
            f"{len(centers)} CENTERS PER ROW, FROM LEFT (mm):",
            " / ".join(f"{center:g}" for center in centers),
            f"FRONT ROW {row_of['FRONT']:g} mm UP - "
            f"REAR ROW {row_of['REAR']:g} mm UP",
            "BLACK BAND = BACK GROOVE - NO SCREWS",
        ),
    )


def _drawer_bottom_groove_diagram(project) -> OperationDiagram:
    rows = _machining(project, "drawer_bottom_groove")
    recess = _uniform((row.location_mm[1] for row in rows),
                      what="drawer-bottom groove recess")
    width = _uniform((row.width_mm for row in rows),
                     what="drawer-bottom groove width")
    depth = _uniform((row.depth_mm for row in rows),
                     what="drawer-bottom groove depth")
    return _machining_plan_diagram(
        project,
        diagram_id="cut-drawer-bottom-grooves",
        title=f"Drawer-bottom groove — same setup on all {len(rows)} "
              "drawer-box parts",
        caption=(
            f"Every drawer side, front, and back gets one identical "
            f"groove on its inside face: {_reader_len(width)} wide, "
            f"{_reader_len(depth)} deep, starting {_reader_len(recess)} up "
            f"from the bottom edge. One fence setting cuts all {len(rows)} "
            "parts, so opposing parts agree."),
        allowed_numbers=_nums(len(rows), _reader_len(width),
                              _reader_len(depth), _reader_len(recess)),
        part_id=_model_part_id(project, "drawer_top_side_left"),
        kinds=("drawer_bottom_groove",),
        outline_label="Drawer side — inside face up",
        notes=(
            f"GROOVE {_reader_len(width)} WIDE x {_reader_len(depth)} DEEP",
            f"STARTS {_reader_len(recess)} UP FROM BOTTOM EDGE",
        ),
    )


def _box_joinery_diagram(project) -> OperationDiagram:
    rows = _machining(project, "drawer_box_confirmat_step_drill")
    inset_by_end = sorted({row.location_mm[0] for row in rows})
    if len(inset_by_end) != 2:
        raise ValueError(
            "drawer-side joinery diagram expects one front and one rear "
            f"column of holes; got X positions {inset_by_end!r}")
    first_height = _uniform((row.location_mm[1] for row in rows),
                            what="drawer joinery first-hole height")
    per_column = _uniform((row.count for row in rows),
                          what="drawer joinery holes per column")
    per_drawer = {}
    for row in rows:
        drawer = row.part_id.rsplit("_side_", 1)[0].rsplit(".", 1)[-1]
        per_drawer.setdefault(drawer, set()).add(row.pitch_mm)
    notes = [
        f"HOLE COLUMNS {_reader_len(inset_by_end[0])} FROM EACH END",
        f"FIRST HOLE {_reader_len(first_height)} UP FROM BOTTOM EDGE",
    ]
    for drawer, pitches in sorted(per_drawer.items()):
        pitch = _uniform(pitches, what=f"{drawer} joinery hole pitch")
        label = drawer.replace("drawer_", "").upper()
        notes.append(
            f"{label} DRAWER: SECOND HOLE {_reader_len(first_height + pitch)}"
            " UP")
    return _machining_plan_diagram(
        project,
        diagram_id="cut-drawer-side-joinery",
        title=f"Drawer-side screw holes — {per_column} near each end of "
              "every side",
        caption=(
            f"Step-drill {per_column} holes near each end of every drawer "
            "side, from the outside face, at the printed columns and "
            "heights — both columns share the same heights, and the deeper "
            "drawers' second hole sits higher, per the printed rows. Drill "
            "a clamped scrap coupon first and reject any splitting."),
        allowed_numbers=_nums(per_column),
        part_id=_model_part_id(project, "drawer_top_side_left"),
        kinds=("drawer_box_confirmat_step_drill",),
        outline_label="Drawer side — outside face up",
        notes=tuple(notes),
    )


def _rear_prep_diagram(project) -> OperationDiagram:
    notches = _machining(project, "runner_rear_notch")
    bores = _machining(project, "runner_hook_bore")
    notch_w = _uniform((row.width_mm for row in notches),
                       what="rear notch width")
    notch_h = _uniform((row.depth_mm for row in notches),
                       what="rear notch height")
    bore_d = _uniform((row.diameter_mm for row in bores),
                      what="hook bore diameter")
    bore_depth = _uniform((row.depth_mm for row in bores),
                          what="hook bore depth")
    bore_up = _uniform((row.location_mm[1] for row in bores),
                       what="hook bore height")
    inset = min(row.location_mm[0] for row in bores)

    def _per_back(rows, what):
        counts = {}
        for row in rows:
            counts[row.part_id] = counts.get(row.part_id, 0) + 1
        return _uniform(counts.values(), what=what)

    notches_per_back = _per_back(notches, "notches per drawer back")
    holes_per_back = _per_back(bores, "hook holes per drawer back")
    backs = len({row.part_id for row in notches})
    return _machining_plan_diagram(
        project,
        diagram_id="cut-drawer-back-prep",
        title="Drawer back — corner notches and hook holes (every drawer)",
        caption=(
            f"On each of the {backs} drawer backs only — never the sides — "
            f"cut the {notches_per_back} lower-corner notches and drill "
            f"the {holes_per_back} runner hook holes at the printed "
            "positions, measured from the lower-left corner of the back's "
            f"rear face. All {backs} backs use the same values."),
        allowed_numbers=_nums(backs, notches_per_back, holes_per_back),
        part_id=_model_part_id(project, "drawer_top_back"),
        kinds=("runner_rear_notch", "runner_hook_bore"),
        outline_label="Drawer back — rear face up",
        notes=(
            f"NOTCHES {notch_w:g} x {notch_h:g} mm AT BOTH LOWER CORNERS",
            f"HOLES {bore_d:g} mm DIA x {bore_depth:g} mm DEEP",
            f"{inset:g} mm IN FROM EACH SIDE, {bore_up:g} mm UP",
        ),
    )


def _runner_stations_diagram(project) -> OperationDiagram:
    rows = _machining(project, "runner_fixing_station")
    left = _model_part_id(project, "left_end")
    right = _model_part_id(project, "right_end")
    stations = {
        part: sorted((round(row.location_mm[0], 3), round(row.location_mm[1], 3))
                     for row in rows if row.part_id == part)
        for part in (left, right)
    }
    if stations[left] != stations[right]:
        raise ValueError(
            "cutting guide claims both end panels share one runner station "
            "layout, but the compiled stations differ between ends")
    diameter = _uniform((row.diameter_mm for row in rows),
                        what="runner pilot diameter")
    xs = sorted({round(row.location_mm[0], 3) for row in rows})
    ys = sorted({round(row.location_mm[1], 3) for row in rows})
    return _machining_plan_diagram(
        project,
        diagram_id="cut-runner-stations",
        title=(f"Runner screw stations — {len(stations[left])} marks, "
               "identical on both end panels"),
        caption=(
            f"Mark {len(ys)} rows of {len(xs)} stations on the inside face "
            "of each end panel, measured from the blank's front lower "
            "corner; both ends use exactly the same numbers. Drill a "
            f"{diameter:g} mm pilot at every mark. Row heights and station "
            "distances are printed under the box in millimeters."),
        allowed_numbers=_nums(len(stations[left]), len(ys), len(xs),
                              diameter),
        part_id=left,
        kinds=("runner_fixing_station",),
        outline_label="Cabinet end panel — inside face up",
        notes=(
            "STATIONS FROM FRONT EDGE (mm):",
            " / ".join(f"{x:g}" for x in xs),
            "ROW HEIGHTS FROM BOTTOM EDGE (mm):",
            " / ".join(f"{y:g}" for y in ys),
            f"PILOT {diameter:g} mm DIA - SAME ON BOTH ENDS",
        ),
    )


def _box_front_holes_diagram(project) -> OperationDiagram:
    rows = _machining(project, "applied_front_attachment")
    part_id = _model_part_id(project, "drawer_top_front")
    mine = [row for row in rows if row.part_id == part_id]
    diameter = _uniform((row.diameter_mm for row in rows),
                        what="front attachment hole diameter")
    length = float(_cut_items(project)[part_id].length_mm)
    insets = sorted({round(row.location_mm[0], 3) for row in mine})
    if (len(insets) != 2
            or abs((length - insets[1]) - insets[0]) > 1e-6):
        raise ValueError(
            "box-front attachment columns are not symmetric about the "
            f"blank; got X positions {insets!r} on a {length:g} mm front")
    per_front_counts = {}
    for row in rows:
        per_front_counts[row.part_id] = (
            per_front_counts.get(row.part_id, 0) + 1)
    per_front = _uniform(per_front_counts.values(),
                         what="attachment holes per box front")
    names = _reader_names(project)
    heights = {}
    for row in rows:
        heights.setdefault(
            names[row.part_id].upper(), set()).add(
                round(row.location_mm[1], 3))
    height_notes = [
        f"{name}: " + " / ".join(f"{y:g}" for y in sorted(ys)) + " UP"
        for name, ys in sorted(heights.items())
    ]
    return _machining_plan_diagram(
        project,
        diagram_id="cut-box-front-holes",
        title=(f"Applied-front screw holes — {per_front} through holes per "
               "box front"),
        caption=(
            f"Drill {per_front} clearance holes straight through each "
            "drawer-box front, working from its inside face. The shallowest "
            "box front is shown; every box front's own hole heights are "
            "printed below in millimeters. Never drill these through the "
            "decorative applied front."),
        allowed_numbers=_nums(per_front),
        part_id=part_id,
        kinds=("applied_front_attachment",),
        outline_label="Drawer-box front — inside face up",
        notes=(
            f"HOLES {diameter:g} mm DIA, THROUGH",
            f"COLUMNS {insets[0]:g} mm IN FROM EACH END",
            "HOLE HEIGHTS UP FROM BOTTOM (mm):",
            *height_notes,
        ),
    )


def _pull_bore_diagram(project) -> OperationDiagram:
    rows = _machining(project, "pull_bore")
    part_id = _model_part_id(project, "drawer_front_top")
    mine = [row for row in rows if row.part_id == part_id]
    diameter = _uniform((row.diameter_mm for row in rows),
                        what="pull bore diameter")
    spacing = project.model.drawer_bank.pull_product.hole_spacing_mm
    xs = sorted(row.location_mm[0] for row in mine)
    if len(xs) != 2 or abs((xs[1] - xs[0]) - spacing) > 1e-6:
        raise ValueError(
            "pull bores on the applied front do not match the catalog "
            f"hole spacing {spacing!r}; got X positions {xs!r}")
    per_front_counts = {}
    for row in rows:
        per_front_counts[row.part_id] = (
            per_front_counts.get(row.part_id, 0) + 1)
    per_front = _uniform(per_front_counts.values(),
                         what="pull holes per decorative front")
    names = _reader_names(project)
    heights = {}
    for row in rows:
        heights.setdefault(
            names[row.part_id].upper(), set()).add(
                round(row.location_mm[1], 3))
    height_notes = [
        f"{name}: "
        + " / ".join(f"{y:g}" for y in sorted(ys))
        + " mm UP"
        for name, ys in sorted(heights.items())
    ]
    return _machining_plan_diagram(
        project,
        diagram_id="cut-pull-bores",
        title=f"Pull holes — {per_front} per decorative front, positions "
              "printed",
        caption=(
            f"Drill the {per_front} pull holes, {diameter:g} mm, straight "
            f"through each decorative front at exactly {spacing:g} mm "
            f"center to center, {xs[0]:g} mm in from the left edge as "
            "drawn, with a backer board clamped behind the finished face. "
            "Every front's own hole height is printed below."),
        allowed_numbers=_nums(per_front, diameter, spacing, xs[0]),
        part_id=part_id,
        kinds=("pull_bore",),
        outline_label="Decorative front — show face up",
        notes=(
            f"HOLES {diameter:g} mm DIA, {spacing:g} mm APART",
            f"LEFT HOLE {xs[0]:g} mm FROM LEFT EDGE",
            "HOLE HEIGHT PER FRONT:",
            *height_notes,
        ),
    )


def _end_panel_joinery_diagram(project) -> OperationDiagram:
    rows = _machining(project, "confirmat_step_drill")
    left = _model_part_id(project, "left_end")
    right = _model_part_id(project, "right_end")
    per_end = {
        part: sorted(
            (round(row.location_mm[0], 3), round(row.location_mm[1], 3),
             round(row.pitch_mm, 3), row.count, row.pitch_axis)
            for row in rows if row.part_id == part)
        for part in (left, right)
    }
    if per_end[left] != per_end[right]:
        raise ValueError(
            "cutting guide claims one step-drill pattern for both end "
            "panels, but the compiled rows differ between ends")
    holes = sum(row.count for row in rows if row.part_id == left)
    labels = {
        "bottom": "BOTTOM ROW",
        "front_stretcher": "FRONT PAIR",
        "rear_stretcher": "REAR PAIR",
        "anchor_strip": "ANCHOR PAIR",
    }
    notes = ["ALL VALUES mm; UP + FROM FRONT EDGE:"]
    for row in sorted((row for row in rows if row.part_id == left),
                      key=lambda row: row.location_mm[0]):
        suffix = row.receiving_part_id.rsplit(".", 1)[-1]
        label = labels.get(suffix)
        if label is None:
            raise ValueError(
                f"end-panel step-drill row receives {suffix!r}, which has "
                "no printed label in the cutting guide")
        series = [row.location_mm[0] + index * row.pitch_mm
                  if row.pitch_axis == "X" else row.location_mm[0]
                  for index in range(row.count)]
        depths = [row.location_mm[1] + index * row.pitch_mm
                  if row.pitch_axis == "Y" else row.location_mm[1]
                  for index in range(row.count)]
        ups = " / ".join(f"{value:g}" for value in
                         sorted(dict.fromkeys(series)))
        fronts = " / ".join(f"{value:g}" for value in
                            sorted(dict.fromkeys(depths)))
        notes.append(f"{label}: {ups} UP - {fronts} FROM FRONT")
    return _machining_plan_diagram(
        project,
        diagram_id="cut-end-panel-joinery",
        title=(f"Cabinet-end screw holes — {holes} step-drilled holes, "
               "identical on both ends"),
        caption=(
            f"Step-drill all {holes} holes in each cabinet end panel at "
            "the plotted centers, working from the outside face — along "
            "the bottom edge, at the front and rear stretcher corners, and "
            "at the anchor strip. Both end panels use exactly the same "
            "printed values."),
        allowed_numbers=_nums(holes),
        part_id=left,
        kinds=("confirmat_step_drill",),
        outline_label="Cabinet end panel — outside face up",
        notes=tuple(notes),
    )


def _toe_rail_joinery_diagram(project) -> OperationDiagram:
    rows = tuple(row for row in _machining(project, "confirmat_step_drill")
                 if row.part_id in (_model_part_id(project, "toe_front"),
                                    _model_part_id(project, "toe_rear")))
    per_rail = {}
    for row in rows:
        per_rail.setdefault(row.part_id, []).append(
            (round(row.location_mm[0], 3), round(row.location_mm[1], 3),
             round(row.pitch_mm, 3), row.count, row.pitch_axis))
    patterns = {tuple(sorted(v)) for v in per_rail.values()}
    if len(patterns) != 1:
        raise ValueError(
            "cutting guide claims one step-drill pattern for both toe "
            "rails, but the compiled rows differ between rails")
    front = _model_part_id(project, "toe_front")
    holes = sum(row.count for row in rows if row.part_id == front)
    front_rows = [row for row in rows if row.part_id == front]
    length = float(_cut_items(project)[front].length_mm)
    insets = sorted(row.location_mm[0] for row in front_rows)
    if len(insets) != 2 or abs((length - insets[1]) - insets[0]) > 1e-6:
        raise ValueError(
            "toe-rail step-drill pairs are not symmetric about the rail; "
            f"got X positions {insets!r} on a {length:g} mm rail")
    heights = sorted({
        round(row.location_mm[1] + index * row.pitch_mm, 3)
        for row in front_rows
        for index in range(row.count)
        if row.pitch_axis == "Y"})
    per_end = _uniform((row.count for row in front_rows),
                       what="toe-rail holes per rail end")
    return _machining_plan_diagram(
        project,
        diagram_id="cut-toe-rail-joinery",
        title=(f"Toe-rail screw holes — {holes} step-drilled holes per "
               "rail, both rails alike"),
        caption=(
            f"Step-drill {holes} holes in each toe rail at the plotted "
            f"centers — {per_end} near each rail end, where the short toe "
            "returns land. The front and rear rails use exactly the same "
            "printed values."),
        allowed_numbers=_nums(holes, per_end),
        part_id=front,
        kinds=("confirmat_step_drill",),
        outline_label="Toe rail — outside face up",
        notes=(
            f"PAIRS {insets[0]:g} mm IN FROM EACH RAIL END",
            "HOLE HEIGHTS UP FROM BOTTOM (mm): "
            + " / ".join(f"{value:g}" for value in heights),
        ),
    )


# ---------------------------------------------------------------------------
# Panels: one per released fabrication work step


_STEP_TITLES = {
    "fab.verify_material": "Check the purchased sheets",
    "fab.breakdown": "Cut every part to the wood list",
    "fab.shell_back_grooves": "Cut the four back grooves",
    "fab.toe_attachment": "Mark the toe screw centers",
    "fab.drawer_bottom_grooves": "Cut the drawer-bottom grooves",
    "fab.drawer_box_joinery": "Drill the drawer-side screw holes",
    "fab.drawer_rear_preparation": "Notch and drill the drawer backs",
    "fab.locking_device_preparation": "Bore the front corners with the "
                                      "template",
    "fab.runner_fixing": "Mark and drill the runner stations",
    "fab.stabilizer_preparation": "Cut the stabilizer racks and rod",
    "fab.fronts_and_pulls": "Drill the front and pull holes",
    "fab.joinery_step_drill": "Drill the cabinet screw holes",
    "fab.edge_band": "Band the edges and label everything",
}


def _step_diagrams(project) -> dict[str, tuple[OperationDiagram, ...]]:
    return {
        "fab.shell_back_grooves": (_back_groove_diagram(project),),
        "fab.toe_attachment": (_toe_centers_diagram(project),),
        "fab.drawer_bottom_grooves": (_drawer_bottom_groove_diagram(project),),
        "fab.drawer_box_joinery": (_box_joinery_diagram(project),),
        "fab.drawer_rear_preparation": (_rear_prep_diagram(project),),
        "fab.runner_fixing": (_runner_stations_diagram(project),),
        "fab.fronts_and_pulls#box_fronts": (
            _box_front_holes_diagram(project),),
        "fab.fronts_and_pulls#pulls": (_pull_bore_diagram(project),),
        "fab.joinery_step_drill#ends": (
            _end_panel_joinery_diagram(project),),
        "fab.joinery_step_drill#toe_rails": (
            _toe_rail_joinery_diagram(project),),
    }


def _machined_parts(project, *kinds) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        row.part_id for row in project.model.machining if row.kind in kinds))


def cutting_panels_manual(project) -> InstructionManual:
    """One panel per builder scene over the released ``fab.*`` steps.

    Fabrication steps carry no CPG placement events (nothing is placed
    yet), so ``source_events`` is empty and frame ownership holds
    trivially; the honest content is the step text, the typed diagrams,
    and the affected-part focus that drives each frame's scene. A step
    that decomposes into two distinct builder actions on different parts
    (fronts vs. pulls, end panels vs. toe rails) gets one panel per
    action, so neither scene occludes the parts actually being machined.
    """
    ids = _assembly_ids(project)
    fabricated = tuple(
        ids[item.part_id] for item in project.artifacts.cut_list)
    related_of = {item.system_id: item.related_parts
                  for item in project.artifacts.hardware_schedule}
    diagrams = _step_diagrams(project)
    # step-id -> ((panel-suffix, machined model part ids), ...); the parts
    # come from the machining schedule, never from a hand-kept list.
    splits = {
        "fab.fronts_and_pulls": (
            ("box_fronts",
             _machined_parts(project, "applied_front_attachment")),
            ("pulls", _machined_parts(project, "pull_bore")),
        ),
        "fab.joinery_step_drill": (
            ("ends", tuple(
                part_id for part_id in
                _machined_parts(project, "confirmat_step_drill")
                if part_id.rsplit(".", 1)[-1].endswith("_end"))),
            ("toe_rails", tuple(
                part_id for part_id in
                _machined_parts(project, "confirmat_step_drill")
                if not part_id.rsplit(".", 1)[-1].endswith("_end"))),
        ),
    }
    panels = []
    steps = sorted(project.artifacts.fabrication_steps,
                   key=lambda step: step.phase)
    for step in steps:
        title = _STEP_TITLES.get(step.step_id)
        if title is None:
            raise ValueError(
                f"released fabrication step {step.step_id!r} has no cutting-"
                "guide title; add it so the guide stays complete")
        affected = []
        for part_id in step.affected:
            if part_id in ids:
                affected.append(part_id)
            elif part_id in related_of:
                # Hardware-system work (e.g. stabilizer cuts): the scene
                # highlights the modeled parts the schedule relates it to.
                affected.extend(pid for pid in related_of[part_id]
                                if pid in ids)
        affected = tuple(dict.fromkeys(affected))
        if step.step_id in splits:
            scenes = tuple(
                (f"{step.step_id}#{suffix}", parts)
                for suffix, parts in splits[step.step_id])
            covered = {pid for _key, parts in scenes for pid in parts}
            if covered != set(affected):
                raise ValueError(
                    f"panel split for {step.step_id!r} does not cover the "
                    "step's affected parts exactly; the machining schedule "
                    f"and the release disagree: {sorted(covered)!r} vs "
                    f"{sorted(affected)!r}")
        else:
            scenes = ((step.step_id, affected),)
        for content_key, parts in scenes:
            focus = tuple(dict.fromkeys(ids[part_id] for part_id in parts))
            if not focus:
                raise ValueError(
                    f"fabrication scene {content_key!r} shows no compiled "
                    "parts; the cutting guide cannot illustrate it")
            # Machining scenes show only the parts being worked, at their
            # compiled positions — inside a closed cabinet the drawer
            # parts would be occluded and the highlight would point at
            # hidden faces. The two whole-kit steps keep every part.
            whole_kit = step.step_id in ("fab.verify_material",
                                         "fab.breakdown")
            panels.append(InstructionPanel(
                index=len(panels) + 1,
                action="machine",
                title=title,
                reader_step_indexes=(len(panels),),
                source_events=(),
                visible_part_ids=fabricated if whole_kit else focus,
                arrival_part_ids=(),
                focus_part_ids=focus,
                instructions=(step.instruction,),
                diagrams=diagrams.get(content_key,
                                      diagrams.get(step.step_id, ())),
                content_key=content_key,
            ))
    return InstructionManual(
        title=f"{project.project_doc.name} — Cutting Guide",
        basename="frameless_three_drawer_40_cutting_guide.html",
        technical_href="frameless_three_drawer_40_build_document.html",
        panels=tuple(panels),
        step_edges=(),
        part_schedule=(),
        inventory=(),
        lede=_GUIDE_LEDE,
    )


# ---------------------------------------------------------------------------
# Per-thickness wood list (the kit page), tape register


def _material_heading(material: str) -> str:
    return material.split("—", 1)[0].strip()


def cutting_kit_groups(project):
    """Per-thickness wood list: (heading, rows) in thickness order.

    Lengths and widths read in the homeowner tape register via
    ``_reader_len``; the sheet thickness keeps the purchased product's
    native units in the group heading. Grouping keys round the compiled
    thickness so float noise cannot split a purchased-sheet family.
    """
    names = _reader_names(project)
    ids = _assembly_ids(project)
    banded: dict[str, list[str]] = {}
    for band in project.artifacts.edge_banding:
        banded.setdefault(band.part_id, []).append(band.edge)

    def _band_text(part_id: str) -> str:
        edges = banded.get(part_id)
        if not edges:
            return ""
        if len(edges) == 4:
            return " — band all 4 edges"
        listed = ", ".join(sorted(dict.fromkeys(edges)))
        noun = "edge" if len(edges) == 1 else "edges"
        return f" — band {listed} {noun}"

    groups: dict[tuple[float, str], list] = {}
    for item in project.artifacts.cut_list:
        key = (round(item.thickness_mm, 2), _material_heading(item.material))
        groups.setdefault(key, []).append(item)
    result = []
    for (thickness, heading), items in sorted(groups.items(), reverse=True):
        rows = tuple(
            DisplayRow(
                "part",
                (f"{item.quantity} × {names[item.part_id]} — "
                 f"{_reader_len(item.length_mm)} × "
                 f"{_reader_len(item.width_mm)}"
                 f"{_band_text(item.part_id)}"),
                count=item.quantity,
                source_part_ids=(ids[item.part_id],),
            )
            for item in sorted(items, key=lambda item: item.description)
        )
        total = sum(item.quantity for item in items)
        noun = "part" if total == 1 else "parts"
        result.append((f"{heading} — {total} {noun}", rows))
    return tuple(result)


# ---------------------------------------------------------------------------
# Frames


def _release_record_fields(project) -> tuple[RecordField, ...]:
    fields = [
        RecordField(
            f"Panel product and lot — {heading}",
            "Write the purchased sheet product and lot before cutting "
            "this group.")
        for heading, _rows in cutting_kit_groups(project)
    ]
    fields.extend((
        RecordField(
            "Finish faces and grain",
            "Confirm every part had its show face and grain direction "
            "marked before breakdown; do not infer them from a drawing."),
        RecordField(
            "Part labels",
            "Confirm every cut part carries its wood-list name, including "
            "left/right pieces."),
        RecordField(
            "Approved by / date",
            "Sign only when every wood-list row, groove, hole, and edge "
            "band above is complete."),
    ))
    return tuple(fields)


def cutting_action_frames(
    panels_manual,
    project,
    *,
    _test_caption_override: tuple[str, str] | None = None,
):
    """Project the fabrication panels into homeowner cutting frames.

    Every quantity is read from the typed cut list, machining schedule,
    catalogs, and drawer bank; the caption contract re-audits each one, so
    a count that stops matching the model fails the build.
    """
    panel_of = {panel.content_key: panel.index
                for panel in panels_manual.panels}
    part_count = sum(item.quantity for item in project.artifacts.cut_list)
    group_count = len(cutting_kit_groups(project))

    back_grooves = len(_machining(project, "captured_back_groove"))
    toe_stations = sum(row.count for row in
                       _machining(project, "toe_attachment_station"))
    bottom_grooves = len(_machining(project, "drawer_bottom_groove"))
    def _per_part_total(rows, what: str) -> int:
        # "each of the N parts gets K" is a uniformity claim: prove K is
        # the same on every part, never read it off one representative.
        totals: dict[str, int] = {}
        for row in rows:
            totals[row.part_id] = totals.get(row.part_id, 0) + max(
                row.count, 1)
        return _uniform(totals.values(), what=what)

    box_rows = _machining(project, "drawer_box_confirmat_step_drill")
    box_holes_per_side = _per_part_total(
        box_rows, "step-drilled holes per drawer side")
    drawer_sides = len({row.part_id for row in box_rows})
    notches = _machining(project, "runner_rear_notch")
    hook_bores = _machining(project, "runner_hook_bore")
    backs = len({row.part_id for row in notches})
    bank = project.model.drawer_bank
    lock = bank.locking_device
    runner_rows = _machining(project, "runner_fixing_station")
    left_end = _model_part_id(project, "left_end")
    stations_per_end = sum(row.count for row in runner_rows
                           if row.part_id == left_end)
    runner_pilot = _uniform((row.diameter_mm for row in runner_rows),
                            what="runner pilot diameter")
    rack_len = _uniform(
        (row.length_mm for row in
         _machining(project, "stabilizer_gear_rack_cut")),
        what="gear rack cut length")
    rod_len = _uniform(
        (row.length_mm for row in
         _machining(project, "stabilizer_linkage_rod_cut")),
        what="linkage rod cut length")
    if rack_len <= 0 or rod_len <= 0:
        raise ValueError(
            "stabilizer cut lengths must be positive typed values; got "
            f"rack {rack_len!r}, rod {rod_len!r}")
    drawers = len(bank.cells)
    front_holes = _machining(project, "applied_front_attachment")
    holes_per_box_front = _per_part_total(
        front_holes, "clearance holes per box front")
    box_fronts = len({row.part_id for row in front_holes})
    pull_rows = _machining(project, "pull_bore")
    fronts = len({row.part_id for row in pull_rows})
    pulls_per_front = _per_part_total(
        pull_rows, "pull holes per decorative front")
    carcass_rows = _machining(project, "confirmat_step_drill")
    end_holes = sum(row.count for row in carcass_rows
                    if row.part_id == left_end)
    toe_holes = sum(row.count for row in carcass_rows
                    if row.part_id == _model_part_id(project, "toe_front"))
    joinery = bank.joinery_fastener
    band_rows = project.artifacts.edge_banding
    banded_parts = len({row.part_id for row in band_rows})
    band_thickness = project.model.profile.edge_band_thickness_mm
    front_band_edges = len([
        row for row in band_rows
        if row.part_id.rsplit(".", 1)[-1].startswith("drawer_front_")])

    specs = (
        FrameSpec(
            frame_id="cut.verify_material.frame",
            panel_index=panel_of["fab.verify_material"],
            caption=(
                f"Before any cutting: check every purchased sheet for the "
                f"{group_count} wood-list thickness groups — flat, "
                "undamaged, with the supplier label still attached. Decide "
                "and mark each part's show face and grain direction, then "
                "start the release record on the last page."),
            source_step_ids=("fab.verify_material",),
            owned_event_keys=(),
            tool="Straightedge and a marking pencil",
            allowed_numbers=_nums(group_count),
            # The scene shows the whole kit; the wood list is the key.
            show_picture_key=False,
        ),
        FrameSpec(
            frame_id="cut.breakdown.frame",
            panel_index=panel_of["fab.breakdown"],
            caption=(
                f"Cut all {part_count} parts to the wood list on the kit "
                "page, keeping each marked show face up and its grain "
                "direction as marked. Label every part with its wood-list "
                "name as it comes off the saw — left and right pieces are "
                "not interchangeable."),
            source_step_ids=("fab.breakdown",),
            owned_event_keys=(),
            tool="Saw suitable for sheet goods, tape measure, and labels",
            warning=(
                "A size written with ≈ is not on a tape mark: cut to "
                "the exact millimeter value printed beside it."),
            allowed_numbers=_nums(part_count),
            show_picture_key=False,
        ),
        FrameSpec(
            frame_id="cut.back_grooves.frame",
            panel_index=panel_of["fab.shell_back_grooves"],
            detail_diagram_ids=("cut-back-grooves",),
            caption=(
                f"Cut the {back_grooves} captured-back grooves — both "
                "cabinet ends, the cabinet bottom, and the rear stretcher "
                "— with the same blade width and depth, at each part's "
                "printed position. Dry-fit the thin back panel in its "
                "grooves before anything is glued."),
            source_step_ids=("fab.shell_back_grooves",),
            owned_event_keys=(),
            tool="Table saw or router with a straight fence",
            allowed_numbers=_nums(back_grooves),
        ),
        FrameSpec(
            frame_id="cut.toe_attachment.frame",
            panel_index=panel_of["fab.toe_attachment"],
            detail_diagram_ids=("cut-toe-centers",),
            caption=(
                f"Mark all {toe_stations} toe screw centers on the cabinet "
                "bottom at the diagram's printed values, over the two "
                "toe-rail rows. Marking only — these are driven during "
                "assembly, and no screw path may enter the rear groove "
                "band."),
            source_step_ids=("fab.toe_attachment",),
            owned_event_keys=(),
            tool="Tape measure, square, and awl",
            allowed_numbers=_nums(toe_stations),
        ),
        FrameSpec(
            frame_id="cut.drawer_bottom_grooves.frame",
            panel_index=panel_of["fab.drawer_bottom_grooves"],
            detail_diagram_ids=("cut-drawer-bottom-grooves",),
            caption=(
                f"Cut the {bottom_grooves} drawer-bottom grooves with one "
                "fence setting — every drawer side, front, and back, "
                "inside face — so opposing parts line up when the boxes "
                "close around their bottoms."),
            source_step_ids=("fab.drawer_bottom_grooves",),
            owned_event_keys=(),
            tool="Table saw or router with a straight fence",
            allowed_numbers=_nums(bottom_grooves),
        ),
        FrameSpec(
            frame_id="cut.drawer_box_joinery.frame",
            panel_index=panel_of["fab.drawer_box_joinery"],
            detail_diagram_ids=("cut-drawer-side-joinery",),
            caption=(
                f"Step-drill {box_holes_per_side} screw holes in each of "
                f"the {drawer_sides} drawer sides at the diagram columns, "
                "keeping every lower hole above the bottom groove. Use the "
                "stepped bit that matches the drawer screws and test it on "
                "a clamped offcut first."),
            source_step_ids=("fab.drawer_box_joinery",),
            owned_event_keys=(),
            tool="Drill with the drawer-screw maker's stepped bit",
            warning=(
                "Reject the offcut test if the hole splits, flakes, or "
                "breaks out inside a void — adjust before drilling real "
                "parts."),
            allowed_numbers=_nums(box_holes_per_side, drawer_sides),
        ),
        FrameSpec(
            frame_id="cut.drawer_rear_prep.frame",
            panel_index=panel_of["fab.drawer_rear_preparation"],
            detail_diagram_ids=("cut-drawer-back-prep",),
            caption=(
                f"On each of the {backs} drawer backs, cut both "
                "lower-corner notches and drill both runner hook holes at "
                "the diagram positions. Work from each back's lower-left "
                "rear corner; the sides get no notches."),
            source_step_ids=("fab.drawer_rear_preparation",),
            owned_event_keys=(),
            tool="Jigsaw or handsaw for notches, drill for the hook holes",
            allowed_numbers=_nums(backs),
        ),
        FrameSpec(
            frame_id="cut.locking_prep.frame",
            panel_index=panel_of["fab.locking_device_preparation"],
            caption=(
                "Seat the runner maker's corner template on each drawer-box "
                f"front corner and bore {lock.pilot_bores_per_device} pilot "
                f"holes per side, {lock.pilot_bore_diameter_mm:g} mm wide "
                f"and {lock.pilot_bore_depth_mm:g} mm deep. The template "
                f"sets the required {lock.installation_angle_deg:g}-degree "
                "angle — never lay these out freehand."),
            source_step_ids=("fab.locking_device_preparation",),
            owned_event_keys=(),
            tool="Drill, extension bit, and the runner maker's template",
            allowed_numbers=_nums(
                lock.pilot_bores_per_device, lock.pilot_bore_diameter_mm,
                lock.pilot_bore_depth_mm, lock.installation_angle_deg),
        ),
        FrameSpec(
            frame_id="cut.runner_fixing.frame",
            panel_index=panel_of["fab.runner_fixing"],
            detail_diagram_ids=("cut-runner-stations",),
            caption=(
                f"Mark the {stations_per_end} runner screw stations on the "
                "inside face of each cabinet end from the diagram — "
                "measured from the front edge, never from the runner's set-"
                f"back — and drill a {runner_pilot:g} mm pilot at each, "
                "without breaking through."),
            source_step_ids=("fab.runner_fixing",),
            owned_event_keys=(),
            tool="Tape measure, square, and drill with a depth stop",
            warning=(
                "No pilot depth is claimed by the runner maker: set the "
                "depth stop for this panel and screw so the bit cannot "
                "break through the outside face."),
            allowed_numbers=_nums(stations_per_end, runner_pilot),
        ),
        FrameSpec(
            frame_id="cut.stabilizer_prep.frame",
            panel_index=panel_of["fab.stabilizer_preparation"],
            caption=(
                f"For each of the {drawers} drawers, cut its stabilizer "
                f"gear racks to {rack_len:.1f} mm and its linkage rod to "
                f"{rod_len:.1f} mm. Deburr every cut and keep each "
                "left/right pinion set together with its own drawer's "
                "parts."),
            source_step_ids=("fab.stabilizer_preparation",),
            owned_event_keys=(),
            tool="Fine-tooth saw and a deburring file",
            allowed_numbers=_nums(drawers, f"{rack_len:.1f}",
                                  f"{rod_len:.1f}"),
            # The cut pieces are purchased hardware, not modeled wood; the
            # scene is drawer context only, so a numbered key would only
            # imply the wrong parts get cut.
            show_picture_key=False,
        ),
        FrameSpec(
            frame_id="cut.box_front_holes.frame",
            panel_index=panel_of["fab.fronts_and_pulls#box_fronts"],
            detail_diagram_ids=("cut-box-front-holes",),
            caption=(
                f"Drill {holes_per_box_front} clearance holes through each "
                f"of the {box_fronts} drawer-box fronts from the inside "
                "face, at the diagram positions. These let screws reach "
                "the decorative front later — never drill through the "
                "decorative front itself."),
            source_step_ids=("fab.fronts_and_pulls",),
            owned_event_keys=(),
            tool="Drill with a backer board under the exit face",
            allowed_numbers=_nums(holes_per_box_front, box_fronts),
        ),
        FrameSpec(
            frame_id="cut.pull_bores.frame",
            panel_index=panel_of["fab.fronts_and_pulls#pulls"],
            detail_diagram_ids=("cut-pull-bores",),
            caption=(
                f"Drill {pulls_per_front} pull holes through each of the "
                f"{fronts} decorative fronts at the diagram spacing, "
                "centered, with a backer board protecting the show face. "
                "Check the spacing against the purchased pulls before "
                "drilling."),
            source_step_ids=("fab.fronts_and_pulls",),
            owned_event_keys=(),
            tool="Drill, backer board, and the purchased pull as a gauge",
            allowed_numbers=_nums(pulls_per_front, fronts),
        ),
        FrameSpec(
            frame_id="cut.end_panel_joinery.frame",
            panel_index=panel_of["fab.joinery_step_drill#ends"],
            detail_diagram_ids=("cut-end-panel-joinery",),
            caption=(
                f"Step-drill the {end_holes} cabinet screw holes in each "
                "end panel from its outside face at the diagram's printed "
                "values, with the same stepped bit as the drawer screws. "
                "Both ends share one pattern."),
            source_step_ids=("fab.joinery_step_drill",),
            owned_event_keys=(),
            tool="Drill with the screw maker's stepped bit",
            allowed_numbers=_nums(end_holes),
        ),
        FrameSpec(
            frame_id="cut.toe_rail_joinery.frame",
            panel_index=panel_of["fab.joinery_step_drill#toe_rails"],
            detail_diagram_ids=("cut-toe-rail-joinery",),
            caption=(
                f"Step-drill {toe_holes} screw holes in each toe rail at "
                "the diagram centers — a vertical pair near each end where "
                "the short returns land. Front and rear rails share one "
                "pattern."),
            source_step_ids=("fab.joinery_step_drill",),
            owned_event_keys=(),
            tool="Drill with the screw maker's stepped bit",
            allowed_numbers=_nums(toe_holes),
        ),
        FrameSpec(
            frame_id="cut.edge_band.frame",
            panel_index=panel_of["fab.edge_band"],
            caption=(
                f"Apply the {band_thickness:g} mm edge band to the "
                f"{banded_parts} banded parts — each one's banded edges "
                "are named on its wood-list row — then trim and inspect. "
                "Never band a grooved edge. Confirm every part keeps its "
                "label and finish the release record on the last page."),
            source_step_ids=("fab.edge_band",),
            owned_event_keys=(),
            tool="Iron or edge-band trimmer",
            allowed_numbers=_nums(band_thickness, banded_parts,
                                  front_band_edges),
            record_title="Purchasing and cutting release record",
            record_fields=_release_record_fields(project),
        ),
    )

    if _test_caption_override is not None:
        frame_id, caption = _test_caption_override
        specs = tuple(
            spec if spec.frame_id != frame_id
            else FrameSpec(**{**spec.__dict__, "caption": caption})
            for spec in specs
        )

    return project_action_frames(
        panels_manual, specs, letters=(),
        forbidden_tokens=consumer_forbidden_tokens(project))


def cutting_guide_diagrams(panels_manual) -> dict:
    """Typed operation diagrams keyed by id, for frame detail rendering."""
    return {
        diagram.diagram_id: diagram
        for panel in panels_manual.panels
        for diagram in panel.diagrams
    }


def build_cabinetry_cutting_guide(
    project,
    *,
    basename: str,
    related_documents: tuple[RelatedDocumentLink, ...] = (),
) -> ConsumerManual:
    """Compose the DB40 cutting guide from one compiled project."""
    panels_manual = cutting_panels_manual(project)
    frames = cutting_action_frames(panels_manual, project)
    return compose_consumer_manual(
        frames=frames,
        title=f"{project.project_doc.name} — Cutting Guide",
        basename=basename,
        letters=(),
        kit_gate=_KIT_GATE,
        cover_caption=_COVER_CAPTION,
        related_documents=related_documents,
    )
