"""Generic, fail-closed DetailSpec scaffolding."""

import json
from pathlib import Path
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
from detailgen.core import IN
from detailgen.spec import compile_spec, compile_spec_file, load_spec_file, load_spec_text
from detailgen.validation import Finding, ValidationReport
from detailgen.validation.checks import UNKNOWN_VERDICT


def _overlapping_slab_request(tmp_path):
    placement = {"raw": {"at": [0, 0, 0]}}
    return ScaffoldRequest(
        "overlapping_slabs",
        tmp_path,
        tuple(
            ScaffoldComponent(
                name,
                "slab",
                {"width": 12, "length": 18},
                placement,
            )
            for name in ("first", "second", "third")
        ),
        (
            ScaffoldConnection("glued", ("first", "second")),
            ScaffoldConnection("glued", ("first", "third")),
            ScaffoldConnection("glued", ("second", "third")),
        ),
    )


def _cut_face_mate_request(tmp_path, placement):
    params = {
        "nominal": "2x4",
        "length": "24 in",
        "length_semantics": "long_point_to_long_point",
        "end_cuts": [
            {"end": "near", "miter_angle_degrees": 60, "long_face": "bottom"},
            {"end": "far", "miter_angle_degrees": 60, "long_face": "bottom"},
        ],
    }
    return ScaffoldRequest(
        "cut_face_mate",
        tmp_path,
        (
            ScaffoldComponent("first", "lumber", params),
            ScaffoldComponent("second", "lumber", params, placement),
        ),
        (ScaffoldConnection("glued", ("first", "second")),),
    )


def test_authoring_cli_without_subcommand_still_prints_manifest(capsys):
    from detailgen.authoring.__main__ import main

    assert main([]) == 0
    assert json.loads(capsys.readouterr().out)["schema"] \
        == "detailgen/authoring-manifest/v2"


def test_authoring_cli_grammar_is_bounded_without_full_registry(capsys):
    from detailgen.authoring.__main__ import main

    assert main(["grammar"]) == 0
    output = capsys.readouterr().out
    grammar = json.loads(output)
    assert grammar["schema"] == "detailgen/authoring-grammar/v1"
    assert len(output.splitlines()) < 300
    assert "components" not in grammar


def test_authoring_cli_scaffolds_explicit_components_and_connection(tmp_path, capsys):
    from detailgen.authoring.__main__ import main

    exit_code = main([
        "scaffold",
        "--slug", "joined_panels",
        "--out", str(tmp_path),
        "--component", "left:slab",
        "--set", "left.width=12",
        "--set", "left.length=18",
        "--place", "left={raw: {at: [0, 0, 0]}}",
        "--component", "right:slab",
        "--set", "right.width=12",
        "--set", "right.length=18",
        "--place", "right={raw: {at: [18, 0, 0]}}",
        "--component", "screw:wood_screw",
        "--set", "screw.diameter=0.16",
        "--set", "screw.length=1.5",
        "--place", "screw={raw: {at: [18, 6, 9]}}",
        "--connection", "butt_screwed:left,right",
        "--connection-set", "0.n_screws=1",
        "--connection-hardware", "0=screw",
    ])

    result = json.loads(capsys.readouterr().out)
    doc = load_spec_file(tmp_path / "joined_panels.spec.yaml")
    assert exit_code == 0
    assert result == {
        "schema": "detailgen/scaffold-result/v1",
        "spec": str(tmp_path / "joined_panels.spec.yaml"),
        "certification": str(tmp_path / "joined_panels.cert.yaml"),
        "implicit_identity_placements": [],
        "geometry_inferred": False,
    }
    assert doc.components[1].place.at == (18, 0, 0)
    assert doc.connections[0].params == {"n_screws": 1}
    assert doc.connections[0].hardware == ["screw"]


def test_authoring_cli_yaml_value_keeps_nominal_size_string(tmp_path, capsys):
    from detailgen.authoring.__main__ import main

    assert main([
        "scaffold", "--slug", "single_member", "--out", str(tmp_path),
        "--component", "member:lumber",
        "--set", "member.nominal=2x4",
        "--set", "member.length=36",
    ]) == 0
    capsys.readouterr()

    raw = yaml.safe_load((tmp_path / "single_member.spec.yaml").read_text())
    assert raw["components"][0]["params"]["nominal"] == "2x4"


def test_authoring_cli_scaffolds_nominal_2x2_with_dressed_dimensions(
    tmp_path, capsys,
):
    from detailgen.authoring.__main__ import main

    assert main([
        "scaffold", "--slug", "single_2x2_member", "--out", str(tmp_path),
        "--component", "member:lumber",
        "--set", "member.nominal=2x2",
        "--set", "member.length=36 in",
    ]) == 0
    capsys.readouterr()

    detail = compile_spec_file(tmp_path / "single_2x2_member.spec.yaml")
    member = detail.assembly.parts[0].component
    assert member.nominal == "2x2"
    assert member.actual == pytest.approx((1.5 * IN, 1.5 * IN))
    bounds = member.bounding_box()
    assert bounds.ylen == pytest.approx(1.5 * IN)
    assert bounds.zlen == pytest.approx(1.5 * IN)


def test_authoring_cli_reports_malformed_yaml_value(tmp_path, capsys):
    from detailgen.authoring.__main__ import main

    with pytest.raises(SystemExit) as error:
        main([
            "scaffold", "--slug", "bad_value", "--out", str(tmp_path),
            "--component", "base:slab",
            "--set", "base.width=[",
            "--set", "base.length=18",
        ])

    assert error.value.code == 2
    assert "invalid YAML value" in capsys.readouterr().err


def test_authoring_cli_reports_unknown_component_with_known_keys(tmp_path, capsys):
    from detailgen.authoring.__main__ import main

    with pytest.raises(SystemExit) as error:
        main([
            "scaffold", "--slug", "bad_type", "--out", str(tmp_path),
            "--component", "base:slba",
        ])

    assert error.value.code == 2
    stderr = capsys.readouterr().err
    assert "unknown component 'slba'" in stderr
    assert "slab" in stderr


def test_writes_generic_component_spec_and_resolvable_certification(tmp_path):
    request = ScaffoldRequest(
        slug="2x4_garden_slab",
        output_dir=tmp_path,
        components=(ScaffoldComponent(
            id="base",
            type="slab",
            params={"width": 12, "length": 18},
        ),),
    )

    result = write_scaffold(request)

    doc = load_spec_file(result.spec_path)
    detail = compile_spec_file(result.spec_path)
    contract = load_contract(result.contract_path, repo_root=tmp_path)
    assert result.spec_path == tmp_path / "2x4_garden_slab.spec.yaml"
    assert result.contract_path == tmp_path / "2x4_garden_slab.cert.yaml"
    assert doc.name == "2x4_garden_slab"
    assert [(row.id, row.type) for row in doc.components] == [("base", "slab")]
    assert len(detail.assembly.parts) == 1
    assert contract.slug == "2x4_garden_slab"
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
                params={"width": 12, "length": 18},
                place={"raw": {"at": [0, 0, 0]}},
            ),
            ScaffoldComponent(
                id="right",
                type="slab",
                params={"width": 12, "length": 18},
                place={"raw": {"at": [18, 0, 0]}},
            ),
            ScaffoldComponent(
                id="screw",
                type="wood_screw",
                params={"diameter": 0.16, "length": 1.5},
                place={"raw": {"at": [18, 6, 9]}},
            ),
        ),
        connections=(ScaffoldConnection(
            type="butt_screwed",
            parts=("left", "right"),
            params={"n_screws": 1},
            hardware=("screw",),
        ),),
    )

    documents = build_scaffold(request)

    doc = load_spec_text(documents.spec_text)
    detail = compile_spec(doc)
    detail.build()
    assert doc.components[1].place.at == (18, 0, 0)
    assert doc.connections[0].type == "butt_screwed"
    assert doc.connections[0].params == {"n_screws": 1}
    assert doc.connections[0].hardware == ["screw"]
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


def test_rejects_connection_that_would_crash_package_validation(tmp_path):
    request = ScaffoldRequest(
        "missing_hardware",
        tmp_path,
        (
            ScaffoldComponent(
                "left", "slab", {"width": 12, "length": 18},
            ),
            ScaffoldComponent(
                "right", "slab", {"width": 12, "length": 18},
                {"raw": {"at": [12, 0, 0]}},
            ),
        ),
        (ScaffoldConnection(
            "butt_screwed", ("left", "right"), {"n_screws": 1},
        ),),
    )

    with pytest.raises(ValueError, match="expected 1 hardware item"):
        build_scaffold(request)


def test_scaffold_rejects_all_definite_validation_failures_with_mate_guidance(
    tmp_path,
):
    with pytest.raises(ScaffoldError) as error:
        build_scaffold(_overlapping_slab_request(tmp_path))

    message = str(error.value)
    assert "scaffold validation failed with 3 definite failure(s):" in message
    assert message.count("[FAIL] interference:") == 3
    assert "first <-> second" in message
    assert "first <-> third" in message
    assert "second <-> third" in message
    assert "datum" in message and "to_datum" in message
    assert "reserve `raw` transforms" in message


def test_nested_mate_wrapper_reports_exact_direct_place_assignment(tmp_path):
    request = _cut_face_mate_request(tmp_path, {"mate": {
        "datum": "cut_near",
        "to": "first",
        "to_datum": "cut_far",
        "flip": True,
    }})

    with pytest.raises(ScaffoldError) as error:
        build_scaffold(request)

    message = str(error.value)
    assert "not a nested `mate` wrapper" in message
    assert (
        "--place 'second={datum: cut_near, to: first, to_datum: cut_far, "
        "flip: true}'"
    ) in message


def test_cut_face_interference_reports_exact_flip_true_assignment(tmp_path):
    request = _cut_face_mate_request(tmp_path, {
        "datum": "cut_near",
        "to": "first",
        "to_datum": "cut_far",
    })

    with pytest.raises(ScaffoldError) as error:
        build_scaffold(request)

    message = str(error.value)
    assert "first <-> second" in message
    assert "Physical cut-face mate `second` -> `first` overlaps" in message
    assert "Set `flip: true` so the cut-face normals oppose" in message
    assert (
        "--place 'second={datum: cut_near, to: first, to_datum: cut_far, "
        "flip: true}'"
    ) in message


def test_validation_failure_leaves_no_partial_outputs(tmp_path):
    with pytest.raises(ScaffoldError):
        write_scaffold(_overlapping_slab_request(tmp_path))

    assert not (tmp_path / "overlapping_slabs.spec.yaml").exists()
    assert not (tmp_path / "overlapping_slabs.cert.yaml").exists()


def test_unknown_validation_does_not_block_scaffold_preview(tmp_path, monkeypatch):
    class UnknownDetail:
        def build(self):
            return None

        def connections(self):
            return ()

        def validate(self):
            report = ValidationReport("unknown preview")
            report.add(Finding(
                "support",
                "generic support fact",
                False,
                "not resolved",
                verdict=UNKNOWN_VERDICT,
            ))
            return report

    monkeypatch.setattr(
        "detailgen.authoring.scaffold.compile_spec",
        lambda _doc: UnknownDetail(),
    )
    request = ScaffoldRequest(
        "unknown_preview",
        tmp_path,
        (ScaffoldComponent(
            "base", "slab", {"width": 12, "length": 18, "thickness": 1},
        ),),
    )

    documents = build_scaffold(request)

    assert "name: unknown_preview" in documents.spec_text


def test_refuses_to_overwrite_before_expensive_build(tmp_path, monkeypatch):
    request = ScaffoldRequest(
        "garden_slab",
        tmp_path,
        (ScaffoldComponent(
            "base", "slab", {"width": 12, "length": 18},
        ),),
    )
    (tmp_path / "garden_slab.cert.yaml").write_text("existing\n")
    monkeypatch.setattr(
        "detailgen.authoring.scaffold.build_scaffold",
        lambda _request: pytest.fail("collision must precede CAD build"),
    )

    with pytest.raises(ScaffoldError, match="refusing to overwrite"):
        write_scaffold(request)

    assert not (tmp_path / "garden_slab.spec.yaml").exists()
    assert (tmp_path / "garden_slab.cert.yaml").read_text() == "existing\n"


def test_second_install_failure_restores_prior_output_pair(tmp_path, monkeypatch):
    request = ScaffoldRequest(
        "garden_slab",
        tmp_path,
        (ScaffoldComponent(
            "base", "slab", {"width": 12, "length": 18},
        ),),
        force=True,
    )
    spec_path = tmp_path / "garden_slab.spec.yaml"
    contract_path = tmp_path / "garden_slab.cert.yaml"
    spec_path.write_text("old spec\n")
    contract_path.write_text("old contract\n")
    original_replace = Path.replace
    failed = False

    def fail_first_contract_install(source, target):
        nonlocal failed
        if Path(target) == contract_path and not failed:
            failed = True
            raise OSError("forced second rename failure")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_first_contract_install)

    with pytest.raises(OSError, match="forced second rename failure"):
        write_scaffold(request)

    assert spec_path.read_text() == "old spec\n"
    assert contract_path.read_text() == "old contract\n"
    assert [path for path in tmp_path.iterdir() if path.is_dir()] == []


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

    raw = yaml.safe_load(documents.spec_text)
    assert set(raw) == {
        "name", "type", "units", "components",
    }
    assert raw["units"] == "mm"


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


def test_readme_teaches_scaffold_and_non_inference_conventions():
    readme = (Path(__file__).parents[1] / "README.md").read_text()

    assert "detailgen.authoring scaffold" in readme
    assert "world-axis bounding-box" in readme
    assert "degrees off square" in readme
    assert "No rotation-invariant member-length measure" in readme
    assert "Bare numeric component and placement lengths are millimeters" in readme
    assert "definite validation failure" in readme
    assert "UNKNOWN" in readme
    assert "datum mate" in readme
    assert "off-square miter = 90° - included corner angle / 2" in readme
    assert "{datum: cut_near, to: previous_member" in readme
    assert "not a nested `mate` wrapper" in readme
