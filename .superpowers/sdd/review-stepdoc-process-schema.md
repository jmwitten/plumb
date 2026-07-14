# STEPDOC +process Task 1 — adversarial code review

Reviewed commit: `1ec9b8378fa92f046b788fc0c60d45f3aa90a2c0`

Verdict: **Task 2 may proceed.** No blocking Task 1 defect was found. Strict
loading, exact serialization, one-instance repeat rejection, retired/zero-
instance diagnostics, and compatibility defaults are coherent.

Two Task 2 acceptance seams remain:

1. Process capability must have one runtime authority. Task 1 necessarily
   checks the current spec registry key (`glued`), while Task 2 introduces
   `ConnectionType.process_events()`. Runtime resolved-reference validation
   must ask that hook/capability surface and fail loudly if the source does not
   actually produce `cure`; tests must pin capability rather than a display
   label.
2. `ResolvedAfter.chain` is currently inert. Task 2 must add a discriminating
   cross-fragment negative: target and source must belong to the claim's own
   fragment, no authored process edge may cross fragment boundaries, and a
   mismatched manual resolved claim must fail loudly.
