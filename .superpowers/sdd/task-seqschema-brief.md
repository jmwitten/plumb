# Task SEQSCHEMA — `sequence:` spec surface for STEPDOC v1-core (loader/schema plumbing only)

**Worktree:** `~/Code/detailgen-stepdoc-core` (branch `sdd/stepdoc-core` off master @c4692f5).
**Import discipline (non-negotiable):** `cd ~/Code/detailgen-stepdoc-core && mkdir -p .shim && ln -sfn "$PWD/src" .shim/detailgen && export PYTHONPATH="$PWD/.shim"` then verify `python -c "import detailgen; print(detailgen.__file__)"` prints the WORKTREE path before trusting any run. Python: `~/Code/construction-detail-generator/.venv/bin/python`.

**Context you must read first:**
- `.superpowers/sdd/stepdoc-cpg-design.md` §3.1 (family 3, authored_sequence), §Owner sign-off (amendment 5: "stage" vs "step" vocabulary — BINDING).
- `.superpowers/sdd/task-install-schema-report.md` — the schema pattern you are mirroring (loader teaching errors, unknown-key registry discipline, dataclass shape).
- The existing spec loading path (find where `install:` overrides are parsed; mirror it).

## Scope — plumbing ONLY, no semantics

Add a spec-level `sequence:` block to detail specs:

```yaml
sequence:
  stages:
    - name: toe_screws_first
      connections: [<connection label>, ...]   # optional
      parts: [<part authored id>, ...]         # optional (at least one of connections/parts non-empty)
      why: "required free text — an order claim ships with its defense"
```

**Rules (each with a loud teaching error + test):**
1. `why:` is REQUIRED per stage — missing/empty ⇒ load-time error naming the stage and the house rule (an authored order claim requires its defense; cite the authored-embedment-override precedent style).
2. Every `connections:` entry must name an existing connection label; every `parts:` entry an existing part authored id — unknown name ⇒ loud error (existing unknown-key/registry discipline; include the unknown name and the valid candidates or a close-match hint if the existing pattern does).
3. Stage names unique; a connection or part listed in MORE than one stage ⇒ loud error (two stages would claim contradictory order over the same events).
4. A stage listing nothing (both lists empty/absent) ⇒ loud error.
5. Unknown keys inside `sequence:` or a stage entry ⇒ the standard unknown-key teaching error. Deliberately NOT supported in v1-core (later increments): `after:`, `subassemblies:`, `assembly:` — these must hit the unknown-key error like any other unknown key (do NOT special-case them).
6. Stages are totally ordered by declaration order — the dataclass preserves it.

**Vocabulary discipline (owner amendment 5, BINDING):** all new type/field names use `stage` (authored sequence grouping), NEVER `step` (reader presentation unit). E.g. `AuthoredStage`, `SequenceSpec.stages`. No identifier, docstring, or error message may use the two interchangeably.

**Landing surface:** the parsed structure must reach the compiled surface the validation checks consume, mirroring how `install:`/`edges` reach `ConnectionChecks` — the axis-3 implementer (next task on this branch) will consume it from there. Every stage entry is REPRESENTED-rung authored content; store the `why:` with it (provenance surface — mirror how authored install overrides carry provenance if they do).

**No spec ships with a `sequence:` block in this task** — the platform's authored order is the NEXT task's job. Your fixtures are test-local specs (mirror how the install schema tests author theirs).

## Deliverables
1. Loader/schema code + dataclasses.
2. Tests in a new `tests/test_sequence_schema.py`: happy path (parsed structure, declaration order preserved, why carried) + one test per teaching error above. Run them + `tests/test_scripts_spec_rewire.py` (the per-test-file no-imperative-load guard will pick up your new module) + any loader-adjacent existing module you touched. Do NOT run the full suite — the controller gates.
3. Report at `.superpowers/sdd/task-seqschema-report.md`: what landed, file/line anchors, test counts, any deviation from this brief with the why.
4. Commit on `sdd/stepdoc-core` with a message starting `seqschema:`.

**Honesty rules:** never weaken an existing check or test; if something in this brief conflicts with what you find in source, STOP and write the conflict into your report file rather than improvising semantics.
