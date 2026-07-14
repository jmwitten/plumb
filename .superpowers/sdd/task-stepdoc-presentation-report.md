# STEPDOC/CPG +presentation implementation report

**Branch:** `codex/stepdoc-presentation`

**Base:** `aa8cd90`

## Result

The armchair caddy now has two self-contained, reciprocally linked offline
documents derived from one compiled detail:

- `armchair_caddy_build_document.html` remains the technical, validation, and
  evidence surface;
- `armchair_caddy_assembly_manual.html` is a five-panel illustrated shop
  manual optimized for chronological use.

The manual's prepare, bond, cure, fasten, and join panels are consecutive runs
of the canonical reader-step sequence. Presentation neither adds a second
linearization nor authors hidden construction facts. The caddy spec's two
project-specific cross-cure point constraints make its selected batch workflow
explicit; deleting them restores the deterministic seven-panel fallback.

## Reader projection repaired before presentation

The work exposed a pre-existing quotient bug: folding events into connection
buckets could create a cycle even when the construction graph was acyclic.
The old reader path could then silently emit zero steps or print steps with
backward technique edges.

The projection now:

- condenses compatible quotient SCCs into the smallest truthful reader step;
- can evict only an otherwise-unclaimed default-folded placement when that
  preserves two valid authored stages;
- rejects SCCs that still cross process, join, stage, unit, drive, or explicit
  placement boundaries;
- enforces complete, unique event ownership and forward inter-step edges;
- raises instead of rendering an empty sequence from a non-empty graph.

This repairs the platform from an invalid 23-step print order to 18 steps with
five truthful paired-hanger merges, and the unstaged stool from zero steps to
three. CAT-L pins the stool's three-step unstaged / two-step staged / exact
reversion behavior while all 137 validation findings and assembly geometry stay
identical.

## Model-backed presentation

The pure panel model consumes the event graph, reader steps, typed process
facts, resolved installation contracts, shared reader names, fabrication
records, and compiled solids. It derives:

- complete reader-step and source-event coverage;
- actual parts, quantities, dimensions, hardware, consumables, and unresolved
  product/tool selection gates;
- process holds and authored reasons;
- placement stations reconciled against compiled geometry;
- visible, arrival, focus, and context part sets for both raster panels and the
  staged 3D viewer.

CAT-M makes placement-critical panels fail closed. The cup bore, both rail
positions, side-board witness faces, clear opening, and all eight screw centers
come from geometry. The fasten image draws all four station rows across both
rails and its embedded metadata records the typed station references.

## Rendering and documents

Panel PNG names are content keys over renderer version, only the relevant part
geometry, ordered source events, camera, callouts, and raw station data. Cache
publication is validated and atomic. The HTML embeds the PNG bytes, so the
assembly manual travels as one file even though reproducible keyed assets are
also emitted.

The manual supplies typed SVG tool/hardware icons, previous/next and keyboard
navigation, whole-panel range snapping, print expansion, and prominent links
to the technical document. The technical document links back only when the
pair generator requests a companion, preserving ordinary technical-only
behavior.

The existing 3D viewer accepts optional panel metadata. It snaps visibility to
the current panel, highlights arrivals, composes with explode, uses the shared
reader labels for hover, and prevents hidden/future parts from raycast or
tooltip leakage. Payloads without panel metadata remain byte-compatible.

## Honesty boundary

The manual visibly distinguishes compiled facts from declared workflow and
unresolved selections. It states that a blocking modeled failure blocks
release. It does not claim insertion travel, stability, sliding resistance,
structural capacity, code compliance, or hot-drink safety. Product selection,
shop conditions, and representative validation remain explicit gates rather
than prose-filled assumptions.

## Verification and delivery

- Broad presentation/caddy/viewer regression selection:
  **100 passed / 3 skipped**.
- Fresh adversarial confirmation: **62 passed / 3 skipped** and final verdict
  APPROVE.
- Python compile checks, JavaScript syntax, diff hygiene, narrow-layout HTML,
  and live staged-viewer probes passed.
- Caddy geometry, 122 finding tuples, 13 event identities, the ten legacy view
  PNGs, and the legacy viewer payload remain unchanged.

The first full gate found one deliberate surface drift: the consolidated
platform golden still carried an empty Build Sequence. The failure reproduced
serially. Regeneration changed only that first build-sequence section from
empty to the pinned 18-step projection; every byte outside it and the second
detail's build sequence stayed identical. The golden selection then passed.

The final frozen tree passed:

```text
1521 passed, 3 skipped, 1 xfailed in 900.89s (0:15:00)
```

`origin/main` remained the reviewed base. A standalone `--ff-only` merge in a
clean integration worktree produced commit `c6a7326`, byte-identical to the
gated feature tree, and was pushed to GitHub `main`.

Merged generation emitted five keyed panel PNGs plus the linked document pair.
Live browser QA found five panels/images, 15 typed SVG icons, reciprocal links,
working panel navigation, both registration-rail labels, the blocking release
rule, no horizontal overflow, and only the expected missing-favicon 404.

Delivered SHA-256:

- technical: `a70f88b423dd9622d1988fbce190b4fded05620e557cfa5a07286d2df8d4c99d`;
- manual: `c042ef84379c19830f569958027b4e9aaee7f514b7307a406cb6be176c1bfafb`.

The exact relative-link pair was delivered to vault
`05_Attachments/Organized/Armchair Caddy Drawings/2026-07-14/` and
`~/Downloads/Build Documents/`. The vault copies were committed and pushed to
JoelBrain without staging any of that worktree's unrelated changes.
