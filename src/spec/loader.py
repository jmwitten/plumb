"""Load a DetailSpec from YAML or JSON into the typed :mod:`schema` model.

YAML is the authoring surface (comments + diffability are why); JSON is the
same structure and loads through the same path, so a spec round-trips through
either. Only a SAFE loader is used (``yaml.safe_load`` — no arbitrary object
construction from the document).

This layer is purely structural: it turns text into nested ``dict``/``list``
and then into frozen schema dataclasses, enforcing the strict key rules
(:func:`~detailgen.spec.schema._take`). It resolves NOTHING numeric — the
value language (params, ``$``/``=`` directives) and vocabulary (component /
connection type names) are the compiler's job, so a spec can be loaded and
structurally validated without CadQuery or the registries.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path

import yaml

from .schema import (
    RENDERABLE_CHECK_KINDS,
    RESERVED_SPATIAL_NAMES,
    AuthoredStage,
    BearingSpec,
    BomTableSection,
    BondSpec,
    CalloutSpec,
    ComponentSpec,
    ConnectionSpec,
    ContactSpec,
    CrossCheckSpec,
    DeclaredCantilever,
    DerivationLogSection,
    DetailSpecDoc,
    DimensionSpec,
    DocSpec,
    ExpectSpec,
    EXPECT_CHECKS,
    ExplodeSpec,
    ExportSpec,
    FacesSpec,
    FeatureSpec,
    FEATURE_KINDS,
    FindingsSection,
    FoundationSpec,
    InstallSpec,
    INSTALL_EXIT_CONDITIONS,
    INSTALL_HEAD_CONDITIONS,
    PostBaseSpec,
    HardwarePresenceSection,
    MateSpec,
    MountSpec,
    MOUNT_AXES,
    MOUNT_FACE_ALIASES,
    OverlapSpec,
    ProseSection,
    RawSpec,
    RepeatSpec,
    RetireSpec,
    RETIRE_KINDS,
    SequenceSpec,
    SpatialSpec,
    SUPPORT_EDGES,
    SpecSchemaError,
    SymmetricSpec,
    ThroughHoleSpec,
    ValidationSpec,
    WalkingSurfaceScheme,
    _MISSING,
    _take,
    reserved_spatial_error,
)


def load_spec_text(text: str, *, fmt: str = "yaml") -> DetailSpecDoc:
    """Parse spec ``text`` (``fmt`` = ``"yaml"`` or ``"json"``) into a
    :class:`DetailSpecDoc`. JSON is parsed as YAML's superset by default; pass
    ``fmt="json"`` to force the stdlib JSON parser (used by the round-trip
    identity test to prove the two surfaces are equivalent)."""
    if fmt == "json":
        raw = json.loads(text)
    else:
        raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise SpecSchemaError(
            f"a DetailSpec document must be a mapping at top level, got "
            f"{type(raw).__name__}"
        )
    return _build_doc(raw)


def load_spec_file(path: str | Path) -> DetailSpecDoc:
    """Load a spec from a file; ``.json`` uses the JSON parser, anything else
    (``.yaml``/``.yml``) the YAML parser."""
    path = Path(path)
    fmt = "json" if path.suffix.lower() == ".json" else "yaml"
    return load_spec_text(path.read_text(), fmt=fmt)


def _build_doc(raw: dict) -> DetailSpecDoc:
    f = _take(raw, {
        "name": True, "type": False, "units": False,
        "params": False, "derived": False,
        "components": True, "connections": False, "validation": False,
        "spatial": False,
        "roles": False,  # ONTOLOGY (task ONTOLOGY): load-system role declarations
        "foundations": False,  # FAB-3 (retire R29): foundation systems
        "retire": False,  # CL-3 (retro R10): intentional removals with provenance
        "sequence": False,  # SEQSCHEMA: the authored sequence: block
        # -- presentation surfaces (task 4B-2) ---------------------------------
        "callouts": False, "explode": False, "doc": False,
        "cross_check": False, "export": False,
    }, "detail spec")
    components = _build_entries(_as_list(f["components"], "components"),
                                _build_component, "components")
    connections = ([] if f["connections"] is _MISSING
                   else _build_entries(_as_list(f["connections"], "connections"),
                                       _build_connection, "connections"))
    validation = (ValidationSpec() if f["validation"] is _MISSING
                  else _build_validation(f["validation"]))
    spatial = (SpatialSpec() if f["spatial"] is _MISSING
               else _build_spatial(f["spatial"]))
    roles, support_schemes, context_grounds = (
        ({}, {}, frozenset()) if f["roles"] is _MISSING
        else _build_roles(f["roles"]))
    foundations = (() if f["foundations"] is _MISSING
                   else tuple(_build_foundation(fd, i) for i, fd
                              in enumerate(_as_list(f["foundations"], "foundations"))))
    retire = (() if f["retire"] is _MISSING
              else tuple(_build_retire(r, i) for i, r
                         in enumerate(_as_list(f["retire"], "retire"))))
    sequence = (SequenceSpec() if f["sequence"] is _MISSING
                else _build_sequence(f["sequence"]))
    callouts = (() if f["callouts"] is _MISSING
                else tuple(_build_callout(c, i)
                           for i, c in enumerate(_as_list(f["callouts"], "callouts"))))
    explode = (() if f["explode"] is _MISSING
               else tuple(_build_explode(e, i)
                          for i, e in enumerate(_as_list(f["explode"], "explode"))))
    doc = DocSpec() if f["doc"] is _MISSING else _build_doc_block(f["doc"])
    cross_check = (None if f["cross_check"] is _MISSING
                   else _build_cross_check(f["cross_check"]))
    export = None if f["export"] is _MISSING else _build_export(f["export"])
    return DetailSpecDoc(
        name=f["name"],
        type=_default(f["type"], "detail"),
        units=_default(f["units"], "in"),
        units_defaulted=f["units"] is _MISSING,
        params=dict(_default(f["params"], {})),
        derived=dict(_default(f["derived"], {})),
        components=components,
        connections=connections,
        validation=validation,
        spatial=spatial,
        roles=roles,
        support_schemes=support_schemes,
        foundations=foundations,
        retire=retire,
        sequence=sequence,
        context_grounds=context_grounds,
        callouts=callouts,
        explode=explode,
        doc=doc,
        cross_check=cross_check,
        export=export,
    )


# -- presentation surfaces (task 4B-2) ---------------------------------------


def _build_callout(raw: dict, index: int) -> CalloutSpec:
    ctx = f"callouts[{index}]"
    f = _take(raw, {"param": True, "label": False, "p0": True, "p1": True}, ctx)
    return CalloutSpec(
        param=str(f["param"]), label=str(_default(f["label"], "{v}")),
        p0=_point3(f["p0"], f"{ctx} p0"), p1=_point3(f["p1"], f"{ctx} p1"))


def _point3(value, ctx: str) -> tuple:
    """A callout/explode endpoint: a 3-element ``[x, y, z]`` list of
    value-language coordinates (numbers or ``$``/``=``/unit directives — the
    compiler resolves them). Structural only here: shape and length."""
    if not (isinstance(value, (list, tuple)) and len(value) == 3):
        raise SpecSchemaError(f"{ctx}: expected a 3-element [x, y, z], got {value!r}")
    return tuple(value)


def _build_explode(raw: dict, index: int) -> ExplodeSpec:
    ctx = f"explode[{index}]"
    f = _take(raw, {"id": True, "vector": True}, ctx)
    return ExplodeSpec(id=str(f["id"]), vector=_point3(f["vector"], f"{ctx} vector"))


def _build_cross_check(raw: dict) -> CrossCheckSpec:
    f = _take(raw, {"ref": True}, "cross_check")
    ref = f["ref"]
    if not isinstance(ref, str):
        raise SpecSchemaError(
            f"cross_check: 'ref' must be a dotted-path string to a callable "
            f"f(detail) -> dict (the escape-hatch reference), got {ref!r}")
    return CrossCheckSpec(ref=ref)


def _build_export(raw: dict) -> ExportSpec:
    f = _take(raw, {"glb_tolerance": True, "glb_angular_tolerance": True,
                    "inject_explode": False, "explode_authoring_units": False},
              "export")
    return ExportSpec(
        glb_tolerance=float(f["glb_tolerance"]),
        glb_angular_tolerance=float(f["glb_angular_tolerance"]),
        inject_explode=bool(_default(f["inject_explode"], False)),
        explode_authoring_units=bool(_default(f["explode_authoring_units"], False)))


#: The doc-section kinds, each a single-key mapping (the key names the kind —
#: the same one-key dispatch a ``repeat:`` block uses). Named here so an unknown
#: kind is a teaching diagnostic listing the valid kinds.
_DOC_SECTION_BUILDERS = {}  # filled below (after the builder defs)


def _build_doc_block(raw: dict) -> DocSpec:
    f = _take(raw, {"report": False, "sections": False}, "doc")
    sections = tuple(_build_doc_section(s, i)
                     for i, s in enumerate(_as_list(_default(f["sections"], []), "doc.sections")))
    return DocSpec(report=str(_default(f["report"], "validation_report.md")),
                   sections=sections)


def _build_doc_section(raw, index: int):
    ctx = f"doc.sections[{index}]"
    if not isinstance(raw, dict) or len(raw) != 1:
        raise SpecSchemaError(
            f"{ctx}: each section is a single-key mapping naming its kind "
            f"({sorted(_DOC_SECTION_BUILDERS)}), got {raw!r}")
    kind = next(iter(raw))
    if kind not in _DOC_SECTION_BUILDERS:
        hint = difflib.get_close_matches(str(kind), sorted(_DOC_SECTION_BUILDERS), n=3)
        tip = f" — did you mean one of {hint}?" if hint else ""
        raise SpecSchemaError(
            f"{ctx}: unknown section kind {kind!r}; valid kinds: "
            f"{sorted(_DOC_SECTION_BUILDERS)}{tip}")
    return _DOC_SECTION_BUILDERS[kind](raw[kind], ctx)


def _build_prose(raw, ctx: str) -> ProseSection:
    if not isinstance(raw, str):
        raise SpecSchemaError(
            f"{ctx} prose: expected a string of report text, got "
            f"{type(raw).__name__}")
    return ProseSection(text=raw)


def _build_findings_section(raw, ctx: str) -> FindingsSection:
    f = _take(raw, {"header": True, "check": True}, f"{ctx} findings")
    check = str(f["check"])
    if check not in RENDERABLE_CHECK_KINDS:
        hint = difflib.get_close_matches(check, sorted(RENDERABLE_CHECK_KINDS), n=3)
        tip = f" — did you mean one of {hint}?" if hint else ""
        raise SpecSchemaError(
            f"{ctx} findings: unknown check kind {check!r} — a findings section "
            f"renders findings of ONE kind, so an unknown name would silently "
            f"render an empty section. Known kinds: "
            f"{sorted(RENDERABLE_CHECK_KINDS)}{tip}")
    return FindingsSection(header=str(f["header"]), check=check)


def _build_derivation_log(raw, ctx: str) -> DerivationLogSection:
    f = _take(raw, {"header": True, "preamble": False, "mode": False,
                    "cap": False}, f"{ctx} derivation_log")
    mode = str(_default(f["mode"], "first_n"))
    if mode not in ("first_n", "per_connection"):
        raise SpecSchemaError(
            f"{ctx} derivation_log: 'mode' must be 'first_n' or "
            f"'per_connection', got {mode!r}")
    return DerivationLogSection(
        header=str(f["header"]), preamble=str(_default(f["preamble"], "")),
        mode=mode, cap=int(_default(f["cap"], 8)))


def _build_hardware_presence(raw, ctx: str) -> HardwarePresenceSection:
    f = _take(raw, {"header": True, "cap": False}, f"{ctx} hardware_presence")
    return HardwarePresenceSection(header=str(f["header"]), cap=int(_default(f["cap"], 2)))


def _build_bom_table(raw, ctx: str) -> BomTableSection:
    f = _take(raw, {"header": True}, f"{ctx} bom_table")
    return BomTableSection(header=str(f["header"]))


_DOC_SECTION_BUILDERS.update({
    "prose": _build_prose,
    "findings": _build_findings_section,
    "derivation_log": _build_derivation_log,
    "hardware_presence": _build_hardware_presence,
    "bom_table": _build_bom_table,
})


# -- ONTOLOGY (task ONTOLOGY): role declarations -----------------------------


def _build_roles(raw) -> tuple[dict, dict, frozenset]:
    """A ``roles:`` block maps ``component_id -> role``. A role is either a bare
    string (``leg: support``) or a mapping — a ``walking_surface`` support scheme
    (task SUPPORT) or an ``existing`` pre-existing-body entry (task CTXGROUND).
    Returns ``(roles_flat, support_schemes, context_grounds)`` — the flat
    ``id->role_name`` map, the typed :class:`WalkingSurfaceScheme` map (by cid),
    and the set of cids declared ``grounded_by: site`` (self-grounded existing
    bodies, exempt from the floating check). Role VOCABULARY validation stays the
    compiler's job; only structure is checked here."""
    if not isinstance(raw, dict):
        raise SpecSchemaError(
            f"roles: expected a mapping of component_id -> role, got "
            f"{type(raw).__name__}")
    roles: dict = {}
    schemes: dict = {}
    context_grounds: set = set()
    for cid, role in raw.items():
        if not isinstance(cid, str):
            raise SpecSchemaError(
                f"roles: each key must be a component_id string, got {cid!r}")
        if isinstance(role, str):
            roles[cid] = role
        elif isinstance(role, dict):
            # 'grounded_by' is the self-grounding exemption; it is ONLY legal on
            # an 'existing' site body — a constructed member claiming it is a
            # teaching error (task CTXGROUND req 2).
            if "grounded_by" in role and role.get("role") != "existing":
                raise SpecSchemaError(
                    f"roles[{cid!r}]: 'grounded_by' is only legal for a "
                    f"'role: existing' pre-existing site body; {cid!r} declares "
                    f"role {role.get('role')!r}. A constructed member is grounded "
                    f"by its supports reaching a foundation, not by the site — "
                    f"give it a support scheme / foundation, or declare "
                    f"'role: existing' if it is a self-grounded site feature.")
            r = role.get("role")
            if r == "walking_surface":
                schemes[cid] = _build_walking_surface(cid, role)
                roles[cid] = "walking_surface"
            elif r == "existing":
                roles[cid] = "existing"
                if _build_existing(cid, role):
                    context_grounds.add(cid)
            else:
                raise SpecSchemaError(
                    f"roles[{cid!r}]: a mapping role must declare 'role: "
                    f"walking_surface' or 'role: existing'; got {r!r}")
        else:
            raise SpecSchemaError(
                f"roles: entry {cid!r} must be a role name (string) or a "
                f"scheme mapping, got {type(role).__name__}")
    return roles, schemes, frozenset(context_grounds)


def _build_existing(cid: str, raw: dict) -> bool:
    """Parse a ``role: existing`` entry (task CTXGROUND). Returns True iff it
    declares ``grounded_by: site`` (self-grounded, exempt from the floating
    check). The exemption is EXPLICIT — an ``existing`` role without
    ``grounded_by`` is a pre-existing body that still connects normally."""
    f = _take(raw, {"role": True, "grounded_by": False}, f"roles[{cid!r}]")
    gb = f["grounded_by"]
    if gb is _MISSING:
        return False
    if gb != "site":
        raise SpecSchemaError(
            f"roles[{cid!r}].grounded_by: only 'site' is legal (the earth-side "
            f"ground of a pre-existing body), got {gb!r}")
    return True


def _build_walking_surface(cid: str, raw: dict) -> WalkingSurfaceScheme:
    """Parse a ``walking_surface`` scheme mapping (the only structured role in
    v1). Enforces the "declare a support scheme" obligation as a teaching error
    when none of supports / declared_cantilever / deferred_support is given."""
    f = _take(raw, {
        "role": True, "members": False, "supports": False,
        "declared_cantilever": False, "deferred_support": False, "label": False,
    }, f"roles[{cid!r}]")
    if f["role"] != "walking_surface":
        raise SpecSchemaError(
            f"roles[{cid!r}]: a mapping role must declare 'role: "
            f"walking_surface' (the only structured role); got {f['role']!r}")
    members = (tuple([cid]) if f["members"] is _MISSING
               else tuple(_as_list(f["members"], f"roles[{cid!r}].members")))
    supports = (() if f["supports"] is _MISSING
                else tuple(_as_list(f["supports"], f"roles[{cid!r}].supports")))
    cantilevers = _build_cantilevers(cid, f["declared_cantilever"])
    deferred = "" if f["deferred_support"] is _MISSING else str(f["deferred_support"])
    label = "" if f["label"] is _MISSING else str(f["label"])
    if not supports and not cantilevers and not deferred:
        raise SpecSchemaError(
            f"walking_surface {label or cid!r} has no support scheme: declare "
            f"supports, declared_cantilever, or deferred_support — or the "
            f"detail cannot validate CLEAN")
    return WalkingSurfaceScheme(
        key=cid, members=members, supports=supports,
        declared_cantilever=cantilevers, deferred_support=deferred, label=label)


def _build_cantilevers(cid: str, raw) -> tuple:
    if raw is _MISSING:
        return ()
    out = []
    for i, entry in enumerate(_as_list(raw, f"roles[{cid!r}].declared_cantilever")):
        ctx = f"roles[{cid!r}].declared_cantilever[{i}]"
        f = _take(entry, {"edge": True, "note": False}, ctx)
        edge = f["edge"]
        if edge not in SUPPORT_EDGES:
            raise SpecSchemaError(
                f"{ctx}: edge {edge!r} must be one of {list(SUPPORT_EDGES)}")
        out.append(DeclaredCantilever(
            edge=edge, note="" if f["note"] is _MISSING else str(f["note"])))
    return tuple(out)


# -- retirement (task CL-3, retro R10) ---------------------------------------


def _build_retire(raw: dict, index: int) -> RetireSpec:
    """Parse one ``retire:`` record (CL-3). Exactly one of ``connection`` (a
    connection label) or ``member`` (a component id) names WHAT is retired; a
    ``reason`` records WHY. Naming both, or neither, is a teaching error — a
    retirement must be unambiguous about its target."""
    ctx = f"retire[{index}]"
    if not isinstance(raw, dict):
        raise SpecSchemaError(
            f"{ctx}: expected a mapping (one retirement, e.g. "
            f"{{connection: \"tree lag +Y\", reason: \"...\"}})")
    f = _take(raw, {"connection": False, "member": False, "reason": True}, ctx)
    named = [k for k in RETIRE_KINDS if f[k] is not _MISSING]
    if len(named) != 1:
        raise SpecSchemaError(
            f"{ctx}: name exactly one of {list(RETIRE_KINDS)} to retire "
            f"(a connection by its label, or a member by its id), got "
            f"{'both' if len(named) == 2 else 'neither'}.")
    kind = named[0]
    reason = str(f["reason"]).strip()
    if not reason:
        raise SpecSchemaError(
            f"{ctx}: a retirement must carry a non-empty 'reason' — the audit "
            f"trail (WHY it was removed) is the knowledge silent deletion loses.")
    return RetireSpec(kind=kind, target=str(f[kind]), reason=reason)


# -- sequence (task SEQSCHEMA, stepdoc-cpg-design.md §3.1 family 3) ---------


def _build_sequence(raw: dict) -> SequenceSpec:
    """Load the spec-level ``sequence:`` block into a :class:`SequenceSpec`.
    Structural checks only, exactly what one block can see on its own:

    - stage names unique within the block;
    - no connection/part named by more than one stage (two stages would
      claim contradictory order over the same events).

    Whether a named connection/part actually EXISTS elsewhere in the doc is
    NOT checked here — the loader builds this block in isolation, with no
    view of ``connections:``/``components:`` (same division as
    :func:`_build_retire`, whose target-existence check is likewise deferred
    to the semantic-analysis pass). See
    :func:`~detailgen.spec.semantics.analyze_sequence`.

    Deliberately unsupported v1-core keys — ``after:`` (point constraints),
    ``subassemblies:``/``assembly:`` (§3.4 staging) — are NOT in the known-key
    sets below, so each hits the ordinary unknown-key teaching error; they
    are never special-cased as "not yet supported"."""
    ctx = "sequence"
    f = _take(raw, {"stages": True}, ctx)
    raw_stages = _as_list(f["stages"], f"{ctx}.stages")
    if not raw_stages:
        raise SpecSchemaError(
            f"{ctx}: 'stages' is empty — a sequence: block with no stages "
            f"declares no order over anything; omit the whole block instead."
        )
    stages = tuple(_build_stage(s, i, ctx) for i, s in enumerate(raw_stages))

    seen_names: dict[str, int] = {}
    for i, stage in enumerate(stages):
        if stage.name in seen_names:
            raise SpecSchemaError(
                f"{ctx}: stage name {stage.name!r} is used by both "
                f"stages[{seen_names[stage.name]}] and stages[{i}] — stage "
                f"names must be unique within one sequence: block."
            )
        seen_names[stage.name] = i

    claimed: dict[tuple[str, str], int] = {}  # (kind, name) -> owning stage index
    for i, stage in enumerate(stages):
        for kind, names in (("connection", stage.connections), ("part", stage.parts)):
            for name in names:
                key = (kind, name)
                if key in claimed:
                    prior_i = claimed[key]
                    raise SpecSchemaError(
                        f"{ctx}: {kind} {name!r} is listed in both "
                        f"stages[{prior_i}] ({stages[prior_i].name!r}) and "
                        f"stages[{i}] ({stage.name!r}) — two stages would "
                        f"claim contradictory order over the same "
                        f"{kind}; list it in exactly one stage."
                    )
                claimed[key] = i

    return SequenceSpec(stages=stages)


def _build_stage(raw: dict, index: int, seq_ctx: str) -> AuthoredStage:
    ctx = f"{seq_ctx}.stages[{index}]"
    if not isinstance(raw, dict):
        raise SpecSchemaError(
            f"{ctx}: expected a mapping (one stage, e.g. "
            f"{{name: toe_screws_first, connections: [...], why: \"...\"}})"
        )
    f = _take(raw, {
        "name": True, "connections": False, "parts": False, "why": True,
    }, ctx)
    name = str(f["name"]).strip()
    if not name:
        raise SpecSchemaError(
            f"{ctx}: 'name' must be non-empty — stages are referenced by "
            f"name in the uniqueness/conflict diagnostics above."
        )
    why = str(f["why"]).strip()
    if not why:
        raise SpecSchemaError(
            f"{ctx} ({name!r}): 'why' is required and must be non-empty — "
            f"the authored-embedment-override precedent applied to order "
            f"claims: an authored order claim ships with its defense, never "
            f"a bare assertion."
        )
    connections = tuple(str(c) for c in _as_list(
        _default(f["connections"], []), f"{ctx}.connections"))
    parts = tuple(str(p) for p in _as_list(
        _default(f["parts"], []), f"{ctx}.parts"))
    if not connections and not parts:
        raise SpecSchemaError(
            f"{ctx} ({name!r}): a stage must list at least one of "
            f"'connections' or 'parts' — a stage naming nothing claims no "
            f"order over anything."
        )
    return AuthoredStage(name=name, why=why, connections=connections, parts=parts)


# -- foundation systems (task FAB-3, retire R29) -----------------------------


def _build_foundation(raw, index: int) -> FoundationSpec:
    """Parse one ``foundations:`` entry into a :class:`FoundationSpec`. Strict
    keys (unknown -> did-you-mean); ``supports``/``block`` are the required post
    and foundation-body component ids. ``post_base`` is an optional attachment
    sub-mapping; its absence is an explicitly-undesigned foundation (the
    obligation pack FAILs it), never a silent pass."""
    ctx = f"foundations[{index}]"
    f = _take(raw, {
        "label": True, "supports": True, "block": True,
        "post_base": False, "bearing_on_grade": False,
        "frost_depth": False, "type": False,
    }, ctx)
    post_base = (None if f["post_base"] is _MISSING
                 else _build_post_base(f["post_base"], f"{ctx}.post_base"))
    return FoundationSpec(
        label=str(f["label"]),
        supports=str(f["supports"]),
        block=str(f["block"]),
        post_base=post_base,
        bearing_on_grade=("field_verify" if f["bearing_on_grade"] is _MISSING
                          else str(f["bearing_on_grade"])),
        frost_depth=None if f["frost_depth"] is _MISSING else f["frost_depth"],
        type="" if f["type"] is _MISSING else str(f["type"]),
    )


def _build_post_base(raw, ctx: str) -> PostBaseSpec:
    f = _take(raw, {"type": True, "params": False, "uplift": False,
                    "id": False}, ctx)
    return PostBaseSpec(
        type=str(f["type"]),
        params=dict(_default(f["params"], {})),
        uplift="declared" if f["uplift"] is _MISSING else str(f["uplift"]),
        id="" if f["id"] is _MISSING else str(f["id"]))


def _build_entries(raw_list: list, item_builder, ctx: str) -> list:
    """Build a components-or-connections list where any entry may be a
    ``repeat:`` block (a :class:`RepeatSpec`) instead of a leaf. The SAME
    dispatch serves both lists — ``item_builder`` (``_build_component`` or
    ``_build_connection``) makes the leaves; a repeat's body is built with the
    same builder (so bodies may nest)."""
    out = []
    for i, entry in enumerate(raw_list):
        if isinstance(entry, dict) and "repeat" in entry:
            out.append(_build_repeat(entry, i, item_builder, ctx))
        else:
            out.append(item_builder(entry, i))
    return out


def _build_repeat(raw: dict, index: int, item_builder, ctx: str) -> RepeatSpec:
    rc = f"{ctx}[{index}] repeat"
    f = _take(raw, {"repeat": True, "body": True}, rc)
    spec = _take(f["repeat"], {"var": True, "count": True, "start": False},
                 f"{rc} header")
    var = spec["var"]
    if not (isinstance(var, str) and var.isidentifier()):
        raise SpecSchemaError(
            f"{rc}: 'var' must be a valid identifier (the loop index name), "
            f"got {var!r}"
        )
    start = 0 if spec["start"] is _MISSING else spec["start"]
    if not isinstance(start, int) or isinstance(start, bool):
        raise SpecSchemaError(f"{rc}: 'start' must be an integer, got {start!r}")
    body = _build_entries(_as_list(f["body"], f"{rc} body"), item_builder,
                          f"{rc} body")
    return RepeatSpec(var=var, count=spec["count"], body=body, start=start)


def _build_component(raw: dict, index: int) -> ComponentSpec:
    ctx = f"components[{index}]"
    f = _take(raw, {
        "id": True, "type": False, "imperative": False,
        "name": False, "params": False, "place": False,
        "features": False, "was": False,
    }, ctx)
    cid = f["id"]
    was = "" if f["was"] is _MISSING else str(f["was"])
    if was == cid:
        raise SpecSchemaError(
            f"{ctx} ({cid!r}): 'was' must name a DIFFERENT prior-revision id, "
            f"not the member's own current id {cid!r}. A member keeps its "
            f"identity by keeping its id — 'was' is only for a RENAME (the old "
            f"id it used to carry). Drop 'was' if the id did not change."
        )
    has_type = f["type"] is not _MISSING
    has_imperative = f["imperative"] is not _MISSING
    if has_type == has_imperative:
        raise SpecSchemaError(
            f"{ctx} ({cid!r}): give exactly one of 'type' (a registered "
            f"component) or 'imperative' (a dotted-path escape hatch), not "
            f"{'both' if has_type else 'neither'}"
        )
    name_defaulted = f["name"] is _MISSING
    name = cid if name_defaulted else f["name"]
    place = None if f["place"] is _MISSING else _build_placement(f["place"], f"{ctx} ({cid!r}) place")
    features = tuple(
        _build_feature(feat, f"{ctx} ({cid!r}) features[{i}]")
        for i, feat in enumerate(_as_list(_default(f["features"], []),
                                          f"{ctx} ({cid!r}) features")))
    return ComponentSpec(
        id=cid,
        type=_default(f["type"], ""),
        imperative=_default(f["imperative"], ""),
        name=name,
        params=dict(_default(f["params"], {})),
        place=place, features=features, name_defaulted=name_defaulted, was=was,
    )


def _build_feature(raw: dict, ctx: str) -> FeatureSpec:
    """Load one FEATURE (CL-2) with strict, teaching diagnostics. A feature is a
    single-key mapping whose key is the kind (``clearance_cut`` / ``bore`` /
    ``drill``) and whose value carries that kind's parameters — the same
    single-key shape ``place:`` uses for ``raw``/``mount``, so a kind typo names
    the valid set instead of silently loading a wrong feature."""
    if not isinstance(raw, dict):
        raise SpecSchemaError(
            f"{ctx}: expected a mapping (one feature, e.g. "
            f"{{clearance_cut: {{around: trunk, gap: $gap}}}})")
    kinds = [k for k in raw if k in FEATURE_KINDS]
    if len(kinds) != 1:
        raise SpecSchemaError(
            f"{ctx}: a feature is exactly one of {list(FEATURE_KINDS)} mapped to "
            f"its parameters; got keys {sorted(raw)}. A clearance_cut fits a part "
            f"around a member; a bore is a designed recess. (drill is deferred — "
            f"see FEATURE_KINDS.)")
    kind = kinds[0]
    body = raw[kind]
    if not isinstance(body, dict):
        raise SpecSchemaError(f"{ctx} ({kind}): expected a mapping of parameters")
    if kind == "clearance_cut":
        b = _take(body, {"around": True, "gap": True, "id": False, "name": False}, f"{ctx} clearance_cut")
        return FeatureSpec(kind=kind, around=str(b["around"]), gap=b["gap"],
                           id=_default(b["id"], ""), name=_default(b["name"], ""))
    # bore
    b = _take(body, {"dia": True, "at": False, "depth": False,
                     "id": False, "name": False}, f"{ctx} bore")
    at = () if b["at"] is _MISSING else tuple(b["at"])
    return FeatureSpec(kind=kind, dia=b["dia"], at=at,
                       depth=(None if b["depth"] is _MISSING else b["depth"]),
                       id=_default(b["id"], ""), name=_default(b["name"], ""))


def _build_placement(raw: dict, ctx: str):
    if not isinstance(raw, dict):
        raise SpecSchemaError(f"{ctx}: expected a mapping (a mate or a raw block)")
    # YAML 1.1 parses a bare ``on``/``off``/``yes``/``no`` key as a boolean, so
    # a mate written ``on: boulder`` silently becomes a ``True`` key — the exact
    # footgun the ``to:``/``to_datum:`` naming avoids. Catch it with the fix,
    # not a bare "unknown key True".
    for key in raw:
        if isinstance(key, bool):
            wrote = "on" if key else "off"
            raise SpecSchemaError(
                f"{ctx}: found a boolean key ({key}) — YAML parses a bare "
                f"{wrote!r} key as a boolean. If you meant the mate target, "
                f"write 'to:' (and 'to_datum:'), which is why this spec uses "
                f"those keys instead of 'on:'/'on_datum:'."
            )
    if "raw" in raw:
        if len(raw) != 1:
            raise SpecSchemaError(
                f"{ctx}: a raw placement takes only the 'raw' key, got "
                f"{sorted(raw)} — mate keys (datum/on/...) can't mix with raw"
            )
        rf = _take(raw["raw"], {"at": True, "rotate": False}, f"{ctx} raw")
        return RawSpec(at=tuple(rf["at"]),
                       rotate=_as_rotate(rf["rotate"], f"{ctx} raw"))
    if "mount" in raw:
        if len(raw) != 1:
            raise SpecSchemaError(
                f"{ctx}: a mount placement takes only the 'mount' key, got "
                f"{sorted(raw)} — mount is a relation, not mixable with raw/mate"
            )
        return _build_mount(raw["mount"], f"{ctx} mount")
    f = _take(raw, {
        "datum": True, "to": True, "to_datum": False,
        "offset": False, "rotate": False, "flip": False,
    }, ctx)
    on_datum_defaulted = f["to_datum"] is _MISSING
    return MateSpec(
        datum=f["datum"], on=f["to"],
        on_datum=_default(f["to_datum"], "top"),
        offset=tuple(_default(f["offset"], (0.0, 0.0, 0.0))),
        rotate=_default(f["rotate"], 0.0),
        flip=bool(_default(f["flip"], False)),
        on_datum_defaulted=on_datum_defaulted,
    )


def _build_mount(raw: dict, ctx: str) -> MountSpec:
    """Load a MOUNT relation with strict, teaching diagnostics (CL-1). Every
    knob is checked at load: an unknown axis, a face role the alias table does
    not carry, more than one standoff, or a mirror on an unknown axis each name
    the valid set — a mount typo is never a silently-wrong placement."""
    f = _take(raw, {
        "to": True, "face": True, "axis": True,
        "flush": False, "clear_by": False, "offset": False,
        "center": False, "ground": False,
        "mirror": False,
    }, ctx)
    axis = str(f["axis"]).upper()
    if axis not in MOUNT_AXES:
        raise SpecSchemaError(
            f"{ctx}: axis {f['axis']!r} is not a mount axis; use one of "
            f"{list(MOUNT_AXES)} (the target-frame axis the standoff is "
            f"measured along — the mate normal)")
    face = str(f["face"])
    if face not in MOUNT_FACE_ALIASES:
        raise SpecSchemaError(
            f"{ctx}: face {face!r} is not a mount face role; use one of "
            f"{sorted(MOUNT_FACE_ALIASES)} (the part face turned to seat toward "
            f"the target — its outward normal, from which the rotation derives)")
    # Exactly one standoff: flush | clear_by | offset. This is the along-normal
    # DOF; giving two fights over one axis (an over-constraint the author must
    # resolve), giving none leaves the normal free (under-constrained).
    flush = bool(_default(f["flush"], False))
    clear_by = None if f["clear_by"] is _MISSING else f["clear_by"]
    offset = None if f["offset"] is _MISSING else f["offset"]
    n_standoff = sum(x for x in (flush, clear_by is not None, offset is not None))
    if n_standoff != 1:
        raise SpecSchemaError(
            f"{ctx}: give EXACTLY ONE standoff along axis {axis} — 'flush' "
            f"(faces meet), 'clear_by: <len>' (a gap beyond the target surface), "
            f"or 'offset: <len>' (a signed length from it); got {n_standoff}. "
            f"Two standoffs fight over one axis; none leaves the mate normal "
            f"unpinned.")
    center = tuple(str(a).upper() for a in _as_list(_default(f["center"], []),
                                                     f"{ctx} center"))
    for a in center:
        if a not in MOUNT_AXES:
            raise SpecSchemaError(
                f"{ctx}: center axis {a!r} is not a mount axis; use a subset of "
                f"{list(MOUNT_AXES)}")
    if axis in center:
        raise SpecSchemaError(
            f"{ctx}: axis {axis} is the standoff axis and cannot also be a "
            f"'center' axis — center pins the IN-PLANE position, the standoff "
            f"pins the normal.")
    mirror = "" if f["mirror"] is _MISSING else str(f["mirror"]).upper()
    if mirror and mirror not in MOUNT_AXES:
        raise SpecSchemaError(
            f"{ctx}: mirror {f['mirror']!r} is not a mount axis; use one of "
            f"{list(MOUNT_AXES)} (the plane-normal axis the opposite hand is "
            f"derived across) or omit it")
    # ``ground`` — the R3 grounding relation: register the base against the world
    # grade datum. A standoff to a named datum (like ``clear_by`` to the target
    # surface), NOT a raw Z coordinate — the compiler derives the grounding fact.
    ground = None
    if f["ground"] is not _MISSING:
        gf = _take(f["ground"], {"above": True}, f"{ctx} ground")
        ground = gf["above"]
    return MountSpec(
        to=str(f["to"]), face=face, axis=axis,
        flush=flush, clear_by=clear_by, offset=offset,
        center=center, ground=ground,
        mirror=mirror,
    )


def _build_connection(raw: dict, index: int) -> ConnectionSpec:
    ctx = f"connections[{index}]"
    f = _take(raw, {
        "type": True, "parts": True, "hardware": False, "params": False,
        "surfaces": False, "assumptions": False, "label": False,
        "expect": False, "install": False,
    }, ctx)
    expect = tuple(
        _build_expect(e, f"{ctx} expect[{i}]")
        for i, e in enumerate(_as_list(_default(f["expect"], []), f"{ctx} expect")))
    install = (None if f["install"] is _MISSING
               else _build_install(f["install"], f"{ctx} install"))
    return ConnectionSpec(
        type=f["type"],
        parts=list(_as_list(f["parts"], f"{ctx} parts")),
        hardware=list(_default(f["hardware"], [])),
        params=dict(_default(f["params"], {})),
        surfaces=dict(_default(f["surfaces"], {})),
        assumptions=list(_default(f["assumptions"], [])),
        label=_default(f["label"], ""),
        expect=expect,
        install=install,
    )


def _build_expect(raw: dict, ctx: str) -> ExpectSpec:
    """Load one attached EXPECT (CL-3). A pin names the ``check`` kind it expects
    (a divergence its owning declaration could produce) and a ``reason`` — the
    subject is IMPLIED by the owner, never re-typed, so the pin cannot drift from
    what it pins. An unknown check kind names the valid set instead of silently
    matching nothing."""
    if not isinstance(raw, dict):
        raise SpecSchemaError(
            f"{ctx}: expected a mapping (one expectation, e.g. "
            f"{{check: bearing, reason: \"...\"}})")
    f = _take(raw, {"check": True, "reason": True, "count": False}, ctx)
    check = str(f["check"])
    if check not in EXPECT_CHECKS:
        raise SpecSchemaError(
            f"{ctx}: check {check!r} is not a pinnable divergence kind; a pin "
            f"names one of {list(EXPECT_CHECKS)} — the finding kinds a "
            f"declaration's derived closure (or the shared-member site checks) "
            f"can actually surface. The subject is taken from the owning "
            f"declaration, so it is not written here.")
    reason = str(f["reason"]).strip()
    if not reason:
        raise SpecSchemaError(
            f"{ctx}: an expectation must carry a non-empty 'reason' — a pin "
            f"WITHOUT its justification is exactly the unreviewable divergence "
            f"the pin-accounting report exists to prevent.")
    count = _default(f["count"], 1)
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise SpecSchemaError(
            f"{ctx}: 'count' is how many {check!r} findings this pin owns on the "
            f"joint — a whole number >= 1 (default 1), got {count!r}. One same-kind "
            f"finding beyond 'count' is a NEW divergence, never silently pinned.")
    return ExpectSpec(check=check, reason=reason, count=count)


#: The InstallSpec fields that actually override contract content — ``role``
#: alone targets a group but overrides nothing, so it does not count toward
#: the at-least-one-field rule.
_INSTALL_CONTENT_KEYS = ("method", "entry", "angle", "exit", "exit_faces",
                         "embedment", "head", "tool", "stage")


def _build_install_face(raw, ctx: str) -> tuple:
    """One ``{part, face}`` semantic face reference (an entry face or a
    declared exit face). Both keys required — a face without its member (or
    vice versa) is not a checkable location."""
    f = _take(raw, {"part": True, "face": True}, ctx)
    return (str(f["part"]), str(f["face"]))


def _build_install(raw: dict, ctx: str) -> InstallSpec:
    """Load one attached ``install:`` override (task INSTALL v1). Modeled on
    :func:`_build_expect`: strict keys with did-you-mean, teaching errors
    for closed-vocabulary values (exit/head), and NO value resolution — the
    value-language fields (embedment, tool lengths) stay raw for the
    compiler, so they resolve inside ``repeat:`` bodies like every other
    authored value."""
    if not isinstance(raw, dict):
        raise SpecSchemaError(
            f"{ctx}: expected a mapping (the contract fields to override, "
            f"e.g. {{method: toe_screw, angle: 30}})")
    f = _take(raw, {
        "method": False, "entry": False, "angle": False, "exit": False,
        "exit_faces": False, "embedment": False, "head": False,
        "tool": False, "stage": False, "role": False,
    }, ctx)
    if all(f[k] is _MISSING for k in _INSTALL_CONTENT_KEYS):
        raise SpecSchemaError(
            f"{ctx}: an install: block must override at least one contract "
            f"field ({list(_INSTALL_CONTENT_KEYS)}) — a block naming only "
            f"'role' (or nothing) declares nothing. The ConnectionType's "
            f"default contract already applies without any install: block.")

    entry_part = entry_face = ""
    if f["entry"] is not _MISSING:
        entry_part, entry_face = _build_install_face(f["entry"], f"{ctx} entry")

    angle = None
    if f["angle"] is not _MISSING:
        angle = f["angle"]
        if isinstance(angle, bool) or not isinstance(angle, (int, float)):
            raise SpecSchemaError(
                f"{ctx}: 'angle' is the tool-axis angle off the entry face "
                f"in degrees — a number in [0, 90) (0 = along the shank), "
                f"got {angle!r}")
        if not (0 <= float(angle) < 90):
            raise SpecSchemaError(
                f"{ctx}: angle {angle!r} is outside [0, 90) — it is measured "
                f"off the entry face plane (0 = straight along the shank; 90 "
                f"would lie IN the face, which is not a drivable axis)")

    exit_ = ""
    if f["exit"] is not _MISSING:
        exit_ = str(f["exit"])
        if exit_ not in INSTALL_EXIT_CONDITIONS:
            suggestions = difflib.get_close_matches(
                exit_, INSTALL_EXIT_CONDITIONS, n=2)
            hint = f" — did you mean one of {suggestions}?" if suggestions else ""
            raise SpecSchemaError(
                f"{ctx}: exit {exit_!r} is not an exit condition; use one of "
                f"{list(INSTALL_EXIT_CONDITIONS)}{hint} ('none' = the shank "
                f"terminates inside wood; 'concealed_exit' = exits on the "
                f"DECLARED non-show faces in exit_faces; "
                f"'through_exit_required' = the exit is REQUIRED, as for a "
                f"through-bolt)")

    exit_faces = tuple(
        _build_install_face(e, f"{ctx} exit_faces[{i}]")
        for i, e in enumerate(_as_list(_default(f["exit_faces"], []),
                                       f"{ctx} exit_faces")))
    if exit_faces and exit_ not in ("concealed_exit", "through_exit_required"):
        raise SpecSchemaError(
            f"{ctx}: exit_faces only accompany exit: concealed_exit (the "
            f"declared non-show faces the shank may exit) or exit: "
            f"through_exit_required (the far-side face the exit must reach); "
            f"got exit: {exit_ or '<not overridden>'!r}")
    if exit_ == "concealed_exit" and not exit_faces:
        raise SpecSchemaError(
            f"{ctx}: exit: concealed_exit REQUIRES exit_faces — the declared "
            f"face-set IS the disclosure that makes a concealed exit a design "
            f"fact instead of a silent show-face breach")
    if exit_ == "through_exit_required" and not exit_faces:
        raise SpecSchemaError(
            f"{ctx}: exit: through_exit_required REQUIRES exit_faces — an "
            f"authored exit override REPLACES the type default's whole Exit "
            f"(including its nut-side face-set), and without a declared "
            f"far-side face the required exit is uncheckable (the axis "
            f"checks degrade it to a blocking UNKNOWN); name the face the "
            f"exit must reach")

    head = ""
    if f["head"] is not _MISSING:
        head = str(f["head"])
        if head not in INSTALL_HEAD_CONDITIONS:
            suggestions = difflib.get_close_matches(
                head, INSTALL_HEAD_CONDITIONS, n=2)
            hint = f" — did you mean one of {suggestions}?" if suggestions else ""
            raise SpecSchemaError(
                f"{ctx}: head {head!r} is not a head condition; use one of "
                f"{list(INSTALL_HEAD_CONDITIONS)}{hint}")

    tool_length = tool_dia = None
    if f["tool"] is not _MISSING:
        tf = _take(f["tool"], {"length": True, "dia": True}, f"{ctx} tool")
        tool_length, tool_dia = tf["length"], tf["dia"]

    return InstallSpec(
        method=str(_default(f["method"], "")),
        entry_part=entry_part, entry_face=entry_face,
        angle=angle, exit=exit_, exit_faces=exit_faces,
        embedment=None if f["embedment"] is _MISSING else f["embedment"],
        head=head, tool_length=tool_length, tool_dia=tool_dia,
        stage=str(_default(f["stage"], "")),
        role=str(_default(f["role"], "")),
    )


def _build_validation(raw: dict) -> ValidationSpec:
    f = _take(raw, {
        "ground": False, "through_holes": False, "dimensions": False,
        "bearings": False, "bonds": False,
        "expected_overlaps": False, "contacts": False,
    }, "validation")
    ths = [_build_through_hole(t, i)
           for i, t in enumerate(_default(f["through_holes"], []))]
    dims = [_build_dimension(d, i)
            for i, d in enumerate(_default(f["dimensions"], []))]
    bearings = _build_entries(_default(f["bearings"], []), _build_bearing,
                              "validation.bearings")
    bonds = _build_entries(_default(f["bonds"], []), _build_bond,
                           "validation.bonds")
    overlaps = _build_entries(_default(f["expected_overlaps"], []),
                              _build_overlap, "validation.expected_overlaps")
    contacts = _build_entries(_default(f["contacts"], []), _build_contact,
                              "validation.contacts")
    return ValidationSpec(
        ground=None if f["ground"] is _MISSING else f["ground"],
        through_holes=ths, dimensions=dims, bearings=bearings, bonds=bonds,
        expected_overlaps=overlaps, contacts=contacts,
    )


def _build_bearing(raw: dict, index: int) -> BearingSpec:
    ctx = f"validation.bearings[{index}]"
    f = _take(raw, {"a": True, "b": True, "axis": True, "area": True}, ctx)
    return BearingSpec(a=f["a"], b=f["b"], axis=f["axis"], area=f["area"])


def _build_bond(raw: dict, index: int) -> BondSpec:
    ctx = f"validation.bonds[{index}]"
    f = _take(raw, {"a": True, "b": True}, ctx)
    return BondSpec(a=f["a"], b=f["b"])


def _build_overlap(raw: dict, index: int) -> OverlapSpec:
    ctx = f"validation.expected_overlaps[{index}]"
    f = _take(raw, {"a": True, "b": True}, ctx)
    return OverlapSpec(a=f["a"], b=f["b"])


def _build_contact(raw: dict, index: int) -> ContactSpec:
    ctx = f"validation.contacts[{index}]"
    f = _take(raw, {"a": True, "b": True}, ctx)
    return ContactSpec(a=f["a"], b=f["b"])


def _build_through_hole(raw: dict, index: int) -> ThroughHoleSpec:
    ctx = f"validation.through_holes[{index}]"
    f = _take(raw, {
        "part": True, "passes_through": True, "axis": True, "center": True,
        "r_inner": True, "r_outer": True, "span": True,
    }, ctx)
    return ThroughHoleSpec(
        part=f["part"],
        passes_through=list(_as_list(f["passes_through"], f"{ctx} passes_through")),
        axis=f["axis"], center=list(f["center"]),
        r_inner=f["r_inner"], r_outer=f["r_outer"], span=f["span"],
    )


def _build_dimension(raw: dict, index: int) -> DimensionSpec:
    ctx = f"validation.dimensions[{index}]"
    f = _take(raw, {
        "name": True, "part": True, "measure": True, "expected": True,
        "tolerance": False, "negate": False, "op": False,
        "minus_part": False, "minus_measure": False,
    }, ctx)
    minus_part = None if f["minus_part"] is _MISSING else f["minus_part"]
    minus_measure = None if f["minus_measure"] is _MISSING else f["minus_measure"]
    if (minus_part is None) != (minus_measure is None):
        raise SpecSchemaError(
            f"{ctx}: a cross-part dimension needs BOTH 'minus_part' and "
            f"'minus_measure' (the second member and its bbox measure), or "
            f"neither for a single-part check")
    op = _default(f["op"], "eq")
    if op not in ("eq", "ge", "gt"):
        raise SpecSchemaError(
            f"{ctx}: 'op' must be one of ['eq', 'ge', 'gt'] (a threshold uses "
            f"ge/gt; the default eq is |actual-expected| <= tolerance), got "
            f"{op!r}")
    return DimensionSpec(
        name=f["name"], part=f["part"], measure=f["measure"],
        expected=f["expected"],
        tolerance=None if f["tolerance"] is _MISSING else f["tolerance"],
        negate=bool(_default(f["negate"], False)),
        op=op, minus_part=minus_part, minus_measure=minus_measure,
    )


# -- spatial intent (task SPATIAL) -------------------------------------------


def _build_spatial(raw: dict) -> SpatialSpec:
    if not isinstance(raw, dict):
        raise SpecSchemaError(
            f"spatial: expected a mapping with keys ['symmetric', 'faces'], "
            f"got {type(raw).__name__}"
        )
    # Reserved planned vocabulary: a specific teaching error (what is reserved
    # AND what is currently provable), not a generic unknown-key did-you-mean —
    # and emphatically NOT a parse-and-noop stub (a fake invariant).
    for key in raw:
        if key in RESERVED_SPATIAL_NAMES:
            raise SpecSchemaError(reserved_spatial_error(key))
    f = _take(raw, {"symmetric": False, "faces": False}, "spatial")
    symmetric = tuple(_build_symmetric(s, i)
                      for i, s in enumerate(_default(f["symmetric"], [])))
    faces = tuple(_build_faces(x, i)
                  for i, x in enumerate(_default(f["faces"], [])))
    return SpatialSpec(symmetric=symmetric, faces=faces)


def _build_symmetric(raw: dict, index: int) -> SymmetricSpec:
    ctx = f"spatial.symmetric[{index}]"
    f = _take(raw, {"plane": True, "pairs": False, "mirror": False,
                    "tol": False}, ctx)
    pairs = ()
    if f["pairs"] is not _MISSING:
        pairs = tuple(_pair(p, f"{ctx} pairs") for p in _as_list(f["pairs"],
                                                                  f"{ctx} pairs"))
    mirror = None
    if f["mirror"] is not _MISSING:
        m = _as_list(f["mirror"], f"{ctx} mirror")
        if len(m) != 2:
            raise SpecSchemaError(
                f"{ctx}: 'mirror' must be a [plus, minus] name-substitution "
                f"pair (e.g. ['+Y', '-Y']), got {m!r}")
        mirror = (str(m[0]), str(m[1]))
    if not pairs and mirror is None:
        raise SpecSchemaError(
            f"{ctx}: declare 'pairs' (explicit [[a, b], ...]) and/or a 'mirror' "
            f"name selector ([plus, minus]) — a symmetric invariant with no "
            f"pairs proves nothing")
    return SymmetricSpec(
        plane=str(f["plane"]), pairs=pairs, mirror=mirror,
        tol=None if f["tol"] is _MISSING else f["tol"])


def _pair(raw, ctx: str) -> tuple:
    if not (isinstance(raw, (list, tuple)) and len(raw) == 2):
        raise SpecSchemaError(f"{ctx}: each pair must be an [a, b] id pair, got {raw!r}")
    return (str(raw[0]), str(raw[1]))


def _build_faces(raw: dict, index: int) -> FacesSpec:
    ctx = f"spatial.faces[{index}]"
    f = _take(raw, {
        "part": True, "facing": False, "facing_datum": False,
        "toward": False, "away": False, "toward_dir": False, "away_dir": False,
        "tol": False,
    }, ctx)
    # exactly one facing source.
    has_axis = f["facing"] is not _MISSING
    has_datum = f["facing_datum"] is not _MISSING
    if has_axis == has_datum:
        raise SpecSchemaError(
            f"{ctx}: give exactly one facing source — 'facing' (a world [x,y,z] "
            f"axis) or 'facing_datum' (a body-fixed datum name), not "
            f"{'both' if has_axis else 'neither'}")
    facing = _vec3(f["facing"], f"{ctx} facing") if has_axis else None
    facing_datum = None if has_datum is False else str(f["facing_datum"])
    # exactly one target: toward|away (a part id) or toward_dir|away_dir (a vec).
    target_keys = [k for k in ("toward", "away", "toward_dir", "away_dir")
                   if f[k] is not _MISSING]
    if len(target_keys) != 1:
        raise SpecSchemaError(
            f"{ctx}: give exactly one target — 'toward'/'away' (a part id) or "
            f"'toward_dir'/'away_dir' (a world [x,y,z] direction); got "
            f"{target_keys or 'none'}")
    tk = target_keys[0]
    sense = "toward" if tk.startswith("toward") else "away"
    target = target_dir = None
    if tk in ("toward", "away"):
        target = str(f[tk])
    else:
        target_dir = _vec3(f[tk], f"{ctx} {tk}")
    return FacesSpec(
        part=str(f["part"]), sense=sense, facing=facing,
        facing_datum=facing_datum, target=target, target_dir=target_dir,
        tol=None if f["tol"] is _MISSING else f["tol"])


def _vec3(value, ctx: str) -> tuple:
    if not (isinstance(value, (list, tuple)) and len(value) == 3):
        raise SpecSchemaError(f"{ctx}: expected a 3-element [x, y, z], got {value!r}")
    return tuple(float(c) for c in value)


# -- small helpers -----------------------------------------------------------


def _default(value, fallback):
    return fallback if value is _MISSING else value


def _as_list(value, ctx: str) -> list:
    if not isinstance(value, list):
        raise SpecSchemaError(f"{ctx}: expected a list, got {type(value).__name__}")
    return value


def _as_rotate(value, ctx: str) -> tuple:
    """A raw ``rotate`` is a list of ``[axis, degrees]`` pairs (global-axis
    rotations in order). Normalize to a tuple of ``(str, number)`` tuples."""
    if value is _MISSING or value is None:
        return ()
    if not isinstance(value, list):
        raise SpecSchemaError(
            f"{ctx}: rotate must be a list of [axis, degrees] pairs, got "
            f"{type(value).__name__}"
        )
    out = []
    for i, pair in enumerate(value):
        if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
            raise SpecSchemaError(
                f"{ctx}: rotate[{i}] must be an [axis, degrees] pair, got {pair!r}"
            )
        out.append((str(pair[0]), pair[1]))
    return tuple(out)
