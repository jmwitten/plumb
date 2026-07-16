# Built-Up 2×4 Member Design

## Goal

Generate a model-backed homeowner fabrication and assembly document for two eight-foot nominal 2×4 boards screwed together wide-face to wide-face at twelve-inch centers. The resulting actual section is 3 inches by 3½ inches; it is closer to, but is not dimensionally equal to, a nominal 4×4.

## Selected architecture

Use concept `alternating_mechanical_lamination` from `details/built_up_2x4.design-review.yaml`:

- Two nominal 2×4 × 8-foot lumber plies, straight and matched, with their 3½-inch faces clamped together.
- Eight 2½-inch structural wood screws located 6, 18, 30, 42, 54, 66, 78, and 90 inches from one reference end.
- Every consecutive screw head alternates to the opposite broad face.
- Every screw center is on the 1¾-inch width centerline.
- No adhesive, machining, finish, mounting hardware, or project-specific end connection is included.

The station pattern gives six-inch end margins and twelve-inch center-to-center spacing. Alternating faces records the selected fabrication pattern but is not presented as an engineered fastening schedule.

## Model and document surfaces

Author the build with the narrowest existing Plumb surface that can represent two lumber components, repeated structural screws, face-to-face contact, fastener overlap, BOM, cut plan, dimensions, and a build sequence. Prefer a declarative DetailSpec. Use an existing connection type only if its semantic claims match dry wide-face lamination; otherwise invoke Plumb Extend rather than mislabeling the joint.

Generate the established standalone package:

- governed design-selection report and current fingerprints;
- compiled 3D model, GLB viewer, STEP source, manifest, and validation report;
- dimensioned fabrication views showing overall length, actual section, centerline, end offsets, and every screw station;
- homeowner build document with BOM, cut list, clamping and alternating-drive sequence, inspection points, and explicit structural holds;
- assembly-state controls, exploded view, and review trace where supported by the existing standalone pipeline.

## Construction sequence

1. Select two straight, dry, matching 8-foot 2×4s; reject severe bow, twist, splits, or damaged ends.
2. Mark one reference end and a centerline on both exposed 3½-inch faces.
3. Mark stations at 6 inches and every 12 inches thereafter through 90 inches.
4. Align both boards with ends and long edges flush, then clamp the full-length mating faces tightly together.
5. Drive the first 2½-inch structural screw from face A at the 6-inch station without over-driving.
6. Drive each following station from the opposite face from the prior screw.
7. Confirm the final assembly remains flush, straight, fully seated, and free of protruding tips or splits.

## Honest limits and holds

- Structural capacity is not analyzed.
- No beam, post, guard, column, foundation, or life-safety use is approved.
- Species, grade, moisture content, preservative treatment, exposure, supports, loads, and end connections are unknown.
- The cited manufacturer precedents establish relevant product and mechanically laminated-member patterns; they do not validate the user-selected twelve-inch schedule for an unspecified use.
- The selected fastener must be compatible with the lumber treatment and exposure, and its current manufacturer instructions govern installation.

## Verification scope

Joel explicitly requested that all automated tests be skipped and treated as assumed passing. Generation, compiler validation, lifecycle gates, and document render checks are still recorded as artifact-production evidence rather than described as tests. Any skipped release requirement remains visible and cannot be relabeled as passed.

## Workflow-efficiency experiment

Record elapsed generation and review work, major tool calls, and avoidable process overhead. The first identified improvement area is initial-context selection: reading the full framework roadmap, the large progress ledger, and an ultimately irrelevant caddy spec added context without improving this small build. Future Plumb preflight should route small details directly to the applicable component, connection, governed-sidecar template, and document precedent.
