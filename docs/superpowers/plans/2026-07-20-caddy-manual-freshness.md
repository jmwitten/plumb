# Caddy Manual Freshness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent Plumb releases from silently using stale compiler branches and replace the wooden diaper-caddy manual with progressively scoped, builder-readable instructions.

**Architecture:** The maintained Plumb plugin owns a read-only, fail-closed source-freshness preflight check. The compiler repository owns project-authored caddy stages and product-specific readability assertions. The package is regenerated only from the fresh compiler branch and replaces the delivered JoelBrain artifact after review.

**Tech Stack:** Python 3, `unittest`, `pytest`, Git CLI, Plumb DetailSpec YAML, deterministic HTML/PNG/STEP/GLB package generation.

## Global Constraints

- Preflight must not fetch, merge, rebase, checkout, or modify the selected compiler repository.
- The default authoritative source is the live `origin/main`, verified with `git ls-remote` and the local `origin/main` ref.
- Stale, diverged, missing-ref, or unreachable-remote states fail closed unless `PLUMB_ALLOW_STALE_SOURCE=1` is explicitly recorded.
- Generated HTML is never authoritative and must not be edited.
- Each caddy panel has one physical goal; no fastening panel may contain more than three connection instructions.
- Numbered picture keys identify at most four arriving workpieces and never identify individual fasteners.
- Existing geometry, dimensions, materials, 27-fastener inventory, honest UNKNOWN states, and architecture remain unchanged.
- Every production change follows a demonstrated red/green test cycle.
- All final claims require fresh plugin, platform, product, package-closure, and visual-review evidence.

---

### Task 1: Fail-closed compiler source freshness

**Files:**
- Modify: `/Users/joelwitten/plugins/plumb/.worktrees/preflight-freshness/tests/test_preflight.py`
- Modify: `/Users/joelwitten/plugins/plumb/.worktrees/preflight-freshness/scripts/plumb-preflight.py`

**Interfaces:**
- Consumes: `PLUMB_REPO`, `PLUMB_BASE_REF`, and `PLUMB_ALLOW_STALE_SOURCE` environment values.
- Produces: required check `source-freshness` and `git.source_freshness` evidence in `plumb-preflight/v1` JSON.

- [ ] **Step 1: Add real-Git test fixtures and failing freshness tests**

Add fixture helpers that initialize a primary repository, create `refs/remotes/origin/main`, create a selected worktree, then advance the authoritative ref. Assert that `inspect_environment()` returns `ready == False`, `source-freshness.ok == False`, and exact behind/ahead evidence. Add passing cases for a feature branch whose HEAD contains `origin/main`, a stale local tracking ref compared with `ls-remote`, and the explicit override.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
python3 -m unittest tests.test_preflight -v
```

Expected: the new tests fail because no `source-freshness` check exists.

- [ ] **Step 3: Implement the minimal read-only check**

Add helpers that resolve the base ref, parse `<remote>/<branch>`, call `git ls-remote --exit-code`, compare advertised and local tracked commits, use `git merge-base --is-ancestor`, and collect `git rev-list --left-right --count`. Append the check to `required_checks`; include its evidence under `git.source_freshness`. When the override is exactly `1`, return an explicit passing check with `override: true` and the underlying failure reason retained.

- [ ] **Step 4: Run focused tests and plugin validation**

Run:

```bash
python3 -m unittest tests.test_preflight -v
python3 /Users/joelwitten/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py /Users/joelwitten/plugins/plumb/.worktrees/preflight-freshness
```

Expected: all preflight tests pass and plugin validation succeeds.

- [ ] **Step 5: Commit the plugin source change**

```bash
git add scripts/plumb-preflight.py tests/test_preflight.py
git commit -m "fix: reject stale Plumb compiler checkouts"
```

### Task 2: Progressive caddy assembly and release gate

**Files:**
- Restore from accepted caddy source commit: `details/wooden_diaper_caddy.spec.yaml`
- Restore from accepted caddy source commit: `details/wooden_diaper_caddy.cert.yaml`
- Restore from accepted caddy source commit: `tests/test_wooden_diaper_caddy_release.py`
- Modify: `details/wooden_diaper_caddy.spec.yaml`
- Modify: `tests/test_wooden_diaper_caddy_release.py`
- Modify: `tests/test_scope_manifest.csv`

**Interfaces:**
- Consumes: public `sequence.stages`, subassembly completion, installation fastener markers, and generic instruction-manual projection from current `main`.
- Produces: an eight-panel caddy manual and product release assertions for panel scope and callout clarity.

- [ ] **Step 1: Bring the accepted caddy source onto the fresh branch**

Cherry-pick commit `aab9c57`, resolving only scope-manifest context if required. Confirm the resulting source diff contains the caddy spec, certification, release test, and scope rows without generated package files.

- [ ] **Step 2: Write the failing readability regression**

Compile the caddy and build its instruction manual in `tests/test_wooden_diaper_caddy_release.py`. Assert eight panels; fastening panel connection counts no greater than three; every `panel_fastener_ids()` result is excluded from `panel_callout_ids()`; and at most four numbered callouts per panel.

- [ ] **Step 3: Run the product release test and confirm RED**

Run through the source-bound launcher:

```bash
pytest tests/test_wooden_diaper_caddy_release.py -q
```

Expected: failure showing the unstaged caddy has four panels and an oversized fastening panel.

- [ ] **Step 4: Add progressive stages and completion semantics**

Declare the eight goals from the design spec using public `sequence.stages`, top-level `sequence.after`, and a named caddy subassembly. Put both handle glue connections in the bond stage and both handle-screw connections in the following fastening stage. Require each handle-screw connection to occur after both glue-connection cure events. Add a completion record that verifies all 27 screws, handle immobility, flush heads, smooth edges, flat bearing, and the existing stop-use conditions.

- [ ] **Step 5: Run the focused regression and product gates**

Run through the source-bound launcher:

```bash
pytest tests/test_wooden_diaper_caddy_release.py -q
pytest --detail-gate wooden_diaper_caddy --detail-cadence inner -q
pytest --detail-gate wooden_diaper_caddy --detail-cadence release -q
```

Expected: focused, inner, and release tests pass.

- [ ] **Step 6: Commit the product source change**

```bash
git add details/wooden_diaper_caddy.spec.yaml details/wooden_diaper_caddy.cert.yaml tests/test_wooden_diaper_caddy_release.py tests/test_scope_manifest.csv
git commit -m "fix: make caddy assembly progressively buildable"
```

### Task 3: Regenerate, review, install the guard, and deliver

**Files:**
- Replace: `/Users/joelwitten/Code/JoelBrain/05_Attachments/Organized/Wooden Diaper Caddy_Plumb Package/`
- Update: `/Users/joelwitten/Code/JoelBrain/04_Archive/04_Side Projects/Diaper Caddy - Plumb Design Brief.md`
- Update: `/Users/joelwitten/plugins/plumb/.worktrees/preflight-freshness/.codex-plugin/plugin.json`

**Interfaces:**
- Consumes: verified plugin source and fresh compiler product branch.
- Produces: installed Plumb plugin guard, refreshed deterministic package, current review evidence, and committed vault delivery.

- [ ] **Step 1: Run platform verification**

Run the preflight-provided `platform_integration` command through the source-bound launcher. Require zero failures before package generation.

- [ ] **Step 2: Generate one complete caddy package**

Use the current package builder and canonical caddy spec to a temporary output directory. Do not edit generated files. Record source commit, spec hash, command, timings, and artifact hashes.

- [ ] **Step 3: Review every panel and classify the original finding**

Inspect all panel PNGs plus assembly, fabrication, technical, manifest, validation, and review evidence. Verify arrivals, fastener targets, action wording, cure order, completion checks, desktop/mobile/print containment, and interactive payload. Record the original density concern as repaired product-blocking instruction usability.

- [ ] **Step 4: Replace the vault package and update the project note**

Move the existing package to a temporary backup, copy the approved package into the exact delivery path, validate closure and hashes, then remove the backup only after successful validation. Update the archived note with the progressive-panel repair and new source fingerprints.

- [ ] **Step 5: Update and reinstall the maintained plugin**

Run the plugin-creator cachebuster helper against the plugin worktree, validate the plugin, and reinstall with `codex plugin add plumb@personal`. Confirm the newly cached preflight rejects the intentionally stale `codex/plumb-fast-lane` checkout and accepts the refreshed caddy branch.

- [ ] **Step 6: Run final verification and commit/push**

Freshly rerun plugin tests, platform integration, caddy inner/release gates, package closure, `git diff --check`, and repository status. Commit the plugin, compiler, and vault changes. Push repositories that have remotes; report any repository without a configured remote as local-only rather than claiming it was pushed.
