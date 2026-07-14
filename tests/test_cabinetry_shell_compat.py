"""B30 characterization oracle guarding the common-shell extraction.

The hashes were captured once from committed pre-refactor behavior at be76370.
The pins remain deliberate compatibility facts. Physical hashes moved in v1.1
only for the reviewed toe-base correction: the rear rail now sits under solid
bottom stock ahead of the captured-back groove and two executable attachment
rows replace an impossible prose-only connection.
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
    # v1.1 moves the rear toe rail ahead of the captured-back groove and
    # shortens both returns so the three rear attachment screws have a solid,
    # centered receiver instead of landing on the bottom back edge.
    assert _hash(project.model.parts) == (
        "0fbb8f9f4e7ed1a95eb7e1cefaa808420b1990c56468135f01253f4d2eb22721"
    )
    # Re-pinned after the executable Confirmat schedule correction: every
    # location now names its physical face/datum, pitch axis, and receiver;
    # the two toe sleepers are separate in-bounds groups rather than one
    # ambiguous four-hole row.
    assert _hash(project.model.machining) == (
        "26afa4ded71bb67cfba3cd92acdce38897ed9b355b2e6a5855baf4a32f8ff682"
    )
    # Re-pinned because the Confirmat row now cites the exact current Häfele
    # product page instead of an unrelated regional catalog PDF.
    assert _hash(project.model.hardware) == (
        "2dda0a1d8db7d59978ca035f93c87f5755b4f7e7cad972c3c64683ae5d9681cb"
    )
    assert _hash(project.model.derived) == (
        "360fb7f04659bb861933ca9ff88f91041a436041f2b0744831f4f9863fd8917c"
    )
    assert _hash(project.lowered_doc) == (
        "f5a75c26e5d7e404772251344ec2bdf98b77fdd83a8c43928fa36708a8101bdf"
    )


def test_existing_b30_findings_artifacts_and_manifests_are_refactor_stable():
    project = compile_project_file(FIXTURE)

    # Deliberate v1.1 validation expansion: impossible shell machining is now
    # a required release failure instead of an unchecked generator assumption.
    assert project.report.by_rule(
        "cabinetry.joinery.shell_machining"
    ).verdict == "PASS"
    assert _hash(project.report.findings) == (
        "058ba99e429991039af5497aec74d4c0ee43323b04d530e5595a045956880728"
    )
    assert _hash(project.report.evidence) == (
        "6c87e84d3b38ec60f6103240567be3a7d3aae708bd5b61b006d76c6de1dff7cc"
    )
    # Artifact v2 adds pre-band cut sizes/edge-band build, centralized
    # procurement meaning, and the executable toe-attachment layout.
    assert project.artifacts.schema == "detailgen/cabinetry-artifacts/v2"
    assert _hash(project.artifacts.to_dict()) == (
        "6b3bf6b6d1fd3740d7d7e83aa664218ef0692b528cdd35163a30c9871838ee0d"
    )
    assert _hash(project.manifest()) == (
        "c458a693da6adf22933af43aae3c029f25a5765b9844cd9ac77321c436e87d64"
    )

    project.require_release()

    assert _hash(project.artifacts.to_dict()) == (
        "aecee03c31d89881d1d1a3dc2e26b1d262cf45524424475748403a6b8d5b103d"
    )
    assert _hash(project.manifest()) == (
        "8bfd20da9bff3849a30bdab74e1f9a80992d1c469814c3a88b8af77369d1d3c1"
    )
