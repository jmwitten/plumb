# Adversarial review — INSTALL axes branch, HONESTY / RUNG-WORDING lens

**Tree under test:** worktree `wt-install-axes`, branch `sdd/install-axes`, tip `d8737f4` (contains master `5feee8a`).
**Reviewer stance:** fresh, adversarial, honesty/rung-wording only. Import path verified before every run (`detailgen.__file__` → `<worktree>/.shim/detailgen/__init__.py`). Read-only on the tree; all synthetic probes built in memory; targeted tests only (controller runs the full suite).

**Verdict: FIX-FIRST** — one CONFIRMED verdict-wording/mechanism overclaim (F1) plus one binding-guardrail doc-disclosure gap the report claims is satisfied (F2). Everything else on the attack list held up under live probing; the branch's honesty machinery is otherwise excellent.

---

## What I probed (methods)

- Enumerated every verdict string `install.py` can emit (all emit sites read line-by-line: `_unknown_pair`, `_termination_represented`, `_termination_shank` ×7 branches, `_access_shank` ×4 branches, `_blocked_finding` ×2, `_access_angled` ×3, `_head_tip` teaching error).
- Compiled **caddy**, **platform**, **sit_reach_frame**, **trebuchet** in the worktree; confirmed `render()` refuses on all three red details (caddy 16 FAIL + 8 UNKNOWN; frame 8 UNKNOWN, 0 FAIL; trebuchet 18 FAIL) while `render_documentation()` writes; read the four rendered `validation_report.md` + matrices.
- Printed live verdict strings off the platform (hanger ordered-after PASS, toe-screw REPRESENTED pair, through-bolt two-sided pair).
- Built two in-memory synthetic assemblies to attack `concealed_exit` (below).
- Ran `tests/test_install_axes.py` (12 passed) and `tests/test_install_sweep.py` (19 passed) single-module in the worktree.
- Grepped the whole branch diff for UNKNOWN-phrased-as-safe / FAIL-phrased-as-cosmetic wording.

---

## FINDINGS

### F1 — CONFIRMED (fix before merge): `concealed_exit` PASSes a breach through a face NOT in the declared face-set, and the wording claims it is "DECLARED"

`_termination_shank` (`install.py:495-505`): for `cond == "concealed_exit"` a breach PASSes unconditionally — the declared `exit.faces` set is **never matched** against the measured exit, unlike `through_exit_required` directly below it, which has a wrong-member FAIL (`install.py:522-527`).

Live in-memory probe (rail 0–88.9 mm, top 88.9–177.8 mm, 8 in screw driven +Z, contract authored `exit=concealed_exit via <rail>.free_face`):

```
[PASS] install_termination: probe joint: long screw — exits top's +Z face at
(3.00", 0.75", 7.00") by 1.00" — a DECLARED concealed exit (declared faces:
lumber-0.free_face); a disclosed design fact, not a defect; ... (GEOMETRY-PROVEN
against modeled geometry); 6.00" x 1.00" dia tool envelope
```

The shank exits **top** (`lumber-1`); the declaration names only **rail** (`lumber-0`). The verdict asserts "a DECLARED concealed exit … not a defect" and stamps GEOMETRY-PROVEN — a proof-shaped claim about a match the checker never performed. This is the motivating defect class re-opened under a contract: the design's own phase-0 evidence is a live show-face breach ("undeclared-exit is a real, currently-silent defect class"), and one `concealed_exit` declaration on any single face currently waives exit checking on **every face of every member** — a waiver by side effect, which amendment #3's spirit (declaration is never a waiver of what it doesn't declare) forbids.

Mitigations that keep this out of REVISE territory: no shipped spec uses `concealed_exit` (grep: spec-surface tests only); the loader refuses a face-set-less `concealed_exit`; and the verdict prints both the actual face and the declared set, so a forensic reader could spot the mismatch. But the sentence affirmatively asserts the opposite of what was checked.

**Fix shape (small):** part-level match exactly like the through-exit rule — `deepest.part.id in {x.part for x in c.exit.faces}` ⇒ current PASS wording; else FAIL "exit through an UNDECLARED member: the shank breaches X, but the declared concealed faces are Y" (or honest UNKNOWN if descriptor-to-face matching is deemed unavailable — but the part-level half is checkable today with data already in hand). Pin with a CAT-style test (the inverse twin of the existing wrong-member through-bolt test).

### F2 — CONFIRMED (fix or explicitly queue with owner sign-off): guardrail #7's doc-disclosure half does not reach any per-detail reader surface, while the branch report claims it does

Guardrail #7 (binding): field provenance appears "in the derivation log **and doc disclosures**". The report's Inherited-review-items section claims `_fact_line` makes assumption sub-lines "reach doc disclosures per guardrail #7". Measured on all four rendered docs:

- **No `install contract` fact prints in any of the four `validation_report.md`s** (caddy, platform, sit_reach_frame, trebuchet — grep: zero hits). The contract facts exist in the full derivation log (verified live: 34 on the platform, each with per-field `[connectiontype_default]`/`[assumption]` stamps and the half-length/toe-angle assumption notes — the mechanism is real and correct), but the doc's per-connection sampling cap cuts each connection's fact list first-N, and the install-contract facts sit past the cap on **every** shipped detail. The disclosure mechanism exists; its content never survives to the page.
- **No per-fastener axis verdict text prints in any per-detail md or single-detail HTML** (`single_detail_report.py` has no blocking-findings block — grep zero; the site-level `consolidated_report.py` open-findings block DOES print them in full, verified in the committed golden). So the trebuchet's reader-facing doc says "Fastener installability: FAIL … 18 failures" in the headline and matrix — loud and honest at family level — while the only per-screw lines a reader sees are hardware-presence "**PASS** butt screw +X front 0 — present", and the `[assumption]`-grade minimum, the measured bites, and the envelope values are reachable only in `evidence_graph.json`/the report object.

Nothing ships **silently** — the family verdict blocks and headlines correctly, which is the branch's stated v1 bar. But the branch cannot simultaneously claim guardrail #7's doc-disclosure clause is satisfied. Fix shape: a lifecycle-level "Blocking findings" section appended to `validation_report.md` exactly the way `_write_coverage_matrix` is appended (framework property, not per-detail authoring), and/or sample install-contract facts ahead of the cap. If deferred, the report must say guardrail #7 is met in the derivation log and machine surfaces only, with the doc half queued — not "reaches doc disclosures".

### F3 — Minor wording (non-blocking): bare GEOMETRY-PROVEN stamp on the ordered-after clearance PASS

Live string (platform hanger header screw):

```
[PASS] install_access: … clear tool corridor along the shank axis (corridor: clear);
joist 0, joist 0+Y joist screw 0, joist 0+Y joist screw 1 occupy the corridor in
final geometry but this connection's own declared order installs them after this
fastener (stage: own_connection) (GEOMETRY-PROVEN against modeled geometry). …
```

The geometric content (who occupies the corridor) is proven; the **deciding premise** — that the occupants arrive later — is a *declared* order (type-authored `installed_before` edges, confidence `inferred` in the derivation log), i.e. sequence-grade knowledge on a ladder whose sequence rung is explicitly axis-3. The disclosure is in-sentence and names the mechanism, so this is not a silent overclaim; but a strict guardrail-#6 reading says the trailing bare rung tag claims more than the mechanism proves. Suggested: qualify — e.g. "corridor clear at this fastener's own install step (occupants' arrival per the connection's DECLARED order — geometry proven, order declared)". The mechanism itself I judge honest and design-sanctioned: the design's `stage` field gives exactly own-connection v1 semantics, the report defends the deviation from "party ⇒ FAIL" openly, and the alternative (FAILing the hanger technique) would be a false alarm the type's real technique knowledge refutes.

### F4 — Advisory: declared recess/countersink accepts arbitrary burial depth as REPRESENTED

A `head: flush_countersunk` declaration would convert even the caddy's 4 in mid-plate burial into a REPRESENTED pass. The wording prints the measured depth and "judged as declared, not geometry-proven", and an authored override would carry visible `authored_override` provenance — so this is design-sanctioned v1 behavior, disclosed. Worth a sanity ceiling when vocab #1 lands (a countersink deeper than the head's plausible recess is physically absurd and could FAIL even as-declared).

---

## Attack results that came back clean

**(1) Verdict-string enumeration — rung-honest.** Every REPRESENTED-rung result leads with "Installation method represented; <angled shank path | angled tool path | recess geometry> not analyzed" — never a bare PASS (verified in source and live). GEOMETRY-PROVEN stamps appear only on shank-mode measured results, and `_access_shank` correctly **drops** the stamp when a represented note is present (`install.py:703`). Every UNKNOWN ("not analyzable" ×5 shapes, "install-order dependent") is `verdict=UNKNOWN_VERDICT`, which `Finding.__post_init__` forces non-passing and `blocking` — UNKNOWN is structurally never safe. The foreign-blocker UNKNOWN names every blocker and its owning connections and states the axis-3 reason verbatim. FAIL wordings state defects as defects ("impossible joint as declared", "station-not-face", "REQUIRED through-exit absent"); the embedment verdict prints the minimum's provenance `[assumption]` live. The only proof-shaped overclaim found is F1.

**(2) Ordered-after disclosure — honest mechanism, not a waiver.** The `FaceMountHanger.edges()` addition is true technique knowledge (hanger to header first, joist drops in after), carries an explanatory comment at the source (`connection.py:1202-1209`), and is doc-visible: the edges land as derivation facts (`edge structural_screw-N -[installed_before]-> lumber-2 (FaceMountHanger.edges)`, confidence `inferred`) and DO print in rendered docs (seen live in the sit_reach_frame report for the analogous RailCapScrewed edges). Abuse surface is narrow by construction: `_Scope.order` filters to the connection's **own** edges only, specs cannot author `installed_before` edges (no spec surface exists — verified), so silencing axis-2 requires a code change to a reviewed ConnectionType, and every use is disclosed in the verdict sentence. There is no explicit "do not add edges to silence axis-2" comment in `_classify`/`edges()` — advisory: add one line; the structural guard is real either way. Rung tension is F3.

**(3) Evidence-graph de-attribution — honest and documented.** `_link_finding` (`evidence.py:552`) drops only `concerns` edges for the two axis kinds, with a docstring that states the exact soundness hazard (partial attribution vs. neighborhood-dependent verdicts, caught live by `test_affected_region`) and the revisit condition; `install_method` keeps attribution. The finding nodes, family rollups, and coverage rows all still exist — the Inspector's per-part panel merges the assembly-wide coverage matrix (`Verification.build`), so a reader inspecting a fastener still sees "Fastener installability: FAIL/UNRESOLVED" against the part, and the honesty-merge sanity check would explode if the family claim diverged. Residual (acceptable, documented): a fastener's *part-scoped findings list* no longer contains its own axis verdicts; the reader must take the family row. The affected-region floor (45 → 209) is coarse-but-sound in the right direction.

**(4) Doc disclosures — honest at family level everywhere; the caddy/frame/trebuchet gate split verified live.** `render()` refused all three red details naming kinds and verdict words; `render_documentation()` wrote full docs whose headline **leads** with the honest family verdict ("Fastener installability: FAIL … (internal verdict: 18 FAILURES)" / "UNKNOWN — UNRESOLVED"), and the appended matrix carries the new install epistemic-ladder preamble ("A represented installation method is a declared claim, not proof the fastener can be driven; sequence-dependent access is NOT ANALYZED until a construction process graph exists"). The site consolidated doc prints the full verdict texts (both toe UNKNOWNs, the composed rod-vs-rung finding, envelope values, rung notes) in its open-findings block — verified in the committed golden. The gap is per-detail surfaces only (F2).

**(5) UNKNOWN-as-safe / FAIL-as-cosmetic sweep — none found.** Branch-diff grep over prose/wording: the only "not a defect" phrasing is the concealed-exit disclosure (design-sanctioned for a *correctly matched* declaration; its unmatched half is F1). `checks.py`/`coverage.py` diffs strengthen blocking language. The e2e re-pins assert exact red states with specific messages so unrelated regressions can't hide under expected red (verified in `test_trebuchet_e2e.py`: exact 18, message-asserted, `blocking == failures`). Pre-existing nit outside this branch's scope: `single_detail_report.py:916` applies CSS class `status-ok` to the headline `<dd>` even when the headline says FAIL — the site stylesheet neutralizes it (`tb-verdict dd.status-ok{color:inherit}`), and it predates this branch.

**Report-vs-tree spot-checks.** Per-detail verdict table matches live runs (caddy 24 blocking incl. 12 embedment FAILs + 4 buried + 8 sofa-arm UNKNOWNs; platform 2 install UNKNOWNs + 3 capacity; frame 8 UNKNOWN / 0 FAIL; trebuchet 18 FAIL / 0 UNKNOWN). The trebuchet-handoff section's claim that the branch touches nothing under `details/` verified via `git diff --name-only 5feee8a...d8737f4`. Both new test modules pass in the worktree.

---

## Verdict

**FIX-FIRST.**

1. **F1 (required):** enforce (at minimum part-level) the `concealed_exit` face-set match, or degrade the unmatched-breach verdict to an honest FAIL/UNKNOWN that names the mismatch — and pin it. The current PASS wording asserts a declaration-match the mechanism never checks, on the branch whose entire purpose is that class.
2. **F2 (required, or explicitly re-scoped):** give the per-detail reader surface the blocking install verdicts + contract provenance (lifecycle append, like the matrix), **or** correct the report's guardrail-#7 claim to "derivation log + machine surfaces; doc half queued" and queue it.
3. F3/F4 and the two advisories are non-blocking; fold F3's wording qualifier in if F1 is being touched anyway.

Everything else — the verdict-axis separation, the rung wording discipline, the disclosed ordered-after mechanism, the de-attribution soundness call, the honest-red re-pins, and the gate split — survived adversarial probing and is high quality.
