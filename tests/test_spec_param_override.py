"""The param-override compile entry point and the ``SpecDetail.params`` proxy
(task 4B-1).

Two capabilities the ``.py`` details carry that a one-instance spec did not:

1. A param-OVERRIDE compile — :func:`compile_spec(doc, overrides=...)` /
   :func:`compile_spec_file` — that re-binds named ``params:`` before
   ``derived:`` recomputes, the declarative twin of ``dataclass.replace``. The
   no-override path must be UNPERTURBED (byte-identical), and every bad override
   is a teaching :class:`SpecCompileError`.
2. A read-only ``.params`` proxy over the resolved param+derived namespace, so a
   consumer written against a ``.py`` detail's ``.params.<field>`` (a
   :class:`~detailgen.details.base.Callout`, ``_site_overview``) works unchanged
   against a ``SpecDetail``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from detailgen.details.base import Callout, fmt_frac_in
from detailgen.spec.compiler import (
    ParamsProxy,
    SpecCompileError,
    compile_spec,
    compile_spec_file,
)
from detailgen.spec.loader import load_spec_file

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "details" / "platform.spec.yaml"


@pytest.fixture(scope="module")
def doc():
    return load_spec_file(SPEC)


def _fingerprint(detail):
    out = {}
    for p in detail.assembly.parts:
        wp = p.world_solid()
        solids = wp.vals()
        vol = sum(s.Volume() for s in solids)
        bb = (wp.combine().objects[0].BoundingBox() if len(solids) > 1
              else solids[0].BoundingBox())
        out[p.name] = (
            tuple(p.world_frame.origin), vol,
            (bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax),
        )
    return out


def _hash(detail) -> str:
    """A stable content hash of the built geometry fingerprint — canonical (sorted
    by part name, full float repr), so two deterministic builds hash equal."""
    fp = _fingerprint(detail)
    canon = repr(sorted((name, fp[name]) for name in fp))
    return hashlib.sha256(canon.encode()).hexdigest()


def _spec_log_text(detail) -> list[str]:
    """The compiler's OWN derivation facts (units/params/derived/placement) — the
    surface the override path produces. Deliberately NOT the full
    ``derivation_report()``, whose Connection-generated facts have a build-order
    that is not stable across runs (pre-existing, orthogonal to compile)."""
    return [f.fact for f in detail._spec_log]


# -- requirement 4: the entry point must not perturb the no-override path -------

def test_empty_override_is_byte_identical_to_plain_compile(doc):
    plain = compile_spec(doc)
    empty = compile_spec(doc, overrides={})
    explicit_none = compile_spec(doc, overrides=None)
    plain.validate(); empty.validate(); explicit_none.validate()
    # geometry
    assert _hash(plain) == _hash(empty) == _hash(explicit_none)
    # namespace + derivation log (facts) — no override fact leaks in
    assert plain.namespace == empty.namespace == explicit_none.namespace
    assert _spec_log_text(plain) == _spec_log_text(empty) == _spec_log_text(explicit_none)
    assert not any("OVERRIDDEN" in f for f in _spec_log_text(empty))
    # BOM
    assert plain.bom_table() == empty.bom_table()


def test_override_compile_is_deterministic(doc):
    a = compile_spec(doc, overrides={"rail_height": 42.0})
    b = compile_spec(doc, overrides={"rail_height": 42.0})
    a.validate(); b.validate()
    assert _hash(a) == _hash(b)


# -- requirement 1: override re-binds params, derived recomputes ---------------

def test_override_rebinds_param_and_recomputes_derived(doc):
    base = compile_spec(doc)
    over = compile_spec(doc, overrides={"deck_width": 44.0})
    # the param itself is re-bound
    assert base.params.deck_width == 33.0
    assert over.params.deck_width == 44.0
    # ...and a DERIVED dimension that references it recomputes (n_deck =
    # deck_width / deck_w = 44 / 5.5 = 8), without any edit to derived:.
    assert base.params.n_deck == 6.0
    assert over.params.n_deck == 8.0
    # the override is logged with provenance (P1/P4) as an OVERRIDDEN param fact
    assert any("param deck_width" in f and "OVERRIDDEN" in f
               for f in _spec_log_text(over))


def test_override_only_changes_named_params(doc):
    over = compile_spec(doc, overrides={"rail_height": 42.0})
    base = compile_spec(doc)
    # every OTHER param is untouched
    for name in doc.params:
        if name == "rail_height":
            continue
        assert getattr(over.params, name) == getattr(base.params, name)


def test_compile_spec_file_honors_overrides():
    detail = compile_spec_file(SPEC, overrides={"rail_height": 42.0})
    assert detail.params.rail_height == 42.0
    # and the plain file compile is unperturbed
    assert compile_spec_file(SPEC).params.rail_height == 36.0


# -- requirement 1: teaching errors for bad overrides --------------------------

def test_override_unknown_param_teaches(doc):
    with pytest.raises(SpecCompileError) as e:
        compile_spec(doc, overrides={"rail_heigth": 42.0})  # typo
    msg = str(e.value)
    assert "unknown override param 'rail_heigth'" in msg
    assert "did you mean" in msg and "rail_height" in msg


def test_override_derived_name_teaches(doc):
    with pytest.raises(SpecCompileError) as e:
        compile_spec(doc, overrides={"n_deck": 4.0})  # a DERIVED dimension
    msg = str(e.value)
    assert "cannot override 'n_deck'" in msg
    assert "DERIVED" in msg
    assert "Override the param(s)" in msg


def test_override_nonnumeric_length_directive_teaches(doc):
    with pytest.raises(SpecCompileError) as e:
        compile_spec(doc, overrides={"rail_height": "42 in"})  # a directive, not a number
    msg = str(e.value)
    assert "must be a bare number" in msg
    assert "rail_height" in msg


def test_override_bool_is_not_a_number(doc):
    # bool is an int subclass in Python — a length override must reject it.
    with pytest.raises(SpecCompileError):
        compile_spec(doc, overrides={"rail_height": True})


# -- requirement 2: the .params proxy ------------------------------------------

def test_params_proxy_reads_params_and_derived(doc):
    detail = compile_spec(doc)
    assert isinstance(detail.params, ParamsProxy)
    # a param (authoring-unit magnitude, the raw number before * IN)
    assert detail.params.rail_height == 36.0
    assert detail.params.deck_width == 33.0
    # a DERIVED dimension is on the same surface
    assert detail.params.n_deck == 6.0
    assert detail.params.beam_total_len == 48.0 + 12.0
    # membership reflects the full namespace
    assert "rail_height" in detail.params
    assert "n_deck" in detail.params
    assert "nope" not in detail.params


def test_params_proxy_is_read_only(doc):
    detail = compile_spec(doc)
    with pytest.raises(AttributeError) as e:
        detail.params.rail_height = 42.0
    msg = str(e.value)
    assert "read-only" in msg
    assert "compile_spec(doc, overrides=" in msg  # names the fix


def test_params_proxy_unknown_attr_teaches(doc):
    detail = compile_spec(doc)
    with pytest.raises(AttributeError) as e:
        detail.params.rail_heigth  # typo
    msg = str(e.value)
    assert "no param or derived dimension 'rail_heigth'" in msg
    assert "did you mean" in msg and "rail_height" in msg


def test_callout_renders_against_spec_params(doc):
    # the exact consumer shape the scout named (base.Callout.render calls
    # getattr(params, param) + a params-callable endpoint): a Callout built over
    # a spec param resolves its label text and geometry off the proxy unchanged.
    detail = compile_spec(doc)
    callout = Callout(
        "rail_height", "{v} RAIL",
        p0=(0.0, 0.0, 0.0),
        p1=lambda p: (p.rail_height, 0.0, 0.0),  # params-callable endpoint
    )
    rendered = callout.render(detail.params)
    assert rendered["label"] == f"{fmt_frac_in(36.0)} RAIL" == '36" RAIL'
    assert rendered["p1"] == [36.0, 0.0, 0.0]
