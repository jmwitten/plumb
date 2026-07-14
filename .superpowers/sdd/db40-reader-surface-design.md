# DB40 Reader-Surface Redesign

**Status:** Owner-authorized autonomous increment  
**Date:** 2026-07-14  
**Scope:** Presentation only. The cabinetry pack, compiled geometry, validation verdicts, process graph, and release semantics remain unchanged.

## Problem

The accepted DB40 technical build document is a 1.3 MB self-contained HTML file with approximately 11,600 visible words, 17 tables, and 453 table rows. Its length is not caused primarily by drawings. It is caused by four different reader jobs being printed in one uninterrupted stream:

- owner/design review;
- installation coordination and commissioning;
- shop fabrication and procurement;
- model/evidence audit.

About 75 percent of the visible text is the complete hardware and machining ledgers, PASS findings, evidence records, and source-map rows. Those records are useful in their own contexts, but their current placement makes the release boundary, setout, and installation story difficult to find. The existing raw right and plan renders are also product views, not usable installation drawings: the plan omits the surveyed wall/stud context and the right view carries no anchor or bearing annotations.

## Considered approaches

### A. Collapse the existing sections

Place the long tables inside closed `<details>` elements. This improves scrolling but leaves one document with four incompatible jobs, a large print surface, and ambiguous ownership. Rejected as a cosmetic treatment.

### B. Delete detailed ledgers from delivered documents

Retain only the short review/installation surface and rely on repository data for everything else. This is concise but makes a standalone handoff insufficient for a fabricator or outside reviewer. Rejected because cut, machining, procurement, and evidence trace remain legitimate deliverables.

### C. Generate a role-based document set from one compiled model

Publish a concise project sheet, illustrated assembly manual, fabrication packet, and review trace. Each surface consumes the same `PackedProject`; no reader-facing fact is copied into a second authoring source. This is the selected approach.

## Document set

### A0/I1 — Project Sheet & Installation Plan

Stable filename: `frameless_three_drawer_40_build_document.html`.

This remains the landing page and the assembly manual's reciprocal link target. It answers, in this order:

1. What is this object?
2. What is released, and what is still held?
3. Does the design fit the intended space and use?
4. Where does it sit relative to wall, floor, studs, and anchors?
5. What must be field-verified?
6. What sequence may be followed only after the hold is cleared?
7. Where are the assembly, shop, and audit companions?

Visible-content budget on DB40: at most 2,500 words, 80 table rows, and eight tables, excluding scripts and embedded model/image data. The full cut list, machining ledger, fabrication steps, PASS finding ledger, evidence register, and source map must not appear on this surface.

Required content:

- a four-part status matrix: design/model data PASS, purchasing/cutting preflight OPEN, whole-cabinet structural capacity UNKNOWN, and installation/use HOLD;
- dynamic fabrication and installation/use release state without relabeling procurement readiness as a model verdict;
- plain-language release boundary and the three active UNKNOWN findings;
- overall cabinet dimensions and the small set of drawer/front dimensions needed to review fit and appearance;
- dedicated installed front/setout elevation;
- dedicated installation plan with cabinet, toe, wall datum, studs, and anchor offsets;
- dedicated anchor/toe side section with modeled stack and embedment;
- optional non-controlling isometric and interactive 3D viewer;
- field-verification and signed-clearance checklist;
- installation-only hardware and manufacturer link;
- model-derived installation and unloaded commissioning sequence;
- links to M1, S1+, and R1.

Every installation drawing is stamped `COORDINATION ONLY` while installation/use is held. It must not imply anchor capacity, installation torque, countertop release, or authorization to load the drawers.

### M1 — Illustrated Assembly Manual

Stable filename: `frameless_three_drawer_40_assembly_manual.html`.

This remains the six-panel construction-process surface. Its first instruction points to the fabrication packet—not the landing page—for cut, edge-band, machining, and material signoff. Its navigation links directly to A0/I1, S1+, and R1 so the builder is never told to find rows in a document that no longer owns them.

### S1+ — Fabrication Packet

Stable filename: `frameless_three_drawer_40_fabrication_packet.html`.

This is intentionally detailed and intended for a shop worker or procurement reviewer. It contains:

- fabrication readiness, tools, material boundary, and vocabulary;
- front, exploded, and drawer-detail shop drawings;
- detailed dimensions;
- part key;
- cut list and edge-banding schedule;
- full hardware schedule with manufacturer links;
- full machining schedule and datum/control rules;
- fabrication and assembly/shipping steps.

It does not duplicate the installation sequence or the evidence/source-map ledger. It links to A0/I1 and M1.

### R1 — Review Trace

Stable filename: `frameless_three_drawer_40_review_trace.html`.

This is the optional model-audit surface. It contains:

- compact verdict counts and release boundary;
- full validation findings;
- evidence register;
- source map;
- model/generator provenance and direct source links.

It links back to A0/I1. The default sheet shows only non-PASS findings; R1 preserves the complete audit trail.

## Installation drawing contract

All displayed values are projected from named model facts through one `installation_drawing_facts(project)` function. Renderers must not own duplicate dimensions.

### Installed front/setout elevation

- cabinet outline, finished front shapes, pulls, toe line, and high-floor datum;
- overall width 1016.00 mm and height 876.30 mm for DB40;
- toe height 101.60 mm;
- front heights and 1.50 mm perimeter / 2.00 mm inter-front reveal policy;
- dashed anchor-strip band;
- surveyed stud/anchor centerlines at model-derived local X and Z values;
- dashed `FIELD INSTALLED / BY OTHERS / HOLD` countertop boundary.

### Installation plan

- wall plane and wall-left datum;
- cabinet global left offset and overall width/depth;
- toe-platform footprint from compiled toe-part geometry;
- surveyed stud global centers and anchor local offsets;
- front direction and a nondimensional field-survey strip for flatness, services, and obstructions.

### Anchor/toe side section

- cabinet depth, toe height/setback, anchor elevation;
- wall finish, anchor strip, stud, and selected screw path;
- selected screw length, modeled intervening stack, and modeled stud embedment;
- `NO ANCHORAGE CREDIT` on nonstructural wall finish;
- field-located stable-bearing shim symbol without invented shim count/location;
- dashed countertop supplier boundary.

The current raw side and plan renders are removed from the primary surface. Exploded and drawer-detail views move to S1+.

## Data and rendering architecture

1. Compile the project once and require fabrication release once.
2. Build the illustrated manual once from that exact project.
3. Render shared image/model assets once.
4. Project four HTML surfaces from the same project and shared assets.
5. Validate every companion href as a relative HTML basename.
6. Write all four files, then return paths and content hashes from the document-set generator.

The platform-level renderer exposes focused pure functions:

- `build_cabinetry_review_html(...)` — A0/I1;
- `build_cabinetry_fabrication_html(...)` — S1+;
- `build_cabinetry_audit_html(...)` — R1;
- `installation_drawing_facts(project)` — single drawing-fact projection.

Existing detailed table renderers remain reusable but are composed only into their owned surface. One shared procurement-preflight projection owns sheet-nesting, unresolved product/SKU, and by-others exclusions so the landing sheet, shop packet, and manual cannot phrase those boundaries independently. A validated immutable basename/link object owns every reciprocal document relationship. The shared instruction-manual type gains additive related-document links with an empty default, leaving non-cabinetry consumers unchanged. `build_cabinetry_html(...)` remains a compatibility wrapper for the new A0/I1 composer, and `generate_released_build_document(...)` continues to support single-document callers. `build_cabinetry_document_set(...)` becomes the normal DB40 delivery path; the old pair function remains as a compatibility alias during this increment.

## Truth and safety rules

- Presentation changes no model, graph, verdict, or release state.
- `fabrication_ready` is labeled as a model/shop-data gate, not a purchasing or cutting authorization; unresolved procurement preflight is shown separately.
- The default sheet derives release language from `InstallationUsePolicy`; no independent PASS/HOLD prose may drift.
- A held project must show the hold before any installation instruction.
- The 40 lb/drawer value is a design input, not an authorized commissioning load.
- Anchor coordinates are coordination geometry, not a capacity claim.
- Manufacturer links come from selected catalog records.
- Machine identifiers are not primary labels; visible part names use the shared reader vocabulary.
- The full audit trace remains available but does not compete with primary decisions.

## Acceptance tests

- DB40 A0/I1 stays within its visible word/table/row budgets.
- The primary sheet excludes all S1+/R1-only headings and includes all active non-PASS findings.
- The DB40 status matrix exposes the open sheet-nesting and edge-band procurement decisions without converting them into validation verdicts.
- S1+ contains every cut, edge-band, hardware, and machining record and all fabrication/assembly step IDs.
- R1 contains every finding, evidence record, and source-map target.
- The four documents link to the correct companions using relative basenames.
- Drawing-fact tests pin model-derived cabinet, toe, stud, anchor, stack, and embedment values and move under a released-width/site variant.
- The project compiles once per document-set generation.
- The illustrated manual retains six panels, nine typed operation diagrams, and the same process order.
- A release-state mutation changes the landing-page banner without an HTML edit.
- Desktop, mobile, and print-oriented visual checks show the release boundary and setout without horizontal overflow.
- A fresh installer/reviewer can identify the hold, overall size, field checks, anchor setout, and correct companion in under two minutes.

## Non-goals

- No structural or code approval is created.
- No current UNKNOWN is converted to PASS.
- No new anchor, countertop, load, torque, or clearance assumption is authored.
- The assembly manual is not redesigned in this increment beyond correcting its document references.
- The underlying cabinetry vocabulary or geometry is not changed.
