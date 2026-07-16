# Reusable Physical Vocabulary Benchmark

**Date:** 2026-07-15  
**Candidate commit:** `38ff70832543f96b34a3dad056794962093beed3`  
**Machine:** Apple Silicon (`arm64`), macOS 15.6.1, normal desktop load  
**Tools:** Python 3.12.13, CadQuery 2.8.0, pytest 9.1.1

These measurements were made on one developer machine under ordinary desktop
load, not on a quiet benchmark host. Small run-to-run differences should not be
treated as meaningful. Correctness is enforced by structural tests; wall-clock
measurements are supporting evidence and are not asserted in pytest.

## Historical baselines

- Focused extension baseline: 72.88 seconds.
- Connection-suite observation before this work: 7 minutes 17 seconds.
- Full-suite observation before this work: 17 minutes 12 seconds.
- Cold birdhouse package: 403.22 seconds, 22 MB total, including a 14 MB GLB
  and 3.9 MB STEP file.

The connection and full-suite values are historical observations from the
implementation plan, not reruns made for this report.

## Screw representation

Each sample came from a new Python process with `DETAILGEN_NO_CACHE=1`. The
timed region constructed one `WoodScrew` and forced `solid.val()` after imports.

| Representation | Fresh-process samples (seconds) | Median |
|---|---|---:|
| Envelope | 0.007137041, 0.008281875, 0.008538792, 0.008584542, 0.007762000, 0.008412000, 0.007703917 | 0.008281875 |
| Represented threads | 0.046475167, 0.047129417, 0.046592000, 0.045872709, 0.046210542, 0.046577792, 0.046576334 | 0.046576334 |

The envelope median is **5.62x faster**. An initial three-solid envelope build
measured only 1.89x faster and missed the rule. Profiling identified its two CAD
boolean unions as the avoidable cost. The final envelope is one equivalent
revolved profile; a deterministic test rejects reintroducing boolean unions,
and the represented-thread compatibility hash remains unchanged.

## Full birdhouse benchmark

Command:

```bash
DETAILGEN_NO_CACHE=1 .venv/bin/python scripts/benchmark.py \
  --details family_birdhouse --runs 2 --no-doc \
  --out /tmp/plumb-birdhouse-bench
```

Both runs compiled the normal declarative spec, validated successfully, found
28 placed parts, and recorded `build:WoodScrew` for all 21 screws.

| Measurement | Run 1 (s) | Run 2 (s) | Median (s) |
|---|---:|---:|---:|
| CLI compile/validate, fresh process | 3.867989 | 3.881584 | 3.874786 |
| Instrumented wall total | 2.918570 | 2.503870 | 2.711220 |
| Assemble | 0.001079 | 0.000896 | 0.000987 |
| Build 7 `FabricatedPanel` instances | 0.054106 | 0.051509 | 0.052808 |
| Build 21 `WoodScrew` instances | 0.104621 | 0.105451 | 0.105036 |
| Validate | 0.865060 | 0.881657 | 0.873358 |
| Interference checks | 0.445605 | 0.442714 | 0.444160 |
| Documentation render wrapper | 0.021637 | 0.020809 | 0.021223 |
| STEP export | 0.041169 | 0.039413 | 0.040291 |
| GLB export | 0.078755 | 0.080415 | 0.079585 |
| PNG render | 1.037443 | 0.880001 | 0.958722 |

The harness now calls the honest, ungated documentation surface. It no longer
attempts a certified delivery render, so an intentionally unconfirmed preview
can be measured without bypassing or weakening its delivery gate.

## Semantic detail gate

Each official run used a new `DETAILGEN_CACHE_DIR`. Before collection was
focused, two successful runs took 37.37 and 37.81 seconds; collect-only showed
that 25.75 seconds were spent importing 2,291 repository tests before 2,281
were deselected. The collector now imports only modules that can declare a
`pytest.mark.detail_gate`, while runtime marker validation still fails closed.
The armchair-caddy gate continues to discover its generic certification node
and specialized geometry tests.

| Fresh run | Pytest time | Wall time | Result |
|---|---:|---:|---|
| 1 | 5.76 s | 6.14 s | 10 passed, 21 deselected |
| 2 | 5.79 s | 6.17 s | 10 passed, 21 deselected |

Both wall times are below the 36.44-second target and are approximately 11.8x
faster than the historical 72.88-second focused-extension baseline.

## Cold package

Command:

```bash
rm -rf /tmp/plumb-family-birdhouse-package
DETAILGEN_CACHE_DIR="$(mktemp -d)" /usr/bin/time -p \
  .venv/bin/python scripts/family_birdhouse_report.py \
  --preview --out-dir /tmp/plumb-family-birdhouse-package
```

| Package measurement | Baseline | Current |
|---|---:|---:|
| Wall time | 403.22 s | 18.62 s |
| Instrumented build total | not recorded | 14.5628 s |
| Package size | 22 MB | 4.93 MiB |
| GLB | 14 MB | 1,189,536 bytes |
| STEP | 3.9 MB | 438,070 bytes |
| Technical HTML | not recorded | 1,789,747 bytes |

The filesystem-reported package size was 5,044 KiB (4.93 MiB). Cold wall time
is **21.66x faster** than baseline. Each placed part is tessellated once and
reused across five still views, and the technical document reuses the package's
prepared documentation export.

| Instrumented phase | Seconds |
|---|---:|
| Compile and validate | 2.2252 |
| Documentation export | 0.1471 |
| Five still views | 7.5051 |
| Instruction panels | 4.6151 |
| Technical document | 0.0379 |
| Companion documents | 0.0276 |
| Package hashing | 0.0045 |

Package identity:

- Selection fingerprint: `b7f91b653c95270ebf35968478b2d3a686cf49e356c35482f3e2c2aed4b8e1ff`
- Model fingerprint: `75b83fc078b0bbda714986c8c9ebf6f7e54bb0d95cd89185f010f72f66ebf773`
- Assembly hash: `76700d6a41a718a1250cbcd10eb392cebde00fdcc9b96731f7d7e8dd820593cc`
- Release state: `PREVIEW — NOT APPROVED FOR DELIVERY`

## Decision

Both go/no-go rules pass:

1. envelope screws are at least 2x faster than represented threads (observed
   5.62x); and
2. both fresh semantic-gate runs are below 36.44 seconds (observed 6.14 and
   6.17 seconds wall time).

The package-specific objective also passes: the cold package is more than 2x
faster than 403.22 seconds (observed 21.66x) while retaining its explicit
preview/delivery hold.
