# Task INSTALL-FAMILY report — the "Fastener installability" coverage family

Branch `sdd/install-family` off master d57bf8a. Vocabulary-only slice of INSTALL
Phase 1: this branch emits NO findings — it teaches every coverage/report
surface the family's name, its kind mapping, and its epistemic ladder, so the
family reads `UNKNOWN — NOT ANALYZED` (non-blocking) in every document from day
one and the axis-check branches can land emitters against an already-mapped
vocabulary (UnmappedCheckKind is a hard crash; mapping-before-emission is the
safe order).

## What changed

1. **`INVARIANT_FAMILIES`** (src/validation/coverage.py:46-62): added
   `"Fastener installability"` inserted immediately after
   `"Construction completeness"` — it is that invariant's installability rung
   (owner amendment #4). Ladder-position comment in place; header comment count
   updated seven→nine (it was already stale at eight since SUPPORT).
2. **`KIND_TO_FAMILY`** (src/validation/coverage.py:139-157): new
   `-- INSTALL (task INSTALL)` block mapping `install_method`,
   `install_termination`, `install_access` → "Fastener installability", each
   annotated with its design axis (amendment-#4 core invariant / axis 1
   termination / axis 2 static access) and its rung semantics.
3. **`STANDING_NOTE`** (src/validation/coverage.py:191-205): the installability
   epistemic ladder (owner guardrail #6) phrased beside the existing
   connected/load-path/support/adequate ladder:
   installation-method-REPRESENTED, then GEOMETRY-PROVEN, then SEQUENCE-PROVEN,
   with the explicit "a represented method is a declared claim, not proof the
   fastener can be driven" and sequence access NOT ANALYZED until a
   construction process graph exists. No UNKNOWN is worded as safe.
4. **`RENDERABLE_CHECK_KINDS`** (src/spec/schema.py:784-791): the three kinds
   are renderable in a doc `findings:` section.
5. **`_IMPERATIVE_DECL`** (src/validation/evidence.py:966-976): friendly
   aspect/label pairs for the three kinds in the evidence graph.

## Decisions

- **EXPECT_CHECKS exclusion (deliberate):** the three kinds were NOT added to
  `EXPECT_CHECKS` (src/spec/schema.py:342) — an installability FAIL must not be
  pinnable/silenceable from a spec. A comment at the RENDERABLE_CHECK_KINDS
  entry records this so a later branch doesn't "helpfully" add it.
- **Tuple position (insertion, not append):** the family sits mid-tuple right
  after Construction completeness because it is that invariant's rung, and the
  canonical order is a report contract read weakest-to-strongest. The SUPPORT
  family (mid-tuple, rung-ordered) is the precedent, confirmed from the
  family-pin test's docstring convention (tests/test_coverage_matrix.py:46-71).

## Tests updated (with the new truth, never weakened)

- tests/test_coverage_matrix.py:46-71 — exact-tuple pin gains the family +
  ladder-position comment per the SUPPORT convention.
- tests/test_evidence_graph.py:252 — `family_verdict` graph-shape constant
  8 → 9.
- tests/test_inspector_payload.py:112-127 — unknown-family count 5 → 6 at both
  assertion sites; docstring corrected (it had gone stale at "four" even before
  this task) to six.
- Presentation golden (tests/baselines/consolidated_doc.textlayer.html)
  regenerated with `REGEN_DOC_GOLDEN=1 ... -k text_layer`. Diff reviewed
  line-by-line (within-line diff on the replaced lines): exactly 5 new
  `Fastener installability | UNKNOWN — NOT ANALYZED` matrix rows (one per
  detail matrix in the consolidated doc), the same entry added to the
  verdict-headline list, and the new ladder sentence in both standing-note
  occurrences. Nothing else moved.
- Baselines: `python scripts/regen_baselines.py --check` → "baselines are
  current." No baseline surface moved (the JSON baselines pin part/derivation
  counts, not family counts), so no regen was run.

## Sanity check (doc surface)

Compiled `details/sit_reach_box.spec.yaml` from the worktree and verified:
the coverage matrix carries `Fastener installability` with verdict
`UNKNOWN — NOT ANALYZED`, checks_run 0, note "no check of this family ran";
`report.require_clean()` still passes (NOT-ANALYZED is non-blocking — only
FAIL/UNRESOLVED block); the rendered markdown surface contains both the row
and the ladder sentence in the standing note.

## Suite

Final run from the worktree (`pytest -n auto -q`, venv python, shimmed
PYTHONPATH, import path re-verified at run start):
**1020 passed / 3 skipped / 1 xfailed** — exactly the master baseline; this
branch adds no tests (vocabulary + pin updates only). An intermediate run
before the golden regen was 1019 passed / 1 failed (the golden drift test,
as predicted) / 3 skipped / 1 xfailed.

## Environment note (import-path verification)

The brief's `PYTHONPATH="$PWD/src"` recipe cannot shadow the editable install
in this repo: the venv's editable hook is a meta-path *finder* mapping the
package name `detailgen` to the MAIN checkout's `src/` (the worktree has no
`src/detailgen/` directory — `detailgen` IS `src/`). Verified failure mode:
with the brief's recipe, `detailgen.__file__` resolved to
`/Users/joelwitten/Code/construction-detail-generator/src/__init__.py`.
Fix used for every run in this task: a git-ignored shim `.pypath/detailgen`
symlink → the worktree's `src/`, with `PYTHONPATH="$WORKTREE/.pypath"`. After
the shim, verification prints
`.../wt-install-family/.pypath/detailgen/__init__.py` (worktree) — re-checked
at the start of the final suite run. `.pypath/` is excluded via
`.git/info/exclude`, not committed.

## Residuals / honest UNKNOWNs

- The family reads `UNKNOWN — NOT ANALYZED` everywhere by construction; no
  emitter exists yet. That is the intended day-one state, not a gap.
- `UNRESOLVED` (blocking UNKNOWN) remains scoped to the support check; the
  installability axis checks will decide their own blocking semantics when
  they land (out of scope here).
