# Component Extension Fast Path

**Status:** owner-authorized autonomous implementation

**Date:** 2026-07-17

## Goal

Make ordinary Plumb component additions easy to describe and verify in under
60 seconds without weakening the evidence required for genuinely novel or
cross-layer behavior.

The public workflow must distinguish what a physical item *is* from how risky
its implementation change is. A screw is a fastener whether it is a new length
of an existing screw or a novel anchor with new substrate rules; those two
changes must not select the same tests.

## Current Problem

Plumb already has a registry-backed component model and generic DetailSpec
compiler. The missing piece is an explicit component-extension contract. In
its absence, a one-row catalog addition such as nominal 2x2 lumber was routed
through the same shared-platform integration tier used for new cross-layer
capabilities. The functional change was one lookup entry, its focused test ran
in seconds, and the selected platform tier ran for minutes.

The earlier reusable-vocabulary work established two useful boundaries:

- semantic tests should not build CAD; and
- one narrow geometry conformance probe is enough when shared geometry and
  renderer behavior are unchanged.

This design makes those boundaries public and machine-checkable.

## Physical Families

Every extension declares one family. Families guide expected evidence and
documentation; they do not select test scope by themselves.

| Family | Examples | Typical evidence |
|---|---|---|
| `stock_member` | dimensional lumber, rod, tube, bar, profile | section and length bounds, end datums, material identity |
| `sheet_panel` | plywood, hardwood panels, sheet metal, glazing | length/width/thickness, face datums, fabrication assumptions |
| `fastener` | screws, nails, bolts, nuts, washers, dowels | axis/head/tip datums, capabilities, envelope and installation meaning |
| `connector` | brackets, hangers, plates, ties | mounting datums, hole geometry, compatible connection semantics |
| `foundation_site` | concrete, masonry, anchors, existing walls/trees | contact datums, explicit field facts, honest UNKNOWN capacity/code state |
| `manufactured_hardware` | hinges, slides, latches, wheels, appliances | manufacturer identity or declared proxy, motion/clearance semantics |
| `custom_geometry` | irregular fabricated or imported parts | source asset, geometry-specific invariants, explicit review |

Material identity is normally a parameter or catalog fact on one of these
families, not a separate CAD component. Adding a wood species/color without a
new rule must not invent strength, durability, or capacity properties.

## Change Classes and Verification Lanes

### 1. `catalog_variant` — micro lane

Use when an existing registered component, geometry implementation, datums,
capabilities, render path, and connection behavior are unchanged. Examples:

- add nominal 2x2 to the lumber-size table;
- add a stocked washer diameter already accepted by `Washer`;
- add a registered material identity/color used by an existing panel.

Required verification:

- compile one instance through the public DetailSpec authoring surface;
- build it once;
- assert exact expected bounding dimensions, material, datums, and capability
  tags that matter to the variant;
- run `check()` and require no parameter problems.

No platform integration tier is selected. Budget: 60 seconds, expected under
10 seconds including interpreter startup.

### 2. `new_primitive` — standard component lane

Use for a new registry key implemented with the existing `Component` contract,
generic renderer, generic BOM, and existing semantics. Examples include a
simple spacer, plate, cleat, or stock profile.

Required verification is the micro lane plus:

- registry/authoring-manifest exposure;
- positive finite volume and non-empty solid;
- required local-frame datums;
- stable material and non-empty BOM label/description;
- at least one rejected invalid-parameter example, expressed as a constructor
  exception or non-empty `check()` result.

Budget: 60 seconds. If a single representative solid cannot meet it, the
component must be reclassified as complex rather than weakening checks.

### 3. `semantic_component` — semantic lane

Use when the new component introduces or changes a closed capability, datum
contract, installation role, or compatible use while still reusing existing
connection, renderer, and validation machinery. Examples include a new family
of wood screw or a new connector proxy accepted by an existing connection.

Required verification is the standard lane plus:

- exact capability expectations;
- exact required datum expectations;
- one focused consumer test proving the existing connection/installation
  consumer accepts or rejects the component correctly;
- semantic tests must not build CAD;
- one separate geometry conformance build.

The generic component probe remains under 60 seconds. The focused consumer
test is named in the change and must keep the combined verification below 60
seconds. A slow consumer test is a test-boundary defect, not permission to run
the entire platform tier.

### 4. `cross_layer_complex` — explicit escalation

Use when the change introduces a connection type, validation/evidence rule,
renderer/document behavior, imported/manufacturer geometry contract, motion,
external capacity/code fact, new schema, or expensive/irregular CAD.

The generic probe may be run for quick feedback, but it cannot release the
change. The extension must identify its owning layers, add focused failing
regressions, run the applicable platform integration/audit tier only for the
changed shared invariant, and return to the requesting product gates. No false
60-second promise is made.

## Public Component Contract File

A YAML contract drives the fast verifier:

```yaml
schema: detailgen/component-extension/v1
id: nominal_2x2_lumber
family: stock_member
change_class: catalog_variant
component:
  type: lumber
  params:
    nominal: 2x2
    length: 24 in
expect:
  dimensions:
    xlen: 24 in
    ylen: 1.5 in
    zlen: 1.5 in
  datums: [end_near, end_far]
  capabilities: []
  material_key: lumber_spf
```

The verifier compiles the component through the same DetailSpec loader and
registry used by products. It then checks the built component rather than
testing a parallel model. Results are deterministic JSON containing the lane,
checks, elapsed time, and budget.

Dimension expectations accept only `xlen`, `ylen`, and `zlen` and use the
existing unit-directive resolver. Expected datums/capabilities are subsets:
the contract names the behavior material to the addition without repeating
every inherited datum.

`new_primitive` and `semantic_component` contracts must include at least one
`reject` parameter mapping. The verifier constructs each rejected case and
requires either an exception or non-empty `check()` findings before geometry
is built.

`semantic_component` contracts must declare at least one expected capability
or a non-origin datum. A component that changes a consumer must additionally
carry its focused semantic regression in normal source control; the generic
contract does not attempt to encode arbitrary assemblies.

## CLI and Authoring Manifest

The public commands are:

```bash
python -m detailgen.authoring component-guide
python -m detailgen.authoring component-check path/to/contract.yaml
```

`component-guide` prints the families, change classes, required fields, and
budgets as bounded JSON. The same guide is published in the live authoring
manifest so an agent does not need to read compiler implementation.

`component-check` exits nonzero on schema, compilation, geometry, expectation,
or budget failure. `cross_layer_complex` returns an explicit escalation result
and never labels the change release-verified.

## Error Handling

- Unknown schema, family, change class, component key, expectation field, or
  unit fails closed with allowed values.
- Missing required evidence for a lane fails before CAD construction.
- Component `check()` findings fail with their original messages.
- Empty/non-finite geometry, dimension mismatch, missing datum/capability, or
  material mismatch fails with the exact expectation.
- A fast-lane result over 60 seconds fails even if its functional checks pass.
- Cross-layer/complex work returns `ESCALATE`, never `PASS`.

## Scope

This increment adds the public contract, verifier, two representative example
contracts, focused tests, documentation, and live authoring-manifest guidance.
It does not migrate every existing component into YAML, generate Python CAD
classes, infer manufacturer/capacity data, or replace focused consumer tests.

## Acceptance

1. A nominal 2x2 catalog contract passes through the public compiler.
2. A wood-screw semantic contract passes and proves its declared capabilities
   and datums.
3. Invalid lane evidence and dimension mismatches fail closed.
4. Cross-layer contracts return `ESCALATE` rather than a false pass.
5. Both representative fast checks complete below 60 seconds from fresh
   processes.
6. Existing authoring/registry focused tests remain green.
7. No repository-wide verification is run; only the affected focused tests and
   component-check benchmarks are required for this increment.
