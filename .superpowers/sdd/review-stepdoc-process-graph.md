# STEPDOC +process Task 2 — adversarial code review

Reviewed commits: `301eeab5c461ea3bd620514deba2589b03d71f64` plus fix
`dbeed165ae30f3585807b9ea968332177e24f6c3`.

## Initial verdict: FIX-FIRST

Core graph behavior was sound, but four trust-boundary constructions remained:

1. Unknown connection types with process authoring could leak or mislabel the
   registry diagnostic.
2. A malicious `ConnectionType.process_events()` hook could synthesize a fact
   stamped `authored_process_fact` without matching authored input.
3. Direct Python callers could supply duplicate point constraints; reverse
   lookup in derivation projection could then attach the wrong `why`.
4. Site-owned connection process facts reached capability validation only
   after site compilation/geometry rather than at declaration time.

## Fix and confirmation

- Capability validation resolves the registry once and preserves its normal
  known-types/suggestion teaching diagnostic for both local process facts and
  point-constraint sources.
- Produced authored facts are bidirectionally equal to the actual authored
  `Connection.process` tuple; type-created facts must carry type-default
  provenance.
- The event-graph boundary rejects duplicate targets and duplicate typed
  process references before edge or derivation-log generation.
- Site-owned connections reuse the shared capability gate before fragment
  compilation or geometry.

Six discriminating RED probes cover those attacks. Final evidence: **190
focused passes**, **66 site/spec passes**, six attack probes green, and clean
diff checks. Confirmation found no important regression or remaining gap.

Final verdict: **CLEAN — Task 3 may proceed.**
