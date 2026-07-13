# Adversarial review — branch `sdd/install-family` (d1c7f48, base d57bf8a)

**Verdict: MERGE.** No blocking findings. Independent reviewer, fresh context;
every claim below is something I reproduced myself (own probe scripts, pristine
master compared against the branch worktree), not the implementer's word.

## What I verified, independently

1. **Full diff read (d57bf8a..d1c7f48).** 8 files, +172/−9. Every changed line
   is vocabulary, wording, a count re-pin, or the regenerated golden. No check
   semantics changed; nothing weakened; zero `Finding(` constructions in the
   diff (grep count 0). The three kinds appear in `src/` ONLY in the three
   vocabulary tables (KIND_TO_FAMILY, RENDERABLE_CHECK_KINDS, _IMPERATIVE_DECL)
   — no emitter exists, exactly as claimed.

2. **Pristine-master vs branch behavior probe** (my own script; compiled
   `details/sit_reach_box.spec.yaml` both places; import resolution verified
   before each run — master: main-checkout `src/__init__.py` with no
   PYTHONPATH; branch: `.pypath/detailgen/__init__.py` inside the worktree):
   - master (fb6c627 ≡ base d57bf8a for src/tests — the two commits between
     them touch only progress/retro docs): **8 families**, no installability
     row, `require_clean()` OK.
   - branch: **9 families**, `Fastener installability` positioned exactly
     after `Construction completeness`, verdict exactly
     `UNKNOWN — NOT ANALYZED`, checks_run 0, `require_clean()` OK
     (non-blocking day-one state confirmed by execution, not by reading).

3. **Golden diff honesty — programmatic, not eyeball.** I wrote a
   SequenceMatcher probe over the old/new golden: the change is **insertions
   only** (any deletion or within-line non-insert edit would have failed the
   probe). Exactly: 5 pure inserted matrix rows, all reading
   `Fastener installability … UNKNOWN — NOT ANALYZED / 0 / 0 / —`; 3 replaced
   lines whose within-line diffs are pure insertions — the verdict-headline
   `vh-row` for the new family, and the ladder sentence in both standing-note
   occurrences. Nothing else moved. Matches the report's claim exactly.

4. **STANDING_NOTE wording vs guardrail #6.** The ladder reads
   "installation-method-REPRESENTED, then GEOMETRY-PROVEN, then
   SEQUENCE-PROVEN" — the exact rung order of guardrail #6
   (REPRESENTED < GEOMETRY-PROVEN < SEQUENCE-PROVEN), phrased in the house
   style of the existing support ladder. The honesty rule holds: "a
   represented installation method is a declared claim, not proof the
   fastener can be driven; sequence-dependent access is NOT ANALYZED until a
   construction process graph exists." No UNKNOWN is phrased as safe — my
   probe greps the RENDERED matrix markdown for "is safe" / "safe to" /
   "no issues" style leakage: none. `test_standing_note_carries_the_
   not_analyzed_honesty` still pins NOT ANALYZED + REPRESENTED + absence of
   "is safe", and the golden now pins the full ladder sentence at the
   presentation layer.

5. **Re-pins are the new truth, not weakenings.** All three count changes are
   exact-equality assertions updated to the measured post-change truth
   (tuple pin gains the family in position; `family_verdict == 9`;
   unknown-count `== 6` at both assertion sites). Nothing was deleted or
   relaxed to `>=`. The two "stale docstring" fixes the implementer flagged
   are genuine pre-existing staleness, verified at the base commit:
   `git show d57bf8a:src/validation/coverage.py` says "The seven invariant
   families" over an 8-entry tuple, and
   `d57bf8a:tests/test_inspector_payload.py` says "four un-analysed families"
   beside `assert len(unknown) == 5`. The corrections (nine; six) match the
   new reality.

6. **EXPECT_CHECKS exclusion is real.** On the branch,
   `EXPECT_CHECKS = ('bearing', 'interference', 'connection_hardware',
   'bond', 'floating', 'dimension')` — none of the install kinds — verified
   by import, not by reading. The deliberate-exclusion comment sits on the
   RENDERABLE_CHECK_KINDS entry (src/spec/schema.py:786-790) so a later
   branch can't "helpfully" add them. An installability FAIL is therefore
   not pinnable/silenceable from a spec.

7. **Full suite, run by me** from the worktree with the `.pypath` shim,
   import path asserted to resolve into the worktree at run start
   (`pytest -n auto -q`, repo venv):
   **1020 passed / 3 skipped / 1 xfailed** — the master baseline, as claimed.
   `scripts/regen_baselines.py --check` → "baselines are current." The JSON
   baselines and frozen_truth carry no family counts (grepped), so the
   textlayer golden was the only presentation surface owed a regen.

8. **Mapping completeness/disjointness.** `family_of()` maps all three kinds
   to "Fastener installability" (probed by import);
   `KIND_TO_FAMILY ∩ PROVENANCE_ONLY_KINDS = ∅` still holds and covers the
   new kinds by construction (set-level test); the four-details emitted-kind
   sweep passes (in-suite). `_IMPERATIVE_DECL` carries well-formed
   (aspect, label) pairs for all three.

## Non-blocking nits (fine to fold into the next INSTALL branch)

- `tests/test_coverage_matrix.py:262` and `:297` — comments still say "the
  five unanalyzed families"; the truth is now six. The assertions are
  `>= 5` so nothing fails, but the same stale-comment class this branch
  fixed twice elsewhere is being minted anew.
- `test_family_of_maps_every_kind_data_driven`
  (tests/test_coverage_matrix.py:77) has no positive `family_of()` assertion
  for the three new kinds — the mapping is pinned only via the KIND_TO_FAMILY
  table itself. One line each would make the emitter branches fail loudly
  here too if the mapping ever drifts.
- The suite's `>= 5` UNKNOWN-count floors in the two markdown-rendering tests
  are now looser relative to reality (6); harmless, same remark.

## Verdict

MERGE. The branch does exactly what the vocabulary slice of INSTALL Phase 1
promised, and nothing else: the family exists on every report surface as an
honest non-blocking `UNKNOWN — NOT ANALYZED`, the ladder wording obeys
guardrail #6, the kinds are mapped ahead of their emitters, and the
one deliberate asymmetry (renderable but never pinnable) is both real and
documented in place.
