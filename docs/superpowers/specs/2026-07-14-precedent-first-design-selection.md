# Precedent-First Design Selection

**Status:** proposed for owner review

**Date:** 2026-07-14

**Pilot:** `armchair_caddy`

## Goal

Add a reusable, opt-in design-selection workflow that requires a governed
project to compare conventional product architectures before its model can be
promoted as production. A governed project may not cross that promotion gate
until its selected concept is approved, and it may not produce delivery
artifacts until the implemented model is confirmed to match that approval.

The first governed example is the armchair caddy. This increment produces its
evidence-backed recommendation and developer-facing design report without
changing the production caddy geometry or adding design-review prose to the
customer assembly manual.

## Why This Is a Separate Capability

The existing `detailgen.review` package records adversarial suspicions found in
renders. Those findings are post-model, may remain unresolved, and deliberately
do not change compiler verdicts. Design selection happens before modeling and
must gate later lifecycle stages. Reusing the visual-review model would make a
non-gating suspicion store responsible for a production approval decision.

The new capability therefore lives in `detailgen.design_review`. It owns a
structured review document, validation results, lifecycle gates, canonical
fingerprints, and a developer report. It consumes no CAD geometry and does not
alter physical validation, the Evidence Graph, or customer-document content.

## Approaches Considered

### 1. Sidecar design-review document with an opt-in DetailSpec binding — selected

Store the complete review in a sibling YAML document and add only a small
governance binding to opted-in DetailSpecs. This keeps early design evidence
independent of geometry, makes the review reusable by future project front
ends, and leaves legacy DetailSpecs unchanged.

### 2. Embed the complete review inside DetailSpec — rejected

This would give one file and one loader, but it would couple product research
to the geometry language, make the already-large schema harder to understand,
and prevent concept review from existing before a production spec exists.

### 3. Extend the visual-review finding store — rejected

This would reuse YAML loading and report widgets, but visual findings model
suspicions about existing renders. They have no concept comparison, approval,
or pre-model lifecycle semantics and are explicitly non-gating.

## Lifecycle

The governed workflow has four states:

1. `draft` — the brief, sources, concepts, and comparison may be edited.
2. `approved_for_modeling` — a named owner approved the selected concept and
   the approval fingerprint matches the canonical design-selection content.
3. `modeled_pending_confirmation` — production modeling exists, but no current
   confirmation binds the model input to the selected concept.
4. `approved_for_delivery` — a named owner confirmed the selected concept is
   implemented in the exact canonical production-spec revision being delivered.

Exploratory sketches, research, and unpromoted DetailSpec drafts remain allowed
in `draft`; the platform cannot and should not prevent someone from editing or
compiling a local draft. “Detailed production modeling” becomes a governed
state when the author asks the platform to promote that draft as the selected
production architecture. The promotion entry point requires
`approved_for_modeling`. Official render and document generators require
`approved_for_delivery`.

The second gate is intentionally conservative: any semantic change to the
canonical DetailSpec invalidates the delivery confirmation. The owner may
reconfirm an unchanged concept after inspecting the revision; the system does
not pretend to infer architectural equivalence from arbitrary CAD changes.

Direct compilation and use of low-level CadQuery/export primitives remain
explicit non-production escape hatches, as they are today. Such output is not a
promoted model or governed Plumb delivery artifact. The design-review promotion
command, `Detail.render()` for a governed compiled detail, and project-specific
document generators are the enforced production boundary.

## Structured Document

The committed sidecar uses schema `detailgen/design-review/v1` and contains:

- `project_id`, `title`, and `status`;
- `brief` with use, loads, fit range, appearance, builder skill, tools,
  required features, and prioritized constraints;
- `precedents`, each with stable id, source kind (`commercial_product` or
  `build_instruction`), title, publisher, URL, access date, observed
  construction pattern, and lessons;
- `concepts`, each with a stable id, summary, architecture signature, feature
  inventory, conceptual part families, and simplification answers;
- `comparison`, containing every required criterion for every concept;
- `deviations`, derived from concept features that cite no supporting
  precedent and therefore require a forcing brief requirement or exception;
- `decision`, containing the recommended concept, decisive comparison cells,
  tradeoffs accepted, and whether the recommendation is already applied;
- `modeling_approval` and `delivery_confirmation` records.

### Architecture signatures

Each concept declares these categorical fields:

- `load_path`;
- `joint_family`;
- `part_topology`;
- `fastening_strategy`;
- `visible_seam_strategy`;
- `fit_strategy`.

At least three concepts are required. Every pair must differ in at least two
signature fields. This rejects renamed or cosmetically varied copies without
claiming that a signature proves good design.

### Comparison matrix

Every concept must have one cell for each criterion:

- strength;
- part count;
- fasteners;
- operations;
- tooling;
- tolerances;
- material;
- appearance;
- builder skill;
- instruction complexity.

A cell contains an ordinal assessment (`advantage`, `neutral`, `disadvantage`,
or `unknown`), an explanation, and supporting precedent or brief references.
`unknown` is legal and visible. A selection rationale must cite the decisive
cell ids instead of restating an unsupported preference.

### Novelty and exceptions

Every concept feature cites zero or more precedent ids. A feature with no
precedent is automatically a deviation. It passes only when it cites a brief
requirement that forces it, or an explicit exception records:

- why the novelty is worth accepting;
- its cost or risk;
- alternatives rejected;
- approver and approval date.

There is no rule about rails, miters, dowels, brackets, or any other product-
specific technique. The validator exposes unsupported novelty through missing
evidence and its general comparison costs.

### Simplification and part purposes

Each conceptual part family must cite at least one brief requirement or concept
feature it serves and answer whether joinery or an existing part could absorb
the function. Repeated or mirrored instances may share a part-family purpose;
the validator does not force fabricated “unique” prose for left/right copies.
The gate fails when a part family has no indispensable function or omits the
joinery-replacement analysis.

## Validation and Superficial-Prose Defense

Validation returns ordered, stable findings with machine-readable codes and
human teaching messages. It checks:

- required sections and controlled vocabularies;
- at least one commercial-product precedent and one real build instruction;
- unique ids and valid cross-references;
- URL scheme, access date, construction observation, and lesson for every
  precedent;
- concept count and pairwise signature distance;
- complete comparison coverage;
- unsupported novelty and valid exceptions;
- part-family purposes and joinery-replacement answers;
- decision references and approval fingerprints;
- placeholder tokens, normalized duplicate prose, trivially short responses,
  and repeated boilerplate across concepts or comparison cells.

Mechanical prose checks are intentionally limited. Length and vocabulary do
not establish thoughtful design. A document cannot reach
`approved_for_modeling` merely because the validator returns no structural
findings: it also needs a named human approval over the canonical fingerprint.
This makes superficial prose detectable without presenting an LLM or word
count as a design authority.

## Canonical Fingerprints and Freshness

Canonical JSON serialization uses sorted keys, normalized enums, and stable
list order. Two SHA-256 fingerprints are exposed:

1. `selection_fingerprint` covers the brief, precedents, concepts, comparison,
   deviations, and decision, excluding approvals and presentation metadata.
2. `model_fingerprint` covers the canonical governed DetailSpec plus selected
   concept id.

`modeling_approval.selection_fingerprint` must equal the current selection
fingerprint. `delivery_confirmation` must match both the current selection and
model fingerprints. Editing the review invalidates both gates; editing the
production spec invalidates delivery but not the prior permission to model the
selected architecture.

The DetailSpec opt-in binding contains only:

```yaml
design_review:
  record: example_project.design-review.yaml
  selected_concept: concept_b
```

Relative paths resolve from the DetailSpec directory. Missing records, concept
mismatches, invalid approvals, and stale fingerprints fail closed with an
actionable `DesignReviewGateError`.

## Commands and Reports

The command surface is:

```bash
python -m detailgen.design_review validate details/armchair_caddy.design-review.yaml
python -m detailgen.design_review report details/armchair_caddy.design-review.yaml \
  --output outputs/design-reviews/armchair_caddy.html
python -m detailgen.design_review gate details/armchair_caddy.spec.yaml \
  --stage modeling
```

All commands are deterministic and non-mutating except for the requested
report file. `validate` exits nonzero on blocking findings. For a structurally
loadable document, `report` renders draft findings so an incomplete review can
be examined; it does not grant approval.

The developer-facing report contains the brief, source provenance, concept
signatures, full comparison matrix, novelty/exception ledger, simplification
review, decision rationale, approval/freshness status, and blocking findings.
It is generated directly from the structured document. It is not embedded in
the assembly manual and does not alter the customer document’s navigation.

## Production Integration

The DetailSpec schema gains an optional `design_review` binding. When absent,
loading, compiling, validating, rendering, and document generation behave as
before. When present:

- compilation resolves the sidecar and attaches immutable governance state to
  the compiled detail without pretending a draft has been promoted;
- the modeling-stage gate checks structural validity, selected-concept
  consistency, and current concept approval before the draft can be promoted;
- governed `Detail.render()` checks delivery confirmation after ordinary
  physical validation;
- `scripts/caddy_documents.py` checks delivery readiness before creating its
  output directory or writing either customer document;
- the design-review `report` command remains usable while approval or delivery
  is blocked.

No existing visual-review finding changes status or meaning.

## Armchair Caddy Pilot

The caddy review contains at least these concepts:

1. current double-wall registration-rail construction;
2. three-panel reinforced-miter construction;
3. rabbet-and-dowel construction;
4. concealed pocket-screw or discrete-bracket construction.

The research record retains commercial-product and real-instruction sources
with claim-level lessons. The comparison must expose the current design’s two
additional full-depth members, eight screws, glue/cure steps, tolerance effects,
and instruction burden through ordinary matrix cells and novelty analysis.

The report recommends one concept from the evidence. In this increment the
decision is marked `recommendation_only`; the selected concept is not silently
written into caddy geometry. Consequently the real caddy record is not given a
delivery confirmation in the feature commit. Its design report remains
generatable for owner review, while governed customer-document regeneration
fails closed until a later implementation and confirmation—or an explicit,
fully documented exception—is approved.

## Error Handling

- Schema errors identify the YAML path, invalid value, and allowed form.
- Validation findings aggregate so an author can fix a whole draft in one pass.
- Gate errors identify whether the blocker is incomplete research, absent
  approval, stale selection, absent model confirmation, or stale model input.
- Report generation represents unknown or blocked states visibly and never
  converts them to pass.
- URL reachability is not a runtime gate; web availability is unstable. URL
  structure and retained observations are validated locally.

## Testing and Acceptance

Unit fixtures cover:

- incomplete precedent research, including a missing source kind;
- fewer than three concepts and concepts with insufficient signature distance;
- unsupported novelty;
- a complete, explicitly approved exception;
- missing part-family purposes and omitted joinery-replacement analysis;
- empty, placeholder, repeated, and superficially duplicated prose;
- invalid and stale selection fingerprints;
- invalid and stale model fingerprints.

Integration tests cover:

- deterministic CLI validation and report output;
- a draft review report remaining available while production is blocked;
- opted-in production promotion blocked before modeling approval while local
  draft compilation remains available;
- opted-in render and caddy document generation blocked before current delivery
  confirmation and before any customer artifact is written;
- changing the governed DetailSpec invalidating delivery confirmation;
- the caddy report containing all four concepts, all comparison criteria,
  source URLs, deviation costs, and an evidence-linked recommendation;
- the production caddy geometry remaining byte-equivalent to its pre-feature
  baseline;
- representative ungoverned DetailSpecs, renders, and document paths retaining
  unchanged behavior.

Verification runs focused design-review and caddy tests first, followed by the
entire suite from the worktree-local environment. The feature branch is pushed
for owner review with the generated caddy report path disclosed and is not
merged.

## Out of Scope

- redesigning the production caddy geometry;
- automatically judging whether a concept is aesthetically good;
- crawling or permanently mirroring source websites;
- making design governance mandatory for legacy details;
- replacing physical, structural, installation, or visual validation;
- exposing the developer design review in the customer build manual.
