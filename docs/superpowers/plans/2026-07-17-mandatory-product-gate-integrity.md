# Mandatory Product-Gate Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make named standalone-product gates automatically prove current validation and release-package integrity instead of trusting bespoke contract labels.

**Architecture:** A focused test-support module resolves a named gate to a canonical standalone spec, validates the freshly compiled model, and reconciles release packages against their manifest. A small autouse pytest fixture invokes it once for the requested cadence; owners without a canonical standalone binding retain their legacy behavior explicitly.

**Tech Stack:** Python 3.11+, pytest, existing DetailSpec compiler, package-manifest/v1, SHA-256.

## Global Constraints

- Certification-contract subject binding takes precedence over filename fallback.
- Filename fallback accepts exact slugs and hyphen-to-underscore normalization only.
- Inner cadence must require authoritative `validation.ok` and zero blockers.
- Release cadence must additionally require package validation, exact artifact closure and hashes, spec identity, and current model/fingerprint identity supported by manifest v1.
- Preview and delivery lifecycle semantics remain distinct.
- No triangle-specific product names or behavior.
- Legacy aliases without a canonical binding remain unchanged and documented.

---

### Task 1: Canonical subject and inner integrity

**Files:**
- Create: `tests/product_gate_integrity.py`
- Create: `tests/test_product_gate_integrity.py`

**Interfaces:**
- Consumes: `discover_contracts`, `compile_spec_file`, and `build_manifest`.
- Produces: `resolve_product_subject(slug, details_dir, repo_root) -> Path | None` and `verify_inner_integrity(slug, spec_path) -> CurrentProductEvidence`.

- [ ] **Step 1: Write failing resolution and validation tests**

Cover explicit certification precedence, normalized fallback, `None` for a legacy
alias, clean compilation, and actionable rejection when `report.ok` is false or
`report.blocking` is non-empty.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_product_gate_integrity.py -q`
Expected: collection fails because `product_gate_integrity` does not exist.

- [ ] **Step 3: Implement the minimal resolver and inner verifier**

Return immutable current evidence containing the detail, assembly hash, and current
governance fingerprints. Raise `ProductGateIntegrityError` with gate and spec context
for compile or validation failure.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `python -m pytest tests/test_product_gate_integrity.py -q`
Expected: all Task 1 tests pass.

### Task 2: Release manifest and artifact reconciliation

**Files:**
- Modify: `tests/product_gate_integrity.py`
- Modify: `tests/test_product_gate_integrity.py`

**Interfaces:**
- Consumes: `CurrentProductEvidence` from Task 1 and `build/<slug>/package-manifest.json`.
- Produces: `verify_release_integrity(slug, spec_path, package_dir) -> None`.

- [ ] **Step 1: Write failing package-integrity tests**

Create a minimal package fixture and require rejection for bad validation status,
wrong spec, stale assembly hash, stale optional governance fingerprints, missing or
extra artifacts, unsafe/duplicate paths, and bad artifact hashes. Require acceptance
for both valid preview and delivery manifests while asserting the corresponding
lifecycle method is called.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_product_gate_integrity.py -q`
Expected: release cases fail because `verify_release_integrity` is absent.

- [ ] **Step 3: Implement fail-closed manifest verification**

Parse strict JSON, validate manifest-v1 fields, enforce lifecycle, compare current
model/fingerprint identity, normalize paths relative to the package root, compare the
declared and actual file sets, and hash every declared artifact.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `python -m pytest tests/test_product_gate_integrity.py -q`
Expected: all Task 1 and Task 2 tests pass.

### Task 3: Automatic pytest activation and documentation

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_detail_gate_selection.py`
- Modify: `tests/test_scope_manifest.csv`
- Modify: `README.md`

**Interfaces:**
- Consumes: requested `--detail-gate`, `--detail-cadence`, and Task 1/2 helpers.
- Produces: `_verify_requested_product_integrity(config, root, details_dir)` invoked once per requested gate by an autouse fixture.

- [ ] **Step 1: Write failing cadence-routing tests**

Assert no action without a named gate, no action for an unresolved legacy alias,
inner routing to `verify_inner_integrity`, release routing to
`verify_release_integrity`, and certification binding precedence.

- [ ] **Step 2: Run routing tests and verify RED**

Run: `python -m pytest tests/test_detail_gate_selection.py -q`
Expected: tests fail because the routing helper does not exist.

- [ ] **Step 3: Wire the automatic fixture and document the contract**

Invoke the routing helper once after per-test cache isolation. Document the canonical
binding rules, inner requirements, release package prerequisite, exact closure, and
the legacy-alias limitation. Classify new harness tests as platform unit tests in the
scope manifest.

- [ ] **Step 4: Run focused and product integration verification**

Run: `python -m pytest tests/test_product_gate_integrity.py tests/test_detail_gate_selection.py tests/test_scope_manifest.py -q`
Expected: all selected tests pass.

Run: `python -m pytest --detail-gate armchair_caddy --detail-cadence inner -q`
Expected: named gate passes with automatic fresh validation evidence.

- [ ] **Step 5: Commit and push**

```bash
git add README.md docs/superpowers tests
git commit -m "feat: enforce automatic product gate integrity"
git push -u origin codex/mandatory-product-integrity
```
