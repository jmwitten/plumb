# STEPDOC/CPG +process implementation plan

> Binding design: `.superpowers/sdd/stepdoc-cpg-design.md`, owner sign-off
> amendment 1 (`+process`) and CAT-K. Research record:
> `.superpowers/sdd/stepdoc-process-research.md`.

**Goal:** Represent adhesive cure as a real construction event and let a spec
declare, with provenance, that another connection must wait for that cure.
Derive the caddy's glue/cure/screw reader sequence from the same graph used by
checks. Do not add product-agnostic duration claims.

**Authoring shape:**

```yaml
connections:
  - type: glued
    label: "rail +X -> top underside (glued)"
    process:
      cure:
        instructions:
          - "Spread the selected wood adhesive on both prepared mating faces."
          - "Clamp the rail to the top and maintain the label-required fixture state."
        completion: selected_label_full_cure
        why: >-
          This project uses an adhesive bond at the long-grain mating plane;
          the selected product label governs its actual cure conditions.
sequence:
  after:
    - connection: "rail +X -> side +X ..."
      after:
        - cure: "rail +X -> top underside (glued)"
      why: >-
        The cured rail preserves the registration datum while the side is
        positioned and screwed.
```

The outer `connection` is the target install unit. Each mapping in `after` is
a typed process reference; v1 accepts exactly the closed key `cure`. This
avoids a mini-language parser such as `cure(label)`, keeps connection labels
verbatim, and leaves room for later process kinds without weakening strict
schema validation. Reader instructions come only from the typed process fact
returned by the connection type hook—never from free-text assumptions. An
authored connection-local `process.cure` block refines that fact:
`instructions` are project/product-selection assumptions, `completion` is the closed v1 token
`selected_label_full_cure`, and `why` is required provenance. Free-text
`assumptions` remain substrate/capacity disclosures and must contain no
cross-connection sequence instruction.

Compatibility rule: an unannotated imperative or spec-built `Glued`
connection still gets a safe typed default cure fact from
`Glued.process_events()`, stamped `connectiontype_default`: follow the selected
adhesive label for preparation/fixturing and treat cure as complete only at its
full-cure/full-strength condition under actual shop conditions; no duration is
represented. An authored `process.cure` replaces/refines those instructions
and is stamped `authored_process_fact`. Tests pin both provenance paths.

V1 rejects an `after` target or process source that expands to more than one
compiled repeat instance. Pairwise repeat provenance is not represented yet;
silently choosing a Cartesian product would invent order the author did not
claim.

## Task 1 — typed authoring and compiled bridge

Files:

- Modify `src/spec/schema.py`
- Modify `src/spec/loader.py`
- Modify `src/spec/semantics.py`
- Modify `src/spec/serialize.py`
- Modify `src/spec/compiler.py`
- Modify `src/spec/site.py`
- Modify `src/details/base.py`
- Modify `tests/test_sequence_schema.py`

TDD sequence:

1. Replace the two “future after key” rejection tests with RED tests for
   `AuthoredProcessRef`, `AuthoredAfter`, and `SequenceSpec.after`.
2. Pin strict teaching errors: scalar/string mini-language rejected; missing
   or blank `why`; empty `after`; unknown keys; unknown target/source
   connection; non-glued `cure` source; duplicate process reference and
   duplicate target declaration.
3. Add typed `ProcessFactSpec` parsing on connections. Pin strict keys,
   required non-empty `instructions`/`why`, the closed
   `selected_label_full_cure` completion token, exact YAML/JSON round-trip,
   and empty/default compatibility.
4. Pin compile resolution, including loud multi-instance repeat-template,
   retired, and zero-instance errors. No all-to-all or pairwise inference.
5. Add `resolved_after()` beside `resolved_sequence()` / `resolved_staging()`;
   replay fragment constraints in a composed site without inventing any
   cross-fragment order.
6. Run the focused schema/compiler/site tests.

## Task 2 — process events and graph truth

Files:

- Modify `src/assemblies/event_graph.py`
- Modify `src/assemblies/connection.py`
- Modify `src/validation/install.py`
- Modify `tests/test_cpg_core.py`
- Modify `tests/test_install_axes.py` only where direct hand-built checks need
  the new resolved constraint surface

TDD sequence:

1. Add a generic `ConnectionType.process_events(conn)` hook, empty by default;
   `Glued` returns the authored typed `cure` fact or the safe
   `connectiontype_default` fallback above. Pin both paths and their
   provenance. Add RED tests that every
   `Glued` connection therefore has
   `Event("process", label, "cure")`, in the same frame as its bond, and a
   `structural_necessity` edge `drive(bond) -> process(cure)`.
2. Add RED tests that a resolved authored constraint emits
   `process(cure) -> drive(target)` with `authored_sequence` provenance and
   the exact `why`.
3. Pin a self-contradictory/cyclic order: the merged error must name both
   process events and provenance families. Pin unknown source/target defense
   below the compiler.
4. Extend `EventGraph` with `processes_of`, typed process facts, and
   `constraints`; keep event identity content-keyed and `process` open-tagged.
   The graph calls the connection type hook and never searches assumptions,
   compares display labels, or hardcodes an adhesive type.
   Runtime resolved-reference validation asks this same hook/capability
   surface; the spec's early `glued` check is not a second graph authority.
5. Thread resolved constraints through `ConnectionChecks`,
   `compile_connections`, the detail validation path, and installability's
   direct-test fallback graph builder.
6. Pin a multi-role target: one point constraint gates every drive role group,
   never only the first. Pin `describe(process)` as
   `process(connection, cure)`, deterministic process sorting by connection
   declaration order then process kind, same-frame inheritance, and R-1
   process-before-join behavior.
7. Add an axis-3 falsifiability fixture: without the point constraint a real
   blocker is UNORDERED/UNKNOWN; with cure-before-target authored, the source
   member is provably present and the same corridor is a loud FAIL. This
   proves `after` informs checks and cannot waive geometry.
8. Add a discriminating composed-site negative: both target and cure source
   must belong to the resolved claim's `chain` according to
   `ConnectionChecks.fragments`; no authored process edge crosses fragments,
   and a mismatched manually built `ResolvedAfter` fails loudly.
9. Run focused CPG/install tests plus all existing glued-connection tests.

## Task 3 — cure is its own reader step; caddy authors CAT-K

Files:

- Modify `src/assemblies/event_graph.py`
- Modify `src/validation/build_sequence.py`
- Modify `scripts/single_detail_report.py`
- Modify `details/armchair_caddy.spec.yaml`
- Modify `tests/test_cpg_core.py`
- Modify `tests/test_armchair_caddy_e2e.py`
- Add `tests/test_stepdoc_process.py`

TDD sequence:

1. Pin that each cure event becomes its own `ReaderStep`, never folds into an
   authored stage, connection step, or join.
2. Make `ReaderStep` carry the process event and its typed fact directly; a
   renderer must not re-call `detail.connections()` or reconstruct process
   truth. Pin content-model and Markdown/HTML text from `process.cure`:
   bond/clamp instructions, completion only when the selected label's
   full-cure/full-strength condition is met under the actual shop conditions,
   and an explicit “no generic duration represented” disclosure.
3. Pin the authored constraint on both affected reader steps: the cure step
   names what must wait; the target step names the cure prerequisite; both
   print authored provenance and `why`.
4. Author both caddy rail cure constraints. The rationale must explain the
   registration strategy and must not masquerade as a universal glue rule.
   Move glue/clamp/cure instructions into each typed `process.cure` block and
   strip every cure-before-side-screws statement from connection assumptions,
   report-script fieldnotes, and authored modeling prose. Only
   `sequence.after` owns that cross-connection order.
5. CAT-K: verify both `drive(bond) -> process(cure)` derived edges, both
   cure-to-side-screw authored edges, cure-before-screw-before-join order,
   byte-stable sequence output, and exact reversion (remove one `after`
   declaration and only that dependency disappears).
6. Retire the caddy's hand-written “Hidden rail joints — glue, then screws”
   fieldnote. Add a grep/AST closer proving report scripts no longer author a
   glue/cure/screw sequence sentence; the derived Build Sequence is the only
   construction-order surface.
7. Bridge process order edges into `ConnectionChecks.derived` so the delivered
   derivation log records `drive(bond) -> process(cure)` as DERIVED and
   `process(cure) -> drive(target)` as DECLARED/authoritative with exact `why`.
   Pin both validation-report Markdown and technical-document HTML provenance.
8. Extend the shared epistemic-contract rows on both reader surfaces with:
   bond-before-cure DERIVED; point constraints DECLARED with this detail's
   actual target/source labels and whys. Pin that omission cannot pass.
9. Confirm geometry hashes and existing static view PNG hashes are unchanged.

## Task 4 — adversarial review, gate, merge, and delivery

1. Write `.superpowers/sdd/task-stepdoc-process-report.md` with tests,
   derivations, declared-vs-derived semantics, research boundary, and known
   deferrals.
2. Request a fresh adversarial review of the whole branch. Required attacks:
   non-glued cure reference, duplicate/ambiguous labels, repeats, staged
   grouping trying to swallow cure, cure frame mismatch, cycle diagnostics,
   presentation reordering truth, derivation-log/epistemic-table omission,
   type-label impersonation, multi-role targets, axis-3 falsifiability, and
   hand-typed prose grep evasion.
3. Fix findings test-first; request confirmation on the final diff.
4. Verify the worktree shim points at this worktree. Run focused gates, then
   exactly one final `pytest -n auto -q` on the true final tree and read the
   result before any merge.
5. Merge as a separate command after verifying remote `main`; push.
6. Regenerate the caddy technical document with unchanged geometry/view
   hashes. Re-run static and browser checks. Deliver byte-identical copies to
   the vault and `~/Downloads/Build Documents/`.
7. Record the final result in `.superpowers/sdd/progress.md`.

## Explicitly deferred to the separately gated +presentation increment

- Illustrated/ghosted assembly panels, callouts, station grouping, tools and
  hardware panel vocabulary, slider/navigation, and content-keyed panel PNGs.
- The separate `armchair_caddy_assembly_manual.html` and the reciprocal links
  between it and `armchair_caddy_build_document.html`.
- Product selection, clock timers, environmental cure calculations, clamp
  pressure/capacity, and structural bond capacity.
