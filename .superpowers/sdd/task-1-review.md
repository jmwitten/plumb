# Task 1 Review — DB40 Surface Ownership Contracts

## Verdicts

- **Spec compliance: FAIL**
- **Code/test quality: CHANGES REQUIRED**

The new budget helper, four-file basename/hash checks, required link graph, and
positive fabrication/audit completeness checks are useful. The Task 1 suite is
not ready to drive the plan, however, because legacy exact assertions remain
bound to the monolithic primary HTML and directly conflict with the new surface
ownership contract.

## Critical findings

### 1. The target suite cannot become green without violating one side of its contracts

`test_db40_primary_sheet_owns_review_and_installation_within_reader_budget`
requires `Cut list`, `Machining schedule`, `Fabrication`, `Validation findings`,
`Evidence register`, and `Source map` to be absent from `build_cabinetry_html()`
(`tests/test_cabinetry_project_report.py:86-99`). The unchanged
`test_report_projects_shop_evidence_sources_and_all_process_phases` requires
those same headings, the shop products, catalog sources, and fabrication,
shipping, and installation step ids in that same primary output
(`tests/test_cabinetry_project_report.py:252-281`). Further legacy pins still
require detailed S1+ machining/procurement content on the primary surface
(`:351-378`) and full audit evidence links there (`:410-421`). The existing view
pin also requires every old raw `REQUIRED_VIEWS` image on A0/I1 (`:239-240`),
although the approved design moves exploded/drawer-detail views to S1+ and
replaces the raw side/plan installation views.

The missing composers hide this contradiction during the evidenced RED run.
Once they exist, the planned implementation must either duplicate S1+/R1
content onto A0/I1, breaking ownership/budget, or change these tests in a later
implementation task. That is not a valid frozen RED contract.

Preserve the exact facts by moving their assertions now: shop headings,
products, catalog sources, fabrication/assembly ids, tools, and machining
language to the fabrication composer; findings/evidence/source-link pins to the
audit composer; release, installation ids, key dimensions, and the intended
review views to the review composer. Also replace the legacy
`Fabrication/model gate: PASS` requirements at `:170`, `:174`, and `:230` with
the approved `Model/shop-data gate: PASS` plus separately pinned open
purchasing/cutting preflight. Requiring both labels would retain the exact old
text but violate the new readiness semantics.

## Important findings

### 1. The UNKNOWN safety contract self-weakens if a verdict regresses

The test derives its required rule ids by filtering whatever findings currently
have `verdict == "UNKNOWN"` (`tests/test_cabinetry_project_report.py:81-82`). If
an existing DB40 UNKNOWN is accidentally changed to PASS, that rule disappears
from the expected tuple and the new check becomes easier to satisfy. The matrix
check also requires only the structural-capacity label, not its UNKNOWN status
(`:67`), while the older generic `UNKNOWN — not qualified` assertion does not
associate UNKNOWN with a specific rule.

Pin the approved three DB40 UNKNOWN rule ids and their exact compiled verdicts,
then require the A0/I1 non-PASS presentation to expose those same rules and
statuses. Pin the four matrix entries as component/status pairs, including
`Whole-cabinet structural capacity: UNKNOWN`, rather than as four unrelated
substrings. This is necessary to enforce “no UNKNOWN becomes PASS.”

### 2. Negative ownership checks are markup-sensitive and incomplete

The primary exclusion recognizes only the exact serialization
`<h2>Heading</h2>` (`tests/test_cabinetry_project_report.py:94-97`), so an id,
class, whitespace change, or different heading level evades it. Fabrication and
audit exclusions compare complete private-renderer strings (`:139-155`); the
same forbidden ledgers rendered with a wrapper or small markup change would
pass. The audit check also does not exclude the other shop ledgers or the
GLB/viewer despite the R1 ownership contract.

Parse or normalize headings and assert forbidden ledger headings/record ids are
absent from each surface. Keep the exact renderer-output checks as positive
completeness checks, but do not use whole-block inequality as the sole negative
ownership check. Explicitly pin that R1 has no shop tables or viewer/GLB and
that S1+ has no installation step ids, finding/evidence ids, or source-map
targets.

### 3. The document-set contract omits the single-pass rendering budget

The real generation test correctly pins four stable basenames, file existence,
byte hashes, the approved relative link graph, and all prior six-panel/manual
metadata (`tests/test_cabinetry_instruction_manual.py:279-367`). It does not
assert the global acceptance rule that one document-set generation compiles the
project once and renders product views once, nor the Task 5 ownership rule that
only the review sheet embeds the viewer/GLB. An implementation that recompiles
or rerenders for each companion would pass.

Add call-count spies around the compiler and shared product-view render helper,
and assert viewer/GLB markers occur only in the technical/landing document.

## Minor findings

None.

## Review evidence

Reviewed the Task 1 brief, implementer report, frozen
`a8f589a..85c3756` diff, and the Task 1-relevant approved design/plan language.
The evidenced baseline and RED results were accepted; tests were not rerun
because no additional execution was needed to establish the contract
contradictions above.
