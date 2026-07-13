# Phase-0 installability sweep — raw results (2026-07-10)

Throwaway geometric probe (F1 head-bearing class) over every shipped spec: for each
screw, both shank ends were tested for material-on-both-sides; a screw with BOTH ends
buried has no accessible head as modeled. Tip-end 'material both sides' hits are
normal embedment and were discarded.

## FULLY EMBEDDED fasteners (no accessible head as modeled) — 14 across 3 details

| Detail | Fasteners | Flavor |
|---|---|---|
| armchair_caddy | rail-up screws x4 | (a) IMPOSSIBLE JOINT: head mid-plate inside the solid 1x6 rail (D6 resize kept the 1x2-cleat-era station). No real technique installs it as declared. |
| platform (zipline) | end-joist toe screws x6 | (b) UNDECLARED IDEALIZATION: toe_screwed names the real angled technique but MODELS a straight fully-buried fastener; heads never land on the exposed joist face. Buildable in reality; the model does not say it is idealizing. |
| step_stool | cleat screws x4 | (c) STATION-AT-INTERFACE: correct 1.25in length, head modeled AT the cleat-panel interface instead of on the cleat's free face (0.75in away). Buildable as documented (countersink note is on the free face); the model draws it unbuildably. |

## Clean details
sit_reach_box, sit_reach_frame (all heads on open faces), tree_attachment,
trolley_launch, rock_anchor (no screw-class fasteners flagged). site.spec.yaml not
compilable standalone (site 'kind' key), not swept — follow up when INSTALL v1 lands.

## Implication for the INSTALL design
The Phase-0 hypothesis ('the caddy is the only failure') is FALSIFIED — the class has
three flavors, and F1's mechanism must distinguish them: (a) FAIL; (b) requires a
DECLARED-idealization path (angled-technique fasteners must either be modeled angled
or carry an explicit idealization fact the doc discloses); (c) FAIL with a
station-not-face message (Phase 2's derived stations kill it at the root).

