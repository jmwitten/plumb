# Fail-Closed Scaffold Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the generic DetailSpec scaffolder from publishing a model with definite validation failures and report every blocker with datum-mate guidance.

**Architecture:** Keep the existing scaffold compile/build/validate pipeline, retain the returned `ValidationReport`, and reject only `report.failures` before document publication. Use canonical `Finding.__str__` output so every current and future definite failure remains complete and ordered; continue permitting honest `UNKNOWN` findings.

**Tech Stack:** Python 3.12, existing DetailSpec compiler and validation model, PyYAML, pytest.

## Global Constraints

- Reject every definite validation `FAIL` before scaffold publication.
- Include every canonical failed finding in report order.
- Include generic guidance to use `datum`, `to`, and `to_datum` for neighbor-seated parts and reserve `raw` for global measurements or genuine free degrees of freedom.
- Permit `UNKNOWN` findings; do not relabel them as passing.
- Do not infer angles, datums, placements, geometry, or validation claims.
- Do not add a loop solver, frame archetype, product template, or product-specific branch.
- Preserve transactional output behavior and the existing raw-placement escape hatch.

---

### Task 1: Fail Closed on Definite Scaffold Validation Failures

**Files:**
- Modify: `tests/test_authoring_scaffold.py`
- Modify: `src/authoring/scaffold.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `detail.validate() -> ValidationReport`, `ValidationReport.failures`, and canonical `Finding.__str__` output.
- Produces: `build_scaffold(request)` raising `ScaffoldError` before returning documents when one or more definite failures exist.
- Preserves: successful return for clean reports and reports containing only `UNKNOWN` blockers.

- [x] **Step 1: Write the failing complete-diagnostic test**

Add a helper request with three generic `slab` components at the same explicit raw placement. Add a test that calls `build_scaffold()`, captures `ScaffoldError`, and asserts:

```python
message = str(error.value)
assert "scaffold validation failed with 3 definite failure(s):" in message
assert message.count("[FAIL] interference:") == 3
assert "first <-> second" in message
assert "first <-> third" in message
assert "second <-> third" in message
assert "datum" in message and "to_datum" in message
assert "reserve `raw` transforms" in message
```

- [x] **Step 2: Write the failing transactional-publication test**

Call `write_scaffold()` with the same request and assert the error is raised and neither `<slug>.spec.yaml` nor `<slug>.cert.yaml` exists.

- [x] **Step 3: Write the FAIL-versus-UNKNOWN contract test**

Patch only the compiler boundary to return a minimal detail whose `validate()` returns a real `ValidationReport` containing one `Finding` with `verdict=UNKNOWN_VERDICT`. Assert `build_scaffold()` returns documents. This pins that the new gate reads `report.failures`, not `report.blocking` or `report.ok`.

- [x] **Step 4: Run focused tests and verify RED**

Run through the source-bound launcher:

```bash
pytest tests/test_authoring_scaffold.py \
  -k 'validation_failures or validation_failure or unknown_validation' -q
```

Expected: the failure-output and transactional tests fail because scaffolding currently returns documents/writes files; the UNKNOWN test passes or remains neutral because existing behavior permits it. Confirm the RED failures are caused by the missing definite-failure gate.

- [x] **Step 5: Implement the minimal gate**

Change the discarded validation call in `build_scaffold()` to:

```python
report = detail.validate()
failures = report.failures
if failures:
    rendered = "\n".join(str(finding) for finding in failures)
    raise ScaffoldError(
        f"scaffold validation failed with {len(failures)} definite "
        f"failure(s):\n{rendered}\n"
        "Parts seated on neighbors should use a datum mate placement with "
        "`datum`, `to`, and `to_datum`; reserve `raw` transforms for global "
        "measurements or genuine free degrees of freedom."
    )
```

- [x] **Step 6: Update the public behavior documentation**

Change the README scaffold-verification paragraph to state that definite validation failures stop publication while honest `UNKNOWN` preview findings remain allowed. State that the failure message recommends datum mates for neighbor-seated parts.

Extend `test_readme_teaches_scaffold_and_non_inference_conventions()` to pin the phrases `definite validation failure`, `UNKNOWN`, and `datum mate`.

- [x] **Step 7: Run focused tests and verify GREEN**

Run:

```bash
pytest tests/test_authoring_scaffold.py -q
```

Expected: all 27 authoring scaffold tests pass with no warnings or errors.

- [x] **Step 8: Inspect and commit**

Run `git diff --check`, review the exact diff, and verify `git status --short` contains only the intended generic source/test/docs changes plus the pre-existing untracked `acceptance/` evidence. Commit only:

```bash
git add src/authoring/scaffold.py tests/test_authoring_scaffold.py README.md \
  docs/superpowers/plans/2026-07-17-fail-closed-scaffold-validation.md
git commit -m "fix: fail closed on invalid scaffolds"
```
