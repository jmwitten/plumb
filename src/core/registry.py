"""``Registry[T]``: the mechanism by which detailgen resolves a stable
string key ("2x6", "hex_bolt", "steel_galv", "step", "bearing") to a
concrete Python object — a component class, a :class:`~.materials.Material`
instance, an exporter function, or a validation-pipeline stage. Roadmap
item 8 ("Registry / plugin architecture"): this is what the future
DetailSpec compiler (W2-7) will call to turn spec vocabulary into working
code, replacing the hardcoded tables that used to live in
``components/__init__.py``, ``core/materials.py``, ``rendering/export.py``
and the fixed pipeline in ``validation/checks.py``.

North star (binds the whole registry surface): a lookup either succeeds or
fails LOUDLY — never a guess, never a silent default. :meth:`Registry.get`
on an unknown key raises :class:`UnknownEntryError`, which lists every
known key plus near-miss suggestions (a typo'd "hexbolt" points at
"hex_bolt") — the same spirit as
:meth:`~detailgen.assemblies.connection.Connection.__post_init__`'s
datum-name diagnostic.

Registration is a decorator applied at the DEFINING module's top level
(``@components.register("lumber")`` on the ``Lumber`` class, etc.), so it
runs once, at import time, with no extra ceremony for a detail author who
just does ``from detailgen.components import Lumber`` — that import
already executes ``components/lumber.py`` top to bottom.
"""

from __future__ import annotations

import difflib
from typing import Callable, Generic, Iterable, Iterator, TypeVar

T = TypeVar("T")


class UnknownEntryError(KeyError):
    """Raised by :meth:`Registry.get` on a key that was never registered.

    A ``KeyError`` subclass (so existing ``except KeyError`` call sites
    keep working unchanged), carrying the offending name, the registry's
    ``kind`` (used in the message), and every known key — a caller can
    inspect ``.known_keys`` instead of re-parsing the message string.
    """

    def __init__(self, name: str, kind: str, known: Iterable[str]):
        known_keys = sorted(known)
        suggestions = difflib.get_close_matches(name, known_keys, n=3)
        hint = f" — did you mean one of {suggestions}?" if suggestions else ""
        message = f"unknown {kind} {name!r}; known {kind}s: {known_keys}{hint}"
        super().__init__(message)
        self.name = name
        self.kind = kind
        self.known_keys = known_keys


class DuplicateEntryError(KeyError):
    """Raised when a key is registered twice without ``override=True``."""

    def __init__(self, name: str, kind: str):
        message = (
            f"{kind} {name!r} is already registered — pass override=True "
            "to replace it"
        )
        super().__init__(message)
        self.name = name
        self.kind = kind


class Registry(Generic[T]):
    """A name -> object table for one vocabulary (``kind``, e.g.
    "component", "material", "exporter", "check"). Decorator registration,
    rich unknown-key diagnostics, hard duplicate detection.

    Not thread-safety-hardened: registration only ever happens at module
    import time (single-threaded, GIL-protected dict writes) — the same
    assumption every other process-wide table in this codebase makes (see
    ``core.base._SOLID_CACHE``).
    """

    def __init__(self, kind: str):
        self.kind = kind
        self._entries: dict[str, T] = {}

    def register(self, name: str, *, override: bool = False) -> Callable[[T], T]:
        """Decorator: ``@registry.register("key")`` (or
        ``@registry.register("key", override=True)`` to replace an
        existing entry on purpose). Returns the decorated object
        unchanged, so it works equally on a class or a plain function with
        zero side effect on the object itself — only this registry's table
        is mutated."""

        def decorator(obj: T) -> T:
            if not override and name in self._entries:
                raise DuplicateEntryError(name, self.kind)
            self._entries[name] = obj
            return obj

        return decorator

    def get(self, name: str) -> T:
        """Resolve ``name`` to its registered object, or raise
        :class:`UnknownEntryError` (with near-miss suggestions) — never a
        guess, never a silent default."""
        try:
            return self._entries[name]
        except KeyError:
            raise UnknownEntryError(name, self.kind, self._entries.keys()) from None

    def names(self) -> list[str]:
        """Every registered key, in registration order."""
        return list(self._entries)

    def __contains__(self, name: object) -> bool:
        return name in self._entries

    def __getitem__(self, name: str) -> T:
        """Dict-like alias for :meth:`get`, for drop-in compatibility with
        code that used to index a plain dict (e.g. the old
        ``MATERIALS[key]``)."""
        return self.get(name)

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[str]:
        return iter(self._entries)


# -- The four concrete registries (roadmap item 8) --------------------------
#
# Each is populated by its DEFINING module at import time:
#   - components -> src/components/{lumber,concrete,fasteners,connectors}.py
#   - materials  -> src/core/materials.py
#   - exporters  -> src/rendering/export.py
#   - checks     -> src/validation/checks.py
#
# Importing detailgen.components / detailgen.core / detailgen.rendering /
# detailgen.validation — which every detail script already does — populates
# all four; no new import ceremony for a detail author.

components: Registry = Registry("component")
materials: Registry = Registry("material")
exporters: Registry = Registry("exporter")
checks: Registry = Registry("check")


#: Thin decorator aliases (``@register_component("lumber")`` instead of
#: ``@components.register("lumber")``) — purely readability at the call
#: site; identical semantics to the underlying registry's ``.register``.
def register_component(name: str, *, override: bool = False):
    return components.register(name, override=override)


def register_material(name: str, *, override: bool = False):
    return materials.register(name, override=override)


def register_exporter(name: str, *, override: bool = False):
    return exporters.register(name, override=override)


def register_check(name: str, *, override: bool = False):
    return checks.register(name, override=override)


def load_entry_points() -> None:
    """Seam for third-party detail libraries (roadmap item 8, requirement
    6): real packaging-level ``importlib.metadata.entry_points`` discovery
    is NOT implemented this task — it needs a third-party distribution
    declaring an entry-point group (e.g. ``detailgen.components``) for this
    to find, which doesn't exist yet in this single-package repo. Wiring it
    in later is a few lines:

        from importlib.metadata import entry_points
        for ep in entry_points(group="detailgen.components"):
            ep.load()  # importing the module runs its @components.register(...)

    Calling this today is a deliberate, documented no-op — not a stub that
    silently almost-works.
    """
    return None
