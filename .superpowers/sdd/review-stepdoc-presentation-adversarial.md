# STEPDOC +presentation adversarial review

**Reviewed:** 2026-07-13
**Base:** `aa8cd90`
**Initial head:** `b48da2b`
**Verdict:** REVISE; confirmation required after the correction round.

## Verified strengths

- Geometry hash, 122 validation finding tuples, and 13 event identities are
  byte-identical to base.
- The event-graph delta contains only the two intended authored cross-cure
  edges. Eight reader steps are covered exactly once by five consecutive panel
  cohorts.
- The manual invents no product, cure timer, clamp count, pilot size, torque,
  finish, capacity, or structural proof.
- The sofa-arm context is absent from the first four panel images and the
  legacy viewer payload is byte-identical when presentation metadata is absent.

## Blocking findings

1. The fasten image drew station annotations on only one of the two rails even
   though the typed panel owned four stations across both rails.
2. Future-panel parts remained raycastable through hidden parent nodes; a
   pinned tooltip could remain visible when its part disappeared on a backward
   panel snap.
3. VTK wrote directly to the final content-key path before the PIL overlay and
   metadata pass. An interrupted overlay could therefore poison the cache.
4. The document-pair compile-once test missed clean checkouts: absent ignored
   legacy views launched a subprocess that compiled the detail again.
5. Typed hardware/tool icon names rendered as the same generic bullet rather
   than actual silhouettes.

## Minor findings

- Add the promised footer link back to the technical document.
- State the blocking-failure release rule in the manual front matter.

The correction round must include discriminating tests, a live WebGL runtime
probe for hidden/pinned parts, and a fresh confirmation review.
