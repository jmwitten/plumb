# Task SEQSCHEMA report — the `sequence:` spec surface (loader/schema plumbing)

Branch `sdd/stepdoc-core` off master @c4692f5. Implements the loader/schema
slice of STEPDOC's `authored_sequence` edge family (stepdoc-cpg-design.md
§3.1 item 3): the typed `AuthoredStage`/`SequenceSpec` schema, the
`sequence:` spec surface with its five load-time teaching errors, the
declaration-time (semantic) existence check for the names it references, and
the compiled landing surface the axis-3 task will consume. NO event graph,
NO axis-3 semantics, NO staging (`subassemblies:`/`assembly:`) or point
constraints (`after:`) — those are later increments per the owner's phased
scope (amendment 1) and are explicitly kept as unknown keys, never
special-cased.

## Import-path verification (environment)

Same shim convention as the INSTALL-SCHEMA task (`.shim/` already in
`.gitignore`):

    cd ~/Code/detailgen-stepdoc-core && mkdir -p .shim && ln -sfn "$PWD/src" .shim/detailgen
    export PYTHONPATH="$PWD/.shim"
    python -c "import detailgen; print(detailgen.__file__)"
    # -> <worktree>/.shim/detailgen/__init__.py   (verified before every gate)

Python: `~/Code/construction-detail-generator/.venv/bin/python`.

## Decisions

### Schema (`src/spec/schema.py:948-1006`)

`AuthoredStage` (frozen, :954) — `name: str`, `why: str`,
`connections: tuple = ()`, `parts: tuple = ()`. `SequenceSpec` (frozen, :992)
— `stages: tuple = ()`. `DetailSpecDoc.sequence: SequenceSpec` added at
:1076 (default `field(default_factory=SequenceSpec)`), so a sequence-free
spec loads/compiles byte-identically to before this task.

Vocabulary discipline (owner amendment 5, BINDING): both new types and every
docstring/comment use "stage" only — never "step" — for the authored
grouping; the reader-facing presentation unit is explicitly named as a
*different, later* type in the docstrings, never blurred with this one.
Stage order is NOT a separate index field — it is the tuple's own
declaration-order position (rule 6), so there is nothing to drift.

### Loader (`src/spec/loader.py`)

- `_build_doc` (:102): `"sequence": False` added to the top-level known-key
  set (:113); `sequence` built at :136-137 and threaded into the
  `DetailSpecDoc(...)` constructor call at :163.
- `_build_sequence` (:453-509): loads the `sequence:` block. Structural
  checks that need ONLY this block's own content (no cross-doc lookup):
  - `stages` list non-empty (a `sequence:` with zero stages is a load-time
    teaching error — see Deviations below, this is one addition beyond the
    brief's literal 6 rules).
  - stage names unique across the block (rule 3a).
  - no connection label / part id claimed by MORE than one stage (rule 3b) —
    keyed `(kind, name)` so a connection and a part sharing the same string
    do NOT collide (they are separate namespaces elsewhere in the schema
    too: `ConnectionSpec.label` vs `ComponentSpec.id`).
- `_build_stage` (:511-545): one stage entry. `why` required + non-empty
  (rule 1) — `_take`'s generic missing-key error covers the omitted-key
  case, a custom message covers the empty-string case (names the stage,
  cites the authored-embedment-override precedent). At least one of
  `connections`/`parts` non-empty (rule 4).
- Unknown-key discipline (rule 5): `_build_sequence`'s `_take` only knows
  `{"stages": True}`; `_build_stage`'s only knows
  `{"name": True, "connections": False, "parts": False, "why": True}`.
  `after:`, `subassemblies:`, `assembly:` are simply ABSENT from both sets,
  so each hits the ordinary `_take` unknown-key error (with did-you-mean) —
  no special "not yet supported" branch exists to diverge from that message
  later.

### Semantics (`src/spec/semantics.py:167-198`, `analyze_sequence`)

The ONE check needing the whole doc (rule 2): every `connections:` entry
must be an existing connection `label` (walks `doc.connections`, including
`repeat:` bodies via the existing `_walk_connections`); every `parts:` entry
an existing component `id` (existing `_declared_ids`). Unknown name -> loud
`SemanticError` with a did-you-mean hint, same style as `analyze_retires`'s
target-existence check — deliberately mirrored, including the "the loader
has no view of the rest of the doc" split rationale in both docstrings.

Wired into `SpecDetail.__init__` (`src/spec/compiler.py:156-161`) alongside
`analyze_mounts`/`analyze_features`/`analyze_retires` — so an unknown
reference is a declaration-time error, before any geometry, exactly like
the other three checks in that pass.

### Landing surface (`src/assemblies/connection.py`, `src/details/base.py`, `src/spec/compiler.py`)

Brief requirement: "the parsed structure must reach the compiled surface the
validation checks consume, mirroring how `install:`/edges reach
`ConnectionChecks`." Implemented as:

- `ConnectionChecks.sequence: tuple = ()` (`connection.py:203`) — a NEW
  field alongside `installs`, deliberately untyped (plain `tuple`, not an
  import of `AuthoredStage`): `assemblies/connection.py` has no dependency
  on `spec/schema.py` today (the dependency runs the other way — `spec`
  depends on `assemblies`), and this field must not invert that layering.
- `compile_connections(assembly, connections, sequence=())` (`connection.py:595-596`)
  — new optional kwarg, passed straight onto the returned
  `ConnectionChecks(sequence=sequence)`; the one existing production caller
  (`details/base.py`) is updated, the five test-only call sites are
  untouched (all still call it with the old 2-arg form, which still works —
  default `()`).
- `Detail.sequence(self) -> tuple` (`details/base.py:232-240`) — new hook,
  same shape as the existing `connections()`/`cross_check()` hooks. Default
  `()` (an imperative `.py` detail authors no sequence).
- `Detail.validate()` (`details/base.py:253-260`): reads `self.sequence()`,
  passes it into `compile_connections`, and widens the build gate from
  `if conns:` to `if conns or sequence:` so a doc with `parts:`-only stages
  and ZERO connections still lands its sequence data (rather than being
  silently dropped by the old connections-only gate). Behaviorally
  IDENTICAL for every existing `Detail` subclass today (`sequence()`
  defaults to `()` everywhere except `SpecDetail`), test-confirmed by the
  unchanged 201/201 count on the loader-adjacent suite below.
- `SpecDetail.sequence()` (`compiler.py:711-718`) — returns
  `self.doc.sequence.stages` directly. Still spec-local labels/ids; NO
  resolution to built `Placed`/event-graph nodes — that resolution is the
  axis-3 task's job, per the brief's "no semantics" scope.

Consumption surface for axis-3: `Detail.sequence()` (pre-build) or
`Detail._connection_checks.sequence` (post-`validate()`, alongside
`.installs`) — a tuple of `AuthoredStage` in declaration order, each with
`.name`, `.why`, `.connections` (labels), `.parts` (ids).

## Deviations from the brief

1. **Added a "zero-stages" load error** (`sequence: {stages: []}`) beyond
   the brief's literal 6 rules. Rationale: a `sequence:` block declaring no
   stages authors no order over anything — the same "no silent no-op"
   discipline the rest of this loader enforces everywhere else (an omitted
   `sequence:` block already means the same thing honestly; an *empty* one
   would be a second, confusing spelling of it). Test:
   `test_sequence_block_with_zero_stages_is_a_loud_load_error`.
2. **Widened `Detail.validate()`'s connections gate** (`if conns:` ->
   `if conns or sequence:`) rather than leaving it untouched. Rationale
   above; flagged here because it touches a shared, heavily-exercised code
   path — verified against the full loader-adjacent suite plus every
   existing direct caller of `compile_connections` (test files), all green,
   no count change.

Neither is a semantics decision about STEPDOC's construction meaning — both
are schema/plumbing-discipline choices consistent with the rest of this
loader. No existing check or test was weakened; both are additive.

## Gates

- Import-path verification: shown above, re-run before each pytest gate.
- New tests: `tests/test_sequence_schema.py` — **28 passed** (happy path x6,
  rule 1 x2, rule 2 x3, rule 3 x5, rule 4 x3, rule 5 x5, landing surface x4).
- `tests/test_scripts_spec_rewire.py` — **98 passed** (includes the +1
  parametrized case of `test_no_test_loads_a_detail_py` picking up the new
  `test_sequence_schema.py` module via its `tests/test_*.py` glob).
- Loader-adjacent suite re-run POST-change (`test_scripts_spec_rewire.py
  test_spec.py test_cl1_semantics.py test_cl3_expect_retire.py
  test_connection.py test_install_contract.py
  test_install_spec_surface.py`): **201 passed** — identical to the
  PRE-change baseline captured before any edit in this task (201 passed),
  confirming no regression from the `schema.py`/`loader.py`/`semantics.py`/
  `compiler.py`/`connection.py`/`details/base.py` touches.
- `compile_connections` direct callers (`test_install_axes.py`,
  `test_install_sweep.py`, `test_bbox_prefilter.py`,
  `test_coverage_matrix.py`) re-run against the new signature (`sequence=()`
  default, one new caller updated in `details/base.py`): **68 passed**
  (run by the controller from the shimmed worktree, 2026-07-12).
- Full suite NOT run (controller gates, per the brief).

## Residuals / honest gaps (all in-scope for the NEXT task)

- No spec ships a `sequence:` block yet — the platform's authored order is
  the next task's job.
- `connections`/`parts` in an `AuthoredStage` are spec-local strings
  (labels/ids), unresolved to `Placed`/event-graph nodes — axis-3's job.
- `after:` (point constraints), `subassemblies:`/`assembly:` (§3.4 staging)
  are unknown keys today by design, not partially-wired stubs.
- `ConnectionChecks.sequence` carries NO provenance wrapper beyond what
  `AuthoredStage.why` already is — matching the brief's "store the why: with
  it" instruction literally (the why travels WITH the stage, not through a
  separate provenance channel like `ResolvedInstallation.provenance`, since
  a stage is a single authored fact, not a per-field-resolved contract).
