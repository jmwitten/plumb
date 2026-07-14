"""Serialize a :class:`DetailSpecDoc` back to the authoring mapping (and to
YAML/JSON text).

This is the inverse of :mod:`~detailgen.spec.loader`, and the two together are
the "diffable, replayable" guarantee: ``load(dump(doc)) == doc`` for both YAML
and JSON, so a spec a tool generated, edited, or migrated re-serializes to the
same document it loaded from. It emits only *authoring* keys (never the
compiler's derived values or the provenance bookkeeping flags), and re-emits the
``to`` / ``to_datum`` mate keys and the ``raw:`` escape-hatch block exactly as a
human would write them.

Default-valued optional fields (a zero ``offset``, an unset ``flip``, an empty
``connections``) are omitted — reloading re-supplies the same default, so the
round-trip is still identity while the dump stays as small as what was authored.
"""

from __future__ import annotations

import json

import yaml

from .schema import (
    BomTableSection,
    CalloutSpec,
    CrossCheckSpec,
    DerivationLogSection,
    DetailSpecDoc,
    DocSpec,
    ExplodeSpec,
    ExportSpec,
    FacesSpec,
    FindingsSection,
    HardwarePresenceSection,
    MateSpec,
    MountSpec,
    ProseSection,
    RawSpec,
    RepeatSpec,
    SpatialSpec,
    SymmetricSpec,
    ValidationSpec,
)


def spec_to_dict(doc: DetailSpecDoc) -> dict:
    """The authoring mapping for ``doc`` — the exact structure
    :func:`~detailgen.spec.loader.load_spec_text` consumes."""
    out: dict = {"name": doc.name, "type": doc.type, "units": doc.units}
    if doc.params:
        out["params"] = dict(doc.params)
    if doc.derived:
        out["derived"] = dict(doc.derived)
    out["components"] = [_entry_to_dict(c, _component_to_dict) for c in doc.components]
    if doc.connections:
        out["connections"] = [_entry_to_dict(c, _connection_to_dict)
                              for c in doc.connections]
    # ONTOLOGY (task ONTOLOGY) + SUPPORT (task SUPPORT): role declarations. A
    # plain id->role mapping, EXCEPT a walking_surface cid re-emits its typed
    # support scheme mapping (the inverse of loader._build_roles' split) so the
    # single authored ``roles:`` block round-trips exactly. Emitted only when
    # present so a role-free spec round-trips unchanged.
    if doc.roles:
        out["roles"] = {cid: _role_to_authored(cid, role, doc)
                        for cid, role in doc.roles.items()}
    # FAB-3 (retire R29): foundation systems. Emitted only when present so a
    # foundation-free spec round-trips unchanged.
    if doc.foundations:
        out["foundations"] = [_foundation_to_dict(fd) for fd in doc.foundations]
    # CL-3 (retro R10): intentional removals with provenance. Emitted only when
    # present so a retire-free spec round-trips unchanged.
    if doc.retire:
        out["retire"] = [{r.kind: r.target, "reason": r.reason}
                         for r in doc.retire]
    # STEPDOC: authored order + staging claims. Emitted only when present so
    # a sequence-free spec round-trips unchanged. Preserve authoring order:
    # stages, explicit units, whole-detail assembly mode.
    if (doc.sequence.stages or doc.sequence.subassemblies
            or doc.sequence.assembly is not None or doc.sequence.after):
        sequence = {}
        if doc.sequence.stages:
            sequence["stages"] = [_stage_to_dict(st)
                                  for st in doc.sequence.stages]
        if doc.sequence.subassemblies:
            sequence["subassemblies"] = [
                _subassembly_to_dict(u) for u in doc.sequence.subassemblies]
        if doc.sequence.assembly is not None:
            sequence["assembly"] = {
                "mode": doc.sequence.assembly.mode,
                "why": doc.sequence.assembly.why,
            }
        if doc.sequence.after:
            sequence["after"] = [_after_to_dict(a) for a in doc.sequence.after]
        out["sequence"] = sequence
    vd = _validation_to_dict(doc.validation)
    if vd:
        out["validation"] = vd
    sd = _spatial_to_dict(doc.spatial)
    if sd:
        out["spatial"] = sd
    # -- presentation surfaces (task 4B-2): emitted only when present, so a
    # detail without them round-trips exactly as before.
    if doc.callouts:
        out["callouts"] = [_callout_to_dict(c) for c in doc.callouts]
    if doc.explode:
        out["explode"] = [{"id": e.id, "vector": list(e.vector)} for e in doc.explode]
    dd = _doc_to_dict(doc.doc)
    if dd:
        out["doc"] = dd
    if doc.cross_check is not None:
        out["cross_check"] = {"ref": doc.cross_check.ref}
    if doc.export is not None:
        out["export"] = _export_to_dict(doc.export)
    return out


def _foundation_to_dict(fd) -> dict:
    """Re-emit one foundation system — the inverse of ``loader._build_foundation``.
    Optional fields are emitted only when non-default so a minimal foundation
    round-trips minimally."""
    out: dict = {"label": fd.label, "supports": fd.supports, "block": fd.block}
    if fd.post_base is not None:
        pb = fd.post_base
        inner: dict = {"type": pb.type}
        if pb.params:
            inner["params"] = dict(pb.params)
        if pb.uplift != "declared":
            inner["uplift"] = pb.uplift
        if pb.id:
            inner["id"] = pb.id
        out["post_base"] = inner
    if fd.bearing_on_grade != "field_verify":
        out["bearing_on_grade"] = fd.bearing_on_grade
    if fd.frost_depth is not None:
        out["frost_depth"] = fd.frost_depth
    if fd.type:
        out["type"] = fd.type
    return out


def _callout_to_dict(c: CalloutSpec) -> dict:
    d: dict = {"param": c.param}
    if c.label != "{v}":
        d["label"] = c.label
    d["p0"] = list(c.p0)
    d["p1"] = list(c.p1)
    return d


def _export_to_dict(e: ExportSpec) -> dict:
    d: dict = {"glb_tolerance": e.glb_tolerance,
               "glb_angular_tolerance": e.glb_angular_tolerance}
    if e.inject_explode:
        d["inject_explode"] = e.inject_explode
    if e.explode_authoring_units:
        d["explode_authoring_units"] = e.explode_authoring_units
    return d


def _doc_to_dict(doc: DocSpec) -> dict:
    if not doc.sections and doc.report == "validation_report.md":
        return {}
    out: dict = {}
    if doc.report != "validation_report.md":
        out["report"] = doc.report
    out["sections"] = [_doc_section_to_dict(s) for s in doc.sections]
    return out


def _doc_section_to_dict(s) -> dict:
    if isinstance(s, ProseSection):
        return {"prose": s.text}
    if isinstance(s, FindingsSection):
        return {"findings": {"header": s.header, "check": s.check}}
    if isinstance(s, DerivationLogSection):
        inner: dict = {"header": s.header}
        if s.preamble:
            inner["preamble"] = s.preamble
        if s.mode != "first_n":
            inner["mode"] = s.mode
        if s.cap != 8:
            inner["cap"] = s.cap
        return {"derivation_log": inner}
    if isinstance(s, HardwarePresenceSection):
        inner = {"header": s.header}
        if s.cap != 2:
            inner["cap"] = s.cap
        return {"hardware_presence": inner}
    if isinstance(s, BomTableSection):
        return {"bom_table": {"header": s.header}}
    raise TypeError(f"unknown doc section type {type(s).__name__}")


def _stage_to_dict(st) -> dict:
    """One authored sequence stage (task SEQSCHEMA/CPGCORE): name + why
    always (why is required by the loader), connections/parts only when
    declared — the exact authored shape, spec-local labels/ids."""
    out = {"name": st.name}
    if st.connections:
        out["connections"] = list(st.connections)
    if st.parts:
        out["parts"] = list(st.parts)
    out["why"] = st.why
    return out


def _subassembly_to_dict(unit) -> dict:
    """One authored bench unit in its exact spec-local shape."""
    return {"name": unit.name, "parts": list(unit.parts), "why": unit.why}


def _after_to_dict(claim) -> dict:
    """One typed process point constraint in its exact nested shape."""
    return {
        "connection": claim.connection,
        "after": [{ref.kind: ref.connection} for ref in claim.after],
        "why": claim.why,
    }


def dump_yaml(doc: DetailSpecDoc) -> str:
    """Serialize to YAML text (block style, keys in authoring order)."""
    return yaml.safe_dump(spec_to_dict(doc), sort_keys=False, default_flow_style=False)


def dump_json(doc: DetailSpecDoc) -> str:
    """Serialize to JSON text — the same structure through the other surface."""
    return json.dumps(spec_to_dict(doc), indent=2)


def _entry_to_dict(entry, leaf_to_dict):
    """A components/connections entry: a :class:`RepeatSpec` re-emits as a
    ``repeat:``/``body:`` block (its body through the same leaf serializer, so
    nesting round-trips); anything else through ``leaf_to_dict``."""
    if isinstance(entry, RepeatSpec):
        header = {"var": entry.var, "count": entry.count}
        if entry.start:
            header["start"] = entry.start
        return {"repeat": header,
                "body": [_entry_to_dict(e, leaf_to_dict) for e in entry.body]}
    return leaf_to_dict(entry)


def _component_to_dict(c) -> dict:
    d: dict = {"id": c.id}
    if c.imperative:
        d["imperative"] = c.imperative
    else:
        d["type"] = c.type
    d["name"] = c.name
    if c.reader_name:
        d["reader_name"] = c.reader_name
    if c.was:
        d["was"] = c.was
    if c.params:
        d["params"] = dict(c.params)
    if c.place is not None:
        d["place"] = _placement_to_dict(c.place)
    if c.features:
        d["features"] = [_feature_to_dict(feat) for feat in c.features]
    return d


def _feature_to_dict(feat) -> dict:
    body: dict = {}
    if feat.kind == "clearance_cut":
        body["around"] = feat.around
        body["gap"] = feat.gap
    else:  # bore
        body["dia"] = feat.dia
        if feat.at:
            body["at"] = list(feat.at)
        if feat.depth is not None:
            body["depth"] = feat.depth
    if feat.id:
        body["id"] = feat.id
    if feat.name:
        body["name"] = feat.name
    return {feat.kind: body}


def _placement_to_dict(place) -> dict:
    if isinstance(place, RawSpec):
        raw: dict = {"at": list(place.at)}
        if place.rotate:
            raw["rotate"] = [list(pair) for pair in place.rotate]
        return {"raw": raw}
    if isinstance(place, MateSpec):
        d: dict = {"datum": place.datum, "to": place.on, "to_datum": place.on_datum}
        if tuple(place.offset) != (0.0, 0.0, 0.0):
            d["offset"] = list(place.offset)
        if place.rotate:
            d["rotate"] = place.rotate
        if place.flip:
            d["flip"] = place.flip
        return d
    if isinstance(place, MountSpec):
        m: dict = {"to": place.to, "face": place.face, "axis": place.axis}
        if place.flush:
            m["flush"] = True
        if place.clear_by is not None:
            m["clear_by"] = place.clear_by
        if place.offset is not None:
            m["offset"] = place.offset
        if place.center:
            m["center"] = list(place.center)
        if place.ground is not None:
            m["ground"] = {"above": place.ground}
        if place.mirror:
            m["mirror"] = place.mirror
        return {"mount": m}
    raise TypeError(f"unknown placement type {type(place).__name__}")


def _connection_to_dict(c) -> dict:
    d: dict = {"type": c.type}
    if c.label:
        d["label"] = c.label
    if c.params:
        d["params"] = dict(c.params)
    d["parts"] = list(c.parts)
    if c.hardware:
        d["hardware"] = list(c.hardware)
    if c.surfaces:
        d["surfaces"] = dict(c.surfaces)
    if c.assumptions:
        d["assumptions"] = list(c.assumptions)
    if c.expect:
        d["expect"] = [_expect_to_dict(e) for e in c.expect]
    if c.install is not None:
        d["install"] = _install_to_dict(c.install)
    if c.process.cure is not None:
        cure = c.process.cure
        d["process"] = {"cure": {
            "instructions": list(cure.instructions),
            "completion": cure.completion,
            "why": cure.why,
        }}
    return d


def _expect_to_dict(e) -> dict:
    out = {"check": e.check, "reason": e.reason}
    if e.count != 1:
        out["count"] = e.count
    return out


def _install_to_dict(i) -> dict:
    """Re-emit one attached ``install:`` override — the inverse of
    ``loader._build_install``. ONLY authored (non-default) fields are
    emitted, per the module's omit-defaults convention, so the round-trip
    stays identity while the dump stays as small as what was authored."""
    out: dict = {}
    if i.method:
        out["method"] = i.method
    if i.entry_part:
        out["entry"] = {"part": i.entry_part, "face": i.entry_face}
    if i.angle is not None:
        out["angle"] = i.angle
    if i.exit:
        out["exit"] = i.exit
    if i.exit_faces:
        out["exit_faces"] = [{"part": p, "face": fc} for p, fc in i.exit_faces]
    if i.embedment is not None:
        out["embedment"] = i.embedment
    if i.head:
        out["head"] = i.head
    if i.tool_length is not None:
        out["tool"] = {"length": i.tool_length, "dia": i.tool_dia}
    if i.stage:
        out["stage"] = i.stage
    if i.role:
        out["role"] = i.role
    return out


def _validation_to_dict(v: ValidationSpec) -> dict:
    out: dict = {}
    if v.ground is not None:
        out["ground"] = v.ground
    if v.through_holes:
        out["through_holes"] = [{
            "part": t.part, "passes_through": list(t.passes_through),
            "axis": t.axis, "center": list(t.center),
            "r_inner": t.r_inner, "r_outer": t.r_outer, "span": t.span,
        } for t in v.through_holes]
    if v.dimensions:
        out["dimensions"] = [_dimension_to_dict(d) for d in v.dimensions]
    if v.bearings:
        out["bearings"] = [_entry_to_dict(b, _bearing_to_dict) for b in v.bearings]
    if v.bonds:
        out["bonds"] = [_entry_to_dict(b, _bond_to_dict) for b in v.bonds]
    if v.expected_overlaps:
        out["expected_overlaps"] = [_entry_to_dict(o, _pair_to_dict)
                                    for o in v.expected_overlaps]
    if v.contacts:
        out["contacts"] = [_entry_to_dict(c, _pair_to_dict) for c in v.contacts]
    return out


def _bearing_to_dict(b) -> dict:
    return {"a": b.a, "b": b.b, "axis": b.axis, "area": b.area}


def _bond_to_dict(b) -> dict:
    return {"a": b.a, "b": b.b}


def _pair_to_dict(p) -> dict:
    return {"a": p.a, "b": p.b}


def _role_to_authored(cid: str, role: str, doc):
    """Re-emit one ``roles:`` entry as its authored form — the inverse of
    ``loader._build_roles``. A walking_surface re-emits its scheme; a self-grounded
    existing body (``cid`` in ``context_grounds``) re-emits ``{role: existing,
    grounded_by: site}``; everything else is the bare role string."""
    if cid in doc.support_schemes:
        return _walking_surface_to_dict(doc.support_schemes[cid])
    if cid in doc.context_grounds:
        return {"role": "existing", "grounded_by": "site"}
    return role


def _walking_surface_to_dict(s) -> dict:
    """Re-emit a :class:`WalkingSurfaceScheme` as its authored mapping (task
    SUPPORT). Optional fields are emitted only when non-default (``members``
    only when it is not the implicit ``[key]``) so the dump matches what a human
    would write while still reloading to an equal scheme."""
    out: dict = {"role": "walking_surface"}
    if tuple(s.members) != (s.key,):
        out["members"] = list(s.members)
    if s.supports:
        out["supports"] = list(s.supports)
    if s.declared_cantilever:
        out["declared_cantilever"] = [
            ({"edge": c.edge, "note": c.note} if c.note else {"edge": c.edge})
            for c in s.declared_cantilever]
    if s.deferred_support:
        out["deferred_support"] = s.deferred_support
    if s.label:
        out["label"] = s.label
    return out


def _spatial_to_dict(sp: SpatialSpec) -> dict:
    out: dict = {}
    if sp.symmetric:
        out["symmetric"] = [_symmetric_to_dict(s) for s in sp.symmetric]
    if sp.faces:
        out["faces"] = [_faces_to_dict(x) for x in sp.faces]
    return out


def _symmetric_to_dict(s: SymmetricSpec) -> dict:
    d: dict = {"plane": s.plane}
    if s.pairs:
        d["pairs"] = [list(p) for p in s.pairs]
    if s.mirror is not None:
        d["mirror"] = list(s.mirror)
    if s.tol is not None:
        d["tol"] = s.tol
    return d


def _faces_to_dict(x: FacesSpec) -> dict:
    d: dict = {"part": x.part}
    if x.facing_datum is not None:
        d["facing_datum"] = x.facing_datum
    else:
        d["facing"] = list(x.facing)
    if x.target is not None:
        d[x.sense] = x.target                       # toward:/away: a part id
    else:
        d[f"{x.sense}_dir"] = list(x.target_dir)    # toward_dir:/away_dir: a vec
    if x.tol is not None:
        d["tol"] = x.tol
    return d


def _dimension_to_dict(d) -> dict:
    out: dict = {"name": d.name, "part": d.part, "measure": d.measure,
                 "expected": d.expected}
    if d.tolerance is not None:
        out["tolerance"] = d.tolerance
    if d.negate:
        out["negate"] = d.negate
    if d.op != "eq":
        out["op"] = d.op
    if d.minus_part is not None:
        out["minus_part"] = d.minus_part
        out["minus_measure"] = d.minus_measure
    return out
