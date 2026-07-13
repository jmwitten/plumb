# Compiled baselines (ARCH0)

These JSON files are the test suite's **golden baselines**. They replace the
hand-maintained Python literals that used to churn every time a part count
changed (retro finding R11: one part-count change → ~10 hand-edited fixtures).

## How it works

- Each file is **one golden surface** — the model's current truth for that
  surface, emitted in a deterministic form (sorted keys, 2-space indent).
- The migrated tests **read** these files and assert `live output == baseline`,
  exactly as they asserted the literal before. A normal `pytest` run never
  rewrites a baseline.
- Changing behaviour means **regenerating** the baseline and **reviewing the git
  diff** — never hand-editing a set or a count:

  ```
  python scripts/regen_baselines.py          # rewrite the committed baselines
  python scripts/regen_baselines.py --check   # CI: fail if any baseline is stale
  ```

The loader (`load_baseline`), the canonical serializer (`dumps`), the shared
fingerprint helpers, and every `compute_*` the regen command calls live in
`tests/baseline_lib.py`. `tests/test_baselines.py` proves the committed files
are deterministic + current (round-trip) and load-bearing (a hand-edit is caught
and named).

## Surfaces

| File | Surface | Read by |
| --- | --- | --- |
| `detail_counts.json` | whole-model part / BOM-row / derivation-log counts of the 5 shipped details | `test_site_model`, `test_viewer_data`, `test_spec`, `test_evidence_graph` |
| `site_divergence.json` | the pinned site divergence finding set, **with a per-finding justification note** | `test_site_model` |
| `slice_accounting.json` | site view slice-completeness counts | `test_site_views` |

## `frozen_truth/` — the imperative details' last testimony (milestone 4B)

`frozen_truth/{platform,rock_anchor,tree_attachment,trolley_launch}.json` are a
**different kind of baseline** from the ARCH0 surfaces above. Each detail is now
authored only as a `details/*.spec.yaml`; the imperative `details/*.py` mirrors it
once had have been retired (milestone 4B-4b). Before they were removed,
`scripts/capture_frozen_truth.py` **froze the imperative path's output** into these
files — its LAST TESTIMONY, captured at the base SHA stamped in each file
(`captured_at_sha`) — and the equivalence oracles were converted to assert
`spec == frozen corpus`. The corpus is now the fixed reference the compiled specs
are held against.

Each file captures everything the five oracles compare between the two paths:

- `geom_fingerprint` — per part: world origin, solid volume, bbox (transforms).
- `findings` — every validation finding as `(check, subject, passed)`, plus
  `by_kind` and `ok`.
- `bom` — the full `bom_table()` (every field, `length_mm` compared to 1e-6).
- `content_fp` — `baseline_lib.content_fingerprint` of the IMPERATIVE path (the
  full-content hash: findings + derivation facts + BOM + transforms). Kept as the
  annotated cross-path reference; NOT the value the oracle locks.
- `content_fp_spec` — the same hash of the SPEC path. **This is what the PROMOTE
  oracle locks** (`test_platform_promote_equiv`), because the spec is canonical
  after 4B-4b. Equals `content_fp` for three details; differs for the platform.
- `content_fp_divergence` — a full accounting of every `content_lines` difference
  between the two paths at freeze time (reworded assumption prose + the unrounded
  `length_mm` residual), with a human-readable `_note`; `{}` when they hash equal.
  The promote oracle asserts its `unexplained_*` fields are zero.
- `findings_fp` — the EVIDENCE validation-outcome hash (`baseline_lib.findings_fingerprint`).
- `connection_kind_types` / `counts` — the library-type identity + pinned counts.

Read by: `test_platform_spec`, `test_tree_attachment_spec`,
`test_trolley_launch_spec`, `test_evidence_equiv`, `test_platform_promote_equiv`.

### A2 re-freeze (task STRUCT #19) — semantics shift

STRUCT evolved three fragments **by design** (platform: tree-end legs + pier
blocks + per-post elevations + the declared tree-apron cantilever + the real
screened deck-notch clearance + support/existing roles; tree_attachment: trunk
extended to the cable-anchor height; trolley_launch: launch-hardware
re-registration + grab-bar re-derivation + the zipline hardware as `existing`
demonstration context). Their corpus is therefore **re-frozen from the SPEC path**
by the new `scripts/refreeze_from_spec.py` (`capture_frozen_truth.py` is left
untouched — it is the imperative-era generator and can no longer run).

The re-froze corpus's **meaning shifts** from "imperative last testimony" to the
**CURRENT-DESIGN determinism baseline**: the compiled spec must reproduce it
byte-for-byte on every build. Because there is no imperative path to compare
against, `content_fp == content_fp_spec` and `content_fp_divergence == {}` for the
three re-frozen files; `FROZEN_POSTDATING_KINDS` is now **empty** (the support
family is folded into the baseline, not set aside). The **imperative-era corpus
stays retrievable at commit `b52626b`**. **`rock_anchor.json` is NOT re-frozen**
(STRUCT did not evolve it) — it keeps its imperative framing and its 8088624
`captured_at_sha`.

**Regeneration:** the corpus is not regenerated by `regen_baselines.py` and is not
a rolling picture of the live model. `capture_frozen_truth.py` (imperative era)
cannot re-run — it raises a teaching error. The three evolved fragments regenerate
ONLY via `scripts/refreeze_from_spec.py`, with a justified, reviewed diff.

## The annotation channel

`site_divergence.json` carries a `note` per finding — the deferred-design
justification for why that failure is *expected*. Regeneration **preserves** the
note of every finding whose `(check, subject)` is unchanged, and **flags** any
finding that appeared or disappeared: a new finding is written with a
`TODO-JUSTIFY` placeholder, and `test_baselines.py` fails while any placeholder
remains — so an un-annotated pinned finding can never be committed. The 4
residual zipline findings and the site's `require_clean` gate are unchanged in
substance; only their storage moved out of Python literals into this file.
