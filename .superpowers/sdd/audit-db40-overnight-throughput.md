# DB40 Overnight Throughput Audit

**Audit timestamp:** 2026-07-14 08:12 EDT  
**Scope:** Read-only forensic review of the overnight cabinetry/vanity arc and,
in detail, the DB40 reader-surface redesign through scratch generation.  
**Evidence freeze:** feature commit `2b8626c`; scratch files generated at
08:09:15–08:09:17 under `/tmp/db40-task-3-5-scratch/`.

## Executive verdict

The user's seven-hour observation is fair for the whole overnight arc, but it
is not accurate to attribute seven hours to shortening the DB40 document.
Repository evidence shows roughly **6 hours 15 minutes from the first recorded
overnight cabinetry commit (01:53) to the first revised four-file scratch set
(08:09)**. The first roughly 4 hours 40 minutes were the previously requested
DB40 model-truth/manual work and the double-vanity study. The DB40
reader-surface redesign began at 06:46 and produced a viewable scratch document
set at 08:09: **about 82 minutes** after its first design commit, or about 95
minutes after the old monolithic output was regenerated.

The revised result is materially better. The landing sheet falls from **13,825
visible words, 18 tables, and 454 rows** to **1,308 words, 7 tables, and 35
rows**. Its visible text is about 90.5% shorter. The detailed material was not
deleted: it moved into a fabrication packet and optional review trace, while
the assembly manual remains separate. This is the right product structure.

The execution sequence was not the fastest way to get there. It optimized
contract completeness before visible feedback: design, plan, RED tests, two
test-review rounds, link typing, link review, installation-fact projection,
three composers, and finally generation. That architecture made the first
visible artifact a Task 5 dependency. No revised HTML existed for the first 82
minutes even though the user's complaint was fundamentally about the reading
experience.

The geometry-heavy tests were **not** the main delay in this increment. The
recorded test commands for Tasks 1–5 total about **six minutes**. Most elapsed
time was implementation, verbose task/report production, reviewer handoffs,
and avoidable review-driven rework in the RED contract.

## Evidence and limits

### Direct evidence

- Git author/commit timestamps from `22cd7f5` through `2b8626c`.
- Output mtimes for the accepted 06:34 documents and 08:09 scratch set.
- `db40-reader-surface-design.md` and `db40-reader-surface-plan.md`.
- Task 1–5 briefs, reports, original review versions, final reviews, and
  `progress.md`.
- Recorded pytest durations in the task reports.
- Current and historical diff statistics.
- Scratch output metrics and hashes from `task-3-5-report.md`.

### What cannot be reconstructed exactly

- The local transcript does not expose exact user-message timestamps.
- Git timestamps bound completed work; they do not prove continuous active
  work between commits.
- Agent thinking, model queue time, and idle time are not separately logged.
- Some implementation, testing, review, and coordination overlapped inside the
  same commit interval.
- The first observable overnight commit is at 01:53; time between the user's
  request and that commit is unknown.

Durations below therefore distinguish high-confidence file/commit intervals
from inferred activity. They should not be read as timesheet precision.

## Wall-clock ledger: the apparent seven hours

| Start–end (EDT) | Elapsed | Observable outcome | Scope | Assessment | Confidence |
|---|---:|---|---|---|---|
| Before 01:53 | unknown | User request intake, research or setup before first commit | Earlier overnight task | Unallocatable from available evidence | Low |
| 01:53–02:06 | 12m | Base-language payload re-pin, model-backed DB40 hardware/instructions, unified reader labels | Earlier DB40 work | Necessary model truth and consistent naming | High for bounds |
| 02:06–05:28 | 3h 22m | Cabinet manual and double-vanity core; commit `0735943` changes 44 files, +7,250/−388 lines and includes the research/design records | Earlier user-authorized cabinet/vanity scope | Large but predominantly valuable implementation; not time spent shortening the DB40 report | High for bounds, medium for internal allocation |
| 05:28–06:16 | 48m | Double-vanity coordination study completed; 1,761 added lines; adversarial/naive reviews and the 967.92-second full-suite gate are recorded in the accepted handoff | Earlier vanity scope | Valuable closure and safety verification; roughly 16m is known full-gate latency | High for bounds |
| 06:16–06:34 | 18m | Accepted outputs regenerated: DB40 manual, 1.3 MB DB40 build document, vanity study | Delivery | Necessary delivery; exact split among generation, copying, browser QA, and final response is unknown | High for output mtimes, low for allocation |
| 06:34–06:47 | 12m | User reads the old document; first redesign commit appears | Feedback intake/design start | Reasonable transition, though no exact user-message time is available | Medium |
| 06:47–08:09 | 82m | DB40 reader-surface design, tests/reviews, typed links, installation drawings, three focused composers, four-file scratch set | Current redesign | Correct result, but too long to first visible artifact for a presentation problem | High |

From the first recorded overnight commit at 01:53:47 to scratch generation at
08:09:17 is **6h 15m 30s**. A request made tens of minutes before the first
commit would make the user's rounded “seven hours” entirely plausible.

## Detailed ledger: DB40 reader-surface redesign

| Start–end | Elapsed | Evidence | Likely work | Value classification |
|---|---:|---|---|---|
| 06:46:56–06:50:29 | 3m 33s | Design, plan, and procurement-preflight amendment commits | Role split, content budgets, safety boundary | Valuable design, but much more detailed than needed before a first draft |
| 06:50:29–07:01:17 | 10m 48s | Gap to Task 1 RED-contract commit; Task 1 brief mtime 07:01 | Briefing, dispatch, test construction, setup | Mixed: necessary setup plus coordination latency |
| 07:01:17–07:24:40 | 23m 23s | Initial RED tests, review-fix commit, re-review-fix commit, review closure | Surface-ownership contract and two review rounds | Safety/value findings were real; two rounds were avoidable rework caused by contradictory and then substring-vacuous test design |
| 07:24:40–07:36:42 | 12m 02s | Gap to typed-link implementation; Task 2 brief at 07:36 | Agent/task transition and implementation setup | Disproportionate coordination latency for a small additive type |
| 07:36:42–07:45:50 | 9m 08s | Typed links, one-line URI-scheme fix, final review | Link model and DB40 ownership copy | Link closure is useful; generic URI hardening was valid but low urgency before a visible page |
| 07:45:50–07:46:00 | 10s | Task 3 brief | Handoff | Negligible |
| 07:46:00–08:09:17 | 23m 17s to scratch | Task 3–5 implementation/report, scratch mtimes | Installation facts/drawings, three composers, one-pass document set, tests | High-value implementation; impressively fast once the visible product path began |
| 08:09:17–08:12 | ~3m | Report and commit `2b8626c` | Record and commit | Reasonable closure, not time to visible output |

### Recorded test and render time

The reports list about **361 seconds (6m 01s)** of test commands across Tasks
1–5:

- Task 1: 93.31s across baseline/RED/review-fix runs.
- Task 2: 138.51s across focused, compatibility, regression, and scheme-fix
  runs.
- Tasks 3–5: 129.20s across baseline, TDD loops, real generation, compatibility,
  and the 249-test broad gate.

These commands include the real 480 × 360 document generation and the wider
cabinetry/instruction/viewer regression set. Even allowing for unreported
probes, testing/rendering is a small minority of the 82-minute redesign.
“Geometry tests are slow” does not explain this episode. The known 16-minute
full-suite gate belonged to the previous vanity closure and has not yet been
rerun for the redesign.

## What the long document should be for

The old file conflated four readers:

1. An owner or designer deciding whether the cabinet is acceptable.
2. An installer surveying, anchoring, setting, and commissioning it.
3. A fabricator cutting, machining, procuring, and assembling it.
4. An auditor tracing every PASS, source, and model record.

No one should be expected to read all four jobs linearly. The user's estimate
that 80% was unreadable noise is consistent with the design audit: roughly
three quarters of the old visible content was complete hardware/machining,
PASS/evidence, and source-map ledgers.

### Content that belongs on the default review/install sheet

- Identity and one clear product image.
- Overall width, height, depth, toe geometry, and drawer/front arrangement.
- A status matrix whose first screen says what is PASS, OPEN, UNKNOWN, and
  HOLD.
- The three active UNKNOWN findings and the exact installation/use boundary.
- Installed elevation, wall/stud/anchor plan, and anchor/toe section, all
  stamped coordination-only while held.
- Field-verification and signed-clearance checklist.
- Installation-only hardware and manufacturer instructions.
- The sequence after the hold is cleared, plus unloaded commissioning.
- Direct links to assembly, fabrication, and optional audit material.

### Content that is valuable but belongs elsewhere

- Cut list, edge-banding schedule, full hardware schedule, machining ledger,
  part key, shop tools, and fabrication/shipping steps: **fabrication packet**.
- Six-panel illustrated build process: **assembly manual**.
- Every PASS row, evidence record, source map, and generator provenance:
  **review trace**.

### Content that can be removed rather than merely moved

- Duplicate explanations repeated in a validation finding, evidence record,
  and source-map row when the audit trace can link them once.
- Repeated safety prose after one prominent typed HOLD banner and one exact
  installation gate.
- Raw product side/plan views that do not show wall, floor, studs, bearings, or
  anchor dimensions.
- Vocabulary tables that merely restate the same visible/hover label without
  adding a fabrication identifier needed by the shop.
- Repeated PASS summaries on reader surfaces; a count plus audit link is enough.

The four-surface design is therefore sound. The mistake was making completion
of the whole four-surface system a prerequisite for showing the first concise
surface.

## Value assessment by work block

### Necessary implementation

- Splitting the landing, manual, fabrication packet, and review trace.
- Preserving all non-PASS findings and the installation/use HOLD.
- Model-derived installation facts and dedicated installed elevation/plan/
  section.
- One compiled project and one shared product-render pass.
- Relative companion links and actual target-file closure.
- Moving rather than deleting cut, machining, procurement, and audit truth.

### Valuable defect prevention

- Exact pins for the three DB40 UNKNOWN verdicts. The first Task 1 test derived
  expectations from whatever happened to be UNKNOWN, so an accidental UNKNOWN
  → PASS would have weakened its own test.
- Separating `Model/shop-data gate: PASS` from `Purchasing/cutting preflight:
  OPEN`. This prevents the page from presenting a modeled fabrication result as
  purchase/cut authorization.
- The first Task 1 review finding that old monolithic tests still required shop
  and audit content on the new landing sheet. Without correction, the suite
  could only become green by duplicating the content or breaking the new
  ownership rule.
- Exact file-relative link resolution. This prevents four files with plausible
  basenames but broken navigation.
- The B30 compatibility probe in Tasks 3–5. It found a real DB40-only aggregate
  dependency before the shared composer shipped.
- Installation facts that fail loudly when cabinet/toe/stud/anchor geometry is
  absent or contradictory.

### Avoidable rework

- Task 1's first RED suite contradicted legacy requirements. The review was
  useful, but the contradiction should have been found by the controller before
  dispatch.
- The first fix introduced a raw substring negative in which
  `install.countertop` collided with the legitimate finding id
  `cabinetry.install.countertop_support`. That forced a second review round for
  test correctness, not product correctness.
- Compile-once instrumentation initially patched one imported compiler alias
  but not the second. This was a test-harness detail that could have been
  designed after the shared generator existed.
- More than 1,000 lines of design, plan, briefs, reports, and reviews existed
  before Tasks 3–5 closed. Durable records are useful, but the granularity was
  out of proportion to an 82-minute presentation increment.

### Over-engineering or premature hardening

- A dedicated pre-implementation task for typed related links was not required
  to produce a safe first scratch sheet. Fixed internal basenames plus an
  existence check would have supported the first slice; the reusable type could
  follow.
- Rejecting `javascript:` and `mailto:` filenames is correct generic hygiene,
  but these hrefs are internally supplied constants. It did not materially
  improve the user's immediate document and should not have blocked first
  output.
- Byte-identical CSS behavior for unrelated empty-default caddy manuals is a
  strong compatibility property, but it was low priority relative to showing
  the DB40 page.
- Compile/render call-count spies are valuable for long-term performance, but
  they should be added after the visible slice, not ahead of it.

### Agent/setup and coordination latency

- Two obvious transition windows total about 23 minutes: 06:50–07:01 and
  07:24–07:36. Some implementation may be hidden in those windows, but the
  commit/report record shows task briefing and handoff as a significant share
  of elapsed time.
- Review was performed per micro-task rather than on one coherent visible
  slice. That produced high context-switch cost and low reviewer leverage.

### Testing/render latency

- Approximately six recorded minutes for the entire redesign: worthwhile and
  not the bottleneck.
- The earlier full suite took 16 minutes and is intrinsically expensive, but
  running it once on a frozen final tree is appropriate.

### Idle or unknown time

- The 3h22 earlier major-commit interval cannot be decomposed from Git alone.
- The 18-minute accepted-output delivery interval cannot be cleanly split.
- No evidence supports claiming that these windows were idle; they remain
  unknown rather than being assigned to coding or waiting.

## Which review findings paid for themselves

| Finding | Prevented shipped defect? | ROI judgment |
|---|---|---|
| Legacy tests required the removed ledgers on A0/I1 | Indirectly: prevented either duplicated bloat or an impossible green suite | High value, but avoidable controller miss |
| Exact UNKNOWN rule/verdict pins | Yes: prevents silent false-release regression | Very high |
| Separate purchasing/cutting OPEN from model/shop-data PASS | Yes: prevents misleading authorization | Very high |
| Normalize negative ownership checks | Helps prevent ledgers drifting back to the wrong surface | Medium-high |
| Exact-token fix for `install.countertop` prefix collision | No direct reader defect; repaired a faulty test | Necessary rework, low product ROI |
| Patch both compiler aliases for call counting | Prevents redundant compilation escaping the performance test | Medium, post-slice priority |
| Resolve hrefs to returned files | Yes: prevents broken delivered navigation | High |
| Reject scheme-bearing `.html` values | Theoretical generic click-risk; fixed inputs make exposure low here | Valid but low immediate ROI |
| Preserve empty-default HTML byte-for-byte | No DB40 defect; conservative cross-product compatibility | Low-medium |
| B30 model-shape compatibility probe | Yes: found a real shared-composer crash | High |

The lesson is not “stop reviewing.” It is to review the coherent reader
artifact and safety boundary, then batch lower-risk framework hardening. A
review that finds only test-harness precision issues should not keep the user
waiting for a first viewable page.

## Root causes of poor time-to-visible-output

1. **No first-artifact service-level objective.** The plan had budgets for the
   final page but no deadline for when a user could first see it.
2. **Waterfall dependency order.** Task 1 froze tests, Task 2 built links, Task
   3 built facts, Task 4 built composers, and Task 5 generated files. The user's
   experience could not change until Task 5.
3. **Audit-first legacy architecture.** The old generator treated every known
   fact as default reader content. Reader role and decision priority were added
   only after the model was complete.
4. **Reviews were attached to micro-tasks, not a product slice.** Two rounds
   were spent making intentional RED tests internally satisfiable before
   production behavior existed.
5. **Excessive task/report granularity.** The redesign produced design, plan,
   three briefs, multiple reports, multiple review versions, and ledger updates
   before the first HTML. This improves traceability but delays the user-facing
   loop.
6. **One large renderer module.** Installation projection, drawings, page
   composers, assets, and compatibility paths meet in
   `cabinetry_project_report.py`, making safe parallel implementation harder.
7. **No early content triage prototype.** The content move/delete decision was
   correct in prose by 06:50, but it was not immediately rendered as a simple
   HTML skeleton using existing facts.
8. **Correctness work was not explicitly prioritized by harm.** False release,
   omitted UNKNOWNs, and broken links deserved to block. URI schemes, byte
   parity, and compile spy aliasing did not need to block the first scratch.

## Revised execution playbook

### Stage budgets and deliverables

| Stage | Budget | Required output |
|---|---:|---|
| 0. Reader contract | 5m | One sentence naming the reader/job; must/move/delete section map; explicit safety invariants |
| 1. Existing-output triage | 10m | Automated words/tables/rows plus section inventory and top five decisions |
| 2. First visible slice | 15m | Scratch landing HTML using existing exact model facts; prominent HOLD; dimensions; non-PASS findings; existing image; links may be temporary but valid |
| **First-artifact deadline** | **T+30m** | A browser-openable page, clearly stamped scratch/coordination-only |
| 3. Useful install/review sheet | 20m | Field checklist, install sequence, status matrix, content under budget |
| **Useful-surface deadline** | **T+50m** | A reviewer can find size, hold, field checks, and next document in under two minutes |
| 4. Model-bound drawings | 35m | Installation fact projection and dedicated elevation/plan/section with loud invariants |
| 5. Companion extraction | 25m | Fabrication packet and review trace composed from existing canonical renderers |
| 6. Focused verification | 20m | Pure/unit tests, one real set generation, link closure, visible metrics, geometry/verdict invariance |
| 7. Batched review and browser QA | 20m | Reader review and adversarial safety review in parallel on the complete scratch set |
| 8. Fix/confirmation | 20m | Critical/Important fixes and one targeted confirmation |
| 9. Final gate/delivery | 25m | One full suite on frozen tree, regenerate, hash, copy, push |

Target: first artifact by 30 minutes, useful surface by 50 minutes, reviewed
four-file result in roughly 2.5–3 hours including the one 16-minute full gate.

### Parallelization rules

1. The controller owns the content map and first HTML skeleton.
2. One worker may own the model-fact projection and drawing functions.
3. A second worker may own companion extraction and link closure.
4. A third worker may perform a read-only reader audit of the scratch output.
5. Never assign two workers to the same production file. If both drawing and
   composition remain in one module, keep them sequential or first extract a
   narrow drawing module.
6. Do not dispatch an adversarial code review until there is a coherent visible
   slice. Run naive-reader and safety/code reviews in parallel on the same
   artifact.
7. Batch all non-Critical review findings into one fix round. A second round is
   confirmation, not a new broad audit.

### Test pyramid

1. **Pure projection/render tests, target <10s:** status/banner text, exact
   UNKNOWN ids, content ownership, word/table/row budgets, href validation.
2. **Model-fact tests, target <20s:** compile one immutable DB40 fixture and pin
   moving geometry facts. Mutation tests receive a deep copy or compile their
   own variant.
3. **One real document-set test, target <60s:** panels, views, hashes, viewer
   ownership, file-relative link closure.
4. **Affected cabinetry regression, target <2m:** selected from a maintained
   changed-file → test-family map.
5. **Full repository gate once, target current ~16m:** only after the tree and
   generated contract are frozen.

Use `.pytest_cache`/`--lf` only for the development loop, never as the final
proof. Record `--durations=25` and JUnit timing so future scheduling uses actual
history rather than intuition.

### Safe reuse of prior test/run knowledge

- Session-scope a compiled project only when its object graph is treated as
  immutable; mutation probes must copy or recompile.
- Cache render assets by spec-byte digest, geometry hash, view definition,
  image size, renderer version, and relevant dependency versions. Validate
  metadata before reuse and publish atomically.
- Cache visible-text metrics by HTML digest.
- Maintain an impacted-test map from files/modules to focused suites. Reuse the
  last green results during the loop, then invalidate on relevant source/test
  changes.
- Never cache validation findings solely by geometry hash: catalog, evidence,
  release policy, process graph, or source versions can change without geometry.
- Never skip the final uncached full gate or final generated-link/hash check.

### Review batching and prioritization

- Blocking tier: false PASS/release, missing non-PASS finding, invented
  dimension, broken install sequence, missing part, broken link, crash, or
  misleading drawing.
- Before-first-slice backlog tier: generic URI hardening, byte-identical CSS,
  performance call-count instrumentation, minor markup resilience.
- Run one naive-reader task: find the hold, overall dimensions, field checks,
  anchor setout, and fabrication companion within two minutes.
- Run one adversarial task: mutate release state, anchor geometry, width/site,
  and companion paths and prove the page changes or fails loudly.
- Stop broad re-review after confirmation reports no Critical/Important issues.

### Stop and pivot thresholds

- **No browser-openable artifact by T+30m:** stop framework work and render the
  minimal safe landing slice immediately.
- **No useful artifact by T+50m:** collapse remaining tasks and defer generic
  abstractions/hardening.
- **More than one review cycle on tests before production exists:** controller
  resolves contradictions and moves review to the coherent slice.
- **Task handoff/setup exceeds 10m:** collapse the task into the active worker's
  scope or rewrite the brief to one page.
- **Process/documentation lines exceed production lines before first output:**
  stop documenting and ship a scratch artifact.
- **Focused suite exceeds 90s:** run durations, isolate real rendering, and use
  a frozen fixture/cache for the loop.
- **A single renderer diff exceeds 500 lines before output:** extract a narrow
  module or intentionally cut scope.
- **Any Critical safety/truth finding:** stop publication, fix, and confirm.
- **Two consecutive review rounds find only test/format/generic-hardening
  issues:** backlog them and proceed to user-visible QA.

### Metrics to retain per document increment

- Time to first browser-openable artifact.
- Time to useful two-minute-reader surface.
- Final visible words, tables, and rows by reader surface.
- Primary-sheet percentage reduction and companion coverage.
- Generation time and render-cache hit rate.
- Focused, affected, and full-suite durations.
- Agent handoff/queue minutes.
- Review yield: Critical/Important findings per review round and whether each
  prevented a reader-visible or safety defect.
- Rework count: commits or lines changed solely to repair prior task/test
  design.
- Geometry hash and validation-finding signature before/after presentation
  work.
- Count of reader-facing numeric literals not projected from model/catalog
  facts; target zero for installation drawings.

## Preserving safety and model truth without repeating the delay

Speed does not require relaxing the platform's truth boundary. The minimum
safe early slice is straightforward:

1. Compile the same project once.
2. Display the typed HOLD and all active UNKNOWNs before any instruction.
3. Use only existing model/catalog facts; omit a drawing rather than hand-type
   a value that is not yet projected.
4. Stamp early installation drawings `COORDINATION ONLY`.
5. Keep geometry hash, validation finding tuples, and CPG order byte-identical
   across presentation-only changes.
6. Maintain a content-ownership manifest: every removed landing section is
   mapped to fabrication, manual, audit, or an explicit deletion rationale.
7. Run exact release/UNKNOWN/link/content-budget tests on the first slice.
8. Add deeper invariants and reusable abstractions after the reader can inspect
   the surface, then run one final frozen-tree gate.

This ordering preserves the strongest parts of the current work—one model,
honest HOLD/UNKNOWN states, model-bound geometry, complete shop/audit records,
and loud failures—while moving the feedback loop from 82 minutes toward 30.

## Final assessment

The redesign itself was not a seven-hour effort; it reached a strong scratch
result in about 82 minutes. That is not catastrophic for a four-document,
model-bound output split with three new installation drawings. It is still too
slow relative to the user's immediate need because **all 82 minutes elapsed
before any visible revision existed**.

The highest-leverage improvement is not faster geometry or fewer safety tests.
It is a different execution order: **render the smallest safe reader slice
first, then formalize, split companions, review, and gate around that visible
artifact.**
