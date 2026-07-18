"""Risk-classified, bounded verification for public component additions."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest
import yaml

import detailgen.authoring.component_extension as component_extension
from detailgen.authoring.__main__ import main as authoring_main
from detailgen.authoring.component_extension import (
    CHANGE_CLASSES,
    COMPONENT_FAMILIES,
    ComponentExtensionError,
    build_component_context_route,
    build_component_extension_guide,
    load_component_extension_contract,
    verify_component_extension,
)


def _catalog_payload():
    return {
        "schema": "detailgen/component-extension/v1",
        "id": "nominal_2x2_lumber",
        "family": "stock_member",
        "change_class": "catalog_variant",
        "component": {
            "type": "lumber",
            "params": {"nominal": "2x2", "length": "24 in"},
        },
        "expect": {
            "dimensions": {
                "xlen": "24 in",
                "ylen": "1.5 in",
                "zlen": "1.5 in",
            },
            "datums": ["end_near", "end_far"],
            "capabilities": [],
            "material_key": "lumber_spf",
        },
    }


def _write_contract(tmp_path, payload):
    path = tmp_path / "component-extension.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _load(tmp_path, payload):
    return load_component_extension_contract(_write_contract(tmp_path, payload))


def _semantic_payload():
    return {
        "schema": "detailgen/component-extension/v1",
        "id": "exterior_wood_screw",
        "family": "fastener",
        "change_class": "semantic_component",
        "component": {
            "type": "wood_screw",
            "params": {
                "diameter": "0.16 in",
                "length": "2 in",
                "exposure": "exterior",
                "representation": "envelope",
            },
        },
        "expect": {
            "dimensions": {
                "xlen": "0.368 in",
                "ylen": "0.368 in",
                "zlen": "2.072 in",
            },
            "datums": ["head_bearing", "tip", "axis"],
            "capabilities": [
                "installation_fastener",
                "wood_screw",
                "ordinary_wood_screw",
                "exterior_use",
            ],
            "material_key": "steel_galv",
        },
        "reject": [{"params": {"exposure": "underwater"}}],
        "focused_tests": [
            "tests/test_component_capabilities.py::"
            "test_fastener_components_declare_required_capabilities"
        ],
    }


def test_component_extension_guide_separates_family_from_change_risk():
    guide = build_component_extension_guide()

    assert guide["schema"] == "detailgen/component-extension-guide/v1"
    assert set(guide["families"]) == set(COMPONENT_FAMILIES)
    assert "screws" in guide["families"]["fastener"]["examples"]
    assert "expected_evidence" in guide["families"]["connector"]
    assert guide["example_contract"]["schema"] \
        == "detailgen/component-extension/v1"
    assert guide["example_contract"]["component"]["type"] == "lumber"
    assert guide["change_classes"]["catalog_variant"]["lane"] == "micro"
    assert (
        guide["change_classes"]["semantic_component"]["budget_seconds"]
        == 60
    )
    assert (
        guide["change_classes"]["cross_layer_complex"]["result"]
        == "ESCALATE"
    )


def test_component_family_does_not_select_verification_lane():
    guide = build_component_extension_guide()

    assert "fastener" in guide["families"]
    assert set(guide["change_classes"]) == set(CHANGE_CLASSES)
    assert "family" in guide["contract_required"]
    assert "change_class" in guide["contract_required"]


def test_loads_catalog_contract_as_immutable_normalized_data(tmp_path):
    contract = load_component_extension_contract(
        _write_contract(tmp_path, _catalog_payload())
    )

    assert contract.id == "nominal_2x2_lumber"
    assert contract.family == "stock_member"
    assert contract.change_class == "catalog_variant"
    assert contract.component_type == "lumber"
    assert contract.params["nominal"] == "2x2"
    assert contract.dimensions["xlen"] == "24 in"
    assert contract.focused_tests == ()


def test_registered_catalog_variant_selects_bounded_context(tmp_path):
    route = build_component_context_route(
        _load(tmp_path, _catalog_payload())
    )

    assert route["schema"] == "detailgen/component-context-route/v1"
    assert route["route"] == "catalog_micro"
    assert route["context_budget_seconds"] == 30
    assert route["required_verification"] == "component-check"
    assert route["allowed_reads"] == [
        "the component-extension YAML contract",
        "the exact registered component declaration",
        "the closest catalog declaration and its focused test",
    ]


def test_context_route_results_do_not_share_mutable_read_lists(tmp_path):
    contract = _load(tmp_path, _catalog_payload())
    first = build_component_context_route(contract)
    first["allowed_reads"].append("README.md")

    second = build_component_context_route(contract)

    assert "README.md" not in second["allowed_reads"]


def test_unknown_component_selects_full_context(tmp_path):
    payload = _catalog_payload()
    payload["component"] = {
        "type": "unimplemented_component",
        "params": {"length": "24 in"},
    }
    route = build_component_context_route(_load(tmp_path, payload))

    assert route["route"] == "full_extension"
    assert route["context_budget_seconds"] is None
    assert route["allowed_reads"] == []
    assert route["required_verification"] == "full-extension-workflow"


def test_zipline_platform_complex_contract_uses_full_context_with_known_lumber(
    tmp_path,
):
    payload = _catalog_payload()
    payload["id"] = "zipline_platform"
    payload["change_class"] = "cross_layer_complex"
    payload["expect"] = {}

    route = build_component_context_route(_load(tmp_path, payload))

    assert route["component_type"] == "lumber"
    assert route["route"] == "full_extension"
    assert route["reason"] == (
        "cross_layer_complex requires the full extension workflow"
    )


def test_primitive_and_semantic_components_select_full_context(tmp_path):
    primitive = _catalog_payload()
    primitive["change_class"] = "new_primitive"
    primitive["reject"] = [{"params": {"length": "-1 in"}}]

    assert build_component_context_route(
        _load(tmp_path, primitive)
    )["route"] == "full_extension"
    assert build_component_context_route(
        _load(tmp_path, _semantic_payload())
    )["route"] == "full_extension"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema", "detailgen/component-extension/v9", "schema"),
        ("family", "furniture-ish", "known families"),
        ("change_class", "small", "known change classes"),
        ("change_class", ["small"], "known change classes"),
    ],
)
def test_rejects_unknown_contract_vocabulary(
    tmp_path, field, value, message,
):
    payload = _catalog_payload()
    payload[field] = value

    with pytest.raises(ComponentExtensionError, match=message):
        load_component_extension_contract(_write_contract(tmp_path, payload))


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (("top", "surprise"), "unknown fields"),
        (("expect", "weight"), "expect has unknown fields"),
        (("dimensions", "volume"), "dimension keys"),
    ],
)
def test_rejects_unknown_contract_fields(tmp_path, mutation, message):
    payload = _catalog_payload()
    owner, field = mutation
    if owner == "top":
        payload[field] = True
    elif owner == "expect":
        payload["expect"][field] = "10 lb"
    else:
        payload["expect"]["dimensions"][field] = 10

    with pytest.raises(ComponentExtensionError, match=message):
        load_component_extension_contract(_write_contract(tmp_path, payload))


def test_fast_lanes_require_all_three_dimensions(tmp_path):
    payload = _catalog_payload()
    del payload["expect"]["dimensions"]["zlen"]

    with pytest.raises(ComponentExtensionError, match="xlen.*ylen.*zlen"):
        load_component_extension_contract(_write_contract(tmp_path, payload))


def test_new_primitive_requires_invalid_parameter_probe(tmp_path):
    payload = _catalog_payload()
    payload["change_class"] = "new_primitive"

    with pytest.raises(ComponentExtensionError, match="reject.*required"):
        load_component_extension_contract(_write_contract(tmp_path, payload))


def test_semantic_component_requires_semantics_and_focused_test(tmp_path):
    payload = _catalog_payload()
    payload["change_class"] = "semantic_component"
    payload["reject"] = [{"params": {"nominal": "unknown"}}]
    payload["expect"]["datums"] = ["origin"]

    with pytest.raises(
        ComponentExtensionError,
        match="capability or non-origin datum",
    ):
        load_component_extension_contract(_write_contract(tmp_path, payload))

    payload["expect"]["capabilities"] = ["wood_screw"]
    with pytest.raises(ComponentExtensionError, match="focused_tests"):
        load_component_extension_contract(_write_contract(tmp_path, payload))


@pytest.mark.parametrize(
    "focused_tests",
    [
        ["pytest tests/test_registry.py"],
        ["tests/test_registry.py"],
        [f"tests/test_registry.py::test_{index}" for index in range(9)],
    ],
)
def test_focused_tests_are_bounded_explicit_node_ids(tmp_path, focused_tests):
    payload = deepcopy(_catalog_payload())
    payload["change_class"] = "semantic_component"
    payload["reject"] = [{"params": {"nominal": "unknown"}}]
    payload["expect"]["capabilities"] = ["wood_screw"]
    payload["focused_tests"] = focused_tests

    with pytest.raises(ComponentExtensionError, match="focused_tests"):
        load_component_extension_contract(_write_contract(tmp_path, payload))


def test_catalog_verifier_compiles_and_checks_real_nominal_2x2(tmp_path):
    result = verify_component_extension(
        _load(tmp_path, _catalog_payload()), repo_root=tmp_path
    )

    assert result["status"] == "PASS"
    assert result["lane"] == "micro"
    assert result["budget_seconds"] == 60
    assert result["elapsed_seconds"] < 60
    assert result["context_route"] == build_component_context_route(
        _load(tmp_path, _catalog_payload())
    )
    assert {
        "public_compile",
        "component_check",
        "positive_geometry",
        "dimensions",
        "datums",
        "capabilities",
        "material",
        "bom_identity",
    } <= set(result["checks"])


def test_verifier_fails_on_wrong_dimension(tmp_path):
    payload = _catalog_payload()
    payload["expect"]["dimensions"]["ylen"] = "2 in"

    with pytest.raises(ComponentExtensionError, match="ylen.*expected.*2 in"):
        verify_component_extension(_load(tmp_path, payload), repo_root=tmp_path)


def test_primitive_reject_probe_must_actually_reject(tmp_path):
    payload = _catalog_payload()
    payload["change_class"] = "new_primitive"
    payload["reject"] = [{"params": {"length": "12 in"}}]

    with pytest.raises(ComponentExtensionError, match=r"reject\[0\].*did not reject"):
        verify_component_extension(_load(tmp_path, payload), repo_root=tmp_path)


def test_semantic_verifier_runs_explicit_tests_without_shell(tmp_path, monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="1 passed", stderr="")

    monkeypatch.setattr(component_extension.subprocess, "run", fake_run)
    result = verify_component_extension(
        _load(tmp_path, _semantic_payload()), repo_root=tmp_path
    )

    assert result["status"] == "PASS"
    assert result["lane"] == "semantic"
    assert "focused_tests" in result["checks"]
    argv, kwargs = calls[0]
    assert argv[:3] == [component_extension.sys.executable, "-m", "pytest"]
    assert argv[-1] == "-q"
    assert "shell" not in kwargs
    assert kwargs["cwd"] == tmp_path.resolve()


def test_semantic_verifier_fails_when_focused_test_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(
        component_extension.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="FAILED consumer", stderr=""
        ),
    )

    with pytest.raises(ComponentExtensionError, match="focused tests failed"):
        verify_component_extension(
            _load(tmp_path, _semantic_payload()), repo_root=tmp_path
        )


def test_fast_lane_budget_is_enforced(tmp_path):
    ticks = iter((0.0, 61.0))

    with pytest.raises(ComponentExtensionError, match="exceeded.*60"):
        verify_component_extension(
            _load(tmp_path, _catalog_payload()),
            repo_root=tmp_path,
            clock=lambda: next(ticks),
        )


def test_complex_contract_escalates_without_building_or_running_tests(
    tmp_path, monkeypatch,
):
    payload = _catalog_payload()
    payload["change_class"] = "cross_layer_complex"
    payload["component"]["type"] = "unimplemented_anchor_system"
    payload["expect"] = {}
    payload["focused_tests"] = [
        "tests/test_registry.py::test_unknown_component"
    ]
    monkeypatch.setattr(
        component_extension,
        "_compile_component",
        lambda *args, **kwargs: pytest.fail("complex probe built CAD"),
        raising=False,
    )
    monkeypatch.setattr(
        component_extension.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("complex probe ran tests"),
    )

    result = verify_component_extension(
        _load(tmp_path, payload), repo_root=tmp_path
    )

    assert result["status"] == "ESCALATE"
    assert result["lane"] == "escalated"
    assert result["budget_seconds"] is None
    assert result["checks"] == ["contract_schema"]


def test_verifier_wraps_unexpected_component_contract_crash(tmp_path, monkeypatch):
    class BrokenComponent:
        def check(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        component_extension,
        "_compile_component",
        lambda contract: BrokenComponent(),
    )

    with pytest.raises(
        ComponentExtensionError,
        match="component verification failed.*boom",
    ):
        verify_component_extension(
            _load(tmp_path, _catalog_payload()), repo_root=tmp_path
        )


def test_component_guide_cli_prints_bounded_public_contract(capsys):
    assert authoring_main(["component-guide"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result == build_component_extension_guide()


def test_component_route_cli_classifies_without_building_cad(
    tmp_path, capsys, monkeypatch,
):
    contract_path = _write_contract(tmp_path, _catalog_payload())
    monkeypatch.setattr(
        component_extension,
        "_compile_component",
        lambda *args, **kwargs: pytest.fail("route command built CAD"),
    )

    assert authoring_main(["component-route", str(contract_path)]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["route"] == "catalog_micro"


def test_component_route_cli_fails_closed_on_invalid_contract(tmp_path, capsys):
    payload = _catalog_payload()
    payload["schema"] = "detailgen/component-extension/v9"
    contract_path = _write_contract(tmp_path, payload)

    assert authoring_main(["component-route", str(contract_path)]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error["schema"] == "detailgen/component-extension-error/v1"


def test_component_check_cli_verifies_catalog_contract(tmp_path, capsys):
    contract_path = _write_contract(tmp_path, _catalog_payload())

    assert authoring_main(["component-check", str(contract_path)]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["schema"] == "detailgen/component-extension-result/v1"
    assert result["status"] == "PASS"
    assert result["lane"] == "micro"


def test_component_check_cli_returns_structured_error(tmp_path, capsys):
    payload = _catalog_payload()
    payload["family"] = "mystery"
    contract_path = _write_contract(tmp_path, payload)

    assert authoring_main(["component-check", str(contract_path)]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error["schema"] == "detailgen/component-extension-error/v1"
    assert "known families" in error["error"]


def test_component_check_cli_returns_nonzero_escalation(tmp_path, capsys):
    payload = _catalog_payload()
    payload["change_class"] = "cross_layer_complex"
    payload["component"]["type"] = "unimplemented_anchor_system"
    payload["expect"] = {}
    contract_path = _write_contract(tmp_path, payload)

    assert authoring_main(["component-check", str(contract_path)]) == 3

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "ESCALATE"
