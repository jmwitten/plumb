"""Compilation-local registry for optional domain packs.

This registry is deliberately unrelated to :mod:`detailgen.core.registry`.
Importing a domain pack must not add vocabulary to the process-wide DetailSpec
registries; a packed project resolves its requested front ends in this local
table and lowers their output to the ordinary base language.
"""

from __future__ import annotations

from collections.abc import Iterable


class PackRegistry:
    """Exact ``pack-id@major`` lookup with no implicit version selection."""

    def __init__(self, packs: Iterable[object] = ()):
        self._packs: dict[tuple[str, int], object] = {}
        for pack in packs:
            self.register(pack)

    def register(self, pack: object) -> object:
        pack_id = str(getattr(pack, "pack_id", "")).strip()
        major = getattr(pack, "major_version", None)
        if not pack_id or not isinstance(major, int) or isinstance(major, bool):
            raise ValueError(
                "a pack must declare a non-empty pack_id and integer major_version"
            )
        key = (pack_id, major)
        if key in self._packs:
            raise ValueError(f"pack {pack_id!r}@{major} is already registered")
        self._packs[key] = pack
        return pack

    def resolve(self, ref):
        from .project import ProjectSchemaError

        key = (ref.pack_id, ref.major_version)
        try:
            return self._packs[key]
        except KeyError:
            available = self.available()
            raise ProjectSchemaError(
                f"unknown pack {ref.key!r}; available packs: {available}"
            ) from None

    def available(self) -> list[str]:
        return [f"{pack_id}@{major}" for pack_id, major in sorted(self._packs)]


def default_pack_registry() -> PackRegistry:
    """Return a fresh built-in registry for one compilation.

    The import is lazy so importing :mod:`detailgen.packs` itself remains free of
    domain behavior and registry side effects. Cabinetry is added by its task;
    until then the built-in table is intentionally empty.
    """

    registry = PackRegistry()
    try:
        from .cabinetry import FramelessCabinetryPack, FramelessVanityPack
    except ModuleNotFoundError as exc:
        if exc.name not in {"detailgen.packs.cabinetry", "detailgen.packs"}:
            raise
    else:
        registry.register(FramelessCabinetryPack())
        registry.register(FramelessVanityPack())
    return registry
