# Armchair-caddy test-performance report

Date: 2026-07-15

Branch: `codex/caddy-test-performance`

## Result

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

## Coverage retained

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

The detail gate is the required inner loop for detail-owned changes. The full
suite remains required before integrating shared compiler, validation,
geometry, rendering, pack, or cache changes. No test was deleted, no assertion
was weakened, and no production or cache behavior changed in this increment.

The remaining caddy-gate cost is primarily the mixed install-sweep module's
whole-corpus module fixture, rebuilt on multiple xdist workers. Refactoring it
could save roughly 15–18 seconds, but the goal is already exceeded by a wide
margin. That extra change was declined to keep this performance fix minimal.
