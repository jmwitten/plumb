# Task 2 Report — Typed Manual Document Links

## Outcome

Implemented the additive related-document seam for instruction manuals on top
of Task 1 commit `b55e330`.

- Added frozen `RelatedDocumentLink(label: str, href: str)` records.
- Added `InstructionManual.related_documents` as an empty tuple default after
  the existing fields, preserving positional construction compatibility.
- Added an explicit related-document tuple to the shared manual builder and
  cabinetry adapter without hard-coding DB40 filenames into either reusable
  API.
- Validated every related href with the existing
  `_relative_html_basename()` rule during model construction and again during
  HTML rendering.
- Rendered the supplied links as compact header and footer navigation lists.
  Empty-default manuals retain the previous single technical-document links
  and omit all new related-link markup and CSS.
- Corrected the DB40 first-panel signoff instruction to send pre-band cut,
  edge-band, machining, and material rows to the fabrication packet. No
  release, installation, geometry, validation, or process copy changed.

No report composer, installation drawing, document-set generator, model fact,
release state, or cabinetry geometry was implemented or modified.

## TDD Evidence

All Python commands used the approved worktree interpreter pattern:

```bash
PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python
```

The shell's bare `pytest` initially resolved through Python 3.13 and returned
exit 127 because that environment has no pytest. Investigation confirmed the
repository's shared Python 3.12 virtualenv and `.shim` worktree import path;
all evidence below uses that prescribed environment.

### Baseline

Before editing, the unaffected tests in the cabinetry manual module passed:

```bash
... -m pytest -q tests/test_cabinetry_instruction_manual.py -k 'not real_document_set'
```

```text
4 passed, 1 deselected in 5.84s
```

The deselected test is Task 1's intentional RED contract for the later
four-file document-set generator.

### RED 1 — type and field absent

After adding only the four focused tests:

```bash
... -m pytest -q tests/test_cabinetry_instruction_manual.py -k 'related_document'
```

```text
4 failed, 5 deselected in 3.53s
```

Three failures were the expected `ImportError` for absent
`RelatedDocumentLink`; the caddy default test failed with the expected
`AttributeError` for absent `InstructionManual.related_documents`. There were
no collection, fixture, compile, or unrelated behavior failures.

### GREEN 1 — typed model, validation, renderer, and DB40 copy

After the minimal implementation, the same command produced:

```text
4 passed, 5 deselected in 6.20s
```

The tests prove that paths and non-HTML hrefs are rejected during construction,
a directly replaced invalid href is rejected again during rendering, the DB40
manual renders the exact `Review & installation sheet`, `Fabrication packet`,
and `Review trace` links in both navigation locations, and cut/material
signoff points to the fabrication packet.

### RED 2 — literal empty-default compatibility

Self-review noticed that unconditional related-link CSS would change caddy
HTML even when the tuple was empty. The default-compatibility test was
strengthened before the fix to reject any `.related-documents` CSS. It failed
for that exact reason:

```text
1 failed in 3.24s
```

The styles were then made conditional. Final focused result:

```text
4 passed, 5 deselected in 5.90s
```

### Full manual module

The prescribed full Task 2 file produced the expected later-task failure
shape:

```bash
... -m pytest -q tests/test_cabinetry_instruction_manual.py
```

```text
1 failed, 8 passed in 18.89s
```

The sole failure is the intentional Task 1 document-set contract:
`build_cabinetry_document_pair()` still lacks `fabrication_path`,
`fabrication_sha256`, `audit_path`, and `audit_sha256`. Its one-compile and
one-product-view assertions pass before that missing-output assertion. This
task deliberately does not implement those later composers or outputs.

### Shared/default regressions

```bash
... -m pytest -q tests/test_instruction_panels.py tests/test_caddy_instruction_manual.py
```

```text
34 passed in 29.11s
```

An additional focused construction/default gate produced:

```text
6 passed, 26 deselected in 5.76s
```

### Byte-compatibility check

The Task 1 renderer source from `b55e330` and the current renderer were loaded
side by side, given the same caddy manual and image bytes, and run with a frozen
generation timestamp. Their complete empty-default HTML strings matched:

```text
baseline_sha256=c56623800c4b74e82a29d49230c79395c89ff2d6c40cf19aef2fb13a34461af4
current_sha256=c56623800c4b74e82a29d49230c79395c89ff2d6c40cf19aef2fb13a34461af4
byte_identical=True
```

## Self-Review

- `RelatedDocumentLink` is frozen and owns only the requested label/href
  surface.
- The new manual field is appended after the existing defaulted field, so old
  positional `InstructionManual` construction retains its meaning.
- Both builders default to `()`. The cabinetry adapter accepts filenames from
  its caller; it does not infer or hard-code a DB40 document set.
- Construction validation normalizes each immutable link through `replace()`;
  render validation independently calls the same existing basename rule.
- Labels and hrefs are HTML-escaped; related links are relative-only, and no
  external navigation behavior was added.
- Header/footer navigation is emitted only for a non-empty tuple. The empty
  path reconstructs the old anchor strings exactly and injects no CSS.
- The only DB40 prose edit is the first-panel fabrication-signoff sentence.
  The adapter's landing-sheet/release/install copy remains otherwise intact.
- `git diff --check` is clean.
- The scoped implementation diff contains only the three authorized source
  files and `tests/test_cabinetry_instruction_manual.py`; this report and the
  controller-supplied Task 2 brief are the only additional commit files.

## Files

- `src/rendering/instruction_panels.py`
- `src/rendering/instruction_manual.py`
- `src/packs/cabinetry/instruction_manual.py`
- `tests/test_cabinetry_instruction_manual.py`
- `.superpowers/sdd/task-2-brief.md`
- `.superpowers/sdd/task-2-report.md`

## Concerns

None for Task 2. The single full-file document-set failure is intentional,
pre-existing RED for later tasks and remains outside this task's scope.

## Review Fix — Reject URI Schemes

The fresh Task 2 review identified one valid Important issue: the shared
`_relative_html_basename()` rule accepted scheme-bearing strings such as
`javascript:alert(1).html` and `mailto:review.html` because both are slashless,
are their own `Path.name`, and end in `.html`. Construction validation and
render-time revalidation therefore both accepted them.

### Review-fix RED

The construction invalid-input table was extended with both schemes, and the
render-time defense test was parameterized over its existing invalid path plus
both schemes. Before the production fix:

```bash
PYTHONPATH="$PWD/.shim" /Users/joelwitten/Code/construction-detail-generator/.venv/bin/python -m pytest -q tests/test_cabinetry_instruction_manual.py -k 'related_document_links_require_relative_html_basenames or related_document_links_are_revalidated_during_rendering'
```

```text
3 failed, 1 passed, 7 deselected in 5.97s
```

The three failures were exact `DID NOT RAISE ValueError` failures: one at
manual construction when the invalid-input loop reached
`javascript:alert(1).html`, and one render-time failure for each scheme. The
existing invalid path case continued to pass.

### Minimal fix and GREEN

Because the validator already rejects both path separator forms, any colon in
the remaining basename is a URI-scheme/drive ambiguity rather than an allowed
delivery filename. Adding `":" in value` to the shared rule closes technical,
manual, related-link construction, and related-link render validation through
the existing call sites.

The same focused command after the one-line validator change produced:

```text
4 passed, 7 deselected in 6.24s
```

All Task 2 link/default cases:

```bash
... -m pytest -q tests/test_cabinetry_instruction_manual.py -k 'related_document'
```

```text
6 passed, 5 deselected in 7.79s
```

Covering cabinetry/manual/shared regression gate:

```bash
... -m pytest -q tests/test_cabinetry_instruction_manual.py tests/test_instruction_panels.py tests/test_caddy_instruction_manual.py -k 'not real_document_set'
```

```text
44 passed, 1 deselected in 40.04s
```

The deselection remains only the later document-set/composer contract.

An explicit validator probe rejected both requested schemes and retained the
valid simple basename `review_trace.html`. The frozen-timestamp empty-default
caddy comparison remained byte-identical to Task 1:

```text
scheme_probe=javascript/mailto rejected; simple basename accepted
baseline_sha256=c56623800c4b74e82a29d49230c79395c89ff2d6c40cf19aef2fb13a34461af4
current_sha256=c56623800c4b74e82a29d49230c79395c89ff2d6c40cf19aef2fb13a34461af4
byte_identical=True
```

`git diff --check` completed with exit code 0. The review-fix scope contains
only the shared validator, its focused cabinetry tests, this appended report,
and `.superpowers/sdd/task-2-review.md`. No composer, drawing, adapter,
document-set, release, geometry, or CPG code changed.
