# Tasks 3–5 Report — DB40 Reader-Surface Integration

## Outcome

Implemented the model-bound installation drawing projection, the three focused
HTML composers, and the one-pass four-file cabinetry document set as one TDD
increment.

- `installation_drawing_facts(project)` now projects cabinet-local bounds,
  global placement, compiled toe footprint, surveyed stud centers, cabinet-local
  anchor coordinates, common anchor elevation, selected screw geometry, modeled
  stack, stud embedment, high-floor datum, and typed release stamp.
- Missing or contradictory cabinet/toe/stud/strip/screw/hardware facts raise
  teaching `ValueError`s before a drawing can be rendered.
- The six shared views are now installed front, installation plan, anchor/toe
  section, isometric, exploded, and drawer detail. The primary sheet owns only
  the three installation views; the fabrication packet owns front/exploded/
  drawer-detail.
- Added frozen, validated `CabinetryDocumentLinks` and shared release,
  procurement-preflight, navigation, and responsive/print CSS projections.
- Added focused A0/I1 review/install, S1+ fabrication, and R1 audit composers.
  `build_cabinetry_html()` is a compatibility wrapper over A0/I1.
- Added one shared render helper returning the product assembly, six image data
  URIs, viewer payload, and raw GLB bytes. Both standalone and set generation
  use it.
- Added `build_cabinetry_document_set()` and retained
  `build_cabinetry_document_pair()` as a compatibility alias. The set compiles
  once, builds one manual, renders panels once, renders product assets once,
  and writes four linked documents.

No cabinetry pack geometry, validation rule, verdict, process graph, CPG order,
or stable landing basename changed. DB40 remains installation/use HOLD with the
same three UNKNOWN findings. The passing label is `Model/shop-data gate`;
purchasing/cutting preflight remains independently OPEN.

## TDD Evidence

Every Python command used the required environment:

```bash
PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python
```

### Baseline RED

Before production edits, the two focused files produced the expected Task 1
failure shape:

```text
16 failed, 14 passed in 28.39s
```

Fifteen failures were absent focused composers; the document-set failure was
the absent fabrication/audit paths and hashes.

### Task 3 exact-fact RED

Added three tests before implementing the projection:

- exact DB40 cabinet/toe/stud/anchor/screw/stack/embedment facts;
- a released DB42 width/site variant proving moved facts and no stale moved
  DB40 values;
- a missing-anchor invariant requiring a teaching error.

Focused RED:

```text
3 failed, 19 deselected in 4.20s
```

All three failures were the expected missing
`installation_drawing_facts` `AttributeError`.

Minimal projection GREEN:

```text
3 passed, 19 deselected in 3.80s
```

### Tasks 3–4 focused GREEN

After adding the dedicated drawings, link type, shared projections, and three
composers:

```text
22 passed in 13.00s
```

This covered exact drawing facts, reader labels, product-scene filtering,
release mutation, vocabulary, source ownership, surface ownership, and the
landing-page word/table/row budgets.

### Task 5 real-set GREEN

The 480 × 360 real document-set test passed:

```text
1 passed, 10 deselected in 10.67s
```

It proves one project compilation, one `_render_views` pass, four path/hash
pairs, reciprocal relative links, six shared panel assets, nine diagrams, and
viewer/GLB markers only on the landing sheet.

### Compatibility bug RED/GREEN

A standalone B30 probe exposed that the legacy `CabinetModel` intentionally
flattens common shell facts while `DrawerBaseModel` retains a `shell` aggregate.
The first projection had incorrectly depended on that DB40-only aggregate.

A regression was added to the existing door-base surface test before the fix:

```text
1 failed, 21 deselected in 3.45s
AttributeError: 'CabinetModel' object has no attribute 'shell'
```

The projection now derives the shared cabinet frame from the cabinet
declaration and site survey, then verifies it against named support parts. The
same focused test passed:

```text
1 passed, 21 deselected in 3.91s
```

The complete B30 standalone generator then wrote:

```text
/tmp/b30-single-doc-compat/b30.html (1,161,201 bytes)
```

### Final focused and broad GREEN

```text
33 passed in 26.63s
```

for:

```text
tests/test_cabinetry_project_report.py
tests/test_cabinetry_instruction_manual.py
```

The wider cabinetry/drawer/instruction/viewer regression gate produced:

```text
249 passed, 3 skipped in 35.15s
```

The skipped tests are pre-existing optional-path skips; there were no failures.

## Scratch Four-File Set

Generated at 480 × 360 under:

```text
/tmp/db40-task-3-5-scratch/
```

| Document | Bytes | Visible words | Tables | Rows | SHA-256 |
|---|---:|---:|---:|---:|---|
| `frameless_three_drawer_40_build_document.html` | 1,204,586 | 1,308 | 7 | 35 | `dca5f8c72f38a8681521a3c30749aaacd55d20dbae0da01579df97285cb5f757` |
| `frameless_three_drawer_40_assembly_manual.html` | 241,983 | 7,441 | 0 | 0 | `ccaf042a151bcb7844f61f22cae107161c51b3c99cd7351fe42f1cb8ca00b552` |
| `frameless_three_drawer_40_fabrication_packet.html` | 404,334 | 10,218 | 13 | 310 | `437905cb6ec2bc2e808f8d9a867020f2e67400b593a8d1aadfb03848cedcfb92` |
| `frameless_three_drawer_40_review_trace.html` | 49,306 | 3,386 | 3 | 133 | `8b2cd627434ec48cfe7709685cb14e318bd40852febf48362bfd9361d7cf5888` |

Visible metrics remove complete `<script>` and `<style>` blocks before stripping
tags. The landing sheet is below all accepted limits: 1,308/2,500 words,
7/8 tables, and 35/80 rows.

Viewer ownership in the scratch set:

- landing sheet: viewer and embedded GLB present;
- manual, fabrication packet, and audit trace: viewer and embedded GLB absent.

The six shared view PNGs were generated once under `views/`. The installed
front, installation plan, and anchor/toe section were visually inspected. They
show the HOLD stamp, field/countertop boundary, high-floor datum, toe footprint,
stud/anchor setout, wall finish with no anchorage credit, selected screw,
modeled stack, and stud embedment.

## Self-Review

- `CabinetryDocumentLinks` is frozen and validates all four hrefs as simple
  relative `.html` basenames, rejecting paths, schemes, drive ambiguity, and
  non-HTML names.
- No generic `surface=` branch or generic page framework was added. Each focused
  composer explicitly owns its content while sharing only release,
  procurement, navigation, and CSS projections.
- A0/I1 includes all three active UNKNOWN rules and every installation step id,
  but excludes shop and audit ledgers. It uses the typed installation policy for
  PASS/HOLD copy and retains CPSC source/scope links.
- S1+ contains the exact complete cut, edge-band, hardware, machining,
  fabrication, and assembly/shipping renderer outputs. It contains no
  installation sequence, audit ledger, viewer JavaScript, or GLB.
- R1 contains the exact complete findings/evidence and source-map renderer
  outputs. It contains no drawings, shop tables, process steps, viewer
  JavaScript, or GLB.
- Installation facts select named semantic roles and expected stable ids,
  require a one-to-one surveyed-stud/structural-screw/hardware-schedule match,
  check placed stud centers, selected catalog screw geometry, common anchor Z,
  common stack/embedment, and closed compiled toe geometry.
- Stack/embedment are independently projected from strip/screw/wall geometry
  and cross-checked against canonical anchor-path validation facts. Structural
  adequacy is not inferred from that geometry.
- The document-set orchestrator performs no second compilation and no second
  product-view render. Standalone single-document generation uses the same
  asset helper.
- `git diff --check` is clean. Intended changes are limited to the two report/
  orchestration scripts, the exact report tests, and this report; supplied Task
  3–5 briefs remain unchanged and tracked.

## Concerns

None within Tasks 3–5. Full desktop/mobile/print browser QA, adversarial reader
review, accepted-output regeneration, and delivery remain Task 6 work.
