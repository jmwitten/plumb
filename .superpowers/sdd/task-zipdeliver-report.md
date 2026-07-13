# Task ZIPDELIVER — report (BLOCKED, not delivered)

**Verdict: STOP before delivery.** Verification point (b) fails outright and
point (a) fails on its specific required content. Per the task's own rule —
"an honest undelivered doc beats a delivered wrong one" — nothing was copied
to the vault or `~/Downloads`.

## Pipeline used

1. Read `task-docregen-report.md`, `brief-consolidated-report.md`,
   `consolidated-report-log.md` to learn the regen pipeline and prior delivery
   history.
2. Found the real prior vault copy by searching the vault repo and checking
   `git log` there: the file currently live at the vault destination is
   `/Users/joelwitten/Code/JoelBrain/05_Attachments/Organized/Zipline Platform
   Drawings/Zipline Build Document (model-backed) 2026-07-10.html`, delivered
   by vault commit `4b9f45a` ("INSTALL v1 re-delivery"), built from detailgen
   master `@ab11af4`.
3. Set up the shim: `mkdir -p .shim && ln -sfn "$PWD/src" .shim/detailgen`;
   verified `PYTHONPATH="$PWD/.shim" .venv/bin/python -c "import detailgen;
   print(detailgen.__file__)"` resolves to
   `/Users/joelwitten/Code/construction-detail-generator/.shim/detailgen/__init__.py`
   (repo src, not a stale install).
4. Ran the real generator: `PYTHONPATH="$PWD/.shim" .venv/bin/python
   scripts/consolidated_report.py` (no `--vault-copy`, so nothing outside the
   repo was touched by the build itself). Output:
   `outputs/consolidated/zipline-build-document.html`, 3.16 MB.
   - All 4 details **REUSED** their on-disk renders (hash-gate matched —
     confirms no geometry changed in this arc, as the task said).
   - Site: 180 parts, **4 open findings** (DIRTY — composed render gated):
     3 `foundation_capacity` + 1 `install_access` (rock anchor rod,
     cross-fragment).
   - BOM: 30 purchased lines, 6 existing lines. Cut plan: 3 sticks PT 2x4,
     4 sticks PT 2x6, 3 sticks PT 5/4x6 decking.
   - Build completed in 34s, no errors.

## Verification (a)–(e)

**(a) Platform's two top toe-screw verdicts read as declared-order clears — FAIL on required content.**
The platform's *Fastener installability* family verdict did flip, and does
carry the amendment-3 marker at the aggregate level:
> `PASS (42 clear(s) at a DECLARED build order — resolved on paper, declared, not sequence-proven)`

But the specific required phrases tied to the individual toe-screw checks —
`"geometry proven at the DECLARED build order"` and "the wedge-fact why" — do
**not** appear anywhere in the generated HTML (`grep -io` for both: 0 hits).
No per-fastener open/closed verdict list is rendered at all for the platform
in the consolidated doc — only the aggregate family-level PASS/count line
above. That per-check text only exists via `_render_install_section()` in
`scripts/single_detail_report.py` (the *single-detail* report builder), which
`consolidated_report.py` never calls.

**(b) New "Build Sequence" section + epistemic-contract table present — FAIL.**
- `grep -io "build.sequence"` → 0 hits. `grep -io "<h[1-4][^>]*>[^<]*sequence[^<]*</h[1-4]>"` → 0 hits.
- `grep -io "wedge"` → 0 hits.
- `grep -c "epistemic-contract"` (the actual `<table class='epistemic-contract'>`) → 0 hits (only a
  pre-existing prose "epistemic ladder" paragraph is present, unrelated to
  this arc's table).
- Root cause, confirmed structurally: `git diff ab11af4..43cd1a4 --
  scripts/consolidated_report.py` is **empty** — the STEPDOC/CPG v1-core arc
  did not touch this file at all. The new reader surface
  (`_render_build_sequence_section`, the `epistemic-contract` table via
  `epistemic_contract_rows`/`EPISTEMIC_TABLE_*` from
  `detailgen.validation.install`) was wired only into
  `scripts/single_detail_report.py`'s per-detail HTML build doc — never into
  the consolidated (4-detail, zipline) report builder this task regenerates.

**(c) Headline/blocking state honestly BLOCKED on the 3 foundation_capacity findings — PASS.**
Site coverage matrix: `Structural capacity | UNKNOWN — UNRESOLVED | 3 | 0 | foundation_capacity×3`.
Each of the 3 findings reads, verbatim (pier -Y / pier tree +Y / pier tree -Y):
> "uplift / lateral / soil-bearing capacity of platform/pier … is NOT ANALYZED
> (rung 4, engineer-of-record) — a represented foundation is never proven
> adequate; bearing_on_grade: field_verify. This BLOCKS a clean 'designed':
> the foundation is REPRESENTED, not verified"

The doc does not claim capacity is resolved anywhere.

**(d) Site rod-vs-rung UNKNOWN names BOTH missing mechanisms — PASS.**
The 4th open finding (`install_access`, rock anchor rod 1) reads, verbatim:
> "…the occupants belong to another site fragment (platform) and this
> fastener to 'rock_anchor' — no site-level cross-fragment sequencing exists
> in v1 (a CPG v2 site graph would order them); this epoxy-set rod's corridor
> is its own body's insertion path — insertion travel is not analyzed at any
> rung (P1)…"

Both named: cross-fragment order (CPG v2) and insertion travel (P1).

**(e) Old sentence "before a construction process graph exists" appears NOWHERE — PASS.**
`grep -c "before a construction process graph exists"` → 0.

## Net

3 of 5 checks pass cleanly (c, d, e). (a) partially passes (the aggregate
family-level wording is correct and honest) but fails the task's specific
requirement for per-fastener declared-order-clear text. (b) fails outright —
the section and table simply are not in this document's generator. Per the
task's stop condition, the document was **not** copied to the vault or
`~/Downloads`; the generated file remains only at
`outputs/consolidated/zipline-build-document.html` in the worktree/repo for
inspection.

## What would unblock this

`scripts/consolidated_report.py` needs the same wiring
`scripts/single_detail_report.py` got: call `_render_build_sequence_section`
(or the shared underlying `build_sequence_model`) and the epistemic-contract
table renderer for each of the four details (and/or the composed site), and
list the open/closed installability verdicts per fastener the way the
single-detail doc does. That's new work on the consolidated generator, not a
data problem — the underlying model (`build_sequence_model`,
`epistemic_contract_rows`) already has the correct information; it just isn't
called from this script. Recommend routing that as a follow-up task (owned by
whoever owns `scripts/consolidated_report.py`) before the next zipline
re-delivery attempt.

## Files

- Ran from: `/Users/joelwitten/Code/construction-detail-generator` (master `@43cd1a4`)
- Generated (undelivered): `/Users/joelwitten/Code/construction-detail-generator/outputs/consolidated/zipline-build-document.html`
- Prior vault copy (untouched, still the live doc): `/Users/joelwitten/Code/JoelBrain/05_Attachments/Organized/Zipline Platform Drawings/Zipline Build Document (model-backed) 2026-07-10.html`
- Nothing committed in either repo (per instructions, and moot since nothing was delivered).
