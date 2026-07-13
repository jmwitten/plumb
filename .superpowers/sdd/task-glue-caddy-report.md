# Task GLUE-CADDY report — the `glued` ConnectionType + the caddy rail->top re-spec

Branch `sdd/glue-caddy` off master ab11af4. OWNER DIRECTIVE (2026-07-11): Joel
has no pocket jig — the armchair caddy's two rail->top joints are built by
glue-and-clamp, not pocket screws. This retires the R-GLUE work order (the
adhesive ConnectionType, "#22's adhesive ConnectionType, second consumer" —
progress.md SITREACH block; #22's glued-miter remains the waterfall sibling)
and replaces the pocket declaration task-fix-caddy-report.md shipped.

## Import-path verification (environment)

    cd <worktree> && mkdir -p .shim && ln -sfn "$PWD/src" .shim/detailgen
    export PYTHONPATH="$PWD/.shim"
    python -c "import detailgen; print(detailgen.__file__)"
    # -> <worktree>/.shim/detailgen/__init__.py — verified before every
    #    pytest/baseline gate (the venv's editable finder maps detailgen to
    #    the MAIN checkout; the shim beats it).

## The `glued` ConnectionType (src/assemblies/connection.py)

Registered `glued` (class `Glued`), the R-GLUE plain face-to-face adhesive
bond. Semantics, each deliberate:

- **Parts** `[member_a, member_b]`, EXACTLY two — a bond plane is pairwise;
  a multi-member glue-up is several declared joints. Wrong count raises a
  teaching error.
- **NO hardware.** Declaring any raises via `_require_hardware_roles(conn,
  [])` — the adhesive IS the joint; a "glued joint with a screw" is a
  different (future) word, never absorbed here.
- **`bonded_pairs` = [(a, b)]** — connectivity only (feeds
  `check_no_floaters`), never a required-contact proof.
- **NO `bears_on` / NO `bearing_pairs`** — the CleatScrewed lesson: a glue
  joint holds parts together; any real gravity seat is a SEPARATE declared
  bearing (the caddy's top-on-side-end-grain bearings are untouched).
- **Edge: ONE `bonded_to`** — a NEW Construction-Graph edge kind, the
  adhesive analog of `fastened_by` (calling a glue bond "fastened" would
  misname the mechanism; edge kinds are an open string by design). Wired
  into the consumers that filter by kind:
  - `loadpath.LOAD_BEARING_EDGE_KINDS` (documented "open by intent") — the
    bond is load-path-eligible, gated per load class by the type's transfer
    claims exactly like `fastened_by`;
  - `evidence.EDGE_KINDS` + `evidence._CONSTRUCTION_EDGE_KINDS` — without
    this the edge would be silently invisible to `what_depends_on` and the
    INCR affected-region seam (`incremental/affected_region.py` imports the
    same frozenset, so change-impact gets it transitively).
- **NO `installed_before`** — clamp-and-cure is a PROCESS fact: the
  connection's `assumptions` carry the technique (glue both faces, clamp,
  cure per the adhesive label) and flow into the derivation log + doc
  disclosures; there is no hardware whose order the joint owns.
- **`transfer_claims`: pull_out + shear**, `placeholder` confidence,
  `verified_heuristic`, capacity NOT analyzed — and the type text names the
  MECHANISM only (adhesive bond across the mating plane). Substrate is
  deliberately NOT in the type (the R-SUBSTRATE lesson: generic type text
  true for one consumer is false for the next); each connection's
  assumptions must name what its two mated faces actually are. Unit-pinned:
  no "grain"/"face-to-face" wording in the claims.
- **`install_contract` returns `()`** — the honest "nothing to contract"
  state (the standoff_post_base distinction: `()` ≠ `None` "cannot
  represent"). The Fastener-installability family therefore has NOTHING to
  judge on a glued joint: no contract, no NO-METHOD UNKNOWN, no axis
  verdicts — correct, because there is no fastener to install.

## Caddy re-spec (details/armchair_caddy.spec.yaml)

- The two rail->top connections are now `glued` (no params, no hardware, no
  `install:` block). Assumptions carry (1) the substrate — the rail's
  0.75in x 5.5in long-grain top edge mates FLUSH to the top board's
  underside FACE grain, long grain both sides, the strong glue case; bond
  capacity NOT analyzed — and (2) the process fact — glue BOTH faces,
  clamp, cure per label BEFORE the side screws, assembled OFF the sofa.
- DELETED: the four up-screw components (`vscrew_*`), params `screw_len_v` /
  `screw_dy_v`, derived `rail_mid_x` / `upscrew_z` (nothing else read
  them), the pocket `install:` contracts, and the pocket-era
  display-idealization + BOM-shadow disclosures (they described the drawn
  up screws, which no longer exist). Geometry CHANGES: 4 screw solids gone
  — intended; the caddy is in NO shared baseline (verified below).
- UNTOUCHED: the 8 side screws, their two `cleat_screwed` connections and
  authored 0.5in embedments + assumptions; all board geometry; the three
  declared bearings (the rail top edge already sat flush at Z=0 under the
  top — the bond plane is the same contact the spec always drew, and no
  contact/bearing fact about it was ever declared or removed).
- Contact honesty note: the bond-plane CONTACT itself is not proven by any
  check (glued asserts no bearing; same epistemic state as the cleat's
  flush face before it) — connectivity is the bond, contact is the drawn
  geometry. Residual below.
- BOM/billing: the four 2in screws leave the buy list (their components are
  gone); wood glue + clamps are shop consumables/tools, NOT billed rows —
  the established convention (sit-reach box/frame bill glue as prose/
  assumption notes; Epoxy is a component only where it is a real modeled
  solid, as in the rock anchor). Disclosed in the spec assumptions, the doc
  prose, and the build document's buy lede/stock line.
- Doc prose rewritten STANDALONE (first-time reader, no pocket-era
  reference): spec `doc:` sections (intro, derivation-log preamble — now
  "a `glued` bond at each rail->top corner, a `cleat_screwed` joint at each
  rail->side face" — the rails bullet, the installability bullet now
  naming 8 corridors) and `scripts/single_detail_report.py`'s caddy panel
  (buy lede, stock line "8 screws + wood glue", joint caption, narrative
  "8 interior screws", fieldnote "Hidden rail joints — glue, then screws,
  all off the sofa").
- Spec round-trips byte-stable through `dump_yaml` (`load(dump(doc)) ==
  doc` and re-dump byte-equal, verified directly).

## Verdict flips (before ab11af4 -> after, hand-probed live)

| Subject | before (pinned) | after (pinned) | probe evidence |
|---|---|---|---|
| 4 rail-up screws, axis 1 | non-blocking REPRESENTED ("angled shank path not analyzed", 15° pocket) | GONE — no screws, no contract, no finding | live validate: install findings = 16, all naming "rail-side screw" |
| 4 rail-up screws, axis 2 | blocking UNKNOWN — pocket corridors (sofa arm / side board) | GONE | same |
| 8 rail-side screws, axes 1+2 | 8x PASS at authored 0.5in minimum + 8x blocking UNKNOWN (sofa arm) | UNCHANGED, wording identical | live validate: Counter{(termination, PASS): 8, (access, UNKNOWN): 8} |
| rail->top connectivity | bonds via 4 screws + fastened_by edges | bonds via 2 glued bonded_pairs + 2 `bonded_to` edges | edge Counter: installed_before 16, bonded_to 2, fastened_by 2 |
| whole detail | failures 0 / blocking 12 / not ok | failures 0 / **blocking 8** / still NOT ok | render() refuses with "8 unresolved (UNKNOWN, blocking)"; render_documentation still writes |

CLEAN was not chased: the 8 side-screw sofa-arm corridor UNKNOWNs are
axis-3 sequence knowledge v1 does not have (assembled off the sofa),
disclosed in prose, standing as blockers.

## Re-pin inventory (all to verified new truth; nothing weakened or silently dropped)

- tests/test_install_sweep.py — caddy flavor section rewritten: NEW
  `test_caddy_glued_top_joints_carry_no_install_verdicts` (zero up-screw /
  glued-joint / install_method findings; install total = exactly 8 screws x
  2 axes; 2 bonded_to edges); blocking-set pin 12 -> 8; side-screw pins
  untouched; the 1.75in overlong-side-screw undeclared-exit probe untouched
  and green.
- **Reversion probe reworked, not dropped**
  (`test_caddy_driven_straight_reversion_is_still_caught`): the old probe
  stripped the four pocket `install:` blocks — they no longer exist. Per
  the never-silently-drop rule it now RE-ADDS the D6 defect to the SHIPPED
  spec text (one straight 2in up screw at the retired -1.5in station, on a
  `cleat_screwed` rail->top connection with NO install block -> type
  default driven_straight + half-length minimum) and requires the original
  verdicts verbatim: buried-head access FAIL ("entry face buried",
  "mid-plate", "4.00\" inside registration rail", "impossible joint as
  declared") + embedment FAIL ("below the declared minimum",
  "[assumption]"), with the 8 shipped side screws keeping their authored
  PASS. The synthetic CAT-1 coverage in test_install_axes.py is unchanged.
- tests/test_armchair_caddy_e2e.py — honest-blocked pin re-pinned to 8
  UNKNOWNs (all side screws) / 8 authored-minimum termination PASSes + 2
  bonded_to edges; BOM pin 12 screws in two rows -> 8 in ONE row; harness
  pin "blocking: 8"; render-refusal "8 unresolved"; fabrication-record
  purchased-part probe re-named to a side screw; show-face sweep 12 -> 8
  screws; module/test docstrings describe the glued joint (first-time
  reader).
- tests/test_glued_connection.py — NEW: registry, derived closure (bond +
  bonded_to only), mechanism-only claims (no substrate words), load-path
  eligibility, `()` vs None, no-hardware and exactly-two guards, and the
  synthetic two-board glued spec through the real spec path (zero
  install findings, family honestly `UNKNOWN — NOT ANALYZED`, report.ok,
  separately-declared bearing passes).

## Shared-baseline impact

**NONE.** `python scripts/regen_baselines.py --check` -> "baselines are
current" (shim-verified import path). The caddy is absent from
tests/baselines/detail_counts.json, the consolidated-doc textlayer golden
(site-composed details only), and has no frozen-truth store. No sibling
detail declares a glued connection, so no other derivation log moves.

## Residuals / honest gaps

- **Adhesive capacity is UNANALYZED** — the claims are placeholder-grade
  mechanism statements; no bond-strength number exists anywhere (ANALYSIS
  v1 material, alongside the existing withdrawal/racking gaps).
- **Bond-plane contact is not PROVEN** — glued emits no bearing (by
  design); the mating faces touch in the drawn geometry and connectivity is
  the declared bond, but no check asserts the flush contact a real glue
  joint needs. A future "bond plane requires contact + min area" derivation
  (a check_bearing-class proof WITHOUT a gravity-seat claim) is the honest
  upgrade path — needs its own wording so contact-proof ≠ bears_on.
- **Clamp/cure is prose, not process** — the cure-before-screws sequencing
  lives in assumptions/doc, not in the Construction Process Graph; when
  axis 3 lands, "glue cures before side screws are driven" becomes a real
  sequence fact.
- **A bare `install:` override on a `()`-contract type is silently
  ignored** — pre-existing (`standoff_post_base` has the same hole, the
  `groups is None` branch raises but the `()` branch consumes no ""-key
  override); out of scope here, filed as a shared-resolution nit.
- The Fastener-installability family row on the SYNTHETIC glued-only spec
  reads `UNKNOWN — NOT ANALYZED` — correct and pinned ("no fastener to
  install" is not "installable"); the shipped caddy's row still gets its
  content from the 8 side screws.

## Gates

- Import path verified (above) before every run.
- Targeted greens along the way: test_glued_connection (8) ·
  test_connection + test_loadpath + test_evidence_graph (37) ·
  test_install_sweep caddy section (5) · test_armchair_caddy_e2e (17).
- `regen_baselines.py --check` -> baselines are current.
- Full suite from the worktree (`pytest -n auto -q`, venv python, shimmed
  PYTHONPATH, import path printed at the head of the log): **1116 passed /
  3 skipped / 1 xfailed** in 14:23 — master baseline 1108/3/1 + 8 net new
  items, accounted exactly: +8 test_glued_connection tests, +1
  test_scripts_spec_rewire per-test-file guard case (its glob picks up the
  new module), −2 retired pocket sweep tests, +1 new glued sweep pin
  (test_armchair_caddy_e2e's count is unchanged at 17).
