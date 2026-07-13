# Task 3 Report: Model-Driven Reader Surfaces

## Outcome

Implemented Task 3 on top of base commit `593e6d2`.

- Routed cut-plan source labels, build-sequence placement and unordered-part
  names, single-detail existing-context BOM/hover labels, and inspector headings
  through the frozen `part_labels()` projection.
- Computed the projection once per assembly at each edited consumer boundary;
  no suffix stripping, coordinate parsing, or independent numbering was added.
- Preserved machine identity in `Placed.name`, inspector `parts` keys,
  `PartInspection.name`, `part_order`, `id_to_name`, Evidence Graph queries and
  neighbor references, GLB joins, and viewer payload keys.
- Preserved raw connection labels and resolved install-contract `describe()`
  lines, including coordinate-bearing `rail +X` text in the technical appendix.
- Made the caddy existing-context label exactly `Sofa arm (existing)` in both
  the visible BOM row and hover payload.
- Did not regenerate or modify any committed output artifact.

## TDD Evidence

### Baseline

Before test or production edits, the requested Task 3 plus caddy end-to-end set
was green:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q \
  tests/test_reader_names.py tests/test_cpg_core.py \
  tests/test_inspector_payload.py tests/test_armchair_caddy_e2e.py
```

```text
82 passed in 36.40s
```

### RED

Tests were added before any Task 3 production edit. They used the real
single-detail report import pattern (`scripts/` added to `sys.path`), the real
`build_document()` entry point, and explicit HTML section boundaries for the
cut plan, existing-context table, install disclosure, and build sequence.

Command:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q \
  tests/test_reader_names.py tests/test_cpg_core.py \
  tests/test_inspector_payload.py
```

Result:

```text
6 failed, 61 passed in 25.32s
```

The six intended failures were:

- caddy build-sequence placements still emitted machine rail names;
- caddy existing-context BOM/hover still emitted lowercase machine identity;
- the build-sequence section still emitted `place registration rail +X`;
- staged and unordered synthetic parts still emitted machine names;
- inspector part records had no `reader_name` field; and
- the inspector header still rendered only `part.name`.

The technical appendix's positive `rail +X` assertion passed at RED, confirming
the test already pinned the raw-contract side of the identity boundary.

### GREEN

Focused GREEN after the minimal production changes:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q \
  tests/test_reader_names.py tests/test_cpg_core.py \
  tests/test_inspector_payload.py
```

```text
67 passed in 26.44s
```

Prescribed Task 3 GREEN command:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q \
  tests/test_reader_names.py tests/test_cpg_core.py \
  tests/test_inspector_payload.py tests/test_armchair_caddy_e2e.py
```

```text
88 passed in 36.33s
```

Additional regression coverage for the shared consolidated cut-plan/report
path and another model-driven build sequence:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q \
  tests/test_cutplan_integration.py tests/test_fab2_cutlist.py \
  tests/test_consolidated_doc_prose.py tests/test_sit_reach_frame_e2e.py
```

```text
36 passed in 107.14s (0:01:47)
```

`git diff --check` completed with exit code 0 and no output.

## Self-Review

- Confirmed `build_sequence_model()` computes one projection, uses it for both
  placement tuples and loose/unordered names, and leaves `units`, `drives`, and
  `joins` unchanged.
- Confirmed consolidated cut maps remain keyed by `(detail_name, Placed.id)`;
  only their visible source string now reads `PartLabel.reader_name`.
- Confirmed single-detail existing-context hover and BOM relabeling share one
  `labels_by_id` projection while the viewer payload dictionary remains keyed by
  machine name (`"sofa arm"`).
- Confirmed inspector Evidence Graph calls still receive `placed.name`, and
  `parts`, `part_order`, `id_to_name`, `PartInspection.name`, dependency
  neighbors, and completeness lookups all remain machine-named.
- Confirmed inspector JavaScript still selects with
  `this.payload.parts[name]`; only the rendered header uses
  `part.reader_name || part.name`.
- Confirmed the caddy HTML tests isolate section bodies before asserting reader
  or machine vocabulary, so a machine name in hidden payload or a reader name in
  another section cannot create a false positive.
- Confirmed the scoped status contains only Task 3 implementation/tests and this
  report, with no generated HTML, PNG, GLB, or unrelated file.

## Files Changed

- `src/validation/build_sequence.py`
- `scripts/consolidated_report.py`
- `scripts/single_detail_report.py`
- `src/rendering/inspector.py`
- `src/rendering/inspector_assets/inspector.js`
- `tests/test_reader_names.py`
- `tests/test_cpg_core.py`
- `tests/test_inspector_payload.py`
- `tests/test_armchair_caddy_e2e.py`
- `.superpowers/sdd/task-3-report.md`

## Concerns

None.
