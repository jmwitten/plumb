# Adversarial review — STEPDOC / Construction Process Graph v1 design

**Target:** `.superpowers/sdd/stepdoc-cpg-design.md` @ `31df981` (branch `sdd/stepdoc-design`)
**Reviewer stance:** fresh adversary. Every geometric and mechanism claim that could be
checked by running code WAS checked by running code: compiled `armchair_caddy`,
`sit_reach_frame`, `platform`, `trebuchet` from the worktree (shim-verified import path),
ran `validate()`, dumped the actual axis-2 UNKNOWN findings and their named blockers,
dumped the platform's full 183-edge `installed_before` set, and inspected the bolt
connection's resolved role-group structure.

## VERDICT: REVISE

The core mechanism is sound — §4.1's partial-order verdict semantics survive every
joint-impossibility attack I could construct (Q1 below: the rule cannot emit a false
PASS; jointly-impossible co-blocker sets surface as cycles, not as quiet clears), the
hit-set-reclassification trick (§4.2) is exact under the stated accretion assumption, the
caddy and platform corpus rows check out against live geometry, and every substrate
citation I verified is accurate. The honesty rules are the right generalization of the
never-silence comment.

But the design's acceptance corpus is 1/3 broken on real geometry: the sit_reach_frame
row promises 8 PASSes that are **provably unreachable under the design's own semantics**
(the blockers are symmetric and mutually blocking — I ran the check and the findings name
each side's screws as blockers of the other side's), which flips Q2's answer from "detail
level is enough" to "the corpus demands per-subassembly staging," breaks CAT-H, and
deflates the headline "18 UNKNOWNs paid down" to 10. Two more CATs (G's reversion half, L)
promise verdicts the mechanism cannot deliver — the same F-3/F-4 defect class the INSTALL
review caught — and the doc contradicts itself twice (§3 vs §4.4 on the rod-vs-rung
reason; §4.4's "either order is buildable" vs CAT-I's required FAIL).

---

## Findings

### F-1 — The sit_reach_frame corpus row and CAT-H are geometrically impossible as designed — MAJOR (blocking)

I compiled the shipped frame and dumped all 8 `install_access` UNKNOWNs. The design's
model of the detail ("8 rail-screw corridors into the opposite wall", fixed by "rails
staged before the closing side") is wrong about the geometry. The real blocker sets are
**symmetric**:

- each **+X** rail screw's corridor is blocked by the **−X side's** front/back leg, side
  rail −X, the −X cap screws, **and the mirror −X rail screws themselves**;
- each **−X** rail screw's corridor is blocked by the mirror **+X** parts and screws.

(Heads at x=±1.0 in, 6.00 in × 1.00 in dia declared envelope, opposite rail at
x[−2.5,−1.0] — the corridor crosses the ~2 in interior gap into the other side. Verified
from the live finding texts; e.g. `rail screw front +X hi` names `front leg -X
(footplate)`, `side rail -X`, `cap screw front -X`, `rail screw front -X hi` as blockers,
and `rail screw front -X hi` names the +X mirrors.)

Consequence, formal: for all 8 to PASS under §4.1, `drive(front +X grp)` must provably
precede `drive(front −X grp)` (the −X screw is a corridor occupant of the +X screw) AND
vice versa (the +X screw occupies the −X corridor) — a direct 2-cycle before member
places are even considered. Adding members makes it worse: clears need
`drive(+X) → place(rail −X)` while structural necessity gives
`place(rail −X) → drive(−X)` and `place(rail +X) → drive(+X)`, closing
`place(rail +X) → drive(+X) → place(rail −X) → drive(−X) → place(rail +X)`. **No
cycle-free detail-level order clears all 8.** The best any authored sequence achieves in
situ at final relative pose is 4 PASS + 4 FAIL (stage side A fully before side B: side A's
screws clear because side B arrives later; side B's screws FAIL because side A is provably
present). Those 4 FAILs are honest — you genuinely cannot drive the second side's screws
across a 2 in gap with a 6 in driver once the first side is closed.

The real build benches each side (legs + rail screwed as a unit, opposite side absent),
then joins the two units under the top plate (the cap-screw corridors PASS in final
geometry — verified). That is exactly **per-subassembly staging**, which §11 Q2 defers
and §3.4's `bench_then_set` cannot express (it only moves CONTEXT bodies, and the frame's
blockers are all real parts; the frame has no context body — verified, only a `floor`
part). Alternative honest fix: a declared stubby/right-angle driver `tool_envelope`
override (< 2 in) clears the corridors at axis 2 with no sequencing at all — the axes
report already names this option for the frame.

**Required:** rewrite the frame row and CAT-H around one of: (a) per-subassembly staging
pulled INTO v1 scope (Q2's answer is yes, the corpus demands it), (b) the tool-envelope
override route (axis-2 fix, no CPG involvement — then the frame leaves this corpus), or
(c) the honest 4-PASS/4-FAIL split as the declared outcome. In every case recompute the
headline: as designed, v1 flips 10 of 18, not 18.

### F-2 — CAT-G's reversion probe contradicts §3.4's own `in_situ` semantics — MAJOR

CAT-G: "delete the staging declaration from the shipped spec text → the 8 UNKNOWNs return
verbatim." But §3.4 says the default absent a declaration is `in_situ` = "context bodies
present from the root." Present-from-root is an order fact: `place(sofa arm)` precedes
every drive event, so §4.1's first bullet (`e_p` provably precedes `e_f`) makes each of
the 8 corridors a **FAIL**, not an UNKNOWN — and that FAIL is arguably the honest in-situ
answer (building the caddy on the sofa, the corridors really are blocked). The promised
reversion verdict is undeliverable as specified — the INSTALL review's F-3 class.

"Verbatim" is separately unsatisfiable for **all three** corpus rows: the standing
UNKNOWN text ends "before a construction process graph exists (axis 3)", which is false
the moment v1 lands; §4.1's own new wording is "build order underdetermined … no order
relates <e_f> and <e_p>". Reversion probes should demand "returns to a blocking UNKNOWN
naming the gap," not byte-verbatim restoration of a sentence that names the CPG's absence.

**Required:** pick the `in_situ` semantics and make CAT-G consistent with it. Either (a)
undeclared-staging context corridors become FAILs — then say so in §10's "no silent
reclassification" section, because it flips today's 8 caddy UNKNOWNs to FAIL for any
author who does NOT declare staging, a semantics change the design currently never
mentions; or (b) context presence absent a declaration is UNORDERED (UNKNOWN) — then
"present from the root" is the wrong sentence and the platform's tree needs re-wording.
And re-word every "verbatim" reversion expectation.

### F-3 — CAT-L's only named lever destroys the thing it claims to hold constant — MAJOR

CAT-L: "Force a different reader-step grouping (stage names removed → per-connection
grouping): every axis-3 verdict is byte-identical." But stages ARE the
`authored_sequence` order surface (§3.3: named stages, totally ordered). Removing them
removes order edges, and on any corpus detail the verdicts then legitimately change (the
frame's/caddy's clears revert). The invariant CAT-L wants to test — verdicts never depend
on presentation grouping — is true by construction (§5.1's grouping is downstream of the
graph and nothing feeds back; I looked for a feedback path through step text, view
coverage, and content-keyed renders and found none), but **v1 has no presentation-only
grouping knob, so the CAT as written is either self-defeating or untestable**. The
INSTALL review's F-4 class: a CAT whose example is invalid.

**Required:** re-author CAT-L with a lever that moves ONLY presentation: e.g. author
stages on a detail whose verdicts provably don't depend on them (the stool — no standing
axis-2 corridor UNKNOWNs) and delete them, asserting byte-identical verdicts; or add an
explicit presentation-grouping override and test that.

### F-4 — §3 and §4.4 contradict each other on the site rod-vs-rung UNKNOWN — MODERATE

§3 (Retire/repeat/site): the composed-site order questions "stay UNKNOWN, named, with
'site-level sequencing not represented (CPG v2)' as the stated reason." §4.4: the same
finding "stays UNKNOWN with the honest reason updated to name insertability rather than
the absent CPG." Both can't be the shipped sentence. Substantively, BOTH facts are true
and the reason should name both: the rung-over-rod blocker is (a) a cross-fragment ORDER
question — the anchor is obviously installed before the platform exists, exactly what a
CPG v2 site graph would prove — and (b) an insertion-travel question (the rod's
"corridor" is its own body's insertion path, the axes report's named P1 residual).
Renaming it insertability-only mislabels the mechanically-checked half. (Checked the rest
of the corpus for secret insertability needs: the caddy's set_in_place is disclosed ✓;
the platform end joist is "wedged in a ~3.5 in clear gap between two thru-bolts" per the
ToeScrewed docstring — its insertion is covered only because the authored toe-first order
also happens to put the joist before the bolts; worth one disclosing sentence.)

### F-5 — The event lift creates self-loops on every bolt stack — MODERATE

§3.1's lift rule: "part → its place event, hardware → its group's drive event." Verified
live: the platform's bolted connections emit hardware→hardware `installed_before` edges
WITHIN one role group — `bolt +Y0 → bolt washer head +Y0 → bolt washer +Y0 → bolt nut
+Y0`, 40 such edges platform-wide, and the resolved contract shows a SINGLE role group
`bolt_stack` (fastener = the hex bolt; washers/nut are its `stack`). Under the lift as
written all four pieces map to the same `drive(conn, bolt_stack)` event and the three
stack edges become **self-loops**, which the extended `_check_install_order` (Kahn) reads
as a cycle — every bolted detail fails at load, day one. **Required:** the lift must
state that edges whose endpoints map to the same event node are order-vacuous and are
dropped (they express intra-event assembly order the event's atomicity already owns).

### F-6 — §3.3's staging falsifiability cites a mechanism the design never builds — MODERATE

§3.3: a declared staging is falsifiable when "a context body a fastener genuinely needs
DURING bench assembly — e.g. a bearing on context — would surface as a cycle." But
`bears_on` is not one of the four edge families; nothing in the design lifts bearings
into the event graph, so a bearing on context surfaces NOTHING. The only real
falsification channel is connection MEMBERSHIP (structural necessity: `place(context) →
drive(...)` vs set_in_place-after-drives → cycle) — and I verified the caddy's sofa arm
is a member of ZERO connections, so the caddy's own staging claim is pure declared trust.
The un-owned-fastener residual compounds this: tree_attachment's lags live outside any
Connection, so even a context body that IS fastened to can escape membership-based
falsification. The abuse case (declare `bench_then_set` on something context-anchored,
e.g. the platform around its tree) is refused only if the context participates in a
connection. **Required:** delete or fix the bearing parenthetical, and state plainly that
for connection-free context bodies v1 staging is declared-and-trusted, falsified only by
insertability later — the rung wording ("at the DECLARED build order" + staging claim
printed) is honest, but §3.3's falsifiability sentence currently overclaims.

### F-7 — §4.1 silently changes today's party-present ⇒ FAIL rule — MODERATE

Today `_classify` (install.py:717-746) FAILs any same-connection occupant not explicitly
ordered after the fastener ("party present at this joint's own install step"). §4.1 has
no party rule: an occupant with no order path either way is UNKNOWN. For MEMBER occupants
structural necessity re-derives the FAIL (place → drive). But for same-connection
HARDWARE in a different role group, no derived family emits drive↔drive edges, so a
today-FAIL would become an axis-3 UNKNOWN — a quiet weakening the design never mentions,
and the pinned unordered-party FAIL tests (CAT-E lineage, test_install_axes.py) re-derive
differently or break. I found no shipped detail that hits this (the hanger's two groups
are ordered by its own technique edges; bolt stacks are one group), so it is a
design-text gap, not a corpus break. **Required:** state the delta and defend it — either
"unordered cross-group hardware is honestly UNKNOWN now, and here is why that beats the
old party assumption," or keep a party-present default with provenance.

### F-8 — SEQUENCE-PROVEN clears are structurally unreachable in v1 (Q4 answered) — MODERATE

§4.3 lets a verdict claim SEQUENCE-PROVEN when "deciding order facts [are] all derived."
Trace the derived families: `structural_necessity` emits only place→drive
(before-direction) edges; `bond→cure` targets a process event, never an occupant. **No
derived edge ever places an occupant provably AFTER a fastener**, so every clear's
deciding path necessarily includes a declared edge (technique_default, authored_sequence,
or staging) — the only all-derived verdicts are FAILs (occupant provably before, via
structural necessity). The SEQUENCE-PROVEN rung as offered for clears is vacuous in v1.
Answer to Q4: take the alternative — v1 claims SEQUENCE-PROVEN nowhere (or state
explicitly that the rung is reachable only by FAIL verdicts, which don't wear rungs the
same way). This also makes §4.3 shorter and the ladder honest by construction.

### F-9 — CAT-J's affected-region half is vacuous under the standing zero-attribution floor — MINOR

The axis findings are DELIBERATELY unattributed in the evidence graph (axes report
"Soundness fix": floor 45 → 209, revisited every non-empty edit), so on any edit today
the affected region includes every axis verdict — CAT-J's "the affected region includes
the flipped verdicts" is satisfied by the coarse floor regardless of whether the CPG
mechanism works. The discriminating halves are the ones CAT-J should lead with: the step
renders' content-key moves (PNG hash) on an order edit, and — add this — an UNRELATED
edit does NOT regenerate step sections/renders. Either scope the region claim to
"once axis dependency sets are persisted" or assert the negative half.

### F-10 — Hand-typed sequence prose already lives in the target documents — MINOR

§6.5: "the step doc contains no hand-typed sequence prose." The caddy's existing
single-detail panel already narrates sequence by hand — the fieldnote "Hidden rail
joints — glue, then screws, all off the sofa" and the buy lede live as authored strings
in `scripts/single_detail_report.py` (the glue-caddy report quotes them). CAT-K's
grep-closer ("no step title, order, or sentence is hand-authored in the report scripts")
either trips on these or is quietly scoped around them. State the boundary: pre-existing
hand panels that narrate sequence must derive, retire, or be explicitly exempted with the
reason on paper — otherwise the single-source mandate is violated inside the very
document that carries the derived steps.

### F-11 — §4.4's platform row contradicts CAT-I (and itself) — MODERATE

§4.4 platform row: "either order is buildable; the builder's pick is the claim." CAT-I:
author bolts-before-toes and "the 2 UNKNOWNs must flip to FAIL." Both cannot be true: if
either order were buildable, CAT-I's FAIL would be a false alarm. The geometry sides with
CAT-I — with the bolts/nuts present, both 30° corridor candidates for the top toe screw
are obstructed (verified live: blockers are `bolt ±Y0/±Y1` + nuts, foreign, both cheeks),
and the ToeScrewed docstring's own wedge fact (the joist drops into the ~3.5 in gap
BETWEEN the bolts) says the joist itself can't arrive after the bolts either. So
bolts-first is NOT buildable under the model, the toe-first order is closer to a
technique fact than a coin flip, and the authored `why:` should cite the wedge, not
"builder's chosen order." Fix the row's parenthetical; this also strengthens Q5's answer
(below).

### F-12 — Substrate claims verified accurate — INFO

Everything I checked is as cited: `_check_install_order` global cycle check
(connection.py:611, Kahn over merged `installed_before`); hanger technique edges incl.
header-screws-before-hung-member (connection.py:1196-1213); `glued` emits NO
installed_before, one `bonded_to` (connection.py:~1710); contract `stage:
"own_connection"` + CPG docstring (installation.py:262-273); `_classify` +
never-add-edges binding comment (install.py:717-746); foreign-UNKNOWN wording
(install.py:750-772); `_Scope.installed_after` own-connection closure (install.py:~323);
`UnknownProcessStepKind` keeps cure out of `fold` (process_graph.py:70-74);
`build_viewer_payload` keyed by `Placed.name` = GLB node names (web_viewer:92-149);
`extra_sections` consumer hook (single_detail_report.py:938/1147); `_ensure_views` is
genuinely fills-missing-only (def at :1099; consumer lambdas :826+ — the design's :826
cite is the consumer, close enough); `ProcessRecord.fab_note` is the one fab-note source;
the caddy spec's assumptions really do put cure BEFORE the side screws (§0's motivating
claim); trebuchet really has 13 connections (Q6's number). Corpus arithmetic verified
live for two of three rows: **caddy ✓** — all 8 corridors name ONLY the sofa arm (zero
other occupants), so `bench_then_set` alone flips all 8, with the cure constraint
orthogonal (it feeds CAT-K, not the corridors); **platform ✓** — the 2 UNKNOWNs' blockers
are exactly the four bolt connections' stacks, and the authored toe-before-bolts edges
are cycle-free against the full dumped edge set (bolts have no outgoing edges except
into their own stacks; `beam → end joist → toe screws` is upstream of the new edge).

---

## The six open questions, answered adversarially

- **Q1 — sound; cannot false-PASS.** For one fastener, corridor blockage is per-part
  monotone (blocked iff ≥1 present part intersects), so per-occupant provably-after is
  exactly the right condition — a PASS holds in every valid linearization, and a valid
  linearization exists because the merged graph is cycle-checked. Jointly-impossible
  co-blockers (each individually orderable-after, not simultaneously) are REAL — the
  shipped frame is the concrete case (F-1: mutual screw-pair blocking) — but the
  semantics catch them as unsatisfiable-order/cycle, never as a quiet double PASS. The
  "too strict" half is empty: a geometrically harmless part is not a corridor hit, so it
  is never an occupant. The one semantic hole is F-7 (unordered same-connection hardware
  flips today's FAIL to UNKNOWN), which is a disclosure gap, not an unsoundness.
- **Q2 — the corpus DEMANDS per-subassembly staging.** F-1: the frame's 8 cannot flip at
  detail granularity; benching each side unit is the real build and the only staging
  shape that clears all 8 (join happens under cap screws that PASS in final geometry).
  Either pull per-subassembly staging into v1 or take the frame out of the corpus (tool
  override or honest 4/4 split) and shrink the headline.
- **Q3 — sound under the stated assumption; no shipped counterexample.** With
  accrete-at-final-pose, the partial assembly at any step IS a subset of final-pose
  solids, so presence-filtered final hits equal partial-assembly hits exactly —
  reclassification without resweeping is not an approximation. Corridor-through-a-
  future-part's-void is handled (the future part is an ordered-after occupant). The
  leaks are precisely the disclosed ones: a part's own travel (insertability, P1),
  temporary poses/supports (CPG v2). Bench staging survives the assumption too: within a
  bench unit parts sit at final RELATIVE pose and the absent context contributes no hits.
- **Q4 — claim SEQUENCE-PROVEN nowhere in v1** (F-8): no derived family can ever decide a
  clear, so the derived-only rung is unreachable except by FAILs. The alternative wording
  in the question is the honest line and costs nothing.
- **Q5 — authored order, but with a defended why.** The both-orders check is real
  mechanism for a rare case; defer it. However §4.4's "either order is buildable" is
  false (F-11) — the platform's toe-first order is quasi-technique (the wedge fact), so
  author it with `why:` citing the joist-between-bolts geometry, and note the insertion
  half stays un-analyzed (P1) in the disclosure.
- **Q6 — per-connection default is right; don't build arrival-cluster grouping.** The
  worst ungrouped case really is 13 (verified), not 57 — parts fold into their consuming
  connection's step, so the trebuchet emits ~13 step renders, which is a page section,
  not an explosion. Arrival-cluster grouping is a derived heuristic whose regrouping
  under small edits would churn content-keyed renders for zero verdict value. Revisit
  only if a real detail ships with an unreadable step count.

## What would move this to ACCEPT

1. **F-1**: re-author the frame corpus row + CAT-H against the real symmetric blockers
   (per-subassembly staging in scope, or tool-override/out-of-corpus), and recompute the
   18-UNKNOWN headline honestly.
2. **F-2**: resolve the in_situ-vs-reversion contradiction; own the UNKNOWN→FAIL flip (or
   the unordered-context alternative) in §10; drop "verbatim" from reversion promises.
3. **F-3**: rebuild CAT-L around a presentation-only lever.
4. **F-4 / F-11**: fix the two self-contradictions (rod-vs-rung reason names BOTH order
   and insertability; platform row's "either order is buildable" retracted).
5. **F-5**: add the same-event edge-drop rule to the lift (bolt stacks self-loop today).
6. **F-6**: fix §3.3's falsifiability sentence (bearings have no event-graph mechanism;
   connection-free context staging is declared-and-trusted, say so).
7. **F-7 / F-8**: state the party-rule delta; adopt the Q4 alternative (no
   SEQUENCE-PROVEN claims in v1).

CATs after fixes: CAT-G (forward half), CAT-I, CAT-K stand as sound; CAT-G's reversion
half, CAT-H, and CAT-L need rebuilding; CAT-J needs its discriminating half stated. The
caddy and platform acceptance rows are verified deliverable; the frame row is not, and
the design should not reach the owner claiming 18 until the frame's honest path is chosen.

---

## Confirmation round — revision @ `c84c8d7`

**Verdict: FIX-AGAIN — exactly two items (R-1, R-2), both one-paragraph edge-rule
additions in §3.1/§3.4; everything else CONFIRMED.** Each F-item's fold was verified
against my original constructions (not re-reviewed from scratch), and the two new gaps
are of the same family as F-5 — order facts the lift/staging rules leave unencoded — one
of which makes a §4.1 sentence false and the other of which would crash the platform at
load. Neither invalidates the design's shape; both are mechanical to state.

### Required before owner

**R-1 — Nothing orders a unit's internal events before its `join` — §4.1's "every valid
build order" sentence is false for bench clears as written.** §3.4 defines bench-frame
presence ("only S's parts can be present") but no edge family emits
`<every bench-scoped event of S> → join(S)`. Without it, valid linearizations exist in
which the unit joins the root and its screws are driven AFTERWARD — with the mirror side
present, exactly the corridor the bench clear claimed absent — so a frame rail-screw
PASS does NOT hold in every valid order, and Kahn's canonical linearization could print
"set the unit in place" before the unit's own screws. The staging declaration's content
("assembled apart") must be encoded as derived staging-family edges: every bench-scoped
place/drive/process event of S precedes `join(S)`. One rule; it also makes CAT-H's step
run ("bench side +X → bench side −X → join") derivable instead of assumed.

**R-2 — The lift rule is ill-defined for hardware riding MULTIPLE role groups' stacks,
and one of the two candidate mappings cycles every hanger-bearing detail.** "hardware →
its group's drive event" (§3.1) assumes one group. The FaceMountHanger's hanger piece
rides BOTH screw groups' stacks (axes report §GEO-F1 — each group drives through one of
its flanges), and its type edges are `header→hanger`, `hanger→header screws`,
`hanger→hung`. Map the hanger to `drive(hung-side)` and `hanger→hung` lifts to
`drive(hung-side) → place(hung)`, which cycles with `place(hung) → drive(hung-side)`
(the type's own hung→hung-screws edge / structural necessity) — the platform fails at
load. Map it to `drive(header-side)` and everything collapses consistently:
`hanger→header screws` becomes a self-loop and drops under the F-5 rule,
`hanger→hung` lands as a duplicate of the existing header-screws-before-hung technique
edge, `header→hanger` becomes place-before-drive. The design must state the multi-stack
mapping rule (e.g.: multi-stack hardware maps to the drive event its OWN type edges
place it at-or-before — the hanger's `hanger→header screws` edge names the header-side
drive), with the hanger as the pinned example. Same defect class as F-5, second live
instance, found by walking the same shipped edges.

### Confirmed items (verified against the original constructions)

- **F-1/Q7 — CONFIRMED (with R-1).** Re-derived the frame row against my 2-cycle: the
  two declared side units dissolve it — each side's 4 screws drive in its bench frame
  where every blocker (mirror legs/rail/screws, root cap screws) is non-S ⇒ absent. The
  scoping falls out of the member-subset rule alone, verified live: all 4 rail
  connections' members ⊆ their side unit ({side rail ±X, front/back leg ±X}); all 4 cap
  connections span (top plate is root) ⇒ root-scoped with the derived join-before-drive
  edges, and their corridors PASS on final geometry. Minimality holds — no corpus case
  demands nesting or per-unit context. Abuse probe run as asked: declaring a platform
  unit `[end joist, beam +Y]` bench-scopes the toe screws and flips the 2 UNKNOWNs with
  NO authored order — and it is geometrically a legitimate alternative build (screw the
  joist to the beam on the ground, hoist, then bolt); what is NOT checkable is
  feasibility (weight, hoisting), which is exactly the declared-trust ceiling §3.4/§6.1/
  §10 now state. Consistent with the F-6 wording; no new waiver channel beyond what the
  design names.
- **F-2/CAT-G — CONFIRMED.** UNDECLARED=UNORDERED preserves the day-one state (today's 8
  caddy UNKNOWNs stay UNKNOWN, re-worded to name the missing declaration); the three
  CAT-G halves each map to a distinct decidable mechanism (bench-frame absence /
  unordered ⇒ named blocking UNKNOWN / explicit in_situ ⇒ provably-before ⇒ FAIL); §10
  owns the only place a today-verdict hardens (explicit in_situ is an authored claim, so
  the flip is author-triggered, never default).
- **F-5 — CONFIRMED for the single-group case.** The drop rule covers my 40-edge
  platform construction (all intra-`bolt_stack`). R-2 is the multi-group remainder.
- **F-7/Q8 — CONFIRMED; Q8 ruled out.** Searched for a technique where the old
  party-present⇒FAIL was load-bearing: the old rule's only load-bearing property was
  that it BLOCKED, and blocking is preserved (the new UNKNOWN is blocking and names the
  fix). Its assumption ("party present at own step") is precisely what produced the
  hanger's false-impossible-FAIL class before the technique edges refuted it — the
  softening removes a known false-FAIL generator, and no shipped verdict moves
  (re-verified: hanger groups ordered by type edges; bolt stacks one group). The
  CAT-E-lineage re-pin plan is stated, not silent.
- **F-3/CAT-L — CONFIRMED, fixture verified live.** Compiled the current stool: 8/8
  `install_access` findings, ALL PASS, and — the stronger property — ZERO
  order-dependent text in any verdict (no corridor occupants, no ordered-after
  disclosures; the station-not-face FAILs were fixed by the stool fix arc). Adding then
  deleting stages cannot move any verdict byte, so the byte-identical assertion is
  airtight on this fixture.
- **Q9 — CONFIRMED, adequate.** The probe form pins four properties: verdict class
  (UNKNOWN), blocking, the occupant's name (the arm), and the named missing declaration.
  A weaker-UNKNOWN regression (non-blocking, or occupant unnamed, or generic wording)
  fails at least one. The implementation must assert all four per pin — the design text
  says so; hold it to that in the task review.
- **Diff sweep for new overclaims — CLEAN.** The 18/18 headline carries its basis
  ("every one rests on at least one declared claim; zero SEQUENCE-PROVEN") in every
  location the number appears (§0 pointer, §4.4, §8, §10). The §3.2 and §4.4 rod-vs-rung
  reasons now agree (both mechanisms named — F-4 contradiction gone). CAT-J correctly
  parks the affected-region assertion while the zero-attribution floor stands and swaps
  in the discriminating negative half. §6.5 strengthened honestly (grep-closer MUST trip
  on the caddy fieldnote/buy lede). §10's "partially falsifiable through cross-unit
  cap-screw necessity edges" is mild and defensible — a wrong part-set changes scoping
  and surfaces as honest verdict movement, not silence.

### For the owner (the 2-3 decisions that are genuinely Joel's)

1. **Scope growth is real and was forced by real geometry:** per-subassembly staging
   enters v1 because the frame's eight blockers are mutually symmetric — no flat
   sequence can clear them (the 2-cycle is proven on the shipped spec). The alternative
   is a leaner v1 that pays down 10 of 18 and leaves the frame honest-red. The design
   chose 18/18 with the bigger authoring surface; that trade is yours.
2. **What the headline claims, epistemically:** all 18 clears read "geometry proven at
   the DECLARED build order" — none is sequence-proven, and the caddy's 8 rest on a
   staging claim NOTHING can falsify until insertability lands (the sofa arm touches no
   connection; §3.4 calls this declared trust, plainly). You are signing off on shipping
   checked-and-disclosed declared orders, not proven ones — the design is honest about
   this everywhere, but it is the claim's ceiling and it is your call that it clears the
   bar for "unblocked on merit."
3. **Your caddy panel prose changes form (§6.5):** the hand-written fieldnote ("Hidden
   rail joints — glue, then screws, all off the sofa") and the buy lede's sequence
   phrasing must derive from the step graph or retire — CAT-K is required to trip on
   them. The voice of that panel may read differently after derivation.
