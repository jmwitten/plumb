# General DetailSpec Scaffolder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a generic, registry-backed command that produces a compiler-valid DetailSpec and certification stub while publishing the missing compact nested grammar.

**Architecture:** A new `detailgen.authoring.scaffold` module parses explicit author inputs, validates them against live registry signatures, builds plain authoring mappings, and verifies them through the existing DetailSpec compiler and certification loader. The existing authoring CLI becomes a subcommand dispatcher while preserving manifest output when invoked without a subcommand.

**Tech Stack:** Python 3.12, argparse, PyYAML, existing DetailSpec compiler, existing certification contract loader, pytest.

## Global Constraints

- Do not read or copy the triangle product spec or tests as implementation precedent.
- Never infer dimensions, placement, connection participants, datums, or validation claims.
- Unknown registry keys and missing or unknown constructor parameters fail closed.
- Dimension grammar must say measures are world-axis bounding-box values and must not recommend one as intrinsic member length.
- Lumber cut grammar must say miter angles are degrees off square and require `long_point_to_long_point` semantics.
- Scaffolding performs structural/compiler/contract verification, not product review, package generation, or full-suite testing.

---

### Task 1: Publish the compact nested grammar

**Files:**
- Modify: `src/authoring/manifest.py`
- Test: `tests/test_authoring_manifest.py`

**Interfaces:**
- Consumes: live component and connection registries plus `DETAIL_SPEC_KEYS`.
- Produces: `build_authoring_grammar() -> dict[str, object]` and manifest schema `detailgen/authoring-manifest/v3` with `authoring_grammar`.

- [ ] **Step 1: Write failing manifest tests**

Add assertions for v3, exact component/placement/connection/certification shapes,
world-axis dimension wording, absence of an intrinsic-length recommendation,
and the lumber off-square/long-point convention.

- [ ] **Step 2: Verify the tests fail for the missing v3 grammar**

Run:
`plumb-python --source <worktree>/src --venv <repo>/.venv -- pytest tests/test_authoring_manifest.py -q`

Expected: failures because the schema is v2 and `authoring_grammar` is absent.

- [ ] **Step 3: Implement the minimal deterministic grammar**

Add one closed dictionary returned through a deep copy, include only the nested
shapes required to author simple products, and add it to the manifest.

- [ ] **Step 4: Verify manifest tests pass**

Run the command from Step 2. Expected: all manifest tests pass.

### Task 2: Build and verify generic scaffold documents

**Files:**
- Create: `src/authoring/scaffold.py`
- Modify: `src/authoring/__init__.py`
- Create: `tests/test_authoring_scaffold.py`

**Interfaces:**
- Consumes: `components`, `connection_types`, `load_spec_text`, `compile_spec`, and `load_contract`.
- Produces: `ScaffoldRequest`, `ScaffoldResult`, `ScaffoldError`, `build_scaffold(request)`, and `write_scaffold(request)`.

- [ ] **Step 1: Write a failing one-component scaffold test**

Use a generic `slab` component with explicit dimensions. Assert generated YAML
loads, compiles to one part, and the generated contract resolves its source.

- [ ] **Step 2: Verify the test fails because the module is absent**

Run the single test with the source-bound launcher. Expected: import failure for
`detailgen.authoring.scaffold`.

- [ ] **Step 3: Implement request/result types and document generation**

Validate slug/id syntax, resolve live registry entries, compare supplied values
to `inspect.signature`, reject missing/unknown parameters, assemble mappings,
load and compile the spec, and load the certification contract after writing.

- [ ] **Step 4: Add failing tests for placements and connections**

Cover explicit `raw` placement and a parameterized generic connection whose
participants name declared components.

- [ ] **Step 5: Implement placement and connection handling**

Pass explicit placement mappings through the loader unchanged; validate
connection type, parts, occurrence-indexed parameters, and constructor
signatures before assembling the connection records.

- [ ] **Step 6: Add and pass fail-closed tests**

Cover unknown keys, missing and unknown parameters, duplicate ids, undeclared
participants, overwrite protection, and cleanup when post-write verification
fails.

### Task 3: Expose the minimal CLI without breaking manifest output

**Files:**
- Modify: `src/authoring/__main__.py`
- Modify: `README.md`
- Test: `tests/test_authoring_scaffold.py`

**Interfaces:**
- Consumes: `write_scaffold()` and `authoring_manifest_json()`.
- Produces: `python -m detailgen.authoring scaffold ...`; no-argument invocation retains manifest JSON.

- [ ] **Step 1: Write failing CLI tests**

Exercise repeated `--component`, `--set`, `--place`, `--connection`, and
`--connection-set` arguments; assert exit code 2 and actionable stderr for bad
input; assert no-argument output remains valid manifest JSON.

- [ ] **Step 2: Verify CLI tests fail before dispatch exists**

Run the CLI-focused tests. Expected: argparse/subcommand failures.

- [ ] **Step 3: Implement parsing and dispatch**

Parse YAML values with `yaml.safe_load`, retain strings such as `2x4`, reject
non-mapping placements, translate parsed records into `ScaffoldRequest`, and
print the two output paths plus a statement that geometry was not inferred.

- [ ] **Step 4: Document the command and conventions**

Add a concise Quick Start example, explicit placement caveat, dimension
world-axis warning, and lumber angle convention to `README.md`.

- [ ] **Step 5: Run focused verification**

Run the authoring manifest/scaffold, generic spec, and certification contract
tests with the source-bound launcher; then run one real CLI scaffold in a temp
directory and invoke `python -m detailgen.package ... --preview` against it.

- [ ] **Step 6: Commit the isolated branch**

Stage only the design, plan, implementation, tests, and README changes. Commit
with `feat: add generic DetailSpec scaffolder`.
