# STEPDOC/CPG +process Task 2 — runtime process graph

**Branch:** `codex/stepdoc-process`

**Worktree:** `.worktrees/stepdoc-staging-integration`

**Scope:** Task 2 only from
`docs/superpowers/plans/2026-07-13-stepdoc-process.md`. No caddy authoring,
reader-step rendering, epistemic-table change, generated document, or geometry
change is included here; those remain Task 3.

## Result

The compiled runtime now carries typed non-geometric process facts and the
event graph consumes them as construction truth:

- `Connection.process` is the typed compiler handoff. `ProcessFact` carries
  kind, instructions, completion predicate, why, and provenance.
- `ConnectionType.supported_process_kinds()` is the one type-level capability
  surface. `process_events(conn)` is the runtime production hook; the generic
  default is empty.
- `Glued` supports `cure`. An unannotated imperative or spec-built glue joint
  receives a duration-free `connectiontype_default` fact that follows the
  selected adhesive label and actual shop conditions. An authored
  `process.cure` reaches the runtime byte-for-byte as
  `authored_process_fact`.
- Spec semantics now asks the registered capability surface instead of the
  display key `glued`. The graph independently confirms an actual typed event
  was emitted. It rejects unsupported, duplicate, dropped, rewritten, or
  forged-provenance process facts.

## Graph truth

`Event("process", connection_label, process_kind)` is content-keyed. The
graph exposes deterministic `processes_of`, `process_facts`, and `constraints`
surfaces. Process events inherit their connection's frame and participate in
R-1, so a bench cure precedes its unit join.

Two order rules now exist on the merged graph:

1. Every drive/install event of a cure-bearing connection precedes its typed
   cure event. This is `structural_necessity` and DERIVED.
2. A resolved `sequence.after` claim orders its source cure before **every**
   role-group drive of the target. This is `authored_sequence`, DECLARED, and
   carries the exact authored `why`.

The ordinary merged cycle check consumes both rules. A self-contradictory
cure/drive claim names `drive(...)`, `process(..., cure)`, both provenance
families, the authored rationale, and the process-point-constraint repair
surface.

## Runtime defenses

- Unknown target/source labels fail below the compiler.
- A type that advertises cure but emits no cure still fails; capability does
  not invent a fact.
- Composed-site point constraints require both target and source to match the
  claim's own `chain` according to `ConnectionChecks.fragments`. A manually
  mismatched `ResolvedAfter` fails and no cross-fragment edge is produced.
- Process events sort deterministically by connection declaration order and
  then process kind.
- `Detail.validate()` threads `resolved_after()` into `ConnectionChecks.after`.
  The direct install-check fallback rebuilds from the same after/fragments
  surface rather than creating a second order truth.

## Checks and provenance

The process order edges are projected into `ConnectionChecks.derived`:

- drive/bond before cure: `inferred` / `verified_heuristic`, rule
  `<ConnectionType>.process_events`;
- cure before target drive: `official` / `authoritative`, rule
  `sequence.after`, with the exact authored why in assumptions.

Axis 3 is demonstrably falsifiable. In the synthetic corridor fixture, a
blocking member owned by the glue connection is UNORDERED/UNKNOWN without the
point constraint. Adding cure-before-target proves that member present via
`member -> drive(bond) -> process(cure) -> drive(target)`, so identical
geometry becomes a loud FAIL. The same result is pinned after clearing the
cached graph and exercising install.py's fallback builder.

## TDD evidence

Clean baseline before Task 2 production edits:

```text
tests/test_glued_connection.py tests/test_cpg_core.py tests/test_install_axes.py
72 passed in 10.34s
```

Initial RED for the new runtime/graph acceptance file:

```text
tests/test_stepdoc_process.py
14 failed in 2.55s
```

The failures were the expected missing `ProcessFact`, capability hook,
`Connection.process`, process nodes, `after` threading, frame/R-1, fragment
defense, and derivation projection. Separate RED probes then pinned:

- axis-3 UNKNOWN -> FAIL plus the direct fallback;
- forged process provenance rejection;
- authored-fact rewrite rejection;
- process-aware cycle teaching text.

Fresh final focused verification on the final code tree:

```text
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest \
  tests/test_stepdoc_process.py tests/test_sequence_schema.py \
  tests/test_glued_connection.py tests/test_cpg_core.py \
  tests/test_install_axes.py -q

185 passed in 10.71s
```

Fresh broader compiler/site/connection verification on the same final tree:

```text
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest \
  tests/test_stepdoc_process.py tests/test_sequence_schema.py \
  tests/test_glued_connection.py tests/test_cpg_core.py \
  tests/test_install_axes.py tests/test_spec.py tests/test_spec_repeat.py \
  tests/test_site_model.py tests/test_connection.py \
  tests/test_install_contract.py -q

281 passed in 178.08s (0:02:58)
```

`git diff --check` exited cleanly after the focused gate. The worktree shim
resolved `detailgen` from this exact worktree before all runs.

## Deliberate deferrals / next-task boundary

- `process(cure)` is not yet a `ReaderStep`; Task 3 must make it its own step
  and carry the typed fact directly to both reader surfaces.
- The caddy does not yet author its two cure facts or cure-before-side-screw
  constraints. Existing hand-written sequence prose remains until Task 3's
  CAT-K retirement/grep closer.
- The epistemic table and document derivation presentation do not change in
  this task.
- No duration, timer, environmental calculation, clamp capacity, adhesive
  selection, or bond capacity is represented.
