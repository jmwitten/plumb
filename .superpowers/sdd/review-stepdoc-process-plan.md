# STEPDOC +process plan — adversarial review

Date: 2026-07-13

## Initial verdict: REVISE

The typed nested `after: [{cure: <connection>}]` shape was accepted, but the
first plan could falsely satisfy CAT-K in eight ways:

1. It inspected graph edges without bridging them to the delivered derivation
   log.
2. It treated the mixed free-text `Connection.assumptions` list as process
   instructions and left duplicate cure-before-screws prose alive.
3. It detected glue capability by comparing the display/provenance string
   `Connection.kind.label` rather than using an extensible type seam.
4. It proposed Cartesian repeat expansion, inventing order between unrelated
   instances.
5. It omitted process facts and actual point constraints from the shared
   epistemic-contract table.
6. It did not pin whether an `after` constraint gates every role group of a
   multi-role connection.
7. It proved edge existence but not falsifiable consumption by axis 3.
8. It did not explicitly pin process description/sorting, frame inheritance,
   R-1 participation, or direct process-fact carriage on `ReaderStep`.

## Revision

The implementation plan now requires:

- typed connection-local `process.cure` facts plus a generic
  `ConnectionType.process_events(conn)` hook;
- a safe `connectiontype_default` cure fact for unannotated `Glued`
  connections, with authored facts stamped separately;
- `sequence.after` as the sole owner of cross-connection cure-before-screws
  order, with all duplicate prose removed;
- loud v1 rejection of multi-instance repeat references rather than an
  invented all-to-all/pairwise mapping;
- derivation-log and epistemic-table bridges on both Markdown and HTML;
- all-role-group gating, an UNKNOWN-to-FAIL axis-3 falsifiability fixture,
  exact process event description/sorting/frame/R-1 tests, and direct typed
  fact carriage into reader steps.

## Confirmation verdict

**ACCEPTED.** All original findings are covered. Confirmation identified one
remaining compatibility ambiguity—whether an unannotated `Glued` connection
still gets a cure fact—and recommended the safe default path. The plan now
defines and tests that behavior explicitly.

