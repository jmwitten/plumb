# Fresh adversarial review — STEPDOC/CPG +process

**Branch:** `codex/stepdoc-process`

**Initial verdict:** NOT READY FOR FULL GATE

**Confirmation verdict:** READY FOR FULL GATE

## Initial findings

1. Direct Python callers could bypass schema validation with malformed
   `ResolvedAfter` values: blank or non-string `why`, an empty `after` tuple,
   and blank target/source/kind fields reached the runtime graph boundary.
2. The reusable `Glued` connection-type docstring repeated the caddy-specific
   cure-before-side-screws strategy. That cross-connection order belongs only
   to typed `sequence.after` authoring.
3. CAT-K's reversion test did not follow the deleted authored constraint
   through every reader projection.
4. The branch contained unrelated reader-name review/ledger material and
   whitespace noise.

## Fix round

Commit `d2aba85` closes the findings:

- Runtime graph validation now rejects every malformed direct-construction
  case with field-specific `sequence.after` diagnostics.
- `Glued` owns only bond and cure semantics; it no longer authors a consumer
  connection's project-specific sequence.
- CAT-K reversion now checks graph constraints, authoritative derivation,
  epistemic rows, the shared model, Markdown, and HTML. The surviving +X
  claim and both derived bond-before-cure edges remain.
- Unrelated reader-name files/ledger text were removed and
  `git diff --check origin/main..HEAD` is clean.

## Independent confirmation

The fresh reviewer re-ran the original malformed-runtime probes and the
expanded CAT-K selection on the final diff:

```text
82 passed / 106 deselected
```

It also confirmed:

- no remaining Critical, Important, or Minor findings;
- no reader-name, manual, or +presentation leakage;
- a clean worktree and clean branch diff check.

**Final verdict:** READY FOR FULL GATE.
