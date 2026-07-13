"""Context-body self-grounding — the proof suite (task CTXGROUND).

A PRE-EXISTING site feature (a living tree, a rock outcrop) is grounded earth-side
in reality, OUTSIDE the constructed load path. Declaring ``role: existing`` +
``grounded_by: site`` exempts it from the constructed-connectivity floating check,
so a truthful clearance gap around it (a real growth gap) no longer needs a
fake-tight contact bond to fake connectivity. The exemption is EXPLICIT and
role-gated, and it does NOT make the body a foundation — a support scheme still
cannot route through it.
"""

from __future__ import annotations

import pytest
import yaml

from detailgen.core.ontology import OntologyError
from detailgen.spec.compiler import compile_spec
from detailgen.spec.loader import load_spec_text
from detailgen.spec.schema import SpecSchemaError


def _in(v):
    return f"{v} in"


def _footing(cid="found"):
    return {"id": cid, "type": "footing", "name": cid,
            "params": {"width": _in(40), "length": _in(40), "thickness": _in(6)},
            "place": {"raw": {"at": [_in(0), _in(0), _in(0)]}}}


def _trunk(at=(30, 30, 0)):
    # A living tree standing off in a real growth GAP — touches nothing.
    return {"id": "trunk", "type": "tree_trunk", "name": "trunk",
            "params": {"diameter": _in(10), "height": _in(96)},
            "place": {"raw": {"at": [_in(at[0]), _in(at[1]), _in(at[2])]}}}


def _leg(cid="leg", at=(0, 0, 0)):
    return {"id": cid, "type": "lumber", "name": cid,
            "params": {"nominal": "4x4", "length": _in(3.5)},
            "place": {"raw": {"at": [_in(at[0]), _in(at[1]), _in(at[2])]}}}


def _compile(doc):
    return compile_spec(load_spec_text(yaml.safe_dump(doc)))


def _floating(detail):
    rep = detail.validate()
    fl = [f for f in rep.findings if f.check == "floating"]
    assert len(fl) == 1, f"expected one floating finding, got {fl}"
    return rep, fl[0]


def _trunk_doc(trunk_role):
    return {"name": "ctx", "units": "in",
            "components": [_footing(), _leg(), _trunk()],
            "roles": {"found": "ground", "trunk": trunk_role},
            "validation": {"ground": "found", "bonds": [{"a": "leg", "b": "found"}]}}


# -- the exemption: open-gap trunk + declaration -> PASS with a visible note --

def test_open_gap_trunk_with_declaration_passes_floating_with_visible_exemption():
    d = _compile(_trunk_doc({"role": "existing", "grounded_by": "site"}))
    rep, f = _floating(d)
    assert f.passed
    # visible, connectivity-rung language — never a load-path/support claim
    assert "trunk" in f.detail
    assert "grounded by site" in f.detail
    assert "outside constructed load paths" in f.detail


# -- without the declaration, the same body still floats (UNCHANGED) ---------

def test_open_gap_trunk_without_declaration_still_floats():
    d = _compile(_trunk_doc("existing"))   # existing role, but NOT grounded_by
    rep, f = _floating(d)
    assert not f.passed
    assert "trunk" in f.subject  # it is named as a floater, exactly as before


def test_no_role_at_all_still_floats():
    doc = _trunk_doc("existing")
    doc["roles"].pop("trunk")   # no role -> ordinary part -> must reach ground
    d = _compile(doc)
    rep, f = _floating(d)
    assert not f.passed and "trunk" in f.subject


# -- the exemption is EXPLICIT: `existing` alone does not silently exempt -----

def test_bare_existing_role_is_not_inferred_as_self_grounded():
    d = _compile(_trunk_doc("existing"))
    assert not d.doc.context_grounds   # nothing exempt unless grounded_by: site


# -- teaching error: a constructed part claiming the exemption ---------------

def test_constructed_part_claiming_the_exemption_is_a_teaching_error():
    doc = {"name": "ctx", "units": "in", "components": [_footing(), _leg()],
           "roles": {"found": "ground",
                     "leg": {"role": "support", "grounded_by": "site"}}}
    with pytest.raises(SpecSchemaError, match="only legal for a 'role: existing'"):
        _compile(doc)


def test_grounded_by_only_accepts_site():
    doc = _trunk_doc({"role": "existing", "grounded_by": "earth"})
    with pytest.raises(SpecSchemaError, match="only 'site' is legal"):
        _compile(doc)


# -- HARD BOUNDARY with the support family (req 3): NOT a foundation ----------

def test_existing_body_is_not_a_foundation_for_a_support_scheme():
    """A walking_surface routing its support scheme THROUGH a context body must
    still FAIL — an existing site body is self-grounded but NOT a foundation, so
    the support check finds no foundation, exactly as it would today."""
    doc = {"name": "ctx", "units": "in",
           "components": [
               _trunk(at=(0, 0, 0)),
               {"id": "board", "type": "deck_board", "name": "board",
                "params": {"length": _in(60)},
                "place": {"raw": {"at": [_in(0), _in(0), _in(96)]}}},
           ],
           "roles": {
               "trunk": {"role": "existing", "grounded_by": "site"},
               "board": {"role": "walking_surface", "label": "deck",
                         "members": ["board"], "supports": ["trunk"]},
           },
           "validation": {"bonds": [{"a": "board", "b": "trunk"}]}}
    rep = _compile(doc).validate()
    sup = [f for f in rep.findings if f.check == "support"]
    assert len(sup) == 1 and not sup[0].passed
    # it fails for lack of a FOUNDATION, not because the trunk is exempt-grounded
    assert "foundation" in sup[0].detail


def test_existing_body_as_validation_ground_is_a_teaching_error():
    """The floating terminal must be a FOUNDATION too: pointing validation.ground
    at a self-grounded context body is the member-as-ground degeneracy's cousin."""
    doc = {"name": "ctx", "units": "in", "components": [_trunk(at=(0, 0, 0))],
           "roles": {"trunk": {"role": "existing", "grounded_by": "site"}},
           "validation": {"ground": "trunk"}}
    with pytest.raises(OntologyError, match="must be a FOUNDATION"):
        _compile(doc).validate()
