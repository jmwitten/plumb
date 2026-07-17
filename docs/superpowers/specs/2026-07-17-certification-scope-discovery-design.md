# Certification Scope Discovery Design

## Problem

Plumb's generic certification engine discovers `details/<slug>.cert.yaml` and
creates a parametrized product test without product-specific Python. Pytest's
runtime scope selection still requires a matching row in
`tests/test_scope_manifest.csv`, however. A newly discovered contract is
therefore invisible to `--detail-gate <slug>` until a central CSV row is added,
contradicting the certification contract's registry-free authoring model.

This did not cause the triangle benchmark to exceed eight minutes: its test
registration was complete within roughly 48 seconds, while blocking physical
overlaps remained through the deadline. It does create unnecessary setup and
makes bespoke tests more attractive than the safer generic certification path.

## Design

At pytest runtime, augment the explicit scope-manifest records with one derived
inner-cadence record for every discovered certification contract whose generic
certification node is not already explicit. The derived node identity is:

`tests/test_certified_builds.py::test_certified_build[<slug>]`

Explicit rows take precedence. Existing repositories therefore retain their
current rationales and ownership without duplicate records, while a new
contract becomes selectable immediately from its slug alone.

Both named-gate selection and ordinary full-collection reconciliation consume
the same augmented record set. This keeps the fail-closed drift check intact:
generic certification parameters are classified automatically, while every
other new test still requires an explicit manifest row.

## Boundaries

- Do not infer scope for arbitrary parametrized or bespoke tests.
- Do not change certification rules, product release/document semantics, or
  platform-tier selection.
- Do not add product names or triangle-specific behavior.
- Invalid or duplicate certification contracts continue to fail through the
  existing strict discovery path.

## Verification

Focused tests prove that an unregistered contract produces the expected inner
scope record, an explicit row is not duplicated or replaced, and full
reconciliation accepts the derived node while still rejecting unrelated drift.
The existing detail-gate, scope-manifest, certification, and authoring-manifest
tests provide the compatibility boundary.
