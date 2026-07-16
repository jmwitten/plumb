# Hierarchical Spatial Validation — Birdhouse Spike

**Status:** approved for experiment design by Joel Witten on 2026-07-15

**Pilot model:** `details/family_birdhouse.spec.yaml`

**Scope:** measurement-only prototype; no production validation or evidence behavior changes

## Goal

Determine whether Plumb can preserve complete interference coverage without
enumerating and materializing every possible part pair. Use the real 28-part
family birdhouse as a certified subassembly, repeat it into larger synthetic
layouts, and compare a hierarchical spatial proof with the current flat
pair-universe oracle.

The spike must answer three questions:

1. Can one conservative envelope comparison prove that every part in one
   remote subassembly is disjoint from every part in another?
2. Can an unchanged subassembly reuse its internal interference certificate
   after another subassembly changes?
3. Can compact coverage certificates replace individual remote-pair PASS
   findings without losing any collision candidate or accounting coverage?

## Non-goals

- Do not modify `validate_assembly`, `ValidationReport`, `EvidenceGraph`, the
  persistent caches, or generated project documents.
- Do not replace OpenCascade's exact solid-intersection narrow phase.
- Do not use mesh proximity as final geometric evidence; its result depends on
  tessellation quality.
- Do not claim that a connection graph alone proves remote spatial separation.
- Do not use wall-clock thresholds as test assertions.
- Do not make the synthetic multi-birdhouse layout a new product or deliverable.

## Why the birdhouse needs a scaling matrix

One birdhouse has 28 parts and therefore only 378 unique part pairs. Its current
benchmark already reports a sub-second interference phase, so a single instance
cannot demonstrate whether hierarchical accounting scales.

The spike repeats the same validated birdhouse geometry by rigid translation:

| Birdhouses | Parts | Flat pair universe | Internal pairs | Cross-birdhouse pairs |
|---:|---:|---:|---:|---:|
| 1 | 28 | 378 | 378 | 0 |
| 4 | 112 | 6,216 | 1,512 | 4,704 |
| 16 | 448 | 100,128 | 6,048 | 94,080 |

For 16 separated birdhouses, 120 birdhouse-envelope comparisons should prove
all 94,080 cross-birdhouse pairs disjoint. Each successful group comparison
therefore certifies 784 leaf-pair relationships without enumerating them.

## Experiment architecture

### Live geometry input

Compile and validate `details/family_birdhouse.spec.yaml` through the normal
production entry point. Extract each placed part's canonical authored id,
world-space conservative axis-aligned bounding box, local-geometry digest, and
world transform. The prototype may use the existing bounding-box and digest
primitives but must not change them.

Repeated instances are rigid translations of those real part bounds. Instance
ids are qualified as `birdhouse_NN/<authored-id>`. The model is compiled once
per base or edited variant; traversal repetitions do not rebuild CadQuery
solids.

For the bounded exact-check case only, the prototype retains each leaf's
immutable component reference and composes its original world frame with the
instance translation to create translated `Placed` handles lazily. It does not
build or fuse a 448-part synthetic product model merely to count spatial
candidates.

### Flat candidate oracle

The oracle enumerates every unique leaf pair and applies the current
`bbox_prefilter_gap` rule. Its output is the canonical set of leaf pairs whose
conservative boxes overlap or lie within the threshold. These are the pairs the
unchanged exact narrow phase would have to examine.

The oracle is deliberately a bounding-candidate oracle, not another 100,128-pair
OpenCascade boolean run. If the hierarchical traversal emits exactly the same
candidate set, the existing exact narrow phase receives identical inputs by
construction.

### Hierarchical traversal

Each birdhouse instance is one group node whose box is the conservative union
of its 28 leaf boxes.

- Internal relationships use a certificate keyed by the birdhouse content
  digest, relative part transforms, tolerance fingerprint, and algorithm
  version.
- For two group nodes whose inflated boxes are disjoint, emit one group
  separation certificate and do not enumerate their cross-product leaf pairs.
- If two group boxes overlap or are within the threshold, descend and apply the
  ordinary leaf bounding-box rule to their cross-product.
- A changed instance invalidates its internal certificate and its group box.
  Unchanged instance certificates remain reusable.

The spike uses one group level because that is sufficient to test the claim.
It does not introduce a general BVH implementation. A production design may
later replace the list of group nodes with a balanced hierarchy without
changing the certificate contract.

### Compact evidence projection

The prototype writes a JSON result containing:

- assembly and algorithm fingerprints;
- total mathematical pair universe;
- pairs covered by reused internal certificates;
- pairs covered by newly computed internal certificates;
- pairs covered by group-separation certificates;
- leaf pairs examined after hierarchy descent;
- exact-narrow-phase candidate pairs;
- failures or accounting anomalies;
- certificate count and estimated serialized size;
- flat and hierarchical traversal timings as informational measurements.

It does not create one PASS record per pair eliminated by a conservative group
bound. The accounting identity must always hold:

```text
reused internal pairs
+ recomputed internal pairs
+ group-certified remote pairs
+ descended remote pairs
= total pair universe
```

Candidate pairs remain individually addressable because they continue into the
existing narrow phase. A group certificate must be expandable for debugging to
show its two group ids, boxes, threshold, digests, and number of covered leaf
pairs.

## Scenarios

### 1. Separated scaling matrix

Run 1, 4, and 16 birdhouses on a grid whose spacing is derived from the live
birdhouse envelope plus the configured threshold. Assert exact equality between
the hierarchical and flat candidate sets.

For 16 instances, assert that 120 group comparisons cover exactly 94,080 remote
pairs and that no remote leaf comparison is required.

### 2. Deliberate cross-instance overlap

Move one birdhouse toward another by a distance derived from the live envelope,
guaranteeing group-box overlap. The hierarchy must descend for that group pair.
Its resulting leaf candidate set must exactly equal the flat oracle's set; this
prevents a hierarchy that is fast only because it silently misses collisions.

Run the unchanged exact interference function on the resulting candidate set
for this bounded negative case and record the unexpected-overlap signatures.

### 3. One-instance roof edit

Compile a second birdhouse variant by overriding `roof_len` from 7.5 inches to
9.5 inches. Replace one instance in the 16-birdhouse layout with the edited
variant.

Assert that:

- the edited instance has a different certificate key;
- its internal certificate and group envelope are recomputed;
- the other 15 internal certificates are reused;
- every group relationship touching the edited instance is reconsidered;
- the hierarchical candidate set still exactly equals a fresh flat oracle.

This proves invalidation behavior without pretending that connection success
alone constrains the edited roof's spatial reach.

## Measurements and decision rules

The prototype records deterministic work counts and informational timings.
The architecture is promising only if all of the following hold:

1. **Soundness:** hierarchical candidate set equals the flat candidate set in
   every scenario; no missing candidate is tolerated.
2. **Complete accounting:** the coverage identity equals the full pair universe
   in every run.
3. **Hierarchical elimination:** the separated 16-instance case replaces
   94,080 remote leaf relationships with 120 group comparisons.
4. **Incremental reuse:** the roof edit reuses exactly 15 of 16 internal
   certificates and invalidates the edited one.
5. **Compact evidence:** remote disjointness is represented by group
   certificates, not 94,080 individual PASS records.
6. **Determinism:** repeated runs produce byte-identical candidate sets,
   certificate keys, accounting counts, and JSON apart from explicitly
   separated timing fields.

No wall-clock speedup is required from the one-birdhouse case. The spike tests
the scaling law, soundness, and evidence representation; a later production
pilot must measure the actual validation and pytest effects.

## Proposed implementation surface

Create only:

- `scripts/spatial_hierarchy_spike.py` — compile the birdhouse, construct the
  layouts, run both traversals, and write JSON under a caller-supplied output
  directory (defaulting to `/tmp`);
- `tests/test_spatial_hierarchy_spike.py` — deterministic count, soundness,
  overlap, edit-invalidation, and serialization contracts.

The script must import production geometry read-only. It must not write to
`details/`, `tests/baselines/`, `outputs/`, or the JoelBrain vault.

## Risks and controls

- **False negatives from approximate geometry:** use conservative BREP-derived
  boxes only. Disjoint boxes are a proof; overlapping boxes merely trigger
  descent.
- **Stale certificate reuse:** include geometry, relative transforms,
  tolerances, and algorithm version in the key. The roof-edit scenario proves
  invalidation.
- **Intentional fastener penetrations:** hierarchy only discovers candidates;
  existing expected-overlap semantics remain the narrow phase's authority.
- **Overstating timing gains:** separate compile/build time, flat traversal,
  hierarchical traversal, exact candidate checks, and JSON projection. Treat
  timings as observations, never assertions.
- **Synthetic-layout overfitting:** use envelope-derived spacing and overlap,
  not birdhouse-specific hardcoded coordinates.
- **Mistaking connection correctness for spatial proof:** connection edges may
  explain allowed contacts but never eliminate remote pairs without a
  conservative geometry certificate.

## Follow-on boundary

Passing this spike authorizes a separate production-design brainstorm; it does
not authorize direct integration. That design must decide how
`ValidationReport`, `EvidenceGraph`, affected-region invalidation, cache
lifetimes, and full-release verification consume hierarchical certificates.
The production implementation must retain an independent fresh full-coverage
gate and must not weaken UNKNOWN, expected-overlap, or delivery-hold semantics.
