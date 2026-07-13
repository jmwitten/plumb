# Task 2 Report: Shared Part Labels and Viewer Hover Hierarchy

## Outcome

Implemented the Task 2 reader-label projection and viewer integration on top of
base commit `02abd62`.

- Added frozen `PartLabel(machine_name, reader_name, item, index, count)`
  records and a single `part_labels(parts)` projection keyed by `Placed.id`.
- Counts and ordinals are computed in assembly declaration order after the
  input iterable is materialized once.
- Preserved viewer payload dictionary and GLB join keys as `Placed.name`.
- Added `reader_name`, `instance_index`, and `instance_count` to each viewer
  payload row.
- Changed the viewer tooltip to render the reader name and stock description as
  separate primary and secondary lines. Repeated reader names show `n of N`
  before the stock item.
- Preserved the compatibility fallback exactly as `p.reader_name or p.name`.
- Did not author reader names in the armchair-caddy spec or touch any caddy
  presentation assets.

## TDD Evidence

### Baseline

Command:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_reader_names.py tests/test_viewer_data.py tests/test_viewer_explode_and_fab.py
```

Output at `02abd62`, before Task 2 test edits:

```text
28 passed, 3 skipped in 28.11s
```

### RED 1: shared projection absent

After adding the projection, payload, and tooltip contract tests but before any
Task 2 production code, command:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_reader_names.py tests/test_viewer_data.py
```

Output:

```text
ERROR tests/test_reader_names.py
ModuleNotFoundError: No module named 'detailgen.rendering.part_labels'
1 error in 2.05s
```

This is the intended first failure: the required shared projection module did
not exist.

### RED 2: viewer fields and hierarchy absent

After adding only the shared projection, the same command produced:

```text
FAILED tests/test_viewer_data.py::test_viewer_keeps_machine_keys_and_adds_reader_fields
KeyError: 'reader_name'
FAILED tests/test_viewer_data.py::test_tooltip_uses_reader_name_but_not_as_lookup_key
assert 'p.reader_name || partName' in js
2 failed, 15 passed, 3 skipped in 2.43s
```

This separately established that the payload additions and tooltip hierarchy
were absent before their implementation.

### GREEN and debugging record

The first prescribed GREEN attempt exposed local-variable shadowing in
`build_viewer_payload`: the existing `for label, value in c.params().items()`
loop replaced the newly introduced `PartLabel` local with a string. The run
reported `4 failed, 21 passed, 3 skipped, 7 errors`. A focused diagnostic
confirmed the value changed from `PartLabel` to `str`; the projected record was
renamed to `part_label`, with no behavioral expansion.

Focused verification after that correction:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_viewer_data.py::test_viewer_keeps_machine_keys_and_adds_reader_fields tests/test_viewer_data.py::test_tooltip_uses_reader_name_but_not_as_lookup_key
```

```text
2 passed in 2.00s
```

Prescribed Task 2 GREEN command:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q tests/test_reader_names.py tests/test_viewer_data.py tests/test_viewer_explode_and_fab.py
```

```text
32 passed, 3 skipped in 13.48s
```

The selected regression set includes the real viewer GLB/payload join checks,
explode behavior, fabrication data, legacy reader-name fallback, duplicate
reader-name ordinals, and the JavaScript source contract.

Additional checks:

```bash
git diff --check 02abd62
node --check src/rendering/web_viewer/viewer.js
```

Both completed with exit code 0 and no output.

### Independent review

A read-only code reviewer inspected the complete Task 2 working-tree snapshot,
including the untracked projection module, against the brief and global
constraints. It reported no Critical, Important, or Minor issues and assessed
the implementation as ready to merge. The reviewer independently reproduced
`32 passed, 3 skipped in 13.71s`, a successful JavaScript syntax check, and a
clean diff check.

## Self-Review

- Confirmed `part_labels` uses a frozen dataclass, materializes the parts once,
  and uses `Counter` totals plus declaration-order `seen` counts.
- Confirmed the projection result is keyed only by `Placed.id`.
- Confirmed payload assembly still writes rows under `parts[p.name]`; no export,
  cache, evidence, geometry, component, `name`, or `id` code changed.
- Confirmed `fillTooltip` still reads `payload.parts[partName]` and uses
  `p.reader_name || partName` only for presentation.
- Confirmed the primary name and secondary stock text use distinct DOM elements
  and CSS classes, with duplicate context rendered only when count is greater
  than one.
- Confirmed all server-provided tooltip text still passes through the existing
  HTML escape function.
- Confirmed the scoped diff contains only Task 2 implementation/tests and this
  report; `details/armchair_caddy.spec.yaml` remains unchanged.

## Files Changed

- `src/rendering/part_labels.py` — new immutable shared projection.
- `src/rendering/web_viewer/__init__.py` — consume the projection and add viewer
  row fields while retaining machine-name keys.
- `src/rendering/web_viewer/viewer.js` — reader-name primary line and repeated
  instance stock subheading.
- `src/rendering/web_viewer/viewer.css` — primary/secondary tooltip hierarchy.
- `tests/test_reader_names.py` — duplicate numbering and legacy fallback tests.
- `tests/test_viewer_data.py` — two-rail payload and tooltip source contracts.
- `.superpowers/sdd/task-2-report.md` — this execution record.

## Concerns

None.
