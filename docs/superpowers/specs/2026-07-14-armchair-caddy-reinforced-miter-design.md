# Armchair Caddy Reinforced-Miter Production Design

**Date:** 2026-07-14  
**Status:** Approved for implementation  
**Decision owner:** Joel Witten

## Objective

Replace the armchair caddy's current five-piece double-wall production model with the selected three-panel, dowel-reinforced miter concept. The redesign must prove the selected concept through the platform's real fabrication, connection, validation, report, and instruction paths. It must not weaken the precedent-first lifecycle gate or imply analyzed structural capacity.

This increment implements the selected geometry. It does not mark the result delivered: delivery remains blocked until the owner reviews the generated model and manual and records confirmation against the exact model fingerprint.

## Evidence and Fixed Product Decisions

The implementation follows the retained precedent survey in `details/armchair_caddy.design-review.yaml`:

- Love & Renovations demonstrates a three-panel, 45-degree glued sleeve.
- Woodworker's Journal demonstrates a 3/4-inch hardwood sleeve reinforced with two 3/8-inch corner-key dowels per joint, positioned about 1-3/16 inches from the front and back edges.
- Rui Silva Studio demonstrates the clean three-surface furniture silhouette and treats the inner opening as a product dimension.

The production design therefore uses:

- three matching 3/4-inch hardwood panels;
- a 5-1/2-inch front-to-back panel width;
- a 6-1/2-inch clear opening around the modeled 6-inch arm, preserving 1/4-inch clearance per side;
- two 3/8-inch diagonal hardwood dowels at each miter joint, four dowels total;
- dowel stations 1-3/16 inches from the front and back edges;
- the existing centered 3-1/2-inch cup opening;
- 7 inches of clear side drop below the top's underside;
- eased exposed long edges, with joint faces left square for closure.

The top panel's outside long-point length is 8 inches: 6-1/2 inches of clear opening plus two 3/4-inch panel thicknesses. Each side panel's outside long-point length is 7-3/4 inches: 7 inches below the top underside plus the 3/4-inch top thickness. The inside miter points meet at the top underside while the outside points meet at the top surface, producing a continuous waterfall corner.

## Architecture Decision

### Chosen: reusable fabrication and connection vocabulary

Add a reusable hardwood panel component, a real `miter_crosscut` process operation, a wooden dowel component, and a `dowel_reinforced_miter` connection type. The caddy consumes those primitives declaratively from its DetailSpec.

This is the only approach that keeps all downstream outputs on the repository's existing truth path:

`stock -> fabrication steps -> folded solid -> placed assembly -> connections -> validation/evidence -> reports/instructions`

### Rejected: miter flags on generic dimensional lumber

Generic `Lumber` uses a local frame and SPF/PT material semantics aimed at construction stock. Adding furniture-panel miters there would make the panel face axes difficult to author and would misstate the selected material. The new component shares the process graph rather than overloading lumber's product meaning.

### Rejected: caddy-specific imperative geometry or prose-only joinery

Custom wedges, unrecorded booleans, or rectangular panels accompanied by miter prose would let geometry, cut notes, and construction claims diverge. That violates the fabrication-fold invariant and would make the selected concept appear implemented without modeling its defining features.

## Reusable Component and Fabrication Interfaces

### `HardwoodPanel`

Register a `hardwood_panel` component with this local frame:

- `+X`: long-point length;
- `+Y`: panel width;
- `+Z`: panel thickness and show-face direction.

Constructor data:

- `length`, `width`, and `thickness`;
- optional `miter_ends`, containing `near`, `far`, or both;
- optional `ease_radius`;
- the existing compiler-applied circular feature cut used for the cup bore.

Its fabrication record is authoritative and ordered:

1. crosscut stock to the authored long-point length;
2. ease the selected exposed long edges when requested;
3. miter-crosscut each declared end;
4. bore any compiler-applied circular feature.

The component reports 3/4-inch hardwood panel stock in the BOM and uses a registered indoor-hardwood material tag. It does not introduce species grading in this increment; the generic material statement is truthful while species/grade vocabulary remains a separate platform concern.

### `miter_crosscut` process step

Add an open-tagged `ProcessStep.miter_crosscut(end, angle_degrees, long_face, provenance)` operation. This increment authors 45 degrees and `long_face="top"`, but the fold uses the angle geometrically rather than hardcoding a caddy wedge.

Rules:

- `end` is exactly `near` or `far`;
- `long_face` is exactly `top` or `bottom`;
- `angle_degrees` must be greater than 0 and less than 90;
- a step's content identity includes its end, allowing one near and one far miter while rejecting duplicate cuts at the same end;
- the fold removes the triangular end wedge across the full `+Y` width;
- the cut note states the end, angle, and which face retains the long point.

Invalid tags or angles raise teaching errors before geometry is silently approximated.

### `WoodDowel`

Register a `wood_dowel` component as a finished cylindrical pin with its axis along local `+X`. It carries diameter and finished flush length, uses the hardwood material tag, and produces a BOM row for hardwood dowel stock. Four separate placed pins preserve per-joint and per-station provenance.

For a 3/4-inch square corner, each finished pin spans diagonally from the top show face to the side show face. Its flush length is `sqrt(2) * 3/4 inch`. The cylinder is placed through both members at the miter centerline; its two exposed ends read as the oval corner-key detail shown by the precedent.

## Reusable Connection Semantics

Register `dowel_reinforced_miter` as a distinct connection type rather than reusing plain `glued`.

Each connection declares:

- exactly two mitered structural panels;
- exactly two wooden dowels in a `keys` hardware role;
- connection-local assumptions naming hardwood miter faces, adhesive-label governance, and the unanalyzed capacity boundary;
- a typed cure process fact, using the selected adhesive label's completion condition rather than inventing a generic time.

The type derives:

- a member-to-member adhesive bond;
- the permitted geometric intersections between each dowel and both panels;
- graph evidence that the corner is `bonded_to` and `keyed_by` its mechanical pins;
- placeholder pull-out and shear transfer claims that name the mechanism while explicitly declining capacity;
- no screw/bolt installation contract, because wooden keys are drilled, glued, inserted, trimmed, and cured rather than driven under the fastener-axis vocabulary.

`keyed_by` becomes a recognized construction/load-path edge kind. It must appear in evidence and affected-region consumers wherever the existing `bonded_to` and `fastened_by` kinds are recognized. It does not create a gravity-bearing claim; any bearing remains separately declared.

## Caddy Assembly Geometry

The revised DetailSpec contains:

- the existing sofa-arm context;
- one top `hardwood_panel` with near and far 45-degree miters and the centered cup bore;
- two side `hardwood_panel` parts with a far-end 45-degree miter;
- four `wood_dowel` parts, two at each corner.

The rails and all eight structural screws are removed. No substitute registration part is introduced. The side panels themselves define the 6-1/2-inch opening and therefore supply the cross-arm registration geometry identified by the selected concept.

At the positive-X joint, each dowel runs from the top show face at the inner miter point toward the positive-X side show face 3/4 inch below the outside top corner. The negative-X joint mirrors that axis. Both joints repeat the same front/back stations.

The top continues to bear on the sofa arm by gravity. The caddy remains removable and unfastened to upholstery. The redesign does not claim longitudinal anti-slide performance, adhesive capacity, dowel capacity, cup-fit capacity, or hot-drink stability beyond the existing disclosed verification requirements.

## Lifecycle and Report Behavior

Before promotion, record the owner's modeling approval against the current selected-concept fingerprint. After the production geometry conforms to the reinforced-miter selection:

- set the design decision application to `implemented`;
- regenerate the design-review report so production promotion passes;
- regenerate the technical build document, assembly manual, model views, BOM, and validation evidence;
- keep delivery blocked because `delivery_confirmation` remains absent;
- present the exact generated result for owner inspection;
- only after owner confirmation, record the exact model fingerprint and allow delivery.

The customer manual remains separate from the design-review report. It may link to the build method and retained precedent where developer-facing provenance is useful, but it must not expose governance internals as customer instructions.

## Error Handling

The implementation fails loudly when:

- a miter end, face, or angle is invalid;
- duplicate miter operations target one end;
- a reinforced-miter connection has other than two panels or two dowels;
- declared dowel hardware is not a `WoodDowel`;
- the selected concept and production topology disagree;
- the generated model still contains legacy rails or structural screws;
- the fit opening, miter closure, dowel stations, or cup bore differ from the authored dimensions;
- delivery is attempted without confirmation bound to the exact implemented model fingerprint.

## Test Strategy

Tests proceed from reusable primitives to the governed product:

1. Process-graph unit tests prove near/far 45-degree wedges, arbitrary valid angles, stable identities, cut notes, invalid-input diagnostics, and the fabrication-fold invariant.
2. Component tests prove hardwood-panel BOM/material behavior, compiler-applied cup bores, and finished dowel geometry.
3. Connection tests prove role guards, bond and key edges, expected intersections, cure facts, unanalyzed transfer claims, and absence of screw-style installation verdicts.
4. Caddy end-to-end tests prove three panels plus four dowels, no rails or screws, 6-1/2-inch clear opening, closed miter seams, four correct diagonal pin placements, retained cup opening, regenerated BOM, and selected-concept conformance.
5. Lifecycle tests prove modeling approval permits promotion while missing delivery confirmation continues to block delivery.
6. Document tests prove the technical report and assembly manual describe the reinforced-miter workflow and contain no stale double-wall instructions.
7. Targeted tests run after each task. The complete suite runs from the clean isolated worktree before the implementation commit is pushed.

## Non-Goals

- No merge to `MAIN` before owner review.
- No delivery confirmation authored on the owner's behalf.
- No numerical adhesive, dowel, or panel capacity analysis.
- No general hardwood species/grade ontology.
- No rule that rails are intrinsically bad.
- No implementation of the rejected rabbet, pocket-screw, or bracket concepts.
