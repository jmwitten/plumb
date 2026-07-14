# Tasks 3–5 Adversarial Review — DB40 Reader-Surface Integration

Review scope: `d00d38c..2b8626c`, the three task briefs, the implementer report,
the supplied review diff, and the two focused test files.

## Verdict

- **Spec compliance: FAIL**
- **Code quality: CHANGES REQUIRED**
- **Critical findings: 1**
- **Important findings: 4**
- **Minor findings: 3**

The four-surface orchestration is substantially in place: the stable landing
basename is unchanged, the DB40 release projection still reports installation/
use HOLD with the same three UNKNOWN findings, `Model/shop-data gate: PASS` is
separate from `Purchasing/cutting preflight: OPEN`, the set path compiles once
and invokes `_render_views` once, and viewer/GLB content is confined to the
landing sheet. The implementation nevertheless cannot ship as a model-bound
installation surface because its toe section invents bearing geometry and the
projection accepts several incoherent cabinet/strip/support arrangements.

## Critical

### C1. The anchor/toe section invents a solid support and locates a shim in a modeled void

`installation_drawing_facts()` collapses four individual toe members to one
outer bounding box (`scripts/cabinetry_project_report.py:327-347`). Both the plan
and section then hatch that whole box as material
(`scripts/cabinetry_project_report.py:1462-1467` and `:1567-1571`). The section
adds a hard-coded triangular shim at `toe_y0 + 30..55 mm`
(`scripts/cabinetry_project_report.py:1592-1600`).

For the actual DB40 model:

- toe envelope Y: `76.200..574.175 mm`;
- front rail material Y: `76.200..95.250 mm`;
- rear rail material Y: `555.125..574.175 mm`;
- drawn shim Y: `106.200..131.200 mm`.

The pictured shim is therefore entirely under open space, not a compiled toe
member. At either interior anchor X, a true side section intersects the front
and rear rails with a large void between them; the drawing instead depicts one
continuous solid plinth. This implies bearing/support geometry the model does
not contain. The `coordination only` title is not an adequate mitigation, and
the same renderer is used for installation/use-PASS B30 output.

The claimed closure invariant is also ineffective: moving `toe_right` onto the
same X as `toe_left` is accepted and still returns the full rectangular
footprint. The front/rear rails alone supply the overall X extrema, while the
check never verifies the two sleeper X positions.

**Required correction:** project all four toe-member rectangles, validate every
corner/adjacency in both X and Y, and draw the actual section intersections.
Do not draw a shim at a numeric location unless that location is a compiled or
field-entered fact; a non-geometric field-verification callout is sufficient.
Add negative tests for a missing/moved/collapsed sleeper and exact tests for the
material intervals shown by the section.

## Important

### I1. The “loud invariants” do not establish cabinet/strip/anchor coherence

The wall-gap check at `scripts/cabinetry_project_report.py:249-263` is an
identity: `cabinet_front_y` is defined as `wall_y - depth`, then the code checks
that `wall_y == cabinet_front_y + depth`. It cannot detect an incoherent placed
cabinet. No cabinet carcass member is inspected before returning the declared
cabinet envelope.

Targeted mutation probes also showed that the projection accepts:

- a `left_end` moved `+500 mm` in global X;
- an `anchor_strip` moved `+2000 mm` in global X, leaving both anchors outside
  the returned strip bounds;
- the collapsed toe-right condition described in C1.

In addition, `anchor_roles` is constructed with a dict comprehension
(`scripts/cabinetry_project_report.py:353-358`), so duplicate anchor roles can be
silently overwritten rather than rejected as a one-to-one violation. The
projection checks the screw's duplicated top-level dimensions but not its
geometry `params`, even though the canonical validation does.

These are direct gaps in Task 3's promised cabinet/toe/stud/strip/screw
invariants. A previously validated project normally starts coherent, but the
new function explicitly promises to reject contradictory geometry and the
tests already mutate a released model to exercise that promise.

**Required correction:** validate the placed cabinet members against a single
explicit global-to-cabinet-local frame; require anchor points to lie within the
strip; count anchor parts before building any mapping; and cross-check the
geometry params/catalog record. Add focused mutations for moved cabinet sides,
strip X/length, duplicate anchors, and catalog/part-param disagreement.

### I2. The release banner makes the desktop cover 1,238 px tall and degrades mobile/print

For HOLD projects, `_release_banner()` places the entire 792-character,
110-word `policy.reader_notice()` inside one status-grid cell
(`scripts/cabinetry_project_report.py:960-992`). Browser QA at `1440 × 1000`
measured a `1,238 px` header, with roughly `900 px` of blank space under the
short left column before the first cover section. This is not a concise typed
release summary.

At mobile widths the grid eventually becomes one column, avoiding the empty
left area but forcing a long safety block before any task content. Print keeps
the two-column header and inherits the same first-page waste.

**Required correction:** keep the status card to a short, explicit HOLD summary
and direct the reader to Active gates / signed clearance / Installation &
commissioning. Retain the complete hazard and clearance language in those
owned sections (the exact full notice already appears in `install.release_gate`)
and retain the CPSC source/scope links. Do not remove safety content merely to
shorten the header.

### I3. Standalone/default generation emits broken DB40 companion links, including for B30

`build_cabinetry_html()` always creates a four-name `CabinetryDocumentLinks`
value (`scripts/cabinetry_project_report.py:1228-1247`), and the review composer
always renders manual/fabrication/audit navigation. However,
`generate_released_build_document()` writes only the requested review file
(`scripts/cabinetry_project_report.py:1932-1958`). Thus the compatibility path
does not satisfy Task 4's requirement to keep single-document callers working.

A focused B30 composer probe emitted these hrefs twice each:

```text
frameless_three_drawer_40_assembly_manual.html
frameless_three_drawer_40_fabrication_packet.html
frameless_three_drawer_40_review_trace.html
```

None is created by the standalone call, and all three are DB40-specific names
inside otherwise generic B30 output. The four-file set has link closure; the
public/default compatibility route does not.

**Required correction:** make rendered companion navigation explicit. The set
orchestrator should pass all linked documents; the standalone wrapper should
render only companions it was actually given (or write the complete set).
Add a standalone B30/DB40 link-closure regression that checks every local href
exists and that generic output contains no DB40 basename.

### I4. Installation annotations already collide, and print/mobile shrink them further

The supplied scratch `front.png` has overlapping title, HOLD stamp, two anchor
callouts, and countertop-boundary text at the top edge. This follows directly
from placing every two-line anchor label at `cabinet.height + 18` while the
26 mm countertop boundary occupies the same band
(`scripts/cabinetry_project_report.py:1374-1384` and `:1416-1424`). The resulting
setout text is not reliably readable even at source resolution.

The shared CSS then prints the three dense review drawings in the default
three-column gallery; there is no print override to enlarge them
(`scripts/cabinetry_project_report.py:938-956`). Mobile uses one column, but it
still scales a raster full of 7–8 pt annotations down to viewport width.

**Required correction:** allocate separate annotation lanes (or move the HOLD
stamp outside the axes), and add a print layout that gives installation figures
one full row/page at readable scale. On small screens, preserve a usable minimum
image width with horizontal pan or provide a full-resolution/open-image affordance.
Add a lightweight rendered-image/layout assertion in addition to string tests.

## Minor

### M1. New drawing HTML trusts `images[view]` as raw attribute markup

`_drawing_figure()` interpolates `images[view]` into `src` without `_esc()`
(`scripts/cabinetry_project_report.py:1036-1041`). Production assets are
internally generated data URIs, so this is not presently an exposed production
exploit, but the public composer accepts caller-provided dictionaries and a
quoted value can inject an attribute. Escape/validate the URI and cover the
composer boundary with one hostile-value test. `_viewer_block()` has the same
legacy assumption for its isometric fallback and should be corrected alongside
the new surface.

### M2. Fabrication ownership copy contradicts the shared front drawing

`_shop_drawings()` says installation geometry is owned by the review sheet
(`scripts/cabinetry_project_report.py:1056-1063`) but embeds `front`, which is now
the installed setout view with stud/anchor centerlines, high-floor datum, HOLD
stamp, and countertop boundary. Sharing the front view may be intentional, but
the ownership statement is false. Narrow the sentence to the plan/section, or
give fabrication a clean shop-front projection.

### M3. The report module is oversized, but a wholesale extraction should follow the correctness fix

`scripts/cabinetry_project_report.py` is now 1,972 lines / 55 top-level
functions; this increment added about 948 lines while combining fact
projection, safety policy copy, three HTML surfaces, six drawing renderers,
viewer assets, and CLI output. The module docstring and README still describe
one all-in-one build document, which is no longer the generated surface.

This size is a real maintenance concern, but a large file move should not
replace the required C1/I1 repairs. Fix the projection/render contract first
with small pure helpers and exact negative tests. Then extract installation
facts/drawings and reader-surface composition in a separately reviewable
follow-up (or immediately after the fixes if Task 6 has not begun). A wholesale
extraction is **not** independently required before merge; the correctness and
link/layout fixes are.

## Verification notes

Per the review request, I did not rerun the already evidenced suites. I used
read-only inspection of the supplied diff/current files, the existing scratch
PNGs, and small focused probes for the exact disputed conditions:

- confirmed the DB40 toe-member and drawn-shim intervals above;
- confirmed moved toe-right, anchor-strip, and cabinet-side geometry is accepted;
- confirmed default B30 HTML emits DB40-specific missing companion hrefs;
- confirmed `git diff --check d00d38c..2b8626c` is clean.

The implementer's stated green suites remain useful regression evidence, but
their assertions do not cover the blocking conditions above.
