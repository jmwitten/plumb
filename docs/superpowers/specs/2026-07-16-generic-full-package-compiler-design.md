# Generic Full-Package Compiler Design

**Status:** Approved direction, clarified 2026-07-16

## Problem

Plumb compiles physical geometry quickly, but a new project still requires an
agent to hand-wire much of the surrounding contractor package. The July 16
simple-assembly experiment took about 33 minutes of observable execution even
though the clean production commands took about 16 seconds and the model render
took about 3 seconds. The gap came from broad initial context loading,
project-specific view and report code, copied document wrappers, repeated
compilation, and handwritten review/delivery records.

The complete lifecycle is not the problem. A simple project should still
receive concept governance, a validated model, drawings, fabrication and
assembly instructions, installation/commissioning information, review evidence,
and delivery records. Those artifacts must be projections of one compiled model
rather than separate authoring projects.

## Outcome

For any ordinary `DetailSpec` that uses existing Plumb vocabulary, one generic
command produces the complete model-backed package without adding project-
specific Python:

```bash
.venv/bin/python -m detailgen.package \
  details/example.spec.yaml \
  --out outputs/example \
  --preview \
  --tests-skipped owner-request
```

The command compiles once and produces:

- STEP and GLB model artifacts plus the authoritative model manifest;
- standard model-derived drawings;
- a standalone technical build document;
- a fabrication guide and machine-readable cut/BOM schedules;
- an illustrated assembly manual derived from the process graph;
- an installation and commissioning guide derived from installation contracts;
- the governed design-review report when the spec binds one;
- a content-addressed review manifest;
- one package manifest containing fingerprints, validation state, explicit
  unknowns, test status, file hashes, and phase timings.

## Non-specialization rule

The July 16 experiment is an external acceptance benchmark only. No production
module, schema key, renderer, recipe, connection type, document template,
dispatch branch, or default copy may name or recognize that project, a built-up
member, nominal 2x4 lumber, or its screw pattern.

The generic implementation may consume only public facts already available on
any compiled detail:

- component identities, materials, capabilities, placements, and fabrication
  records;
- connections, installation contracts, process events, and reader steps;
- validation findings, coverage, evidence, assumptions, and honest unknowns;
- BOM rows, callouts, explode vectors, design-governance fingerprints, and
  export settings;
- assembly geometry and content hashes.

The experiment is replayed only after implementation by passing its existing
spec path to the generic CLI. Removing or renaming that project must not change
the package subsystem or its tests.

## Architecture

### 1. Compact authoring manifest

`detailgen.authoring` emits a deterministic JSON description of the currently
registered component and connection vocabulary, their constructor signatures,
the legal standard camera names, and the top-level `DetailSpec` keys. This is a
routing aid, not a second schema and not an authority for geometry.

An agent checks this manifest before reading implementation source. A compiler
diagnostic remains authoritative if a signature is ambiguous or a requested
capability is missing.

### 2. One prepared build context

`PackageBuilder` owns one `SpecDetail` instance and one validation report for
the entire run. It calls `render_documentation()` once, then passes the same
detail, assembly, report, process graph, and model manifest to every downstream
projection. No document consumer recompiles the spec or re-runs validation.

### 3. Generic view projection

The first release uses Plumb's existing named orthographic/isometric cameras.
It renders a fixed, generic set selected from the public camera registry and
uses the detail's existing interactive explode vectors when present. It does
not implement topology-specific view logic or authored per-project captions.

Instruction panels continue to use the existing process-graph-driven renderer,
which already focuses the parts involved in each reader step.

### 4. Typed document projections

The package subsystem first projects the compiled detail into typed,
presentation-neutral document data:

- technical summary, views, coverage, validation, BOM, and unknowns;
- fabrication records and cut-stock data;
- assembly `InstructionManual`;
- resolved installation contracts, sequence, holds, and commissioning checks.

HTML and CSV renderers consume those values. They may format or reorder data,
but they may not rediscover construction semantics from component class names,
display strings, or project identifiers.

### 5. Content-addressed package manifest

Every emitted artifact receives a relative path, media type, SHA-256 hash, and
source projection. The final manifest records:

- spec path and schema version;
- assembly, selection, and model fingerprints;
- validation and coverage summaries;
- explicit unknowns/holds;
- requested test status, including `skipped` without claiming a pass;
- phase timings and total duration;
- every artifact hash.

The manifest is written last and is deterministic except for measured timings.

### 6. Lean Plumb orchestration

The Plumb plugin keeps the full lifecycle but changes how it enters it:

1. Run preflight.
2. Classify whether the requested architecture is specified and whether the
   current vocabulary is sufficient.
3. Query `detailgen.authoring`; do not load roadmap, progress, full precedents,
   tests, or review stores during initial authoring.
4. Complete concept governance using the brief and appropriate external
   precedents; load repository implementation only if the compiler reports a
   capability gap.
5. Author the spec and invoke `detailgen.package` once.
6. Review one contact sheet plus the generated manifests and documents.
7. Escalate to `plumb-extend` only for a concrete missing public capability.
8. Deliver the generated package and recorded trace.

Roadmap and progress state remain required for actual framework-extension work.
They are prohibited during initial execution of a project that fits existing
vocabulary.

## Eight-minute service-level objective

The target covers agent execution from accepted brief/selection through local
package generation, review, commit, push, and vault delivery. Time waiting for a
human response is excluded. Tests requested as skipped consume no execution time
and are recorded honestly as skipped.

| Deadline | Stage |
| ---: | --- |
| 0:30 | Preflight and task classification |
| 1:00 | Capability-manifest query and authoring decision |
| 2:00 | Governance binding and authoritative DetailSpec |
| 2:30 | Compile and validate once |
| 4:00 | Model exports, standard drawings, and instruction images |
| 5:15 | Technical, fabrication, assembly, installation documents |
| 6:30 | Contact-sheet and document review |
| 7:15 | Trace, hashes, fingerprints, and package manifest |
| 8:00 | Commit, push, vault copy, and delivery response |

### Hard budgets

- Initial routing: no more than 60 seconds.
- Initial source context: no more than four targeted sections or approximately
  400 lines.
- Compilation: exactly one prepared detail per package run.
- Regeneration: at most one complete regeneration.
- Production-code additions during a new ordinary project: zero.
- Project-specific report/renderer registration: zero.

If existing public vocabulary cannot represent the project, the run exits with
a capability-gap diagnostic and becomes extension work. The SLA is not preserved
by silently adding bespoke code.

## Delivery sequence

The work is split into two independently reviewable plans:

1. **Core package compiler:** the generic authoring manifest, package model,
   projections, renderers, CLI, hashes, and timing evidence.
2. **Plugin orchestration:** context budgets, lazy stage loading, generic CLI
   invocation, routing evaluations, and local plugin reinstall.

The core plan lands first. The plugin plan consumes only its public CLI and JSON
contracts. The experiment is replayed only after both plans land.

## Acceptance criteria

- Two existing, materially different details produce packages through the same
  public function without runtime registry mutation or project-name dispatch.
- A fresh spec using existing vocabulary needs no Python changes to generate a
  complete package.
- Package output is deterministic apart from recorded elapsed durations.
- Every generated claim traces to a compiled fact; missing facts remain
  `UNKNOWN — NOT ANALYZED` or a visible hold.
- The package manifest records skipped tests as skipped, never passed.
- Initial Plumb execution does not read roadmap, progress, complete precedent
  packages, or review stores before a concrete extension/review stage requires
  them.
- The external simple-project replay completes in less than eight minutes with
  zero project-specific infrastructure changes.
