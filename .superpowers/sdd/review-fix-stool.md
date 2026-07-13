# Adversarial review — `sdd/fix-stool-station` (tip 3017765, base master 8d1f1df)

Fresh reviewer; every claim reproduced with independent probes in the worktree
(`import detailgen` verified to resolve into the worktree shim before every run).

## VERDICT: FIX-FIRST (one stale spec comment states wrong numbers about the
shipped geometry; everything geometric, every verdict, every pin, and the
process around the deviation verified TRUE)

Both fixes are comment/prose-level; no geometry, verdict, test, or baseline
changes needed. After F1 (one comment block) and optionally F2 (report wording),
this is a MERGE.

---

## Independently verified TRUE (own probes, not the implementer's)

### Geometry (claim 1 — station move), hand-measured from the compiled spec
- cleat +X spans X [3.750, 4.500]; side panel +X spans X [4.500, 6.000].
- `cleat screw +X 0/1` solid X [3.627, 5.500]: head cap 3.627–3.750, **head
  bearing plane exactly on the cleat free face x = 3.750**; shank 3.750→5.500.
- **-X mirror sign trap avoided**: `cleat screw -X` solids span X [-5.500,
  -3.627] with the head plane at **-3.750** = the true mirror
  `-(side_inner_x - cleat_thk)`, not the -a-b error (-5.25). Cleat -X spans
  [-4.500, -3.750]; panel -X [-6.000, -4.500]. Symmetric to +X.

### Termination (claim 2 — screw_len_h 1.25 → 1.75)
- 0.75" through the cleat + **1.00" bite into the panel ≥ 0.88"** half-length
  minimum [assumption]; tip at ±5.50 = **0.50" short of the outer show face
  (±6.00)** — no exit. Live verdict text matches the pinned strings verbatim
  (`1.00" bite into side panel`, `>= 0.88" declared minimum [assumption]`,
  `0.50" short of its far face`, `no undeclared exit`, GEOMETRY-PROVEN).
- **The deviation was necessary — probed myself**: mutating the fixed spec back
  to `screw_len_h: 1.25` (station move kept) yields
  `install_termination FAIL ×4: 0.50" bite < 0.62" minimum [assumption]`,
  report not ok. The brief's four-line move alone does NOT go green; master's
  old "PASS 1.25" bite" was indeed an artifact of the unbuildable station.
- The longer screw is a sanctioned fix-menu member
  (task-install-axes-report.md:265 — "longer screws, or an authored
  `install: embedment:` override with a defensible WHY"), and `screw_len_h` is
  a detailing dim the spec's governing-dims contract declares free to tune.
- Adversarial side-effects of 1.75 checked: tip stays 0.50" inside the show
  face (comfortable under tolerance); cleat penetration unchanged (0.75",
  splitting exposure identical to before); #10 × 1-3/4 is a standard purchasable
  size; `$screw_len_h` has exactly 4 component references, all cleat screws; no
  other check's verdict moved (16/16 install findings, all other families
  unchanged — full Counter pinned in the sweep and e2e).

### Interference allowlists now geometrically TRUE (claim 2 tail)
Boolean-intersected the actual world solids: screw ∩ cleat = 0.0180 in³ and
screw ∩ panel = 0.0240 in³ for all four screws (nonzero, proportioned to the
0.75"/1.00" spans with the tapered tip). On master the screw ∩ cleat allowlist
was vacuous (shank entirely inside the panel).

### Synthetic mutation pins the OLD flavor (claim 3) — and discriminates
- The test asserts the shipped station strings exist (count == 2 + 2) before
  replacing, so it can never silently no-op if the spec is refactored.
- Ran the mutation live myself: access **FAIL ×4** `head stationed AT the joint
  interface … station-not-face`, report not ok — the checker still catches the
  Phase-0 defect; the test fails if it ever stops.
- The report's residual disclosure is accurate: at the interface station the
  1.75" shank ALSO breaches the show face by 0.25" (termination FAIL ×4,
  observed live), so the pin honestly asserts only the length-independent
  axis-2 flavor. (Contrast: the caddy synthetic at test_install_sweep.py:135
  mutates the CADDY spec, which still carries `screw_len_h: 1.25` — no
  collision with this arc.)

### Tests / gates (claim on numbers)
- `pytest tests/test_install_sweep.py tests/test_step_stool_e2e.py
  tests/test_install_axes.py` → **47 passed** (matches the report's 20 + 27).
- `report.ok` True, `require_clean()` passes, e2e pins the full 16-finding
  install Counter + `Fastener installability == PASS` + perf test asserts ok.
- `regen_baselines.py --check` → "baselines are current"; no `step_stool` in
  `tests/baselines/`.

### Inherited nits (claim 5, commit 6787a2f) — each checked at source
- Probe-C Boulder dims: `Boulder.__init__(width, length, depth)` builds
  `.box(length, width, …)` (concrete.py:132) ⇒ length→X, width→Y. The corrected
  `Boulder(22.4, 2.0, 20)` at (61, 90, 54) gives x 60–62 / y 78.8–101.2 — the
  documented radial nut-hugger; the old `Boulder(2, 22.4, 20)` straddled the
  bolt axis (x 49.8–72.2). Correct, and the comment now records the signature.
- `_fmt` -0.00 clamp: logic sound (strips sign only when the rounded magnitude
  is exactly zero); pinned by `assert "-0.00" not in term.detail` in the CAT-A
  knife-edge test.
- `far_face_station` docstring now says ANTI-conservative (overstated margin)
  for rotated members — matches the actual AABB-projection behavior.
- HON-F3: direct string pin `"DECLARED order, not sequence-proven"` added in
  CAT-E. All 20 axes tests green.

### Isolation (claim h)
Diff touches exactly 6 files: the arc report, the stool spec, install.py +
test_install_axes.py (the sanctioned inherited nits), and the stool sections of
test_install_sweep.py / test_step_stool_e2e.py. The sweep diff stays inside the
flavor-(c) section; caddy/platform specs, their tests, and frozen truth are
untouched (verified via `git diff --stat` on those paths — empty).

---

## Findings

### F1 — FIX-FIRST (doc truth, in the shipped spec): stale 1.25"/0.5" comment
`details/step_stool.spec.yaml:168-171` — the cleat-screw component comment
describes the CURRENT geometry as "the 1.25in shank passes 0.75in through the
cleat and bites 0.5in into the panel — the buildable station". The shipped
shank is 1.75" with a 1.00" bite; a 1.25"/0.5" screw at this station is the
exact configuration the checker FAILs (probed above). It directly contradicts
the corrected param comment at :72-75. In a project whose core principle is
that geometry and doc never describe different fasteners, the spec's own
comment must not describe the pre-fix screw as the shipped one. One-line fix:
"the 1.75in shank passes 0.75in through the cleat and bites 1.0in into the
panel".

### F2 — MINOR (report accuracy / downstream doc truth): the rendered BOM says 1.8", not 1.75"
The OWNER FLAG states the re-delivered buy list moves "4× #10 × 1.25 in → 4×
#10 × 1.75 in". The actual generated BOM row prints `0.19" dia x 1.8"`
(fasteners.py:115 formats screw length via `fmt_in(length, 1)` — one decimal).
This display precision is PRE-EXISTING (the old 1.25 printed as 1.2"), so it is
not this arc's regression and I do not gate on it — but (a) the OWNER FLAG
misstates what the regenerated document will literally say, and (b) a buy list
reading "1.8-inch screws" names a non-purchasable size where "1-3/4" is the
real SKU. Recommend: amend the flag to state the rendered figure, and queue the
screw-length display precision (quarter-inch-honest formatting) as an owner nit
for the doc-regen step (task #18) — it affects every screw row repo-wide.

### F3 — INFO (downstream, no action on this branch)
R42's "countersink note" prose lives in the delivered vault document, not in
this repo; no generated stool .md exists in `outputs/` (views only) and doc
regeneration is explicitly downstream. Whoever regenerates must confirm the
new buy list and any countersink/screw-length prose reflect the 1.75" screws
(subject to F2's display caveat).

---

## Targeted numbers measured
- 47 passed (test_install_sweep 19 + test_step_stool_e2e 8 + test_install_axes 20).
- Stool install Counter: {(install_termination, PASS): 8, (install_access, PASS): 8}; ok=True; failures=0; blocking=0.
- Station-move-only probe (1.25 kept): {(termination, FAIL): 4, (termination, PASS): 4, (access, PASS): 8}; ok=False.
- Interface-station synthetic probe (1.75 kept): {(termination, FAIL): 4, (access, FAIL): 4, (termination, PASS): 4, (access, PASS): 4}; ok=False.
- Screw∩cleat 0.0180 in³ ×4; screw∩panel 0.0240 in³ ×4.
- `regen_baselines.py --check`: baselines are current.
