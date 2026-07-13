"""Tests for task PROMOTE — the platform ConnectionTypes moved into the
library (``detailgen.assemblies.connection``) + registered, plus the two
W2-6 rider fixes:

- 4a: ``required_hardware`` confidence tracks WHO produced the list — the
  base pass-through is "official", an overriding (inferring) hook is
  "inferred", never silently mis-tagged.
- 4b: positional hardware unpack is guarded — a wrong-order (same-count) or
  wrong-count declaration is a HARD diagnostic, not a plausible-but-wrong
  derived fact.
"""

import pytest

from detailgen.core import IN
from detailgen.core.registry import UnknownEntryError
from detailgen.components import (
    HexBolt, HexNut, Washer, StructuralScrew, JoistHanger, Lumber,
)
from detailgen.assemblies import (
    BoltedClamp, Connection, ConnectionType, DetailAssembly,
    FaceMountHanger, RailCapScrewed, ThreadedRodEpoxyAnchor, ToeScrewed,
    connection_types,
)


# -- registry: every promoted type is discoverable by name -------------------

def test_promoted_types_registered_alongside_originals():
    assert connection_types.get("face_mount_hanger") is FaceMountHanger
    assert connection_types.get("toe_screwed") is ToeScrewed
    assert connection_types.get("rail_cap_screwed") is RailCapScrewed
    # the two originally-shipped types still resolve, unchanged.
    assert connection_types.get("bolted_clamp") is BoltedClamp
    assert connection_types.get("threaded_rod_epoxy_anchor") is ThreadedRodEpoxyAnchor
    assert set(connection_types.names()) >= {
        "face_mount_hanger", "toe_screwed", "rail_cap_screwed",
        "bolted_clamp", "threaded_rod_epoxy_anchor",
    }


def test_unknown_connection_type_did_you_mean():
    with pytest.raises(UnknownEntryError, match="did you mean") as exc:
        connection_types.get("face_mount_hangr")   # one-char typo
    assert "face_mount_hanger" in str(exc.value)


# -- rider 4a: required_hardware confidence scoping --------------------------

def _one_pair_assembly():
    a = DetailAssembly("t")
    p0 = a.add(Lumber("2x6", 10 * IN, name="p0"))
    p1 = a.add(Lumber("2x6", 10 * IN, name="p1"))
    return a, p0, p1


class _NoopType(ConnectionType):
    label = "noop"


def test_hardware_confidence_official_for_base_passthrough():
    """The base ``required_hardware`` returns declared hardware verbatim — an
    author-declared fact — so its DerivedFacts are tagged "official"."""
    a, p0, p1 = _one_pair_assembly()
    nut = a.add(HexNut(0.5 * IN, name="declared nut"))
    conn = Connection(kind=_NoopType(), parts=[p0, p1], hardware=[nut], label="c")
    checks = conn.generate_checks(a)
    hw_facts = [f for f in checks.derived if f.rule.endswith(".required_hardware")]
    assert hw_facts and all(f.confidence == "official" for f in hw_facts)


def test_hardware_confidence_inferred_when_hook_overridden():
    """A subclass that OVERRIDES ``required_hardware`` to INFER hardware
    beyond what was declared must have its requirement facts tagged
    "inferred" — the bug the rider fixes was hardcoding "official" regardless
    of the producing rule."""
    a, p0, p1 = _one_pair_assembly()
    inferred = a.add(HexNut(0.5 * IN, name="inferred nut"))

    class _InfersHardware(ConnectionType):
        label = "infers"

        def required_hardware(self, conn):
            return list(conn.hardware) + [inferred]   # NOT a pass-through

    conn = Connection(kind=_InfersHardware(), parts=[p0, p1], label="c")
    checks = conn.generate_checks(a)
    hw_facts = [f for f in checks.derived if f.rule.endswith(".required_hardware")]
    assert hw_facts and all(f.confidence == "inferred" for f in hw_facts)


# -- rider 4b: positional-unpack role/count guards ---------------------------

def _bolted_clamp_parts():
    a = DetailAssembly("t")
    bolt = a.add(HexBolt(0.5 * IN, 4 * IN, name="bolt"))
    hw = a.add(Washer(0.5 * IN, name="head washer"))
    nw = a.add(Washer(0.5 * IN, name="nut washer"))
    nut = a.add(HexNut(0.5 * IN, name="nut"))
    p0 = a.add(Lumber("2x6", 10 * IN, name="p0"))
    p1 = a.add(Lumber("2x6", 10 * IN, name="p1"))
    return a, (bolt, hw, nw, nut), (p0, p1)


def test_bolted_clamp_correct_order_unpacks():
    _a, (bolt, hw, nw, nut), (p0, p1) = _bolted_clamp_parts()
    kind = BoltedClamp(axis="Y", hardware_area=40, end_plate_area=60)
    conn = Connection(kind=kind, parts=[p0, p1], hardware=[bolt, hw, nw, nut])
    assert kind._unpack(conn) == (bolt, hw, nw, nut)   # no raise


def test_bolted_clamp_wrong_order_same_count_raises():
    """Washer where the bolt is expected (same count, wrong order) — the
    exact wrong-order-same-count case the rider flagged."""
    _a, (bolt, hw, nw, nut), (p0, p1) = _bolted_clamp_parts()
    kind = BoltedClamp(axis="Y", hardware_area=40, end_plate_area=60)
    conn = Connection(kind=kind, parts=[p0, p1], hardware=[hw, bolt, nw, nut])
    with pytest.raises(ValueError, match="slot 0 must be a HexBolt"):
        kind._unpack(conn)


def test_bolted_clamp_wrong_count_raises():
    _a, (bolt, hw, nw, nut), (p0, p1) = _bolted_clamp_parts()
    kind = BoltedClamp(axis="Y", hardware_area=40, end_plate_area=60)
    conn = Connection(kind=kind, parts=[p0, p1], hardware=[bolt, hw, nut])
    with pytest.raises(ValueError, match="expected 4 hardware"):
        kind._unpack(conn)


def _hanger_parts(n_header=1, n_hung=1):
    a = DetailAssembly("t")
    header = a.add(Lumber("2x6", 10 * IN, name="header"))
    hung = a.add(Lumber("2x6", 10 * IN, name="hung"))
    hanger = a.add(JoistHanger(1.5 * IN, 5.5 * IN, name="hanger"))
    screws = [a.add(StructuralScrew(0.157 * IN, 1.5 * IN, name=f"s{i}"))
              for i in range(n_header + n_hung)]
    return a, header, hung, hanger, screws


def test_face_mount_hanger_correct_order_unpacks():
    _a, header, hung, hanger, screws = _hanger_parts(1, 1)
    kind = FaceMountHanger(seat_axis="Z", seat_area=60,
                           n_header_screws=1, n_hung_screws=1)
    conn = Connection(kind=kind, parts=[header, hung], hardware=[hanger, *screws])
    h, u, hg, hs, us = kind._unpack(conn)
    assert (h, u, hg) == (header, hung, hanger)
    assert hs == [screws[0]] and us == [screws[1]]


def test_face_mount_hanger_screw_in_hanger_slot_raises():
    _a, header, hung, hanger, screws = _hanger_parts(1, 1)
    kind = FaceMountHanger(seat_axis="Z", seat_area=60,
                           n_header_screws=1, n_hung_screws=1)
    # a screw where the hanger belongs (slot 0)
    conn = Connection(kind=kind, parts=[header, hung],
                      hardware=[screws[0], hanger, screws[1]])
    with pytest.raises(ValueError, match="slot 0 must be a JoistHanger"):
        kind._unpack(conn)


def test_face_mount_hanger_wrong_screw_count_raises():
    _a, header, hung, hanger, screws = _hanger_parts(1, 1)
    kind = FaceMountHanger(seat_axis="Z", seat_area=60,
                           n_header_screws=1, n_hung_screws=1)
    conn = Connection(kind=kind, parts=[header, hung], hardware=[hanger, screws[0]])
    with pytest.raises(ValueError, match="expected 3 hardware"):
        kind._unpack(conn)


def test_toe_screwed_non_screw_hardware_raises():
    a = DetailAssembly("t")
    header = a.add(Lumber("2x6", 10 * IN, name="header"))
    hung = a.add(Lumber("2x6", 10 * IN, name="hung"))
    good = a.add(StructuralScrew(0.157 * IN, 1.5 * IN, name="screw"))
    impostor = a.add(HexBolt(0.5 * IN, 2 * IN, name="not a screw"))
    kind = ToeScrewed(n_screws=2)
    ok = Connection(kind=kind, parts=[header, hung],
                    hardware=[good, a.add(StructuralScrew(0.157 * IN, 1.5 * IN, name="s2"))])
    assert kind._unpack(ok)[0] is header    # no raise on the all-screw case
    bad = Connection(kind=kind, parts=[header, hung], hardware=[good, impostor])
    with pytest.raises(ValueError, match="must be a StructuralScrew"):
        kind._unpack(bad)


def test_rail_cap_screwed_non_screw_hardware_raises():
    a = DetailAssembly("t")
    support = a.add(Lumber("2x4", 10 * IN, name="support"))
    cap = a.add(Lumber("2x4", 10 * IN, name="cap"))
    impostor = a.add(Washer(0.5 * IN, name="washer, not a screw"))
    kind = RailCapScrewed(n_screws=1)
    bad = Connection(kind=kind, parts=[support, cap], hardware=[impostor])
    with pytest.raises(ValueError, match="must be a StructuralScrew"):
        kind._unpack(bad)
