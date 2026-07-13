# Adversarial review — branch `sdd/fix-caddy-pocket` (caddy pocket-joint fix arc, CAT-A live)

**Reviewer:** fresh adversarial reviewer, independent probes only.
**Tree:** tip 1ceba23 off master 8d1f1df. Import path verified before every run
(`import detailgen` → `<worktree>/.shim/detailgen/__init__.py`).

## VERDICT: FIX-FIRST

One MEDIUM doc-honesty finding (the buy list bills idealization hardware for the
pocket joint with no disclosure — F-1 below, one sentence of prose to fix, no
vocabulary needed). Everything else independently confirmed at MERGE grade:
the authored embedments are defensible and fully disclosed, the checker changes
are strictly additive, the verdict flips reproduce exactly, the reversion probe
restores the original defect in full on the shipped spec, the note-filter kills
the doc-surface lie in both directions, the spec round-trips byte-stable, and
no shared baseline or sibling-owned surface moves.

## Findings

### F-1 (MEDIUM, doc surface — the one fix): the buy list bills the display
idealization's hardware for the pocket joint, undisclosed at the point of sale

`validation_report.md` §Bill of materials bills `4 | Structural Screw | 0.19"
dia x 2.0"` — the four UP screws the same document declares are pocket screws.
The only note on that BOM row is about thread rendering. The honest-limits
bullet does say the drawn straight screws are a display idealization, but it
speaks about the DRAWING; nothing anywhere tells a purchaser the buy list is
billing those drawn stand-ins. Worse than a labeling gap: a 2.0" screw driven
from a pocket in the 0.75"-thick rail's inner face at 15° reaches ≈1.93"
vertically (less pocket depth) into a 1.0" top — a builder who follows the
technique AND the buy list drives the billed screw out the show face. This is
the same class as the "embedment default" note this very branch killed as "an
honest-looking lie on the doc surface." The arc report flags the BOM shadow
honestly as a residual and is right that fixing the BOM LINE needs the pocket
vocabulary — but a disclosure does not. Fix: one sentence in the pocket-joint
honest-limits bullet (or the BOM row's assumption), e.g. "the buy list bills
the drawn display screws; a real pocket joint uses purpose-made pocket screws
sized at the jig (shorter than the billed 2" — do not drive the billed screws
from the pockets)."

### O-1 (LOW, observation, pre-existing semantics — no action): the angled
sweep passes on EITHER clear cheek, independent of the declared face name

`_access_angled` derives both cheek candidates from the entry PART and returns
PASS on the first clear one; the declared descriptor (`inner_face`) never
selects a side. If the declared inner-face corridor were blocked and the outer
clear, the verdict would read PASS naming the OUTER cheek. Not silent (the
wording names the cheek actually used, and every angled verdict stays
REPRESENTED-rung), and identical semantics already governed `exposed_face`
before this branch — the `inner_face` addition opens no new hole. Worth
remembering when the pocket vocabulary lands and the entry face becomes real
geometry.

### Attack results (all held)

1. **Authored embedments — DEFENSIBLE, not green-chasing.** Hand-verified from
   the compiled model and spec deriveds: top = 5/4 stock = 1.00" thick, so the
   2" up screw's half-length default (1.00") EQUALS the top's thickness —
   declaring the default declares a show-face breach, contradicting
   `exit: none`. 0.5" bite leaves 0.5" cover (assumption's "≥0.25"" claim is
   conservative-true). Side screws: head at rail inner face x=3.25", tip
   x=4.50", side board 4.00–4.75" ⇒ bite exactly 0.50", cover 0.25"; the 0.62"
   default is unreachable without a longer screw, which the untouched 1.75"
   probe pins as an undeclared-exit FAIL. The declared side minimum equals the
   actual bite (zero margin) but it is a declared minimum judged
   GEOMETRY-PROVEN against real geometry, with the why authored. Both whys ride
   the connections' `assumptions:` into the derivation-log facts AND the doc's
   hardware-presence assumption lines; field-level `[authored_override]` is
   printed per field in the derivation log and the doc's Resolved-contracts
   section (side connections show ONLY embedment authored — the rest
   `connectiontype_default` — exactly guardrail #7).
2. **Checker changes additive — verified.** `_MAPPABLE_ANGLED_FACES` is
   consulted at exactly one site, gated per tool-axis mode: `inner_face` on a
   straight/shank axis still degrades to honest UNKNOWN ("no geometric
   mapping... never guessed", pinned by the mystery_face test). The recess
   wording only APPENDS to `rung_note` for `recessed_in_pocket` /
   `flush_countersunk`; no shipped angled contract declares either (platform
   toe screws are `proud`), and no other spec uses `inner_face` (grepped). The
   sweep-module sibling pins (stool, platform, sit-reach box+frame, rock
   anchor, trebuchet, site-composed) ran green and their expected verdicts are
   untouched by the diff (no sibling-named line in any hunk).
3. **Verdict flips reproduced from scratch.** Fresh compile+validate: 0
   failures, 24 install findings = 12 termination PASS + 12 access blocking
   UNKNOWN, `report.ok` False. Pocket four carry the exact guardrail-#6 recess
   wording and name BOTH foreign blockers (sofa arm + own-side side board);
   side eight name the sofa arm. Corridor geometry hand-checked: inner cheek
   x=3.25" tipping −X at 15° crosses the arm face (x=3.00") at
   t = 0.25/sin 15° ≈ 0.97"; outer cheek x=4.00" sits ON the side board's
   inner face. `render()` refuses with "12 unresolved (UNKNOWN, blocking)" and
   no failure line; `render_documentation` writes the doc with the
   off-the-sofa prose, the install-order bullet, contracts + provenance, and
   all 12 named UNKNOWNs.
4. **Reversion probe — would-have-caught confirmed independently.** I ran the
   strip myself (`re.subn` on the shipped spec text, n=4): the original defect
   returns in full — Counter{termination FAIL: 12, access FAIL: 4 (buried
   head, "mid-plate", "4.00\" inside registration rail", "impossible joint as
   declared"), access UNKNOWN: 8}. The test's assertions are wording-specific
   FAIL pins, so a weakened checker fails it; it discriminates.
5. **Note-filter — dead lie, both directions.** Rendered doc contains zero
   "embedment default" occurrences beside the four authored contracts; the
   pinned contract test covers authored-drops-it AND plain-default-keeps-it.
6. **Round-trip.** `load(dump(doc)) == doc` and re-dump byte-equal, with all 4
   `install:` blocks surviving the dump — verified directly.
7. **Honesty sweep.** The sofa-arm UNKNOWNs stand blocking (no waiver
   mechanism appears anywhere in the diff; the stage exemption is untouched).
   The four inherited nits landed as described: `_fmt` negative-knife-edge
   clamp (display-only), `far_face_station` anti-conservative docstring,
   probe-C blocker dims now matching its comment (x 60–62, never straddling
   the bolt axis; verdict unchanged, test green), HON-F3 "DECLARED order, not
   sequence-proven" pinned verbatim. BOM shadow → F-1.
8. **Ownership/baselines.** Diff touches only the caddy spec, install.py,
   installation.py, and four test files; no sibling spec/test/baseline.
   `regen_baselines.py --check` → "baselines are current."

## Targeted-test numbers measured

- `test_install_axes.py + test_install_sweep.py + test_install_contract.py +
  test_armchair_caddy_e2e.py` → **78 passed** (one run, 306s).
- Independent reversion reproduction: 4 buried-head FAILs + 12 embedment
  FAILs on the stripped shipped spec (fresh compile).
- Full suite not run (controller gates it per review protocol).
