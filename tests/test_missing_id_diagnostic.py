"""TRIAGE rider (task W31): a validation-spec reference to a part that is
not in the assembly must be a hard, self-explaining DIAGNOSTIC — naming the
bad reference and offering did-you-mean suggestions — not a bare crash.

Reproduced from the RAILFASTEN review: an ``expected_overlaps`` entry that
names a missing id raised an unhandled ``KeyError`` deep in
``_stage_interference`` via ``assembly._resolve``.
"""

import pytest

from detailgen.assemblies.assembly import DetailAssembly, SpecReferenceError
from detailgen.components.lumber import Lumber
from detailgen.core.units import IN
from detailgen.validation import validate_assembly


def _two_beam_assembly() -> DetailAssembly:
    d = DetailAssembly("triage")
    d.add(Lumber("2x4", length=24 * IN, name="beam"), at=(0, 0, 0))
    d.add(Lumber("2x4", length=24 * IN, name="ledger"), at=(0, 10 * IN, 0))
    return d


def test_expected_overlaps_missing_id_raises_hard_diagnostic():
    """The reproduction: expected_overlaps names a part that isn't present."""
    d = _two_beam_assembly()
    with pytest.raises(SpecReferenceError) as exc:
        validate_assembly(d, expected_overlaps={("beam", "ledgr")})
    msg = str(exc.value)
    # names the bad reference verbatim
    assert "ledgr" in msg
    # did-you-mean suggestion for the near-miss part name
    assert "ledger" in msg
    assert "did you mean" in msg.lower()


def test_diagnostic_is_a_keyerror_subclass_for_backward_compat():
    """Existing ``except KeyError`` / ``pytest.raises(KeyError)`` callers keep
    working; the diagnostic only enriches the message."""
    assert issubclass(SpecReferenceError, KeyError)
    d = _two_beam_assembly()
    with pytest.raises(KeyError, match="known parts"):
        validate_assembly(d, expected_overlaps={("beam", "ledgr")})


def test_diagnostic_message_is_not_repr_wrapped():
    """A plain ``KeyError`` stringifies its message wrapped in ``repr`` (escaped
    quotes, unreadable in a traceback). The diagnostic reads as prose."""
    d = _two_beam_assembly()
    with pytest.raises(SpecReferenceError) as exc:
        validate_assembly(d, expected_overlaps={("beam", "ledgr")})
    # a repr-wrapped message would start and end with an escaped quote
    assert not str(exc.value).startswith("\"")


def test_no_close_match_still_names_the_reference_and_known_parts():
    d = _two_beam_assembly()
    with pytest.raises(SpecReferenceError) as exc:
        validate_assembly(d, expected_overlaps={("beam", "zzzzz")})
    msg = str(exc.value)
    assert "zzzzz" in msg
    assert "known parts" in msg
