# STEPDOC/CPG +process Task 1 — typed authoring and compiled bridge

**Branch:** `codex/stepdoc-process`

**Worktree:** `.worktrees/stepdoc-staging-integration`

**Scope:** Task 1 only from
`docs/superpowers/plans/2026-07-13-stepdoc-process.md`

## Result

The spec language now represents two +process facts without changing graph or
runtime Connection behavior:

- A connection may author a typed `process.cure` refinement with a non-empty
  instruction list, the closed `selected_label_full_cure` completion token,
  and required `why` provenance. Omission remains an empty typed default and
  serializes to no new key.
- `sequence.after` carries typed nested process references. The outer
  connection is the target; each inner `{cure: <connection label>}` names a
  source process prerequisite; every declaration requires `why`.

Both authoring shapes round-trip through YAML and JSON. Connection labels are
kept verbatim—no `cure(label)` parser, token splitting, or whitespace rewrite
can change identity.

## Strictness and semantic checks

The loader/semantic pass rejects:

- scalar/string mini-languages and wrong mapping/list shapes;
- unknown keys at the process, cure, point-constraint, and nested-reference
  levels;
- missing/blank instructions or `why`, empty process/after blocks, and an
  open-ended or duration-like completion value;
- duplicate process references and duplicate target declarations;
- unknown target/source connection labels (with did-you-mean help);
- a connection-local cure fact or cure prerequisite on a non-`glued`
  connection;
- ambiguous duplicate authored labels.

## Compiled bridge

`SpecDetail.resolved_after()` resolves target and source labels to the actual
built connection labels. A reference that expands through `repeat` to more
than one instance fails loudly in v1; no all-to-all or index-pairing order is
invented. Retired and zero-instance references also fail loudly.

`Detail.resolved_after()` supplies the empty imperative default.
`SiteDetail.resolved_after()` replays each fragment's constraints under its
own chain, matching `resolved_sequence()` and preserving the no-cross-fragment
order boundary.

`ResolvedProcessRef` and `ResolvedAfter` live beside `ResolvedStage` in
`assemblies/event_graph.py`, but are inert bridge values in this task. Per the
controller clarification, Task 1 does **not** add `Connection.process`,
`ConnectionType.process_events()`, process nodes, graph edges, reader output,
or caddy authoring. Task 2 owns the runtime process fact/default and compiler
handoff.

## TDD evidence

RED, before production changes:

```text
41 failed, 51 passed in 2.85s
```

The failures were the expected missing `sequence.after`, `process.cure`,
resolved bridge, and teaching-diagnostic behavior. A separate label-preservation
probe also failed before its minimal loader correction and passed afterward.

GREEN during implementation:

```text
tests/test_sequence_schema.py
94 passed in 2.16s

tests/test_spec.py tests/test_spec_repeat.py tests/test_glued_connection.py
tests/test_site_model.py
73 passed in 165.40s
```

## Final verification

Fresh pre-commit run on the final code tree, after re-verifying the shim import
path:

```text
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest \
  tests/test_sequence_schema.py tests/test_spec.py tests/test_spec_repeat.py \
  tests/test_glued_connection.py tests/test_site_model.py -q

167 passed in 169.04s (0:02:49)
```

`git diff --check` exited cleanly in the same verification command.

## Known deferrals

- Runtime Connection process facts and the safe `Glued` default cure fact.
- `process(cure)` events and bond-before-cure / cure-before-target edges.
- Cycle diagnostics, axis-3 consumption, reader steps, CAT-K caddy authoring,
  derivation-log projection, and delivered document changes.
