# Adversarial review — INSTALL axes branch, REGRESSION / RE-PIN-LEGITIMACY lens

**Tree under test:** worktree `wt-install-axes`, branch `sdd/install-axes`, tip `d8737f4`
(merge of branch `5e62c29` + master `5feee8a`; merge-base verified = `267d91b`).
**Reviewer stance:** fresh, read-only; every claim below independently reproduced.
**Import path verified** before every run: `detailgen.__file__` →
`<worktree>/.shim/detailgen/__init__.py`.

## Verdict: MERGE

No weakened pin, no silenced failure, no lost merge hunk, no unjustified frozen-truth
churn found. Every probe the lens demanded reproduced the report's claims exactly.

---

## 1. Re-pin audit (`git diff 267d91b..5e62c29 -- tests/`) — every re-pin SPECIFIC, none loosened

Read every hunk of all 16 changed/new test files. Findings:

- **Exact counts everywhere, and several pins got STRONGER than what they replaced:**
  - `test_platform_spec.py`: old `len(blocking) == 3` → new exact
    `Counter({foundation_capacity: 3, install_access: 2})` (per-check counts where only
    a length was pinned before).
  - `test_platform_detail.py`: helper renamed and re-pinned to the same exact Counter;
    all 6 call sites intact (20 → 20 test functions).
  - `test_site_model.py`: set-of-checks pin → exact Counter {capacity×3, access×3} PLUS
    a named-finding pin (`"rod 1"` subject must contain `"rung 0"` in its detail).
  - `test_site_model_report.py`: `len(blocking) == 6` + every blocker's subject must
    appear escaped in the rendered section.
  - `test_armchair_caddy_e2e.py`: `report.ok` → exact
    `Counter({install_termination: 12, install_access: 4})` failures, message substrings
    ("entry face buried", "mid-plate"), exact `Counter({install_access: 8})` UNKNOWNs
    all naming "sofa arm", harness string `"failures: 16" and "blocking: 24"`. Plus a
    NEW test (`test_render_refuses_but_documentation_still_renders`) pinning the gate
    split live.
  - `test_step_stool_e2e.py`: exact 4 access FAILs, every one asserted to carry
    "head stationed AT the joint interface" + "station-not-face", and
    `blocking == failures` (no UNKNOWNs allowed to sneak in).
  - `test_trebuchet_e2e.py`: exact 18 termination FAILs, every one carrying
    "embedment below the declared minimum" + "[assumption]", `blocking == failures`.
  - `test_sit_reach_frame_e2e.py`: exact `Counter({(install_access, UNKNOWN): 8})`,
    every blocker's subject "rail screw" + verbatim "UNKNOWN — install-order dependent".
  - `test_affected_region.py`: `45` → `45 + 164` (exact, not `>=`), and the
    unattributed-kind set extended by exactly the two axis kinds (exact set equality).
  - `test_cl3_expect_retire.py`: closure `8 → 10` with the two new members asserted BY
    NAME (`("install_termination", "tree lag +Y: lag bolt")` etc.).
  - `test_inspector_payload.py`: `6 → 5` unknown families with the POSITIVE assertion
    that "Fastener installability" left the unknown set — not just a count drop.
  - `test_coverage_matrix.py`: three positive `family_of()` pins added; the two
    `md.count("UNKNOWN") >= 5` bounds were `>=` before and the bound went UP to 6.
- **The two `assert report.ok` → `assert not report.ok` flips in perf tests**
  (caddy/stool/frame `test_full_flow_is_fast`) are deliberate truth-pins with comments
  pointing at the specific honest-red test; they will trip when the fix arcs land —
  the correct behavior for a deliberate re-pin.
- **Nothing deleted, nothing dodged:** test-function counts per changed file are
  monotone (only caddy +1); grep over the whole branch test diff for added
  `skip`/`xfail`/`except` → **zero hits**.
- `test_doc_build_blocked_detail.py` kept its set-shaped pin (was set-shaped before,
  now two elements); the exact counts are pinned in `test_platform_spec` /
  `test_foundation_obligation`, so no coverage gap.

## 2. Frozen-truth refreeze — structured JSON diff (not eyeball)

Multiset diff of the `findings` triples between `267d91b` and `d8737f4` versions:

| file | removed | added | other keys |
|---|---|---|---|
| platform.json | **0** | install_termination(ok)×82, install_access(ok)×80, install_access(not-ok)×2 — exactly the 2 toe-screw UNKNOWNs | `by_kind` +2 install kinds, `counts.derivation_log` 722→762, `geom_fingerprint`/`bom`/`content_fp_divergence`/`connection_kind_types` **identical**, `ok` False→False |
| rock_anchor.json | **0** | install_termination(ok)×4, install_access(ok)×4 | `geom_fingerprint`/`bom`/divergence identical, `ok` True→True |

The report's "1e-6 transform pins did NOT move (no geometry changed)" is corroborated
by the byte-identical `geom_fingerprint` in both files.

**Tree/trolley revert claim verified:** `git diff 267d91b..d8737f4 --name-only --
tests/baselines/frozen_truth/` lists ONLY platform.json + rock_anchor.json;
tree_attachment.json and trolley_launch.json are byte-identical to 267d91b.

## 3. `detail_counts` platform 762 — recomputed live

Compiled `details/platform.spec.yaml` in the worktree (import path verified),
`validate()`, then `len(detail.derivation_log)` → **762** (the count is taken
post-validate, matching `baseline_lib.py`'s recipe). Also recomputed live:
install_termination 82 / install_access 82, failures 0, blocking
`Counter({foundation_capacity: 3, install_access: 2})` — the exact new pins.
Arithmetic checks: +40 facts = 10 hangers × 4; +164 findings = 82 fasteners × 2 axes.

## 4. Textlayer golden vs BOTH parents

- Branch-side content (267d91b..5e62c29): exclusively the install family rows
  (NOT ANALYZED → UNRESOLVED with 172 site / 164 platform / PASS 8 rock-anchor
  counts), the site open-findings block 3→6 with the three named install_access
  UNKNOWNs, the divergence table, and the two narrative count strings. Nothing else.
- Master-side content: the single DRAWDIM deck-notch station line.
- The merged file's diff against EACH parent equals the OTHER parent's diff
  **byte-for-byte** (diff-of-diffs, only blob-index lines differ). No churn, no loss.

## 5. DRAWDIM merge resolution (d8737f4)

- Merge-base(5e62c29, 5feee8a) = 267d91b, confirmed.
- File-name lists: `diff(5e62c29..d8737f4)` == master-side name list;
  `diff(5feee8a..d8737f4)` == branch-side name list. Exactly two files touched by
  both sides: `tests/test_trebuchet_e2e.py`, `tests/baselines/consolidated_doc.textlayer.html`.
- Non-overlapping content: full-patch diff-of-diffs in both directions (excluding the
  two overlap files) → **empty**. Neither side lost a hunk anywhere.
- `test_trebuchet_e2e.py`: the merged file carries BOTH master's DRAWDIM/V5
  sheet-and-station guards (verified hunk-identical vs 267d91b..5feee8a) AND the
  branch's honest-embedment re-pin (hunk-identical vs 267d91b..5e62c29). And the
  module **runs green at the merge tip** (below) — both halves are simultaneously true.

## 6. 33-failure triage — 5+ sampled, each re-pinned TRUE, none silenced

The intermediate run (1027 passed / 33 failed = exactly the 1060-test baseline) was at
the core commit before re-pins. Sampled failures → their re-pins → independently
verified TRUE at tip:

1. caddy `test_compiles_and_validates_clean` → exact 12+4 FAIL / 8 UNKNOWN pin —
   **ran green live** (module run below).
2. `test_platform_spec::test_spec_findings_match_frozen_truth` → refrozen corpus —
   **structural diff shows only the install additions** (item 2), and the by-kind
   multiset equality still holds at tip (module asserts it; live compile matches).
3. `test_site_model::test_site_blocks_on_*` → Counter{3,3} + named rod-vs-rung pin —
   the composed truth is also independently exercised by
   `test_install_sweep::test_site_composed_connections_drive_the_same_checks` (green).
4. `test_inspector_payload` 6→5 → carries the positive left-the-set assertion; the
   rock anchor's 8 install PASSes verified in the frozen-truth diff and live sweep run.
5. `test_affected_region` 45→209 → exact-count pin backed by a REAL soundness change
   (`EvidenceGraph._link_finding` deliberately zero-attributes the two axis kinds —
   read the src diff; `install_method` keeps attribution as claimed).
6. detail_counts 722→762 → **recomputed live = 762**.

Every sampled re-pin asserts the new truth with exact values; no assertion was deleted
or broadened to absorb the failure.

## 7. Targeted runs (worktree venv python, shimmed, import verified)

`pytest -q -p no:xdist tests/test_install_axes.py tests/test_install_sweep.py
tests/test_armchair_caddy_e2e.py tests/test_step_stool_e2e.py
tests/test_trebuchet_e2e.py tests/test_sit_reach_frame_e2e.py`
→ **75 passed in 91.4s** (12 + 19 + 17 + 8 + 9 + 10 — matches the claimed module
counts, incl. the new caddy render-refusal test). Full suite deliberately left to the
controller per instructions.

Also verified while in there: the sweep's synthetic overshoot probe mutates spec TEXT
via `load_spec_text` (in memory, asserts the shipped value is present first — the
shipped spec untouched); the trebuchet handoff section's claim that the branch touches
no file under `details/` holds (`git diff --name-only` shows none).

## Notes (non-blocking)

- N1. `rock_anchor.json`'s `content_fp_spec` moved in the refreeze — expected (the
  content fingerprint covers the findings corpus, which grew by 8), and the invariant
  that matters (`geom_fingerprint`, `bom`, divergence fp) is byte-stable. No action.
- N2. `test_doc_build_blocked_detail.py`'s blocking pin is set-shaped (two members)
  rather than a Counter; exact counts for the same state are pinned in two other
  modules, so this is redundancy-covered, not a gap. No action.
- N3. The report's growth arithmetic (+34 = 31 new + 2 rewire parametrizations + 1
  caddy render test) is consistent with the per-file test-def counts measured here;
  the final 1094/3/1 figure itself is the controller's full-suite gate to confirm.
