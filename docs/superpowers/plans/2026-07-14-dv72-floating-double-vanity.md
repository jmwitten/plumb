# DV72 Floating Double-Sink Vanity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a tested, linked four-document DV72 coordination package from the reusable cabinet pack without misrepresenting unresolved release facts.

**Architecture:** Extend `vanity.double_sink@1` with pinned drain, trap, runner, and comparative mount evidence, then project the single compiled model into four small self-contained HTML reader surfaces. Preserve the existing DetailSpec lowering and UNKNOWN release gates.

**Tech Stack:** Python 3.12, frozen dataclasses, CadQuery/DetailSpec, deterministic HTML/SVG, pytest.

## Global Constraints

- Geometry uses millimetres internally and manufacturer dimensions retain source URLs and revisions.
- All nine unresolved release facts remain UNKNOWN.
- Generated artifacts remain under `outputs/` and are not committed.
- The four documents link to each other and each has one clear reader purpose.
- The primary section shows sinks, plumbing, drawers, countertop, and wall mounting.

---

### Task 1: Lock the four-document contract

**Files:**
- Create: `tests/test_double_vanity_documents.py`
- Modify: `src/packs/cabinetry/double_vanity_document.py`
- Create: `scripts/double_vanity_documents.py`

**Interfaces:**
- Consumes: `PackedProject` from `compile_project_file()`.
- Produces: `build_double_vanity_document_set(project) -> dict[str, str]` and four deterministic HTML files.

- [ ] Write failing tests asserting exact filenames, reciprocal safe relative links, document-specific headings, no `file://` links, and validation ownership of all nine release rows.
- [ ] Run `pytest tests/test_double_vanity_documents.py -q` and confirm failure because the set builder is absent.
- [ ] Implement shared navigation and the four focused builders by composing existing model-backed section functions.
- [ ] Run the focused tests and confirm all pass.
- [ ] Commit the document contract.

### Task 2: Pin product evidence and service facts

**Files:**
- Modify: `src/packs/cabinetry/double_vanity.py`
- Modify: `tests/test_double_sink_vanity.py`

**Interfaces:**
- Consumes: manufacturer adapter dimensions and source URLs.
- Produces: drain/trap/mount comparison manifests and model facts without changing release authority.

- [ ] Write failing tests for K-7124-A drain, K-8998 trap, MOVENTO 18-in candidate, and Rakks comparative support facts.
- [ ] Run the focused tests and confirm the new manifest keys are missing.
- [ ] Add immutable adapters and expose them through catalog/source/derived manifests; keep placement provisional and wall capacity UNKNOWN.
- [ ] Run focused model and document tests.
- [ ] Commit product evidence.

### Task 3: Generate the linked deliverables and timing record

**Files:**
- Modify: `scripts/double_vanity_documents.py`
- Create: `docs/projects/dv72/time-log.md`

**Interfaces:**
- Consumes: the checked-in DV72 project fixture.
- Produces: four linked HTML files in `outputs/floating_double_sink_four_drawer/` plus a committed elapsed-time ledger.

- [ ] Add a failing generator test for two-run byte equality and exact output inventory.
- [ ] Run it and confirm failure before generation is implemented.
- [ ] Implement one compile followed by four projections and SHA-256 reporting.
- [ ] Generate the document set and visually inspect the review section and navigation.
- [ ] Record time by reused-platform, bespoke-product, document, and verification buckets.
- [ ] Commit the generator and ledger.

### Task 4: Review, fix, and release branch

**Files:**
- Modify: files identified by the two requested reviews.

**Interfaces:**
- Consumes: git range from `origin/main` to branch HEAD and generated outputs.
- Produces: review findings resolved or explicitly retained with rationale.

- [ ] Run focused double-vanity tests and the complete suite.
- [ ] Request an adversarial technical review with no write access.
- [ ] Request a no-context handyman review of the four generated documents.
- [ ] Write a failing regression test for each accepted Important defect, then fix it.
- [ ] Regenerate documents and run the complete verification commands again.
- [ ] Commit, push `codex/72-floating-double-vanity`, and report acceleration/custom-work lessons.
