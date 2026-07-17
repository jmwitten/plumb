# Mandatory product-gate integrity design

## Problem

A named product gate currently proves only that selected pytest markers collectively
claim every semantic contract label. Those labels are self-attested by test authors.
A bespoke test can therefore claim `validation`, `geometry`, or `documents` while
checking only selected fields or file existence. The 2x4-triangle benchmark exposed
this gap: its gate was complete by label without generic certification or package
manifest reconciliation.

## Boundary

The gate runner will add mandatory evidence checks when a requested owner has a
canonical standalone subject. Resolution is deterministic:

1. a discovered certification contract with the requested slug binds its
   `subject.source`;
2. otherwise `details/<slug>.spec.yaml` or the hyphen-to-underscore normalized
   equivalent binds the subject;
3. otherwise the existing legacy alias remains unchanged.

The third case preserves established owners such as composite zipline gates whose
scope owner does not map one-to-one to a standalone spec. It is an explicit migration
limitation, not evidence that those gates gained automatic integrity.

## Inner cadence

Before the first selected product test runs, the automatic integrity check compiles
the canonical spec, calls authoritative validation, and requires both
`validation.ok is True` and zero blocking findings. Failure reports the named gate,
spec path, and blocking findings. This evidence is automatic and cannot be supplied
by a bespoke marker label.

## Release cadence

Release repeats the inner check and requires
`build/<slug>/package-manifest.json`. It validates:

- the existing `detailgen/package-manifest/v1` schema and the manifest's preview or
  delivery lifecycle value;
- exact spec filename identity;
- `validation.ok is True` and `blocking_count == 0`;
- current compiled `assembly_hash` and, when present, current governance selection
  and model fingerprints;
- exact artifact closure: every declared relative path exists, no undeclared file is
  present, no path escapes the package root, and every SHA-256 digest matches.

Preview remains preview and delivery remains delivery. The verifier does not rewrite
the manifest, relabel skipped/not-run tests as passed, or require a delivery package
for an inner gate. A delivery manifest must still satisfy the detail's delivery-ready
lifecycle gate; a preview manifest must satisfy the same modeling-approval boundary
used by package generation.

The v1 manifest has no persisted spec-content digest. The verifier therefore checks
the schema's current spec identity field and uses the current compiled assembly hash
for model freshness. It does not invent a hidden spec-hash convention.

## Structure

`tests/product_gate_integrity.py` owns pure binding, compile/validation, and package
verification helpers. `tests/conftest.py` owns only pytest activation and invokes the
helper once per requested named gate after test-cache isolation is active.

## Verification

Focused tests cover canonical resolution, legacy non-binding, blocking validation,
spec/model identity, governance fingerprints, path safety, exact artifact closure,
artifact digests, preview/delivery lifecycle behavior, and automatic cadence routing.
One existing canonical product inner gate proves integration without running the full
suite.
