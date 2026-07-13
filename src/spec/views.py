"""SITEMODEL (task SM2 VIEWS): a detail is a VIEW of the one site model.

The north star (progress.md ADOPTED DIRECTION #1, the user's own framing): once
there is ONE compiled site model, "a detail" is no longer a separately-authored
document — it becomes a **view** of the site: a scope selector + a camera + a
little view-local annotation intent. A member two subsystems share is ONE node
in the model (SM1's ``bind:``/``dedup:``), so it appears in every view that
scopes it — the same ``Placed`` object, never a second copy that could diverge.
That single-node fact is what makes the reverse query ("where else does this
part appear?") meaningful rather than a name-match heuristic.

A view NEVER re-validates. Verdicts are SITE-level: the site runs one validation
sweep and one coverage matrix over the whole composed model. A view only
*presents* the slice that touches its scope — the site findings whose subjects
fall in scope, the BOM of the in-scope parts, the site coverage matrix verbatim.
It presents; it never re-proves. Correspondingly the render gate is site-level
(:meth:`View.render`): a view of a scoped subset may render ONLY when the WHOLE
site is clean — rendering a "clean-looking" view of a model with an open
contradiction elsewhere is exactly the dishonesty the site model exists to kill.

Drawing sheets later are just views with a projection (progress.md): the
``camera`` here already carries a projection hint, so that seam is not painted
out — a drawing sheet is a :class:`View` whose camera additionally fixes a scale
and a paper frame.

This module owns the view layer; ``src/spec/site.py`` carries only a marked
block (the ``views:`` loader hook + thin :class:`~detailgen.spec.site.SiteDetail`
accessors that delegate here).
"""

from __future__ import annotations

import difflib
import fnmatch
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..details.base import fmt_frac_in
from .schema import SpecSchemaError, _MISSING, _take
from .loader import _as_list, _default


# --------------------------------------------------------------------------- #
# Scope selectors — the minimal set that expresses the current site's two views.
#
# "the platform detail" and "the rock anchor close-up" both reduce to a single
# subsystem, so ``subsystem:`` is the primary (and the two authored views' only)
# selector. ``id:`` (a qualified-id glob) and ``name:`` (a display-name glob) are
# the two finer selectors a future view needs to carve BELOW a subsystem (e.g.
# "just the anchor's clamp angles", ``id: rock_anchor/angle_*``); they are here
# so a view can express sub-subsystem scope without inventing a tag vocabulary,
# and they are exercised by the tests. All three resolve against the ONE model's
# qualified id space (retired stubs / deduped bodies included — they resolve, by
# identity, to the shared real member, so a view that scopes the rock anchor
# sees the platform leg it clamps).
# --------------------------------------------------------------------------- #
_SELECTOR_KINDS = ("subsystem", "id", "name")


@dataclass(frozen=True)
class Selector:
    """One scope selector. ``kind`` is one of :data:`_SELECTOR_KINDS`:

    - ``subsystem`` — every qualified id prefixed ``<pattern>/`` (a whole
      subsystem, the natural "this detail" scope).
    - ``id`` — a ``fnmatch`` glob over the qualified ids (``rock_anchor/angle_*``).
    - ``name`` — a ``fnmatch`` glob over the parts' display names.

    A selector that matches ZERO parts is a LOUD error at resolve time (the
    SPATIAL precedent: a zero-match selector is a fake view, never a silently
    empty one)."""

    kind: str
    pattern: str

    def matches(self, qid: str, name: str) -> bool:
        if self.kind == "subsystem":
            return qid.startswith(f"{self.pattern}/")
        if self.kind == "id":
            return fnmatch.fnmatchcase(qid, self.pattern)
        if self.kind == "name":
            return fnmatch.fnmatchcase(name, self.pattern)
        raise AssertionError(f"unknown selector kind {self.kind!r}")  # pragma: no cover

    def to_dict(self) -> dict:
        return {self.kind: self.pattern}


@dataclass(frozen=True)
class ViewCallout:
    """A view-local dimension callout whose text is generated from a LIVE site
    value, so it can never drift from the model — the same discipline as
    :class:`detailgen.details.base.Callout`, generalized to reference ANY
    subsystem's param/derived by QUALIFIED name (``platform.leg_station``,
    ``rock_anchor.leg_gap``). ``p0``/``p1`` are fixed world-frame endpoints (mm);
    the value (and thus the label) is pulled from the site namespace at render
    time."""

    param: str
    label: str = "{v}"
    p0: tuple = (0.0, 0.0, 0.0)
    p1: tuple = (0.0, 0.0, 0.0)
    fmt: Callable[[float], str] = fmt_frac_in

    def value(self, site_ns: dict) -> float:
        try:
            return site_ns[self.param]
        except KeyError:
            known = sorted(k for k in site_ns if k.startswith(
                self.param.split(".", 1)[0] + "."))
            hint = difflib.get_close_matches(self.param, sorted(site_ns), n=3)
            tip = f" — did you mean one of {hint}?" if hint else ""
            raise SpecSchemaError(
                f"view callout param {self.param!r} is not a qualified site value"
                f"{tip}; a callout references a subsystem param/derived by "
                f"'<subsystem>.<name>'"
                + (f" (that subsystem has: {known})" if known else "")) from None

    def text(self, site_ns: dict) -> str:
        return self.label.format(v=self.fmt(self.value(site_ns)))

    def render(self, site_ns: dict) -> dict:
        return {"label": self.text(site_ns),
                "p0": [float(x) for x in self.p0],
                "p1": [float(x) for x in self.p1]}

    def to_dict(self) -> dict:
        d = {"param": self.param}
        if self.label != "{v}":
            d["label"] = self.label
        if tuple(self.p0) != (0.0, 0.0, 0.0):
            d["p0"] = list(self.p0)
        if tuple(self.p1) != (0.0, 0.0, 0.0):
            d["p1"] = list(self.p1)
        return d


#: Camera projections a view (and, later, a drawing sheet) may request.
_PROJECTIONS = ("iso", "top", "front")


@dataclass(frozen=True)
class Camera:
    """A view's camera hint: a projection + whether to frame the view's own
    scope (the default). ``projection`` is one of :data:`_PROJECTIONS`; the same
    strings the PNG pipeline's ``VIEWS`` accepts, so a view drives the existing
    renderer unchanged. ``zoom_to_scope`` is the drawing-sheet seam: a sheet is a
    view whose camera additionally fixes a scale/paper frame."""

    projection: str = "iso"
    zoom_to_scope: bool = True

    def to_dict(self):
        if self.zoom_to_scope:
            return self.projection
        return {"projection": self.projection, "zoom_to_scope": False}


@dataclass(frozen=True)
class ViewSpec:
    """A named view of the site model: a set of scope selectors (unioned), an
    optional camera, and optional view-local callouts. Pure declaration — the
    runtime :class:`View` binds it to a compiled site."""

    name: str
    include: tuple = ()
    camera: Camera = field(default_factory=Camera)
    callouts: tuple = ()

    def to_dict(self) -> dict:
        d = {"name": self.name,
             "include": [s.to_dict() for s in self.include],
             "camera": self.camera.to_dict()}
        if self.callouts:
            d["callouts"] = [c.to_dict() for c in self.callouts]
        return d


# --------------------------------------------------------------------------- #
# Loader — strict, same _take / did-you-mean culture as the rest of src/spec.
# --------------------------------------------------------------------------- #
def build_views(raw) -> tuple:
    """Parse a site document's ``views:`` block (a list) into a tuple of
    :class:`ViewSpec`. Strict keys, did-you-mean, teaching errors — the same
    culture as the site loader. Round-trips: ``build_views(dump_views(v)) == v``
    (tested)."""
    views = tuple(_build_view(v, i)
                  for i, v in enumerate(_as_list(raw, "views")))
    names = Counter(v.name for v in views)
    dupes = sorted(n for n, c in names.items() if c > 1)
    if dupes:
        raise SpecSchemaError(
            f"views: duplicate view name(s) {dupes}; a view name is its handle "
            f"(SiteDetail.view(name)) and must be unique")
    return views


def dump_views(views) -> list:
    """Serialize views back to the document form (round-trip with
    :func:`build_views`)."""
    return [v.to_dict() for v in views]


def _build_view(raw: dict, index: int) -> ViewSpec:
    ctx = f"views[{index}]"
    if not isinstance(raw, dict):
        raise SpecSchemaError(
            f"{ctx}: each view is a mapping with 'name' and 'include', got "
            f"{type(raw).__name__}")
    f = _take(raw, {"name": True, "include": True,
                    "camera": False, "callouts": False}, ctx)
    name = f["name"]
    if not isinstance(name, str) or not name:
        raise SpecSchemaError(f"{ctx}: 'name' must be a non-empty string")
    include = tuple(_build_selector(s, f"{ctx} ({name!r}) include", i)
                    for i, s in enumerate(_as_list(f["include"], f"{ctx} include")))
    if not include:
        raise SpecSchemaError(
            f"{ctx} ({name!r}): 'include' must list at least one scope selector")
    camera = (Camera() if f["camera"] is _MISSING
              else _build_camera(f["camera"], f"{ctx} ({name!r}) camera"))
    callouts = (() if f["callouts"] is _MISSING else tuple(
        _build_view_callout(c, f"{ctx} ({name!r}) callouts", i)
        for i, c in enumerate(_as_list(f["callouts"], f"{ctx} callouts"))))
    return ViewSpec(name=name, include=include, camera=camera, callouts=callouts)


def _build_selector(raw, ctx: str, index: int) -> Selector:
    if not isinstance(raw, dict) or len(raw) != 1:
        raise SpecSchemaError(
            f"{ctx}[{index}]: a scope selector is a single-key mapping, one of "
            f"{list(_SELECTOR_KINDS)} -> pattern, got {raw!r}")
    (kind, pattern), = raw.items()
    if kind not in _SELECTOR_KINDS:
        hint = difflib.get_close_matches(str(kind), _SELECTOR_KINDS, n=1)
        tip = f" — did you mean {hint[0]!r}?" if hint else ""
        raise SpecSchemaError(
            f"{ctx}[{index}]: unknown selector kind {kind!r}{tip}; a selector is "
            f"one of {list(_SELECTOR_KINDS)}")
    if not isinstance(pattern, str) or not pattern:
        raise SpecSchemaError(
            f"{ctx}[{index}]: selector {kind!r} pattern must be a non-empty string")
    return Selector(kind=kind, pattern=pattern)


def _build_camera(raw, ctx: str) -> Camera:
    if isinstance(raw, str):
        projection, zoom = raw, True
    elif isinstance(raw, dict):
        f = _take(raw, {"projection": True, "zoom_to_scope": False}, ctx)
        projection = f["projection"]
        zoom = True if f["zoom_to_scope"] is _MISSING else bool(f["zoom_to_scope"])
    else:
        raise SpecSchemaError(
            f"{ctx}: camera is a projection string {list(_PROJECTIONS)} or a "
            f"mapping {{projection, zoom_to_scope}}, got {type(raw).__name__}")
    if projection not in _PROJECTIONS:
        hint = difflib.get_close_matches(str(projection), _PROJECTIONS, n=1)
        tip = f" — did you mean {hint[0]!r}?" if hint else ""
        raise SpecSchemaError(
            f"{ctx}: unknown projection {projection!r}{tip}; one of "
            f"{list(_PROJECTIONS)}")
    return Camera(projection=projection, zoom_to_scope=zoom)


def _build_view_callout(raw, ctx: str, index: int) -> ViewCallout:
    if not isinstance(raw, dict):
        raise SpecSchemaError(f"{ctx}[{index}]: a callout is a mapping")
    f = _take(raw, {"param": True, "label": False, "p0": False, "p1": False},
              f"{ctx}[{index}]")
    param = f["param"]
    if not isinstance(param, str) or "." not in param:
        raise SpecSchemaError(
            f"{ctx}[{index}]: callout 'param' is a qualified site value "
            f"'<subsystem>.<name>', got {param!r}")

    def _pt(v, key):
        if v is _MISSING:
            return (0.0, 0.0, 0.0)
        if not isinstance(v, (list, tuple)) or len(v) != 3:
            raise SpecSchemaError(
                f"{ctx}[{index}]: callout {key!r} is a 3-list [x, y, z] (mm)")
        return tuple(float(x) for x in v)

    return ViewCallout(param=param, label=_default(f["label"], "{v}"),
                       p0=_pt(f["p0"], "p0"), p1=_pt(f["p1"], "p1"))


# --------------------------------------------------------------------------- #
# Runtime — a view bound to a compiled SiteDetail.
# --------------------------------------------------------------------------- #
#: The honest framing every view findings-slice carries (wording rule: never
#: "safe"). Validation is site-level; a slice is a presentation, not a verdict.
FINDINGS_NOTE = (
    "Validation ran on the WHOLE site, not on this view. These are the site "
    "findings whose subjects fall in this view's scope; the absence of a FAIL "
    "in this slice is NOT a view-local clean bill — the site verdict governs, "
    "and the site render gate blocks every view while any site finding fails."
)


class View:
    """A named view bound to a compiled :class:`~detailgen.spec.site.SiteDetail`.

    Everything a view exposes is a SLICE or a verbatim pass-through of the one
    model — resolved parts, the site findings touching the scope, the in-scope
    BOM, the (site-level, not re-derived) coverage matrix, resolved callouts and
    camera. It never runs a validation of its own."""

    def __init__(self, spec: ViewSpec, site):
        self.spec = spec
        self.site = site
        self._part_ids = None

    @property
    def name(self) -> str:
        return self.spec.name

    # -- scope resolution -----------------------------------------------------

    def part_ids(self) -> list[str]:
        """Qualified ids in scope, in the site's build order. Each selector must
        match at least one part (zero-match = loud error)."""
        if self._part_ids is None:
            self.site.build()
            by_id = self.site._by_id
            # build-order: iterate the site's own qid order (PASS-1 insertion),
            # then any retired qids (binds/dedups) that also match.
            all_qids = list(dict.fromkeys(by_id))
            selected: dict[str, None] = {}
            for sel in self.spec.include:
                hits = [qid for qid in all_qids
                        if sel.matches(qid, by_id[qid].name)]
                if not hits:
                    raise SpecSchemaError(
                        f"view {self.spec.name!r}: selector {sel.to_dict()} "
                        f"matches ZERO parts in the site model — a scope "
                        f"selector that selects nothing is a fake view. Known "
                        f"subsystems: "
                        f"{sorted({q.split('/', 1)[0] for q in all_qids})}")
                for qid in hits:
                    selected[qid] = None
            self._part_ids = list(selected)
        return list(self._part_ids)

    def parts(self) -> list:
        """The resolved :class:`Placed` handles in scope — deduplicated by
        identity (a shared member reached via two qualified ids is ONE part
        here, once), in build order."""
        qids = self.part_ids()  # triggers site.build() (which (re)binds _by_id)
        by_id = self.site._by_id  # read AFTER the build, never before
        seen: dict[int, object] = {}
        for qid in qids:
            p = by_id[qid]
            seen.setdefault(id(p), p)
        return list(seen.values())

    def _scoped_part_id_set(self) -> set:
        return {p.id for p in self.parts()}

    # -- findings slice (site-level verdict; presented, never re-proved) ------

    def findings(self) -> list:
        """The site findings whose subjects intersect this view's scope. The
        site is validated once (whole model); this filters, it does not re-run.
        A finding whose subjects span two views appears in BOTH (the shared
        member is one node) — that is the point."""
        report = self.site.report
        if report is None:
            report = self.site.validate()
        name_to_id = _name_to_id(self.site.assembly)
        scope = self._scoped_part_id_set()
        out = []
        for f in report.findings:
            ids = _subject_part_ids(f.subject, name_to_id)
            if any(i in scope for i in ids):
                out.append(f)
        return out

    def findings_note(self) -> str:
        return FINDINGS_NOTE

    # -- BOM slice ------------------------------------------------------------

    def bom_table(self) -> list:
        """The aggregated BOM of the in-scope parts — the site BOM restricted to
        this view (site BOM minus out-of-scope). Computed with the SAME
        aggregation the assembly uses, over this view's parts."""
        from ..assemblies.assembly import DetailAssembly
        scoped = DetailAssembly(f"view:{self.spec.name}")
        scoped.parts = self.parts()
        return scoped.bom_table()

    # -- coverage: site-level, NOT re-derived ---------------------------------

    def site_coverage(self) -> list:
        """The SITE coverage matrix, verbatim — a view presents the site's
        verdict, it does not re-derive a view-local one (a view can't prove a
        family the site didn't)."""
        return self.site.coverage_matrix()

    # -- callouts + camera ----------------------------------------------------

    def callouts(self) -> list:
        """View-local callouts resolved against the LIVE site namespace —
        overlay/manifest ready, text tracking the model's current values."""
        ns = self.site._site_ns
        return [c.render(ns) for c in self.spec.callouts]

    def camera(self) -> dict:
        return {"projection": self.spec.camera.projection,
                "zoom_to_scope": self.spec.camera.zoom_to_scope}

    # -- render (SITE-level gate) ---------------------------------------------

    def render(self, out_dir) -> Path:
        """Render this view's scoped subset via the existing PNG pipeline —
        GATED at the SITE level. ``require_clean`` runs on the WHOLE site first,
        so a view renders ONLY when the entire model is clean; a scoped subset
        that looks clean cannot be exported while a contradiction is open
        anywhere in the site. Returns the PNG path."""
        self.site.require_clean()  # SITE-level gate — raises on ANY site failure
        from ..rendering.export import export_png
        from ..assemblies.assembly import DetailAssembly
        scoped = DetailAssembly(f"view:{self.spec.name}")
        scoped.parts = self.parts()
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        cam = self.spec.camera.projection
        path = out / f"{_slug(self.spec.name)}_{cam}.png"
        return export_png(scoped, path, view=cam)


# --------------------------------------------------------------------------- #
# View-layer entry points (SiteDetail delegates its thin accessors here).
# --------------------------------------------------------------------------- #
def views_of(site) -> list:
    """All views declared on a site's document, bound to the compiled site."""
    return [View(spec, site) for spec in site.doc.views]


def view_of(site, name: str) -> View:
    """One named view, with did-you-mean on a miss."""
    for spec in site.doc.views:
        if spec.name == name:
            return View(spec, site)
    known = [s.name for s in site.doc.views]
    hint = difflib.get_close_matches(name, known, n=3)
    tip = f" — did you mean one of {hint}?" if hint else ""
    raise KeyError(f"no view {name!r} in the site document{tip}; views: {known}")


def views_including(site, part_ref: str) -> list[str]:
    """The reverse query — "where else does this part appear?": the names of
    the views whose scope contains the part ``part_ref`` (a qualified id, or a
    retired stub/deduped id that resolves to a shared real member). Membership
    is by PART IDENTITY, so a shared member found through any of its qualified
    ids answers with every view that scopes it.

    This is the Evidence/Inspector seam: the Inspector's "where else does this
    appear?" panel calls exactly this over the view layer (it is NOT wired into
    :mod:`detailgen.validation.evidence` here — the evidence graph stays a
    per-model artifact; this is the view-level index the Inspector consults
    alongside it). See the SM2 report's Inspector-seam note."""
    site.build()
    by_id = site._by_id
    if part_ref not in by_id:
        known = sorted(by_id)
        hint = difflib.get_close_matches(part_ref, known, n=3)
        tip = f" — did you mean one of {hint}?" if hint else ""
        raise KeyError(
            f"no part {part_ref!r} in the site model{tip}; a part reference is "
            f"a qualified id '<subsystem>/<component>'")
    target = by_id[part_ref]
    out = []
    for spec in site.doc.views:
        v = View(spec, site)
        if any(p is target for p in v.parts()):
            out.append(spec.name)
    return out


# --------------------------------------------------------------------------- #
# Helpers — finding-subject resolution (a small, self-contained restatement of
# the evidence graph's subject parser; kept here so the view layer does not
# reach into another module's private helpers).
# --------------------------------------------------------------------------- #
def _name_to_id(assembly) -> dict:
    """``display name -> Placed.id`` for UNAMBIGUOUS names only (a duplicated
    name maps to ``None`` — silence over a wrong guess). Every site part name is
    namespaced and unique, so this is total in practice."""
    counts = Counter(p.name for p in assembly.parts)
    return {p.name: (p.id if counts[p.name] == 1 else None)
            for p in assembly.parts}


#: The separators the validation checks place BETWEEN part names in a finding
#: subject. Audited against every ``Finding(...)`` construction in
#: ``src/validation/{checks,spatial,loadpath}.py`` and
#: ``src/assemblies/connection.py`` (rev-sm2 required the ``through`` shape; the
#: audit adds the rest so no emitted shape is silently dropped):
#:   ``A <-> B``              interference / contact / bearing / symmetric_about
#:   ``A through B``          through_hole
#:   ``A -> B``               load_path (``load_class: A -> B``)
#:   ``A, B, C``              floating (comma-joined names)
#: (`` <-> `` is listed first so it is never mis-split on its inner ``->``.)
_SUBJECT_SEPS = re.compile(r" <-> | through | -> |, ")

#: Trailing prose CLAUSES that qualify a subject but are not themselves part
#: names — ``symmetric_about`` appends ``about <plane>`` and ``faces_*`` appends
#: ``faces toward/away <target-desc>``. Stripped so the leading part name
#: resolves; the prose target never spuriously matches a part.
_SUBJECT_CLAUSE = re.compile(r" (?:about|faces toward|faces away) .*$")


def _subject_part_ids(subject: str, name_to_id: dict) -> list[str]:
    """The ``Placed.id``s a finding subject names, resolved from the STRUCTURED
    subject shapes the checks emit (see :data:`_SUBJECT_SEPS` /
    :data:`_SUBJECT_CLAUSE`). A subject that names no resolvable part (e.g. the
    dimension check's prose ``leg held 1/2" above rock``) yields no ids — it
    then falls in no view's slice (silence over a guess: P1), while remaining in
    the site report and the consolidated divergence list.

    NOTE: this deliberately covers MORE shapes than
    ``validation.evidence._subject_part_ids`` (which parses only ``<->`` /
    ``: ``) — the findings slice is an honesty surface this phase protects, so it
    must not drop a failure that names an in-scope part (rev-sm2 Attack B: the
    two ``through_hole`` failures). Keep the two in sync as new check shapes
    appear (e.g. re-verify SM3b's tree divergence subjects land here)."""
    # A leading ``<label>: `` prefix (connection_hardware, load_path) is not a
    # part; the parts follow it. Split once on the FIRST ": " and parse the tail.
    remainder = subject.split(": ", 1)[1] if ": " in subject else subject
    ids = []
    for token in _SUBJECT_SEPS.split(remainder):
        name = _SUBJECT_CLAUSE.sub("", token).strip()
        pid = name_to_id.get(name)
        if pid:
            ids.append(pid)
    return ids


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
