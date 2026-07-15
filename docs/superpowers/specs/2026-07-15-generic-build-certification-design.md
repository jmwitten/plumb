# Generic Build Certification Design

Date: 2026-07-15

Status: approved for implementation

## Objective

Replace repeated product-specific Python suites with a generic certification
engine that proves the accuracy of any supported construction build from its
compiled evidence and a compact, declarative acceptance contract.

The armchair caddy is the first proving subject, not a special case. A future
unrelated standalone build must receive the same certification by adding its
normal build specification and `<slug>.cert.yaml`, without changing the engine
or creating a project-specific Python suite. Bespoke tests remain only for new
framework behavior or a physical invariant that the generic evidence model
cannot express honestly.

## Scope

The first increment will:

- define a build-adapter protocol and implement a standalone `*.spec.yaml`
  adapter;
- define and validate versioned `<slug>.cert.yaml` contracts;
- collect typed evidence from the production compiler, validator, assembly,
  fabrication, BOM, governance, and optional document APIs;
- run a stable catalog of generic certification rules;
- evaluate typed product intent without arbitrary Python or expression code;
- return structured pass, warning, failure, and decision results;
- expose the engine through a Python API, a non-interactive CLI, and the
  existing `pytest --detail-gate <slug>` workflow;
- migrate the caddy as a coverage-equivalence proof;
- remove caddy tests made redundant by generic rules or declarative intent;
- retain the smallest honest bespoke caddy test surface for invariants not yet
  representable by the generic model;
- keep fresh per-test caches and avoid previous-run result reuse.

Site composition and cabinet project adapters are not implemented in this
increment. Their support is an adapter addition, not a rule-engine redesign.

## Architectural boundaries

### Build adapter

`BuildAdapter` converts one source kind into a common certification subject.
It owns source loading and calls authoritative production APIs. It does not
decide pass or fail.

The standalone adapter exposes:

- source identity and content fingerprint;
- compiled detail and validation report;
- assembly parts and connection evidence;
- fabrication records and reconstruction verification;
- BOM rows;
- governance/review state;
- optional declared deliverables.

The engine selects adapters by the contract's `subject.kind`. No rule branches
on a slug, filename, or product name.

### Evidence snapshot

The collector converts adapter output into immutable typed evidence. It keeps
raw authoritative objects available to rules that must invoke an existing
production verifier, while also publishing normalized facts for intent
selectors and deterministic reporting.

The snapshot includes:

- subject identity and fingerprints;
- compilation success or a structured compile failure;
- validation findings, blockers, and verdicts;
- parts with stable IDs, names, component/material identities, roles, bounds,
  and volumes where supported;
- connection relations, connection types, and referenced hardware IDs;
- fabrication records and the result of the production fabrication-fold
  verifier;
- normalized BOM rows and their source part IDs;
- governance/review and delivery state;
- optional deliverable evidence only when the contract requests it.

The collector does not reimplement geometry, validation, or fabrication
algorithms. Certification checks authoritative results and cross-layer
agreement, avoiding a second shadow implementation.

### Generic rule engine

Every rule has a stable ID, fixed severity, applicability predicate, and pure
evaluation function over a snapshot and contract. Rules emit structured
findings rather than raising assertion errors.

The initial mandatory rule groups are:

- `compile`: the subject loads and compiles through its declared adapter;
- `validation`: the production validation report has no unresolved blocker or
  failure permitted by policy;
- `geometry`: constructed parts have valid non-empty solids and stable unique
  identities; production interference/fit findings remain clean;
- `connections`: all connection references resolve and production
  constructibility/installability findings remain clean;
- `fabrication`: every fabricated part has a record and the authoritative
  fabrication-fold verifier reproduces installed geometry;
- `bom`: modeled purchasable/fabricated parts and BOM source IDs/quantities
  agree, while existing context is not billed as fabricated stock;
- `governance`: required review, model approval, and delivery state are
  internally consistent;
- `intent`: every typed acceptance fact in the contract matches collected
  evidence;
- `determinism`: normalized evidence for the same compiled subject is stable
  within the certification run where the adapter supports the check.

Documentation and presentation are optional rule groups. They run only when
the contract declares those outputs as deliverables and never become universal
requirements merely because a renderer exists.

### Contract evaluator

The contract is data, not executable code. Version 1 supports typed intent:

- exact, minimum, and maximum counts using stable part/component/material/role
  selectors;
- required and forbidden part/connection selectors;
- expected fabrication-step sequences for selected parts;
- expected BOM item quantities and optional dimensional ranges;
- required validation verdict counts or absence by stable check ID;
- governance state requirements;
- approved decisions for otherwise unresolved claims.

Selectors are closed-schema mappings. Arbitrary Python, regular-expression
execution from YAML, and general expression evaluation are excluded.

Example:

```yaml
schema_version: 1
subject:
  kind: standalone_detail
  source: armchair_caddy.spec.yaml
intent:
  counts:
    - selector: {component: HardwoodPanel}
      exactly: 3
    - selector: {component: WoodDowel}
      exactly: 4
  forbidden:
    - selector: {name_contains: screw}
    - selector: {name_contains: bracket}
  connections:
    - selector: {kind: bonded_to}
      exactly: 2
    - selector: {kind: keyed_by}
      exactly: 2
deliverables: []
decisions: []
```

Contract paths are resolved relative to the contract file. Sources cannot
escape the repository root.

## Autonomy and decisions

The engine never prompts. It returns a deterministic result with findings in
these states:

- `PASS`: supported by authoritative evidence;
- `WARN`: a nonessential documentation, presentation, or metadata claim is
  unknown or incomplete;
- `FAIL`: observed evidence contradicts a mandatory rule or declared intent;
- `NEEDS_DECISION`: a correctness-critical claim cannot be established from
  evidence and has no still-valid recorded owner decision.

The severity policy is global and cannot be weakened per product:

- geometry, safety, constructibility, fabrication fidelity, material/BOM
  accuracy, and declared design intent block;
- documentation, presentation, and nonessential descriptive metadata warn
  unless the contract explicitly promotes them to requested deliverables.

CLI and agent consumers may present `NEEDS_DECISION` findings. Accepted answers
are stored with a rule ID, outcome, rationale, and dependency fingerprint.
Only changes to that rule's relevant evidence invalidate the answer. Test runs
are always non-interactive.

A recorded decision may classify applicability or explicitly accept that a
claim remains unknown. It cannot override contradictory evidence, suppress an
observed validation/geometry/fabrication failure, or convert a failed declared
intent fact into a pass. Certification results always disclose applied
decisions and retain `UNKNOWN` wording even when policy permits release.

The first increment provides the structured decision model and deterministic
CLI output. It does not build a product-specific UI. An agent or later CLI
wizard can write recorded decisions without changing engine semantics.

## Entry points and discovery

The canonical API accepts a contract path and returns `CertificationResult`.

The CLI supports:

```bash
python -m detailgen.certification details/armchair_caddy.cert.yaml
python -m detailgen.certification details/armchair_caddy.cert.yaml --json
```

Exit codes are stable: zero for pass/warn-only, one for failure, two for a
required decision, and four for contract/usage errors.

Pytest discovers `details/*.cert.yaml` and creates one generic parametrized
certification node per contract. Each node receives its slug marker during
collection. `pytest --detail-gate armchair_caddy -q -n 4` selects that generic
node plus any deliberately retained bespoke caddy nodes. New standalone builds
require no edit to the generic pytest module.

Ordinary pytest remains unfiltered. Platform unit tests and the full suite stay
the integration gate for changes to shared compiler, geometry, validation,
rendering, pack, cache, adapter, evidence, or certification-rule code.

## Caddy migration and deletion policy

Before deleting a caddy test, the implementation produces a row-by-row map of
all 53 current gate nodes. Each row records exactly one disposition:

- replaced by a named generic rule;
- replaced by a typed fact in `armchair_caddy.cert.yaml`;
- retained as a named bespoke invariant with a reason;
- removed as duplicate coverage, naming the equivalent surviving row.

No row may be classified only as "covered elsewhere." The map names the rule,
contract path, or surviving test.

The migration runs old and new gates against the unchanged caddy first. It also
runs representative mutations for compile failure, validation failure,
interference, fabrication drift, BOM mismatch, intent mismatch, governance
block, malformed contract, unknown adapter, and decision-required behavior.
Only after equivalence and mutation evidence pass are redundant caddy tests
deleted.

Dedicated documentation/manual tests are removed from the caddy fast gate when
documentation is not a declared deliverable. Shared document framework tests
remain in the full platform suite.

The target is to replace at least 80 percent of the 53 caddy gate nodes with
the generic certification node, contract facts, or deduplicated coverage. The
retained bespoke set must be justified by evidence the generic snapshot cannot
yet express without adding product-specific engine logic.

## Performance requirements

- The generic caddy gate must remain below the previously accepted 645.17
  second ceiling on a clean cache.
- It must not compile unrelated standalone builds.
- One gate invocation compiles the caddy no more than needed by authoritative
  checks; duplicated collection fixtures are prohibited.
- It must not read geometry, verdict, render, or certification results from a
  previous pytest process.
- The report records at least two fresh-process wall times and uses the slower
  value.

## Error handling

- YAML/schema/source errors are usage failures with contract path and field
  identity.
- An unsupported adapter kind is a usage failure, not an unknown certification
  result.
- A compiler exception becomes a structured blocking compile finding so JSON
  consumers receive a result; failures before a subject can be identified are
  usage errors.
- Rule exceptions are reported with the rule ID and fail certification. They
  are never silently converted to warnings.
- Unknown contract fields fail closed to prevent misspelled intent from being
  ignored.
- Duplicate slugs or multiple contracts for one source fail collection.

## Testing strategy

Engine unit tests use small fake adapters and snapshots. They prove schema
strictness, rule ordering, severity, decision invalidation, selector behavior,
exit codes, and slug-independent operation without CadQuery cost.

Standalone-adapter integration tests compile the caddy and exercise real
production validators and fabrication verification. Mutation tests prove that
the engine catches representative failures rather than merely recording clean
output.

A generality test creates a temporary, unrelated miniature standalone spec and
contract. It must be discovered and certified without editing a registry or
adding a Python test. This is a release-blocking acceptance criterion.

The final branch must pass:

- certification engine/unit tests;
- clean-cache caddy generic gate twice;
- the caddy mutation matrix;
- default collection preservation except for explicitly mapped caddy test
  removals/additions;
- the complete repository suite with `pytest -q -n 4`.

## Completion criteria

The increment is complete only when:

1. no engine or generic test code contains `armchair_caddy` or caddy-specific
   geometry knowledge;
2. a temporary unrelated spec and contract certify through automatic
   discovery;
3. the caddy has a valid separate contract and passes the generic gate;
4. every original caddy gate node has an explicit equivalence disposition;
5. at least 80 percent of the caddy gate nodes no longer require a bespoke
   caddy Python test;
6. all deleted assertions have named replacements and mutation evidence;
7. documentation is optional unless explicitly requested;
8. the slower of two fresh caddy gate runs is below 645.17 seconds;
9. the full repository regression passes; and
10. implementation, coverage, timing, and retained-risk reports are committed
    and pushed on the feature branch.
