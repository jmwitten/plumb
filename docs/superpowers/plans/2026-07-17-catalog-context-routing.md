# Catalog Context Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let pure catalog variants skip broad repository context while all other or ambiguous Plumb changes fail closed into the full extension workflow.

**Architecture:** `detailgen.authoring.component_extension` classifies a validated contract into an authoritative context route without building CAD. The authoring CLI exposes that route and the normal verifier repeats it in its result. The canonical Plumb `plumb-extend` skill uses only the machine route to choose between a strict read allowlist and its existing full preflight/context workflow.

**Tech Stack:** Python 3.12, argparse, PyYAML, pytest/unittest, Markdown skill contracts.

---

### Task 1: Add the compiler context-route contract

**Files:**
- Modify: `src/authoring/component_extension.py`
- Modify: `src/authoring/__init__.py`
- Test: `tests/test_component_extension.py`

- [ ] Write failing tests for a registered catalog variant, an unknown component, every non-catalog class, route immutability, and verifier route parity.
- [ ] Run `tests/test_component_extension.py` and confirm the new tests fail for missing route behavior.
- [ ] Add `build_component_context_route()` with only `catalog_micro` and `full_extension` outcomes.
- [ ] Require a validated contract and an already registered component key for `catalog_micro`; return `full_extension` otherwise.
- [ ] Include the same route in PASS and ESCALATE verifier results.
- [ ] Export the public classifier and rerun the focused tests.

### Task 2: Add the route-only CLI

**Files:**
- Modify: `src/authoring/__main__.py`
- Test: `tests/test_component_extension.py`

- [ ] Write failing CLI tests for micro, full, malformed, and no-CAD behavior.
- [ ] Run the CLI tests and confirm RED.
- [ ] Add `component-route CONTRACT`, returning route JSON with exit code 0 for valid contracts and the existing structured failure with exit code 2 for invalid contracts.
- [ ] Rerun the focused tests and confirm GREEN.

### Task 3: Make Plumb consume the route before broad context

**Files:**
- Modify in canonical plugin repo: `skills/plumb-extend/SKILL.md`
- Modify in canonical plugin repo: `tests/test_skill_contracts.py`

- [ ] Add failing skill-contract assertions for route-first operation, the micro read allowlist, scoped diff/check closure, full fallback, and zipline-platform exclusion.
- [ ] Run `python3 -m unittest tests.test_skill_contracts -v` and confirm RED.
- [ ] Rewrite preflight so the installed compiler launcher runs `component-route` first when a component-extension contract can represent the request.
- [ ] Permit bounded context only for exact `catalog_micro` output; require full workflow for invalid, full, ambiguous, behavioral, structural, site, load, safety, connection, schema, renderer, or document changes.
- [ ] Require `component-check` PASS plus an allowlisted diff before release from the micro lane.
- [ ] Rerun the plugin contract tests and confirm GREEN.

### Task 4: Focused verification and timing

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Create: `docs/superpowers/specs/2026-07-17-catalog-context-routing-benchmark.md`

- [ ] Document the route command, micro boundary, and full-workflow fallback in the compiler's public guidance.
- [ ] Run compiler component-extension tests and plugin skill-contract tests only.
- [ ] Benchmark `component-route` and representative catalog `component-check` from fresh processes.
- [ ] Verify a zipline-like complex contract returns `full_extension` without CAD.
- [ ] Run `git diff --check` in both repositories and review scoped diffs.

### Task 5: Integrate the compiler and reinstall the canonical plugin

- [ ] Commit compiler changes on `codex/catalog-context-lane`, merge them into compiler `main`, and push `origin/main`.
- [ ] Commit plugin changes on `codex/catalog-context-lane`.
- [ ] Run the plugin cachebuster helper in the canonical plugin source.
- [ ] Validate the plugin, reinstall it through the local marketplace, and verify the installed `plumb-extend` skill contains the route-first contract.
- [ ] Push the plugin branch if an upstream is configured; otherwise report the local commit explicitly.
