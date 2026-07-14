# Tasks 3–5 Final Confirmation

Date: 2026-07-14  
Final commit reviewed: `fd0215aa74239712e59283238009eaad3a32c79c`  
Fix range reviewed: `fa4d474..fd0215a`

## Result

- **PASS**
- **Critical findings: 0**
- **Important findings: 0**

The prior Important geometry-projection finding is closed. The final tree also
preserves the Task 3–5 surface ownership, release boundary, one-pass document
set, link closure, and model-backed drawing contract. The later builder-safety
manual, release-record, and drawing changes introduce no Critical or Important
regression.

## Prior geometry finding

`installation_drawing_facts()` now validates the absolute frame facts that the
previous confirmation found missing:

- every toe member must bear at the compiled floor high point;
- the anchor strip must match its expected cabinet/wall-local X, Y, and Z
  placement as well as its dimensions and rotation; and
- every surveyed stud must match its expected origin, rotation, height, width,
  and depth before its anchor path can be projected.

Independent probes against the final HEAD produced:

```text
raised toe frame: REJECTED — toe_front must bear on the compiled floor high point
shifted strip+anchors: REJECTED — anchor strip is incoherent with the compiled cabinet-local frame
shifted/resized stud: REJECTED — modeled stud/anchor path for 'stud_32' is incoherent with the survey, anchor strip, or selected screw geometry
```

The unmodified projection still returns the truthful section and anchor facts:

```text
toe material Y intervals: 76.20–95.25 mm and 555.125–574.175 mm
anchor-strip local Z: 755.65–857.25 mm
anchor local Z: 806.45 mm
modeled stack: 47.625 mm
modeled stud embedment: 31.75 mm
```

The section therefore shows the two actual toe-member intersections and the
void between them; it does not invent a continuous plinth or shim location.

## Task 3–5 contract and final-fix regression review

- DB40 reaches the model/shop-data gate after base validation and remains
  installation/use HOLD with the same three UNKNOWN rules:
  `cabinetry.performance.anchor_capacity`,
  `cabinetry.performance.physical_tests`, and
  `cabinetry.performance.whole_cabinet_capacity`.
- The landing page keeps the explicit `MODEL DATA PASS — DO NOT BUY OR CUT`
  boundary, stays within its reader budget, owns the three installation views,
  and is the only document containing the viewer/embedded GLB.
- The fabrication packet owns the complete shop ledgers and the blank per-part
  purchasing/cutting release record. It does not gain installation or audit
  ownership.
- The audit trace retains findings, evidence, and source-map ownership without
  shop tables, installation drawings, or viewer assets.
- All relative links in the regenerated four-file set resolve. Standalone
  generation remains restricted to explicitly supplied companion links.
- The held manual opens at its cover/inventory unless a panel hash is explicitly
  requested. Panel 6 begins with `DO NOT ANCHOR / INSTALL / LOAD` before tools,
  hardware, or imagery and includes the signed installation/fit record.
- The added drawer-hardware instructions and stabilizer sequence are derived
  from selected model/catalog facts. They do not alter the compiled process
  graph or CPG order.
- The original Task 5 brief pinned nine operation diagrams. The later
  builder-safety review deliberately adds the tenth stabilizer sequence diagram;
  the final document-set contract and tests consistently carry six panels and
  ten diagrams. This is the explicit reviewed scope extension, not an
  orchestration regression.
- The final two commits after `e496983` are CSS-only containment fixes for long
  inventory/resource identifiers and the fit-record table. The regenerated
  manual includes those exact rules; browser QA supplied for the final tree
  reports a 390 px body at a 390 px viewport and correct direct `#panel-6`
  positioning.
- Source inspection shows no cabinet geometry, validation verdict/rule, event
  identity/edge, CPG ordering, or stable landing-basename change in the final
  fix range. The validation-file change is reader-summary wording only.

The regenerated front, anchor/toe section, and exploded drawings were inspected
at source resolution. Annotation lanes are separated, the actual toe members
are visible, the wall-finish/stud labels do not collide, and the drawer groups
are separated into non-overlapping lanes.

## Fresh verification

Exact final-HEAD focused gate:

```text
PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python \
  -m pytest tests/test_cabinetry_project_report.py \
  tests/test_cabinetry_instruction_manual.py -q

52 passed in 31.07s
```

Additional checks:

- independent toe-Z, strip/anchor-YZ, and stud-placement/dimension mutations;
- regenerated link resolution and viewer ownership across all four documents;
- stop-banner ordering, no unconditional initial hash jump, signed fit record,
  cutting release record, and six-panel/ten-diagram manual structure;
- source-resolution inspection of `front.png`, `anchor_section.png`, and
  `exploded.png`;
- `git diff --check e496983..fd0215a` clean;
- final `git status --short --untracked-files=all` clean before this ignored
  confirmation record was written.
