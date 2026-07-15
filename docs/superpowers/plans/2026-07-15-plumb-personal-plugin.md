# Plumb Personal Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install a personal Codex plugin that routes new physical designs, concept selection, existing-package review, and automatic compiler extension through Joel Witten's local Plumb semantic construction compiler.

**Architecture:** A personal `plumb` plugin contains four focused skills and one shared, read-only environment preflight. `plumb-design` is the explicit orchestrator; it reads and applies the sibling concept, extension, and review skills in a required sequence, while durable Plumb records and git state carry handoffs between stages.

**Tech Stack:** Codex plugin manifest and personal marketplace, Agent Skills `SKILL.md` plus `agents/openai.yaml`, Python 3.12 standard library, existing Plumb Python/CadQuery toolchain, unittest, plugin/skill validation helpers, git.

## Global Constraints

- Personal plugin root: `/Users/joelwitten/plugins/plumb`.
- Personal marketplace: `/Users/joelwitten/.agents/plugins/marketplace.json`.
- Default Plumb repository: `/Users/joelwitten/Code/construction-detail-generator`.
- Default delivery vault: `/Users/joelwitten/Code/JoelBrain`.
- Environment overrides: `PLUMB_REPO` and `PLUMB_VAULT`.
- Version one includes no MCP server, connector, app, hook, or output asset bundle.
- Generated HTML is never an authoritative source and may not be used as a fallback for missing compiler functionality.
- Missing compiler vocabulary triggers `plumb-extend` automatically; unknowable external facts remain explicit holds.
- Every skill reads current Plumb repository guidance instead of embedding a duplicate compiler manual.
- Every skill must support explicit invocation and narrowly scoped implicit invocation.
- Every source change uses an isolated worktree, preserves unrelated changes, runs relevant tests, and records verification before delivery.

---

## File Map

### Personal plugin

- `/Users/joelwitten/plugins/plumb/.codex-plugin/plugin.json` — plugin identity and UI metadata.
- `/Users/joelwitten/plugins/plumb/scripts/plumb-preflight.py` — shared, non-mutating environment discovery.
- `/Users/joelwitten/plugins/plumb/tests/test_preflight.py` — preflight unit tests.
- `/Users/joelwitten/plugins/plumb/tests/test_skill_contracts.py` — static skill, trigger, and orchestration contract tests.
- `/Users/joelwitten/plugins/plumb/tests/prompt-evals.json` — realistic explicit and implicit invocation cases.
- `/Users/joelwitten/plugins/plumb/skills/plumb-concept/SKILL.md` — governed pre-model design selection.
- `/Users/joelwitten/plugins/plumb/skills/plumb-concept/agents/openai.yaml` — concept skill UI metadata.
- `/Users/joelwitten/plugins/plumb/skills/plumb-extend/SKILL.md` — reusable compiler-extension workflow.
- `/Users/joelwitten/plugins/plumb/skills/plumb-extend/agents/openai.yaml` — extension skill UI metadata.
- `/Users/joelwitten/plugins/plumb/skills/plumb-review/SKILL.md` — source-backed package review and regeneration.
- `/Users/joelwitten/plugins/plumb/skills/plumb-review/agents/openai.yaml` — review skill UI metadata.
- `/Users/joelwitten/plugins/plumb/skills/plumb-design/SKILL.md` — end-to-end orchestrator and handoff rules.
- `/Users/joelwitten/plugins/plumb/skills/plumb-design/agents/openai.yaml` — design skill UI metadata.

### Personal marketplace

- `/Users/joelwitten/.agents/plugins/marketplace.json` — personal marketplace entry generated through the plugin-creator helper.

### Plumb repository

- `docs/superpowers/specs/2026-07-15-plumb-personal-plugin-design.md` — mark implemented only after all plugin and fresh-task evaluations pass.

---

### Task 1: Scaffold the Plugin and Build the Shared Preflight

**Files:**
- Create: `/Users/joelwitten/plugins/plumb/.codex-plugin/plugin.json`
- Create: `/Users/joelwitten/plugins/plumb/scripts/plumb-preflight.py`
- Create: `/Users/joelwitten/plugins/plumb/tests/test_preflight.py`
- Create: `/Users/joelwitten/.agents/plugins/marketplace.json`

**Interfaces:**
- Consumes: optional `PLUMB_REPO` and `PLUMB_VAULT` environment variables.
- Produces: `inspect_environment(env: Mapping[str, str]) -> dict[str, object]` and a JSON CLI that exits `0` when required local inputs exist or `1` when a required input is absent.

- [ ] **Step 1: Scaffold the personal plugin and marketplace**

Run:

```bash
python3 /Users/joelwitten/.codex/skills/.system/plugin-creator/scripts/create_basic_plugin.py plumb --path /Users/joelwitten/plugins --with-skills --with-scripts --with-marketplace
```

Expected: `/Users/joelwitten/plugins/plumb/.codex-plugin/plugin.json` and the personal marketplace entry are created without scaffold markers.

- [ ] **Step 2: Initialize local version control for the personal plugin**

Run:

```bash
git -C /Users/joelwitten/plugins/plumb init
git -C /Users/joelwitten/plugins/plumb branch -M main
```

Expected: the plugin root is a local git repository on `main`.

- [ ] **Step 3: Replace the scaffold manifest with the intended plugin contract**

Set `.codex-plugin/plugin.json` to:

```json
{
  "name": "plumb",
  "version": "0.1.0",
  "description": "Personal Codex workflows for the Plumb semantic construction compiler.",
  "author": {
    "name": "Joel Witten"
  },
  "keywords": ["cad", "carpentry", "construction", "physical-design"],
  "skills": "./skills/",
  "interface": {
    "displayName": "Plumb",
    "shortDescription": "Design validated, contractor-facing projects",
    "longDescription": "Routes concept selection, compiler-backed modeling, automatic compiler extension, review, and delivery through Joel Witten's local Plumb construction compiler.",
    "developerName": "Joel Witten",
    "category": "Productivity",
    "capabilities": ["Interactive", "Write"],
    "defaultPrompt": [
      "Design a buildable project with my Plumb compiler.",
      "Compare precedent-backed concepts before modeling.",
      "Review and regenerate an existing Plumb package."
    ]
  }
}
```

- [ ] **Step 4: Write the failing preflight tests**

Create `tests/test_preflight.py`:

```python
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts" / "plumb-preflight.py"


def load_module():
    spec = importlib.util.spec_from_file_location("plumb_preflight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_layout(root: Path) -> tuple[Path, Path]:
    repo = root / "construction-detail-generator"
    vault = root / "JoelBrain"
    for path in (
        repo / "src",
        repo / "scripts",
        repo / "details",
        repo / ".venv" / "bin",
        vault / "05_Attachments" / "Organized",
    ):
        path.mkdir(parents=True, exist_ok=True)
    for path in (
        repo / "README.md",
        repo / "CLAUDE.md",
        repo / "pyproject.toml",
        repo / ".venv" / "bin" / "python",
    ):
        path.write_text("fixture", encoding="utf-8")
    return repo, vault


class PreflightTests(unittest.TestCase):
    def test_environment_overrides_produce_ready_result(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            repo, vault = make_layout(Path(tmp))
            result = module.inspect_environment(
                {"PLUMB_REPO": str(repo), "PLUMB_VAULT": str(vault)}
            )
        self.assertTrue(result["ready"])
        self.assertEqual(result["paths"]["plumb_repo"], str(repo.resolve()))
        self.assertEqual(result["paths"]["vault"], str(vault.resolve()))
        self.assertTrue(all(check["ok"] for check in result["required_checks"]))

    def test_missing_repository_fails_without_creating_files(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "missing"
            vault = root / "vault"
            vault.mkdir()
            result = module.inspect_environment(
                {"PLUMB_REPO": str(repo), "PLUMB_VAULT": str(vault)}
            )
            self.assertFalse(result["ready"])
            self.assertFalse(repo.exists())

    def test_cli_emits_json_and_nonzero_for_missing_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "PLUMB_REPO": str(Path(tmp) / "missing"),
                "PLUMB_VAULT": str(Path(tmp) / "missing-vault"),
            }
            completed = subprocess.run(
                [sys.executable, str(SCRIPT)],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertFalse(payload["ready"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 5: Run the tests and verify the expected failure**

Run:

```bash
python3 -m unittest /Users/joelwitten/plugins/plumb/tests/test_preflight.py -v
```

Expected: three errors because `scripts/plumb-preflight.py` does not exist.

- [ ] **Step 6: Implement the read-only preflight**

Create `scripts/plumb-preflight.py`:

```python
#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path


DEFAULT_REPO = Path("/Users/joelwitten/Code/construction-detail-generator")
DEFAULT_VAULT = Path("/Users/joelwitten/Code/JoelBrain")


def _check(check_id: str, path: Path, required: bool = True) -> dict[str, object]:
    return {
        "id": check_id,
        "path": str(path),
        "ok": path.exists(),
        "required": required,
    }


def _git(repo: Path, *args: str) -> str | None:
    if not (repo / ".git").exists():
        return None
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def inspect_environment(env: Mapping[str, str] | None = None) -> dict[str, object]:
    values = os.environ if env is None else env
    repo = Path(values.get("PLUMB_REPO", str(DEFAULT_REPO))).expanduser().resolve()
    vault = Path(values.get("PLUMB_VAULT", str(DEFAULT_VAULT))).expanduser().resolve()
    required = [
        _check("repo", repo),
        _check("readme", repo / "README.md"),
        _check("guidance", repo / "CLAUDE.md"),
        _check("package", repo / "pyproject.toml"),
        _check("source", repo / "src"),
        _check("scripts", repo / "scripts"),
        _check("details", repo / "details"),
        _check("python", repo / ".venv" / "bin" / "python"),
        _check("vault", vault),
        _check("vault-artifacts", vault / "05_Attachments" / "Organized"),
    ]
    optional = [
        {
            "id": "blender",
            "path": shutil.which("blender")
            or "/Applications/Blender.app/Contents/MacOS/Blender",
            "ok": bool(
                shutil.which("blender")
                or Path("/Applications/Blender.app/Contents/MacOS/Blender").exists()
            ),
            "required": False,
        }
    ]
    return {
        "schema": "plumb-preflight/v1",
        "ready": all(bool(check["ok"]) for check in required),
        "paths": {
            "plumb_repo": str(repo),
            "vault": str(vault),
            "python": str(repo / ".venv" / "bin" / "python"),
        },
        "git": {
            "branch": _git(repo, "branch", "--show-current"),
            "status": _git(repo, "status", "--short"),
            "worktrees": _git(repo, "worktree", "list", "--porcelain"),
        },
        "required_checks": required,
        "optional_checks": optional,
    }


def main() -> int:
    result = inspect_environment()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7: Run the preflight tests and real preflight**

Run:

```bash
python3 -m unittest /Users/joelwitten/plugins/plumb/tests/test_preflight.py -v
python3 /Users/joelwitten/plugins/plumb/scripts/plumb-preflight.py
```

Expected: three tests pass; the real command prints `"schema": "plumb-preflight/v1"` and `"ready": true`.

- [ ] **Step 8: Validate and commit the scaffold**

Run:

```bash
python3 /Users/joelwitten/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py /Users/joelwitten/plugins/plumb
git -C /Users/joelwitten/plugins/plumb add .codex-plugin/plugin.json scripts/plumb-preflight.py tests/test_preflight.py
git -C /Users/joelwitten/plugins/plumb commit -m "feat: scaffold personal Plumb plugin"
```

Expected: plugin validation passes and the first local plugin commit is created.

---

### Task 2: Implement the Governed Concept Skill

**Files:**
- Create: `/Users/joelwitten/plugins/plumb/tests/test_skill_contracts.py`
- Create: `/Users/joelwitten/plugins/plumb/skills/plumb-concept/SKILL.md`
- Create: `/Users/joelwitten/plugins/plumb/skills/plumb-concept/agents/openai.yaml`

**Interfaces:**
- Consumes: a physical-design brief and the live `detailgen.design_review` contract.
- Produces: a committed `detailgen/design-review/v1` sidecar, rendered report, selected concept id, and current `approved_for_modeling` fingerprint.

- [ ] **Step 1: Create the reusable skill contract test helper and failing concept assertions**

Create `tests/test_skill_contracts.py`:

```python
import re
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def skill_text(name: str) -> str:
    return (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def frontmatter_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"missing frontmatter key: {key}")
    return match.group(1).strip().strip('"')


def assert_tokens(test: unittest.TestCase, text: str, tokens: tuple[str, ...]) -> None:
    for token in tokens:
        test.assertIn(token, text)


class SkillContractTests(unittest.TestCase):
    def test_concept_contract(self):
        text = skill_text("plumb-concept")
        self.assertEqual(frontmatter_value(text, "name"), "plumb-concept")
        assert_tokens(
            self,
            text,
            (
                "../../scripts/plumb-preflight.py",
                "detailgen/design-review/v1",
                "approved_for_modeling",
                "three materially different concepts",
                "simplified visual",
                "selection fingerprint",
            ),
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the contract test and verify it fails**

Run:

```bash
python3 -m unittest /Users/joelwitten/plugins/plumb/tests/test_skill_contracts.py -v
```

Expected: `test_concept_contract` errors because the concept skill is absent.

- [ ] **Step 3: Initialize the concept skill**

Run:

```bash
python3 /Users/joelwitten/.codex/skills/.system/skill-creator/scripts/init_skill.py plumb-concept --path /Users/joelwitten/plugins/plumb/skills --interface display_name="Plumb Concept" --interface short_description="Compare and approve buildable concepts" --interface default_prompt="Use \$plumb-concept to compare precedent-backed concepts before modeling."
```

Expected: the skill directory and `agents/openai.yaml` are generated.

- [ ] **Step 4: Replace the generated concept instructions**

Write `skills/plumb-concept/SKILL.md` with this contract:

```markdown
---
name: plumb-concept
description: Research, compare, visualize, and approve precedent-backed physical-design concepts before production modeling in Joel Witten's Plumb construction compiler. Use when asked to explore build methods, compare concepts, show simplified design options, choose a physical architecture, use the contractor/design code for concept work, or create a modeling handoff.
---

# Plumb Concept

## Preflight

Run `python3 ../../scripts/plumb-preflight.py`. Stop without creating fallback
documents if required checks fail. Read the live Plumb `README.md`,
`CLAUDE.md`, `detailgen.design_review` implementation, and the closest
governed precedent before authoring a review.

## Workflow

1. Capture use, environment, users, builder skill, tools, loads, installation
   conditions, appearance, safety boundaries, required features, and ranked
   constraints.
2. Research at least one comparable commercial product and one real build
   instruction. Record claim-level observations, lessons, URLs, publishers,
   and access dates.
3. Author at least three materially different concepts. Every pair differs in
   at least two architecture-signature fields.
4. Show one comparable simplified visual per concept before production
   modeling. Include direct links to supporting precedents.
5. Complete every comparison criterion required by
   `detailgen/design-review/v1`; retain visible unknowns.
6. Derive unsupported novelty and require either a forcing brief requirement
   or an explicit exception with risk, alternatives, approver, and date.
7. Give every conceptual part family an indispensable purpose and answer
   whether joinery or an existing part can absorb it.
8. Recommend one concept from decisive comparison cells and record accepted
   tradeoffs.
9. Validate and render the design-review report with the live Plumb CLI.
10. Obtain covered owner approval and write the current selection fingerprint,
    transitioning the record to `approved_for_modeling`.

## Completion

Return the sidecar path, report path, selected concept id, selection fingerprint,
approval state, and unresolved holds. A direct concept request stops here. An
end-to-end Plumb design returns these artifacts to the calling orchestrator.

## Boundaries

- Do not begin promoted production modeling before current modeling approval.
- Do not infer capacity or safety from precedent popularity.
- Do not replace missing research with generic prose.
- Do not expose developer governance prose as customer instructions.
```

- [ ] **Step 5: Validate and test the concept skill**

Run:

```bash
python3 /Users/joelwitten/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/joelwitten/plugins/plumb/skills/plumb-concept
python3 -m unittest /Users/joelwitten/plugins/plumb/tests/test_skill_contracts.py -v
```

Expected: skill validation passes and `test_concept_contract` passes.

- [ ] **Step 6: Commit the concept skill**

Run:

```bash
git -C /Users/joelwitten/plugins/plumb add skills/plumb-concept tests/test_skill_contracts.py
git -C /Users/joelwitten/plugins/plumb commit -m "feat: add precedent-first concept skill"
```

---

### Task 3: Implement Automatic Compiler Extension

**Files:**
- Create: `/Users/joelwitten/plugins/plumb/skills/plumb-extend/SKILL.md`
- Create: `/Users/joelwitten/plugins/plumb/skills/plumb-extend/agents/openai.yaml`
- Modify: `/Users/joelwitten/plugins/plumb/tests/test_skill_contracts.py`

**Interfaces:**
- Consumes: a concrete blocked Plumb project step and the smallest reproducible missing capability.
- Produces: a reusable, tested compiler commit and a return handoff naming the exact workflow step to resume.

- [ ] **Step 1: Add the failing extension contract**

Add to `SkillContractTests`:

```python
    def test_extend_contract(self):
        text = skill_text("plumb-extend")
        self.assertEqual(frontmatter_value(text, "name"), "plumb-extend")
        assert_tokens(
            self,
            text,
            (
                "../../scripts/plumb-preflight.py",
                "smallest reproducible example",
                "failing test",
                "full Plumb suite",
                "return to the exact blocked step",
                "Do not invent external facts",
            ),
        )
```

- [ ] **Step 2: Run the contract test and verify it fails**

Run:

```bash
python3 -m unittest /Users/joelwitten/plugins/plumb/tests/test_skill_contracts.py -v
```

Expected: extension contract errors because the skill is absent.

- [ ] **Step 3: Initialize the extension skill**

Run:

```bash
python3 /Users/joelwitten/.codex/skills/.system/skill-creator/scripts/init_skill.py plumb-extend --path /Users/joelwitten/plugins/plumb/skills --interface display_name="Plumb Extend" --interface short_description="Extend and verify the Plumb compiler" --interface default_prompt="Use \$plumb-extend to add a tested capability to the Plumb compiler."
```

- [ ] **Step 4: Write the extension workflow**

Write `skills/plumb-extend/SKILL.md`:

```markdown
---
name: plumb-extend
description: Extend Joel Witten's Plumb semantic construction compiler with tested reusable vocabulary. Use when a physical project needs a missing component, datum, placement primitive, connection, installation contract, DetailSpec construct, domain pack, validation or evidence rule, process-graph feature, renderer, interactive viewer behavior, or generated-document capability.
---

# Plumb Extend

## Preflight

Run `python3 ../../scripts/plumb-preflight.py`. Read the live Plumb
`README.md`, `CLAUDE.md`, roadmap state when relevant, closest implementation,
and its tests. Use an isolated Plumb worktree and preserve unrelated work.

## Workflow

1. Reproduce the blocked project behavior and reduce it to the smallest
   reproducible example.
2. Classify the owning layer: component, datum/placement, connection,
   installation, base schema/compiler, pack, validation/evidence, process
   graph, rendering/viewer, or document generation.
3. Decide whether the fact belongs in general compiler vocabulary, a versioned
   domain pack, or project-authored data. Keep project constants out of generic
   layers.
4. Write the smallest failing test through the intended public surface, plus an
   end-to-end regression for the requesting project when behavior crosses
   layers.
5. Run the focused test and record the expected failure.
6. Implement the narrowest reusable capability with deterministic geometry,
   explicit provenance, stable identity, honest unknowns, and backward
   compatibility.
7. Version a schema, pack, or archetype when its public contract changes.
8. Run focused tests, affected subsystem tests, the project end-to-end test,
   and the full Plumb suite.
9. Regenerate and visually compare affected artifacts; update frozen truth only
   for intentional semantic changes.
10. Commit the compiler change and return to the exact blocked step in the
    calling design or review workflow.

## Boundaries

- Do not invent external facts such as soil, substrate, field dimensions,
  utilities, manufacturer capacities, or code interpretations.
- Do not bypass a compiler gap with static HTML or prose-only claims.
- Do not merge or release when the full suite regresses.
- Preserve UNKNOWN rather than upgrading incomplete evidence to PASS.
```

- [ ] **Step 5: Validate, test, and commit**

Run:

```bash
python3 /Users/joelwitten/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/joelwitten/plugins/plumb/skills/plumb-extend
python3 -m unittest /Users/joelwitten/plugins/plumb/tests/test_skill_contracts.py -v
git -C /Users/joelwitten/plugins/plumb add skills/plumb-extend tests/test_skill_contracts.py
git -C /Users/joelwitten/plugins/plumb commit -m "feat: add automatic compiler extension skill"
```

Expected: both skill contracts pass and the extension skill is committed.

---

### Task 4: Implement Source-Backed Review and Regeneration

**Files:**
- Create: `/Users/joelwitten/plugins/plumb/skills/plumb-review/SKILL.md`
- Create: `/Users/joelwitten/plugins/plumb/skills/plumb-review/agents/openai.yaml`
- Modify: `/Users/joelwitten/plugins/plumb/tests/test_skill_contracts.py`

**Interfaces:**
- Consumes: an existing Plumb sidecar/spec/project/model/package or reported presentation/technical concern.
- Produces: classified findings traced to authoritative sources, source-level fixes, regenerated artifacts, fresh review evidence, and explicit remaining holds.

- [ ] **Step 1: Add the failing review contract**

Add:

```python
    def test_review_contract(self):
        text = skill_text("plumb-review")
        self.assertEqual(frontmatter_value(text, "name"), "plumb-review")
        assert_tokens(
            self,
            text,
            (
                "../../scripts/plumb-preflight.py",
                "Generated HTML is never the source of truth",
                "../plumb-extend/SKILL.md",
                "../plumb-concept/SKILL.md",
                "desktop, mobile, and print",
                "reference package",
                "review trace",
            ),
        )
```

- [ ] **Step 2: Run the suite and verify the review test fails**

Run:

```bash
python3 -m unittest /Users/joelwitten/plugins/plumb/tests/test_skill_contracts.py -v
```

Expected: the existing tests pass and the review contract errors.

- [ ] **Step 3: Initialize the review skill**

Run:

```bash
python3 /Users/joelwitten/.codex/skills/.system/skill-creator/scripts/init_skill.py plumb-review --path /Users/joelwitten/plugins/plumb/skills --interface display_name="Plumb Review" --interface short_description="Review and regenerate Plumb packages" --interface default_prompt="Use \$plumb-review to audit and regenerate this Plumb package."
```

- [ ] **Step 4: Write the review workflow**

Write `skills/plumb-review/SKILL.md`:

```markdown
---
name: plumb-review
description: Audit, diagnose, revise, regenerate, or release an existing project or model-backed package from Joel Witten's Plumb construction compiler. Use when a packet looks wrong, an exploded or installation view is missing, dimensions or instructions disagree, generated documents need review, or fabrication/install readiness must be assessed.
---

# Plumb Review

## Required sibling workflows

Read `../plumb-extend/SKILL.md` before fixing a compiler gap. Read
`../plumb-concept/SKILL.md` before reopening an approved architecture.

## Preflight and baseline

Run `python3 ../../scripts/plumb-preflight.py`. Identify the design-review
sidecar, spec/project/detail, compiler source, review stores, generated outputs,
and approval fingerprints. Use an isolated worktree and regenerate from source.
Generated HTML is never the source of truth.

## Review

1. Reproduce the concern from a fresh generation.
2. Check schema, compilation, geometry, interference allowances, bearings,
   bonds, through-holes, connectivity, connections, spatial invariants,
   represented load paths, evidence, coverage, BOM, cuts, machining, fasteners,
   installation contracts, and construction order.
3. Confirm production topology conforms to the approved concept. If a proposed
   correction changes architecture, execute the concept workflow before
   changing production geometry.
4. Check every reader step and instruction panel for arrivals, ordering, tools,
   hardware, cure/clamp dependencies, placement marks, stop gates, and
   acceptance checks.
5. Inspect hero, orthographic, dimensioned, exploded, and interactive views;
   explode and assembly controls; labels; hidden connections; fabrication
   drawings; and the installation/commissioning sheet.
6. Render every customer document at desktop, mobile, and print sizes.
7. Compare document surfaces, model payloads, controls, navigation, and
   structural file-size signals with the closest established reference package.
8. Classify findings as blocking geometry, lifecycle/concept mismatch,
   unresolved UNKNOWN, installation hold, document inconsistency, presentation
   defect, or advisory. Trace each to its authoritative source.

## Repair and release

1. Add a failing regression for the finding.
2. Fix the spec, project data, compiler, or renderer at the source.
3. Execute the extension workflow when compiler vocabulary is missing.
4. Regenerate and repeat focused checks, project end-to-end checks, the full
   Plumb suite, visual QA, and reference comparison.
5. Update the review trace and review stores, copy approved artifacts to
   JoelBrain, commit/push source changes, and report remaining holds.

Complete only when the concern is resolved or accurately retained as a hold
and all generated evidence is fresh.
```

- [ ] **Step 5: Validate, test, and commit**

Run:

```bash
python3 /Users/joelwitten/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/joelwitten/plugins/plumb/skills/plumb-review
python3 -m unittest /Users/joelwitten/plugins/plumb/tests/test_skill_contracts.py -v
git -C /Users/joelwitten/plugins/plumb add skills/plumb-review tests/test_skill_contracts.py
git -C /Users/joelwitten/plugins/plumb commit -m "feat: add source-backed Plumb review skill"
```

---

### Task 5: Implement the End-to-End Design Orchestrator

**Files:**
- Create: `/Users/joelwitten/plugins/plumb/skills/plumb-design/SKILL.md`
- Create: `/Users/joelwitten/plugins/plumb/skills/plumb-design/agents/openai.yaml`
- Modify: `/Users/joelwitten/plugins/plumb/tests/test_skill_contracts.py`

**Interfaces:**
- Consumes: a physical-design goal, current governed design state when present, and all three sibling skill contracts.
- Produces: an approved compiler-backed package in JoelBrain containing the established interactive, exploded, fabrication, assembly, installation, and review surfaces.

- [ ] **Step 1: Add failing orchestration assertions**

Add:

```python
    def test_design_orchestration_order(self):
        text = skill_text("plumb-design")
        self.assertEqual(frontmatter_value(text, "name"), "plumb-design")
        ordered = (
            "../plumb-concept/SKILL.md",
            "Model and validate",
            "../plumb-extend/SKILL.md",
            "Generate the complete package",
            "../plumb-review/SKILL.md",
            "Deliver to JoelBrain",
        )
        positions = [text.index(token) for token in ordered]
        self.assertEqual(positions, sorted(positions))
        assert_tokens(
            self,
            text,
            (
                "../../scripts/plumb-preflight.py",
                "no native skill-call runtime",
                "interactive GLB viewer",
                "installation and commissioning sheet",
                "Never substitute static HTML",
            ),
        )
```

- [ ] **Step 2: Run the suite and verify the orchestrator test fails**

Run:

```bash
python3 -m unittest /Users/joelwitten/plugins/plumb/tests/test_skill_contracts.py -v
```

Expected: concept, extension, and review contracts pass; design orchestration errors.

- [ ] **Step 3: Initialize the design skill**

Run:

```bash
python3 /Users/joelwitten/.codex/skills/.system/skill-creator/scripts/init_skill.py plumb-design --path /Users/joelwitten/plugins/plumb/skills --interface display_name="Plumb Design" --interface short_description="Design complete model-backed build packages" --interface default_prompt="Use \$plumb-design to design and deliver a complete model-backed project."
```

- [ ] **Step 4: Write the explicit orchestrator**

Write `skills/plumb-design/SKILL.md`:

```markdown
---
name: plumb-design
description: Design and deliver a complete real-world physical project through Joel Witten's Plumb semantic construction compiler. Use when asked to use Plumb, the contractor/design code, the construction-detail generator, model-backed drawings, or the full fabrication, assembly, installation, and review suite for furniture, carpentry, fixtures, outdoor projects, or related buildable objects.
---

# Plumb Design

## Orchestration contract

Codex has no native skill-call runtime. Execute this workflow explicitly by
reading each required sibling SKILL.md completely before its stage, adding that
stage to the active task plan, and using durable repository artifacts for the
handoff. Do not paraphrase a sibling workflow from memory.

## 1. Preflight

Run `python3 ../../scripts/plumb-preflight.py`. Read current Plumb
`README.md`, `CLAUDE.md`, relevant roadmap state, and the closest complete
precedent. Sync affected repositories and use isolated worktrees.

## 2. Concept

Read and execute `../plumb-concept/SKILL.md` unless the project already has a
current, valid `approved_for_modeling` record. Carry the selected concept id
and selection fingerprint forward.

## 3. Model and validate

Choose the narrowest authoring surface: an existing versioned pack,
declarative DetailSpec, or imperative Detail escape hatch. Implement through
tests. Compile and validate geometry, connections, construction completeness,
evidence, coverage, installation contracts, BOM, cut plan, and concept
conformance.

## 4. Extend when blocked

Read and execute `../plumb-extend/SKILL.md` whenever required compiler
vocabulary is absent. Return to the exact blocked model/validation step and
continue; do not create a local document-only workaround.

## 5. Generate the complete package

Generate the established contractor-facing surfaces from the model:

- interactive GLB viewer;
- real exploded view and explode control;
- assembly-state controls and instruction panels;
- dimensioned and fabrication views;
- fabrication packet and schedules;
- assembly manual;
- installation and commissioning sheet;
- review trace and explicit field holds.

## 6. Review

Read and execute `../plumb-review/SKILL.md` as the release gate. If review
invokes extension, regenerate and repeat review. If review finds architecture
drift, reopen concept selection before changing the model.

## 7. Deliver to JoelBrain

Bind delivery confirmation to the current concept and model fingerprints. Copy
approved artifacts into the appropriate JoelBrain attachment folder, update
the project note, commit/push intentionally modified repositories, and report
verification plus remaining holds.

## Non-negotiable boundaries

- Never substitute static HTML for the Plumb compiler.
- Never call an artifact Plumb-generated unless it came through the compiler.
- Never edit generated HTML as the authoritative repair.
- Never turn UNKNOWN into implied approval.
- Complete only when the full package is delivered or an exact blocking
  prerequisite prevents further safe progress.
```

- [ ] **Step 5: Validate, test, and commit**

Run:

```bash
python3 /Users/joelwitten/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/joelwitten/plugins/plumb/skills/plumb-design
python3 -m unittest /Users/joelwitten/plugins/plumb/tests/test_skill_contracts.py -v
git -C /Users/joelwitten/plugins/plumb add skills/plumb-design tests/test_skill_contracts.py
git -C /Users/joelwitten/plugins/plumb commit -m "feat: orchestrate complete Plumb designs"
```

Expected: all four skill contract tests pass.

---

### Task 6: Add Prompt Evaluations and Validate the Complete Plugin

**Files:**
- Create: `/Users/joelwitten/plugins/plumb/tests/prompt-evals.json`
- Modify: `/Users/joelwitten/plugins/plumb/tests/test_skill_contracts.py`

**Interfaces:**
- Consumes: installed plugin metadata and the four skill trigger descriptions.
- Produces: a deterministic evaluation inventory plus complete structural validation evidence.

- [ ] **Step 1: Add prompt evaluation fixtures**

Create `tests/prompt-evals.json`:

```json
[
  {
    "prompt": "Use my contractor/design code to design a freestanding birdhouse and run the full suite.",
    "expected_primary": "plumb-design",
    "expected_sequence": ["plumb-concept", "plumb-extend-if-needed", "plumb-review"]
  },
  {
    "prompt": "Use Plumb to compare three precedent-backed concepts before modeling.",
    "expected_primary": "plumb-concept",
    "expected_stop": "approved_for_modeling"
  },
  {
    "prompt": "Why is this Plumb packet missing its exploded view and installation sheet?",
    "expected_primary": "plumb-review",
    "expected_sequence": ["plumb-extend-if-needed", "regenerate", "review"]
  },
  {
    "prompt": "Add a reusable mitered-panel primitive to my construction compiler.",
    "expected_primary": "plumb-extend",
    "expected_stop": "tested compiler commit"
  },
  {
    "prompt": "Review this essay about household plumbing.",
    "expected_primary": null
  },
  {
    "prompt": "Create a landing page design for a contractor.",
    "expected_primary": null
  }
]
```

- [ ] **Step 2: Add a fixture integrity test**

Add imports `json` and then:

```python
    def test_prompt_eval_inventory(self):
        cases = json.loads((PLUGIN_ROOT / "tests" / "prompt-evals.json").read_text())
        self.assertEqual(len(cases), 6)
        positives = {case["expected_primary"] for case in cases if case["expected_primary"]}
        self.assertEqual(
            positives,
            {"plumb-design", "plumb-concept", "plumb-review", "plumb-extend"},
        )
        self.assertEqual(
            sum(case["expected_primary"] is None for case in cases),
            2,
        )
```

- [ ] **Step 3: Run all local plugin tests**

Run:

```bash
python3 -m unittest discover -s /Users/joelwitten/plugins/plumb/tests -p 'test_*.py' -v
```

Expected: preflight tests, four skill contracts, orchestration order, and evaluation inventory all pass.

- [ ] **Step 4: Validate all skills and the plugin**

Run:

```bash
for skill in plumb-concept plumb-extend plumb-review plumb-design; do
  python3 /Users/joelwitten/.codex/skills/.system/skill-creator/scripts/quick_validate.py   "/Users/joelwitten/plugins/plumb/skills/$skill"
done
python3 /Users/joelwitten/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py /Users/joelwitten/plugins/plumb
python3 /Users/joelwitten/plugins/plumb/scripts/plumb-preflight.py
```

Expected: four skill validations pass, plugin validation passes, and preflight reports ready.

- [ ] **Step 5: Verify marketplace policy and plugin source**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path

path = Path("/Users/joelwitten/.agents/plugins/marketplace.json")
data = json.loads(path.read_text(encoding="utf-8"))
entry = next(item for item in data["plugins"] if item["name"] == "plumb")
assert entry["source"] == {"source": "local", "path": "./plugins/plumb"}
assert entry["policy"] == {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL",
}
assert entry["category"] == "Productivity"
print(data["name"])
PY
```

Expected: the personal marketplace name is printed and all assertions pass.

- [ ] **Step 6: Commit the evaluation inventory**

Run:

```bash
git -C /Users/joelwitten/plugins/plumb add tests/prompt-evals.json tests/test_skill_contracts.py
git -C /Users/joelwitten/plugins/plumb commit -m "test: verify Plumb skill routing contracts"
```

---

### Task 7: Install and Forward-Test in Fresh Codex Tasks

**Files:**
- Modify: `/Users/joelwitten/plugins/plumb/.codex-plugin/plugin.json` only through the cachebuster helper if reinstalling after an initial failed evaluation.
- Modify: `docs/superpowers/specs/2026-07-15-plumb-personal-plugin-design.md` after successful evaluations.

**Interfaces:**
- Consumes: validated plugin source and personal marketplace entry.
- Produces: installed plugin visible to new Codex tasks and evidence that explicit orchestration works outside the authoring task.

- [ ] **Step 1: Read the personal marketplace name and install**

Run:

```bash
python3 /Users/joelwitten/.codex/skills/.system/plugin-creator/scripts/read_marketplace_name.py
codex plugin add plumb@personal
codex plugin list
```

Expected: `plumb` appears as an installed local plugin. If the printed marketplace name is not `personal`, substitute the printed name in the add command.

- [ ] **Step 2: Start a fresh Codex task in JoelBrain and test explicit orchestration**

Prompt:

```text
$plumb-design

Evaluation only: do not modify files. For a simple freestanding birdhouse,
show the exact Plumb stages and sibling skills you would execute in order,
the durable artifact handed off by each stage, and where automatic extension
returns control.
```

Expected:

- `plumb-concept` precedes production modeling.
- `plumb-extend` is conditional and returns to the blocked step.
- complete package generation precedes `plumb-review`.
- delivery to JoelBrain occurs only after review.
- the response states that skill chaining is explicit orchestration, not a native runtime call.

- [ ] **Step 3: Test independent skill completion in fresh tasks**

Run one fresh task per prompt:

```text
$plumb-concept

Evaluation only: do not modify files. Explain where this workflow stops and
name the durable handoff to a later Plumb design run.
```

Expected: stops at committed `approved_for_modeling` design-review state.

```text
$plumb-review

Evaluation only: do not modify files. Review the existing birdhouse packet's
format against DB40 and state which source system must be changed.
```

Expected: rejects static HTML as non-compiler-backed, traces the repair to Plumb source/model generation, and names extension if the compiler lacks birdhouse vocabulary.

```text
$plumb-extend

Evaluation only: do not modify files. Describe how you would add a reusable
mitered-panel primitive and where you would return after verification.
```

Expected: failing test first, correct architectural layer, full suite, then exact blocked-step return.

- [ ] **Step 4: Test implicit positive and negative routing**

In fresh tasks, use the six prompts from `tests/prompt-evals.json` without explicit skill tags. Confirm the four positive prompts select the expected primary skill and the two negative prompts do not select a Plumb skill.

Expected: all six outcomes match the fixture.

- [ ] **Step 5: Repair and reinstall only if an evaluation fails**

After changing plugin source, run:

```bash
python3 /Users/joelwitten/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py /Users/joelwitten/plugins/plumb
python3 /Users/joelwitten/.codex/skills/.system/plugin-creator/scripts/read_marketplace_name.py
codex plugin add plumb@personal
```

Expected: the helper replaces one cachebuster suffix and the updated plugin is installed. Repeat only the failed evaluation plus the full local validation suite.

- [ ] **Step 6: Mark the design specification implemented**

Change the specification status to:

```markdown
**Status:** implemented and forward-tested on 2026-07-15
```

Then run:

```bash
git -C /Users/joelwitten/Code/construction-detail-generator diff --check
git -C /Users/joelwitten/Code/construction-detail-generator add docs/superpowers/specs/2026-07-15-plumb-personal-plugin-design.md
git -C /Users/joelwitten/Code/construction-detail-generator commit -m "docs: record Plumb plugin implementation"
```

- [ ] **Step 7: Run final verification**

Run:

```bash
python3 -m unittest discover -s /Users/joelwitten/plugins/plumb/tests -p 'test_*.py' -v
for skill in plumb-concept plumb-extend plumb-review plumb-design; do
  python3 /Users/joelwitten/.codex/skills/.system/skill-creator/scripts/quick_validate.py   "/Users/joelwitten/plugins/plumb/skills/$skill"
done
python3 /Users/joelwitten/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py /Users/joelwitten/plugins/plumb
python3 /Users/joelwitten/plugins/plumb/scripts/plumb-preflight.py
git -C /Users/joelwitten/plugins/plumb status --short
git -C /Users/joelwitten/Code/construction-detail-generator status --short
```

Expected:

- all plugin unit and contract tests pass;
- all four skills and the plugin validate;
- real preflight is ready;
- the plugin git repository is clean;
- the Plumb repository contains only pre-existing unrelated untracked files;
- fresh-task evaluations match all positive and negative routing expectations.
