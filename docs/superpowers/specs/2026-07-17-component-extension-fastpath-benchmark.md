# Component Extension Fast Path Benchmark

**Date:** 2026-07-17

**Candidate branch:** `codex/component-extension-fastpath`

**Environment:** Apple Silicon macOS, Python 3.12.13, CadQuery 2.8.0

Both acceptance samples ran in fresh Python processes with
`DETAILGEN_NO_CACHE=1`. External wall time therefore includes Python/plugin
startup, YAML loading, real component construction, the generic contract
checks, and—in the semantic case—the declared focused pytest subprocess.

## Catalog variant

Contract: `examples/component_extensions/nominal_2x2_lumber.yaml`

Checks: public DetailSpec compile, parameter check, positive geometry, exact
24 × 1.5 × 1.5 inch envelope, end datums, capability expectation, SPF material,
and BOM identity.

| Measurement | Result |
|---|---:|
| Status | PASS |
| Internal verifier time | 0.005100 s |
| External wall time | 2.20 s |
| Budget | 60 s |
| Headroom | 57.80 s |

## New primitive

Contract: `examples/component_extensions/fabricated_panel_primitive.yaml`

Checks: public DetailSpec compile, parameter check, positive geometry, exact
24 × 12 × 0.75 inch envelope, face/end datums, cedar material, BOM identity,
registry-manifest exposure, and a negative-thickness rejection probe.

| Measurement | Result |
|---|---:|
| Status | PASS |
| Internal verifier time | 0.006732 s |
| External wall time | 2.18 s |
| Budget | 60 s |
| Headroom | 57.82 s |

## Semantic component

Contract: `examples/component_extensions/exterior_wood_screw.yaml`

Checks: public DetailSpec compile, parameter check, positive geometry, exact
0.368 × 0.368 × 2.072 inch envelope, head/tip/axis datums, four capability
tags, galvanized material, BOM identity, registry-manifest exposure, invalid
exposure rejection, and the declared capability consumer test. The focused
test is invoked as an argv vector without a shell.

| Measurement | Result |
|---|---:|
| Status | PASS |
| Internal verifier time | 2.382794 s |
| External wall time | 4.58 s |
| Budget | 60 s |
| Headroom | 55.42 s |

## Affected test surface

The affected component-extension, authoring-manifest, authoring-scaffold,
registry, component-capability, and scope-manifest modules completed as 106
passing tests in 2.96 seconds external wall time. Repository-wide verification
was not run by design.

## Decision

All three fast lanes meet the sub-minute objective with more than 55 seconds of
external headroom under cold-cache conditions. Cross-layer or complex
additions do not receive a budget waiver disguised as success; the CLI returns
nonzero `ESCALATE` before CAD or consumer-test execution.
