# STEPDOC/CPG +staging implementation report

Date: 2026-07-13
Branch: `codex/stepdoc-staging`
Status: **COMPLETE; gated, merged @`6f4f131`, and delivered**

## Delivered semantics

- Typed staging authoring for explicit subassemblies and whole-detail
  assemblies, plus `bench_then_set` sugar.
- Compiler resolution onto the shared construction-process graph.
- Join events and R-1: every bench placement/drive event precedes its unit's
  join without inventing order between separate units.
- Presence rules distinguishing bench-frame membership, undeclared context,
  explicit `in_situ`, and declared-trust context absence.
- Loud validation for duplicate/reserved units, bad membership, null labels or
  rationales, and explicit cross-frame hardware claims.
- Axis-3 installability classification against the staged event graph, with
  declared-order epistemic wording preserved.
- Derived reader steps for bench work and joins, retaining authored stage and
  staging rationales without hand-typed sequence claims.

## Corpus rows

- `details/armchair_caddy.spec.yaml`: two rail/top bench units joined around
  the existing sofa-arm context. Eight prior install-order UNKNOWNs now PASS
  for the declared build strategy, visibly relying on DECLARED TRUST where the
  sofa arm has no connection event.
- `details/sit_reach_frame.spec.yaml`: left and right frames are built on the
  bench and joined by the rails. Eight prior install-order UNKNOWNs now PASS;
  explicit in-situ construction retains the required symmetric blockers.

## Reader/document work

- Exact caddy and frame stations, tools, consumables, hardware-head treatment,
  safe bore guidance, use gates, and derived build sequence were added to the
  model-backed document surface.
- Caddy side-board wording now states that the side boards are flush with the
  top ends while their inner faces clear the sofa arm by 1 inch; geometry did
  not change.
- Existing-context viewer labels no longer leak unrelated material names.
- The consolidated document golden was regenerated for the new staging
  epistemic rows and truthful derived-sequence introduction.

## Verification

- Focused semantic/document suite before the gate: 173 passing.
- Golden equivalence after regeneration: 1 passing.
- Final binding gate: **1337 passed, 3 skipped, 1 xfailed in 1183.90s**.
- Geometry hashes remained:
  - armchair caddy: `511f77d74c211a3a777e2388a520c54a20d15746373c2de70633be40b14a3a3d`
  - sit-and-reach frame: `6c18040b3765d282bd9fd9ea17f1eb1207ae69b24b38fff90282334c8f41b5ed`
- Fresh adversarial confirmation: CLEAN after the fixes recorded in
  `review-staging.md`.

## Honest residuals

- Staging establishes declared build order and presence; it does not analyze
  insertion travel, cure, capacity, or stability.
- The frame remains a prototype and must not be used for scored or
  unsupervised testing until its stated use blockers are resolved.
- Process/cure semantics and grouped interactive presentation remain the
  separately approved later increments.

## Delivery

- Vault caddy:
  `/Users/joelwitten/Code/JoelBrain/05_Attachments/Organized/Armchair Caddy Drawings/Armchair Caddy Build Document (model-backed) 2026-07-13.html`
- Vault frame:
  `/Users/joelwitten/Code/JoelBrain/05_Attachments/Organized/Sit-and-Reach Box Drawings/Sit-and-Reach Box 2x4 Frame Build Document (model-backed) 2026-07-13.html`
- Downloads caddy:
  `/Users/joelwitten/Downloads/Build Documents/Armchair Caddy Build Document.html`
- Downloads frame:
  `/Users/joelwitten/Downloads/Build Documents/Sit-and-Reach Box (2x4 Frame) Build Document.html`

The source and both delivered copies were checked byte-for-byte. Existing view
PNGs were checksum-verified unchanged after regeneration.
