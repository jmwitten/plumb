"""Typed access to the checked-in screw-catalog snapshot."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from types import MappingProxyType
from typing import Mapping

from ..core.units import IN


@dataclass(frozen=True)
class ScrewCatalogEntry:
    """One normalized retailer listing used for geometry and reader copy."""

    ref: str
    item_label: str
    display_size: str
    diameter_in: float
    length_in: float
    head_style: str
    drive_style: str
    product_class: str
    manufacturer: str
    model_number: str
    retailer: str
    retailer_product_id: str
    retailer_url: str
    retrieved_on: str
    geometry_basis: str

    @property
    def diameter_mm(self) -> float:
        return self.diameter_in * IN

    @property
    def length_mm(self) -> float:
        return self.length_in * IN


_FIELDS = tuple(ScrewCatalogEntry.__dataclass_fields__)


def _entry(row: object, index: int) -> ScrewCatalogEntry:
    if not isinstance(row, dict):
        raise ValueError(f"screw catalog row {index} must be an object")
    missing = sorted(set(_FIELDS) - set(row))
    extra = sorted(set(row) - set(_FIELDS))
    if missing or extra:
        raise ValueError(
            f"screw catalog row {index} schema mismatch: "
            f"missing={missing}, extra={extra}"
        )
    entry = ScrewCatalogEntry(**row)
    if not entry.ref.strip():
        raise ValueError(f"screw catalog row {index} has an empty ref")
    if entry.diameter_in <= 0 or entry.length_in <= 0:
        raise ValueError(f"screw catalog {entry.ref!r} has non-positive geometry")
    if not entry.retailer_url.startswith("https://www.homedepot.com/p/"):
        raise ValueError(
            f"screw catalog {entry.ref!r} has an unexpected retailer URL"
        )
    return entry


@lru_cache(maxsize=1)
def screw_catalog() -> Mapping[str, ScrewCatalogEntry]:
    """Load and validate the immutable screw catalog once per process."""
    resource = files("detailgen.catalogs").joinpath("screws.json")
    rows = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("screw catalog root must be a list")
    entries: dict[str, ScrewCatalogEntry] = {}
    for index, row in enumerate(rows):
        entry = _entry(row, index)
        if entry.ref in entries:
            raise ValueError(f"duplicate screw catalog reference {entry.ref!r}")
        entries[entry.ref] = entry
    return MappingProxyType(entries)


def get_screw(ref: str) -> ScrewCatalogEntry:
    """Resolve one stable reference or fail loudly with the available keys."""
    catalog = screw_catalog()
    try:
        return catalog[ref]
    except KeyError:
        raise ValueError(
            f"unknown screw catalog reference {ref!r}; "
            f"known references: {sorted(catalog)}"
        ) from None
