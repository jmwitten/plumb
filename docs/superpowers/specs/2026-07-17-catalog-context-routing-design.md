# Catalog Context Routing

**Status:** owner-approved for autonomous implementation

**Date:** 2026-07-17

## Goal

Remove broad repository reading from the critical path for a pure catalog
variant while preserving Plumb's normal concept, extension, validation, and
review workflow for complex or ambiguous work.

A dimensions-only addition to an already registered component family should
need one small YAML contract, one exact catalog declaration, and one focused
component check. It should not require rereading the repository README,
CLAUDE.md, roadmap, broad implementation, or broad tests.

## Decision

The compiler owns one authoritative, machine-readable context route. The
Plumb extension skill consumes that route before selecting repository context.
Prose in the skill does not independently infer that a request is safe.

The route has two outcomes:

- `catalog_micro`: bounded context for a candidate `catalog_variant` using an
  already registered component type; or
- `full_extension`: the existing fail-closed extension workflow.

The micro route is only a candidate implementation route. Release still
requires the normal `component-check` result to be `PASS`. A malformed
contract, unknown component type, mismatched geometry, changed behavior, or
additional implementation surface moves the work to `full_extension`.

## Compiler Contract

`detailgen.authoring` exposes a route-only command:

```bash
python -m detailgen.authoring component-route path/to/contract.yaml
```

It parses the existing component-extension contract without constructing CAD.
Its JSON result includes:

```json
{
  "schema": "detailgen/component-context-route/v1",
  "id": "nominal_3x3_lumber",
  "change_class": "catalog_variant",
  "route": "catalog_micro",
  "context_budget_seconds": 30,
  "allowed_reads": [
    "the component-extension YAML contract",
    "the exact registered component declaration",
    "the closest catalog declaration and its focused test"
  ],
  "required_verification": "component-check"
}
```

Every valid non-catalog contract returns `full_extension`. A catalog contract
whose component type is not already registered also returns `full_extension`.
Invalid or unreadable contracts exit nonzero and provide no authorization for
the micro route.

The existing `component-check` result also carries the same route object so
the implementation and verification evidence cannot disagree about scope.

## Micro-Lane Boundary

The micro lane permits only:

1. read the YAML contract;
2. read the exact existing registered component declaration;
3. read and modify the closest catalog declaration;
4. add or update the focused catalog contract/test if needed;
5. run `component-check`; and
6. inspect the scoped diff.

It requires all of the following:

- the contract declares `change_class: catalog_variant`;
- the component type is already registered;
- constructor, geometry implementation, datums, capabilities, material
  semantics, connections, renderers, schemas, and document behavior remain
  unchanged;
- the source diff is limited to catalog data plus its focused contract/test;
  and
- `component-check` returns `PASS` within its existing 60-second budget.

If any condition is false or cannot be established from the bounded context,
the skill immediately resumes the full extension workflow.

## Full-Workflow Boundary

`new_primitive`, `semantic_component`, and `cross_layer_complex` always select
`full_extension`, even when their focused tests happen to be fast. The same is
true for requests that introduce or alter geometry, behavior, connections,
installation meaning, validation/evidence, renderers, documents, schema, or
external capacity/code facts.

A zipline platform cannot enter the micro lane. It is a new structural product
with site/support conditions, load paths, connections, fall hazards, dynamic
use, installation facts, and code/capacity questions. It must start with Plumb
concept/design routing and use the full risk and review workflow; any missing
compiler vocabulary encountered later is extended through the appropriate
non-micro class.

## Failure Behavior

- Invalid YAML or schema: fail; do not guess a route.
- Unknown component type: `full_extension`.
- Any change class other than `catalog_variant`: `full_extension`.
- Catalog check failure: stop micro work and use `full_extension`.
- Extra source changes outside the catalog/contract/focused-test boundary:
  use `full_extension`.
- Ambiguity about semantics, safety, or ownership: use `full_extension`.

## Testing

Focused compiler tests prove:

- a registered lumber catalog variant selects `catalog_micro`;
- an unknown component type fails closed to `full_extension`;
- primitive, semantic, and complex classes select `full_extension`;
- malformed contracts cannot authorize bounded context;
- `component-check` reports the same route; and
- the route command does not construct CAD.

Plugin contract tests prove the skill runs routing before broad context,
honors the exact allowlist only for `catalog_micro`, requires a passing scoped
check and diff, and explicitly routes structural/site/safety work such as a
zipline platform through the full workflow.

## Performance Acceptance

The route command must complete in under one second in the warmed local
environment. A representative catalog variant route plus verification must
remain under one minute. No repository-wide test suite is required for this
change; focused compiler and plugin contract tests are sufficient.
