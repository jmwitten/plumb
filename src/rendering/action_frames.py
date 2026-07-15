"""Pure ActionFrame projection for consumer instruction manuals.

This module is deliberately free of HTML, VTK, and file I/O. It projects the
validated :class:`~detailgen.rendering.instruction_panels.InstructionManual`
into single-builder-action frames — the consumer instruction unit — while
proving three honesty contracts at construction time:

- deterministic hardware lettering from typed hardware identities;
- caption honesty: word budget, no machine identifiers, and every numeric
  token backed by a typed fact the caller supplied;
- complete, unique source-event ownership: no construction event may be
  dropped or duplicated when panels are decomposed into frames.

Missing facts stay absent; nothing here invents captions, counts, motion,
or warnings.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .instruction_panels import RecordField


class FrameContractError(ValueError):
    """The semantic model cannot be projected into an honest action frame."""


_ILLUSTRATION_INTENTS = ("assembly_scene", "operation_diagram")

_NUMBER_TOKEN = re.compile(r"\d+(?:[./]\d+)*")


@dataclass(frozen=True)
class HardwareLetter:
    """One lettered hardware identity on the prepared-kit inventory card."""

    letter: str
    kind: str
    product_id: str
    reader_label: str
    size_text: str
    quantity_total: int
    quantity_unit: str
    icon: str
    source_system_ids: tuple[str, ...]

    def __post_init__(self):
        if not self.letter or not self.letter.isalpha():
            raise FrameContractError(
                f"hardware letter must be alphabetic; got {self.letter!r}")
        if self.quantity_total < 1:
            raise FrameContractError(
                f"hardware letter {self.letter} quantity_total must be "
                f"positive; got {self.quantity_total}")


@dataclass(frozen=True)
class FrameHardware:
    """Exact hardware usage of one frame, referenced by letter."""

    letter: str
    quantity: int

    def __post_init__(self):
        if self.quantity < 1:
            raise FrameContractError(
                f"frame hardware quantity must be positive; got "
                f"{self.quantity}")


@dataclass(frozen=True)
class FrameIllustration:
    """Typed illustration intent backed by an actual rendered/derived view."""

    intent: str
    panel_index: int
    diagram_id: str = ""
    inset: str = ""

    def __post_init__(self):
        if self.intent not in _ILLUSTRATION_INTENTS:
            raise FrameContractError(
                f"illustration intent must be one of "
                f"{_ILLUSTRATION_INTENTS}; got {self.intent!r}")
        if self.intent == "operation_diagram" and not self.diagram_id:
            raise FrameContractError(
                "operation_diagram illustration requires a diagram_id")


@dataclass(frozen=True)
class ActionFrame:
    """One builder action with typed provenance, hardware, and conditions."""

    frame_id: str
    caption: str
    source_step_ids: tuple[str, ...]
    owned_events: tuple[tuple[str, str, str], ...]
    focus_part_ids: tuple[str, ...]
    context_part_ids: tuple[str, ...] = ()
    hardware: tuple[FrameHardware, ...] = ()
    tool: str = ""
    repeat: int = 1
    repeat_subject: str = ""
    hold: str = ""
    warning: str = ""
    illustration: FrameIllustration | None = None
    detail_diagram_ids: tuple[str, ...] = ()
    is_hold_gate: bool = False
    record_title: str = ""
    record_fields: tuple[RecordField, ...] = ()
    show_picture_key: bool = True

    def __post_init__(self):
        if not self.frame_id:
            raise FrameContractError("frame_id must be non-empty")
        if self.repeat < 1:
            raise FrameContractError(
                f"frame {self.frame_id!r} repeat must be >= 1; got "
                f"{self.repeat}")
        if self.repeat > 1 and not self.repeat_subject:
            raise FrameContractError(
                f"frame {self.frame_id!r} repeats {self.repeat}x but has no "
                "typed repeat_subject naming the modeled repetition")


def _letters_sequence():
    """A, B, ..., Z, AA, AB, ... — deterministic and unbounded."""
    import string
    for char in string.ascii_uppercase:
        yield char
    for first in string.ascii_uppercase:
        for second in string.ascii_uppercase:
            yield first + second


def assign_hardware_letters(items, *, labeler) -> tuple[HardwareLetter, ...]:
    """Assign letters from typed hardware identities, input-order independent.

    ``items`` are HardwareItem-shaped objects (``system_id``, ``kind``,
    ``product_id``, ``quantity``, ``quantity_unit``, ``related_parts``).
    Identity is ``(kind, product_id, quantity_unit)``; identical rows (e.g.
    per-drawer triplets) merge with quantities summed. ``labeler(kind,
    product_id, quantity_unit)`` must return ``(reader_label, size_text,
    icon)`` — reader vocabulary is the caller's typed knowledge, never
    invented here.
    """
    groups: dict[tuple[str, str, str], list] = {}
    for item in items:
        key = (item.kind, item.product_id, item.quantity_unit)
        groups.setdefault(key, []).append(item)

    letters = []
    sequence = _letters_sequence()
    for key in sorted(groups):
        kind, product_id, quantity_unit = key
        members = sorted(groups[key], key=lambda item: item.system_id)
        reader_label, size_text, icon = labeler(kind, product_id,
                                                quantity_unit)
        letters.append(HardwareLetter(
            letter=next(sequence),
            kind=kind,
            product_id=product_id,
            reader_label=reader_label,
            size_text=size_text,
            quantity_total=sum(item.quantity for item in members),
            quantity_unit=quantity_unit,
            icon=icon,
            source_system_ids=tuple(item.system_id for item in members),
        ))
    return tuple(letters)


def validate_caption(caption: str, *, allowed_numbers: frozenset[str],
                     forbidden_tokens: tuple[str, ...]) -> None:
    """Enforce the consumer caption contract.

    A caption may carry at most 50 words, no machine/catalog identifier
    tokens, and no numeric token that is not present in
    ``allowed_numbers`` — the exact set of typed-fact values the caller
    interpolated. This is what makes authored caption templates safe: any
    hand-written count that stops matching the model fails loudly.
    """
    if not caption or not caption.strip():
        raise FrameContractError("caption must be non-empty")
    words = caption.split()
    if len(words) > 50:
        raise FrameContractError(
            f"caption exceeds 50 words ({len(words)}): {caption[:60]!r}...")
    for token in forbidden_tokens:
        if token and token in caption:
            raise FrameContractError(
                f"caption contains forbidden identifier {token!r}: "
                f"{caption[:80]!r}")
    for number in _NUMBER_TOKEN.findall(caption):
        if number not in allowed_numbers:
            raise FrameContractError(
                f"caption number {number!r} is not backed by a typed fact "
                f"(allowed: {sorted(allowed_numbers)}): {caption[:80]!r}")


@dataclass(frozen=True)
class FrameSpec:
    """Authored decomposition of one panel into one builder action.

    Everything quantitative must arrive as typed values: ``allowed_numbers``
    is the exact set of numeric tokens the caller interpolated into the
    caption, and ``hardware`` letters must resolve against the assigned
    letter card. ``owned_event_keys`` are ``"kind:subject"`` strings matched
    against the panel's source events; the single wildcard ``"*"`` claims
    the whole panel and is only legal for a panel's sole frame.
    """

    frame_id: str
    panel_index: int
    caption: str
    source_step_ids: tuple[str, ...]
    owned_event_keys: tuple[str, ...]
    focus_part_ids: tuple[str, ...] = ()
    context_part_ids: tuple[str, ...] | None = None
    hardware: tuple[FrameHardware, ...] = ()
    tool: str = ""
    repeat: int = 1
    repeat_subject: str = ""
    hold: str = ""
    warning: str = ""
    allowed_numbers: frozenset[str] = frozenset()
    diagram_id: str = ""
    inset: str = ""
    detail_diagram_ids: tuple[str, ...] = ()
    is_hold_gate: bool = False
    record_title: str = ""
    record_fields: tuple[RecordField, ...] = ()
    show_picture_key: bool = True


def _events_for_keys(panel, spec) -> tuple[tuple[str, str, str], ...]:
    if spec.owned_event_keys == ("*",):
        return panel.source_events
    matched = []
    for key in spec.owned_event_keys:
        kind, _, subject = key.partition(":")
        hits = [event for event in panel.source_events
                if event[0] == kind and event[1] == subject]
        if not hits:
            raise FrameContractError(
                f"frame {spec.frame_id!r} claims event key {key!r} that "
                f"matches no event of panel {spec.panel_index}")
        matched.extend(hit for hit in hits if hit not in matched)
    return tuple(matched)


def project_action_frames(
    manual,
    specs: tuple[FrameSpec, ...],
    *,
    letters: tuple[HardwareLetter, ...],
    forbidden_tokens: tuple[str, ...],
) -> tuple[ActionFrame, ...]:
    """Project instruction panels into validated consumer action frames.

    Every panel must be decomposed by at least one spec; every panel event
    must be owned exactly once across the panel's frames; captions pass the
    honesty contract; hardware letters must exist. Frames are returned in
    panel order, preserving spec order within a panel.
    """
    panels_by_index = {panel.index: panel for panel in manual.panels}
    known_letters = {letter.letter for letter in letters}

    specs_by_panel: dict[int, list[FrameSpec]] = {}
    for spec in specs:
        if spec.panel_index not in panels_by_index:
            raise FrameContractError(
                f"frame {spec.frame_id!r} references panel "
                f"{spec.panel_index}, which does not exist")
        specs_by_panel.setdefault(spec.panel_index, []).append(spec)

    uncovered = sorted(set(panels_by_index) - set(specs_by_panel))
    if uncovered:
        raise FrameContractError(
            f"panel {uncovered[0]} has no action-frame decomposition "
            f"(uncovered panels: {uncovered!r})")

    frames = []
    for panel_index in sorted(specs_by_panel):
        panel = panels_by_index[panel_index]
        panel_specs = specs_by_panel[panel_index]
        wildcards = [s for s in panel_specs if s.owned_event_keys == ("*",)]
        claiming_others = [s for s in panel_specs
                           if s not in wildcards and s.owned_event_keys]
        if wildcards and (len(wildcards) > 1 or claiming_others):
            raise FrameContractError(
                f"panel {panel_index}: wildcard event ownership is only "
                "legal when no sibling frame claims events; wildcard "
                f"{wildcards[0].frame_id!r} conflicts")
        panel_diagram_ids = {
            diagram.diagram_id for diagram in getattr(panel, "diagrams", ())}
        for spec in panel_specs:
            for row in spec.hardware:
                if row.letter not in known_letters:
                    raise FrameContractError(
                        f"frame {spec.frame_id!r} references hardware "
                        f"letter {row.letter!r} that was never assigned")
            for diagram_id in spec.detail_diagram_ids:
                if diagram_id not in panel_diagram_ids:
                    raise FrameContractError(
                        f"frame {spec.frame_id!r} references diagram "
                        f"{diagram_id!r} that its source panel "
                        f"{spec.panel_index} does not carry")
            validate_caption(
                spec.caption,
                allowed_numbers=spec.allowed_numbers,
                forbidden_tokens=forbidden_tokens,
            )
            for text in (spec.hold, spec.warning, spec.tool,
                         spec.repeat_subject):
                if text:
                    validate_caption(
                        text,
                        allowed_numbers=spec.allowed_numbers,
                        forbidden_tokens=forbidden_tokens,
                    )
            focus = spec.focus_part_ids or panel.focus_part_ids
            if spec.context_part_ids is not None:
                context = spec.context_part_ids
            else:
                context = tuple(pid for pid in panel.visible_part_ids
                                if pid not in focus)
            frames.append(ActionFrame(
                frame_id=spec.frame_id,
                caption=spec.caption,
                source_step_ids=spec.source_step_ids,
                owned_events=_events_for_keys(panel, spec),
                focus_part_ids=focus,
                context_part_ids=context,
                hardware=spec.hardware,
                tool=spec.tool,
                repeat=spec.repeat,
                repeat_subject=spec.repeat_subject,
                hold=spec.hold,
                warning=spec.warning,
                illustration=FrameIllustration(
                    intent=("operation_diagram" if spec.diagram_id
                            else "assembly_scene"),
                    panel_index=panel_index,
                    diagram_id=spec.diagram_id,
                    inset=spec.inset,
                ),
                detail_diagram_ids=spec.detail_diagram_ids,
                is_hold_gate=spec.is_hold_gate,
                record_title=spec.record_title,
                record_fields=spec.record_fields,
                show_picture_key=spec.show_picture_key,
            ))

    frames = tuple(frames)
    validate_frame_ownership(manual.panels, frames)
    return frames


def validate_frame_ownership(panels, frames) -> None:
    """Prove complete, unique event ownership across the frame set.

    Multiset semantics: an event identity that occurs in N panels must be
    claimed exactly N times, so a shared identity cannot let one claim
    satisfy two panels while a copy silently vanishes.
    """
    expected = Counter(
        event for panel in panels for event in panel.source_events)
    claimed = Counter()
    for frame in frames:
        for event in frame.owned_events:
            if event not in expected:
                raise FrameContractError(
                    f"frame {frame.frame_id!r} owns unknown event {event!r}")
            claimed[event] += 1
    duplicated = sorted(event for event, count in claimed.items()
                        if count > expected[event])
    if duplicated:
        raise FrameContractError(
            f"events owned more than once: {duplicated!r}")
    unowned = sorted(event for event, count in expected.items()
                     if claimed[event] < count)
    if unowned:
        raise FrameContractError(
            f"panel events left unowned by every frame: {unowned!r}")
