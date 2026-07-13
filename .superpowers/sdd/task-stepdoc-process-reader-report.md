# STEPDOC/CPG +process Task 3 — reader steps and caddy CAT-K

**Branch:** `codex/stepdoc-process`

**Worktree:** `.worktrees/stepdoc-staging-integration`

**Scope:** Task 3 from
`docs/superpowers/plans/2026-07-13-stepdoc-process.md`. This increment does
not implement illustrated panels, an assembly-manual document, or links to
that future document.

## Result

Typed cure facts now reach both implemented reader surfaces without a renderer
reconstructing process truth:

- `ReaderStep` carries its exact `process_event` and `process_fact` from the
  event graph.
- Every process event is a standalone reader step. A process-adjacent bond or
  target connection splits out of an ordinary stage/bench grouping, so a real
  `bond -> cure -> target` barrier cannot be swallowed by presentation.
- Presentation buckets are topologically ordered from graph edges. Existing
  non-process stage and bench grouping stays byte-compatible.
- The shared build-sequence model carries the typed fact and the exact
  `authored_sequence` point constraint to Markdown and HTML. The cure step says
  what must wait; the target step names its cure prerequisite; both print the
  same authored `why` and provenance.
- Cure completion is rendered only as the selected adhesive label's
  full-cure/full-strength condition under actual shop conditions. The reader
  explicitly states that no generic duration is represented.

## Caddy CAT-K authoring

Both rail-to-top glue connections now author `process.cure` with project-local
preparation/fixturing instructions, the closed
`selected_label_full_cure` completion predicate, and provenance. Both
rail-to-side screw connections author a typed `sequence.after` prerequisite on
their corresponding cure.

The authored rationale says this sequence preserves the caddy's registration
datum and is **not a universal glue-before-screws rule**. That boundary follows
the primary-source research record: common cabinet workflows legitimately
drive screws in wet glue, while other workflows wait for cure.

The resulting graph and reader run are:

1. place/prepare the benched caddy parts;
2. install both rail-to-top adhesive bonds;
3. render each rail cure as its own step;
4. drive each side connection only after its corresponding cure;
5. join/set the completed caddy over the sofa arm.

The process graph derives both `drive(bond) -> process(cure)` edges and records
both authored `process(cure) -> drive(side screws)` edges. Removing one
`sequence.after` declaration removes only that authored dependency; both
derived bond-before-cure rules remain.

## Single-source prose retirement

The hand-written single-detail fieldnote titled “Hidden rail joints — glue,
then screws, all off the sofa” is retired. Cross-connection cure-before-screw
wording was removed from connection assumptions and authored modeling prose.
The spec's structural/material disclosure remains, while preparation,
fixturing, completion, and project-specific order appear only through the
typed process fact and graph-derived Build sequence.

An AST/loaded-spec closer rejects glue/cure-before/then-screw sequence prose in
report-script string constants, connection assumptions, and authored document
prose.

## Provenance on both reader surfaces

The shared epistemic-contract table now adds:

- **Bond/install before process cure — DERIVED**, with this detail's actual
  event descriptions and producing `Glued.process_events` sources;
- **Authored process point constraints — DECLARED**, with each actual cure
  source, target connection, and authored `why`.

The caddy derivation-log sample cap was raised to include the late-appended
`sequence.after` facts for both four-screw side connections. Its validation
Markdown therefore shows the derived and declared process-edge classes rather
than hiding the second class behind sampling. The technical HTML renders the
same epistemic rows and the same process/constraint content model.

The consolidated-document text-layer golden was regenerated through its
prescribed command. Review showed six intentional line replacements: the new
shared process rows, updated reader intro, and the already-landed Task-2
`sequence.after` teaching text. The golden guard passes afterward.

## TDD evidence

Initial reader RED, before production changes:

```text
tests/test_stepdoc_process.py
3 failed, 21 passed in 2.01s
```

The failures were the missing standalone typed cure step, a same-stage /
same-bench grouping that swallowed the process barrier, and absent typed
process/dual-end content in the build-sequence model.

Initial caddy/table RED, before caddy authoring and the shared epistemic rows:

```text
4 failed in 2.23s
```

The failures were the absent process epistemic rows, default rather than
authored caddy facts, zero caddy point constraints, and the standing
hand-written glue-then-screws fieldnote.

During the broader reader gate, three existing grouping tests caught an empty
registry-key compatibility error: every connection label was initially treated
as process-bearing because `processes_of` contains empty tuples. The split now
requires an actual process event (or a real point-constraint target), and the
targeted regression set passes.

## Final verification

Worktree import verification:

```text
/Users/joelwitten/Code/construction-detail-generator/.worktrees/
stepdoc-staging-integration/.shim/detailgen/__init__.py
```

Focused process/reader/caddy/install/schema/report gate:

```text
261 passed in 35.20s
```

Presentation/report gate, including the refreshed whole-document golden:

```text
20 passed in 75.52s (0:01:15)
```

The golden guard also passed independently:

```text
1 passed, 4 deselected in 40.89s
```

`git diff --check` exited cleanly with the 261-test gate.

## Geometry/view non-change gate

The caddy assembly geometry hash is byte-identical between `HEAD`'s spec and
this Task-3 spec under the same code:

```text
HEAD   511f77d74c211a3a777e2388a520c54a20d15746373c2de70633be40b14a3a3d
TASK3  511f77d74c211a3a777e2388a520c54a20d15746373c2de70633be40b14a3a3d
```

No view renderer ran and no generated output is in the diff. All ten existing
caddy view PNG SHA-256 values match the prior staging worktree byte-for-byte.

## Deliberate deferrals / concerns

- Product selection, timers, temperature/humidity calculations, clamp
  pressure/capacity, and adhesive bond capacity remain outside +process.
- The caddy connection labels are exact machine identities and therefore long
  in the plain-text reader run. Reader-facing connection vocabulary can be a
  later projection, but must not replace the keys checks consume.
- Illustrated grouped panels, hardware/tool strips, slider/navigation, the
  separate `armchair_caddy_assembly_manual.html`, and reciprocal links remain
  exclusively in the independently gated +presentation increment.
