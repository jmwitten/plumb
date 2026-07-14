# Armchair Caddy +presentation Design

**Status:** APPROVED — this document consolidates the binding +presentation
requirements in `.superpowers/sdd/stepdoc-cpg-design.md`, the owner's approval
of the live IKEA-panel prototype, and the owner's explicit 2026-07-13 choice:
keep the illustrated instructions linked from the technical document, but in a
separate document.

## Goal

Produce a consumer-shaped, illustrated armchair-caddy assembly manual from the
same Construction Process Graph and compiled geometry that drive the technical
build document. Keep the technical document intact as the audit/evidence
surface. Deliver the two offline HTML files side by side with reciprocal
relative links.

## Approaches considered

1. **Separate linked manual generated from the model — selected.** The
   technical document remains dense and auditable; the manual can optimize for
   one-action panels, large images, and shop use. Both consume the same typed
   facts, so presentation cannot become a second construction model.
2. **Put illustrated panels inside the technical document — rejected by the
   owner.** This would make the existing document larger and mix two reader
   registers.
3. **Hand-author a conventional manual — rejected.** It would be quick, but
   dimensions, part names, hardware counts, cure order, and warnings could
   drift from the model—the defect class STEPDOC exists to remove.

## Delivered files

- `armchair_caddy_build_document.html` — existing technical/audit document.
- `armchair_caddy_assembly_manual.html` — new illustrated manual.

The technical header links to the manual using the relative basename above.
The manual header and footer link back to the technical basename. A pair
generator writes both; the ordinary technical-only API keeps its current
behavior and never emits a broken link.

## Architecture

### 1. Presentation model

`src/rendering/instruction_panels.py` owns a typed presentation model:

- `InstructionPanel` — content-key, title/action family, source reader-step
  indexes, visible/arrival/focus part ids, callouts, placement stations,
  resolved hardware/tool rows, process hold, order rationale, and honesty
  markers.
- `PlacementStation` — a geometry-derived label with two end distances, the
  physical reference member/end, second-axis datum, and image anchors.
- `InstructionManual` — title, ordered panels, unordered-part policy,
  technical-document basename, coverage/honesty summary, and part inventory.

The panel builder consumes the validated detail's existing `EventGraph`,
`derive_reader_steps()`, `build_sequence_model()`, resolved installation
contracts, shared `part_labels()`, `ProcessRecord` fabrication steps, and
world solids. It does not parse rendered prose or recompile connections.

### 2. Panel grouping and ordering

Panels group **consecutive runs of the one canonical reader-step order**; they
never perform a second Kahn pass or choose another valid linearization. The
builder scans `derive_reader_steps()` in order and joins only adjacent steps
with the same unit, authored stage, and action family. Process and join runs
always have a boundary before and after them. A panel never crosses an
authored-stage, bench-unit, process-kind, or join boundary.

The reader-step projection itself is total and fail-closed. Folding events
into install buckets can make a cyclic quotient even when the underlying CPG
is a DAG. Compatible ordinary install buckets in one quotient SCC condense
into the smallest truthful reader step; this restores the shipped platform's
18-step sequence (including five paired-hanger merges) and the unstaged
stool's three-step sequence. A default-folded, otherwise unclaimed placement
may instead become its own step when that is sufficient to preserve two valid
authored stages. Drives, process events, joins, explicitly staged parts, and
bench-unit members are never evicted. An SCC that still crosses one of those
hard boundaries raises `ReaderStepProjectionError`. Mapping and emission both
check complete, unique event coverage, and the document consumer refuses a
non-empty graph that produces zero steps.

The caddy's phase grouping is not invented by presentation. Each side-fastening
constraint names both cure events in `sequence.after`, adding the two honest
cross-rail facts needed to represent this declared batch workflow. Deleting
those cross terms deterministically restores the interleaved seven-panel
fallback; a reversion test pins that behavior. A two-stage glue/fasten amendment
was probed and rejected because stages order connection drive events, not the
intervening cure processes, so it does not make the cure steps consecutive.

The expected caddy structure is five panels, described by source content rather
than finished caption copy:

1. prepare — the bench unit's five fabricated structural members and their
   `ProcessRecord` fabrication facts;
2. bond — the two consecutive adhesive-connection reader steps and their typed
   preparation/fixture facts;
3. cure — the two consecutive cure events, each carrying its completion fact
   and every authored cross-cure rationale;
4. fasten — the two consecutive resolved side installations and all eight
   modeled fasteners;
5. join — the completed unit entering context, with no invented along-arm
   station or safety proof.

The cure panel says no generic duration is represented. The join panel carries
the caddy's connection-free-context **DECLARED TRUST** marker and says insertion
travel, stability, sliding resistance, structural capacity, and hot-drink use
are not proved.

### 3. Human instruction register

Captions are compositional rules over typed facts:

- reader names and ordinals come from `part_labels()`;
- prepare/cut/bore lines come from structured `ProcessRecord` content and its
  single `fab_note()` projection;
- bond/clamp/cure lines come from `ProcessFact`;
- fastener counts, sizes, head condition, entry member, and drive method come
  from `ResolvedInstallation` plus the actual fastener components;
- “why” boxes appear only for a typed technique rationale, authored `why`, or
  named not-analyzed gap;
- raw contract descriptions remain linked in the technical document and never
  become the panel caption voice.

A small technique vocabulary maps typed methods to icons and verbs
(`driven_straight` → drill/driver and “drive”; `cure` → clamp/hold). It may not
invent a product, timer, clamp count, pilot size, torque, capacity, or finish.
Where selection is unresolved, the manual prints a visible selection gate and
links to the technical assumptions.

### 4. Station-complete panels (CAT-M)

Every placement-critical panel must carry enough geometry-derived information
to place its parts without consulting prose elsewhere:

- the top-board cup-bore station comes from its `ProcessRecord` and remains in
  both-ends form;
- rail layout derives the distance from each top-board end, front/back flush
  datum, and underside datum from the world geometry;
- every rail-to-side screw station derives its distance from both rail ends
  and its drop from the top underside;
- panel images draw the same station anchors and dimension labels that the text
  prints.

For every both-ends station, the two distances plus the positioned feature
extent must reconcile to the reference length within tolerance. Missing or
inconsistent station data blocks manual generation. An adversarial spec
variant moves a screw/landing and must move both printed and image station
data; hand-typed literals cannot pass.

The caddy-specific station adapter selects meaningful construction datums but
all numeric values are measured from compiled world geometry. This is a
presentation adapter, not a second geometry model.

### 5. Images and content keys

`src/rendering/instruction_render.py` graduates the prototype's VTK/PIL path:

- prior work is ghost gray at 0.16 opacity;
- current arrivals/focus parts use their material colors;
- numbered part callouts and dimension lines are projected after the final
  camera is chosen;
- the camera fits the panel's arrival/focus bounding box with enough prior
  context to orient the builder;
- a process panel highlights the process connection's members without
  pretending a new part arrived;
- a join panel reveals the context body only at the join.

Each PNG filename is the SHA-256 of renderer version, the per-part world-
geometry hashes for only that panel's visible/arrival/focus ids, ordered source
event identities, camera, callouts, and stations. Existing files are reused
only on an exact key match. Changing relevant geometry or order must re-key;
geometry belonging only to a later panel, unrelated wording, and review
metadata must not. The HTML embeds PNG bytes as data URIs, so the manual itself
is portable even though keyed PNGs remain available as reproducible assets.

### 6. Navigation and viewer

The manual has previous/next buttons, keyboard arrows, a range control that
snaps to whole panels, and print CSS that shows every panel. The existing 3D
viewer receives optional panel metadata:

- each built part has a first-visible panel;
- context/unordered parts follow the manual's explicit policy;
- moving the assembly slider to panel `k` shows parts with first panel ≤ `k`;
- current-panel arrivals are highlighted;
- the assembly slider composes with, and does not reset, the explode slider.

Payloads without panel metadata render exactly as before.

## Error handling and honesty

Manual generation is fail-closed. It raises a teaching error when it cannot
map a graph step to a panel, when a panel lacks a visible/focus region, when a
placement-critical station is absent/inconsistent, when hardware ids do not
resolve, when a process fact lacks its typed content, or when either companion
basename is not relative.

The front matter says once that this is one machine-checked build order, names
the caddy's declared batch-workflow provenance, and says a blocking modeled
failure blocks release. It never calls independent-event tie-breaks uniquely
derived. It separately lists analysis gaps; silence never implies
capacity/code/hot-drink safety. Per-panel trust wording appears only for
declared-trust or named not-analyzed exceptions.

## Testing and acceptance

- Panel-model unit tests pin the five caddy cohorts, source event coverage,
  process/join boundaries, typed captions, shared reader names, exact hardware
  counts, and no `+X/-X`, raw part ids, or raw contract register in human text.
- CAT-J pins both content-key directions: order/geometry changes re-key affected
  images; unrelated prose/review changes do not.
- CAT-L uses the binding step-stool lever: the unstaged quotient condenses to
  three steps; two authored stages regroup it to two; removing them restores
  the three steps and edge set byte-for-byte. The staged form adds exactly four
  `authored_sequence` edges, affected render keys move through reader/source
  event fields, assembly geometry is identical, and all 137 validation finding
  tuples remain byte-identical.
- CAT-M pins station completeness and a moved-station mutation through model,
  text, and image overlays.
- Viewer tests pin panel snapping, arrival highlighting, explode composition,
  and legacy payload compatibility.
- Document tests pin two distinct HTML files, reciprocal relative links,
  portable embedded images, navigation, print expansion, safety/trust markers,
  and zero hand-authored step captions.
- Browser QA checks desktop and narrow layouts, navigation, images, links, 3D
  panel slider, hover reader names, and console errors.
- A fresh document-only handyman review asks verbatim: “could I place every
  part using only this page?” and compares the result to official manufacturer
  manuals.

## Explicit deferrals

This increment does not choose an adhesive/screw/finish product, add timers,
analyze clamp pressure, insertion travel, stability, sliding, capacity, code,
or hot-drink safety, or revise caddy geometry. It does not generalize every
station adapter to every detail. The production panel engine is generic; the
caddy is its first fully gated consumer.
