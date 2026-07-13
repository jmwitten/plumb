# Adversarial review — INSTALL / Fastener Installability design

**Target:** `.superpowers/sdd/installability-design.md` (uncommitted, working tree on `master`)
**Reviewer stance:** fresh adversary; every concrete number/mechanism re-checked against source and the compiled model.

## VERDICT: REVISE

The motivating failure is **real and accurately characterized** — I reproduced it on the compiled
model down to the coordinates, and every source-mechanism claim the design leans on (coverage
UNKNOWN rule, `installed_before` edge emission, the pre-D6 cleat-bottom meaning of `z=-1.5`) checks
out. The two-prong root-cause-vs-detection framing and the four-IR fit are sound.

But three of the design's load-bearing artifacts are defective and must be fixed before the owner
reads it: (F-2) F1's mechanism would false-fail the design's OWN prescribed caddy fix, with no
vocabulary to rescue it; (F-3) CAT-2's promised FAIL is undeliverable in Phase 1 and secretly needs
Phase 3; (F-4) CAT-3's example is geometrically invalid — I ran it, and a 2.5in cap screw breaches
nothing, so its "ships silently" claim is true but vacuous. A design whose acceptance tests are 1
sound / 2 broken cannot yet claim "a class of wrongness disappears."

---

## Findings

### F-1 — Premise CONFIRMED (no change; recorded so the owner knows it was checked) — INFO
Compiled `details/armchair_caddy.spec.yaml` and probed the solids (mm→in):
- registration rail +X: solid `z[-5.5, 0.0]`.
- rail-up screw +X 0: shank `z[-1.62, +0.5]` — head plane ≈ `z=-1.5`, **4in above the rail's bottom
  edge, embedded mid-plate**; tip 0.5in into the top board (`z[0, 1.0]`). Solid on BOTH sides of the
  head plane; a driver would have to pass through 4in of solid rail from below.
- Pre-D6 spec (`git show 876af44`): `cleat_bot_z = -cleat_drop = -1.5` was **literally the 1x2
  cleat's bottom face** (`cleat_drop=1.5`), head bearing there, 1.5 through + 0.5 bite. Exactly as the
  design states.
- `d.require_clean()` **PASSES** today: 172 findings, zero non-pass; coverage matrix has 8 families,
  none named installability. The "silent CLEAN / invisible absence" premise is real.

### F-2 — F1 would false-fail the caddy's OWN pocket-screw fix; no vocabulary rescues it — MAJOR
The design proposes F1 ("air-behind / material-ahead at the head plane") **and**, in Phase 0.4, fixes
the caddy with "pocket-angle up screws through the rail's inner face." A pocket screw's head bears at
the bottom of a **bored recess** — the exact case the reviewer flagged. F1's "air-behind" is
satisfied ONLY IF that pocket void is modeled as removed material.

It is not modeled, and cannot be today: `bore` folds to a **full-through-thickness cylinder**
(`process_graph.py:174-182` — "the geometry it folds to is identical to a notch"), and `drill is
deferred` (`loader.py:570`). There is no partial-depth counterbore / pocket that removes material
behind a head to create a bearing shoulder + air. So on the compiled model the fixed caddy's
pocket-screw head would **still sit in solid rail**, and F1 as literally specified would FAIL the very
fix the design prescribes — or F1 must be lenient enough that it also misses the original embedding.

This is the design's biggest self-consistency hole and it is entirely unaddressed. **Required:** state
how a declared pocket/counterbore satisfies F1, and name the vocabulary that models the air behind the
head. If that vocabulary is Phase 2 work, then F1 (Phase 1) cannot ship a truthful verdict on any
pocket-screwed detail — including the caddy fix — until then, and the phasing must say so.

### F-3 — CAT-2's FAIL branch is undeliverable in Phase 1; it secretly needs Phase 3 — MAJOR
F2's F4 policy FAILs only when the obstructor is "a party to the same connection **or**
`installed_before` the fastener." I read every shipped `edges()`: `CleatScrewed`, `ToeScrewed`,
`RailCapScrewed`, `FaceMountHanger`, etc. emit only `member/cleat installed_before its-OWN-screw`
(e.g. `connection.py:1215-1216`). There is **no cross-connection order** — deliberately (CleatScrewed
docstring: "Deliberately NO cleat↔member order edge").

CAT-2 pairs "a platform deck screw" with "a joist hanger flange" — **different connections**, no
`installed_before` edge between them. So the policy returns `UNKNOWN — install-order dependent` for
**both** the earlier- and later-install cases; CAT-2 cannot produce the FAIL it advertises until
Phase 3 supplies a global sequence. As written, Phase 1 depends on Phase 3. **Required:** either
author CAT-2 so the obstructor is a party to the fastener's own connection (then it's a genuine
Phase-1 FAIL, though closer to F1 restated), or relocate CAT-2's FAIL claim to Phase 3 and keep only
the UNKNOWN half in Phase 1.

### F-4 — CAT-3's example is geometrically invalid; "ships silently" is true but vacuous — MAJOR
I ran the reviewer's exact test: copied `details/sit_reach_box.spec.yaml`, set `screw_len: 2.5`,
`validate()` → **258 findings, zero non-pass** (ships silently). But the compiled geometry shows why
that is the *wrong* kind of silence: the top cap screw drives straight DOWN into an **11.25in-tall
wall**, tip landing at `z=9.50in` — 1.75in into an 11.25in wall, drive axis **parallel to the inner
face**. A 2.5in vertical cap screw **breaches nothing**: no exit through the inner face, no
blow-through. The design's CAT-3 ("exiting the wall's inner face into the box cavity") describes a
breach that does not physically occur. It ships silently because **there is no defect**, not because
F3 is blind.

CAT-3 is therefore not a valid F3 acceptance test. **Required:** replace it with a screw that actually
blows through — e.g. a cap screw longer than the full 12in wall+top stack (exits the wall bottom), or
a horizontal butt screw longer than the panel depth it enters (exits a show face). (Note: at 2.5in the
butt screws don't breach either — 1.75in into a 10.5in panel edge — so the whole `screw_len 2.5`
sweep is defect-free; the CAT needs a purpose-built overlong screw on a specific joint.)

### F-5 — Source-mechanism claims CONFIRMED accurate — INFO
- **Coverage UNKNOWN rule** (`coverage.py:278-279`): a family in `INVARIANT_FAMILIES` with no check
  ran renders `UNKNOWN — NOT ANALYZED`; adding `Fastener installability` to that tuple auto-appears in
  every doc's matrix with UNKNOWN. Claim accurate. (Note it's an EDIT to the tuple, which the design
  does acknowledge — "new coverage family in validation/coverage.py.")
- **`installed_before` edges** (`connection.py`): concrete types genuinely emit them. Claim accurate —
  with the sparseness caveat that is the crux of F-3.
- **Caddy uses a real `cleat_screwed` Connection** declaring the up screws as `hardware`
  (`armchair_caddy.spec.yaml:249-284`), so F1/F2/F3 iterating "every fastener the connections declare"
  would in fact see the offending screw. Architecturally the check has a handle on its target.

### F-6 — F2's 6×1 default sends the flagship zipline toe screw to UNKNOWN; the override can't be a footnote — MODERATE
Checked the default against the three named real joints:
- **Stool cleat screws**: driven across a 9in clear inner span (`step_stool.spec.yaml:64`) → 9 > 6, a
  6in corridor fits → PASS. Fine.
- **Sit-reach butt screws**: heads on the open outside face → PASS. Fine.
- **Zipline toe screws**: `ToeScrewed` docstring says the joist is "wedged in a ~3.5" clear gap
  between a leg's own two thru-bolts... NOT [wide enough] for a hanger's flanges." A 6in straight
  corridor cannot clear a 3.5in gap flanked by bolts, and the obstructing leg/bolts are **not** in the
  `toe_screwed` connection → F4 policy returns UNKNOWN, not PASS. A deliberately-shipped "tight
  retrofit" joint the codebase is proud of immediately reads UNKNOWN on the new family.

No false-FAIL, but a real good joint drops to UNKNOWN and needs a per-detail driver override to read
clean. The design mentions the override only parenthetically ("overridable per detail"). **Required:**
make the override a first-class, worked part of the design, with the toe-screw joint as its motivating
example.

### F-7 — Phase 2 REPLAY is under-specified vs the ACTUAL D6 fix — MODERATE
REPLAY says re-running D6 with derived stations makes "the up screws either move to the rail's real
free face... or raise a teaching error." But the honest D6 remedy is a **pocket/angled joint through
the rail's inner face** — a different connection type — not a relocated straight screw. A naive
`cleat_screwed` derivation ("head on the cleat's free face") applied to the 5.5in rail would put the
head at the rail bottom (`z=-5.5`), from which a 2in screw cannot reach the top at `z=0`. The correct
outcome is a **teaching error**, which the design does allow — but it should say plainly that the
derivation reproduces the fix by ERRORING (forcing a real pocket joint), **not** by relocating a
straight screw to a valid station. As written, REPLAY can be misread as "straight-screw derivation
would have prevented D6," which it would not. This also ties back to F-2: the real fix needs pocket
vocabulary that does not yet exist.

### F-8 — F1/F2/F3 assume the drive axis / head plane is recoverable; unstated — MINOR
The checks need to know which end of the placed fastener is the head and which way is "behind." The
design asserts "pure geometry, no new authoring surface" without saying how head-vs-tip is identified
from a `structural_screw` Placed. Plausible (the component has a head end + a rotation), but a symmetric
shank could be ambiguous. State the mechanism (head datum/axis on the screw component).

### F-9 — Scope-honesty is mostly good; one phrase overclaims — MINOR
The detectable (Phase 1) vs impossible-to-author-silently (Phase 2) distinction is drawn crisply, and
the "does NOT do" section is honest about tools/torque/swing. But the CAT preamble's "a class of
wrongness disappears" overclaims for Phase 1 — Phase 1 makes the caddy class **detectable**, not
impossible; only Phase 2 makes it impossible-to-author-silently. With CAT-1 the only sound CAT of the
three (F-3, F-4), the "disappears" framing currently rests on a shaky base. Tighten the wording and
land two real CATs first.

---

## What would move this to ACCEPT
1. F-2: resolve the F1-vs-pocket-screw contradiction — either declare the pocket vocabulary that
   models air behind the head (and sequence F1 after it), or scope F1 to explicitly exclude
   pocket/counterbore heads with an honest UNKNOWN and say so.
2. F-3: re-author CAT-2 as a same-connection obstruction (Phase-1 FAIL) or move its FAIL to Phase 3.
3. F-4: replace CAT-3 with a screw that actually blows through a face.
4. F-6: promote the F2 driver override to a first-class mechanism, toe-screw as the exemplar.
5. F-7 / F-9: tighten REPLAY and the "disappears" wording to match what each phase actually delivers.

CATs after fixes: CAT-1 (caddy up screw) is a genuine would-have-caught and stands. It is currently
the design's only sound acceptance test — the discipline needs the other two rebuilt, not patched.
