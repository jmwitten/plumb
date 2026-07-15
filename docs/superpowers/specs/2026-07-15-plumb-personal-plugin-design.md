# Plumb Personal Codex Plugin

**Status:** approved architecture; written specification awaiting owner review

**Date:** 2026-07-15

**Owner:** Joel Witten

## Goal

Create a personal Codex plugin that reliably routes physical-design requests
through the existing Plumb semantic construction compiler at
`/Users/joelwitten/Code/construction-detail-generator`. The plugin must make the
full precedent-first, model-backed, validated, contractor-facing workflow
available from any local repository, including JoelBrain.

The plugin prevents a plausible-looking static document from being substituted
for a Plumb delivery. A deliverable may be called Plumb-generated only when its
geometry, evidence, instructions, interactive viewer, and documents came from
the compiler.

## Decision

Package Plumb as one personal plugin containing four focused skills:

1. `plumb-design` — end-to-end orchestration for a new physical project.
2. `plumb-concept` — precedent research, concept comparison, and modeling
   approval.
3. `plumb-review` — source-backed technical, lifecycle, document, and visual
   review of an existing project or delivery.
4. `plumb-extend` — tested compiler development when a requested design exceeds
   the current authoring or generation vocabulary.

This boundary follows user intent rather than internal pipeline stages. Concept
selection, review, and compiler extension can each be requested independently.
Modeling, rendering, fabrication documentation, assembly documentation,
installation documentation, and publishing remain coordinated stages of one
design lifecycle because separating them would make partial or stale packages
more likely.

## Alternatives Considered

### One user-level `plumb` skill

This would be simple to install, but one skill would mix design research,
modeling, generated-document review, compiler architecture, and release work.
Its trigger description and body would be broad, more context would load for
every request, and independent review or compiler-development requests would
be harder to route precisely.

### Personal plugin with four skills — selected

This gives Plumb one visible product identity while keeping each skill focused.
Only the procedures relevant to the current intent need to load. The
end-to-end skill remains a thin orchestrator that composes the other skills
through explicit, file-backed handoffs.

### Plugin plus an MCP server

An MCP layer could expose compiler operations as tools, but the current Python
and CLI APIs already provide deterministic entry points. A server would add
startup, transport, schema, and lifecycle complexity without solving a current
problem. It remains a future option if Plumb needs remote execution or a stable
tool API for non-Codex clients.

## Installation and Scope

The plugin is personal rather than repository-scoped because design requests
often begin in JoelBrain while the implementation system lives in a sibling
repository. The initial layout is:

```text
~/plugins/plumb/
├── .codex-plugin/
│   └── plugin.json
├── skills/
│   ├── plumb-design/
│   │   ├── SKILL.md
│   │   └── agents/openai.yaml
│   ├── plumb-concept/
│   │   ├── SKILL.md
│   │   └── agents/openai.yaml
│   ├── plumb-review/
│   │   ├── SKILL.md
│   │   └── agents/openai.yaml
│   └── plumb-extend/
│       ├── SKILL.md
│       └── agents/openai.yaml
└── scripts/
    └── plumb-preflight.py
```

The plugin is registered in the default personal marketplace at
`~/.agents/plugins/marketplace.json`. Version one has no MCP server, app,
connector, hook, or bundled output assets.

`plumb-preflight.py` centralizes environment discovery instead of duplicating
paths in four skills. It reads optional `PLUMB_REPO` and `PLUMB_VAULT`
environment variables and otherwise defaults to:

- Plumb repository: `/Users/joelwitten/Code/construction-detail-generator`
- delivery vault: `/Users/joelwitten/Code/JoelBrain`

It reports machine-readable paths, repository state, active branch/worktrees,
Python environment availability, Blender availability, and the expected
compiler entry points. It does not mutate either repository.

## Shared Operating Contract

Every skill follows these rules:

1. Run the shared preflight before interpreting or changing a project.
2. Read the current Plumb `README.md`, `CLAUDE.md`, and the closest relevant
   precedent/specification; do not freeze a duplicate compiler manual inside
   the plugin.
3. Sync the affected repository and use an isolated worktree for changes.
4. Treat structured design records, specs, pack projects, compiler source, and
   review stores as sources of truth. Generated HTML is never the source of
   truth.
5. Preserve deterministic geometry, explicit provenance, model-backed
   documents, and honest `UNKNOWN` verdicts.
6. Never infer structural capacity, code compliance, manufacturer performance,
   or field suitability from modeled geometry alone.
7. Automatically invoke the extension workflow when software vocabulary is
   missing. Do not replace missing compiler functionality with prose or static
   HTML.
8. Retain explicit field and manufacturer holds when the missing fact cannot be
   established by software.
9. Verify source changes, regenerate artifacts, inspect them visually, and only
   then copy delivery artifacts into JoelBrain.
10. Commit and push changes in every repository the workflow intentionally
    modifies while preserving unrelated user work.

## Skill 1: `plumb-design`

### Trigger

Use for requests to design or build a real-world physical object with Plumb,
the contractor/design code, the construction compiler, model-backed drawings,
or the full fabrication/assembly/installation suite. Explicit invocation is
`$plumb-design`.

### Responsibility

Own the complete user outcome without duplicating the detailed concept,
review, or compiler-extension procedures. It coordinates their handoffs and
ensures the run does not stop at a partial artifact.

### Workflow

1. Run preflight, sync both repositories as needed, and establish an isolated
   Plumb worktree.
2. Invoke the concept workflow unless a current governed concept already has a
   valid modeling approval.
3. Select the narrowest authoring surface that expresses the approved design:
   an existing versioned pack, declarative `DetailSpec`, or imperative `Detail`
   escape hatch.
4. Create the model and all authored project data through test-driven changes.
5. Invoke the extension workflow whenever the selected authoring surface,
   component library, validation system, process graph, renderer, or document
   generator cannot express a required fact.
6. Compile and validate the model, including geometry, connections,
   construction completeness, evidence coverage, installation contracts, BOM,
   cut plan, and modeled-to-concept conformance.
7. Generate the established contractor-facing suite: interactive GLB viewer,
   real exploded view and explode control, assembly-state controls,
   dimensioned views, fabrication packet, assembly manual, installation and
   commissioning sheet, and review trace.
8. Invoke the review workflow as a mandatory release gate.
9. Obtain or apply the available delivery confirmation against the current
   concept and model fingerprints.
10. Copy approved artifacts into the appropriate JoelBrain attachment folder,
    update the project note, commit and push both repositories as applicable,
    and report remaining field holds.

### Completion Condition

The skill completes only when the approved compiler-backed package is available
in JoelBrain, verification evidence is recorded, and no required delivery step
is silently omitted. An explicit field hold may remain without preventing
document delivery when the hold is accurately represented.

## Skill 2: `plumb-concept`

### Trigger

Use for concept exploration, precedent research, architecture comparison,
simplified design visuals, or selection of a build method before detailed
modeling. It may run independently or as the first stage of `plumb-design`.
Explicit invocation is `$plumb-concept`.

### Workflow

1. Capture the brief: use, environment, users, builder skill, available tools,
   loads, site and installation conditions, appearance, material preferences,
   safety boundaries, required features, and prioritized constraints.
2. Research at least one comparable commercial product and one real build
   instruction. Record claim-level construction observations and lessons with
   provenance rather than retaining bare links.
3. Produce at least three materially different concepts. Each pair differs in
   at least two architecture-signature fields: load path, joint family, part
   topology, fastening strategy, visible-seam strategy, and fit strategy.
4. Show a simplified visual for every concept before production modeling. Use
   comparable viewpoints and include direct precedent examples.
5. Complete the standard comparison matrix for strength representation, part
   count, fasteners, operations, tooling, tolerances, material, appearance,
   builder skill, and instruction complexity.
6. Derive the novelty ledger. Every unsupported feature cites a forcing brief
   requirement or an explicit approved exception with risks and rejected
   alternatives.
7. Record the purpose of each conceptual part family and whether joinery or an
   existing part could absorb that function.
8. Recommend one concept from decisive comparison cells and document accepted
   tradeoffs.
9. Render the developer-facing design-review report and obtain approval when
   required. Prior broad autonomy may satisfy this gate only when it clearly
   covers the choice and no new safety-critical decision has emerged.
10. Store the current selection fingerprint and transition the governed record
    to `approved_for_modeling`.

### Handoff

The output is the committed `detailgen/design-review/v1` sidecar plus its report
and current modeling approval. A concept-only request may stop here. An
end-to-end request passes the selected concept id and fingerprint to
`plumb-design`.

## Skill 3: `plumb-review`

### Trigger

Use to review, audit, diagnose, revise, regenerate, or release an existing
Plumb project or model-backed package. Use it when a packet looks wrong,
dimensions or instructions disagree, an expected view is absent, or a user
asks whether a design is ready to fabricate or install. Explicit invocation is
`$plumb-review`.

### Workflow

1. Identify the sources of truth: design-review sidecar, DetailSpec or pack
   project, imperative detail when applicable, compiler source, review stores,
   generated outputs, and approval fingerprints.
2. Create an isolated worktree and regenerate the current package from source
   to establish a reproducible baseline. Do not diagnose solely from a copied
   HTML artifact.
3. Verify schema, compilation, geometry, interference allowances, bearings,
   bonds, through-holes, connectivity, connection contracts, spatial
   invariants, load-path representation, evidence provenance, coverage
   matrices, BOM, cut plans, machining, fastener schedules, installation
   contracts, and construction ordering.
4. Confirm the production topology and selected construction method still
   conform to the approved concept fingerprint. Reopen `plumb-concept` when a
   proposed correction changes the architecture rather than refining its
   implementation.
5. Review every reader step and instruction panel for complete arrivals,
   feasible ordering, visible tools/hardware, curing and clamping dependencies,
   placement marks, stop gates, and acceptance checks.
6. Perform visual QA on the hero view, orthographic and dimensioned views,
   exploded view, interactive explode control, assembly-state control, labels,
   hidden connections, fabrication drawings, and installation sheet.
7. Render every customer document at desktop and mobile widths and render the
   print/PDF path. Inspect for overflow, missing assets, illegible labels,
   broken navigation, orphaned headings, and inconsistent presentation.
8. Compare the package structure and capabilities with the closest established
   Plumb reference package. Treat missing GLB/model payloads, viewer controls,
   expected document sections, or unusual file-size differences as diagnostic
   evidence rather than accepting superficial visual similarity.
9. Classify every finding as blocking geometry, lifecycle/concept mismatch,
   unresolved `UNKNOWN`, installation hold, document inconsistency,
   presentation defect, or advisory. Trace each finding to the authoritative
   source that must change.
10. Add a failing regression, then fix the spec, project data, compiler, or
    renderer at the source. Invoke `plumb-extend` automatically for a compiler
    gap. Never make a generated HTML edit the authoritative repair.
11. Regenerate and repeat the focused checks, full Plumb suite, project
    end-to-end checks, visual review, and reference-package comparison.
12. Update the review trace and review stores, copy approved artifacts to
    JoelBrain, and commit/push the source changes.

### Completion Condition

The reported concern is reproduced and resolved or accurately classified as a
remaining hold. Generated artifacts match their sources and approved concept,
and the relevant release evidence is fresh.

## Skill 4: `plumb-extend`

### Trigger

Use when Plumb lacks a component, datum/placement primitive, connection type,
installation contract, DetailSpec construct, pack/archetype, validation rule,
evidence behavior, process-graph feature, viewer behavior, renderer, or
document feature required by a real project. It may be invoked directly for
compiler work or automatically from design/review. Explicit invocation is
`$plumb-extend`.

### Workflow

1. Capture the missing capability as a concrete failing project case and reduce
   it to the smallest reproducible example.
2. Classify the owning layer: component geometry, datum/placement, connection,
   installation, base schema/compiler, domain pack, validation/evidence,
   process graph, rendering/viewer, or document generation.
3. Read the closest reference implementation, its public contract, tests, and
   relevant roadmap state before choosing a seam.
4. Decide whether the required fact belongs in general compiler vocabulary,
   a versioned domain pack, or project-authored data. Do not embed one
   project's dimensions or prose in a generic layer.
5. Write the smallest failing unit test plus an integration or end-to-end test
   through the public surface that the requesting project will use.
6. Implement the narrowest reusable capability while preserving determinism,
   provenance, stable identities, explicit unknowns, model-backed documents,
   and backward compatibility.
7. Expose the capability through the narrowest appropriate public authoring
   surface. Version a schema, pack, or archetype when its public contract
   changes; retain the imperative Detail API as the deliberate P3 escape hatch.
8. Run focused tests, affected subsystem tests, the requesting project's
   end-to-end test, and the full Plumb suite.
9. Regenerate and visually compare affected outputs. Update frozen references
   only when the semantic change is intentional and reviewed.
10. Update current repository documentation when a public authoring or
    lifecycle contract changed.
11. Commit the compiler change, report the new capability and verification,
    and return control to the calling design/review workflow at the blocked
    step.

### Automatic-Extension Boundary

The skill may autonomously change and test the Plumb compiler when that work is
necessary for the requested design. It does not invent external facts. Unknown
soil, substrate, field dimensions, utility locations, manufacturer capacities,
or code interpretations remain explicit holds unless authoritative evidence is
available.

## Handoff and State Model

Skills communicate through durable repository state rather than relying on
conversation memory:

```text
brief + precedents
  -> design-review sidecar + selection fingerprint
  -> approved concept
  -> DetailSpec / packed project / Detail
  -> compiled model + evidence + review stores
  -> generated package
  -> review findings and fixes
  -> delivery confirmation + JoelBrain artifacts
```

`plumb-design` owns the end-to-end plan and records each subordinate workflow
as a plan step. `plumb-concept`, `plumb-review`, and `plumb-extend` can also run
independently when their own completion condition satisfies the user's request.

### Orchestration mechanics

Codex skills do not call one another through a native `callSkill()` runtime.
`plumb-design` therefore implements explicit orchestration: its `SKILL.md`
links directly to the three sibling `SKILL.md` files, requires Codex to read the
complete applicable sibling instructions before that stage begins, and places
each stage in the active task plan.

The required new-design order is:

```text
plumb-design preflight
  -> plumb-concept (unless current modeling approval already exists)
  -> model and validate
  -> plumb-extend zero or more times when compiler vocabulary is missing
  -> generate the complete package
  -> plumb-review
  -> plumb-extend and repeat review when a compiler defect is found
  -> delivery
```

Direct invocation preserves each skill's independent completion condition:

- `$plumb-concept` stops at a committed, approved modeling handoff.
- `$plumb-review` completes the review and invokes extension when necessary;
  it reopens concept selection when the proposed correction changes the
  approved architecture.
- `$plumb-extend` completes and verifies a reusable compiler increment, then
  returns to the exact blocked step when invoked by another Plumb workflow.

End-to-end evaluation must prove this explicit sequence. Skill chaining is an
instruction-backed agent workflow, not an implicit plugin-platform behavior.

## Error Handling

- Missing Plumb repository or broken environment: attempt ordinary local setup
  and repair; block with the exact failing prerequisite if repair is not safe
  or possible. Never substitute static HTML.
- Dirty worktree: preserve unrelated changes and use an isolated worktree.
- Invalid or stale concept approval: reopen the concept gate and report which
  fingerprint changed.
- Physical validation failure: keep rendering/release blocked and trace the
  failing invariant to authored or derived input.
- Missing compiler capability: invoke `plumb-extend` and resume afterward.
- Unknowable external fact: retain a visible `UNKNOWN` or field/manufacturer
  hold and continue only through stages that the hold does not prohibit.
- Visual or document failure: fix the renderer or source data, regenerate, and
  repeat visual QA.
- Failed full-suite regression after extension: do not release the project or
  merge the compiler change.

## Skill and Plugin Validation

Implementation must validate both the plugin itself and its behavior.

### Structural validation

- Validate every `SKILL.md` with the skill quick validator.
- Validate `.codex-plugin/plugin.json` and the complete plugin scaffold.
- Confirm all four skills appear after personal-marketplace installation.
- Confirm the preflight script works from JoelBrain, the Plumb repository, and
  another local directory.

### Trigger evaluations

Confirm implicit and explicit routing for prompts including:

- “Use my contractor/design code to design a freestanding birdhouse.”
- “Use Plumb and run the full fabrication, assembly, and installation suite.”
- “Show me three precedent-backed concepts before modeling.”
- “Why is this Plumb packet missing its exploded view?”
- “Regenerate and review the caddy package.”
- “Add a reusable mitered-panel primitive to the construction compiler.”

Confirm that unrelated requests about plumbing, ordinary web design, or prose
reviews do not trigger the plugin.

### Forward workflow evaluations

1. Start a new physical-design request from JoelBrain and prove the skill finds
   the sibling Plumb repository.
2. Run a concept-only prompt and prove it stops with an approved design-review
   record rather than beginning production modeling.
3. Run a design requiring one missing compiler feature and prove extension
   tests fail first, the compiler is extended, and the design resumes.
4. Review a deliberately incomplete static packet and prove the workflow
   rejects it as non-Plumb rather than polishing it.
5. Introduce a presentation defect in a generated package and prove review
   fixes the renderer/source and regenerates the output.
6. Make the Plumb repository unavailable and prove every skill blocks clearly
   without creating fallback HTML.

## Acceptance Criteria

1. A user can invoke one end-to-end workflow with `$plumb-design` or natural
   language from any local repository.
2. “Use my contractor/design code” resolves to the real Plumb compiler.
3. Concept selection always produces simplified visuals before production
   modeling and retains governed precedent evidence.
4. Missing compiler vocabulary is extended and tested automatically.
5. A new design cannot be delivered without the established interactive,
   exploded, assembly, fabrication, installation, and review surfaces.
6. Review findings are fixed at their authoritative source, never only in
   generated HTML.
7. The plugin preserves Plumb's validation, provenance, and `UNKNOWN` rules.
8. Skill bodies stay focused and concise; detailed compiler truth remains in
   the live Plumb repository instead of being duplicated into plugin context.
9. The personal plugin passes structural validation and realistic trigger and
   workflow evaluations.

## Out of Scope

- An MCP server or remote Plumb service.
- A shared/team marketplace or distribution to other users.
- Independent skills for modeling, rendering, fabrication, assembly,
  installation, or publishing.
- Replacing Plumb's existing compiler, review, design-review, or release
  schemas with plugin-owned equivalents.
- Automatically approving a new safety-critical concept when the available
  authority does not cover that decision.
