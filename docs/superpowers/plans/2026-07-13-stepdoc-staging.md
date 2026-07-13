# STEPDOC/CPG +Staging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the approved subassembly/frame/join staging increment so the armchair caddy and sit-reach frame resolve their 8+8 install-order UNKNOWNs for the declared, auditable reasons in CAT-G and CAT-H.

**Architecture:** Extend the existing `sequence:` authoring surface with typed staging declarations, resolve those declarations to built part ids, and normalize both explicit subassemblies and whole-detail `bench_then_set` sugar into one `ResolvedStaging` model. The event graph owns frames, join events, R-1 bench-before-join edges, and presence decisions; installability consumes those decisions without resweeping geometry. Reader steps and coverage summaries project the same model, including the caddy's mandatory DECLARED TRUST marker.

**Tech Stack:** Python 3.12 dataclasses, PyYAML spec loader/serializer, CadQuery/OCCT geometry already present, pytest/pytest-xdist, existing HTML/Markdown report generators.

## Global Constraints

- Owner amendments in `.superpowers/sdd/stepdoc-cpg-design.md` are binding.
- This increment contains staging only: no `cure` events, hand-prose retirement, viewer slider, or step PNG work.
- Use `/Users/joelwitten/Code/construction-detail-generator/.venv/bin/python` with `PYTHONPATH="$PWD/.shim"`; verify `detailgen.__file__` points inside this worktree before every trusted run.
- Do not weaken a check or turn an underdetermined case into a default assumption.
- Undeclared context remains UNORDERED/UNKNOWN; explicit `in_situ` is the FAIL mirror.
- A part may belong to at most one subassembly; duplicate membership is a loud load/compile error.
- Every staging claim carries a non-empty `why` and prints anywhere a verdict relies on it.
- A connection-free context clear is DECLARED TRUST, not proof; insertion travel remains not analyzed (P1).
- Staging changes no geometry. Existing geometry fingerprints must remain byte-identical and no view PNG may be regenerated.
- One fresh adversarial review, fix round, confirmation round, and one final full-suite gate precede merge.
- Read the final gate result before running merge; gate and merge are separate commands.

---

### Task 1: Typed staging authoring and round trip

**Files:**
- Modify: `src/spec/schema.py`
- Modify: `src/spec/loader.py`
- Modify: `src/spec/semantics.py`
- Modify: `src/spec/serialize.py`
- Test: `tests/test_sequence_schema.py`

**Interfaces:**
- Produces: `AuthoredSubassembly(name: str, why: str, parts: tuple)`.
- Produces: `AuthoredAssembly(mode: str, why: str)` where mode is exactly `bench_then_set` or `in_situ`.
- Extends: `SequenceSpec(stages=(), subassemblies=(), assembly=None)`.
- Authoring shape:

```yaml
sequence:
  assembly:
    mode: bench_then_set
    why: Build every joint on the bench before setting the unit on context.
```

```yaml
sequence:
  subassemblies:
    - name: side_px
      parts: [leg_fp, leg_bp, rail_pos]
      why: Screw this side flat while the opposite side is absent.
```

- [ ] **Step 1: Replace the future-key assertions with failing schema tests.**

Add tests that load the two examples above, reject a missing/blank `why`, reject unknown modes, reject empty part sets, reject duplicate unit names, reject one part listed in two units, reject `assembly` plus `subassemblies`, and accept staging-only `sequence:` blocks with no `stages` key.

- [ ] **Step 2: Run the schema tests and verify the new cases fail.**

Run:

```bash
PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_sequence_schema.py -q
```

Expected: the new cases fail because `subassemblies` and `assembly` are still unknown keys.

- [ ] **Step 3: Add the schema dataclasses and loader validation.**

Use these exact public shapes:

```python
@dataclass(frozen=True)
class AuthoredSubassembly:
    name: str
    why: str
    parts: tuple = ()


@dataclass(frozen=True)
class AuthoredAssembly:
    mode: str
    why: str


@dataclass(frozen=True)
class SequenceSpec:
    stages: tuple = ()
    subassemblies: tuple = ()
    assembly: AuthoredAssembly | None = None
```

Make `stages`, `subassemblies`, and `assembly` individually optional, but require at least one to be present. Preserve the existing stage uniqueness/double-claim checks. Validate subassembly uniqueness and multi-membership in `_build_sequence` so the diagnostic names both units and the repeated part.

- [ ] **Step 4: Add semantic existence checks.**

Extend `analyze_sequence(doc)` so every `subassembly.parts` entry must name an authored component id, with the same did-you-mean behavior as stage parts. Reject a context part (`doc.roles[pid] == "existing"`) inside an authored bench unit because a bench unit contains constructed parts, while context presence is controlled by `assembly`.

- [ ] **Step 5: Serialize the exact authored structure.**

Extend `spec_to_dict` so `sequence` can contain any combination of `stages`, `subassemblies`, or `assembly`. Emit `assembly` as `{"mode": ..., "why": ...}` and each subassembly as `name`, `parts`, `why` in that order.

- [ ] **Step 6: Run schema and round-trip tests green.**

Run the Step 2 command. Expected: all tests in `test_sequence_schema.py` pass.

- [ ] **Step 7: Commit the authoring surface.**

```bash
git add src/spec/schema.py src/spec/loader.py src/spec/semantics.py src/spec/serialize.py tests/test_sequence_schema.py
git commit -m "stepdoc: add typed staging authoring"
```

---

### Task 2: Resolve staging to the compiled surface

**Files:**
- Modify: `src/spec/compiler.py`
- Modify: `src/details/base.py`
- Modify: `src/assemblies/connection.py`
- Modify: `src/assemblies/event_graph.py`
- Test: `tests/test_cpg_core.py`

**Interfaces:**
- Produces: `ResolvedUnit(name: str, why: str, parts: tuple[str, ...])`.
- Produces: `ResolvedStaging(mode: str, why: str, units: tuple[ResolvedUnit, ...], context_parts: frozenset[str])`.
- Extends: `compile_connections(..., staging: ResolvedStaging | None = None)` and `ConnectionChecks.staging`.
- Produces: `Detail.resolved_staging()`; base default is `None`, `SpecDetail` maps authored ids/repeat templates to built `Placed.id` values.

- [ ] **Step 1: Write failing compile-resolution tests.**

Add a staging fixture whose component ids resolve to built ids, a repeat-backed unit whose template expands to all built instances, a retired/zero-instance part that errors loudly, and a defensive multi-membership fixture passed directly to `build_event_graph` that errors even if loader validation is bypassed.

- [ ] **Step 2: Run the focused tests and verify red.**

```bash
PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_cpg_core.py -q
```

Expected: failures for missing `ResolvedUnit`, `ResolvedStaging`, and `resolved_staging`.

- [ ] **Step 3: Implement compiled staging resolution.**

Normalize explicit subassemblies directly. Normalize `bench_then_set` to one unit named `whole detail` containing every built part whose authored role is not `existing`; keep its `why`. Normalize `in_situ` to zero units with the explicit mode/why. Store every built `role: existing` id in `context_parts` whether or not it is self-grounded.

- [ ] **Step 4: Thread the one resolved object into connection compilation.**

`Detail.validate()` must call both `resolved_sequence()` and `resolved_staging()`, then pass them to `compile_connections`. Store the object on `ConnectionChecks`; do not make installability reach back into the spec document.

- [ ] **Step 5: Run focused tests green and commit.**

Run the Step 2 command. Expected: all `test_cpg_core.py` tests pass.

```bash
git add src/spec/compiler.py src/details/base.py src/assemblies/connection.py src/assemblies/event_graph.py tests/test_cpg_core.py
git commit -m "stepdoc: resolve staging onto the compiled graph surface"
```

---

### Task 3: Frames, join events, and R-1

**Files:**
- Modify: `src/assemblies/event_graph.py`
- Test: `tests/test_cpg_core.py`

**Interfaces:**
- Adds: `FAMILY_STAGING = "staging"`; include it in `DECLARED_FAMILIES` only for authored presence claims, while R-1 edges state their derived source explicitly.
- Extends: `Event.kind` with `join` while keeping content identity `Event("join", unit_name)`.
- Extends: `EventGraph.frame_of`, `unit_of`, `join_of`, `units`, `staging`.
- Produces: `EventGraph.presence_at(drive: Event, part_id: str) -> PresenceDecision` with states `present`, `absent`, `unordered`, `coincident` and structured proof facts.

- [ ] **Step 1: Add failing CAT-core tests for frames.**

Pin these constructions:

```python
assert graph.frame_of[side_drive] == "side_px"
assert graph.frame_of[cap_drive] == "root"
assert graph.precedes(Event("join", "side_px"), cap_drive)
assert graph.precedes(side_drive, Event("join", "side_px"))  # R-1
```

Also pin that every unit-scoped place/drive event precedes its join, cross-unit/root connections are root-scoped, and an explicit `in_situ` context is present while undeclared context is unordered.

- [ ] **Step 2: Run the tests red.**

Run the Task 2 focused command. Expected: failures because frames and joins do not exist.

- [ ] **Step 3: Assign frames from connection membership.**

Build `unit_of` from resolved part sets. A connection is bench-scoped only when all `conn.parts` belong to the same unit; otherwise it is root-scoped. Assign every drive event its connection frame and every structural place event its part's unit or root frame. Hardware mapped to a drive inherits that drive's frame.

- [ ] **Step 4: Add joins and necessity across boundaries.**

Create one `join(unit)` event per unit. For a root-scoped connection, use `join(unit) -> drive(...)` as structural necessity for a member in that unit; use `place(member) -> drive(...)` for root members. For bench-scoped connections, keep internal `place(member) -> drive(...)` necessity.

- [ ] **Step 5: Add R-1 without inventing unit order.**

Emit every bench-scoped place/drive event of a unit to its own `join(unit)`. Do not emit cross-unit ordering. Canonical linearization may use declaration order as a tie-breaker, but reachability must leave independent units unordered.

- [ ] **Step 6: Implement frame-aware presence.**

For a drive in unit `S`, parts outside `S` are absent by the declared bench-frame rule. Parts inside `S` use ordinary graph reachability. For a root drive, a unit part is governed by `join(unit)` and a root part by its place/drive event. Undeclared context is unordered. Explicit `in_situ` context is present by the authored staging claim. A `bench_then_set` context is absent during bench work and present at/after the whole-detail join. Mark a clear as declared trust when the absent blocker is context and belongs to no connection.

- [ ] **Step 7: Run graph tests green and commit.**

```bash
PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_cpg_core.py -q
git add src/assemblies/event_graph.py tests/test_cpg_core.py
git commit -m "stepdoc: add frames joins and bench-before-join semantics"
```

---

### Task 4: Axis-3 staging verdicts and declared-trust visibility

**Files:**
- Modify: `src/validation/install.py`
- Modify: `src/validation/checks.py`
- Modify: `src/validation/coverage.py`
- Test: `tests/test_install_axes.py`
- Test: `tests/test_coverage_matrix.py`

**Interfaces:**
- Extends: `Finding.declared_trust: bool = False` independently of `declared_order`.
- Extends: `FamilyCoverage.declared_trust: int = 0` and JSON key `declared_trust_clears`.
- Consumes: `EventGraph.presence_at`; `_classify` does not invent a second frame/order model.

- [ ] **Step 1: Write failing synthetic verdict tests.**

Pin all three caddy mechanisms on a minimal context blocker: bench-frame absence yields PASS with `[staging]`, `DECLARED TRUST`, the authored why, and P1; undeclared yields blocking UNKNOWN naming the blocker and missing staging declaration; `in_situ` yields FAIL naming the context as provably present. Pin a unit-vs-unit bench clear without `declared_trust=True`.

- [ ] **Step 2: Write failing summary-surface tests.**

Create one passing `Finding(declared_order=True, declared_trust=True)` and assert the trust marker appears in the coverage note, verdict cell, markdown/HTML matrices, and both headline forms. Create a declared-order-only finding and assert it does not acquire the trust marker.

- [ ] **Step 3: Run the focused tests red.**

```bash
PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_install_axes.py tests/test_coverage_matrix.py -q
```

- [ ] **Step 4: Route classification through graph presence.**

Preserve the existing final-geometry hit sets. Replace raw `event_of` comparison with `graph.presence_at`. Keep ordinary later-arrival wording for path-based clears; add explicit bench-frame wording for frame-absence clears. Any clear using either declared order or staging sets `declared_order=True`; only connection-free context staging sets `declared_trust=True`.

- [ ] **Step 5: Update teaching and rung wording.**

Undeclared context must say a staging declaration is authorable now, not future. Every staging-dependent PASS says insertion travel is not analyzed. Caddy clears say the claim is DECLARED TRUST because the sofa arm participates in no connection and staging is unfalsifiable until insertability.

- [ ] **Step 6: Extend the epistemic-contract table.**

Add DERIVED bench-events-before-join, DECLARED subassembly/assembly claims with their whys, and retain UNKNOWN rows for undeclared context, cross-fragment order, and insertability. Both Markdown and HTML consume the same rows.

- [ ] **Step 7: Run focused tests green and commit.**

Run the Step 3 command. Expected: all focused tests pass.

```bash
git add src/validation/install.py src/validation/checks.py src/validation/coverage.py tests/test_install_axes.py tests/test_coverage_matrix.py
git commit -m "stepdoc: classify install access in declared frames"
```

---

### Task 5: CAT-G and CAT-H on the shipped specs

**Files:**
- Modify: `details/armchair_caddy.spec.yaml`
- Modify: `details/sit_reach_frame.spec.yaml`
- Modify: `tests/test_install_sweep.py`
- Modify: `tests/test_armchair_caddy_e2e.py`
- Modify: `tests/test_sit_reach_frame_e2e.py`

**Interfaces:**
- Caddy authors `assembly.mode: bench_then_set` with a why that explicitly says all joints are made off the sofa.
- Frame authors units `side +X` = `[leg_fp, leg_bp, rail_pos]` and `side -X` = `[leg_fm, leg_bm, rail_neg]` with bench-flat whys.

- [ ] **Step 1: Add CAT-G's three failing halves.**

Compile the shipped caddy and require 8 install-access PASSes carrying staging, declared trust, and P1. Mutate away `sequence` and require four Q9 properties on all 8: UNKNOWN class, blocking, `sofa arm` named, missing staging declaration named. Mutate to explicit `in_situ` and require 8 FAILs naming the arm and staging proof.

- [ ] **Step 2: Add CAT-H's two failing halves.**

Compile the shipped frame and require all 8 rail-screw access findings PASS because the mirror side is absent from the current bench frame; require all four cap connections root-scoped after both joins. Mutate away the subassemblies and author an in-situ two-stage side-A-then-side-B build including each side's parts and rail connections; require exactly 4 rail PASSes and 4 rail FAILs.

- [ ] **Step 3: Author the two real staging declarations.**

Use reasons that describe the actual shop technique, not verdict-silencing language. Do not change any dimensions, components, placements, connections, or validation geometry.

- [ ] **Step 4: Deliberately re-pin only the 16 moved verdicts.**

Update caddy/frame whole-report counts, render-gate expectations, and stale prose that says no staging mechanism exists. Keep every non-install verdict byte-identical. Remove no test merely because its old expected state changed.

- [ ] **Step 5: Verify the corpus and geometry invariance.**

```bash
PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_install_sweep.py tests/test_armchair_caddy_e2e.py tests/test_sit_reach_frame_e2e.py -q
```

Expected: all pass; caddy and frame each move from 8 UNKNOWN to 8 declared-order PASS, and CAT-G/CAT-H mirrors pass.

- [ ] **Step 6: Commit the corpus declarations.**

```bash
git add details/armchair_caddy.spec.yaml details/sit_reach_frame.spec.yaml tests/test_install_sweep.py tests/test_armchair_caddy_e2e.py tests/test_sit_reach_frame_e2e.py
git commit -m "stepdoc: author caddy and frame staging strategies"
```

---

### Task 6: Derived reader steps for bench units and joins

**Files:**
- Modify: `src/assemblies/event_graph.py`
- Modify: `src/validation/build_sequence.py`
- Modify: `scripts/single_detail_report.py` only if its shared model needs a new field; do not hand-author step text.
- Test: `tests/test_cpg_core.py`
- Test: `tests/test_armchair_caddy_e2e.py`
- Test: `tests/test_sit_reach_frame_e2e.py`

**Interfaces:**
- Extends: `ReaderStep` with `unit` and `joins` fields.
- `build_sequence_model` derives bench-unit titles, unit whys, join actions, and trust markers from `EventGraph`/`ResolvedStaging`.

- [ ] **Step 1: Write failing reader-order tests.**

Assert the caddy sequence contains a bench-assembly step before `set whole detail in place`. Assert the frame order contains `bench side +X`, then `bench side -X`, then visible join/set steps before the root cap-screw installs. Assert every title and why comes from the resolved graph model.

- [ ] **Step 2: Implement deterministic grouping.**

Group a unit's internal events into its bench step, preserve unit declaration order as a presentation-only tie-breaker, and emit joins as visible steps. Do not add cross-unit graph edges merely to obtain presentation order.

- [ ] **Step 3: Update unordered-part language.**

An undeclared context note may still say staging is missing; after a staging declaration, do not list that context as a loose unordered part if its presence is governed by the declaration.

- [ ] **Step 4: Run reader-surface tests green and commit.**

```bash
PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_cpg_core.py tests/test_armchair_caddy_e2e.py tests/test_sit_reach_frame_e2e.py -q
git add src/assemblies/event_graph.py src/validation/build_sequence.py scripts/single_detail_report.py tests/test_cpg_core.py tests/test_armchair_caddy_e2e.py tests/test_sit_reach_frame_e2e.py
git commit -m "stepdoc: derive bench and join reader steps"
```

---

### Task 7: Documents, naive-builder reviews, adversarial review, and integration

**Files:**
- Create: `.superpowers/sdd/task-staging-report.md`
- Create: `.superpowers/sdd/review-staging.md`
- Modify: `.superpowers/sdd/progress.md`
- Deliver: `05_Attachments/Organized/...` caddy/frame dated HTML copies in the JoelBrain vault.
- Deliver: `~/Downloads/Build Documents/` caddy/frame dated HTML copies.

**Interfaces:**
- No production interface changes beyond Tasks 1-6.

- [ ] **Step 1: Run the focused staging gate.**

```bash
PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest tests/test_sequence_schema.py tests/test_cpg_core.py tests/test_install_axes.py tests/test_coverage_matrix.py tests/test_install_sweep.py tests/test_armchair_caddy_e2e.py tests/test_sit_reach_frame_e2e.py -q
```

- [ ] **Step 2: Verify no geometry or PNG changed.**

Compare caddy/frame geometry fingerprints and existing view-file hashes against `main`. If a geometry fingerprint or view PNG hash differs, stop and investigate before document generation.

- [ ] **Step 3: Generate both HTML documents from a clean staging worktree.**

Use the repository's real single-detail report entry path for `details/armchair_caddy.spec.yaml` and `details/sit_reach_frame.spec.yaml`. Verify visible text contains the derived Build Sequence, declared-trust marker on caddy clears/summaries, frame bench/join steps, and no old “staging is future” sentence. Do not render new view PNGs.

- [ ] **Step 4: Run one fresh naive-builder review per document.**

Give each reviewer only its HTML document and this brief: “Imagine you were a handyman without official contracting/engineering training and were asked to build this item. Would you understand how to build it? Do you see all parts included? Compare it with instruction manuals for comparable products you find online. Can you place every part using only this page?” Fix material gaps and repeat the review until neither reviewer finds a build-blocking comprehension or missing-parts issue.

- [ ] **Step 5: Run a fresh adversarial branch-diff review.**

The reviewer must attack CAT-G all three halves, CAT-H the bench and 4-PASS/4-FAIL mirror, R-1, multi-membership, declared-trust summaries, geometry invariance, and absence of hand-authored reader steps. Record findings in `.superpowers/sdd/review-staging.md`, fix, then obtain a confirmation round.

- [ ] **Step 6: Run the one true final full-suite gate and read it.**

```bash
PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest -n auto -q
```

Expected baseline is at least `1169 passed / 3 skipped / 1 xfailed` plus the new staging tests, with zero failures. Record exact counts and wall time in the task report.

- [ ] **Step 7: Commit final reports and ledger.**

Add SESSION UPDATE 12 to `.superpowers/sdd/progress.md`, force-add ignored SDD files when needed, and commit the task/review/ledger artifacts.

- [ ] **Step 8: Verify live main before merge.**

From the main checkout, verify `git rev-parse main`, `git rev-parse origin/main`, and `git status`. Never include the pre-existing dirty `src/spec/compiler.py` edit. If main moved, rebase this branch in its worktree and rerun the final gate.

- [ ] **Step 9: Merge as a separate command, then push.**

Run the merge only after Step 8 and only as its own command. Push `main` to `origin` (`https://github.com/jmwitten/plumb.git`).

- [ ] **Step 10: Redeliver the two verified HTML documents.**

Copy dated documents to the vault's organized attachment folders and `~/Downloads/Build Documents/`, then content-verify the delivered copies against the gated source artifacts.

---

## Self-review result

- Spec coverage: schema, resolution, frames, R-1, presence semantics, CAT-G, CAT-H, Q9, reader surface, trust markers, docs, reviews, gate, merge, push, and delivery all map to a task.
- Scope: `+process` and `+presentation` remain excluded.
- Type consistency: authored types resolve to `ResolvedStaging`; only that object reaches `ConnectionChecks` and `EventGraph`; installability and readers consume the graph rather than the spec.
- Placeholder scan: no implementation placeholder or deferred acceptance item remains in this increment.
