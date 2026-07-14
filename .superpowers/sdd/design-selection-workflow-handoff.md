# Precedent-first design selection — implementation handoff

**Status:** proposed next increment

**Recorded:** 2026-07-14
**Pilot detail:** `armchair_caddy`

## Why this increment exists

The caddy's current double-wall construction is mechanically explainable, but it is not a conventional solution for this product. Two nearly full-depth internal registration rails were added while locally repairing a butt-jointed concept: first to create hidden face-grain glue and screw connections, then extended to recover arm registration. The resulting design passed structural and process checks while adding two large parts, eight screws, two glue/cure operations, reduced fit tolerance, additional exposed end grain, and a more complicated manual.

The existing validators answer questions such as "is this connection modeled honestly?" and "is this build sequence possible?" They do not answer the earlier product-design question: "is this a good and reasonable construction strategy compared with established practice?"

## Precedent findings

Research on 2026-07-14 found many products and plans using the same three-sided saddle form, but no reviewed example using full-depth wooden inner rails.

| Source | Observed construction |
|---|---|
| [Love & Renovations](https://www.loveandrenovations.com/sofa-arm-table/) | Three boards, glued 45-degree miters, optional lining |
| [Woodworker's Journal](https://www.woodworkersjournal.com/project-sofa-armrest-table/) | Three mitered panels reinforced with diagonal corner-key dowels |
| [Kreg sofa arm table](https://learn.kregtool.com/plans/sofa-arm-table/) | Three boards joined with concealed pocket screws |
| [Lowe's](https://www.lowes.com/n/how-to/diy-sofa-arm-table) | Three boards joined with glue and screws through the top |
| [Mitre 10](https://www.mitre10.com.au/diy/how-to-make-a-couch-sleeve) | Three panels joined with glue and finish nails |
| [Full Hearted Home](https://thefullheartedhome.com/how-to-build-a-diy-couch-arm-table-tray-for-your-sofa/) | Three panels reinforced by small internal metal corner brackets |
| [Rui Silva Studio](https://www.ruisilvastudio.com/lusitano/sofa-armrest) | Premium commercial solid-oak saddle retaining the simple three-panel form |

The closest analogue to hidden internal reinforcement uses discrete metal brackets, not two additional wooden walls. Conventional designs strengthen the corner joint directly with miters, rabbets, dowels, splines, pocket screws, nails, or brackets. The side panels themselves register the caddy against the upholstered arm; felt, cork, or leather can provide grip, protection, and fit tolerance.

## Root-cause assessment

1. **Local iteration replaced concept selection.** Each change repaired the current design rather than reopening the construction architecture.
2. **Representation availability biased the result.** The language expressed flat faces, butt connections, glue areas, and screws more readily than common furniture joinery.
3. **Validation was mistaken for design quality.** A coherent model was treated as evidence of a sensible product.
4. **Precedent research happened after concept commitment.** Manuals were used to audit instructions rather than to select the design family.
5. **Novelty carried no burden of proof.** Adding two large parts did not require an explicit unmet requirement or comparison with simpler alternatives.
6. **The suggestion to use glue was interpreted too narrowly.** It led to adding a face-grain glue surface while preserving the butt-jointed geometry, instead of reconsidering the joint itself.

## Required workflow

Before detailed geometry, every governed new detail should carry a structured design-selection record containing:

1. A prioritized brief covering use, loads, fit range, appearance, skill, tools, required features, and constraints.
2. A precedent survey with comparable commercial products and real instructions, retained URLs, construction patterns, and takeaways.
3. At least three materially distinct concepts.
4. A comparison covering strength, part count, fasteners, operations, tooling, tolerances, material, appearance, skill, and instruction complexity.
5. A novelty/deviation review in which every unsupported feature names the requirement that forces it, or records an explicit exception.
6. A simplification review giving every part a unique purpose and asking whether joinery can replace it.
7. A selected concept with an evidence-based rationale.

This must become a machine-checkable platform gate rather than a prose checklist. It should be introduced by opt-in so legacy details continue to compile. Governed details must not be promoted or delivered when the record is incomplete. The resulting design-review report is a developer/owner surface and must not bloat the builder manual.

The gate must not contain product-specific rules such as "registration rails are bad." It should expose unsupported novelty and complexity through general evidence and comparison requirements. Honest, justified exceptions remain possible.

## Pilot acceptance

Use `armchair_caddy` as the first governed example and compare at least:

- the current double-wall design;
- a three-panel reinforced-miter design;
- a rabbet-and-dowel design; and
- a concealed pocket-screw or bracket design.

The first increment should produce an evidence-backed recommendation without silently changing production caddy geometry. Geometry redesign follows only after the workflow itself is working and reviewed.

Tests must cover incomplete precedent research, insufficiently distinct concepts, unsupported novelty, justified exceptions, missing part purposes, superficial or empty prose, and unchanged legacy behavior.

## Implementation brief for the next controller

Work in `~/Code/construction-detail-generator` (GitHub `jmwitten/plumb`, branch `main`). Use an isolated worktree and preserve concurrent work. Inspect the repository before choosing the exact integration, then implement the smallest reusable structured artifact, validation gate, command/pipeline integration, and generated developer-facing report that satisfy the workflow above. Do not hardcode the caddy outcome. Use the caddy to prove the general mechanism, obtain a fresh adversarial review, run focused tests and the full suite from the verified worktree import, and push a feature branch for owner review without merging it.
