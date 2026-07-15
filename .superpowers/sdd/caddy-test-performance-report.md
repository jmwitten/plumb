# Armchair-caddy test-performance report

Date: 2026-07-15

Branch: `codex/caddy-test-performance`

## Result

The final implementation replaces the build-specific suite with one generic
certification node plus eight retained physical caddy probes. Two fresh-process
runs passed the nine-node gate:

| Run | Pytest time | Process wall time | Result |
| --- | ---: | ---: | --- |
| Generic gate 1 | 33.51 s | 33.62 s | 9 passed |
| Generic gate 2 | 33.36 s | 33.53 s | 9 passed |

The slower 33.62-second wall time is the acceptance value. It is a **97.39%
reduction** and **38.38x speedup** against the referenced 1,290.34-second gate,
leaving 611.55 seconds of margin below the requested 645.17-second ceiling. It
is also 49.74% faster than the slower 66.89-second semantic-gate result below.

The certification engine is not caddy-specific. A proof test creates an
unrelated garden-shelf spec and contract in a temporary directory, discovers
it without a registry edit, and certifies it without adding a Python test. A
source audit also rejects caddy names or corner-key concepts anywhere in the
generic engine.

Gate collection contains exactly the eight retained caddy probes and the one
caddy contract parameter. The generic node loads only the source named by that
contract, so no unrelated product fixture compiles during the gate.

Every certification invokes the production adapter twice from source and
compares typed evidence. The benchmark fixture gives every test a new cache
root. No saved geometry, verdict, rendered output, or previous test result is
eligible.

Command:

```bash
.venv/bin/python -m pytest --detail-gate armchair_caddy -q -n 4
```

## Previous semantic-gate result

The armchair-caddy semantic build gate passed 53 real tests in two fresh Python
processes:

| Run | Pytest time | Process wall time | Result |
| --- | ---: | ---: | --- |
| Semantic gate 1 | 61.68 s | 61.85 s | 53 passed |
| Semantic gate 2 | 66.64 s | 66.89 s | 53 passed |

The slower wall time is the acceptance value. Against the referenced final
gate's 1,290.34 seconds, 66.89 seconds is a **94.82% reduction** and a **19.29x
speedup**. The requested ceiling was 645.17 seconds.

Command:

```bash
.venv/bin/python -m pytest --detail-gate armchair_caddy -q -n 4
```

Both runs used Python 3.12.13, pytest 9.1.1, pytest-xdist 3.8.0, CadQuery 2.8,
an 8-core Apple Silicon machine, and a new process. The existing autouse fixture
created new temporary detailgen cache roots for every test. No prior-run
geometry, verdict, pytest-last-failed, output, or render result was eligible.
An unrelated serial detailgen test process was active during both gate runs, so
the recorded times are conservative rather than idle-machine best cases.

## Baselines and hypotheses

| Experiment | Command shape | Pytest time | Process wall | Outcome |
| --- | --- | ---: | ---: | --- |
| Referenced final gate | `pytest -q -n 4` | 1,290.34 s | not separately recorded | 1,829 passed, 3 skipped, 1 xfailed |
| Fresh full reproduction | `pytest -q -n 4 --durations=100` | 1,351.06 s | 1,351.59 s | 2 failed, 1,827 passed, 3 skipped, 1 xfailed; concurrent machine load |
| Source-reference grep | 12 modules mentioning caddy | 78.36 s | 78.51 s | 179 passed; included unrelated products |
| Scheduler hypothesis | same 12 modules, `--dist loadscope` | 85.06 s | 85.25 s | 179 passed; rejected as slower |
| Semantic gate 1 | `--detail-gate armchair_caddy` | 61.68 s | 61.85 s | 53 passed |
| Semantic gate 2 | same, fresh process | 66.64 s | 66.89 s | 53 passed |
| Previous committed full regression | `pytest -q -n 4` | 1,027.31 s | 1,027.54 s | 1,839 passed, 3 skipped, 1 xfailed |
| Generic gate 1 | `--detail-gate armchair_caddy` | 33.51 s | 33.62 s | 9 passed |
| Generic gate 2 | same, fresh process | 33.36 s | 33.53 s | 9 passed |
| Final generic full regression | `pytest -q -n 4` | 1,780.68 s | 1,780.90 s | 1,848 passed, 3 skipped, 1 xfailed |

The full-suite duration table showed that unrelated products dominated the
cost: trebuchet prose truthfulness took 218 seconds; blocked-platform document
generation 134 seconds; platform prefilter equivalence 118 seconds; multiple
site baseline mutations 85–117 seconds; and unrelated sit-and-reach/stool
prose checks 58–95 seconds. No caddy test appeared in the 100 slowest full-suite
durations.

The root cause was not a universally slow caddy. The workflow asked the full
platform regression question after a detail-owned change. Xdist scheduling was
not the solution: grouping modules saved some fixture duplication but reduced
load balance enough to make the measured selection slower.

## Generic coverage and migration

All certified builds run the same nine rule families: compilation, geometry,
validation, connections, fabrication, BOM, governance, declared intent, and
fresh-build determinism. The caddy contract supplies data, not executable test
logic. Documents are deliberately optional; they do not establish construction
accuracy.

The equivalence ledger maps every one of the 53 former caddy-gate nodes to a
generic rule, declarative contract fact, shared platform invariant, explicit
policy decision, or retained physical probe. Forty-five bespoke nodes were
removed (84.91%); eight high-value physical probes remain, including oversized
key interference and padded keyed-miter hardware. A migration audit fails if a
removed node reappears, a ledger row is lost, or a retained node disappears.

The generic mutation matrix exercises the failure side of every accuracy
boundary:

| Corruption | Rule that rejects it |
| --- | --- |
| compile/collector exception | `compile.success` |
| blocking validation failure or unresolved UNKNOWN | `validation.clean` |
| empty, duplicate-ID, or non-positive geometry | `geometry.parts_valid` |
| connection endpoint absent from modeled parts | `connections.resolved` |
| production fabrication-fold drift | `fabrication.fold` |
| duplicate, unknown, or missing BOM source IDs | `bom.source_ids` |
| absent/mismatched declared governance | `governance.ready` / `intent.matches` |
| part, validation, connection, fabrication, or BOM intent mismatch | `intent.matches` |
| second fresh evidence snapshot differs | `determinism.evidence` |
| any rule raises unexpectedly | engine converts the exception to `FAIL` |

At the product boundary, an extra keyed-miter hardware item and four oversized
key/sofa-arm interferences remain real production negative probes.

## Previous gate coverage

The collection hook refuses an unknown gate or a gate missing any universal
contract. The caddy maps existing tests to:

- `compile`, `validation`, and `fabrication` — the full caddy pipeline,
  fabrication-fold invariant, honest family verdicts, build sequence, and
  standalone document path;
- `geometry` — three-panel reinforced-miter shell, four diagonal keys, cup
  bore, BOM, and geometric mutations;
- `governance` — precedent-first review completeness, selection/model
  fingerprints, modeling approval, delivery confirmation, and blocked preview;
- `documents` — one-compile linked technical/manual pair, typed stations,
  release gates, deterministic regeneration, shared reader names, and embedded
  panel assets.

Representative negative probes remain in the gate:

- an oversized corner-key mutation must produce four interference failures;
- padded keyed-miter hardware must fail closed;
- a review with delivery confirmation removed must write no customer package;
- governance binding must not change geometry.

Nine plugin tests prove slug selection, complete-contract enforcement, and
malformed marker rejection. `--detail-gate missing` exits 4 with `unknown detail
gate`. Ordinary collection retains all 1,833 pre-existing node IDs; the final
collection has 1,843 nodes, consisting of those 1,833 plus nine new plugin
tests and the repository's automatic audit node for the new test file.

## Test policy

The generic detail gate is the required inner loop for build-owned changes. A
future standalone build adds a spec and `<slug>.cert.yaml`; filesystem
discovery supplies its pytest gate automatically. The full suite remains
required before integrating shared compiler, validation, geometry, rendering,
pack, cache, certification-engine, or adapter changes.

The earlier semantic gate deleted no tests; the subsequent generic migration
removed only after the equivalence ledger and migration audit established the
replacement.

The frozen final tree collected 1,852 nodes and passed the full unfiltered
repository gate: **1,848 passed, 3 skipped, 1 xfailed** in 1,780.68 seconds
(1,780.90 seconds process wall). The full gate intentionally includes every
unrelated product and shared framework regression; its runtime is integration
evidence, not the build-owned inner-loop measurement.
