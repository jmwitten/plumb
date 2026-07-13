# Adversarial review — sdd/fix-platform-toe (platform toe-screw fix arc, CAT-B/F-6)

Fresh reviewer, independent probes only. Worktree tip 0bb18c4, base master
8d1f1df. Import path verified before every run
(`detailgen -> <worktree>/.shim/detailgen/__init__.py`).

## VERDICT: MERGE

Every claim I could measure held, including the one direction the arc could
have weakened the checker — verified by exact boolean intersection, not by
trusting the arc's own probe.

## What I verified (my own numbers)

### (a) Diff ownership — CLEAN
`git diff --stat 8d1f1df..0bb18c4`: exactly 5 files — platform.spec.yaml,
test_install_sweep.py, frozen_truth/platform.json, the SHARED
consolidated_doc.textlayer.html, and the arc report. No src/ change, no
caddy/stool surfaces. The spec diff is only the two `toe_screwed`
connections: `install: {tool: {length: "3 in", dia: "1 in"}}`, one new
assumption line each, and a source comment.

### (b) Fresh compile — verdicts match the claims
Compiled `details/platform.spec.yaml` in the worktree and validated:
- 12 toe install findings: 6 `install_termination` PASS + 4 `install_access`
  PASS + 2 `install_access` UNKNOWN — counts unchanged.
- All 12 texts carry `3.00" x 1.00" dia tool envelope`; zero carry 6.00".
- The 2 UNKNOWNs are the top screws (`toe screw ±Y 2`) and name exactly
  bolt/nut ±Y0 and ±Y1.
- Whole-report blocking set: 5 (2 install_access UNKNOWN + 3
  foundation_capacity) — same set as base.

### (c) The CANNOT-CLEAR claim and the adversarial mask sweep — both settled
Two independent probes, mine, not the arc's:

1. **Analytic AABB march** (point-to-box distance, 0.02in steps, tool radius
   0.5in, all 148 parts, all 12 corridors = 6 screws x 2 cheek candidates,
   full 6in): first-hit stations on the top corridors at 0.18in (washer
   AABB), 0.34in (bolt, nut). **No part's first entry falls in (3in, 6in]
   on ANY corridor** — the one way a shorter envelope could mask a real
   blocker. NONE found.
2. **Exact boolean intersection** (true tool cylinder vs true part solids at
   BOTH 3in and 6in, noise threshold 1.0 mm³): the full 6in true hit set is
   bolt (entry 0.82in, ~181 mm³) + nut (entry 0.58in, ~6 mm³) per top-screw
   cheek, **identical at 3in and 6in**. Middle and bottom screws: zero true
   intersection with anything over the full 6in — the 4 PASSes are genuine
   clears, not threshold artifacts. So shortening 6in→3in provably changes
   no hit set anywhere; the blocking UNKNOWNs cannot be cleared and the
   passes cannot flip.

The exact probe also resolved my one scare: the AABB march flagged the
**washer** (0.18in) and the middle screws' corridors grazing bolt boxes at
~1.0in — both are box-corner artifacts of my conservative probe; true-solid
intersections are empty (washer: thin disc, corridor misses it). The verdict
text naming only bolt+nut is correct.

Note: the arc report's "~0.35in" is the axis-entering-inflated-x-range
metric; true solid entry is 0.58–0.82in. Same conclusion (first inch), no
contradiction. I could not reproduce the report's 1.9"/1.06" lower-screw
margins metric-for-metric (different distance definitions), but ground truth
— zero intersection volume over 6in — is stronger than any margin number.

### (d) Frozen truth — structured JSON compare, base vs tip
IDENTICAL keys: `bom, by_kind, connection_kind_types, content_fp_divergence,
counts, findings (11,340 rows, 0 differing), geom_fingerprint, name, ok`.
CHANGED keys: exactly `_doc` (base-SHA sentence), `captured_at_sha`,
`content_fp`, `content_fp_spec`, `findings_fp`. The NO-geometry claim is
byte-verified: `geom_fingerprint` identical, as pledged.

### (e) Textlayer golden — token-level
`git diff --word-diff=porcelain`: exactly 4 tokens `6.00"` → `3.00"` — the
two toe UNKNOWN texts, each quoted in two sections (narrative + divergence
table). The rock-anchor UNKNOWN correctly keeps the 6.00" module default.
Nothing else moved.

### (f) The 3in x 1in stubby claim — honest
A stubby screwdriver / stubby impact driver is ~2.5–3.5in overall; a
right-angle adapter head is shorter. 3in x 1in is a real tool class, neither
optimistic (not 1–2in, which would have been the suspicious choice had the
author wanted to clear blockers — and per (c) even that wouldn't have) nor
absurd. The WHY names the tool ("stubby/right-angle driver") in the
connection assumptions and the spec comment. Note the blockers are hit
regardless, so there was no incentive-shaped number here. Minor inherited
nit (pre-existing on master, not this arc's text): "~3.5in clear gap" is
center-to-center (bolt centers 43.25/46.75in); the clear gap between bolt
AABBs is 2.85in.

### (g) Provenance — matches claim (5) exactly
Both resolved toe contracts:
`tool_envelope=authored_override`; `tool_axis=assumption`,
`embedment=assumption`, `method/entry_face/exit/head/stage=
connectiontype_default`; `tool_axis.angle=30.0, axis_idealized=True`;
display-idealization note present on the contract. The deliberate
non-authoring of method/angle (avoiding fake authored provenance on
assumption-grade values) is real in the resolved output, not just prose.

### (h) Tests (this worktree, import path asserted in-run)
- `tests/test_install_sweep.py tests/test_platform_spec.py
  tests/test_platform_detail.py`: 45 passed (sweep 20 incl. the new
  mechanism pin, platform spec 17, platform detail 8).
- `tests/test_spec_presentation_equiv.py` (the shared textlayer golden's
  consumer): 8 passed.

## Findings

- **NONE blocking.**
- INFO (inherited, out of arc scope): the "~3.5in clear gap" wording in the
  pre-existing hanger assumption is center-to-center, not clear distance
  (2.85in) — cosmetic, predates this branch.
- INFO: the report's corridor-station and margin numbers use different
  metrics than a naive re-derivation will produce (envelope-inflated axis
  entry vs true-solid entry; axis-to-blocker distance). Conclusions verified
  identical by exact boolean intersection; future reports could state the
  metric next to the number.

## Why MERGE

The change is exactly what it claims: an epistemic upgrade (module-default
tool → declared, provenance-stamped, doc-disclosed, pin-guarded authored
envelope) with provably zero behavioral movement — and the zero was verified
in the dangerous direction (mask check) by independent exact geometry, not
by symmetry hand-waving. The shared textlayer golden is the only
cross-branch coupling; the controller's sequencing note stands.
