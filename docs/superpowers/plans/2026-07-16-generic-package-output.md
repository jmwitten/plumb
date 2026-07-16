# Generic Package Output Implementation Plan

> **Execution note:** The user explicitly approved autonomous execution after planning. Implement this plan in the isolated `codex/generic-package-output` worktree and do not pause for an additional approval checkpoint.

**Goal:** Improve the reusable generic package so local image paths resolve, assembly starts with the interactive exploded viewer, structural screws can be selected by catalog reference, and new packages omit installation HTML by default.

**Architecture:** Preserve path information at the package projection boundary, compose the existing viewer into the generic instruction renderer, add a small typed JSON catalog consumed by `StructuralScrew`, and make installation output an explicit opt-in. Keep project-specific proof changes confined to the 2x4 input spec and comparison artifact.

**Tech stack:** Python 3.12, pytest, CadQuery, static HTML/CSS/JavaScript, JSON package data.

---

### Task 1: Preserve complete package-relative image paths

**Files:**
- Modify: `tests/test_package_projections.py`
- Modify: `tests/test_package_documents.py`
- Modify: `src/package/projections.py`
- Modify: `src/package/builder.py`

1. Change the existing projection/document assertions to require `views/iso.png` and verify the rendered `src` value.
2. Run the two focused tests and observe the old basename-only behavior fail.
3. Preserve supplied relative paths in `technical_projection`; have `build_package` derive those paths from the package root.
4. Re-run the focused tests.

### Task 2: Put the existing exploded viewer at the top of assembly

**Files:**
- Modify: `tests/test_package_builder.py`
- Modify: `src/package/builder.py`
- Modify: `src/rendering/instruction_manual.py`

1. Extend the existing generic builder integration test to require viewer markup, `Explode`, an embedded GLB/payload, `views/iso.png`, and viewer ordering before the first panel.
2. Run the focused integration test and observe the missing viewer fail.
3. Build the instruction viewer payload from the compiled detail/manual; deterministically gzip/base64 the exported GLB.
4. Add an optional viewer input to the generic manual renderer, inline existing viewer assets, map its theme variables, render it before overview/panels, and hide it in print.
5. Re-run the focused integration test.

### Task 3: Add and consume the screw catalog

**Files:**
- Create: `src/catalogs/__init__.py`
- Create: `src/catalogs/screws.py`
- Create: `src/catalogs/screws.json`
- Modify: `pyproject.toml`
- Modify: `tests/test_wood_screw.py`
- Modify: `tests/test_scope_manifest.csv`
- Modify: `src/components/fasteners.py`
- Modify: `src/rendering/instruction_panels.py`
- Modify: `src/rendering/web_viewer/__init__.py`

1. Add tests proving a `structural_screw` spec resolves a known catalog reference into geometry, retailer-style reader size, purchase source, and a non-existing viewer part; add error tests for unknown and conflicting inputs.
2. Classify the new test nodes in the scope manifest and run them to observe missing catalog support fail.
3. Add the validated JSON snapshot and typed cached loader with duplicate/schema checks and loud unknown-reference diagnostics.
4. Make `StructuralScrew` resolve either explicit dimensions or `catalog_ref`, retaining backward compatibility and separating catalog identities in the BOM.
5. Prefer catalog display size in manual surfaces and honor an explicit `existing=False` in the viewer rather than treating a retailer source as an existing site feature.
6. Re-run the catalog tests plus existing wood-screw, instruction-panel, authoring-manifest, and viewer tests.

### Task 4: Omit installation HTML by default, retain explicit rendering

**Files:**
- Modify: `tests/test_package_documents.py`
- Modify: `tests/test_package_builder.py`
- Modify: `src/package/documents.py`
- Modify: `src/package/builder.py`
- Modify: `README.md`

1. Change the existing document writer test to require no installation file by default and to prove an explicit installation model still writes one.
2. Extend the builder test to require no emitted or manifested `installation.html`; run and observe failure.
3. Make `installation` optional in `write_package_documents` and stop projecting/passing it in `build_package`.
4. Update the quick-start artifact description and re-run focused package tests.

### Task 5: Project proof and comparison

**Files:**
- Modify in project worktree: `details/built_up_2x4.spec.yaml`
- Generate in vault: `05_Attachments/Organized/Built-Up 2x4 Drawings/2026-07-16/generic-full-package-improved/`
- Update the existing Built-Up 2x4 vault project note.

1. Replace explicit screw diameter/length in the project spec with one generic catalog reference; do not add a 2x4-specific platform rule.
2. Run focused platform tests, then the repository-wide suite.
3. Generate a fresh preview package with the improved platform, leaving the previous package untouched.
4. Verify links and artifacts mechanically; render/open `technical.html` and `assembly.html`, exercise the viewer/explode control, and capture comparison screenshots.
5. Compare before/after artifact lists, HTML ordering, image references, BOM terminology/source, and installation output.
6. Update the vault record with results and links.

### Task 6: Release the changes

1. Review diffs and confirm unrelated dirty files were not touched.
2. Commit and push the platform branch, project-spec branch, and vault update separately.
3. Report test evidence, output comparison, remaining limitations, and clickable output paths.
