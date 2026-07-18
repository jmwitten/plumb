# Birdhouse Assembly Clarity Design

## Outcome

The family birdhouse guide will use eight progressive panels with one physical goal per panel. Identical screws will be named once with a quantity and length, while the illustration marks every modeled head location and drive axis without numbered screw balloons. The interactive and static exploded views will consume canonical millimeter offsets and recover the intended large separation.

## Diagnosis

There is no four-panel cap. `derive_reader_steps()` folds unstaged connections inside the same subassembly into one reader step, and `_panel_cohorts()` groups by action, unit, and authored stage. Because the birdhouse declares only two stages, ten enclosure connections collapse into panel 1. Separately, `SpecDetail.explode_vectors()` returns bare inch-authored values while the manifest injector alone scales them to millimeters; the instruction-manual viewer and static exploded render bypass that injector and therefore move parts only 3–5 mm.

## Sequence

1. Attach the fixed side to the entrance front with two 1 1/2-inch screws.
2. Attach the extended back to the fixed side with two 1 1/2-inch screws.
3. Seat the recessed floor and secure it to front, back, and fixed side with six 1 1/2-inch screws.
4. Install the cleanout side on its two upper pivot screws.
5. Swing the cleanout side closed, install the lower latch screw, and verify movement.
6. Set and secure the roof with six 2 1/4-inch screws.
7. Verify the completed enclosure: floor recess, open drains and vents, seams, cleanout swing, and latch.
8. Attach the mounting cleat with two 1 1/2-inch screws; field installation remains on hold.

## Illustration Language

- Number only newly arriving structural parts in the picture key.
- Exclude installation fasteners from numbered callouts.
- For every current fastener, project the compiled `head_bearing` datum and `axis` into the image, draw an orange target ring at the head, and draw a short arrow along the drive direction.
- Show one panel resource chip per screw family, formatted as `Screw ×N — <length>, <head condition>`.
- Keep prior work ghosted and current structural parts and fasteners in color.
- A panel with no arriving structural part may have no numbered picture key; its screw targets and quantity chip are sufficient.

This follows the repeated-hardware convention in official West Elm, IKEA, Article, and Crate & Barrel instructions: inventory hardware once, show the current quantity, and use arrows/locations instead of separately naming identical fasteners.

## Compiler Boundaries

- Stage boundaries and acceptance copy are birdhouse-owned data.
- Fastener marker projection is reusable rendering vocabulary because it depends only on installation-fastener capabilities and canonical datums.
- `explode_vectors()` must honor the base `Detail` contract and return millimeters. Manifest injection must serialize the already-canonical values without a second scale.
- Do not impose a global panel-count cap. The regression instead constrains this product's panel scope and confirms that panel count is derived from authored stages.

## Verification

- Unit tests prove canonical explode units, no double scaling, structural-only numbered callouts, complete fastener markers, and the eight-panel schedule.
- The regenerated package is inspected for callout density, panel progression, screw target placement, desktop/mobile/print layout, and visibly large explode offsets.
- Run the family-birdhouse inner and release gates plus platform integration because the renderer and compiler contracts are shared.

