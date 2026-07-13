# Adversarial review — sdd/install-schema (SEMANTICS/HONESTY lens)

**Branch:** sdd/install-schema @ a731952 (base d57bf8a; master 353224a merged in
at 58ea2e0). **Reviewer:** fresh semantics reviewer, independent reproduction
only — every claim below was re-derived with my own throwaway probes (scratchpad
`probe1..4_*.py`), never taken from the task report. Import path verified before
every run (`detailgen.__file__` → worktree `.shim`); pristine-master probes ran
in the main checkout with no PYTHONPATH.

## VERDICT: MERGE

No blocking findings. The contract layer says only true things, stamps every
field with its source, discloses every assumption it ships, and represents
without judging — the owner amendments and both guardrails are honored in the
mechanism, not just the prose. Three non-blocking nits below.

## Independently observed evidence (by attack)

### 1. Per-type default contracts vs each type's own docstring — VERIFIED, all 8

Read every ConnectionType docstring against its `install_contract` and probed
the four flagged spots on real compiled details:

- **(a) cleat_screwed through-member = parts[0] (the cleat), both caddy
  consumers.** Compiled `armchair_caddy.spec.yaml`: all 4 cleat_screwed joints
  — both the up-into-top pair AND the side-into-side pair — resolve
  `entry_face = <registration rail ±X>.free_face`, i.e. the cleat, matching the
  docstring's "screws driven through the cleat's FACE into the member's FACE"
  for both orientations. The `free_face` descriptor is joint-relative
  ("opposite the joint interface", EntryFace docstring) and each
  ResolvedInstallation carries its owning connection label, so the SAME rail
  having two different free faces in its two connections is coherent data for
  the axes branch, not an ambiguity. The contract is the honest TARGET state;
  the shipped buried-head defect stays for axis-2 to FAIL (nothing here
  declares it fixed).
- **(b) bolted_clamp head side = plates[0].** Geometrically verified on all 10
  shipped clamps (8 platform leg/beam + tree bolts, 2 rock-anchor leg
  thru-bolts) by projecting washer centers and plate extents onto the declared
  clamp axis: the head washer sits at/just outside plates[0]'s outer face
  (e.g. platform: washer @458.2 vs leg face 457.2) and the nut washer outside
  plates[-1] — head/nut sides in every contract match built geometry, and
  `exit.faces` names the true nut side. The docstring's hardware order
  `[bolt, head_washer, nut_washer, nut]` is what `_unpack` role-guards.
- **(c) toe_screwed 30°.** The resolved platform contracts stamp `tool_axis`
  AND `embedment` `[assumption]`; the derivation-log fact prints
  `tool_axis=angled 30° off the entry face (drawn solid is straight — display
  idealization, verdicts REPRESENTED-rung) [assumption]` and the fact's
  assumptions carry the explicit technique note ("typical technique
  (assumption, not manufacturer data)"). Entry member verified = the hung end
  joist (`'end joist'.exposed_face`), per the docstring's technique.
- **(d) standoff_post_base `()`.** On the platform's 3 compiled
  standoff_post_base connections: hardware is exactly one `PostBase`,
  `is_fastener` False, `install_contract()` returns `()` — the "nothing to
  contract" statement is TRUE of the modeled hardware (anchor/post fasteners
  live on the PostBase BOM line per its own docstring), and `()` vs the base
  `None` produces no finding vs blocking-UNKNOWN respectively (probed both).

### 2. Guardrail #7 field-level provenance — VERIFIED

- Compiled all Connection-bearing shipped specs: every one of the 32
  install-contract derivation facts prints ALL 8 contract fields, each with its
  `[source]`, in canonical order; assumption-grade fields (`embedment`
  half-length, toe `tool_axis`, epoxy `embedment=no declared minimum`) read
  `[assumption]` inline in the fact the doc renderer prints verbatim
  (`report.py:_fact_line`).
- Authored-override stamping proved end-to-end with my own synthetic spec (step
  stool + `install: {role: cleat_screws, method: pocket_screw, angle: 15,
  head: recessed_in_pocket, embedment: 1 in}`): exactly
  {method, tool_axis, head, embedment} stamp `authored_override`, the rest keep
  `connectiontype_default`; authored angle 15 → `axis_idealized=True`;
  confidence stays `inferred` (not all fields authored) per the stated rule.

### 3. No fake data / never declared-PASS — VERIFIED

- `METHOD_TOOL_ENVELOPES` is empty at source (installation.py:140) and nothing
  else writes it; every verdict-facing envelope is the printable module default
  (`6.00" x 1.00" dia`), named in every log line.
- Half-under-head-length embedment is stamped `assumption` AND ships its
  explanatory note ("rule of thumb, NOT derived from joint geometry") into the
  DerivedFact assumptions; a length-less component yields `None` + its own note
  (code path read; no fabricated number exists).
- Nothing in the branch emits a PASS: the only Finding it can emit is the
  blocking UNKNOWN. The coverage row stays `UNKNOWN — NOT ANALYZED` even for
  the caddy whose 4 contracts all resolve — representation is not proof
  (guardrail #6 honored by mechanism).

### 4. Core invariant — REPRODUCED + all-9 sweep CLEAN

- My own contract-less `ConnectionType` subclass with one StructuralScrew:
  exactly one `install_method` Finding, `verdict=UNKNOWN`, `blocking=True`,
  detail starting `UNKNOWN — NO INSTALLATION METHOD REPRESENTED`;
  `require_clean()` raises on it; `KIND_TO_FAMILY["install_method"] ==
  "Fastener installability"`. Authoring `{"": {"method": ...}}` on the same
  joint covers it (finding gone), with un-authored fields honestly
  `not declared [assumption]`.
- All 9 standalone shipped specs compile + validate with ZERO `install_method`
  findings; platform's `ok=False` is byte-identical blocking sets master vs
  branch (3 pre-existing `foundation_capacity` UNKNOWNs — nothing new, nothing
  silenced).
- Backstop verified: tree_attachment (lag screws, zero Connections → invariant
  can't see them) still reads family row `UNKNOWN — NOT ANALYZED` — the
  connection-scoped invariant plus the family's auto-UNKNOWN leave no honest
  gap.

### 5. Amendment #3 (idealization never a waiver) — VERIFIED

`axis_idealized=True` on every angled axis (type default and authored — the
compiler sets it unconditionally for angle>0, with the comment saying it flips
only when the compiler can PROVE the solid matches). Grep of src/: zero
consumers besides the producers and `describe()` — nothing branches on the flag
to skip or soften anything; its only observable effect is the REPRESENTED-rung
disclosure text.

### 6. Open descriptor honesty — VERIFIED

`EntryFace` docstring (installation.py:153-167) states the descriptor set is
open and "an unknown descriptor degrades a verdict to honest UNKNOWN, never a
guess"; the module docstring's consumption-surface section repeats it
normatively. No code in this branch maps a descriptor to geometry (no
solid/bbox reads anywhere in the install path) — nothing pretends geometry.

### 7. Owner-amendment sweep — CLEAN

No global geometric rules (the branch emits no geometric verdicts at all); no
verdict silencing (`EXPECT_CHECKS` excludes all install kinds, so an
installability verdict cannot be pinned away; no allowlist edits); frozen-truth
re-freeze verified at JSON level — `findings`/`by_kind`/`findings_fp`/`bom`/`ok`
byte-identical for both platform and rock_anchor, only
`counts.derivation_log` (688→722, 100→104) and the content fingerprints moved;
the rock_anchor EVOLVED promotion is documented in the script with the
imperative-testimony pointer intact. (`details/_probe_site.spec.yaml` matching
`install:` is an UNTRACKED sibling-reviewer probe file, not branch content —
"no shipped spec authors an install block" holds for tracked specs.)

## Non-blocking findings

- **N1 (minor, report accuracy)** — task-install-schema-report.md §Gates says
  geom_fingerprint churn is "1e-11..1e-14 float noise vs the 1e-6 oracle". My
  measurement of the platform re-freeze: max ABSOLUTE diff 1.19e-7 (on the
  trunk's 1.44e8 mm³ volume → relative 8e-16) and max RELATIVE diff 1.1e-5 (a
  near-zero bbox coordinate). The substantive claim — float noise, no real
  geometry change, accepted by the oracle — is true; the quoted magnitudes
  don't correspond to any single metric. Suggest a one-line correction next
  time the report is touched.
- **N2 (minor, future-proofing)** — the UNKNOWN finding's detail text
  (connection.py, `_resolve_install` uncovered branch) hard-codes "the
  '<type>' type declares no default contract and the spec authors no
  resolvable install: override". Accurate for every path reachable today (all
  8 types either role-guard full coverage or return `()`), but the uncovered
  branch also runs after a groups-not-None resolution — a FUTURE type whose
  role groups under-cover its fastener hardware would fire this finding with a
  false explanation. Fold a wording generalization into the axes branch.
- **N3 (observation)** — `DerivedFact.assumptions` carries the WHY notes
  (half-length rule of thumb, toe-technique caveat) but the doc renderer's
  `_fact_line` prints only confidence + fact + rule. The per-field
  `[assumption]` tags ARE in the printed fact (guardrail #7's "see WHICH
  fields" is satisfied in docs); the explanatory notes surface only
  programmatically. Fine for this branch — flagging so the doc-disclosure work
  in the axes arc doesn't forget the notes exist.

## Attack-status one-liners

1. Per-type defaults vs docstrings: VERIFIED all 8 (caddy both consumers ✓,
   bolted_clamp head side geometrically ✓ on 10 clamps, toe 30° stamped +
   disclosed ✓, standoff `()` true of real hardware ✓).
2. Guardrail #7: VERIFIED — every field, every source, in log + doc line;
   authored stamping proved via synthetic spec.
3. No fake data: VERIFIED — empty envelope map, assumption-stamped heuristics
   with notes, no PASS emitted anywhere.
4. Core invariant: REPRODUCED (blocks require_clean, family-mapped); all 9
   shipped specs clean of it; platform ok=False pre-existing (identical sets).
5. Amendment #3: VERIFIED — flag always True for angled, zero waiver consumers.
6. Open descriptors: VERIFIED — degrade-to-UNKNOWN documented; no geometry
   pretended.
7. Forbidden-by-amendment sweep: CLEAN (plus frozen-truth diff independently
   verified at JSON level).
