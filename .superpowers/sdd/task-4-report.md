# Task 4 Report: Caddy Reader Vocabulary and Presentation Invariance

## Outcome

Implemented Task 4 on top of base commit `ddc38be`.

- Authored `reader_name` on all 14 caddy components using only the closed
  vocabulary `Sofa arm`, `Side board`, `Top board`, `Registration rail`, and
  `Rail-to-side screw`.
- Preserved every authored component `id` and machine `name` exactly.
- Replaced `+X`/`-X` only in the four builder-visible raster title literals
  that contained those tokens.
- Preserved renderer machine-name color keys, `p.name` lookup, hide keys,
  camera/limit geometry, and X/Y/Z axis labels.
- Added real-API geometry, validation-truth, and machine-name invariance tests.
- Added a source-level raster-caption contract test.
- Did not render, create, or commit PNG/HTML output. Task 5 remains responsible
  for forcing the renderer before composing the document.

## TDD Evidence

### RED 1: test-contract correction before production edits

After adding tests, but before changing either production file, the prescribed
RED command was run:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_reader_names.py tests/test_armchair_caddy_e2e.py
```

Output:

```text
FAILED tests/test_reader_names.py::test_caddy_authors_the_closed_reader_vocabulary
FAILED tests/test_armchair_caddy_e2e.py::test_raster_builder_captions_avoid_x_coordinate_part_names
2 failed, 31 passed in 55.84s
```

The first test correctly found all `reader_name` values empty, but its first
version also assumed runtime `Placed.id` equals the authored YAML component id.
The repository generates runtime placement ids independently. Before any
production edit, the test was corrected to pin authored ids/names through
`load_spec_file()` and compiled machine/reader names through `compile_spec()`.

### RED 2: intended failures only

The same command was then rerun, still before production edits:

```text
FAILED tests/test_reader_names.py::test_caddy_authors_the_closed_reader_vocabulary
  authored ids and machine names matched; all 14 reader names were empty
FAILED tests/test_armchair_caddy_e2e.py::test_raster_builder_captions_avoid_x_coordinate_part_names
  four draw-title literals still contained +X/-X
2 failed, 31 passed in 19.16s
```

This is the valid RED boundary: both failures were caused only by missing Task
4 behavior. The reader-name-only invariance characterization passed before the
production edits.

## GREEN and Regression Evidence

After adding the 14 YAML fields and changing the four title literals, the
prescribed Task 4 acceptance command was run:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_reader_names.py tests/test_armchair_caddy_e2e.py tests/test_viewer_data.py tests/test_inspector_payload.py
```

Output:

```text
........................................sss.............                 [100%]
53 passed, 3 skipped in 28.96s
```

The three skips are the repository's existing optional viewer cases; there
were no failures or errors.

Syntax verification used the required interpreter:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m py_compile \
  scripts/render_caddy_views.py \
  tests/test_reader_names.py \
  tests/test_armchair_caddy_e2e.py
```

It exited 0 with no output. `git diff --check` also exited 0 with no output.

## Invariance Evidence

A separate audit loaded and validated the real caddy, changed only
`cleat_pos.reader_name` with `dataclasses.replace()`, recompiled it through the
real spec API, and compared `geometry_hash(part.world_solid())`, validation
finding tuples, and `Placed.name` sequences.

```text
components=14
reader_name_counts={'Sofa arm': 1, 'Side board': 2, 'Top board': 1, 'Registration rail': 2, 'Rail-to-side screw': 8}
geometry_equal=True
geometry_digest=de3584daa57cdafab21e1a5ef47a07b8d960b36a34625058d8ee37cf4794545c
truth_equal=True
truth_findings=122
truth_digest=d183263d2086b023098f1a917fc88836c0ebe92a87d5562e37da8b591b287100
machine_names_equal=True
machine_names=('sofa arm', 'side board +X', 'side board -X', 'top board', 'registration rail +X', 'registration rail -X', 'rail-side screw +X upper 0', 'rail-side screw +X upper 1', 'rail-side screw +X lower 0', 'rail-side screw +X lower 1', 'rail-side screw -X upper 0', 'rail-side screw -X upper 1', 'rail-side screw -X lower 0', 'rail-side screw -X lower 1')
```

The closed-vocabulary test separately compares the exact 14 authored YAML ids
and machine names against fixed expected pairs, then compiles that document and
checks the reader-name projection.

## Self-Review

- Confirmed the caddy YAML diff contains exactly 14 added `reader_name` lines;
  no `id`, `name`, params, placement, connection, validation, or sequence line
  changed.
- Confirmed the reader-name cardinalities are 1 sofa arm, 2 side boards, 1 top
  board, 2 registration rails, and 8 rail-to-side screws.
- Confirmed duplicate reader names are intentional and retain unique machine
  identities.
- Confirmed the renderer diff changes exactly four `draw(..., title, ...)`
  string literals and nothing else.
- Confirmed coordinate-bearing `COLOR` dictionary keys, the
  `COLOR.get(p.name, SCREW)` lookup, all `hide=("sofa arm",)` arguments, view
  limits/cameras, and explicit X/Y/Z axis labels remain intact.
- Confirmed the source-caption test parses `draw` calls with `ast`, rejects
  `+X`/`-X` only in their title argument, and positively pins semantic caption
  text plus the preserved renderer contracts.
- Confirmed `git status --short` listed only the four Task 4 source/test files
  and this report; no PNG, HTML, or unrelated file was generated or modified.

## Files Changed

- `details/armchair_caddy.spec.yaml`
- `scripts/render_caddy_views.py`
- `tests/test_reader_names.py`
- `tests/test_armchair_caddy_e2e.py`
- `.superpowers/sdd/task-4-report.md`

## Concerns

None.
