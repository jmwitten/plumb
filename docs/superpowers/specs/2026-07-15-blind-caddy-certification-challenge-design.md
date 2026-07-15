# Blind caddy certification challenge

Date: 2026-07-15

Status: approved experiment design

## Objective

Test whether the generic build-certification gate retained the meaningful
rejection power of the former 53-node armchair-caddy gate. The challenge uses
one plausible alternative caddy design that is authored before either gate is
run. It is not a mutation constructed around individual assertions.

This is a rejection-equivalence experiment, not a claim that every legacy test
should fail or that every architectural difference is a construction defect.
The question is whether every meaningful legacy rejection category is also
visible in the generic gate or one of its deliberately retained physical
probes.

## Frozen product brief

Create a removable armchair caddy for the same modeled six-inch sofa arm. The
alternative remains a waterfall sleeve with:

- one hardwood top containing a centered 3-1/2-inch cup bore;
- two hardwood side panels with upholstery clearance;
- two hidden interior hardwood cleats below the top;
- ordinary structural screws fastening the side panels to the cleats;
- gravity bearing on the sofa arm and no fastening to the furniture; and
- honest omission of capacity, sliding-resistance, and hot-drink-stability
  claims.

The design should be internally coherent and should compile and validate if
the available construction vocabulary can represent it. Do not add malformed
geometry, dangling references, deliberately impossible dimensions, or
test-named metadata. Its expected rejections arise because it is an unapproved
replacement for the selected reinforced-miter design, not because the fixture
is intentionally corrupted.

## Frozen predictions

Before executing either test system, the cleated design is expected to differ
from the approved caddy in these categories:

1. **Architecture and governance** — it is not the selected reinforced-miter
   concept and has no matching approved selection/model fingerprint.
2. **Part and BOM topology** — the cleats and screws replace the four corner
   keys, changing component counts, BOM rows, and source IDs.
3. **Forbidden hardware** — screw parts are present even though the approved
   contract forbids screw- or bracket-named parts.
4. **Connection topology** — screwed cleat joints replace two `bonded_to`, two
   `keyed_by`, and their derived cure-order edges.
5. **Fabrication intent** — side/top operations and made-part coverage differ
   from the approved keyed-miter fabrication sequences.
6. **Physical selected-design invariants** — no closed miter geometry, diagonal
   key axes/stations, or four flush corner keys exist.

Compilation, non-empty solids, resolved connection endpoints, clean production
validation, BOM source-ID partitioning, and repeat evidence determinism are
expected to pass if the alternative is represented correctly. Those outcomes
are not to be changed after the first run; discrepancies become findings in the
comparison report.

## Experimental isolation

The committed alternative lives only under `tests/fixtures/certification/` and
is not discovered as a shipped detail. The experiment uses disposable git
worktrees so neither source tree is rewritten in place:

- **Legacy oracle:** commit `5e1498e`, the baseline containing the original
  53-node caddy gate.
- **Generic oracle:** the completed generic-certification branch containing
  one certification node and eight retained physical probes.

In each disposable worktree, copy the identical alternative spec over
`details/armchair_caddy.spec.yaml`, clear generated/cache state through the
existing test isolation, and run:

```bash
pytest --detail-gate armchair_caddy -q -n 4
```

The current tree keeps `details/armchair_caddy.cert.yaml` unchanged, so it
evaluates the alternative against the already-approved caddy intent. No result
from one run is reused by the other.

If the alternative cannot compile at the legacy commit because it uses newer
syntax, revise only its representation to the common vocabulary. Do not revise
its product architecture or the frozen failure predictions.

## Result classification

Capture every legacy and current node result. Classify legacy failures using
the committed equivalence-ledger vocabulary:

- **meaningful accuracy:** compilation, geometry, validation, connections,
  fabrication, BOM, governance, declared intent, or determinism;
- **retained spatial invariant:** physical geometry beyond v1 normalized
  evidence;
- **shared framework duplicate:** independently preserved by a named shared
  test; or
- **approved policy:** documentation/presentation behavior that is optional
  because the caddy declares no deliverables.

The comparison reports categories rather than demanding identical assertion
counts. One generic finding may replace several legacy assertions, while one
legacy node may fail for multiple reasons.

## Success and failure criteria

The experiment succeeds only if:

1. the alternative design and frozen predictions are committed before either
   oracle is executed;
2. the same spec bytes are used by both disposable worktrees;
3. every meaningful legacy rejection category is rejected by a generic rule or
   retained physical probe;
4. generic pass findings align with the frozen predictions and do not conceal
   contradictory evidence;
5. obsolete documentation/presentation failures are identified as policy, not
   falsely claimed as generic accuracy coverage; and
6. the ordinary approved caddy gate still passes after the experiment.

Any meaningful legacy category missed by the current gate is a certification
regression. Add a failing generic regression test, make the smallest
slug-independent correction, rerun the blind challenge, then run the ordinary
caddy gate. Do not edit the alternative to make the current gate look better.

## Permanent evidence

Commit:

- `tests/fixtures/certification/blind_cleated_caddy.spec.yaml` — the frozen
  alternative;
- a reproducible comparison harness or test that invokes both isolated
  oracles without saving certification results;
- `.superpowers/sdd/blind-caddy-certification-comparison.md` — predictions,
  exact commands, node outcomes, category mapping, gaps, corrections, and final
  conclusion; and
- focused regression tests for any newly discovered generic-engine gap.

Disposable worktrees and generated outputs are removed after their command
logs and hashes have been recorded. The shipped caddy spec and contract remain
unchanged.
