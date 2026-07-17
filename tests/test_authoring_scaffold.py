"""Generic, fail-closed DetailSpec scaffolding."""

import yaml

import pytest

from detailgen.authoring.scaffold import (
    ScaffoldComponent,
    ScaffoldConnection,
    ScaffoldError,
    ScaffoldRequest,
    build_scaffold,
    write_scaffold,
)
from detailgen.certification import load_contract
from detailgen.spec import compile_spec, compile_spec_file, load_spec_file, load_spec_text


def test_writes_generic_component_spec_and_resolvable_certification(tmp_path):
    request = ScaffoldRequest(
        slug="garden_slab",
        output_dir=tmp_path,
        components=(ScaffoldComponent(
            id="base",
            type="slab",
            params={"width": 12, "length": 18, "thickness": 1},
        ),),
    )

    result = write_scaffold(request)

    doc = load_spec_file(result.spec_path)
    detail = compile_spec_file(result.spec_path)
    contract = load_contract(result.contract_path, repo_root=tmp_path)
    assert doc.name == "garden_slab"
    assert [(row.id, row.type) for row in doc.components] == [("base", "slab")]
    assert len(detail.assembly.parts) == 1
    assert contract.slug == "garden_slab"
    assert contract.subject.source == result.spec_path.resolve()
    assert result.implicit_identity_placements == ("base",)


def test_preserves_explicit_raw_placement_and_parameterized_connection(tmp_path):
    request = ScaffoldRequest(
        slug="joined_panels",
        output_dir=tmp_path,
        components=(
            ScaffoldComponent(
                id="left",
                type="slab",
                params={"width": 12, "length": 18, "thickness": 1},
                place={"raw": {"at": [0, 0, 0]}},
            ),
            ScaffoldComponent(
                id="right",
                type="slab",
                params={"width": 12, "length": 18, "thickness": 1},
                place={"raw": {"at": [12, 0, 0]}},
            ),
        ),
        connections=(ScaffoldConnection(
            type="butt_screwed",
            parts=("left", "right"),
            params={"n_screws": 0},
        ),),
    )

    documents = build_scaffold(request)

    doc = load_spec_text(documents.spec_text)
    detail = compile_spec(doc)
    detail.build()
    assert doc.components[1].place.at == (12, 0, 0)
    assert doc.connections[0].type == "butt_screwed"
    assert doc.connections[0].params == {"n_screws": 0}
    assert len(detail.connections()) == 1
    assert documents.implicit_identity_placements == ()


@pytest.mark.parametrize(
    ("scaffold_request", "message"),
    [
        (
            ScaffoldRequest(
                "bad_component", ".",
                (ScaffoldComponent("base", "slba", {}),),
            ),
            "unknown component",
        ),
        (
            ScaffoldRequest(
                "missing_params", ".",
                (ScaffoldComponent("base", "slab", {"width": 12}),),
            ),
            "missing required params ['length']",
        ),
        (
            ScaffoldRequest(
                "unknown_params", ".",
                (ScaffoldComponent(
                    "base", "slab",
                    {"width": 12, "length": 18, "widht": 1},
                ),),
            ),
            "unknown params ['widht']",
        ),
        (
            ScaffoldRequest(
                "duplicate_ids", ".",
                (
                    ScaffoldComponent(
                        "base", "slab", {"width": 12, "length": 18},
                    ),
                    ScaffoldComponent(
                        "base", "slab", {"width": 10, "length": 16},
                    ),
                ),
            ),
            "duplicate component id 'base'",
        ),
        (
            ScaffoldRequest(
                "bad_connection", ".",
                (ScaffoldComponent(
                    "base", "slab", {"width": 12, "length": 18},
                ),),
                (ScaffoldConnection("gluedd", ("base",), {}),),
            ),
            "unknown connection type",
        ),
        (
            ScaffoldRequest(
                "missing_connection_params", ".",
                (ScaffoldComponent(
                    "base", "slab", {"width": 12, "length": 18},
                ),),
                (ScaffoldConnection("butt_screwed", ("base", "base"), {}),),
            ),
            "missing required params ['n_screws']",
        ),
        (
            ScaffoldRequest(
                "undeclared_part", ".",
                (ScaffoldComponent(
                    "base", "slab", {"width": 12, "length": 18},
                ),),
                (ScaffoldConnection("glued", ("base", "missing"), {}),),
            ),
            "undeclared parts ['missing']",
        ),
    ],
)
def test_fails_closed_for_invalid_registry_inputs(scaffold_request, message):
    with pytest.raises(ScaffoldError, match=message.replace("[", r"\[").replace("]", r"\]")):
        build_scaffold(scaffold_request)


def test_build_scaffold_instantiates_geometry_before_success(tmp_path):
    request = ScaffoldRequest(
        "bad_nominal",
        tmp_path,
        (ScaffoldComponent(
            "member", "lumber", {"nominal": "2by4", "length": 36},
        ),),
    )

    with pytest.raises(ValueError, match="Unknown nominal size"):
        build_scaffold(request)


def test_refuses_to_overwrite_either_output_without_force(tmp_path):
    request = ScaffoldRequest(
        "garden_slab",
        tmp_path,
        (ScaffoldComponent(
            "base", "slab", {"width": 12, "length": 18},
        ),),
    )
    (tmp_path / "garden_slab.cert.yaml").write_text("existing\n")

    with pytest.raises(ScaffoldError, match="refusing to overwrite"):
        write_scaffold(request)

    assert not (tmp_path / "garden_slab.spec.yaml").exists()
    assert (tmp_path / "garden_slab.cert.yaml").read_text() == "existing\n"


def test_contract_verification_failure_leaves_no_partial_outputs(tmp_path, monkeypatch):
    request = ScaffoldRequest(
        "garden_slab",
        tmp_path,
        (ScaffoldComponent(
            "base", "slab", {"width": 12, "length": 18},
        ),),
    )

    def fail_contract(*_args, **_kwargs):
        raise RuntimeError("contract verification failed")

    monkeypatch.setattr("detailgen.authoring.scaffold.load_contract", fail_contract)

    with pytest.raises(RuntimeError, match="contract verification failed"):
        write_scaffold(request)

    assert list(tmp_path.glob("garden_slab.*.yaml")) == []
    assert not [path for path in tmp_path.iterdir() if path.is_dir()]


def test_generated_yaml_uses_only_authoring_fields(tmp_path):
    documents = build_scaffold(ScaffoldRequest(
        "garden_slab",
        tmp_path,
        (ScaffoldComponent(
            "base", "slab", {"width": 12, "length": 18},
        ),),
    ))

    assert set(yaml.safe_load(documents.spec_text)) == {
        "name", "type", "units", "components",
    }


def test_connection_missing_param_diagnostic_names_connection_set_flag(tmp_path):
    request = ScaffoldRequest(
        "joined_panels",
        tmp_path,
        (ScaffoldComponent(
            "base", "slab", {"width": 12, "length": 18},
        ),),
        (ScaffoldConnection("butt_screwed", ("base", "base"), {}),),
    )

    with pytest.raises(
        ScaffoldError,
        match=r"--connection-set 0\.n_screws=VALUE",
    ):
        build_scaffold(request)


def test_scaffold_api_is_public():
    from detailgen.authoring import (
        ScaffoldComponent as PublicComponent,
        ScaffoldRequest as PublicRequest,
        build_scaffold as public_build,
        write_scaffold as public_write,
    )

    assert PublicComponent is ScaffoldComponent
    assert PublicRequest is ScaffoldRequest
    assert public_build is build_scaffold
    assert public_write is write_scaffold
