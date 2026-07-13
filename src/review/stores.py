"""Per-detail findings-store enumeration: the naming convention as a first-class
surface, so a detail's stores are DISCOVERED, not hand-pointed.

A reviewer files suspicions into repo-tracked YAML under ``reviews/visual/``. Each
detail owns up to two sibling stores with the same schema (:mod:`.store`):

    ``<name>-findings.yaml``          — the VISUAL smell-test store
    ``<name>-design-findings.yaml``   — the DESIGN-review store

``<name>`` is the store's short label (the zipline's is ``zipline``; the caddy's
is ``caddy``). This module turns that convention into an enumeration: given the
reviews directory, it maps each name to its store paths in a byte-stable order,
resolves one store by ``(name, kind)``, and loads a detail's stores together with
a cross-store id check. It is the seam that lets a NEW detail's store appear with
zero plumbing — drop ``<name>-findings.yaml`` in the directory and it is found.

The single main store predates the convention as the bare ``findings.yaml``; it is
the ZIPLINE's visual store in fact. It has been renamed ``zipline-findings.yaml``
so the convention is TOTAL (no nameless special case in the enumerator). A legacy
bare ``findings.yaml`` is still resolved as the zipline's visual store — a compat
read so an un-migrated checkout or an external reference to the old path does not
hard-fail — but it may not coexist with the canonical name (that is ambiguous, and
loud).

Schema drift stays loud: each store still loads through :func:`load_findings_file`,
which is strict and teaching. This module adds one cross-file rule — a detail's
finding ids share ONE namespace across its stores, so an id in both the visual and
the design store is a hard, teaching error (a finding must be referenceable
unambiguously).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .finding import ReviewSchemaError
from .store import FindingStore, load_findings_file

#: Store-filename suffixes. The DESIGN suffix is a strict extension of the VISUAL
#: one, so it MUST be tested first: ``caddy-design-findings.yaml`` is the caddy's
#: design store, not a visual store named ``caddy-design``.
VISUAL_SUFFIX = "-findings.yaml"
DESIGN_SUFFIX = "-design-findings.yaml"

#: The store's short label carried by the bare pre-convention filename.
ZIPLINE = "zipline"
#: The pre-convention name of the zipline's visual store (compat read only).
LEGACY_ZIPLINE_VISUAL = "findings.yaml"

VISUAL = "visual"
DESIGN = "design"


def _classify(filename: str) -> tuple[str, str] | None:
    """Map a filename to ``(name, kind)`` per the convention, or ``None`` if it is
    not a findings store. The design suffix wins over the visual one; a store with
    an empty name (e.g. a stray ``-findings.yaml``) is not a store."""
    if filename.endswith(DESIGN_SUFFIX):
        name = filename[: -len(DESIGN_SUFFIX)]
        return (name, DESIGN) if name else None
    if filename.endswith(VISUAL_SUFFIX):
        name = filename[: -len(VISUAL_SUFFIX)]
        return (name, VISUAL) if name else None
    if filename == LEGACY_ZIPLINE_VISUAL:
        return (ZIPLINE, VISUAL)
    return None


@dataclass(frozen=True)
class DetailStores:
    """One detail's store PATHS: its visual store and/or its design store (either
    may be absent). Paths only — loading is :meth:`load` / :func:`load_detail_stores`
    so a caller that only needs to know where a store lives never reads it."""

    name: str
    visual: Path | None
    design: Path | None

    def path(self, kind: str) -> Path | None:
        if kind == VISUAL:
            return self.visual
        if kind == DESIGN:
            return self.design
        raise ValueError(f"unknown store kind {kind!r}; expected {VISUAL!r} or {DESIGN!r}")


def enumerate_detail_stores(reviews_dir: str | Path) -> dict[str, DetailStores]:
    """Discover every per-detail store under ``reviews_dir`` by the naming
    convention. Returns ``{name: DetailStores}`` in sorted-by-name order (a
    byte-stable, reproducible enumeration). A missing directory is an empty map,
    not an error — the surface is additive.

    Two files claiming the same ``(name, kind)`` — e.g. both the canonical
    ``zipline-findings.yaml`` and the legacy bare ``findings.yaml`` — is a loud,
    teaching error: the store is ambiguous and must be de-duplicated."""
    reviews_dir = Path(reviews_dir)
    visual: dict[str, Path] = {}
    design: dict[str, Path] = {}
    if reviews_dir.is_dir():
        for p in sorted(reviews_dir.iterdir(), key=lambda x: x.name):
            if not p.is_file():
                continue
            classified = _classify(p.name)
            if classified is None:
                continue
            name, kind = classified
            target = visual if kind == VISUAL else design
            if name in target:
                raise ReviewSchemaError(
                    f"{reviews_dir}: two files both claim the {kind} store for detail "
                    f"{name!r}: {target[name].name} and {p.name}. A detail has exactly "
                    "one store per kind; remove the stale/legacy file (the canonical "
                    f"name is {name}{DESIGN_SUFFIX if kind == DESIGN else VISUAL_SUFFIX})."
                )
            target[name] = p
    names = sorted(set(visual) | set(design))
    return {n: DetailStores(name=n, visual=visual.get(n), design=design.get(n)) for n in names}


def find_detail_store(reviews_dir: str | Path, name: str,
                      kind: str = VISUAL) -> Path | None:
    """Resolve ONE store path for ``(name, kind)``, or ``None`` if the detail has
    no store of that kind. Includes the legacy-``findings.yaml`` compat read for
    the zipline's visual store (via :func:`enumerate_detail_stores`)."""
    stores = enumerate_detail_stores(reviews_dir)
    detail = stores.get(name)
    return None if detail is None else detail.path(kind)


@dataclass(frozen=True)
class LoadedDetailStores:
    """A detail's LOADED stores. ``visual`` / ``design`` are :class:`FindingStore`
    or ``None`` (that kind absent). The load has already enforced the cross-store
    id namespace, so a consumer can render both blocks without re-checking."""

    name: str
    visual: FindingStore | None
    design: FindingStore | None


def load_detail_stores(reviews_dir: str | Path, name: str) -> LoadedDetailStores:
    """Load a detail's stores together. Each store loads through the strict,
    teaching :func:`load_findings_file` (so schema drift is loud per file), then a
    cross-store rule fires: the visual and design stores share ONE id namespace, so
    an id present in both is a hard, teaching error.

    An unknown detail (no store of any kind) is a teaching error naming the detail
    names that DO have stores — the enumeration is the source of truth."""
    stores = enumerate_detail_stores(reviews_dir)
    detail = stores.get(name)
    if detail is None:
        raise ReviewSchemaError(
            f"{Path(reviews_dir)}: no findings store for detail {name!r}. Stores are "
            f"discovered by filename ({{name}}{VISUAL_SUFFIX} / {{name}}{DESIGN_SUFFIX}); "
            f"known details: {sorted(stores)}."
        )
    visual = load_findings_file(detail.visual) if detail.visual else None
    design = load_findings_file(detail.design) if detail.design else None
    _check_cross_store_ids(name, detail, visual, design)
    return LoadedDetailStores(name=name, visual=visual, design=design)


def _check_cross_store_ids(name: str, detail: DetailStores,
                           visual: FindingStore | None,
                           design: FindingStore | None) -> None:
    """A detail's finding ids are unique ACROSS its stores (each store already
    enforces uniqueness within itself). An id in both stores would make a finding
    reference ambiguous — a loud, teaching error naming the ids and both files."""
    if visual is None or design is None:
        return
    vids = {f.id for f in visual.findings}
    collisions = sorted({f.id for f in design.findings if f.id in vids})
    if collisions:
        raise ReviewSchemaError(
            f"detail {name!r}: finding id(s) {collisions} appear in BOTH "
            f"{detail.visual.name} and {detail.design.name}. A detail's finding ids "
            "share one namespace across its stores so a finding is referenced "
            "unambiguously — renumber one store."
        )
