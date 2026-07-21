# Platform instruction precision

## Problem

The birdhouse manual has already moved away from one numbered balloon per
screw, but its prose still loses construction facts that are present in the
compiled model. Generic screw joints render the contract token `proud`
literally, modeled head stations are shown without transferable edge
measurements, and an authored stage can explain *why* it is ordered without
stating how to align or verify the work. The birdhouse also closes its
enclosure subassembly before the pole cleat is installed, so its authored
completion copy claims 21 screws while only 19 have occurred.

These are shared instruction-contract defects. Fixing only the birdhouse HTML
would create a second source of truth and would not improve later Plumb
packages.

## Design

### 1. A tight authored guidance surface

Extend sequence stages with two optional, single-sentence fields:

- `setup`: the physical alignment, support, clamp, or hole-preparation state
  that must exist before the modeled connection is installed.
- `check`: the observable acceptance check before the reader advances.

They compile through `AuthoredStage` to `ResolvedStage`. The instruction
projection prints at most one setup line before the generated install action
and at most one check line after it. `why` remains provenance for the order
claim and is not repurposed as an instruction.

Single strings are intentional: the surface encourages one scoped action per
stage instead of allowing another unbounded paragraph list.

### 2. Model-derived fastener layouts

Add a shared `FastenerLayout` instruction value. For every straight,
axis-aligned modeled screw group it records:

- the entry member and receiver member(s),
- the modeled screw ids and head points,
- the drive direction,
- two edge-datum coordinate phrases derived from the entry member's compiled
  bounds.

The formatter groups symmetric stations (`from each side edge`) and repeated
ordinates (`2 1/2 in and 5 1/2 in above bottom`) so the reader receives one
compact location line per connection. The same modeled fastener ids continue
to drive the orange targets in the diagram; the layout text supplies the
transferable measurements those targets lacked. Unsupported non-axis-aligned
geometry stays explicit instead of receiving guessed coordinates.

For fastener scenes, the shared camera biases toward the side of the assembly
where the current structural members sit. A left-side corner is therefore seen
from the left-front instead of being hidden behind its front board; centered
and right-side work retains the established view. This is geometry-derived and
does not add a project camera override.

### 3. Honest screw termination language

Introduce `seated` as the ordinary straight-driven screw head condition.
`seated` means the head bearing surface is snug against the entry member; it
does not claim a countersink or that every head style becomes visually flush.
The generic straight-screw helper uses `seated`. Pivot and removable latch
connections explicitly retain `proud` because that clearance is their modeled
service mechanism. Hardware rows say `Screw` once with quantity and length;
the procedural sentence carries the termination action.

### 4. State-derived closeout

When a bench unit joins the root, the instruction projection derives its
modeled installation-fastener count from the compiled unit membership and
prints that count before authored product checks. The birdhouse unit will own
the pole cleat and its two screws, putting its join/completion panel after the
cleat instead of between enclosure and cleat. Authored closeout copy will no
longer duplicate a screw count.

### 5. Birdhouse sequencing

Split the floor and roof stages so each ordinary fastener diagram installs one
connection. The two aligned pivot screws remain one operation because they
form one mechanism. The resulting manual has 11 scoped installation panels
plus one final closeout panel; there is no four-panel limit.

Each birdhouse stage supplies only the setup/check facts geometry cannot infer:
flush/recess/overhang datums, support and clamping, clearance-versus-pilot hole
preparation for the moving side, and an observable check. Screw centers,
direction, quantities, and head termination remain compiler-derived.

## Proof boundary

This change does not select a screw product, pilot diameter, countersink,
torque, coating system, pole, baffle, foundation, or field clamp. Those remain
manufacturer- or field-controlled holds. It improves the executable assembly
contract without inventing missing engineering capacity.
