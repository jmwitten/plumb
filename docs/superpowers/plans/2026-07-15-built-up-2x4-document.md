# Built-Up 2×4 Document Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and deliver a complete Plumb model-backed document package for two eight-foot 2×4s mechanically laminated with alternating-side screws at twelve-inch centers.

**Architecture:** Author one governed declarative DetailSpec using existing lumber, structural-screw, and `cleat_screwed` vocabulary. Split the eight screws into two four-screw connections with reversed part order so each connection’s installation contract matches its actual drive direction. Reuse the standalone technical-document and generic instruction-panel engines, adding only a detail-specific view renderer and a thin document-pair entry point.

**Tech Stack:** Python 3.12, DetailSpec YAML, CadQuery/OCCT, Plumb validation and rendering, Matplotlib views, self-contained HTML, Obsidian Markdown.

## Global Constraints

- Use exactly two nominal 2×4 × 8-foot plies, wide face to wide face, actual assembly section 3 inches × 3½ inches.
- Use eight 0.22-inch × 2½-inch structural wood screws at 6, 18, 30, 42, 54, 66, 78, and 90 inches.
- Alternate screw heads between the two exposed broad faces at every consecutive station.
- Use no adhesive and make no structural-capacity, code-compliance, or use-approval claim.
- Automated tests are explicitly skipped by Joel and must not be represented as run or passed.
- Compiler generation, model validation, lifecycle gates, document rendering, link checks, and visual inspection remain required production evidence.
- Track elapsed generation/review time and record initial-context over-reading as an efficiency improvement opportunity.

---

### Task 1: Declarative built-up-member model

**Files:**
- Create: `details/built_up_2x4.spec.yaml`

**Interfaces:**
- Consumes: `details/built_up_2x4.design-review.yaml`, registered `lumber`, `structural_screw`, and `cleat_screwed` types.
- Produces: `compile_spec_file("details/built_up_2x4.spec.yaml") -> SpecDetail` with two lumber parts, eight screw parts, two direction-correct connections, exact dimensions, callouts, explode vectors, and contractor-facing report sections.

- [ ] **Step 1: Author the governed parameters and derived stations**

Use these authoritative values:

```yaml
params:
  member_length: 96.0
  stud_thickness: 1.5
  stud_depth: 3.5
  screw_diameter: 0.22
  screw_length: 2.5
  first_station: 6.0
  station_spacing: 12.0
  station_count: 8
derived:
  assembly_width: "= 2 * stud_thickness"
  screw_center_z: "= stud_depth / 2"
  final_station: "= first_station + (station_count - 1) * station_spacing"
```

- [ ] **Step 2: Place the two lumber plies and eight screws**

Place `ply_a` at `[0, 0, 0]` and `ply_b` at `[0, 1.5, 0]`. Place A-side screw heads at Y=0 and rotate +90° around X; place B-side heads at Y=3 and rotate −90° around X. Every screw is centered at Z=1.75 and at its exact X station.

- [ ] **Step 3: Declare two drive-direction-correct connections**

```yaml
connections:
  - type: cleat_screwed
    params: {n_screws: 4}
    parts: [ply_a, ply_b]
    hardware: [screw_06, screw_30, screw_54, screw_78]
  - type: cleat_screwed
    params: {n_screws: 4}
    parts: [ply_b, ply_a]
    hardware: [screw_18, screw_42, screw_66, screw_90]
```

Both connections must state that capacity is not analyzed and that the exact twelve-inch pattern comes from the owner brief.

- [ ] **Step 4: Add physical and dimensional validation declarations**

Declare the ply-to-ply contact, exact length, assembled Y width, each ply depth, outer faces at Y=0/Y=3, and first/final screw X centers. Add overall-length, actual-section, end-offset, and station-spacing callouts.

- [ ] **Step 5: Compile, validate, and generate model artifacts**

Run:

```bash
/usr/bin/time -p .venv/bin/python -m detailgen.spec details/built_up_2x4.spec.yaml
/usr/bin/time -p .venv/bin/python -m detailgen.spec details/built_up_2x4.spec.yaml --render outputs/built_up_2x4/model
```

Expected: successful compilation, ten placed parts, eight hardware-presence findings, contact/dimension findings with no physical failure, and STEP/GLB/manifest/report outputs. Do not run pytest.

### Task 2: Dimensioned views and standalone technical document

**Files:**
- Create: `scripts/render_built_up_2x4_views.py`
- Modify: `scripts/single_detail_report.py`
- Create after review: `reviews/visual/built_up_2x4-findings.yaml`
- Create after review: `reviews/visual/built_up_2x4-design-findings.yaml`

**Interfaces:**
- Consumes: compiled `SpecDetail`, its live namespace, assembly part transforms, rendered callouts, and review stores.
- Produces: `outputs/built_up_2x4/views/{iso,side_a,side_b,section,stations}.png` and a registered `single_detail_report` consumer.

- [ ] **Step 1: Render five model-backed fabrication views**

Create `render_built_up_2x4_views(detail=None, out_dir=None)` that compiles only when no detail is passed, reads the live assembly bounding boxes and screw centers, and emits:

- `iso.png`: full member and alternating hardware;
- `side_a.png`: A-face stations 6/30/54/78 inches;
- `side_b.png`: B-face stations 18/42/66/90 inches;
- `section.png`: 3-inch × 3½-inch actual cross-section;
- `stations.png`: dimensioned 6-inch end offsets and 12-inch station chain.

All printed dimensions must come from `detail.namespace`, not repeated literals.

- [ ] **Step 2: Register the standalone report consumer**

Add constants and a `CONSUMERS["built_up_2x4.spec.yaml"]` entry with the five views, owner-approved narrative, build notes, BOM/cut-plan copy, design-review disclosure, and explicit capacity/code holds. Use `render_views` to avoid recompiling the detail.

- [ ] **Step 3: Add initial review stores after viewing the generated PNGs**

Record visual findings against actual rendered files. Every unresolved limitation must remain `UNKNOWN` or a documented hold; do not invent proof from the images.

- [ ] **Step 4: Generate the technical document**

Run:

```bash
/usr/bin/time -p .venv/bin/python scripts/single_detail_report.py details/built_up_2x4.spec.yaml --out outputs/built_up_2x4/built_up_2x4_build_document.html
```

Expected: one self-contained HTML technical document containing all five embedded views, interactive GLB, BOM, cut plan, construction graph, coverage matrix, installation disclosures, sequence, findings, and current design-review state.

### Task 3: Assembly manual and commissioning sheet

**Files:**
- Create: `scripts/built_up_2x4_documents.py`

**Interfaces:**
- Consumes: `build_instruction_manual`, `render_instruction_images`, `render_instruction_manual_html`, and the registered standalone technical document.
- Produces: a reciprocal technical/manual pair plus `built_up_2x4_installation_and_commissioning.md` generated from live model facts.

- [ ] **Step 1: Build the generic instruction manual from the validated event graph**

Compile once, validate once, call `build_instruction_manual(detail, TECHNICAL_BASENAME)`, render content-keyed panel images, and write the self-contained assembly manual. Do not add caddy-specific station decorators.

- [ ] **Step 2: Generate the commissioning sheet from live facts**

Write a sheet that interpolates `member_length`, `assembly_width`, `stud_depth`, `station_spacing`, `first_station`, `final_station`, and hardware quantity from the compiled model. Include checkboxes for flush ends/edges, straightness, fully seated heads, no protruding tips, no splitting, count/station verification, and the explicit prohibition on treating this sheet as structural approval.

- [ ] **Step 3: Generate the linked package**

Run:

```bash
/usr/bin/time -p .venv/bin/python scripts/built_up_2x4_documents.py --out-dir outputs/built_up_2x4
```

Expected: technical HTML, assembly-manual HTML, commissioning Markdown, panel PNGs, and SHA-256 values printed as JSON.

### Task 4: Plumb review, delivery, and efficiency record

**Files:**
- Modify: `details/built_up_2x4.design-review.yaml`
- Create: `01_Projects/04_Side Projects/Plumb Built-Up 2x4 Experiment.md` in JoelBrain
- Copy generated artifacts to: `05_Attachments/Organized/Built-Up 2x4 Drawings/2026-07-15/` in JoelBrain

**Interfaces:**
- Consumes: current selection fingerprint, canonical spec payload, model fingerprint, generated package, visual review, and elapsed command timings.
- Produces: delivery-confirmed Plumb record, vault package, linked project note, pushed commits in both repositories, and a concise waste/time retrospective.

- [ ] **Step 1: Execute Plumb review without automated tests**

Load and follow `plumb-review/SKILL.md`, inspect all generated views and documents, check model/document fingerprint consistency, and record automated tests as `SKIPPED BY OWNER` rather than passed.

- [ ] **Step 2: Confirm model conformance and update governance**

Set `decision.application: implemented`, compute the canonical model fingerprint, and add delivery confirmation for Joel only after the reviewed package matches the selected concept.

- [ ] **Step 3: Deliver to JoelBrain**

Copy the approved model-backed HTML documents, commissioning sheet, design-selection report, GLB, STEP, manifest, validation/review trace, and representative PNGs into the dated attachment folder. Create an Obsidian project note with YAML frontmatter and shortest-path wiki links to every delivered artifact.

- [ ] **Step 4: Verify document integrity without running tests**

Check that every linked/embedded local asset resolves, HTML parses, output hashes match copied files, the vault note has no broken attachment links, and git diffs contain no unrelated changes.

- [ ] **Step 5: Commit and push both repositories**

Commit Plumb source/model/document changes on `codex/built-up-2x4-document`; commit the JoelBrain note and copied artifacts on `main`. Push both and report any blocked push as a hold.

- [ ] **Step 6: Report workflow efficiency**

Separate concept/process overhead from compilation, model generation, rendering, review, and delivery time. Record initial-context over-reading, mandatory three-concept governance, plan duplication, and any repeated compilation as improvement opportunities with concrete routing or caching recommendations.
