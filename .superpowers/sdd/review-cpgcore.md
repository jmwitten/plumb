# Adversarial review — CPGCORE (STEPDOC/CPG v1-core), branch `sdd/stepdoc-core`

**Reviewer:** fresh adversary (no stake in this branch). **Date:** 2026-07-13.
**Target:** master @c4692f5 → branch tip @b9c3029 (09a116f seqschema + 00f9022..b9c3029 cpgcore).
**Method:** every checkable claim run from the shimmed worktree
(`.shim/detailgen` verified to resolve to THIS worktree before every gate;
python = `~/Code/construction-detail-generator/.venv/bin/python`). Scoped
suites re-run live: test_cpg_core (14 PASS), test_sequence_schema (29 PASS),
test_install_axes (21 PASS), test_install_sweep (23 PASS, 73s — includes
CAT-I both halves, the Q9 reversion probe, the corpus rung guard, and the
composed-site replay), plus the re-pinned batch (coverage_matrix, platform
spec/detail, foundation, doc_build_blocked, site_model ×2, caddy/frame/
trebuchet e2e — see §Gates). Synthetic adversarial probes written and run
against the third lift rule and the §4.1 semantics (constructions below).
Full suite deliberately NOT run (controller owns the merge gate).

## VERDICT: **FIX-FIRST** — one blocking finding (F-1, with a live
end-to-end FAIL→PASS construction), three nits. Everything else probed —
the two pinned lift rules, the interleave drop itself, §4.1 reachability
semantics, the corpus rows, CAT-I/Q9, rung/marker discipline, suite
arithmetic, and the re-pin inventory — held under attack.

---

## F-1 — BLOCKING: an authored `sequence:` stage can silence structural
necessity — the exact waiver channel the design promises is impossible

**Design promise (binding).** §3.1 family 2: the structural-necessity
default yields ONLY "where a technique edge orders the opposite way (the
hanger …)". §6 honesty rule 1, verbatim: "a declared order contradicting a
technique edge **or structural necessity** is a load-time cycle error
naming both claims." §10(b): what becomes impossible is "a declared order
silencing a check rather than being tested by it."

**Shipped behavior.** `src/assemblies/event_graph.py:467-470`: the
`declared_out` map that the necessity exception (`_declared_reaches`,
:472-497) walks is built from `graph_edges` — which at that point already
contains the **FAMILY_AUTHORED** stage edges (family 3 is appended at
:443-465, BEFORE family 2 at :467). So an authored stage that orders a
member's `place` event AFTER its own connection's drive event is itself the
"declared path" that suppresses the `place(member) → drive` necessity edge.
No cycle. No teaching error. The member reads **provably later**.

**Live construction 1 (minimal, end-to-end verdict flip).** The exact CAT-E
member-FAIL fixture from test_install_axes (`_blocked_corridor`,
`blocker_in_connection=True` — the hovering-slab member blocking its own
screw's corridor), plus two stages: stage 1 `connections: [the joint]`,
stage 2 `parts: [the slab]`. Run:

- baseline: `FAIL — tool corridor blocked by hovering slab — provably
  present when this fastener is driven (order facts: [structural_necessity]
  …)` ✓ (the F-7 re-pin's truth)
- with the stages: **loads cycle-free, no error; the finding is `PASS —
  clear tool corridor … occupants … provably arrive later: hovering slab …
  deciding order facts: [authored_sequence] …(geometry proven at the
  DECLARED build order …)`**

A derived member-presence FAIL — the one occupant class §4.1/F-7 says
"keeps its FAIL via structural necessity … as a derived FACT now" — flips
to a declared-order clear with no resistance. UNKNOWN→FAIL is falsifiable
(CAT-I, verified live); FAIL→PASS is wide open for members. The channel is
reachable from the spec surface: a `sequence:` stage's `parts:` may list
any member (SEQSCHEMA validates existence, nothing else), and
`resolved_sequence` maps it straight onto the graph.

**Live construction 2 (interleave interaction).** The third lift rule's own
promise — "structural necessity supplies the surviving conservative
direction (the member is PRESENT at the drive event — an occupant is never
quietly ordered 'later' by a fact this coarse)" — is defeated by the same
channel. On a synthetic connection with the shipped rock anchor's chain
shape (`f1 → member → f2`, one role group): both technique directions drop
(correct), then the same two stages flip the member to provably-later.
Here it is strictly worse than construction 1: the type's own part-level
chain says the member arrives before `f2` (it IS present mid-drive), and
that technique knowledge was discarded by the drop — so the authored claim
contradicts the ConnectionType's shipped edges and STILL doesn't cycle.
The part-level `_check_install_order` cannot catch it (it never sees stage
edges); the event-level check cannot catch it (the technique edges are
gone). The contradiction is caught nowhere.

**Why the shipped tests don't see it.** CAT-I's load half
(`test_cat_i_load_half_stage_contradicting_technique_is_a_cycle_error`)
pins authored-vs-**technique** cycles — those are declared-vs-declared,
both edge sets present in the graph, so Kahn catches them. The hole is
specifically authored-vs-**necessity** (declared-vs-derived), where the
implementation suppresses the derived edge instead of letting it cycle.
The F-7/CAT-E pins run with no stages authored. No shipped spec's stages
list a member part (platform's two stages list connections only), so the
corpus is currently unaffected — this is a mechanism hole, not a shipped
wrong verdict.

**Suggested fix (one scoped change).** Build `declared_out` from
`FAMILY_TECHNIQUE` edges only (that is the design's own wording for the
exception). Then: the hanger suppression still works (technique);
authored-vs-necessity contradictions produce the merged cycle error, which
already names both edges AND both provenance families — the teaching
message needs no change. Both probe constructions then fail loudly. Corpus
impact: none that I can find — the platform/site stages order drive events
only, so no authored path reaches any member's place event; the frozen
truth, sweep pins, and CAT-I should all hold. A regression pin for this
exact construction (member staged after its own drive ⇒ cycle error naming
authored_sequence + structural_necessity) should ship with the fix.

## F-2 — NIT: the amendment-3 `declared` count is wording-coupled

`FamilyCoverage` counts declared-order clears by substring — coverage.py
:334: `"at the DECLARED build order" in f.detail`. A future re-word of
`_DECLARED_ORDER_RUNG` / the angled order-note would silently zero the
count and strip the declared-trust marker from every summary surface while
the clears keep passing; the synthetic marker test
(test_coverage_matrix) hand-builds a finding with the magic substring, so
it would keep passing too. The live guards are the presentation golden
(marker present ×3, byte-pinned) and the sweep's wording pins — real but
indirect. Worth a shared constant (install.py exports the phrase; coverage
imports it) or a structured flag on `Finding`. Not blocking.

## F-3 — NIT (resolved by verification): the reports' suite-growth
itemization sums to +49; the real growth is +50 and is legitimate

Live collect-only counts, master (e87b915 = c4692f5 + a .gitignore line)
vs branch tip: coverage_matrix 21→22 (+1), install_axes 20→21 (+1),
install_sweep 20→23 (+3), scripts_spec_rewire **97→99 (+2)**, new
test_sequence_schema 29, new test_cpg_core 14; every other changed test
module count unchanged (caddy 17, frame 10, platform_detail 20,
platform_spec 4, site_model 26, site_model_report 9, trebuchet 10,
foundation 9, doc_build_blocked 2). Total +50 = 1116→1166 ✓. The
"unaccounted" test is `test_scripts_spec_rewire.py::test_no_test_loads_a_detail_py[test_cpg_core.py]`
— the `tests/test_*.py` glob (rewire :154) auto-picking up the SECOND new
test file, exactly as it picked up test_sequence_schema.py for seqschema's
+1. A guard auto-extending over a new file, not a behavior change. The
cpgcore report's growth list just failed to count it separately.

## F-4 — NIT: `Detail._write_build_sequence` appends on every call

base.py: the Build Sequence section is appended (`open("a")`) to
`validation_report.md`; a second `document()` into the same out_dir would
double-append the section. The other writers overwrite. Only matters for
repeated documentation into one directory; flag for the +presentation
increment.

---

## What was probed and HELD (run evidence)

**Third lift rule, scoping (brief probe 1).** Read: the drop
(event_graph.py:431-441) requires (a) BOTH directions present in the SAME
connection's lifted set (the `(ea, eb, conn)` key), (b) the drive event to
belong to that connection (`drive_ev.subject == conn`), (c) the placed part
to be that connection's member. Probes run:
- genuine part-level member↔fastener 2-cycle in one connection ⇒ **loud**
  (`_check_install_order` still runs on the union first — connection.py:646
  — and it is now load-bearing for the third rule's soundness: only
  part-level-ACYCLIC interleaves ever reach the drop);
- cross-connection both-directions (connection B declaring both ways
  between A's fastener and a shared member) ⇒ **loud** (part-level cycle;
  and the event-level scoping would refuse the drop regardless since
  drive.subject ≠ B);
- the shipped rock anchor compiles cycle-free with exactly the pinned
  surviving necessity direction (test_cpg_core, re-run PASS);
- dropping both directions of a true interleave and keeping derived
  presence is the conservative reading at event granularity (the FAIL
  direction; never a quiet "later") — sound, EXCEPT via the F-1 channel
  above, which is the one way the "never quietly later" promise breaks.

**Axis-3 §4.1 on the ONE graph (brief probe 2).** No false PASS is
constructible from the reachability mechanics themselves: `precedes` is
BFS over out-edges (a-before-b stored as a→b, verified at :193-224 and in
the lift at :414-417), so `later` = a proof path in a checked DAG = the
occupant is later in EVERY valid linearization. Every path OUT of a drive
event must start with a technique/authored edge (necessity edges all point
INTO drives — :484-502), so the §4.3 "every clear leans on a declared
fact" ceiling holds structurally. The `e_p == e_f` co-installed skip is
safe: only the fastener's own group's material maps to its drive event,
and that is already in the sweep's skip sets. The accretion assumption is
stated in `_DECLARED_ORDER_RUNG`, the angled order-note, the epistemic
table lede, and SEQUENCE_INTRO. `_Scope.installed_after` and the `order`
field are GONE (diff-verified; the only remaining mention is a docstring
describing the old closure) — one order truth. The one semantic hole found
is F-1 (a wrong edge admitted, not wrong reachability).

**Corpus truth, live (brief probe 3).** All from re-run suites on this
machine: platform {capacity×3, install_access×2} → {capacity×3}, counter
pinned term-PASS×82/access-PASS×82; the two top-toe clears are
double-qualified (wedge-fact why + "covers the joist's own insertion
between the bolts" + "insertion travel is not analyzed at any rung (P1)")
and the four lower toes are pinned NOT to borrow the declared wording;
caddy 8 blocking UNKNOWNs stand (arm named, no-order-fact named,
no-connection clause, staging FUTURE-only); frame 8 stand (§4.1 wording);
composed site 6→4 blocking with the toes flipping via fragment-chain
replay ([authored_sequence] visible composed) and rod-vs-rung naming BOTH
gaps (cross-fragment/CPG v2 + insertion/P1); platform frozen truth
re-frozen with EXACTLY the two (check,subject,passed) flips +
findings_fp/content_fp/SHA bookkeeping, geometry fingerprint untouched
(diff read in full); "before a construction process graph exists" greps to
zero in src/scripts/tests/details. Five further modules re-pin the
platform blocking set consistently (spec/detail/foundation/doc_build/site).

**CAT-I + Q9 (brief probe 4).** Both halves re-run PASS. The opposite
authored order flips the two toes UNKNOWN→FAIL with [authored_sequence] as
the proving fact (spec-TEXT mutation, shipped file untouched); the load
half pins the authored-vs-technique cycle error with both families named.
The Q9 probe asserts all four properties per pin — verdict class UNKNOWN,
blocking, occupants named (bolt AND nut), missing order fact named — plus
the false old sentence asserted ABSENT; a weaker UNKNOWN (non-blocking, or
occupant-less, or gap-less) fails at least one assertion. Caveat for the
record: CAT-I's falsifiability covers hardware/drive occupants; F-1 shows
the member/place class escapes it.

**Rung/marker discipline (brief probe 5).** The AST guard walks every
string constant in src/ excluding docstrings, exempting only
RESERVED/negation phrasings — injecting a claiming string would land in
`offenders` (logic read in full); its live twin sweeps every corpus
finding. SEQUENCE-PROVEN is claimed nowhere; STANDING_NOTE re-words the
rung as RESERVED and stays escape-stable. The amendment-3 marker rides the
family note, both matrix renderers' verdict cells (`verdict_display`), and
both headline forms, with the bare-verdict negative half pinned; the
presentation golden carries it ×3. Amendment-5 vocabulary: `AuthoredStage`
/`ResolvedStage` vs `ReaderStep` are distinct types; the only "step"
mentions in the new spec-surface code are the deliberate differentiation
notes. The `FastenerInstallation.stage` collision is pre-existing and
flagged in the report — treated as the known residual, not a finding.
v1-core scope (amendment 1) respected: no `join`/`process` event kinds, no
staging keys (unknown-key errors pinned), no viewer/PNG changes (zero
rendering/ diffs), no evidence projection (`install_event` greps to zero;
detail_counts.json untouched).

**Re-pin honesty sweep (brief probe 7).** Every changed test diff read:
caddy/frame e2e keep their verdicts and STRENGTHEN assertions (5 wording
clauses added each); the five platform-adjacent modules all re-pin to
capacity-only with the CPGCORE reason in the comment; site_model asserts
the cross-fragment + P1 clauses on the rod; axes re-pins the CAT-E lineage
to the new mechanism truths (member FAIL now demands the
structural_necessity provenance — a STRONGER pin) and adds the F-7
synthetic; trebuchet extends the reader-surface pin (epistemic table +
Build Sequence on md AND html, 13 install units, rung-guard). Nothing
silenced, nothing weakened, no orphaned churn (tree/trolley/rock_anchor
frozen-truth noise reverted as claimed — their files show zero diff).
serialize.py round-trip gap is a real fix (`sequence:` now serializes,
emitted only when present).

## Gates (this review's own runs)

- Import path verified before every run:
  `<worktree>/.shim/detailgen/__init__.py`.
- test_cpg_core 14 · test_sequence_schema 29 · test_install_axes 21 ·
  test_install_sweep 23 — all PASS.
- Re-pinned batch (coverage_matrix, platform_spec, platform_detail,
  foundation_obligation, doc_build_blocked, site_model,
  site_model_report, caddy e2e, frame e2e, trebuchet e2e):
  **129 passed in 8:37** (shimmed, single worker).
- Probe scripts (scratchpad): probe_lift3.py (A: part-level cycle loud ·
  A2: interleave drop + necessity present · B: cross-connection loud ·
  C: **authored-after stage sails through, member flips later**),
  probe_necessity_override.py (plain member, same flip),
  probe_waiver_e2e.py (CAT-E fixture FAIL→PASS end-to-end).

---

# Confirmation round (fix commit 9837dbc) — **CONFIRMED**

Scoped re-verification of the fix round, run live from the shimmed
worktree (import path re-verified). No re-review of the branch.

**F-1 closed, verified by re-running my original constructions.**
`build_event_graph` now walks a `technique_out` map filtered to
`FAMILY_TECHNIQUE` (`_technique_reaches` — event_graph.py), exactly the
suggested scope. All three original silencing constructions re-run against
the fixed tree:

- plain member staged after its own drive → **EventOrderCycleError**, the
  message printing BOTH edges with BOTH families and sources:
  `drive(J, g) -> place(member) [authored_sequence] (…why…)` and
  `place(member) -> drive(J, g) [structural_necessity] (…must exist
  before…)` — the §6 rule 1 error, verbatim shape;
- the interleave variant (f1 → member → f2 chain, technique directions
  dropped, necessity the only guard) → same loud cycle;
- the end-to-end CAT-E waiver probe → compile now REFUSES (cycle error);
  the baseline derived member FAIL re-verified intact with no stages.
  The FAIL→PASS flip is unreachable — it cannot even load.

Unchanged behavior re-verified in the same runs: the hanger's technique
suppression still works, the rock-anchor interleave drop still leaves
exactly the conservative necessity direction, part-level and
cross-connection contradictions still loud.

**The three regression pins genuinely encode the constructions.**
`test_f1_stage_cannot_silence_structural_necessity_member_after_drive`
(graph level, asserts both families AND both source claims in the
message), `test_f1_interleave_variant_stage_vs_necessity_still_cycles`
(the exact chain-through-member shape, WITH the sanity half first
asserting the drop + surviving necessity direction, then the cycle), and
`test_f1_authored_stage_cannot_flip_a_member_fail_to_declared_pass` (the
exact CAT-E fixture through `compile_connections`, asserting refusal +
both families + the slab named). Each fails if the exception walk regrows
authored edges: no cycle would be raised and every `pytest.raises` trips.
Pinning refusal-at-load is stronger than pinning the verdict.

**F-2 correct.** `Finding.declared_order` structured flag; set at both
(and only) declared-order clear emitters (`_access_shank`
`declared_order=bool(later_all)`, `_access_angled`
`declared_order=bool(later)` — the same two sites the old substring
matched); coverage counts the flag, never the wording. Decoupling pinned
BOTH directions in test_coverage_matrix: flagged finding counts; a
finding whose TEXT contains the marker wording but lacks the flag does
NOT. Re-worded rung sentences can no longer silently move the summaries.

**F-4 correct.** `_write_build_sequence` cuts any prior section from its
heading before re-appending — safe because the section is the last md
writer in `document()`'s fixed order; pinned by the trebuchet double-append
(one heading, 13 install units preserved).

**Corpus unmoved, verified.** The fix commit touches NO files under
`tests/baselines/` or `details/` (frozen truth + presentation golden
byte-identical by construction), and my re-runs: test_install_sweep
**23 passed** (every per-detail counter pin, the platform declared-order
clears, caddy 8 / frame 8 / site rod blocking, CAT-I both directions, Q9);
test_cpg_core + test_install_axes + test_coverage_matrix **60 passed**
(16 + 22 + 23 — the +4 are exactly the three F-1 pins and the F-2
negative-direction case, matching the report's gate counts).

**Residual nit (non-blocking, cosmetic):** the cycle error's closing
teaching line still reads "…contradicts a ConnectionType's technique
edge…" even when the conflict is authored-vs-structural_necessity; the
edge list above it names the true families, so no one is misled — worth a
generic re-word whenever the message is next touched.

**Verdict: CONFIRMED.** F-1/F-2/F-4 closed on merit with real pins; F-3
was already resolved-by-verification. No new findings.
