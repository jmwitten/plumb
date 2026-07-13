# Adversarial review — sdd/install-schema, MECHANICS/REGRESSION lens

Reviewer: fresh adversarial reviewer (machinery + regression surface).
Branch tip a731952, base d57bf8a, master 353224a merged in at 58ea2e0.
All runs from this worktree with the .shim import path, `detailgen.__file__`
verified into the worktree before every run I relied on. Pristine-master
probes ran read-only in the main checkout (353224a, no PYTHONPATH).

## VERDICT: MERGE

No blocking findings. Every claim I attacked reproduced under my own probes;
the highest-risk change (the baseline re-freeze) is exactly as narrow as
claimed. Four low-severity notes below, none merge-gating.

## Suite numbers I measured

- Full suite, this worktree, `pytest -n auto -q`: **1060 passed / 3 skipped /
  1 xfailed** in 342s — matches the report exactly.
- Collection accounting: branch collects 1064 items vs master's 1024 (+40);
  the two new modules collect exactly 38; `test_scripts_spec_rewire`
  contributes exactly 2 new parametrized guard cases naming the new install
  test files. +40 = 38 + 2, verified.

## Findings

### LOW-1 — report overstates geom_fingerprint tightness (report text only)

The report claims re-freeze geom churn of "1e-11..1e-14". My structured
field-by-field diff measured max abs delta **1.19e-07** (platform, 1480
numbers) and **3.73e-09** (rock_anchor, 260 numbers). Both are safely under
the 1e-6 oracle (`tests/test_platform_spec.py:27` TOL), so nothing is at
risk, but the report's characterization is off by 4–7 orders of magnitude.
Correct the wording if the report is kept as testimony; no code change.

### LOW-2 — authored `exit: through_exit_required` with no `exit_faces` silently drops the default face-set

`loader._build_install` requires `exit_faces` for `concealed_exit` but not
for `through_exit_required`; `compiler.build_install_overrides` then builds
`Exit("through_exit_required", ())`, which REPLACES a type default that
carried the nut-side face (bolted_clamp) — losing the far-side checkability
the contract exists to provide, with no diagnostic. Mechanically confirmed
by code read (compiler.py `if ispec.exit:` branch). The axes branch will
surface it as an uncheckable exit, so it degrades honestly rather than
lies — but a loader teaching error (mirroring the concealed_exit rule)
would be cheap. Fine to defer to the axes branch.

### NOTE-3 — unknown role surfaces as a raw ValueError at validate() time

An `install: {role: <typo>}` loads and compiles cleanly and only raises at
`Detail.validate()` (via `Connection._resolve_install`,
connection.py:466-577), as a ValueError rather than a Spec*Error. The
message is excellent (did-you-mean, lists the type's role groups), and this
matches the pre-existing `_require_hardware_roles` convention of role-guard
ValueErrors at generate_checks time — so consistent, just later than the
other install teaching errors. Observation only.

### NOTE-4 — zero-fastener role group produces an empty contract

`cleat_screwed` with `n_screws=0` and no hardware yields a resolved contract
with `fasteners=()`, `embedment=None`, and a DerivedFact with empty
`subjects`. Verified harmless: the evidence orphan guard keys on the
connection label (evidence.py:500-511), empty subjects just add no
`concerns` edges, nothing crashes. Slightly odd data (a contract "for"
nothing); acceptable.

### Pre-existing, NOT this branch (for the ledger)

Two fresh compiles produce derivation logs whose "allowed intersection ..."
facts differ in ORDER/pairing run-to-run (set iteration; 14 facts wobble on
step_stool). Reproduced identically on pristine master — pre-existing, and
invisible to baselines (detail_counts stores lengths; frozen findings don't
include the log). The 42 new install-contract facts are byte-stable across
fresh processes (identical sha both runs). Worth a ledger note someday;
not this branch's problem.

## Status per attack

1. **Full suite**: 1060/3/1 measured myself; +40 accounting verified by
   collection diff (1024 → 1064; 38 + 2). MATCHES.
2. **Baseline re-freeze**: my own python json field-by-field diff of
   platform.json and rock_anchor.json at d57bf8a AND 353224a vs branch tip:
   `findings` (full multiset), `by_kind`, `findings_fp`, `bom` all
   byte-identical; only `counts.derivation_log` (688→722, 100→104),
   `content_fp`/`content_fp_spec`, `captured_at_sha`, `_doc`, and
   sub-oracle geom float noise moved. Platform `ok: false` confirmed
   pre-existing at d57bf8a (false→false); rock_anchor true→true.
   refreeze_from_spec.py edit read: EVOLVED gains rock_anchor with an
   honest rationale comment (imperative-era record retrievable at b52626b);
   no comparison logic touched, nothing weakened. tree_attachment /
   trolley_launch untouched (their counts carry no derivation_log — no
   justified diff, consistent). CLEAN.
3. **Teaching errors**: 13 of my own bad-YAML probes (unknown key, bad
   exit, concealed_exit w/o faces, exit_faces w/o exit, angle 95 / string /
   bool, tool missing dia, entry missing face, empty block, role-only
   block, unknown role, non-mapping install) — every one a helpful
   diagnostic, zero crashes, zero silent accepts. Unknown role = NOTE-3.
4. **Round-trip**: my own patched platform spec with an install: inside the
   joist-hanger `repeat:` body (`entry: {part: "joist_{k}"}`) + a second
   block with concealed_exit/faces/tool: `load(dump(doc)) == doc` True,
   dump byte-stable True, both blocks survive the dump. Repeat expansion
   resolves PER-ITERATION Placed ids (lumber-2/3/4 across joists 0/1/2)
   with correct authored_override stamps. A no-install spec dumps
   BYTE-IDENTICALLY on master and branch (sha-equal dumps of all 3 probe
   specs). CLEAN.
5. **Determinism**: install contracts + describe() byte-stable across two
   fresh processes (identical shas, 34+4+4 contracts);
   test_evidence_determinism rerun explicitly, 2 passed (includes the
   shuffle order-invariance). Whole-log wobble is pre-existing (see above).
6. **Both build paths**: shipped site.spec.yaml compiles + validates
   (ok=False on branch AND pristine master — pre-existing, platform's
   foundation UNKNOWN); the compiled site model carries **38** resolved
   contracts (34 platform + 4 rock_anchor — matches the fragment deltas),
   so site-composed connections do NOT silently lose contracts. My own
   synthetic site doc with a SITE-LEVEL cross-subsystem connection +
   install: override resolved through the shared helper correctly
   (authored embedment/head stamped authored_override, type defaults
   retained). The report's admitted gap (no in-tree site install e2e test)
   is real but hides no defect; recommend the axes branch add one.
7. **No behavior change on shipped specs**: master-vs-branch probe on
   platform / rock_anchor / step_stool: findings multiset IDENTICAL
   (11176 / 379 / 121), ok flags identical, zero facts lost, derivation
   log grew by exactly +34/+4/+4 facts, every new fact starts
   "install contract". No shipped spec authors an install: block
   (grep-verified). CLEAN.
8. **generate_checks edge cases**: zero-hardware group (NOTE-4, no crash),
   no-default type + fasteners → exactly one blocking UNKNOWN
   install_method finding, authored-only contract path works, named role
   on no-default type raises the intended teaching ValueError, no-default
   type with no fasteners is silent, length-less fastener → honest None
   embedment with its note. Repeat-expanded connections exercised via
   probe 4 and the shipped platform. No new crash paths found.

Probe files live in the scratchpad (probe_teaching.py, probe_roundtrip.py,
probe_findings.py, probe_site.py, probe_determinism.py, probe_edge.py,
frozen_diff.py); the temporary details/_probe_site.spec.yaml was removed
after the run. No git state mutated.
