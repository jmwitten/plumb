# Task 1 Re-review — DB40 Surface Ownership Contracts

## Verdicts

- **Spec compliance: FAIL**
- **Code/test quality: CHANGES REQUIRED**

The amendment closes most of the first review: legacy facts now target their
owning surfaces; the old readiness label is rejected; the three UNKNOWN
rule/verdict pairs and four matrix states are exact; normalized headings and
viewer exclusions strengthen ownership; and the four-file test retains the
existing manual, asset, hash, basename, and link assertions. One new negative
assertion is nevertheless incompatible with a required canonical audit block,
so the RED suite is still not internally satisfiable.

## Critical findings

### 1. The audit ownership test forbids a substring that its required findings block contains

`test_audit_composer_owns_complete_findings_evidence_and_source_map` requires
the exact complete `_render_findings(project)` output
(`tests/test_cabinetry_project_report.py:223`) and then rejects every process
step id with a raw substring assertion (`:239-244`). DB40 has an installation
step id `install.countertop`; the required findings HTML contains the distinct
finding rule `cabinetry.install.countertop_support`. Therefore
`"install.countertop" in CPR._render_findings(project)` is true.

This was confirmed with a targeted compiled-ledger inspection; the collision
is in `_render_findings`, not speculative future markup. Once the audit composer
exists, it cannot both contain the required findings ledger and satisfy the
step-id negative. Changing the finding rule would violate the frozen validation
truth, so production implementation cannot resolve the contradiction.

Compare identifiers as exact tokens rather than substrings—for example, parse
the rendered `<code>` values and reject an exact step-id value, or use
dot/word-aware boundaries that distinguish `install.countertop` from
`cabinetry.install.countertop_support`. Apply the same exact-token discipline to
the fabrication finding/evidence negatives to avoid future prefix collisions.

## Important findings

### 1. The compile-once spy does not intercept the compiler alias in the report module

The document-set test wraps only `documents.compile_project_file`
(`tests/test_cabinetry_instruction_manual.py:279-294`).
`documents.CPR.compile_project_file` remains a separate imported alias. A set
generator that performs the intended compile through `documents` and then
accidentally calls a CPR path that recompiles—such as the existing standalone
path-based generator—would still report one call and pass the global
compile-once assertion.

Patch both module aliases to the same counted wrapper, or route all compilation
through one injectable boundary and assert that boundary is called exactly
once. The `_render_views` interception is module-wide and adequately pins the
one product-view render pass.

## Minor findings

### 1. Link presence is pinned, but filesystem closure is only implied

The output test verifies exact basenames, existing returned files, and required
relative `href` strings, but not that every source-relative target resolves to
the corresponding returned path. Files with the right basename in different
directories would satisfy the assertions while the links are broken. A small
`source_path.parent / target_basename` resolution check would make the stated
link-closure contract literal.

## Prior-finding closure audit

- **Legacy monolithic assertions:** substantially closed. Shop, audit,
  installation, viewer, release, B30, and exact content pins were redistributed
  without changing model/process truth.
- **UNKNOWN self-weakening:** closed. The compiled DB40 boundary now pins the
  exact three `(rule, "UNKNOWN")` pairs, and A0/I1 must render the same pairs.
- **Markup-sensitive/incomplete negatives:** partially closed. Heading and
  viewer checks are stronger, but the audit substring collision above leaves
  this finding open.
- **Single compile/render pass:** partially closed. Rendering is pinned once;
  compilation counting misses the CPR alias.

## Review evidence

Reviewed the same Task 1 brief, the updated implementer report, the frozen
`a8f589a..f41aa34` review package, and both amended test modules. The reported
focused RED run was not repeated. A targeted read-only compiled-ledger probe was
run solely to investigate the concrete identifier-overlap risk; it confirmed
`install.countertop` occurs inside the canonical required findings output as
part of `cabinetry.install.countertop_support`. The review artifact itself was
then verified separately.
