"""Pure Letter-size print-sheet compositor for consumer manuals.

Free of HTML, VTK, and file I/O. Packs validated
:class:`~detailgen.rendering.action_frames.ActionFrame` values into printed
Letter pages under the consumer contract: cover first, prepared-kit
inventory next, at most two frames per page, an installation HOLD alone on
its own unavoidable page, no frame split across pages, and signed records
on their own page at the end.
"""

from __future__ import annotations

from dataclasses import dataclass

from .action_frames import ActionFrame, FrameContractError, HardwareLetter
from .instruction_panels import (
    RecordField,
    RelatedDocumentLink,
    _relative_html_basename,
)


@dataclass(frozen=True)
class ConsumerManualPage:
    """One printed Letter page."""

    number: int
    kind: str  # "cover" | "inventory" | "frames" | "hold" | "record"
    frames: tuple[ActionFrame, ...] = ()
    record_title: str = ""
    record_fields: tuple[RecordField, ...] = ()

    def __post_init__(self):
        if self.kind not in ("cover", "inventory", "frames", "hold",
                             "record"):
            raise FrameContractError(f"unknown page kind {self.kind!r}")
        if self.kind == "frames" and not 1 <= len(self.frames) <= 2:
            raise FrameContractError(
                f"page {self.number} carries {len(self.frames)} frames; "
                "printed pages hold one or two")
        if self.kind == "hold" and len(self.frames) != 1:
            raise FrameContractError(
                f"hold page {self.number} must carry exactly the hold frame")


@dataclass(frozen=True)
class ConsumerManual:
    """The composed consumer manual, ready for one HTML/print rendering."""

    title: str
    basename: str
    pages: tuple[ConsumerManualPage, ...]
    letters: tuple[HardwareLetter, ...]
    kit_gate: str
    cover_caption: str
    related_documents: tuple[RelatedDocumentLink, ...]


def compose_consumer_manual(
    *,
    frames: tuple[ActionFrame, ...],
    title: str,
    basename: str,
    letters: tuple[HardwareLetter, ...],
    kit_gate: str,
    cover_caption: str,
    related_documents: tuple[RelatedDocumentLink, ...] = (),
) -> ConsumerManual:
    """Pack frames into printed pages under the consumer page contract."""
    basename = _relative_html_basename(basename, "basename")
    if not frames:
        raise FrameContractError(
            "consumer manual requires at least one action frame")
    if not title.strip():
        raise FrameContractError("title must be non-empty")

    pages = [
        ConsumerManualPage(number=1, kind="cover"),
        ConsumerManualPage(number=2, kind="inventory"),
    ]
    pending: list[ActionFrame] = []

    def flush():
        if pending:
            pages.append(ConsumerManualPage(
                number=len(pages) + 1, kind="frames",
                frames=tuple(pending)))
            pending.clear()

    record_sources = []
    for frame in frames:
        if frame.record_fields:
            record_sources.append(frame)
        if frame.is_hold_gate:
            flush()
            pages.append(ConsumerManualPage(
                number=len(pages) + 1, kind="hold", frames=(frame,)))
            continue
        pending.append(frame)
        if len(pending) == 2:
            flush()
    flush()

    for frame in record_sources:
        pages.append(ConsumerManualPage(
            number=len(pages) + 1, kind="record",
            record_title=frame.record_title or "Completion record",
            record_fields=frame.record_fields))

    return ConsumerManual(
        title=title,
        basename=basename,
        pages=tuple(pages),
        letters=letters,
        kit_gate=kit_gate,
        cover_caption=cover_caption,
        related_documents=related_documents,
    )


def visible_instructional_words(manual: ConsumerManual) -> int:
    """Count reader-visible instructional words.

    Counts the cover caption and every frame's caption, warning, hold, and
    tool text on frame/hold pages. Inventory and record pages are excluded
    by the acceptance definition.
    """
    total = len(manual.cover_caption.split())
    for page in manual.pages:
        for frame in page.frames:
            for text in (frame.caption, frame.warning, frame.hold,
                         frame.tool):
                total += len(text.split())
    return total
