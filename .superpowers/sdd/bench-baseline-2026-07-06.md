# Generation-speed baseline (directive #8, step 1) — 2026-07-06

Measured with `scripts/benchmark.py` (branch `sdd/bench`, commit `8b98f8d`),
single M-series Mac, normal desktop load — **not** a quiet CI box; treat any
<15% run-to-run delta as noise. 2 runs per measurement everywhere below
(reported as the average of the two, which for n=2 is also the median).
Raw JSON: `outputs/bench/bench.json` (gitignored; re-generate with
`.venv/bin/python scripts/benchmark.py`).

This is measurement only, per the directive's benchmark-first order. No
optimization was attempted or is proposed as code here — the lever ranking
at the bottom is evidence for whoever dispatches S3, not a design.

## Methodology in one paragraph

Every phase number below is **self time** (`detailgen.core.timing.PhaseTimer`):
nested phases (e.g. a component solid build happening lazily on its first
`world_solid()` touch inside the interference sweep) subtract out of their
parent, so each detail's phase column sums to its measured wall clock — you
can add the rows below and get the total, with nothing double-counted.
Instrumentation is applied by monkeypatching `Component.solid`, the five
`validate_assembly` check functions, `buildinfo.geometry_hash`, and the four
`rendering.export` exporters for the duration of one measured run, then
restored — nothing in `src/` was edited to build this harness.

## Headline numbers

| Detail | parts | pairs (C(n,2)) | **no-render CLI** (`python details/X.py`, fresh process) | in-process assemble+validate+render+PNG (warm process) |
|---|---:|---:|---:|---:|
| rock_anchor | 26 | 325 | **10.08s** | 14.52s |
| tree_attachment | 11 | 55 | **4.47s** | 7.70s |
| trolley_launch | 11 | 55 | **2.92s** | 4.09s |
| platform | 45 | 990 | **11.81s** | 18.67s |

Consolidated report (`scripts/consolidated_report.py`, all 4 details, run
against a scratch cache dir — never the real `outputs/consolidated` or the
vault copy): **cold 83.7s**, **warm 14.0s**.

Fresh-subprocess import cost is ~1.7-1.9s of `cadquery` alone (cold OCCT/VTK
load) plus a negligible ~7ms for `detailgen` + the specific detail module —
import cost is dominated by the cadquery/OCCT stack, not this project's code,
and is nearly identical across all 4 details.

## Hypothesis confirm/refute (session notes, 2026-07-06)

| Hypothesis | Verdict | Evidence |
|---|---|---|
| "full `d.render()` ~15-18s/detail" | **Partially confirmed, but conflates two different things** | The bare `Detail.render()` call (step+GLB+manifest+hash, already-validated) is only 2.3-6.2s across the 4 details (trolley 2.27s, tree 3.76s, rock_anchor 4.73s, platform 6.24s). The 15-18s figure matches a **fresh-process import + build + validate + render** run for platform-scale details specifically (≈1.7+8.2+6.2=16.2s) — i.e. it was measuring the whole pipeline from cold, not `render()` in isolation, and conflates validate's O(n²) sweep with render's hashing (see below) into one number. |
| "cold 4-detail consolidated doc regen ~55s; warm ~14s" | **Warm confirmed (14.0s measured); cold refuted** | Warm matches almost exactly. Cold is **83.7s**, ~52% above the ~55s figure — this benchmark's cold run is genuinely cold (fresh scratch dir, no prior manifests/PNGs at all), so 83.7s should replace 55s as the cold baseline for the 4× target. |
| "single-detail CLI run ~60-90s including imports + validation" | **Refuted — actual cost is far lower** | Measured no-render CLI wall time is **2.9-11.8s** across all 4 details (platform, the heaviest, is 11.8s). This is the single biggest correction in this report: the real per-iteration authoring-loop cost is roughly 10-30× lower than believed, which changes the shape of the 4× target for that metric from "get 75s down to ~20s" to "get ~12s down to ~3s." |
| "the earlier '25-30 min' figure was multi-process orchestration overhead, NOT geometry cost" | **Supported** | Even a fully cold, from-scratch run of all 4 details plus doc assembly/GLB embedding is 83.7s (1.4 min) — nowhere near 25-30 min, consistent with that figure being orchestration overhead elsewhere, not geometry/doc-generation cost. |
| "agent authoring loops... per-iteration latency (import+build+validate, NO render) is the metric that matters most" | **Adopted as the primary metric below** | Confirmed as the right framing: render's hashing cost (next section) is real but only paid at render checkpoints, not every authoring iteration, so the no-render CLI column above is what lever rankings are optimized against. |

## Where the time goes (ranked, per detail)

Percentages are of that detail's in-process wall total (assemble + validate +
render + a PNG capture; PNG isn't part of these details' `Detail.render()`,
so it's timed as an extra step — see harness docstring).

**rock_anchor** (26 parts, 325 pairs, 14.52s):
1. `validate:interference` 4.68s (32.2%) — 325 pairwise boolean intersects
2. `hash` 4.10s (28.2%) — 27 `geometry_hash` calls (26 parts + assembly), inside `render:manifest`
3. `render:png` 2.09s (14.4%)
4. `validate:bearing` 1.07s (7.3%) — 20 declared bearing checks
5. `validate:floating` 0.84s (5.8%)
6. `build:HexNut` 0.58s (4.0%, 8 instances)
7. `render:glb` 0.46s (3.2%)
8. `build:AngleBracket` 0.20s (1.4%, 2 instances) / `build:HexBolt` 0.16s (1.1%, 2) / `render:step` 0.10s / rest <1% each

**tree_attachment** (11 parts, 55 pairs, 7.70s):
1. `hash` 3.25s (42.2%)
2. `render:png` 1.54s (19.9%)
3. `build:LagScrew` 0.93s (12.0%, 4 instances — threaded-shaft revolve geometry is the expensive part)
4. `validate:interference` 0.59s (7.6%)
5. `validate:bearing` 0.45s (5.8%)
6. `render:glb` 0.44s (5.7%)
7. `validate:floating` 0.29s (3.7%) / `build:SlottedBeamEnd` 0.13s (1.7%) / rest <1% each

**trolley_launch** (11 parts, 55 pairs, 4.09s):
1. `hash` 1.79s (43.8%)
2. `render:png` 0.90s (22.0%)
3. `render:glb` 0.43s (10.5%)
4. `validate:interference` 0.37s (9.2%)
5. `build:StructuralScrew` 0.20s (4.8%, 2 instances) / `build:StrapGate` 0.11s (2.7%) / rest <2% each (no `validate:floating` — this detail declares no `ground`)

**platform** (45 parts, 990 pairs, 18.67s):
1. `validate:interference` 6.41s (34.3%) — 990 pairwise boolean intersects
2. `hash` 5.60s (30.0%) — 46 `geometry_hash` calls
3. `render:png` 2.80s (15.0%)
4. `validate:bearing` 1.19s (6.4%, 38 checks)
5. `validate:floating` 0.58s (3.1%)
6. `build:Lumber` 0.37s (2.0%, 17 instances) / `build:HexBolt` 0.34s (1.8%, 4) / `render:glb` 0.44s (2.3%) / rest <2% each

**Standout finding not on directive #8's candidate list**: `geometry_hash`
(called per-part + once for the whole assembly, from `build_manifest` inside
`export_manifest`) is **28-44% of wall time in every detail**, and it is
tessellating the **world-transformed** solid (`p.world_solid()`), not the
local one — so identical components at different placements (e.g. 8
identical hex nuts in rock_anchor) still each pay a full tessellate +
canonicalize + hash, unlike the `_build()` cost a solid cache could dedupe.
tree_attachment and trolley_launch (both 11 parts, only 12 hash calls each)
show the clearest signal that per-shape complexity, not part count, drives
this: their hash phase (3.25s / 1.79s) is 1.8x the size despite fewer parts
than rock_anchor, almost certainly the 20"-dia `TreeTrunk` cylinder's finer
tessellation facet count. This is `core/buildinfo.py` territory (owned by
task S2, out of scope here — not touched), but it is too large a share of
render time to leave out of the evidence for whoever dispatches next steps;
see the lever ranking below.

## Lever (a): component-solid cache, keyed on (type, params)

Grouped every placed component by `(type(component).__name__, params())`
after build; `count - distinct` per type is what a cache would eliminate.
Savings = `(that type's measured total build seconds / its instance count) ×
redundant instances` — i.e. assumes near-uniform per-instance cost within a
type, accurate for identical fasteners.

| Detail | distinct groups / total components | redundant instances (by type) | estimated savings |
|---|---:|---|---:|
| rock_anchor | 12 / 26 | HexNut ×4, Washer ×6, Epoxy/ThreadedRod/AngleBracket/HexBolt ×1 each | 0.52s |
| tree_attachment | 4 / 11 | LagScrew ×3, Washer ×3, SlottedBeamEnd ×1 | 0.78s |
| trolley_launch | 9 / 11 | Lumber ×1, StructuralScrew ×1 | 0.11s |
| platform | 16 / 45 | Lumber ×9, JoistHanger ×5, DeckBoard ×5, HexBolt ×3, Washer ×3, HexNut ×3, WireMesh ×1 | 0.99s |
| **aggregate** | | | **2.39s** of 29.28s aggregate no-render CLI time (**8.2%**) |

Caveat: this bounds `_build()` savings only. It does **not** shrink the
`hash` phase, since `build_manifest` hashes each part's *world*-transformed
solid — same-type duplicates sit at different placements and hash
differently regardless of whether their local solid is cached.

## Lever (c): bbox/spatial prefilter before the pairwise interference sweep

**Confirmed absent** — `validate_assembly` (`src/validation/checks.py`) runs
`for a, b in combinations(assembly.parts, 2): check_interference(a, b, ...)`
unconditionally; `check_interference` goes straight to a full OCCT boolean
`.intersect()` for every pair. No bounding-box or any other short-circuit
exists anywhere in that file today.

Measured (post-build, via a cheap AABB test over every pair — not part of
the main phase table): fraction of pairs whose bounding boxes don't even
overlap, i.e. pairs a prefilter could skip before ever calling
`.intersect()`:

| Detail | pairs | bbox-disjoint pairs | skippable fraction | `validate:interference` time | estimated savings |
|---|---:|---:|---:|---:|---:|
| rock_anchor | 325 | 271 | 83.4% | 4.68s | 3.90s |
| tree_attachment | 55 | 37 | 67.3% | 0.59s | 0.40s |
| trolley_launch | 55 | 45 | 81.8% | 0.37s | 0.31s |
| platform | 990 | 887 | 89.6% | 6.41s | 5.74s |
| **aggregate** | | | | | **10.35s** of 29.28s aggregate no-render CLI time (**35.3%**) |

This is the single largest lever, and — unlike (a) — its savings **scale
with assembly size**: 39-48% of the no-render CLI loop for the two bigger
assemblies (rock_anchor, platform), only 9-11% for the two 11-part ones
(import + component-build time dominates those instead). Since the 4×
target is framed around "a moderately complex design," this lever is
highest-leverage for exactly the assemblies the directive is worried about.

## Lever (b): persistent solid cache across process runs

Not directly measurable with a single from-scratch benchmark (no run here
reuses a prior process's cache). Upper bound = each detail's total `build:*`
time, since a warm persistent cache would let a subsequent run of the *same*
detail skip `_build()` entirely: rock_anchor 1.06s, tree_attachment 1.08s,
trolley_launch 0.46s, platform 1.39s — aggregate **3.99s** (13.6% of the
no-render CLI baseline). Note this is the *same* underlying build cost lever
(a) also bounds — (a) dedupes within one run, (b) dedupes across runs — so
if implemented, they should likely be **one cache with two tiers** (an
in-memory type+params dict, persisted to `outputs/cache/`) rather than two
separate mechanisms; their savings are not simply additive on top of each
other.

## Lever (d): per-pair verdict cache (geometry hash + relative transform)

Not measurable here — this benefits an *edit → rebuild* loop (change one
param, most pairs' relative geometry is unchanged), and this benchmark only
measures from-scratch builds. Needs a dedicated follow-up methodology (edit
one param, rebuild, diff against the unedited baseline) before a number can
be attached. Qualitatively: it's complementary to (c), not additive with it
— (c) already removes 67-90% of pairs by bbox alone within a single run, so
whatever (d) would additionally save across runs is bounded by the *smaller*
post-(c) interference cost, not the numbers in the (c) table above.

## Lever (e): multiprocessing for pairwise checks

Not attempted/measured (feasibility question, not a timing one — OCC solids
don't pickle, per the directive's own text). Given (c) alone cuts the
interference sweep to ~0.3-0.8s per detail, the serial workload remaining
after (c) is small enough that fork/BREP-(de)serialization overhead is
unlikely to pay for itself — recommend revisiting only after (c) lands and
is re-measured.

## Ranking (by measured/derived expected savings, aggregate no-render CLI baseline = 29.28s)

1. **(c) bbox/spatial prefilter** — ~10.35s (35.3%), confirmed absent from `checks.py`, scales with assembly size, no known correctness risk (a bbox miss is a mathematically sound early-exit before the expensive exact boolean test).
2. **(a)+(b) as one combined solid cache** — ~4-8s depending on cross-run hit rate; design as a single in-memory-then-persisted cache, not two mechanisms.
3. **(d) per-pair verdict cache** — plausibly large for iterative editing loops, but needs its own edit/rebuild benchmark methodology before a number can be trusted; likely most of its addressable cost will already be gone after (c).
4. **(e) multiprocessing** — lowest priority, highest implementation risk (non-picklable OCC objects); revisit only if (c)+(a/b) still leave a meaningful serial bottleneck.

**Not on the original list, but larger than every lever above in absolute
terms**: `geometry_hash`/`build_manifest` hashing is 28-44% of wall time in
every detail (often bigger than the entire interference sweep). It's
`core/buildinfo.py` territory, owned by task S2 — flagged here as evidence,
not touched.

## Concerns / methodology caveats

- **This baseline predates the S2 `geometry_hash` fix and should NOT be used
  as-is for an S3 before/after comparison.** It was measured at master
  `f932ae7`. Master has since merged `a5875c1`/`e5d8207`: `geometry_hash` now
  forces `BRepTools.Clean_s` before every `tessellate()` call, because the
  old code let OCCT silently reuse whatever mesh a prior exporter (e.g. the
  GLB export at tolerance 0.08, which runs immediately before
  `export_manifest`'s hashing in every one of these details' `_export`) had
  already left on the shape, instead of recomputing at the canonical
  `MESH_TOL_LINEAR`/`MESH_TOL_ANGULAR`. That reuse was an accidental
  cache-hit discount — the reviewer's microbenchmark measured it at ~27%
  per part — so (a) the `hash` phase mechanism this baseline measured has
  changed underneath it, and the ~28-44%-of-wall-time hash figures above are
  now understated relative to current master, not overstated; (b) anyone
  building the "before" side of an S3 4× comparison must re-run
  `scripts/benchmark.py` fresh on current master rather than reuse the
  numbers in this file directly.
- Only rock_anchor's `__main__` calls `cross_check()` (the constraint-solver
  verification pass); that call isn't broken out as its own phase, and is
  the likely explanation for rock_anchor's no-render CLI measurement running
  ~0.4-0.6s above what its instrumented phases alone predict. The other 3
  details don't call `cross_check()` in `__main__` and show a smaller,
  consistent ~0.2-0.45s gap (Python startup + BOM-table printing).
- The lever (a)/(b) savings estimates assume uniform per-instance cost
  within a component type; this is a reasonable approximation for near-
  identical fasteners but not verified at the per-instance level (the
  harness times by type, not by individual part).
- This is a single machine, single session's numbers — re-run
  `scripts/benchmark.py` before/after any lever lands using the identical
  methodology (that's the point of committing it) rather than trusting this
  file's absolute seconds on a different machine.
