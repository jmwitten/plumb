# Plumb Lean Full-Package Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep Plumb's complete concept, model, documentation, review, and delivery lifecycle while routing ordinary supported projects through the generic package CLI with bounded initial context and an eight-minute execution target.

**Architecture:** The plugin remains the lifecycle orchestrator, but it changes from precedent-led source exploration to capability-led execution. It runs preflight, queries the compact authoring manifest, authors the governed spec, invokes `detailgen.package` once, reviews generated evidence, and escalates to `plumb-extend` only when a concrete compiler diagnostic identifies missing public vocabulary.

**Tech Stack:** Markdown Codex skills, Python `unittest`, JSON prompt fixtures, the local plugin cachebuster/reinstall workflow, and the public `detailgen.authoring` / `detailgen.package` CLIs.

## Global Constraints

- Repository: `/Users/joelwitten/plugins/.worktrees/plumb`.
- Core prerequisite: the generic full-package compiler plan must be available in `/Users/joelwitten/Code/construction-detail-generator`.
- Preserve the complete lifecycle; this is not a model-only or reduced-document path.
- Preserve three materially different concepts and governed approval when concept selection is applicable.
- Ordinary project startup may not read roadmap, progress, full precedent specs, generated precedent packages, tests, or review stores.
- Actual compiler-extension work still reads the relevant roadmap, implementation, and tests through `plumb-extend`.
- Initial authoring decision deadline: 60 seconds.
- Initial source context budget: four targeted sections or approximately 400 lines.
- Invoke the generic package compiler once per ordinary project run.
- Do not add any production reference to the July 16 simple-assembly experiment.

---

### Task 1: Pin the ordinary-project execution contract in plugin tests

**Files:**
- Modify: `tests/test_skill_contracts.py`
- Modify: `tests/prompt-evals.json`

**Interfaces:**
- Consumes: Plumb skill Markdown.
- Produces: a static contract proving full lifecycle, bounded startup context, generic CLI use, and extension-only roadmap loading.

- [ ] **Step 1: Add a reusable fast full-package assertion**

```python
def assert_ordinary_full_package_contract(test: unittest.TestCase, name: str) -> None:
    text = " ".join(skill_text(name).split())
    assert_terms(test, text, (
        "AUTHORING_DECISION_DEADLINE: 60 seconds",
        "INITIAL_CONTEXT_BUDGET: four targeted sections or approximately 400 lines",
        "python -m detailgen.authoring",
        "python -m detailgen.package",
        "compile exactly once",
        "complete package",
        "concept governance",
        "fabrication",
        "assembly",
        "installation",
        "review",
        "delivery",
    ))
    test.assertIn(
        "Do not read roadmap, progress, complete precedent packages, tests, or "
        "review stores during ordinary-project startup",
        text,
    )
    test.assertIn(
        "Load roadmap state only after a concrete compiler capability gap routes "
        "the work to plumb-extend",
        text,
    )
```

Call this helper from `test_design_orchestration_order`.

- [ ] **Step 2: Add a generic ordinary-project routing fixture**

Append this fixture without naming the experiment:

```json
{
  "prompt": "Use Plumb to generate the complete fabrication, assembly, installation, and review package for a small owner-specified assembly using existing registered components. Skip project tests.",
  "expected_primary": "plumb-design",
  "expected_sequence": ["plumb-concept", "detailgen.package", "plumb-review", "delivery"]
}
```

Update the inventory count assertion from `6` to `7`; the positive skill set and two negative cases remain unchanged.

- [ ] **Step 3: Run the contract tests and confirm the expected failures**

Run: `python3 -m unittest tests.test_skill_contracts -v`

Expected: failures name the missing authoring deadline, context budget, and generic CLI contract.

- [ ] **Step 4: Commit the red contract**

```bash
git add tests/test_skill_contracts.py tests/prompt-evals.json
git commit -m "test: pin lean full-package Plumb orchestration"
```

---

### Task 2: Rewrite `plumb-design` around the public package compiler

**Files:**
- Modify: `skills/plumb-design/SKILL.md`

**Interfaces:**
- Consumes: preflight, `python -m detailgen.authoring`, approved design-review state, a `DetailSpec`, and `python -m detailgen.package`.
- Produces: the complete package and a deterministic escalation to `plumb-extend` only for public capability gaps.

- [ ] **Step 1: Replace unconditional initial reading with this bounded startup contract**

Add this section immediately after preflight:

```markdown
## Ordinary-project startup contract

**AUTHORING_DECISION_DEADLINE: 60 seconds.**

**INITIAL_CONTEXT_BUDGET: four targeted sections or approximately 400 lines.**

For a project request, run preflight and then run:

```bash
"$PLUMB_PYTHON" -m detailgen.authoring
```

Use that manifest plus the user brief to decide whether the registered public
vocabulary can express the project. Do not read roadmap, progress, complete
precedent packages, tests, or review stores during ordinary-project startup.
Do not preload sibling skills; read each immediately before its stage.

Load roadmap state only after a concrete compiler capability gap routes the work
to plumb-extend. A missing type, parameter, connection role, renderer behavior,
or generated-document projection is a capability gap. Unfamiliarity is not: use
the public manifest and compiler diagnostic before reading implementation.
```

Set `PLUMB_PYTHON` from preflight's returned `paths.python`; do not assume the caller's active virtualenv.

- [ ] **Step 2: Preserve the lifecycle while removing bespoke package authoring**

Replace the package-generation stage with:

```markdown
## Generate the complete package

The complete package still includes concept governance, the authoritative
DetailSpec, model exports, drawings, fabrication guide, assembly manual,
installation/commissioning guide, design-review evidence, visual-review
evidence, hashes, trace, and delivery records.

Do not create a project-specific renderer, document generator, report registry
entry, or handwritten package manifest. Invoke the generic compiler:

```bash
"$PLUMB_PYTHON" -m detailgen.package "$SPEC_PATH" \
  --out "$PACKAGE_DIR" --preview
```

When the user explicitly requests skipped tests, append
`--tests-skipped owner-request`. A skipped status is not a pass claim.

The package compiler must compile exactly once. If the command reports a
capability gap, stop this ordinary-project path, read and execute
`../plumb-extend/SKILL.md`, then return to this exact command after the reusable
extension lands.
```

- [ ] **Step 3: Add execution budgets and abort rules**

```markdown
## Execution budget

- 0:30 preflight and classification
- 1:00 capability decision
- 2:00 governed spec ready
- 2:30 compile and validate once
- 5:15 all package artifacts generated
- 6:30 contact-sheet and document review complete
- 7:15 trace and hashes complete
- 8:00 commit, push, vault delivery, and response complete

At 60 seconds without an authoring decision, stop broadening context and state
the unresolved public capability. Never compensate for lateness with bespoke
project code. Allow at most one complete regeneration. Record actual elapsed
time, initial files/lines read, compiler invocations, regenerations, and
project-specific production-code additions in the final trace.
```

- [ ] **Step 4: Run the skill contract test**

Run: `python3 -m unittest tests.test_skill_contracts.SkillContractTests.test_design_orchestration_order -v`

Expected: the design orchestration test passes.

- [ ] **Step 5: Commit the design workflow**

```bash
git add skills/plumb-design/SKILL.md
git commit -m "feat: route Plumb through generic full-package compiler"
```

---

### Task 3: Make concept and review stages load context lazily

**Files:**
- Modify: `skills/plumb-concept/SKILL.md`
- Modify: `skills/plumb-review/SKILL.md`
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**
- Consumes: the same governed concept and review artifacts as today.
- Produces: unchanged lifecycle outcomes with stage-local context rather than startup preloading.

- [ ] **Step 1: Add failing stage-local context assertions**

```python
def test_concept_and_review_context_is_stage_local(self):
    concept = " ".join(skill_text("plumb-concept").split())
    review = " ".join(skill_text("plumb-review").split())
    self.assertIn("Use the authoring manifest before implementation source", concept)
    self.assertIn("Repository precedent is fallback context, not startup context", concept)
    self.assertIn("Start from the generated package manifest and review manifest", review)
    self.assertIn("Read implementation only for a concrete finding", review)
```

- [ ] **Step 2: Run the new test and confirm it fails**

Run: `python3 -m unittest tests.test_skill_contracts.SkillContractTests.test_concept_and_review_context_is_stage_local -v`

Expected: failure on the missing stage-local wording.

- [ ] **Step 3: Narrow concept-stage repository context without reducing governance**

In `plumb-concept`, retain three materially different concepts, precedent provenance, the comparison matrix, visuals, approval fingerprint, and stop at `approved_for_modeling`. Replace unconditional repository implementation/precedent reads with these rules:

```markdown
Use the authoring manifest before implementation source. External construction
precedents support concept claims; a repository project is not required merely
because it already generated a package. Repository precedent is fallback
context, not startup context: load one targeted slice only when it answers a
specific construction or public-interface question within the context budget.
```

- [ ] **Step 4: Narrow review-stage source exploration**

In `plumb-review`, make the generated outputs the entry point:

```markdown
Start from the generated package manifest and review manifest. Confirm artifact
closure, fingerprints, hashes, explicit UNKNOWN states, and standard/contact-
sheet views before reading source. Read implementation only for a concrete
finding whose owning layer cannot be determined from those manifests and the
authoritative spec. Do not load a complete reference package by default.
```

Keep desktop, mobile, print, interactive, fabrication, installation, and trace review obligations unchanged.

- [ ] **Step 5: Run all skill contracts**

Run: `python3 -m unittest tests.test_skill_contracts -v`

Expected: all plugin skill contracts pass.

- [ ] **Step 6: Commit lazy stage loading**

```bash
git add skills/plumb-concept/SKILL.md skills/plumb-review/SKILL.md tests/test_skill_contracts.py
git commit -m "fix: bound Plumb stage context loading"
```

---

### Task 4: Extend routing evidence with full-lifecycle expectations

**Files:**
- Modify: `scripts/evaluate_routing.py`
- Modify: `tests/test_routing_evaluator.py`

**Interfaces:**
- Consumes: `expected_sequence` from `tests/prompt-evals.json` and the Codex final response.
- Produces: routing evidence that distinguishes the primary skill from the required full-lifecycle sequence.

- [ ] **Step 1: Write the sequence-marker tests**

```python
def test_observed_sequence_reads_one_ordered_marker():
    output = "PLUMB_SEQUENCE: plumb-concept > detailgen.package > plumb-review > delivery\n"
    assert observed_sequence(output) == (
        ["plumb-concept", "detailgen.package", "plumb-review", "delivery"], []
    )


def test_observed_sequence_rejects_duplicate_markers():
    output = "PLUMB_SEQUENCE: a > b\nPLUMB_SEQUENCE: a > b\n"
    sequence, issues = observed_sequence(output)
    assert sequence is None
    assert issues == ["ambiguous sequence marker"]
```

- [ ] **Step 2: Run the evaluator tests and confirm the missing function**

Run: `python3 -m unittest tests.test_routing_evaluator -v`

Expected: failure because `observed_sequence` does not exist.

- [ ] **Step 3: Implement the sequence marker**

```python
SEQUENCE_MARKER = re.compile(r"^PLUMB_SEQUENCE:\s*(.+?)\s*$", re.MULTILINE)


def observed_sequence(final_output: str):
    markers = SEQUENCE_MARKER.findall(final_output)
    if len(markers) != 1:
        return None, ["missing sequence marker" if not markers else "ambiguous sequence marker"]
    return [part.strip() for part in markers[0].split(">") if part.strip()], []
```

When a fixture has `expected_sequence`, make `controller_prompt()` request both `ROUTING_PRIMARY` and `PLUMB_SEQUENCE`, compare the parsed sequence in `evaluate_cases()`, and store `observed_sequence` in the evidence report. Cases without `expected_sequence` remain primary-only.

- [ ] **Step 4: Run unit and read-only routing evaluations**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/evaluate_routing.py \
  --workdir /Users/joelwitten/Code/construction-detail-generator \
  --evidence-dir /tmp/plumb-routing-evidence
```

Expected: unit tests pass and every routing fixture reports `passed: true`.

- [ ] **Step 5: Commit the routing evidence update**

```bash
git add scripts/evaluate_routing.py tests/test_routing_evaluator.py
git commit -m "test: verify Plumb full-lifecycle routing sequence"
```

---

### Task 5: Validate, reinstall, and run the external eight-minute acceptance

**Files:**
- Modify: `.codex-plugin/plugin.json` through the cachebuster helper only.

**Interfaces:**
- Consumes: the updated local plugin and generic core CLI.
- Produces: a validated/reinstalled plugin and measured external acceptance evidence.

- [ ] **Step 1: Validate skill and plugin structure**

Run:

```bash
python3 /Users/joelwitten/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/joelwitten/plugins/.worktrees/plumb
python3 /Users/joelwitten/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py /Users/joelwitten/plugins/.worktrees/plumb
python3 -m unittest discover -s tests -v
```

Expected: all three commands succeed.

- [ ] **Step 2: Commit the validated plugin source**

```bash
git add skills scripts tests .codex-plugin/plugin.json
git commit -m "feat: deliver lean full-package Plumb workflow"
```

- [ ] **Step 3: Refresh the cachebuster using the required helper**

Run:

```bash
python3 /Users/joelwitten/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py \
  /Users/joelwitten/plugins/.worktrees/plumb
git add .codex-plugin/plugin.json
git commit -m "chore: refresh Plumb plugin cachebuster"
```

Expected: the version retains `0.1.0+codex.` and replaces the old suffix once.

- [ ] **Step 4: Read the marketplace name and reinstall**

Run:

```bash
python3 /Users/joelwitten/.codex/skills/.system/plugin-creator/scripts/read_marketplace_name.py
codex plugin add plumb@personal
```

If the helper prints a marketplace name other than `personal`, substitute that exact value in the second command. Do not edit marketplace files manually.

- [ ] **Step 5: Start a fresh Codex task and replay the external experiment**

Use the existing experimental spec as an input path to `detailgen.package`; do not cherry-pick its project-specific renderer, report registration, or document script into the core implementation. The task instruction retains the original request to skip project tests.

Record:

- elapsed time from accepted brief/selection to delivered vault package;
- initial files and approximate source lines read;
- number of compiler invocations;
- number of full regenerations;
- project-specific production-code lines added;
- package artifact count and manifest path.

Acceptance:

```text
elapsed < 8:00
initial context <= 4 targeted sections / approximately 400 lines
compiler invocations = 1
full regenerations <= 1
project-specific production-code additions = 0
complete package present
tests.status = skipped
```

- [ ] **Step 6: Record results without adding an experiment-specific code path**

Append the measured acceptance results to the existing JoelBrain experiment note and commit/push that vault change. If the SLA fails, record the stage timing that exceeded its deadline and open a generic package/plugin work item; do not patch the project itself.
