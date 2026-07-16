# Built-Up 2×4 — Plumb Review Trace

Reviewed: 2026-07-15 (America/New_York)  
Reviewer: Codex for Joel Witten  
Lifecycle result: delivery gate passed; unresolved engineering facts retained as holds

## Authoritative sources

- Design selection: `details/built_up_2x4.design-review.yaml`
- Production model: `details/built_up_2x4.spec.yaml`
- Shop-view renderer: `scripts/render_built_up_2x4_views.py`
- Technical-document consumer: `scripts/single_detail_report.py`
- Document-pair generator: `scripts/built_up_2x4_documents.py`
- Visual findings: `reviews/visual/built_up_2x4-findings.yaml`
- Design findings: `reviews/visual/built_up_2x4-design-findings.yaml`

Generated HTML, PNG, STEP, GLB, JSON, and Markdown outputs were regenerated
from these sources. No generated HTML was edited.

## Governance fingerprints

- Selected concept: `alternating_mechanical_lamination`
- Selection fingerprint: `0badb26b2bb1e1c90523a430c0b37e1b513248d26cdc10d40145c4b7d9bbdea8`
- Model fingerprint: `36eb70fffd81e26e139b858f71428263675ff8d0b386a40f8eec864a30302c81`
- Decision application: `implemented`
- Modeling approval and delivery confirmation: Joel Witten, 2026-07-15

Both `detailgen.design_review validate` and the DetailSpec delivery gate
completed successfully after the fingerprints were refreshed.

## Fresh-generation evidence

- Final DetailSpec render: 10 parts; validation `CLEAN`; 56 genuine derived / 17 authored facts (3.3:1); 2.97 seconds.
- Final document pair: one technical HTML, one one-panel assembly manual, one commissioning Markdown sheet; 3.40 seconds.
- Final design-review report: 2.95 seconds.
- Technical HTML SHA-256: `ade680b1371c758553db2c8933d35de6e750fa4e945777f9b887e572eac91041`
- Assembly-manual HTML SHA-256: `a4948374300cbf4be33f089a46ad7f5924ca59a6a78805e654d6ca67b29c4df8`
- Commissioning Markdown SHA-256: `ed363965cfed0284db6097239277ad80c89d3f17f04e46e9553a3555ef4d7054`
- Fine GLB SHA-256: `5ee954333415d5839c28b258eaee75dbeae968b3bd2bc27fd55fca1b99c4f2cc`
- STEP SHA-256: `c25b5798ed1f1ebd0e3624fee730c633094f35596cc869db75a41d0d9a1435d5`

## Model and document review

- Production topology matches the selected concept: two 96-inch nominal 2×4
  plies, wide-face contact, no adhesive, and eight alternating-face screws.
- The actual 3 × 3.5-inch section and the 6, 18, 30, 42, 54, 66, 78, and
  90-inch stations appear consistently in the model-backed views and prose.
- Both drive-direction connections resolve with 1 inch of modeled receiving-ply
  bite. This is explicitly geometric evidence, not capacity evidence.
- Coverage reports PASS only for physical geometry, construction completeness,
  and fastener installability. Spatial intent, functional use, load-path and
  support/stability representation, structural capacity, and code compliance
  remain `UNKNOWN — NOT ANALYZED`.
- The single reader step includes both plies, all eight screws, both drive
  directions, required hardware/tools, and the surface-head condition.
- Browser review exercised the 3D open, dimension toggle, explode slider,
  assembly slider, and close control. The default camera makes the extreme-
  aspect-ratio member read as a thin line; V3 records this supplemental-view
  limitation while the five static views remain fabrication authority.
- The technical document was checked at 1280 × 720 and 390 × 844. Mobile table
  overflow was reproduced, repaired in source, regenerated, and remeasured at
  exactly 390 pixels with zero oversized images, tables, or canvases.
- The manual was checked at 390 × 844: one panel, one valid panel target, two
  reciprocal technical-document links, no horizontal overflow, and no caddy,
  sofa, cup, or hot-drink language.
- Print rules remove the screen border/shadow and hide interactive controls;
  the document has no horizontal overflow at a letter-page-sized viewport.

## Automated test status

`SKIPPED BY OWNER` — Joel explicitly instructed Codex to skip all automated
tests and assume they pass. No pytest, unit, focused regression, project, or
full-suite test command was run, and this trace does not represent them as
passing. Source regeneration, compiler validation, lifecycle gates, browser
inspection, and document-integrity checks were still performed.

## Remaining holds

- Species, grade, moisture, loads, supports, end connections, withdrawal,
  shear, composite action, structural capacity, use suitability, and code
  compliance are unknown and unapproved.
- The representative 0.22 × 2.5-inch structural screw must be reconciled with
  a purchased product and its current manufacturer instructions.
- The standard interactive camera is not optimized for this member's extreme
  aspect ratio. This is a presentation advisory, not a geometry or document
  release blocker.
