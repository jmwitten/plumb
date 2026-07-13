# INSTALL — Fastener Installability: design for preventing geometry-valid-but-unbuildable details

**Status:** APPROVED-WITH-AMENDMENTS (owner, 2026-07-10). v1 adversarially reviewed
(review-install-design.md: REVISE → revised); v2 restructured per the owner's
amendments (§Owner sign-off). Implementation arcs get their own adversarial reviews.

## Owner sign-off amendments (2026-07-10, binding)

1. **No global geometric rules.** "Tip must stay inside wood" / "head must sit on a
   surface with air behind it" are true for some installation methods and FALSE for
   through-bolts, pocket screws, countersunk hardware, captive fasteners, and
   intentionally concealed exits. Checks must DERIVE from a **typed fastener
   installation contract carried by the Connection**, representing at minimum:
   installation method · entry face · driven/tool axis · allowed exit condition ·
   required embedment · head condition · tool-clearance envelope · installation stage.
2. **Three separated verdict axes:** geometric termination · static tool access ·
   sequence-aware installability. v1 may prove the first two and must honestly report
   sequence-dependent cases UNKNOWN until the Construction Process Graph exists.
3. **Display idealization is never a waiver.** A toe screw drawn straight is
   acceptable visually ONLY if the actual angled installation semantics are
   represented and drive validation, documentation, and access checks.
4. **The core invariant:** *a connection is not construction-complete merely because
   its hardware exists and penetrates the right members — it must also carry a
   represented, checkable installation method.*
5. **Success criterion:** pocket screws, toe screws, through-bolts, resize-induced
   movement, post-placement obstruction, and sequence-dependent access each receive
   DIFFERENT CORRECT VERDICTS from the SAME general model — not three current
   documents patched.

**Final guardrails (owner, second pass — binding):**

6. **The installability epistemic ladder — never "declared-PASS."** A declared
   installation method is REPRESENTED, not proven. Claims climb exactly:
   `REPRESENTED < GEOMETRY-PROVEN < SEQUENCE-PROVEN`, mirroring the project's
   existing rung discipline (connected < load-path < support-represented <
   adequate). A pocket screw before pocket geometry exists reads **"Installation
   method represented; recess geometry not analyzed"** — never PASS. No surface
   claims a stronger rung than its mechanism proves.
7. **Field-level provenance on resolved contracts.** A ConnectionType default is
   useful but not universally authoritative: every resolved contract field carries
   its source — `connectiontype_default | manufacturer_data | authored_override |
   assumption` — in the derivation log and doc disclosures, so a reviewer can see
   WHICH fields are assumption-grade.
8. **Sequence pragmatically; never fake the rung.** Ship the minimal contract +
   verdict family soon with honest REPRESENTED/UNKNOWN states; the pocket and
   angled-fastener vocabulary raises those cases to GEOMETRY-PROVEN later. The
   standing criterion: a connection cannot claim construction completeness without
   a represented installation method, and cannot claim geometric or sequence
   installability beyond what has actually been proved.

## Motivating failure and the measured class (unchanged from v1, reviewer-confirmed)

Owner-caught: the caddy up screws' heads are embedded mid-plate in the solid 1x6 rail
(the D6 cleat→rail resize kept the cleat-era authored station `upscrew_z=-1.5`, which
had meant "the cleat's bottom face"); `validate()` is CLEAN — overlaps allowlisted, no
installability invariant, and the absence invisible (no coverage family row).

Phase-0 sweep (phase0-sweep-results.md, DONE): **14 no-accessible-head fasteners
across 3 delivered docs, 3 flavors** — caddy x4 (impossible joint), zipline platform
toe screws x6 (real technique is angled; modeled straight and buried, idealization
undeclared), step stool cleat screws x4 (right length, head stationed at the joint
interface instead of the cleat's free face). sit_reach_box / sit_reach_frame clean.
Also verified live: a 1.75in caddy side screw exits the OUTER SHOW FACE by 0.25in and
ships CLEAN today — undeclared-exit is a real, currently-silent defect class.

The three flavors demanding three different verdicts — plus the through-bolt case,
where an exit is REQUIRED, not a defect — is exactly why global rules are wrong and
the contract is the design (owner amendment #1).

## The FastenerInstallation contract

A typed value carried by the **Connection** for its hardware (per fastener or per
role-group), supplied by DEFAULT from the ConnectionType's own semantics and
overridable/refinable in the spec:

```
install:
  method:      driven_straight | pocket_screw | toe_screw | through_bolt
               | captive | <open tag, like ProcessStep.kind>
  entry_face:  part face/datum the tool enters from (derivable per method)
  tool_axis:   the driven axis (per method: straight = shank axis;
               toe/pocket = declared angle off the entry face)
  exit:        none | concealed_exit(face-set) | through_exit_required
  embedment:   min bite into the anchor member (or `through`)
  head:        proud | flush_countersunk | recessed_in_pocket | nut_and_washer
  tool_envelope: {length, dia} — defaults per method, overridable per connection,
               the used value printed in every verdict
  stage:       install-step reference (v1: relative to own connection;
               real sequence = Construction Process Graph)
```

**Semantics, not annotation:** the contract DRIVES validation, documentation prose,
and access checks. The rendered solid may simplify (a toe screw drawn straight) only
as a flagged presentation fact that REFERENCES the contract — never as a waiver
(owner amendment #3). ConnectionType defaults make migration honest: `toe_screwed`'s
default contract IS `method: toe_screw` with an angled tool axis off the exposed
member face — the type finally says machine-readably what its docstring always said.
`cleat_screwed`/`rail_cap_screwed`/`butt_screwed` default to `driven_straight` with
entry on the through-member's free face; `bolted_clamp`/hex-bolt stacks default to
`through_bolt` with `through_exit_required` + `nut_and_washer` (two-sided access).

**Enforcement of the core invariant (owner amendment #4):** hardware without a
resolvable installation contract caps the connection's Construction-completeness
claim — the new family reads `UNKNOWN — NO INSTALLATION METHOD REPRESENTED` for that
joint and blocks CLEAN. Existing specs inherit type defaults, so the day-one state is
honest, not red noise. Every resolved field carries provenance
(`connectiontype_default | manufacturer_data | authored_override | assumption` —
owner guardrail #7), and every verdict speaks its rung on the installability ladder
`REPRESENTED < GEOMETRY-PROVEN < SEQUENCE-PROVEN` (guardrail #6): axis-1/-2 results
against modeled geometry are GEOMETRY-PROVEN; results resting on declared-but-
unmodeled conditions (pocket voids, angled axes) are REPRESENTED, worded as
"represented; <X> not analyzed"; axis-3 claims are SEQUENCE-PROVEN and exist only
after the Construction Process Graph.

## Verdict axes (owner amendment #2)

1. **Geometric termination** — the shank/bolt path judged against the CONTRACT's exit
   condition and embedment: an undeclared face exit FAILs naming the face (show faces
   called out); a `through_exit_required` bolt with NO exit FAILs; a declared
   concealed exit PASSes with the disclosure in the doc; embedment below the declared
   minimum FAILs.
2. **Static tool access** — the tool envelope swept along the CONTRACT's tool axis
   from the entry face, against final geometry: entry face buried in solid material
   FAILs (the caddy class); obstruction by a party to the SAME connection FAILs;
   obstruction by any foreign part → `UNKNOWN — install-order dependent` (no
   cross-connection order exists today — reviewer-verified); `through_bolt` checks
   BOTH sides (driver side + nut side).
3. **Sequence-aware installability** — axis 2 re-evaluated against the partial
   assembly at the contract's `stage`; Construction Process Graph territory. v1
   reports it UNKNOWN wherever it is the deciding question, by name.

Head/tip identification comes from the fastener component's own head datum +
placement (a fastener type without one is a loud teaching error). Pocket/countersink
head conditions judge against MODELED voids where vocabulary exists, and against the
declared head condition (disclosed in the doc) where it does not yet.

## Named vocabulary work orders (vocabulary-gap directive)

1. **`counterbore`/`pocket` partial-depth step kind** — `bore` folds full-through
   only (reviewer-verified); a pocket-screwed or counterbored head needs a modeled
   void to upgrade from declared-condition to geometry-proven.
2. **Angled fastener placement** — toe/pocket tool axes need a first-class angled
   representation (today's screws are axis-aligned solids); until it lands, the
   contract's angle drives checks/docs and the drawn solid carries the flagged
   simplification.
3. **Derived fastener stations** (Phase 2 below) — stations derived from the joint +
   contract (entry face + embedment), killing authored-coordinate rot at the root.

## Phases

**Phase 0 — DONE except fix arcs:** sweep (done, artifact committed) · reviewer
checklist line ("narrate installing every fastener: head, path, step") · retro rows
(caddy impossible-joint; D6 station rot; undeclared idealization; station-at-
interface) · fix arcs queued on owner: caddy pocket joint (contract `pocket_screw` +
vocab #1 for the geometry-proven grade), stool station move (trivial), platform
toe-screw contract adoption.

**Phase 1 — INSTALL v1:** coverage family `Fastener installability` (auto-UNKNOWN in
every doc's matrix, day one) → contract schema + ConnectionType default contracts →
axis-1 (termination) and axis-2 (static access) checks driven by contracts → the
Phase-0 sweep re-lands as pytest pinned to per-flavor expected verdicts. Verdict
language: this makes the class impossible to ship SILENTLY; Phase 2 makes it
impossible to AUTHOR silently (the distinction stays crisp).

**Phase 2 — derived stations (CL v2 queue, with R1-R3 + R-SUBSTRATE):** stations
derived from joint + contract; authored stations remain legal but flagged
`authored-station` in the derivation log. REPLAY: the D6 resize under derivation
raises a TEACHING ERROR (a 2in straight screw cannot span from the 5.5in rail's free
face to the top) — forcing the pocket-joint decision at compile time; prevention =
forced decision, not silent relocation.

**Phase 3 — sequence-aware (Construction Process Graph roadmap slot):** axis-3 real
(partial-assembly access at each contract's stage), part insertability (P1), global
install order feeding `stage`. Phase 1's named UNKNOWNs are the bridge.

## Conceptual acceptance tests (owner amendment #5 — one general model, different correct verdicts)

- **CAT-A pocket screw** (the caddy fix): contract `pocket_screw`, entry = rail inner
  face, head `recessed_in_pocket` → termination PASS (bite into the top), access
  checked along the ANGLED axis from the inner face; head condition reads
  "Installation method represented; recess geometry not analyzed" now (REPRESENTED
  rung), rising to GEOMETRY-PROVEN once vocab #1 models the void. The same joint with
  `driven_straight` (today's declaration) FAILs axis 2 — CAT-1's would-have-caught
  property is preserved inside the general model.
- **CAT-B toe screw** (platform): `toe_screwed`'s default contract = angled axis off
  the exposed joist face → checks and doc prose run on the ANGLED semantics; the
  straight drawn solid is a flagged display simplification referencing the contract
  (never a waiver); the 3.5in-gap driver question is judged against the declared
  tool envelope, honestly.
- **CAT-C through-bolt** (zipline bolted_clamp): `through_exit_required` +
  `nut_and_washer` → the exit is REQUIRED (no-exit FAILs), both sides get access
  checks. The inverse verdict of CAT-A/B from the same checker — the direct proof
  that global tip/head rules were the wrong shape.
- **CAT-D resize-induced movement** (the D6 REPLAY): under derived stations the
  resize errors loudly at compile; under authored stations axis-2 FAILs post-hoc.
  Both paths speak; neither is silent.
- **CAT-E obstruction introduced after placement:** add a new part into a
  previously-clear tool corridor in a revision — axis 2 flips (same-connection ⇒
  FAIL; foreign ⇒ named UNKNOWN) and the revision diff's affected region includes the
  flip (ties into revision semantics: a placement edit that breaks someone else's
  installability is surfaced, not discovered on site).
- **CAT-F sequence-dependent access:** a corridor blocked by a part whose contract
  `stage` is LATER → v1: `UNKNOWN — install-order dependent`, naming the blocker;
  Phase 3 resolves it to PASS. The mirror (blocker installs earlier) FAILs in
  Phase 3. Success = the UNKNOWN→PASS/FAIL split happens by mechanism, not prose.

## What this deliberately does NOT do
- No torque/swing-arc/two-hands modeling — a declared tool envelope along a declared
  axis is the v1 mechanism, and verdicts claim exactly that much.
- No silent reclassification: docs regenerate with the new family row; the caddy
  reads FAIL and the platform reads per-contract until their fix arcs run — the
  truthful state of the delivered artifacts.
- No patch-and-declare-victory: the three shipped defects become pinned regression
  verdicts inside the general model (owner amendment #5), not one-off fixes.

## Why this fits the architecture
The contract is Construction Language surface (declared intent) lowered into
Construction Graph facts (axes 1-2) and Construction Process Graph facts (axis 3);
the coverage family is the Presentation Graph's honest reader-facing row; derived
stations are the compiler doing what it exists to do. Every mechanism traces to an
observed failure (14 shipped fasteners, three flavors, one live-verified silent
show-face breach) or an owner/reviewer adversarial probe.
