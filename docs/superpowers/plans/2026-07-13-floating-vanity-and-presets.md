# Floating Vanity and Fast Authoring Implementation Plan

> Execution contract: implement in small TDD increments and preserve the
> release-honesty boundary in the accompanying spec.

**Goal:** Add an opt-in floating-vanity compiler and versioned cabinetry
archetypes without changing the base DetailSpec language.

**Architecture:** `vanity.frameless@1` owns a strict authoring schema and
semantic model, reuses stable cabinetry dataclasses/catalog adapters, and lowers
to ordinary components and relationships. A pre-parse archetype expander turns
compact declarations into the same existing strict schemas.

## Task 1: Lock the vanity authoring contract

- Add failing schema tests for required wall-hung dimensions, backing,
  plumbing keepout, loads, and mount evidence.
- Implement immutable declarations and strict parsers.
- Register `vanity.frameless@1` without activating it implicitly in other
  projects.

## Task 2: Generate the physical model

- Add failing model/lowering tests for carcass, rail, backing, fasteners, and
  plumbing-clear geometry.
- Generate parts and provenance.
- Lower bonds, contacts, expected overlaps, and existing-context roles.
- Run the unchanged base compiler and geometry sweep.

## Task 3: Enforce the wall-hung release boundary

- Add failing validation tests for missing/unverified backing, insufficient
  anchor targets, keepout conflict, embedment, and mount-engineering UNKNOWN.
- Implement deterministic findings/evidence.
- Prove only a referenced, verified project-specific mount review can change
  the structural assembly finding to PASS.

## Task 4: Produce shop and installation artifacts

- Add failing artifact tests for cut list, hardware, fabrication, assembly,
  temporary support, anchoring, plumbing, sealing, leak test, and commissioning.
- Reuse JSON-safe cabinet artifact shapes where compatible.
- Add a real example project that remains release-blocked until its illustrative
  mount review is explicitly marked verified.

## Task 5: Add preset expansion

- Add failing tests for named/versioned archetypes, overrides, unknown keys,
  deterministic run placement, and manifest traceability.
- Implement expansion before strict domain parsing.
- Add compact examples for B30, a straight run, and a floating vanity.
- Assert compact and fully expanded projects produce equivalent lowered models.

## Task 6: Integration gate

- Run focused pack tests after every task.
- Build wheel/sdist and inspect that both pack surfaces ship.
- Merge completed STEPDOC only after its isolated implementation lands.
- Run the complete test suite, deterministic artifact checks, and an adversarial
  review before branch handoff.

