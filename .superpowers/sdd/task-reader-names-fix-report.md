# Reader-Names Final Review Fix Report

## Outcome

Closed every finding from the final reader-names review on
`codex/reader-names`, starting from `a3a1565`.

- Added an optional machine identity channel to cut planning:
  `CutItem.source_key` and `PlacedCut.source_key` carry
  `(detail origin, Placed.id)` independently of the visible source label.
- Propagated that key through deterministic packing and changed fabrication-note
  association/render lookup to use it. Callers that omit `source_key` retain
  the legacy `(profile, source)` note contract.
- Added the canonical `PartLabel.display_name`. Duplicate names render exactly
  as `Name (index of count)` and singletons remain unchanged.
- Routed build-sequence placed/unordered labels and cut-plan visible sources
  through `display_name`; the viewer retains its approved two-line
  reader-name plus ordinal/stock presentation.
- Extended every inspector part row with `reader_name`, `instance_index`,
  `instance_count`, and `display_name`, while preserving machine-named payload
  keys, `part_order`, `id_to_name`, selection targets, graph queries, and GLB
  joins.
- Changed inspector headings, no-WebGL picker labels, construction-neighbor
  labels, and navigable load-path node labels to resolve machine targets through
  `payload.parts[machineName].display_name`, falling back to the machine name for
  legacy payloads. Clicks still pass the machine key to `selectPart`.
- Preserved `reader_name` when the legacy site-overview composer creates its new
  `Placed`, without changing the component/machine name or composed id.
- Added no generated HTML, PNG, GLB, or other output artifacts.

## Root-Cause Verification

Before editing, the requested worktree was clean at
`a3a15658d3ee70b44395c8b01f6f5502bcfde5e0`. The existing affected-module
baseline was:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q \
  tests/test_reader_names.py tests/test_cpg_core.py \
  tests/test_inspector_payload.py tests/test_cutplan.py \
  tests/test_cutplan_integration.py tests/test_fab2_cutlist.py \
  tests/test_site_overview.py
```

```text
108 passed in 147.27s (0:02:27)
```

Code tracing confirmed the review's four causes:

1. `lumber_cut_items()` projected human labels into `CutItem.source`, while
   `cutlist_fab_notes()` and `render_cutplan()` used `(profile, source)` as
   identity, allowing duplicate display labels to overwrite notes.
2. `part_labels()` computed one `index/count`, but build sequence, cut plan, and
   inspector consumed only `reader_name`, discarding the ordinal.
3. Inspector fallback and neighbor navigation rendered their machine selection
   target directly; only the selected heading had a reader-name fallback.
4. `_site_overview.build_site_overview()` reconstructed `Placed` without
   copying `reader_name`.

## TDD RED Evidence

All focused regressions were added before any production edit. At that point
`git status --short` listed only the six edited test modules. Command:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q \
  tests/test_cutplan.py tests/test_fab2_cutlist.py \
  tests/test_reader_names.py tests/test_cpg_core.py \
  tests/test_inspector_payload.py tests/test_site_overview.py
```

Result:

```text
12 failed, 96 passed in 138.31s (0:02:18)
```

The twelve failures were the intended missing behaviors only:

- `CutItem` rejected the new `source_key` argument and `PlacedCut` exposed no
  `source_key` after packing.
- The two machine-distinct `Registration rail` cuts had no independent key for
  fabrication-note association.
- `PartLabel` exposed no `display_name`, for duplicates or legacy singletons.
- Caddy sequence and cut-plan surfaces emitted two unordinaled
  `Registration rail` strings.
- Inspector rows omitted `instance_index`, `instance_count`, and `display_name`.
- Inspector JavaScript lacked the display-name resolver and still used
  `reader_name` only for the selected heading.
- The site-overview copy reset the authored `reader_name` to `""`.

The caddy ordinal regression pins the central projection against viewer and
inspector payloads for both registration rails and all eight rail-to-side
screws. The FAB regression constructs two same-profile, machine-distinct parts
with the same reader name and different fabrication notes, then requires both
packed cuts and each correctly associated note exactly once.

## GREEN Evidence

The twelve previously failing tests passed immediately after the minimal
production changes:

```text
12 passed in 5.56s
```

The complete affected-module set, including cut-plan integration, passed:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q \
  tests/test_cutplan.py tests/test_cutplan_integration.py \
  tests/test_fab2_cutlist.py tests/test_reader_names.py \
  tests/test_cpg_core.py tests/test_inspector_payload.py \
  tests/test_site_overview.py
```

```text
114 passed in 140.92s (0:02:20)
```

Expanded reader-name/viewer/spec/caddy coverage passed:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -q \
  tests/test_reader_names.py tests/test_cpg_core.py \
  tests/test_inspector_payload.py tests/test_cutplan.py \
  tests/test_cutplan_integration.py tests/test_fab2_cutlist.py \
  tests/test_site_overview.py tests/test_viewer_data.py \
  tests/test_viewer_explode_and_fab.py tests/test_armchair_caddy_e2e.py \
  tests/test_spec.py tests/test_spec_repeat.py
```

```text
197 passed, 3 skipped in 166.21s (0:02:46)
```

The binding full gate passed with the verified shim/interpreter:

```bash
PYTHONPATH="$PWD/.shim" ../../.venv/bin/python -m pytest -n auto -q
```

```text
1366 passed, 3 skipped, 1 xfailed in 857.91s (0:14:17)
```

The one xfail and three skips are the repository's existing expected outcomes;
there were no failures or errors.

Additional checks:

```bash
node --check src/rendering/inspector_assets/inspector.js
git diff --check
```

Both exited 0 with no output.

## Self-Review

- Confirmed `source_key` is populated only from `(origin, Placed.id)` and is
  never derived from reader name, display name, or ordinal.
- Confirmed `pack()` preserves `source_key` on every `PlacedCut` and includes it
  only as the final deterministic tie-breaker after length and visible source.
- Confirmed the legacy default is `None`, so all existing three-argument
  `CutItem` and two-argument `PlacedCut` callers remain valid.
- Confirmed the renderer explicitly falls back to `c.source` only when
  `c.source_key is None`; a dedicated regression renders a legacy source-keyed
  note.
- Confirmed the duplicate FAB regression verifies two cuts survive, two stable
  note keys survive, each ordinal label renders once, and each note appears once
  beside its correct displayed cut.
- Confirmed `PartLabel.display_name` formats but does not recompute ordinals;
  `part_labels()` remains the only declaration-order `index/count` computation.
- Confirmed duplicate caddy rails render `(1 of 2)` / `(2 of 2)`, all eight
  screws render `(1 of 8)` through `(8 of 8)`, and singleton fallback remains
  exactly the reader/machine name without a suffix.
- Confirmed viewer payload and GLB keys remain machine names; viewer JavaScript
  retains the approved two-line `reader_name` plus `index of count · stock`
  contract.
- Confirmed inspector payload keys, `PartInspection.name`, `part_order`,
  `id_to_name`, Evidence Graph queries, dependency targets, mesh selection, and
  `selectPart()` arguments remain machine-named.
- Confirmed inspector legacy fallback is exactly machine name when
  `display_name` is absent; it does not independently reconstruct ordinals.
- Confirmed build-sequence raw drive/install contract text and technical graph
  identities remain unchanged.
- Confirmed the site-overview copier changes only the copied presentation field;
  its source component, `Placed.name`, and generated `{detail}-{Placed.id}` id
  are unchanged and pinned by regression.
- Confirmed no suffix stripping, `Component.reader_name`, cache/fingerprint,
  geometry, finding identity, YAML, generated artifact, or unrelated source
  change entered the diff.

## Files Changed

- `src/core/cutplan.py`
- `src/rendering/part_labels.py`
- `src/validation/build_sequence.py`
- `src/rendering/inspector.py`
- `src/rendering/inspector_assets/inspector.js`
- `scripts/consolidated_report.py`
- `scripts/_site_overview.py`
- `tests/test_cutplan.py`
- `tests/test_fab2_cutlist.py`
- `tests/test_reader_names.py`
- `tests/test_cpg_core.py`
- `tests/test_inspector_payload.py`
- `tests/test_site_overview.py`
- `.superpowers/sdd/task-reader-names-fix-report.md`

## Concerns

None.
