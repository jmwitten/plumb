# Task FIX-CADDY report — the pocket joint, contract-first (Phase-0 fix arc, CAT-A live)

Branch `sdd/fix-caddy-pocket` off master 8d1f1df. The D6 defect
(installability-design.md §Motivating failure): the caddy's 4 rail-up
screws keep the 1x2-cleat-era authored station `upscrew_z = -1.5`, leaving
their heads 4.00 in inside the solid 5.5 in 1x6 rail — no straight-driven
technique installs the joint as drawn. The owner-approved fix is the
CONTRACT, not a station move (review F-7's trap: a 2 in screw cannot span
the 5.5 in rail): the honest joint is a POCKET SCREW through the rail's
inner face, declared on the connection, judged by the same general checks.

## Import-path verification (environment)

    cd <worktree> && mkdir -p .shim && ln -sfn "$PWD/src" .shim/detailgen
    export PYTHONPATH="$PWD/.shim"
    python -c "import detailgen; print(detailgen.__file__)"
    # -> <worktree>/.shim/detailgen/__init__.py — verified before every
    #    pytest gate and printed at the head of the full-suite log.

## What changed

**details/armchair_caddy.spec.yaml** — the fix itself. The two rail→top
`cleat_screwed` connections author the CAT-A contract:

    install:
      method: pocket_screw
      entry: {part: cleat_pos|cleat_neg, face: inner_face}
      angle: 15            # typical pocket-jig technique value, declared as such
      exit: none
      head: recessed_in_pocket
      embedment: "0.5 in"  # authored joint-geometry minimum (why below)

NO geometry moved (the diff touches no `at:`/`rotate:`/param values; the
four side-screw connections keep their plain `driven_straight` defaults).
The drawn straight screws stay as the contract-referencing display
idealization (amendment #3), never a waiver. The two rail→side connections
author `install: {embedment: "0.5 in"}` only. Spec comments + reader-facing
doc prose now describe the pocket joint and disclose the honest
install-order state (below).

**Authored embedment decisions (the arc's "new verified truths" scope)** —
never overridden just to go green; each why is authored into the
connection's `assumptions:` (which flow into the derivation-log fact and
doc disclosures), provenance `authored_override` on the field:

- **Up screws, 0.5 in into the 1.0 in top board.** The half-length default
  (1.00 in for the 2 in screw) EQUALS the top's full thickness — declaring
  it would declare a show-face breach, contradicting `exit: none` and the
  design's no-show-face rule. 0.5 in is a real pocket-screw purchase that
  keeps ≥ 0.25 in of show-face cover. Withdrawal demand is the caddy's
  few-pound service load — engineering judgment, stated as such, not
  analyzed to a number.
- **Side screws, 0.5 in into the 0.75 in side board.** The half-length
  default (0.62 in for the 1.25 in screw) is GEOMETRICALLY UNREACHABLE in
  this joint without breaching the outer show face (0.75 in board − 0.25 in
  cover caps the honest bite at 0.5 in); longer screws are the F-7-adjacent
  trap the synthetic 1.75 in probe already pins as an undeclared-exit FAIL.
  Four screws per joint; few-pound demand; engineering judgment, disclosed.

**Sofa-arm corridor decision (axis-2 UNKNOWN ×8, side screws).** Left
STANDING — it is true. The real technique assembles the caddy OFF the sofa
(rails to the top first, then the sides), which is axis-3 sequence
knowledge v1 cannot prove, and no design-sanctioned mechanism exists to
discharge a FOREIGN-body corridor block (the `installed_before` stage
exemption is per-connection-own-edges only, and the design forbids adding
edges to silence axis-2). The assembly-order reality is disclosed in the
doc prose ("Installability is honestly install-order UNKNOWN" bullet) and
the verdicts stay blocking UNKNOWNs, named after their blockers.

**src/validation/install.py** (checker, additive only — no check weakened):

- `inner_face` joins `_MAPPABLE_ANGLED_FACES`: the concealed interior face
  an authored pocket contract enters. For an angled axis the descriptor
  names the technique's face; the sweep geometry is unchanged (it already
  tries BOTH cheek candidates, one of which IS the inner face). Chosen over
  reusing `free_face`, whose documented meaning ("the face OPPOSITE the
  joint interface" — the rail's bottom end) would have been an actively
  wrong declaration for a pocket entry.
- `_access_angled` now appends guardrail #6's CAT-A acceptance wording when
  the contract declares `recessed_in_pocket`/`flush_countersunk`:
  "Installation method represented; recess geometry not analyzed — head
  condition ... judged as declared, not geometry-proven" — the same
  disclosure the shank path already made for declared heads. Before this,
  the angled path never spoke the declared-void rung at all. No shipped
  angled contract declares a recessed head (platform toe screws are
  `proud`), so no sibling baseline moves.
- Inherited nits: `_fmt` clamps the negative side of a knife-edge zero
  ('-0.00"' can no longer print); `far_face_station`'s docstring now states
  the rotated-member AABB projection is ANTI-conservative for the
  reader-facing "N short of its far face" note (it overstates margin),
  matching the cheek-plane residual's wording.

**src/assemblies/installation.py**: `resolve_role_group` drops a note that
explains an OVERRIDDEN field's default (`_DEFAULT_NOTE_FIELDS`). Surfaced
live by this arc: the resolved caddy contracts printed "embedment default =
half the under-head length ..." beside `embedment=0.50" min bite
[authored_override]` — an honest-looking lie on the doc surface. Pinned
both directions in test_install_contract.py (authored drops it, plain
default keeps it). `EntryFace` docstring gains the `inner_face` descriptor.

**tests/test_install_axes.py**: CAT-A's full-contract test now authors
`entry inner_face` and asserts the recess acceptance wording; nit 1 (the
probe-C blocker dims corrected to the comment's intended off-axis position,
`Boulder(22.4, 2.0, 20)` → x 60–62 mm, never straddling the bolt axis —
verdict unchanged, the probe is now the sharper radial-hugger it claimed to
be); nit 4 (HON-F3's "DECLARED order, not sequence-proven" pinned verbatim
in the ordered-after CAT-E test).

## Verdict flips (before → after, each hand-probed)

| Fasteners | Axis | master 8d1f1df (pinned) | this branch (pinned) | probe evidence |
|---|---|---|---|---|
| 4 rail-up screws | 1 termination | FAIL — 0.50" bite into top < 1.00" [assumption] | non-blocking REPRESENTED pass — "angled shank path not analyzed", 15° pocket_screw, authored 0.50" minimum printed | angled+idealized contract ⇒ the drawn solid is not the technique's path; not measured, worded per guardrail #6 |
| 4 rail-up screws | 2 access | FAIL — head 4.00" inside the rail, mid-plate, impossible joint | blocking UNKNOWN — install-order dependent; "every declared 15° corridor candidate ... obstructed"; recess wording present | inner cheek (x=3.25): corridor tips −X/−Z across the 0.25" reveal into the sofa arm (arm face x=3.0, centerline crosses at t≈0.97"); outer cheek (x=4.0): base sits ON the side board's face, tips into it — both foreign |
| 8 rail-side screws | 1 termination | FAIL — 0.50" bite < 0.62" [assumption] | PASS — '0.50" bite into side board ≥ 0.50" declared minimum [authored_override]' | head at rail inner face x=3.25, tip x=4.5, side board 4.0–4.75 ⇒ bite exactly 0.5"; authored minimum = the joint's geometric max honest bite |
| 8 rail-side screws | 2 access | blocking UNKNOWN — sofa arm | UNCHANGED (deliberately) | corridor backs across the 0.25" reveal into the arm; assembly-off-the-sofa is axis-3 knowledge — disclosed in prose, not waived |

Whole-detail: failures 16 → **0**; blocking 24 → **12** (all UNKNOWN);
`report.ok` stays False — the truthful state is BLOCKED-on-UNKNOWN, and
`render()` still refuses ("12 unresolved (UNKNOWN, blocking)", no failure
line, no install_termination) while `render_documentation` writes the doc
about it. CLEAN was not chased; the doc now tells the reader exactly why.

## Re-pin inventory (all to the verified new truth; nothing weakened/deleted)

- tests/test_install_sweep.py — the caddy flavor section rewritten:
  termination-represented pin, pocket-corridor UNKNOWN pin (recess wording
  asserted), side-screw authored-minimum PASS pin (UNKNOWNs unchanged),
  blocking-set pin (0 failures / 12 blocking), and the NEW
  `test_caddy_driven_straight_reversion_is_still_caught` — strips the four
  authored `install:` blocks from the SHIPPED spec text (`re.subn` count
  asserted = 4) and requires the original defect verdicts to return in
  full: 4 buried-head access FAILs + 12 embedment FAILs. CAT-A's
  would-have-caught property, preserved on the real spec, not just the
  synthetic CAT joint. The 1.75 in overlong-side-screw regression probe is
  untouched and green (its undeclared-exit FAIL is independent of the
  authored embedment).
- tests/test_armchair_caddy_e2e.py — honest-red pin → honest-blocked pin
  (`test_compiles_and_validates_with_honest_install_unknowns`: failures
  == [], per-kind Counter of the 12 UNKNOWNs, REPRESENTED disclosures on
  the pocket four, 4 represented + 8 authored-minimum termination split);
  harness pin "failures: 0"/"blocking: 12"; render-refusal message re-pinned
  (UNKNOWN-only, never conflated); module docstring's joint description
  corrected (it still described the pre-D1 screwed-down-through joint).
- tests/test_install_contract.py — new note-filter pin (both directions).
- tests/test_install_axes.py — CAT-A full-contract extension + nits 1/4.

## Shared-baseline impact (controller sequencing)

**NONE regenerated.** The caddy is absent from `tests/baselines/
detail_counts.json`, absent from the consolidated-doc textlayer golden
(site-composed details only), and has no frozen-truth store.
`regen_baselines.py --check` → "baselines are current" on this branch. The
1e-6 transform pins did not move (no geometry changed — `git diff` on the
spec touches only comments, connection blocks, and prose). The checker
wording additions fire only on angled+recessed-head contracts, which no
sibling detail declares. Merge order vs the stool/platform arcs should not
matter, EXCEPT: all three arcs were offered the same four "inherited
cosmetic nits" — THIS branch fixed all four (install.py `_fmt` +
`far_face_station` docstring; test_install_axes.py probe-C dims + HON-F3
assertion). If a sibling also fixed them, take either side (this branch's
probe-C fix changes the fixture dims per the nit's first option; a sibling
that only fixed the comment will conflict textually, not semantically).

## Residuals / honest gaps

- The pocket void is DECLARED, not modeled (vocabulary work order #1 — not
  this arc): every pocket verdict is REPRESENTED-rung by mechanism
  (`axis_idealized`) and says so; the joint climbs to GEOMETRY-PROVEN only
  when the counterbore/pocket vocabulary lands.
- The caddy's truthful whole-detail state is BLOCKED on 12 install-order
  UNKNOWNs until axis 3 (Construction Process Graph) can prove the
  off-the-sofa assembly sequence — the same class as the sit-reach frame's
  standing UNKNOWNs. The doc prose carries the builder-facing reality.
- The BOM still bills the drawn 2 in/1.25 in structural screws; a real
  pocket jig uses purpose-made pocket screws. This is the display
  idealization's BOM shadow — honest to flag here, out of scope to fix
  without the pocket vocabulary (the fabrication records would also need a
  pocket-boring step, which `bore` (full-through only) cannot express).
- The 15° angle and the 0.5 in minimums are authored technique/judgment
  values, visible as `authored_override` with their whys in the connection
  assumptions — not manufacturer data, and they never claim to be.

## Gates

- Import path verified (above) at every run.
- Targeted modules green along the way: install axes/contract/spec-surface
  (59), sweep + coverage + viewer + scripts-rewire (152), caddy e2e (17).
- Caddy spec round-trips byte-stable through `dump_yaml` (the first
  SHIPPED spec with an authored `install:` block exercises
  `_install_to_dict` on real content): `load(dump(doc)) == doc` and
  re-dump byte-equal, verified directly.
- `scripts/regen_baselines.py --check` → baselines are current.
- Full suite from the worktree (`pytest -n auto -q`, venv python, shimmed
  PYTHONPATH): **1112 passed / 3 skipped / 1 xfailed** — master baseline
  1105/3/1 + 7 new tests (sweep reversion probe +1, e2e unchanged count,
  contract note-filter +1; remainder are the parametrized per-test-file
  guards and split pins added in the sweep/e2e rewrites; exact accounting
  in the suite log).
