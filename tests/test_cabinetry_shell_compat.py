"""B30 characterization oracle guarding the common-shell extraction.

The hashes were captured once from committed pre-refactor behavior at be76370.
The physical cabinetry hashes remain those compatibility facts. Base-language
payload hashes move only for reviewed base-schema additions or presentation-
only reader names; machine identities and the physical model hashes above must
remain stable.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from hashlib import sha256
import json
from pathlib import Path

from detailgen.packs import compile_project_file


FIXTURE = Path(__file__).parent / "fixtures/cabinetry/frameless_base_cabinet.project.yaml"


def _native(value):
    if is_dataclass(value):
        return _native(asdict(value))
    if isinstance(value, dict):
        return {
            str(key): _native(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_native(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_native(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    return value


def _hash(value) -> str:
    payload = json.dumps(
        _native(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return sha256(payload.encode()).hexdigest()


def test_existing_b30_model_and_lowering_are_refactor_stable():
    project = compile_project_file(FIXTURE)

    assert [part.role for part in project.model.parts] == [
        "left_end", "right_end", "bottom", "captured_back",
        "front_stretcher", "rear_stretcher", "anchor_strip",
        "adjustable_shelf", "door_left", "door_right", "toe_front",
        "toe_rear", "toe_left", "toe_right", "wall_stud_stud_32",
        "wall_stud_stud_48", "wall_anchor_stud_32", "wall_anchor_stud_48",
    ]
    assert _hash(project.model.parts) == (
        "c7c75914fe408b85ddfb2068173cf0005b147680e6fbae563881439de16102a8"
    )
    assert _hash(project.model.machining) == (
        "a16d823c3f9861e9b62d9ca1270d5a0b5ab9af5c587b86cf65dc40058b0c5233"
    )
    assert _hash(project.model.hardware) == (
        "79d9ba239096b0959b0268bd6e2806b55a2ea235af58bbc721a184f7d2e4ec87"
    )
    assert _hash(project.model.derived) == (
        "360fb7f04659bb861933ca9ff88f91041a436041f2b0744831f4f9863fd8917c"
    )
    assert _hash(project.lowered_doc) == (
        "507287f6628f320f8dae25b58d89cc9ff5d18c1b346d1f23461d9c79c0eaa93d"
    )


def test_existing_b30_findings_artifacts_and_manifests_are_refactor_stable():
    project = compile_project_file(FIXTURE)

    assert _hash(project.report.findings) == (
        "7b4c0c4180ed1025a3afb5242e72b34afeda67645d27354f17535a9afe5f63a9"
    )
    assert _hash(project.report.evidence) == (
        "3347c2a2f43cb88381b58ef806961c9fe3217760afb5bd6c2b708dde0df235f4"
    )
    assert _hash(project.artifacts.to_dict()) == (
        "7c73591bfa7df838ba0b6c477119ef5c9823a5663c18ded9ca41b94826ce2325"
    )
    assert _hash(project.manifest()) == (
        "66a573fe26e1de2e6b4f261069df5cf6d8ad37f58e919842c75efc1970bf5fbd"
    )

    project.require_release()

    assert _hash(project.artifacts.to_dict()) == (
        "9a6343eb919b70e9a4be92aae8631913d53ffe493f19ad2bcd64e6376bb7c43c"
    )
    assert _hash(project.manifest()) == (
        "5c659e4cee7bba24cb9a48fa4aefedf60ddc54fd17850d2e4b07ae0b059c5b21"
    )
