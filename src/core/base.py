"""Component: the base class every part in this package inherits from.

Design contract
---------------
1. A Component is an immutable-ish parametric part. All dimensions are set in
   ``__init__`` (in mm — use ``detailgen.core.units`` helpers for imperial).
2. Subclasses implement ``_build() -> cq.Workplane`` and nothing else is
   required. Geometry must be built in the component's own **local frame**,
   with a documented datum (state it in the class docstring). Placement into
   a detail is the assembly's job, never the component's.
3. ``solid`` caches the built geometry; parameters must not be mutated after
   first build (there is no invalidation on purpose — keep parts simple).
   The build is also shared process-wide across every instance with an
   equal ``cache_key()`` (see ``_SOLID_CACHE`` below) — a direct consequence
   of the same "pure function of params" contract: two components with
   equal params are, by construction, geometrically identical, so a real
   assembly's repeated fasteners (8 identical washers, etc.) only pay the
   ``_build()`` cost once per run.
4. ``check()`` returns human-readable problems with the *parameters*
   (e.g. "lag screw longer than stock lengths"). Geometric checks between
   parts live in ``detailgen.validation``, not here.

See ``detailgen.components.lumber.Lumber`` for the annotated reference
implementation of this contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import cadquery as cq

from .diskcache import DiskCache, brep_dumps, brep_loads, component_disk_key
from .frame import Frame
from .materials import Material, MATERIALS

#: Process-wide cache of built LOCAL solids, keyed by ``Component.cache_key()``.
#: Shared across every ``Component`` instance and every ``DetailAssembly`` in
#: the process (not per-assembly), because identity here is (type, params),
#: never object identity — see ``cache_key``. Safe to share the built
#: ``cq.Workplane`` object itself rather than copy it: no plain READ mutates
#: a component's local solid in place (``Placed.world_solid`` calls the
#: non-mutating ``.moved()`` — which still shares this ``TShape`` —
#: and ``bounding_box``/``volume`` only read).
#:
#: Meshing is the one operation that WOULD mutate the shared shape (a
#: triangulation attached to the ``TShape`` shifts a later exact
#: ``BoundingBox()``/``Volume()`` on borderline geometry by up to ~1e-1 mm),
#: so every mesh path is required to run on a deep COPY that shares no
#: ``TShape`` with this cache: ``geometry_hash`` copies each shape before it
#: ``Clean_s``+tessellates (see ``core.buildinfo``), and the tessellating
#: exporters mesh ``DetailAssembly.isolated_world_solids`` copies rather than
#: the shared ``world_solid`` (see ``rendering.export``). Nothing that meshes
#: ever touches a cached ``TShape`` — that is what keeps a shared solid's
#: geometry stable for every reader across the process.
_SOLID_CACHE: dict[tuple, cq.Workplane] = {}


def _reset_solid_cache() -> None:
    """Test helper: clear the process-wide solid cache. Only needed by tests
    that assert exact build/cache-hit counts across otherwise-unrelated
    component instances — normal operation never needs to invalidate this."""
    _SOLID_CACHE.clear()


#: Persistent (cross-RUN, cross-PROCESS) tier of the solid cache — S3c
#: lever (b). Tier 2 under ``_SOLID_CACHE`` above: a miss on the in-run
#: dict now checks this disk cache before paying ``_build()``'s CAD-kernel
#: cost. Content-addressed by (component type, exact params,
#: geometry-code fingerprint) — see ``diskcache.component_disk_key``.
#:
#: Deliberately does NOT also compute/persist this component's geometry
#: DIGEST here (only the raw BREP): that digest is only ever needed by
#: ``core.buildinfo.local_geometry_digest`` (called from ``build_manifest``
#: at render time, and from ``validation.checks``'s verdict-cache keys
#: during validation) — computing it eagerly on every miss would force a
#: tessellation into every build, including the plain "assemble + validate,
#: never render" CLI loop that today never pays that cost at all. Leaving
#: it to ``local_geometry_digest`` keeps this tier's cost identical to
#: ``_build()`` alone; the digest gets ITS OWN persistent tier, in
#: ``core.buildinfo``, keyed by the same ``component_disk_key``.
_SOLID_DISK_CACHE = DiskCache("solids")


def _persist_solid(key: str, shapes: list) -> None:
    """Best-effort write: a serialization failure (or a disk-full/
    read-only filesystem, already handled inside ``DiskCache.put``) must
    never break a build that otherwise succeeded — the freshly-built
    ``shapes`` this process is about to use are unaffected either way."""
    try:
        payload = brep_dumps(shapes)
    except Exception:
        return
    _SOLID_DISK_CACHE.put(key, payload)


def _load_solid(key: str) -> "cq.Workplane | None":
    """Disk-cache read for the persistent solid tier. Any failure —
    missing entry, malformed payload, a BREP that fails to parse — is a
    miss, never an exception (see ``core.diskcache`` module docstring)."""
    data = _SOLID_DISK_CACHE.get(key)
    if data is None:
        return None
    try:
        return cq.Workplane("XY").newObject(brep_loads(data))
    except Exception:
        return None


class Component(ABC):
    #: Key into MATERIALS; subclasses override (or set per-instance).
    material_key: str = "steel_galv"

    def __init__(self, name: str):
        self.name = name
        self._solid: cq.Workplane | None = None

    # -- geometry -----------------------------------------------------------

    @abstractmethod
    def _build(self) -> cq.Workplane:
        """Build and return the part in its local frame. Called once."""

    def cache_key(self) -> tuple:
        """Stable identity for this component's (type, parameters), used to
        share a built solid (and its geometry hash, see ``core.buildinfo``)
        across every instance that is geometrically identical.

        Independent of ``name`` and instance identity — like ``bom_group``
        — but exact rather than ``describe()``'s human-rounded bounding-box
        string: a build/hash cache can't tolerate two different geometries
        colliding on the same key, so this hashes every public param's
        ``repr()`` instead."""
        return (type(self).__name__, tuple(sorted(
            (k, repr(v)) for k, v in self.params().items()
        )))

    @property
    def solid(self) -> cq.Workplane:
        """The part's geometry (built lazily, cached). Shared process-wide
        across every component instance with an equal ``cache_key()`` —
        see ``_SOLID_CACHE`` — and, beneath that, shared ACROSS RUNS via
        the persistent disk tier (``_SOLID_DISK_CACHE``, S3c lever b): a
        miss on both the in-run dict AND the disk cache builds fresh and
        persists the BREP for next time; a hit loads BREP bytes instead of
        calling ``_build()`` at all. Deliberately does not compute or
        persist a geometry digest here — see ``_SOLID_DISK_CACHE``'s
        docstring for why that's ``core.buildinfo``'s job instead."""
        if self._solid is None:
            key = self.cache_key()
            cached = _SOLID_CACHE.get(key)
            if cached is None:
                disk_key = component_disk_key(self)
                cached = _load_solid(disk_key)
                if cached is None:
                    cached = self._build()
                    _persist_solid(disk_key, cached.vals())
                _SOLID_CACHE[key] = cached
            self._solid = cached
        return self._solid

    @property
    def material(self) -> Material:
        return MATERIALS[self.material_key]

    # -- datums (named local-frame placement handles) -----------------------

    @property
    def datums(self) -> dict[str, Frame]:
        """Named :class:`~detailgen.core.frame.Frame` handles in the component's
        **local** frame, promoting the prose datum note in each class docstring
        to machine geometry. The assembly mates two datums to place a part (see
        ``DetailAssembly.place``); a datum's +Z is its assembly-up axis.

        Every component gets a free ``origin`` datum (the local origin, axes
        aligned). Subclasses add construction-vocabulary datums by overriding
        ``_datums`` (e.g. lumber ``base``/``top``/``end_near``; a bolt's
        ``head_bearing``/``tip``)."""
        d: dict[str, Frame] = {"origin": Frame.identity()}
        d.update(self._datums())
        return d

    def _datums(self) -> dict[str, Frame]:
        """Component-specific datums (excluding ``origin``). Override this."""
        return {}

    def datum(self, name: str) -> Frame:
        """Look up a single named datum, with a helpful error listing the
        available names."""
        try:
            return self.datums[name]
        except KeyError:
            raise KeyError(
                f"{self.name}: no datum {name!r}; available: "
                f"{sorted(self.datums)}"
            ) from None

    def bounding_box(self) -> cq.BoundBox:
        return self.solid.val().BoundingBox()

    def volume(self) -> float:
        """Solid volume in mm^3 (useful for sanity checks and BOM weights)."""
        return self.solid.val().Volume()

    # -- validation ---------------------------------------------------------

    def check(self) -> list[str]:
        """Return a list of parameter problems (empty list = OK).

        Subclasses should extend, not replace:

            def check(self):
                problems = super().check()
                if self.length > 12 * FT:
                    problems.append(f"{self.name}: length exceeds stock")
                return problems
        """
        return []

    # -- misc ----------------------------------------------------------------

    def params(self) -> dict:
        """Public parameters for BOMs/reports (everything not underscored)."""
        return {
            k: v for k, v in vars(self).items()
            if not k.startswith("_") and k != "name"
        }

    # -- bill-of-materials hooks (override for readable BOM rows) -------------

    def describe(self) -> str:
        """Human-readable size string for the BOM. Default: bounding box in
        inches. Override for catalog-style descriptions."""
        from .units import inches
        bb = self.bounding_box()
        return (f'{inches(bb.xlen):.2f} x {inches(bb.ylen):.2f} x '
                f'{inches(bb.zlen):.2f} in')

    def assumptions(self) -> str:
        """Modeling assumptions/simplifications for this part (BOM + report)."""
        return ""

    def bom_group(self) -> str:
        """Key that identical parts share so a BOM can aggregate quantities.
        Default groups by type + description; override to merge/split lines."""
        return f"{type(self).__name__}|{self.describe()}"

    def bom_label(self) -> str:
        """Clean noun for the BOM 'item' column. Default: class name spaced."""
        import re
        return re.sub(r"(?<!^)(?=[A-Z])", " ", type(self).__name__)

    def bom_length_mm(self) -> float | None:
        """Machine-readable cut length in mm, for components that are linear
        stock (cut-planning/optimization). ``None`` for parts with no single
        cut-length axis (fasteners, connectors, poured/imported parts) — the
        default ``describe()`` string is display-only and not meant to be
        parsed back into a number; components that DO have a real length
        (e.g. ``Lumber``) override this instead of asking a caller to parse
        their ``describe()`` output."""
        return None

    def fabrication_record(self):
        """This part's :class:`~detailgen.core.process_graph.ProcessRecord` —
        ``stock -> ordered steps -> installed geometry`` (the Construction
        Process Graph's v1 fabrication slice). ``None`` here: the base part is
        not a fabricated linear-stock member, so it has no derived record yet.
        ``Lumber`` and ``DeckBoard`` override to return a real record; their
        ``_build`` delegates to ``fold`` of it, so the record is the single
        authoritative source of their installed geometry (fab-design §5/§8).
        Purchased-as-is parts (a bolt, a joist hanger) are honestly step-empty
        and are formalized as FAB-2/3 need them."""
        return None

    def stub_of(self) -> dict | None:
        """Partial-member metadata: non-``None`` when this component models
        only a portion of a longer physical member whose full run belongs to
        another detail (e.g. a beam-end stub at a tree or rock-anchor
        connection, whose continuous run is the platform's beam or leg).

        ``None`` for an ordinary part. When set, a dict with:

        - ``full_dims``: the full piece's dimension string (e.g.
          ``'2x6 x 48.0" (continuous beam)'``).
        - ``modeled_dims``: this component's own ``describe()`` — the
          modeled (stub) portion, for display alongside the full piece.
        - ``note``: a site-facing sentence naming which detail owns the
          full run.

        Consumed by the BOM row (``DetailAssembly._part_row``) and the
        interactive-viewer tooltip payload (``build_viewer_payload``) so a
        stub is never presented as if it were the complete piece."""
        return None

    def __repr__(self) -> str:
        args = ", ".join(f"{k}={v!r}" for k, v in self.params().items())
        return f"{type(self).__name__}({self.name!r}, {args})"
