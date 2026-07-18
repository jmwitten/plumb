# Catalog Context Routing Benchmark

**Date:** 2026-07-17

**Machine:** local macOS development environment

**Source:** `codex/catalog-context-lane`

## Representative catalog variant

Contract: `examples/component_extensions/nominal_3x3_lumber.yaml`

| Command | Result | Internal work | Fresh-process wall time |
|---|---|---:|---:|
| `detailgen.authoring component-route` | `catalog_micro` | no CAD construction | 3.41 s |
| `detailgen.authoring component-check` | `PASS` | 0.018270 s | 2.20 s |
| Route + check | bounded and verified | — | 5.61 s |

The fresh-process time is dominated by the source-bound Plumb/Python/CadQuery
startup. Once imported, 1,000 route classifications took 0.001397 seconds
(0.000001397 seconds mean). The routing decision itself is therefore well
under one second; it does not add meaningful time to compiler startup.

The previous 187-second 3x3 extension interval spent only about two seconds in
each component check. This route removes the mandatory broad
README/CLAUDE/roadmap/implementation/test read from that catalog path. Even
including two cold process launches, routing and verification consume 5.61
seconds of the one-minute extension target, leaving the majority of the budget
for the one-row catalog edit and scoped diff review.

## Complex fail-closed case

`test_zipline_platform_complex_contract_uses_full_context_with_known_lumber`
uses an already registered `lumber` component but declares a zipline platform
as `cross_layer_complex`. It returned `full_extension` and passed without CAD
construction in 0.05 seconds test time (2.43 seconds fresh-process wall time).

This proves reuse of an existing stock component is not enough to authorize
the micro lane. Structural product intent, site/support conditions, loads,
safety, code, and capacity remain governed by Plumb concept/design/review and
the full extension workflow.

## Focused verification

- Compiler component-extension contract: 35 tests passed in 0.17 seconds.
- Canonical Plumb plugin skill contract: 11 tests passed in 0.005 seconds.
- No repository-wide suite was run.
