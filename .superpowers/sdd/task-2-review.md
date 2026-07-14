# Task 2 Review — Typed Manual Document Links

**Spec compliance: FAIL**

**Code quality: CHANGES REQUIRED**

## Findings

### Critical

None.

### Important

1. **URI schemes pass the promised relative-basename validation.**
   `src/rendering/instruction_panels.py:184-191` defines
   `_relative_html_basename()` using basename, slash, and `.html` checks, but it
   does not reject a URI scheme. Consequently both new validation sites
   (`src/rendering/instruction_panels.py:604-611` and
   `src/rendering/instruction_manual.py:74-80`) accept values such as
   `javascript:alert(1).html` and `mailto:review.html`. The renderer then places
   the accepted value directly in `href`; HTML escaping does not make a
   scheme-bearing URL relative. This violates the Task 2/global invariant that
   related hrefs are relative HTML basenames and, for a `javascript:` value,
   creates a click-triggered script URL despite the claimed validation.

   A focused probe against the reviewed implementation produced:

   ```text
   javascript:alert(1).html => javascript:alert(1).html scheme= javascript
   mailto:review.html => mailto:review.html scheme= mailto
   review_trace.html => review_trace.html scheme= <none>
   ```

   Reject scheme-bearing/colon-containing first path segments in the shared
   basename validator (or otherwise prove the parsed scheme is empty), and add
   construction and render regression cases alongside the existing path and
   non-HTML cases in `tests/test_cabinetry_instruction_manual.py`.

### Minor

None.

## What is otherwise correct

- `RelatedDocumentLink` is a minimal frozen value type, and the new manual
  tuple is appended with a safe empty default.
- Normal related hrefs are checked during builder construction and rechecked
  during rendering; labels and hrefs are HTML-escaped.
- DB40's landing, fabrication-packet, and review-trace labels are represented
  without hard-coding document-set filenames into reusable rendering code.
  Fabrication signoff ownership is corrected while landing/release/install
  prose and HOLD behavior remain untouched.
- Header and footer links use list/navigation semantics with distinct accessible
  landmark labels. Conditional markup and CSS preserve the legacy empty-default
  rendering path, including non-cabinetry manuals.
- The reviewed source diff does not change geometry, validation/CPG behavior,
  shop-data or purchasing-readiness state, and does not add premature document
  composers.

## Verification note

I accepted the report's recorded RED/GREEN, shared-regression, and byte-identity
evidence without rerunning those suites. I ran only the focused validator probe
shown above because the scheme boundary was a concrete review issue.
