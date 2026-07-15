# Detail Build Test Performance

**Status:** approved for autonomous implementation by the owner's 2026-07-15
performance directive

**Date:** 2026-07-15

**Pilot:** `armchair_caddy`

## Goal

Reduce the clean-process wall time paid to verify an armchair-caddy build to no
more than half of the referenced final gate, without using results persisted
from an earlier run and without weakening the product's meaningful defect
coverage. The historical gate was:

```text
pytest -q -n 4
1829 passed, 3 skipped, 1 xfailed in 1290.34s (21:30)
```

The binding acceptance ceiling is therefore **645.17 seconds**. A fresh
reproduction on the accepted caddy branch took 1,351.06 seconds under concurrent
machine load and exposed two order-sensitive failures. The optimized gate must
pass repeatedly in fresh Python processes with fresh temporary cache roots.

## Root-Cause Evidence

The focused design-review tests in the referenced session took 8.69 seconds.
The final 21-minute command was the entire repository suite, not a caddy build
gate. A fresh duration run showed the dominant costs were unrelated assemblies:

- trebuchet prose truthfulness: 218 seconds;
- blocked platform document generation: 134 seconds;
- platform prefilter equivalence: 118 seconds;
- site baseline mutation checks: 85–117 seconds each;
- sit-and-reach and step-stool prose truthfulness: 58–95 seconds each.

The 12 test modules whose source mentions the caddy contain 179 tests and took
78.36 seconds. That selection still over-runs unrelated DB40, platform, site,
stool, and rock-anchor tests because a source-file grep is not a semantic test
contract. Xdist `loadscope` was tested as a single-variable hypothesis and was
slower (85.06 seconds), so scheduler changes are rejected.

The current workflow conflates two different questions:

1. Did this design still compile, validate, fabricate, govern, and document
   correctly?
2. Did any compiler/platform behavior anywhere in the repository regress?

A design-only change needs the first answer immediately. A compiler/platform
change still needs the second answer before integration. Paying for question 2
after every design edit is the principal waste.

## Selected Design: Explicit Semantic Detail Gates

Pytest gains an explicit `detail_gate` marker and `--detail-gate SLUG` option.
Each marked test names the detail and one or more semantic contracts it proves.
The initial universal contract vocabulary is:

- `compile` — the authored detail compiles through the supported production
  entry point;
- `geometry` — product-defining geometry and adversarial geometric mutations
  are checked;
- `validation` — physical/construction verdicts and honest UNKNOWNs are checked;
- `fabrication` — process records fold to the installed design;
- `governance` — design selection and delivery fingerprints gate lifecycle
  transitions;
- `documents` — certifying reader artifacts derive from the accepted model and
  fail closed when release facts are absent.

When `--detail-gate armchair_caddy` is supplied, collection keeps only tests
marked for that detail. Collection fails before execution if any universal
contract is absent. This makes an accidentally thin gate loud rather than
silently fast. Future details use the same marker and contract vocabulary; no
caddy-specific selection logic belongs in the plugin.

The caddy gate selects existing real tests rather than writing a new set of
shallow duplicates. Dedicated caddy modules receive module-level markers;
mixed platform modules mark only their caddy-specific probes. Unrelated tests
that merely contain a caddy filename, link label, or comparison fixture are not
selected.

## Freshness and Cache Rules

The gate may reuse immutable objects inside one Python process or one
module-scoped fixture. It may not read a cache produced by an earlier gate run.
The existing autouse fixture gives every test a newly created temporary cache
directory, which is stricter than required and is retained in this increment.
Benchmark repetitions start new Python processes. No `--lf`, testmon database,
committed geometry result, warmed `outputs/cache`, or previous-run render cache
may contribute to the measured acceptance time.

This design deliberately distinguishes in-run common-subexpression elimination
from cross-run result reuse. Compiling a detail once and projecting multiple
assertions from that one immutable build is a general algorithmic improvement;
serving yesterday's verdict is not.

## Test-Policy Boundary

The detail gate is the required loop for changes limited to:

- a detail spec, its governed design-review document, or detail-owned source;
- detail-specific reader projection or visual assets;
- detail-specific tests and acceptance facts.

The repository-wide suite remains required before integration when a change
touches shared compiler, validation, geometry, rendering, pack, or cache code.
The performance change does not hide that obligation. It removes the full suite
from the inner design loop and makes the reason for running either gate explicit.

## Correctness and Anti-Gaming Requirements

The implementation must prove all of the following:

1. An unknown detail slug fails collection rather than running zero tests.
2. Removing one required contract from a synthetic gate fails collection.
3. The caddy gate includes all six required contracts.
4. Representative negative probes remain selected: invalid design governance,
   oversized/interfering corner keys, and blocked document delivery.
5. The selected tests are real compiler/build/document tests, not mocks of
   pytest marker behavior.
6. Ordinary `pytest` collection remains byte-for-byte equivalent in node count;
   markers only filter when `--detail-gate` is supplied.
7. Two fresh-process caddy-gate runs both pass and each finish at or below
   645.17 seconds.

No test is deleted merely because it is slow. Tests may be removed only when a
named compiler invariant makes the asserted defect structurally impossible and
another test proves that invariant at its source. This increment is expected to
gain most of its speed from relevance, not weaker assertions.

## Rejected Alternatives

### Optimize every OCCT operation first

This would benefit the full suite, but the duration table shows the immediate
problem is that unrelated product suites run at all. Kernel optimization is a
separate project and carries much higher geometry-equivalence risk.

### Persist a warm cache between runs

Rejected by the owner and by the acceptance contract. It can conceal invalid
keys and does not improve the first build of a new project.

### Select tests by filename grep or `-k caddy`

The 179-test experiment proved this is both over-inclusive and incomplete as a
contract. Names and incidental source strings are not semantic dependencies.

### Make the full suite session-cache global

Deferred. The current fixture intentionally isolates tests that mutate cache
keys and reset in-run geometry state. Sharing a verdict cache may be valuable,
but it first requires an explicit isolation audit and cache-key mutation tests.
It is not necessary to achieve this increment's target.

## Deliverables

- pytest marker/option implementation with strict contract coverage;
- caddy annotations on existing tests;
- plugin unit tests and collection-preservation tests;
- a documented one-command caddy gate;
- a benchmark report containing historical, clean full-suite, broad grep, and
  final semantic-gate timings;
- an updated roadmap ledger describing when the detail gate versus full suite
  is required.
