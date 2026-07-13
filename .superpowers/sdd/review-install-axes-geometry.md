# Adversarial review — INSTALL axes branch, GEOMETRY-CORRECTNESS lens

**Tree under test:** worktree `wt-install-axes`, branch `sdd/install-axes`, tip `d8737f4`.
**Reviewer stance:** fresh, geometry/math only. Read all 801 lines of
`src/validation/install.py`, `src/assemblies/installation.py`, the binding design doc,
and the task report. Import path verified before every run
(`detailgen.__file__` → `<worktree>/.shim/detailgen/__init__.py`). No worktree files
touched; all synthetic assemblies built in memory; no full-suite run.

## Verdict: **FIX-FIRST**

The shipped-detail verdicts are right — I hand-recomputed six pinned numbers and all
reproduce exactly (see §Hand-recomputations). The axis-aligned chord math, the contract
derivation, the head-station classification, the platform toe-screw cheek selection,
and the prefilter accounting are all correct as exercised. But two constructed
counterexamples make the checker's central promise — a **GEOMETRY-PROVEN** "no
undeclared exit" / "wrench side clear" — provably false on realistic geometry, and one
shipped verdict prints a false geometric statement inside a GEOMETRY-PROVEN sentence.
Under this project's own epistemic-ladder discipline (guardrail #6: no surface claims a
stronger rung than its mechanism proves), those are fix-before-merge, not notes.

---

## Findings

### F1 — MAJOR: axis-1 breach detection judges only the DEEPEST chord; an undeclared exit is silently masked by any material past the tip, including material the screw never touches

`_termination_shank` (install.py:454–475): `breaches = shank_len > deepest.s_out +
_FACE_TOL`, where `deepest = max(on_path, key=s_out)` over chords from **every member in
the assembly** (`chords()` skips only `{f.id} | scope.stack`). There is no chord
**continuity** check and no **membership** check that the terminating chord belongs to
the connection. Three confirmed flavors:

**F1a — gap-jump into a foreign part (Probe A).** Screw enters plate A (z 0–88.9),
passes anchor B (88.9–127.0), **breaches B's far face by 0.51″**, crosses a 5 mm air
gap, bites 8 mm into foreign slab C (132.0–170.1). Contract: `cleat_screwed` default,
`exit=none`. Measured output:

    install_termination | FAIL | embedment below the declared minimum: 0.31" bite into
    foreign slab < 2.76" minimum [assumption] (GEOMETRY-PROVEN ...)

No "undeclared exit" FAIL at all — and the embedment verdict credits the bite **into a
part that is not a member of the connection**, with no disclosure. With
`embedment=None` authored (Probe A2) the whole axis reads:

    install_termination | PASS | terminates inside foreign slab (1.19" short of its
    far face) — no undeclared exit (GEOMETRY-PROVEN ...)

(Defense-in-depth note: this flavor produces a real screw∩C overlap, so the
interference stage would still block it — the axis verdict is wrong but the doc is not
CLEAN.)

**F1b — phantom chord from the oversized probe masks a breach into OPEN AIR (Probe B)
— fully silent, default contract, no other check fires.** The chord probe radius is
`shank_r + _HOLE_CLEARANCE` (2.413 + 2.5 = 4.913 mm here) so that a bolt/rod registers
its own modeled clearance hole's wall — but it is applied indiscriminately to every
part. Geometry: screw through head plate (z 0–38.1) into anchor block (38.1–76.2), tip
at z=88.9 — **breaches the anchor's far face by 0.50″ into open air; nothing exists on
the axis past 76.2**. A parallel stud runs alongside, its near face 4.6 mm off the
shank axis (2.2 mm of clear air off the shank *surface* — the screw never touches it),
spanning past the tip. Measured output under the **fully default** contract:

    install_termination | PASS | terminates inside parallel stud (1.97" short of its
    far face) — no undeclared exit; 3.50" bite into parallel stud >= 1.75" declared
    minimum [assumption] (GEOMETRY-PROVEN ...)
    install_access     | PASS | clear tool corridor ...

Every clause of that termination sentence is geometrically false: the screw does not
terminate inside the stud, has 0.00″ bite into it, and has an undeclared 0.50″ exit.
Because there is no actual solid overlap, **no interference finding fires either — this
ships CLEAN.** This is precisely the live-verified defect class the branch exists to
catch (the caddy's silent show-face breach), reproduced as a silent pass. Realistic
trigger: any member face within ~2.5 mm of a screw's surface beyond its breach station
— inside corners, gapped decking over a breaching screw, a screw driven beside a
perpendicular cleat. The same mechanism masks a breach into a **foreign part's modeled
bore** (hole clearance 0.25 mm < probe oversize 2.5 mm ⇒ the hole wall registers as
on-path material and hole air counts as bite).

**Fix shape (suggestion, not implemented):** (1) require the terminating/anchor chord
to be a `scope.members` part — anything else is at minimum a named disclosure, arguably
FAIL/UNKNOWN; (2) walk chords in station order and treat a gap > tolerance before the
tip as an exit at the last member chord's face; (3) use the oversized radius only to
bridge the fastener's OWN stack/hole (two-pass: thin probe for stations, oversized pass
only for parts in `scope.stack` or the entry/anchor members).

### F2 — MEDIUM/MAJOR: through-bolt wrench-side sweep starts at the TIP, so the span [far face → tip] — exactly where the nut lives — is never swept (Probe C)

`_access_shank` (install.py:679): `sides = [..., ("wrench side (past the nut): ", tip,
d)]`, base at the tip + 0.5 mm. Constructed: CAT-C clamp, 4″ bolt, tip 1.00″ past the
nut plate's far face, nut at y 72.9–87.1. A foreign disc at y 78.8–101.2, 9–11 mm off
the bolt axis — wrapped around the nut's station, inside the declared 12.7 mm corridor
radius; no socket can reach that nut. Measured output:

    install_access | PASS | ... wrench side (past the nut): clear (GEOMETRY-PROVEN ...)

The unswept gap equals the bolt overshoot — on the shipped platform that is the 0.92″/
1.42″ protrusion zone, so anything hugging a protruding bolt end (gusset, flange,
adjacent member face) is invisible to the two-sided-access claim. The driver side has
no analogous hole (its sweep from `head_bearing` backward covers the head region).
**Fix shape:** start the wrench-side sweep at the declared exit face's station (or at
`min(tip, exit-face station)`), keeping `scope.stack` in the skip set so the nut/washers
themselves don't self-block.

### F3 — MINOR (but live in shipped verdicts): "N″ short of its far face" prints the 50 mm probe cap, not the member's far face

`chords()` truncates every chord at `ahead = shank_len + max(2·_FACE_TOL, 50.0)`, and
`_termination_shank` prints `deepest.s_out − shank_len` as "short of its far face".
Whenever the terminating member extends more than 50 mm past the tip, the printed
number is exactly 50 mm (1.97″), not the face distance. Live in the shipped step stool:
all four up-screw PASS verdicts read "terminates inside side panel +X (**1.97″** short
of its far face)" — the panel's real far face is **8.25″** past the tip (head z=10.25″
driving −Z, panel spans z 0–9.25″; 10.25 − 2.00 shank = 8.25). 50/25.4 = 1.9685 ≈ 1.97
— arithmetic confirmed. The same artifact appears in Probe B's output ("1.97″", true
2.5″) and would appear in `through_exit_required`-absent FAIL wording. Verdict classes
are unaffected (breach compare is `s_out ≥ shank_len` side, bite is `min(shank_len,
s_out)` — both truncation-immune), but this is a false geometric statement inside a
sentence labeled GEOMETRY-PROVEN. Fix: compute the face distance from the part's bbox
projected on the axis, or stop printing the phrase when the chord hit the probe cap.

### F4 — LOW: tilted-member chord error bound is r·tan θ, not "~one probe radius"

Docstrings (`_PROBE_R`, `_Sweep.chords`, task report) document the tilted-member
station error as "at most ~one probe radius". The true bound for a face tilted θ from
axis-perpendicular is r·tan θ — matches "~r" only for θ ≤ 45°, unbounded at grazing
incidence. No shipped shank-mode fastener is tilted (verified claim; all six
hand-recomputed cases are axis-aligned), so this is a documentation-accuracy item, but
the honesty wording should carry the real bound or the θ ≤ 45° qualifier.

### F5 — LOW (angled sweep, REPRESENTED rung, no shipped impact): three geometric approximations worth recording

- `_cheek_candidates` offers only the **thinnest** perpendicular pair. A member whose
  usable toe face is the wide pair (both thin cheeks blocked, wide face open) gets a
  false block/UNKNOWN — conservative direction, but the verdict wording claims "every
  declared corridor candidate … obstructed" when a real cheek was never tried.
- Face planes come from the **world AABB**; for a rotated member the plane sits outward
  of the true face, so the corridor base starts too far out and a blocker hugging the
  true cheek face is under-swept (anti-conservative). The docstring calls this
  "conservative outward" — for blocker detection it is the opposite.
- `t_dir = n·sinθ − d·cosθ` is unit-length only when n ⊥ d; the candidate filter admits
  |n·d| up to 0.5, where the effective angle off the face deviates from the declared θ.
  All shipped angled cases have n·d = 0 exactly (verified on the platform toe screws).

### F6 — LOW: per-connection stack UNION over-excludes across role groups

`check_installability` builds `stack_of[connection] = ⋃ ri.stack` and every fastener's
axis-1/axis-2 skip set uses the whole union. In a connection carrying both a bolt stack
and a screw group, the bolt's nut/washers can never block the screws' corridors (and
never appear as chord material) even when geometrically they do. Shipped details are
unaffected — I dumped every multi-role-group connection: platform hanger connections
(stack = the hanger itself, exclusion arguably correct since the screws pass its
flange) and all bolt stacks live in single-fastener connections. Synthetic-only today;
worth a comment or per-group scoping before a type with mixed hardware lands.

### F7 — INFO: probes that came back clean

- **_BEHIND_SPAN 305 mm**: a burial deeper than 12″ saturates the printed depth (probe
  base starts inside material) but still FAILs — nothing escapes silently; the deepest
  shipped burial is 4″. A head buried in a NON-entry member is not classified "buried"
  but its material blocks the corridor sweep, so it still reads non-pass (as
  obstruction) — acceptable, message-precision only.
- **Inclusive tip filter** (`s_in < L + _FACE_TOL`): correct for the blind-hole class
  (rock anchor); the butted-member tie at the tip resolves to the true anchor via the
  `s_in` sort. Its failure modes are exactly F1's (gap/foreign chords), not the filter
  itself. Point-touch/coincident-face slivers fall under `noise_volume` (1 mm³) —
  honest drop.
- **AABB prefilter accounting**: cylinder AABB is a true superset for any direction;
  gap > threshold cannot intersect; `skipped + checked == total` holds by construction
  over the counted candidate set (skip-listed and fastener-class parts are excluded
  from `total` by definition — consistent with the docstring's accounting rule).
- **Same-role-group sibling exclusion**: scoped to `scope.ri.fasteners` only (verified
  live: platform hung screws do NOT exclude header screws); the co-driven rationale is
  documented and the design accepts it.
- **Angled cheek selection on the shipped platform**: picked the end joist's ±X 1.5″
  faces (the physically correct toe cheeks), tried both, and the two UNKNOWN top
  screws name the leg thru-bolts/nuts with owning connections — hand-checked the
  bolt-vs-corridor distances and the per-screw top/lower split is geometrically right.

## Hand-recomputations (all reproduce exactly)

1. **Caddy up screw burial + bite**: rail z −5.5..0″, head_bearing z −1.5″, shank 2.0″,
   top board z 0..1″. Entry chord s_in = −4.0″ ⇒ "stationed **4.00″** inside …
   (mid-plate, **1.50″** short of its far face)" ✓; bite = min(2.0, 2.5) − max(0, 1.5)
   = **0.50″** < 1.00″ (half of 2″) ⇒ FAIL ✓. Side screws: bite 1.25 − 0.75 = 0.50″ <
   0.62″ ✓; sofa-arm corridor UNKNOWN across the 0.25″ reveal ✓.
2. **Stool interface station**: cleat x 3.75–4.50″, panel starts 4.50″, head_bearing at
   x = **4.50** ⇒ entry chord s_in = −0.75, s_out = 0.0 ∈ (−1 mm, 1 mm) ⇒
   station-at-interface FAIL, "0.75″ past cleat's free face" ✓. Cleat-screw bite
   1.25″ into panel ✓, "0.25″ short of far face" ✓ (untruncated — real).
3. **Platform bolt exit overshoot**: beam +Y inner face y = 15.00″, bolt tip y = 14.08″
   ⇒ **0.92″** past the declared far plate ✓; nut side declared ⇒ required-exit PASS ✓.
4. **Trebuchet butt screw**: head x 9.50 (rail free face), tip 7.00, rail 8.00–9.50,
   cross member −8.00..8.00 ⇒ bite = 2.5 − 1.5 = **1.00″** < 1.25″ ✓.
5. **Trebuchet upright lap screw**: tip 7.25, upright 7.00–8.00 ⇒ bite = min(2.25, 2.5)
   − 1.5 = **0.75″** < 1.12″ ✓, terminates 0.25″ short of the upright's far face ✓.
6. **Truncation arithmetic** (F3): 50 mm = 1.9685″ = the printed "1.97″" on all four
   stool up screws, whose true far-face distance is 8.25″.

## Why FIX-FIRST and not REVISE

The architecture is right: contract-derived verdicts, per-member `.vals()` chords,
station math, classification ladders, and determinism all check out against shipped
geometry, and the branch's honest re-pins (trebuchet, sit_reach_frame) are measured
truth. F1/F2 are localized mechanism holes with clear fix shapes inside
`_termination_shank`/`chords`/`_access_shank`, plus a one-line wording fix for F3 —
they do not implicate the design. But they cannot ride to master as-is, because each
one lets the exact defect family this branch was chartered against (a silent undeclared
breach; a false two-sided-access clear) ship under a **GEOMETRY-PROVEN** label, and
probe B's flavor ships fully CLEAN with no other stage catching it. Fix F1 (membership
+ continuity + probe-oversize scoping), F2 (wrench sweep from the exit face), F3
(truthful far-face distance), and pin probes A/B/C as regression tests; F4–F6 may land
as docstring/comment corrections now or as named residuals.
