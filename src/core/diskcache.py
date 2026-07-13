"""Persistent, content-addressed, on-disk cache mechanism (S3c).

Two callers build on the one mechanism here: ``core.base``'s persistent
BREP solid cache (lever b — tier 2 of the in-run ``_SOLID_CACHE`` S3b
added) and ``validation.checks``'s per-pair verdict cache (lever d). Both
own their OWN key construction (mapping each check's/component's complete
input surface — see those modules) and their own (de)serialization; this
module supplies only the shared byte store, gitignored default root, and
the honesty/safety rules that both tiers must obey identically:

- **Content-addressed**: a key is written once and read many times; the
  same key always maps to the same bytes (callers are responsible for that
  invariant by keying on every input that can change the value — a stale
  hit is a key that FAILED to cover its inputs, never a cache bug).
- **Atomic writes**: ``put`` writes to a pid+counter-unique temp file in
  the same directory, then ``os.replace`` (atomic on POSIX) — a reader
  never observes a partial write, and two processes racing to fill the
  same key is redundant work, never corruption (content-addressing means
  both writers would write the identical bytes anyway).
- **Corrupt/unreadable entry = miss, never a crash**: a cache is an
  optimization, not a source of truth, so any doubt about an entry (I/O
  error, and — for callers layering their own deserialization on top of
  the raw bytes here, e.g. a torn BREP or invalid JSON — a parse error)
  must fail open to "recompute", never fail closed to "raise".
- **Kill switch**: ``DETAILGEN_NO_CACHE=1`` disables both tiers; checked
  fresh on every ``get``/``put`` call (never latched at import or
  construction time), so a single process — notably the equivalence tests
  in ``tests/test_persistent_caches.py`` — can flip it between calls.
- ``DETAILGEN_CACHE_DIR`` overrides the on-disk root the same way, for the
  same reason (test isolation without reimporting every ``detailgen``
  module).
"""

from __future__ import annotations

import itertools
import os
from pathlib import Path

DEFAULT_CACHE_ROOT = Path("outputs") / "cache"

_tmp_seq = itertools.count()


def cache_disabled() -> bool:
    """The kill switch. Read fresh on every call — see module docstring."""
    return os.environ.get("DETAILGEN_NO_CACHE") == "1"


def cache_root() -> Path:
    """``DETAILGEN_CACHE_DIR`` if set, else ``outputs/cache`` (relative to
    the process cwd — every detail script/test in this repo runs with the
    repo root as cwd). Read fresh on every call — see module docstring."""
    override = os.environ.get("DETAILGEN_CACHE_DIR")
    return Path(override) if override else DEFAULT_CACHE_ROOT


class DiskCache:
    """A content-addressed byte store under ``cache_root() / subdir``.

    Keys are opaque strings; this class only hashes a key into a
    filesystem-safe fixed-length name (so callers never need to worry about
    path-unsafe characters or filename length limits). Values are raw
    bytes — (de)serialization is entirely the caller's job, so this one
    class serves both the solid cache (BREP bytes) and the verdict cache
    (JSON bytes) without knowing about either.

    ``hits``/``misses`` count real attempts to read a value (including
    while the kill switch is on, so a benchmark comparing scenarios can
    tell "disabled" apart from "enabled but empty" if needed) — the
    per-check-kind breakdown callers may want (e.g. ``pairs_from_cache`` on
    ``ValidationReport``) is their own responsibility to derive from a
    before/after snapshot of these counters, since one ``DiskCache``
    instance is shared across every key this tier ever sees.
    """

    def __init__(self, subdir: str):
        self.subdir = subdir
        self.hits = 0
        self.misses = 0

    def _path(self, key: str) -> Path:
        import hashlib

        digest = hashlib.sha256(key.encode()).hexdigest()
        return cache_root() / self.subdir / digest[:2] / f"{digest}.bin"

    def get(self, key: str) -> bytes | None:
        if cache_disabled():
            self.misses += 1
            return None
        path = self._path(key)
        try:
            data = path.read_bytes()
        except OSError:
            self.misses += 1
            return None
        self.hits += 1
        return data

    def put(self, key: str, data: bytes) -> None:
        """Never raises: a write failure (read-only filesystem, disk full,
        a racing rmtree of the cache dir) degrades to a future miss, not a
        crash of whatever build/check triggered the write."""
        if cache_disabled():
            return
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.parent / f".tmp-{os.getpid()}-{next(_tmp_seq)}"
            tmp.write_bytes(data)
            os.replace(tmp, path)
        except OSError:
            pass

    def reset_counts(self) -> None:
        """Test helper: zero the hit/miss counters without touching
        on-disk content."""
        self.hits = 0
        self.misses = 0


def component_geometry_fingerprint() -> str:
    """sha256 over every source file whose text can change what
    ``Component._build()`` produces for ANY component: every module
    directly under ``components/`` (all component classes plus shared
    geometry helpers such as ``_geometry.py``'s ``angle_profile``/
    ``threaded_shaft``/``hex_prism``) and ``core/units.py`` (``IN``/
    ``FT``/etc — almost every ``_build()`` multiplies a raw literal by
    one of these, so a changed conversion constant would silently change
    real millimeter geometry with no parameter change at all — a
    per-file, per-class fingerprint would miss that). Deliberately broad
    rather than tracing which component uses which helper: hashing a
    handful of small text files once per process is free next to the
    OCCT work this fingerprint exists to gate, and erring toward
    invalidating too much (a shared helper's unrelated change busts every
    component's cache, not just its callers) is the honest direction to
    err in — see the S3c task brief's code-version-salting rule.

    Lives here (not in ``core.base``, the only place ``Component`` is
    defined) so ``core.buildinfo``'s persistent digest cache can use the
    IDENTICAL fingerprint without importing ``core.base`` — ``base.py``
    already imports ``buildinfo`` (for ``local_geometry_digest``), so the
    reverse import would be circular. Computed once per process; see
    ``COMPONENT_GEOMETRY_FINGERPRINT`` below."""
    src_root = Path(__file__).resolve().parent.parent  # .../src
    paths = sorted((src_root / "components").glob("*.py"))
    paths.append(src_root / "core" / "units.py")
    import hashlib

    h = hashlib.sha256()
    for p in paths:
        h.update(p.read_bytes())
    return h.hexdigest()


#: Computed once per process — see :func:`component_geometry_fingerprint`.
COMPONENT_GEOMETRY_FINGERPRINT = component_geometry_fingerprint()


#: Bumped whenever the on-disk serialization or hashing contract changes in a
#: way that makes previously-written entries wrong to reuse, so both persistent
#: tiers retire incompatible entries by simply missing on the new key (the old
#: files are unreachable, gitignored, and self-heal on next build). ``brep2`` =
#: the switch from lossy ASCII BREP to bit-faithful binary BREP (task #14):
#: without this bump an already-warm cache would keep serving old ASCII solids
#: (self-heal on read via a load failure) but ALSO keep serving digest strings
#: that were poisoned by an ASCII round trip (a valid ASCII string decodes fine
#: — nothing to fail on), so the poisoned assembly hashes would survive the fix.
_SERIALIZATION_FORMAT = "brep2"


def component_disk_key(component) -> str:
    """The identity key shared by ``core.base``'s persistent solid cache
    AND ``core.buildinfo``'s persistent digest cache for the same
    component: (serialization-format tag, geometry-code fingerprint, exact
    type+params). Two different persistent tiers, cached under different
    ``DiskCache`` subdirs, but they must agree on what "this exact component"
    means — sharing this one function is what guarantees that, rather than two
    independently-written key-builders drifting apart. The
    ``_SERIALIZATION_FORMAT`` prefix is what lets a format change (see there)
    invalidate BOTH tiers at once."""
    return (
        f"{_SERIALIZATION_FORMAT}|{COMPONENT_GEOMETRY_FINGERPRINT}"
        f"|{component.cache_key()!r}"
    )


def brep_dumps(shapes: list) -> bytes:
    """Serialize a list of ``cq.Shape`` into one bytes blob, preserving
    shape COUNT and each shape's OCCT type exactly — never collapsed into a
    single fused/compound identity. The shapes are added as immediate
    children of a container ``TopoDS_Compound`` purely as an envelope
    (nothing is fused or unioned); ``brep_loads`` recovers the exact same
    list ``Component._build()`` would have returned by iterating that
    container's immediate children back out, in the same order.

    Serialized in OCCT's BINARY BREP format (``BinTools``), NOT the ASCII
    ``BRepTools`` format, and the distinction is load-bearing, not stylistic.
    The ASCII writer emits surface/curve control points at limited decimal
    precision, so a reloaded shape's geometry differs from the built shape by
    ~1e-10 mm — negligible for volume/bbox but occasionally enough to tip one
    tessellation vertex across ``geometry_hash``'s 6-decimal rounding boundary,
    making a cache-warm ``geometry_hash`` (and every digest/assembly hash built
    on it) DIFFER from a cache-cold one. That was the SOLIDCACHE
    tessellation-faithfulness defect (task #14): a round trip must reproduce the
    built solid's ``geometry_hash`` bit-for-bit, or the persistent cache
    silently corrupts warm-cache doc builds once the solid and digest tiers
    desync. Binary BREP stores doubles in IEEE-754 exactly, so the round trip is
    bit-faithful — proven in
    ``tests/test_persistent_caches.py::test_solid_cache_round_trip`` on the
    trunk cylinder + cut-lumber shapes that expose the ASCII defect. It is also
    ~35% faster to write+read and ~20% smaller on disk than ASCII, so
    faithfulness costs nothing here — it is strictly cheaper.

    ``BinTools``' OCP binding is file-path based (no in-memory stream overload
    exposed), so this writes to a throwaway temp file and reads the bytes back
    — negligible cost next to the OCCT geometry work this cache exists to avoid.
    """
    import tempfile

    from OCP.BinTools import BinTools
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for s in shapes:
        builder.Add(compound, s.wrapped)

    fd, tmp_path = tempfile.mkstemp(suffix=".brep")
    os.close(fd)
    try:
        BinTools.Write_s(compound, tmp_path)
        return Path(tmp_path).read_bytes()
    finally:
        os.unlink(tmp_path)


def brep_loads(data: bytes) -> list:
    """Inverse of :func:`brep_dumps` (binary BREP — see there for why binary).
    Raises on any malformed input (unreadable BREP, wrong root shape type,
    or an entry written by the old ASCII format before the
    ``_SERIALIZATION_FORMAT`` bump) — callers reading a disk-cache entry must
    treat any exception from this as a corrupt entry, i.e. a miss (see module
    docstring), never let it propagate."""
    import tempfile

    import cadquery as cq
    from OCP.BinTools import BinTools
    from OCP.TopoDS import TopoDS, TopoDS_Iterator, TopoDS_Shape

    fd, tmp_path = tempfile.mkstemp(suffix=".brep")
    os.close(fd)
    try:
        Path(tmp_path).write_bytes(data)
        shape = TopoDS_Shape()
        BinTools.Read_s(shape, tmp_path)
    finally:
        os.unlink(tmp_path)

    compound = TopoDS.Compound_s(shape)
    it = TopoDS_Iterator(compound)
    children = []
    while it.More():
        children.append(cq.Shape.cast(it.Value()))
        it.Next()
    return children
