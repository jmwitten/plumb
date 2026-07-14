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
from dataclasses import dataclass, field

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
    is_hold_gate: bool = False
    record_title: str = ""
    record_fields: tuple[RecordField, ...] = ()

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


def validate_frame_ownership(panels, frames) -> None:
    """Prove complete, unique event ownership across the frame set."""
    panel_events = [event for panel in panels for event in panel.source_events]
    known = set(panel_events)
    claimed = Counter()
    for frame in frames:
        for event in frame.owned_events:
            if event not in known:
                raise FrameContractError(
                    f"frame {frame.frame_id!r} owns unknown event {event!r}")
            claimed[event] += 1
    duplicated = sorted(event for event, count in claimed.items() if count > 1)
    if duplicated:
        raise FrameContractError(
            f"events owned more than once: {duplicated!r}")
    unowned = sorted(set(panel_events) - set(claimed))
    if unowned:
        raise FrameContractError(
            f"panel events left unowned by every frame: {unowned!r}")
