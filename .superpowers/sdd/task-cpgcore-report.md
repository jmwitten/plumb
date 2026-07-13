# Task CPGCORE report — STEPDOC/CPG v1-core semantic core

STATUS: COMPLETE — all 10 deliverables landed; full suite green
(1166 passed / 3 skipped / 1 xfailed) at the final cpgcore commit
(branch tip; the gate ran on that exact tree).

Branch `sdd/stepdoc-core` (base @09a116f = SEQSCHEMA plumbing). All work
committed with `cpgcore:` messages. Import discipline followed: `.shim`
symlink + `PYTHONPATH`, import path printed and verified at every gate
(one near-miss caught live: a shell without the export resolves detailgen
to the MASTER repo — re-verified before the final gate).

## Per-deliverable status

1. **Event graph — DONE.** `src/assemblies/event_graph.py`. Nodes
   `place(part)` / `drive(connection, role_group)`, content-keyed
   (`Event`); `bond` = drive with empty hardware set — every group-less
   connection (glued, standoff connector) gets ONE `drive(label, "")`
   install unit; no `process`/`join` kinds built (open-tag headroom kept).
   Edge families `technique_default` / `structural_necessity` /
   `authored_sequence`, every edge provenance-stamped (`EventEdge.family`
   + `.source` claim).
   - **Both pinned lift rules + a third found live.**
     (a) Same-event drop (F-5): pinned on a live BoltedClamp
     (`test_f5_intra_stack_edges_are_order_vacuous_and_drop` — the
     platform's 40 intra-stack edges collapse; graph loads cycle-free).
     (b) Multi-stack mapping (R-2): hardware maps to the drive event its
     OWN type edges place it at-or-before; pinned on a live
     FaceMountHanger (`test_r2_multi_stack_hanger_maps_to_the_header_side_drive`)
     WITH the reviewer's cycling counterexample encoded as a test that
     performs the wrong (hung-side) lift by hand and exhibits the 2-cycle
     (`test_r2_counterexample_the_hung_side_mapping_would_cycle`);
     ambiguity (0 or 2+ at-or-before candidates) is a loud teaching error
     (`test_multi_stack_hardware_without_a_disambiguating_edge_is_loud`).
     (c) **DEVIATION/DISCOVERY — mid-event member interleave.** The
     shipped `ThreadedRodEpoxyAnchor` threads its hardware chain THROUGH
     a member (`… lo_washer → bracket → up_washer …`), so the lift
     produced BOTH `drive → place(bracket)` and `place(bracket) → drive`
     for the one anchor_rod drive event — a 2-cycle the part-level chain
     never had, failing the shipped rock anchor at load. Same defect
     class as F-5/R-2 (an order fact the lift must handle), a third live
     instance the design and review did not state. Rule shipped: when ONE
     connection's lifts produce both directions between its own drive
     event and a member's place event, both are the member's MID-EVENT
     arrival and drop as intra-event order; structural necessity supplies
     the surviving conservative direction (member PRESENT at the drive —
     an occupant is never quietly ordered "later" by a fact this coarse).
     Pinned on the shipped spec:
     `test_mid_event_member_interleave_drops_both_directions_rock_anchor`.
   - Structural necessity emits `place(member) → drive(conn, g)` EXCEPT
     where a DECLARED path (technique/authored, reachability not just
     direct edges) orders the opposite way (hanger pinned:
     `test_structural_necessity_yields_to_a_declared_opposite_path`);
     every derived edge points INTO a drive (§4.3's ceiling holds by
     construction).
   - Authored stages order stage k's events before stage k+1's WITHIN one
     chain only (`ResolvedStage.chain`; cross-chain isolation pinned:
     `test_stages_in_different_chains_never_cross_order` — a site can
     never invent cross-fragment order).
   - Merged cycle check `_check_event_order` (Kahn over all families),
     teaching error names conflicting edges AND provenance families. The
     part-level `_check_install_order` is KEPT (an intra-role-group
     hardware-chain contradiction would be masked by event collapse).
   - Duplicate connection labels are a loud error (event identity is
     (label, group) — two connections sharing a label would silently
     merge).

2. **Axis-3 reclassification — DONE.** `src/validation/install.py`:
   `_Scope.graph` (the ONE graph; the own-connection `installed_after`
   closure is GONE — single order truth), `_classify` → present / later /
   unordered by graph reachability on the same hit sets (accretion
   assumption stated in the verdicts). FAILs print deduped proof paths
   with provenance (`_order_facts`); clears lean-on-declared print §4.3
   wording; unordered ⇒ blocking `UNKNOWN — build order underdetermined`
   naming occupant + the missing order fact (`_unordered_clauses`), with
   the no-connection clause (caddy sofa arm), the cross-fragment clause
   (composed site, via `ConnectionChecks.fragments` ←
   `SiteDetail.connection_fragments()`), and the epoxy_set
   insertion-path clause (P1).
   - **F-7 party delta, deliberate:** member occupants keep FAIL via
     structural necessity with the proving edge + family printed
     (`test_cat_e_same_connection_blocker_fails_naming_it` re-pinned);
     unordered cross-group hardware re-pins FAIL → named UNKNOWN — NEW
     synthetic fixture
     `test_f7_delta_unordered_cross_group_hardware_is_named_unknown`
     (no shipped detail hits it — hanger groups are technique-ordered,
     verified by the corpus pins staying put).

3. **Rung wording — DONE, grep-enforceable.** Every axis-3 clear that
   leans on order facts reads "geometry proven at the DECLARED build
   order" (shank: `_DECLARED_ORDER_RUNG`; angled: the "clear at the
   DECLARED build order only … declared build strategy, not derived and
   not sequence-proven" sentence), with the deciding declarations + their
   provenance families printed inline and accretion + insertability (P1)
   stated in the verdict. Guards: AST scan over ALL src string constants
   (docstrings excluded; RESERVED-only mentions allowed) —
   `test_sequence_proven_is_claimed_nowhere_in_source_strings` — plus a
   live-corpus twin over every shipped report
   (`test_no_verdict_claims_sequence_proven_anywhere_in_the_corpus`).
   **Amendment 3 (declared-trust visibility) done as a product feature:**
   `FamilyCoverage.declared` + `verdict_display`; the marker rides the
   family note, BOTH matrix renderers' verdict cells, and BOTH headline
   forms ("resolved on paper, declared, not sequence-proven") — pinned by
   `test_declared_order_clears_carry_the_marker_on_every_summary_surface`.
   STANDING_NOTE re-worded (SEQUENCE-PROVEN = RESERVED rung, claimed
   nowhere) and kept html-escape-stable (no quote/apostrophe characters —
   a live lesson: escaped renders broke raw-`in`-section pins).

4. **Epistemic-contract table — DONE.** `epistemic_contract_rows` +
   framing constants in install.py; rendered near the top of
   `render_install_disclosures_md` (validation_report.md) AND the HTML
   `_render_install_section` from the SAME rows/strings. DERIVED
   (structural necessity), DECLARED (technique defaults; authored stages
   listed with their whys per detail), UNKNOWN (no-connection context,
   cross-fragment order, insertability — all named future/P1).

5. **Platform corpus row — DONE.** `details/platform.spec.yaml` authors
   two stages (toes → launch-leg bolts, template labels `bolt +Y{i}`/
   `bolt -Y{i}` expanding to the four launch bolts only — tree bolts
   deliberately unstaged): a DECLARED build strategy (amendment 4), the
   why citing the ToeScrewed wedge fact AND the joist-insertion P1
   sentence. EXACTLY the 2 top toe UNKNOWNs flip to PASS; no other
   verdict moves anywhere in the corpus (the per-detail sweep counters
   pin every other detail byte-identically; platform counter now
   term-PASS×82 / access-PASS×82). Verbatim shipped verdict (+Y top toe
   screw; −Y symmetric):

   > Installation method represented; angled tool path not analyzed
   > against the drawn solid — the declared 30° corridor off end joist's
   > -X cheek face is clear of third-party material; occupants of the
   > corridor in final geometry provably arrive later: bolt +Y0 (at
   > drive(bolt +Y0, bolt_stack)), bolt nut +Y0 (at drive(bolt +Y0,
   > bolt_stack)) — deciding order facts: [authored_sequence] authored
   > sequence: stage 'toe-screw the end joist before bolting the launch
   > legs' precedes stage 'launch-leg thru-bolts after the end joist'
   > (stage 'toe-screw the end joist before bolting the launch legs' why:
   > The end joist drops into the ~3.5" clear gap BETWEEN each launch
   > leg's two thru-bolts (the ToeScrewed wedge fact): with the bolts and
   > nuts in place, the top toe screw's 30° corridors are fouled and the
   > joist itself cannot arrive — bolts-first is unbuildable under the
   > model. The same order is also what covers the joist's own insertion
   > between the bolts; insertion travel itself is not analyzed (P1).)
   > (declared, not sequence-proven) — clear at the DECLARED build order
   > only: the deciding order facts above are declared claims (a declared
   > build strategy, not derived and not sequence-proven), parts are
   > assumed to accrete at their final pose, and insertion travel is not
   > analyzed at any rung (P1); represented axis — the declared 30° angle
   > is not modeled by the drawn solid, and the joint's own members
   > (beam +Y, end joist) are negotiated by the declared technique, not
   > analyzed; 3.00" x 1.00" dia tool envelope

6. **17 UNKNOWN texts re-worded — DONE (generator-level, all 17 stay
   blocking).** Caddy 8: name the sofa arm, "no order fact relates
   drive(…) to the occupants' own events", the v1-core authorable
   surfaces (sequence: stage / technique edge), staging explicitly "a
   FUTURE mechanism, not authorable today", plus "sofa arm participates
   in no connection, so no order fact can be derived for it". Frame 8:
   same §4.1 form naming the mirror-side occupants. Site rod-vs-rung 1:
   names BOTH missing mechanisms — "the occupants belong to another site
   fragment (platform) … no site-level cross-fragment sequencing exists
   in v1 (a CPG v2 site graph would order them)" AND "this epoxy-set
   rod's corridor is its own body's insertion path — insertion travel is
   not analyzed at any rung (P1)". The old "before a construction process
   graph exists (axis 3)" sentence is gone from every emitter, comment,
   and docstring (checks.py, coverage.py, install.py).

7. **CAT-I both halves — DONE.**
   (a) `test_cat_i_opposite_authored_order_flips_the_toes_to_fail`
   (spec-TEXT yaml mutation reversing the stages; shipped spec untouched;
   `sort_keys=False` required — the derived: block is
   declaration-ordered): the 2 flip to FAIL naming the bolts + the
   authored_sequence provenance — UNKNOWN→PASS and UNKNOWN→FAIL both
   proven; authoring is falsifiable, not a waiver channel.
   (b) `test_cat_i_load_half_stage_contradicting_technique_is_a_cycle_error`:
   a stage placing the hung member before the hanger's drives ⇒
   `EventOrderCycleError` naming both claims and both families
   (authored_sequence + technique_default) with the fix-the-wrong-claim
   teaching line.

8. **Reversion probes (Q9 form) — DONE.**
   `test_reversion_probe_removing_the_sequence_returns_the_unknowns`:
   sequence block deleted by spec-TEXT mutation ⇒ the 2 blocking UNKNOWNs
   RETURN with all FOUR properties asserted per pin — class UNKNOWN,
   blocking, occupants named (bolts/nuts), missing order fact named — and
   the false old sentence asserted ABSENT.

9. **Reader surface — DONE (one surface, both destinations).**
   `linearize` (Kahn; ties: declared stage order → connection declaration
   order → part id; byte-stability pinned), `derive_reader_steps` (one
   step per authored stage where staged, else per connection install
   unit; place folds into the first consuming connection's step;
   stage-claimed parts fold into the stage's step; `ReaderStep` is a
   distinct type from `ResolvedStage`/`AuthoredStage` — amendment 5
   unrepresentable-blurring via types), `unordered_parts` (no-order parts
   are REPORTED, never positioned). `src/validation/build_sequence.py`
   `build_sequence_model` = ONE derived content model consumed by
   `render_build_sequence_md` (appended to validation_report.md by
   `Detail._write_build_sequence`, lifecycle-level) and
   `_render_build_sequence_section` (single_detail_report.py HTML).
   Parts print name + BOM label + `ProcessRecord.fab_note` (the one
   cut-plan source); fasteners print the resolved contract's
   `describe()` line (per-field provenance — disclosure content scoped to
   the step); stage steps print the claim + why inline ("authored build
   strategy, declared and checked, never derived"). Nothing hand-typed;
   pinned end-to-end on the trebuchet (13 install units) in
   `test_install_disclosures_reach_the_per_detail_reader_surfaces`.

10. **Re-pins — DONE, every one deliberate to the new truth.** Inventory:
    - `test_install_axes.py` — CAT-E lineage re-derived (member FAIL with
      structural_necessity provenance; foreign→named-UNKNOWN wording;
      ordered-after clear now §4.3-worded); NEW F-7 fixture.
    - `test_sequence_schema.py` — landing test now uses a real part (the
      graph validates names); NEW loud-unknown-name pin.
    - `test_install_sweep.py` — platform {capacity×3, install_access×2} →
      {capacity×3} with the declared-order double qualification asserted;
      lower toe screws asserted NOT to borrow the declared wording; caddy
      /frame §4.1 wording; site: composed toes flip via chain replay,
      rod-vs-rung asserts both named gaps; + CAT-I/Q9/corpus-rung guards.
    - `test_platform_spec.py` / `test_platform_detail.py` /
      `test_foundation_obligation.py` / `test_doc_build_blocked_detail.py`
      — blocking sets → capacity-only.
    - `test_site_model.py` (blocking 3+3 → 3+1, cross-fragment asserted),
      `test_site_model_report.py` (6 → 4 blocking).
    - `test_armchair_caddy_e2e.py` / `test_sit_reach_frame_e2e.py` —
      wording re-pins, verdicts unchanged (still 8+8 blocking UNKNOWNs).
    - `test_coverage_matrix.py` — NEW amendment-3 marker test.
    - Frozen truth: platform.json re-frozen (JUSTIFIED: exactly the two
      toe (check,subject,passed) flips + findings_fp/content_fp; geometry
      fingerprint byte-identical). tree/trolley float-noise and
      rock_anchor stamp-only churn REVERTED per the axes-report
      precedent. `baselines/detail_counts.json` unchanged (no new
      DerivedFacts — event edges deliberately do not enter the derivation
      log in v1-core; evidence projection is a later increment).
    - Presentation golden regenerated twice (after the wording, after the
      amendment-3 marker); final diff: site DIRTY 6→4, rod-vs-rung
      re-worded, platform family UNRESOLVED→PASS, declared markers on the
      family headlines (the site's pooled document-level aggregate counts
      84 = site 42 + standalone platform 42, consistent with that
      surface's existing pooled semantics; the site report itself has 42
      declared-order clears — hand-verified).
    - `serialize.py` — REAL GAP found by the round-trip oracle: the
      `sequence:` block now serializes (`_stage_to_dict`, emitted only
      when present).

## Honesty rules — verified against each
- No order fact was declared to silence a verdict: the platform stage's
  why is the wedge-fact technique defense (F-11), and CAT-I proves the
  opposite authoring FAILs.
- No check weakened: the F-7 softening is the design's stated delta,
  pinned both directions; the mid-event interleave rule keeps the
  conservative presence direction.
- Underdetermined ≠ resolved: undeclared context stays blocking UNKNOWN
  (caddy 8 / frame 8 / site rod unchanged as verdicts).
- Insertability not analyzed at any rung — in every declared-leaning
  clear, the platform why, the epoxy UNKNOWN clause, and the epistemic
  table.
- No geometry moved: platform frozen-truth geom fingerprint
  byte-identical; no PNG re-render triggered.

## Residuals / UNRESOLVED
- **Vocabulary collision (pre-existing):** the contract field
  `FastenerInstallation.stage` ("own_connection") predates amendment 5's
  stage/step split and still prints in `describe()` lines (and therefore
  in Build Sequence drive lines). Not renamed in this task (schema-wide
  rename touching every contract pin); flag for the owner — cheap to
  retire when the field's docstring promise ("the CPG is the real
  sequence vocabulary") is redeemed.
- Event edges carry provenance on themselves but are NOT DerivedFacts /
  evidence-graph nodes (evidence projection is explicitly a later
  increment; axis findings stay on the zero-attribution floor).
- The caddy panel's hand-typed sequence prose (fieldnote/buy lede) still
  ships beside the new derived Build Sequence section — its
  derivation/retirement is the +process increment's CAT-K, per the
  phasing; the derived section itself is fully machine-written.
- `EventGraph.describe_path` retained as a query API though verdicts now
  print deduped `_order_facts` (used by tests).
- Reader-step rendering prints contract `describe()` lines verbatim —
  complete but dense; a friendlier per-step summary is presentation
  polish for the +presentation increment.
- A stale full-suite run from another session was executing in parallel
  during development timings; the final gate below ran on a quiet
  machine.

## Gates
- Import path verified at every run (`<worktree>/.shim/detailgen/__init__.py`).
- Module gates (all green before the final run): test_cpg_core 14 ·
  test_install_axes 21 · test_sequence_schema 30 · loader-adjacent 262 ·
  test_install_sweep 23 · batch (platform_spec/detail, caddy, frame,
  coverage_matrix, doc_build_blocked, foundation) 83 · batch (stool,
  trebuchet, view_coverage, inspector, cl3, ontology, affected_region,
  site_model, site_model_report, consolidated_coverage) 132.
- FULL SUITE (`pytest -n auto -q`, shimmed, import path printed at run
  start): **1166 passed / 3 skipped / 1 xfailed** in 13:51 wall-clock
  (8 workers, quiet machine). Growth master→tip = +50 (1116→1166),
  reconciled per the reviewer's live collect-only counts (review F-3):
  new test_sequence_schema 29 + new test_cpg_core 14 +
  scripts_spec_rewire +2 (the per-test-file guard glob auto-extending
  over BOTH new modules — the +1 over test_cpg_core.py was the item my
  original itemization missed) + install_sweep +3 (CAT-I, Q9, rung
  guard) + install_axes +1 (F-7 fixture) + coverage_matrix +1
  (amendment-3 marker). Intermediate reds during development were all
  triaged into the deliberate re-pin inventory above; none silenced.

## Fix round (review-cpgcore FIX-FIRST, 2026-07-13)

- **F-1 (BLOCKING) — FIXED as the reviewer suggested; no reason found to
  deviate.** The structural-necessity exception's reachability walk is now
  scoped to `FAMILY_TECHNIQUE` edges ONLY (`event_graph.py`, `technique_out`
  / `_technique_reaches`; module docstring updated to match §3.1's own
  wording). An authored stage ordering a member after its own connection's
  drive now leaves BOTH edges in the merged graph and the existing cycle
  check errors loudly naming both claims + both provenance families — the
  teaching message needed no change, exactly as the reviewer predicted.
  The hanger's technique-path suppression is untouched (its pin re-ran
  green). THREE regression pins encode the reviewer's constructions:
  - `test_f1_stage_cannot_silence_structural_necessity_member_after_drive`
    (test_cpg_core.py — construction 1 at graph level);
  - `test_f1_interleave_variant_stage_vs_necessity_still_cycles`
    (test_cpg_core.py — construction 2: the rock-anchor chain shape where
    the interleave drop leaves necessity as the ONLY guard; sanity half
    asserts the conservative direction survives stage-free, cycle half
    asserts the authored silencing attempt errors);
  - `test_f1_authored_stage_cannot_flip_a_member_fail_to_declared_pass`
    (test_install_axes.py — the exact CAT-E member-FAIL fixture end-to-end
    through compile_connections: refuses, never a PASS flip).
  Corpus unaffected as predicted (platform/site stages order drives only):
  the full install_sweep module re-ran green, counters unmoved, and the
  presentation golden is byte-identical.
- **F-2 (nit) — FIXED with a structured flag** (the reviewer's second
  option): `Finding.declared_order: bool = False` (checks.py — additive
  field, positional compatibility preserved; safe against the verdict
  cache because axis-3 clears are deliberately never cached, and
  `findings_fingerprint` hashes (check, subject, passed, detail) only).
  Set by the two axis-3 clear paths (`declared_order=bool(later…)`), so a
  represented-rung clear that leans on later-arrival facts also counts —
  the honest definition, no shipped case differs. Coverage's amendment-3
  count keys on the flag, never on wording; the marker test now pins the
  decoupling both ways (flagged-without-wording counts,
  wording-without-flag does NOT).
- **F-4 (nit) — FIXED:** `Detail._write_build_sequence` is idempotent —
  the section is the last appended to validation_report.md, so a prior
  copy is cut from its heading to EOF before the fresh write; pinned in
  the trebuchet reader-surface test (double re-write ⇒ one section, 13
  install units once).
- **F-3 (report-only) — corrected above:** the +50 growth itemization now
  counts the rewire glob's auto case over test_cpg_core.py.

Fix-round gates (shimmed, import path verified): test_cpg_core **16** ·
test_install_axes **22** · test_coverage_matrix **23** ·
test_install_sweep + test_trebuchet_e2e + test_detail_base +
test_spec_presentation_equiv **60** (golden byte-identical — the flag-keyed
declared counts equal the wording-keyed ones everywhere in the corpus) ·
test_connection + test_sequence_schema **39**. Full suite deliberately NOT
run — the controller owns the merge gate.

## Commits
- `00f9022` cpgcore: event graph + axis-3 reclassification (+ the third
  lift rule discovery)
- `d8c4b63` cpgcore: platform sequence + resolution bridges + reader
  surface + epistemic table
- `a4b211c` cpgcore: sweep re-pins + CAT-I + Q9 probes
- `14b9a00` cpgcore: e2e re-pins + frozen-truth refreeze + serializer gap
  + amendment-3 marker
- `52fe89a` cpgcore: batch triage + golden regen + escape-stable note
- (final) cpgcore: full-gate counts + report
