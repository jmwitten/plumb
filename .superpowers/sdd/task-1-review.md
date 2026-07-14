# Final Task 1 Re-review — DB40 Surface Ownership Contracts

## Verdicts

- **Spec compliance: PASS**
- **Code/test quality: APPROVED**

The amended RED suite is precise, non-vacuous, and internally satisfiable. It
now pins the approved A0/I1, S1+, R1, manual, and four-file document-set
boundaries without changing geometry, validation truth, release state, or CPG
order. Existing exact facts remain tested on their new owning surfaces.

## Critical findings

None.

## Important findings

None.

## Minor findings

None.

## Final closure audit

- **Primary ownership and budgets:** visible text excludes script/style data;
  DB40 is capped at 2,500 words, 80 rows, and eight tables. Exact status pairs,
  the three frozen UNKNOWN rule/verdict pairs, key dimensions, field checks,
  installation ids, intended installation views, and forbidden companion
  headings are all pinned.
- **Truth and release semantics:** the suite requires
  `Model/shop-data gate: PASS`, separately requires
  `Purchasing/cutting preflight: OPEN`, rejects the obsolete
  `Fabrication/model gate` wording, and retains DB40 installation/use HOLD. An
  UNKNOWN verdict cannot disappear from the expectation by changing to PASS.
- **Surface completeness:** S1+ must contain the complete canonical cut,
  edge-band, hardware, machining, fabrication, and assembly outputs. R1 must
  contain the complete canonical findings/evidence and source-map outputs.
  Legacy product, source, tool, machining, reader-vocabulary, release, viewer,
  and evidence-link facts were moved to their correct composers rather than
  deleted.
- **Exact-token negatives:** `_code_tokens()` normalizes complete rendered
  `<code>` values before comparison. This correctly distinguishes the step id
  `install.countertop` from the required finding rule
  `cabinetry.install.countertop_support`, while preserving exact installation,
  finding, and evidence ownership checks. Heading and viewer/GLB exclusions
  remain independently enforced.
- **Compatibility and existing behavior:** `build_cabinetry_html()` must equal
  the focused review composer, the existing B30 cabinetry project remains
  accepted across focused surfaces, and no shared non-cabinetry manual default
  was changed in Task 1.
- **Single-pass generation:** both `documents.compile_project_file` and
  `documents.CPR.compile_project_file` are patched to one counted wrapper, so a
  compile through either imported boundary contributes to the exact one-call
  limit. The module-wide `_render_views` wrapper independently requires one
  product-view render pass.
- **Four-file and link closure:** stable basenames include the required landing
  basename; all four returned files and SHA-256 values are pinned; every
  required relative href is present; and each href resolves from its source
  directory to the corresponding returned, existing target file. Viewer/GLB
  markers are limited to the landing/review document.
- **Prior manual pins:** the six shared panel assets, six instruction panels,
  nine operation diagrams, coordinate rows, procedure links, accessibility
  markers, embedded images, and self-containment assertions remain intact.

## Review evidence

Reviewed the Task 1 brief, updated Task 1 report, prior review, frozen
`a8f589a..bf50723` package, and final amended test code. The reported focused
result of `16 failed, 8 passed` was accepted as coherent intentional RED:
fifteen failures are absent focused composers and one is the absent companion
path/hash output contract. Tests were not rerun because the supplied evidence
already covers the final patch and no concrete inconsistency required another
execution. The review artifact was verified separately for required verdicts,
severity sections, and patch cleanliness.
