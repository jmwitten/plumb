# Blind Caddy Certification Challenge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a byte-identical, precommitted cleated-caddy alternative through the legacy 53-node and generic nine-node gates, then permanently record whether the generic gate retains every meaningful legacy rejection category.

**Architecture:** Freeze the alternative as a certification-only DetailSpec fixture before either oracle runs. A small Python harness creates two detached disposable worktrees, copies the identical fixture bytes over the shipped caddy spec, invokes each worktree's own code with the same focused pytest command, captures collection and run output in memory, and removes both worktrees. The comparison report maps empirical node outcomes to the already-committed equivalence vocabulary; any generic accuracy gap stops execution for a separately specified TDD correction.

**Tech Stack:** Python 3.12, pytest/pytest-xdist, DetailSpec YAML, git worktrees, Markdown.

## Global Constraints

- Keep `details/armchair_caddy.spec.yaml`, `details/armchair_caddy.cert.yaml`, and `details/armchair_caddy.design-review.yaml` unchanged in the source branch.
- Commit the alternative fixture before executing either oracle.
- Use the exact same fixture bytes in both disposable worktrees and record their SHA-256 digest.
- The alternative is one hardwood top with a centered 3-1/2-inch bore, two hardwood sides, two hidden hardwood cleats, eight ordinary structural screws, gravity bearing on the same modeled six-inch sofa arm, and no fastening to the furniture.
- Do not add malformed geometry, dangling references, impossible dimensions, test-named metadata, capacity claims, sliding-resistance claims, or hot-drink-stability claims.
- Use legacy oracle commit `5e1498e` and the committed generic branch `HEAD` at execution time.
- Invoke the gate in each worktree as `.venv/bin/python -m pytest --detail-gate armchair_caddy -q -n 4`, where the Python executable is the source worktree's resolved `.venv/bin/python` and `PYTHONPATH` points first to the disposable worktree's `src` directory.
- Do not persist certification result objects or generated outputs; only command text, hashes, node outcomes, category mapping, corrections, and the final conclusion belong in the committed Markdown report.
- Classify legacy failures only as meaningful accuracy, retained spatial invariant, shared framework duplicate, or approved policy.
- Do not edit the alternative after the first oracle run except for a representation-only change required to use vocabulary common to both commits; never change its architecture or the frozen predictions.
- If a meaningful legacy category is missed, stop the comparison task, use systematic debugging plus TDD to specify and implement the smallest slug-independent correction, then rerun both oracles and the ordinary approved caddy gate.

---

### Task 1: Freeze the all-hardwood cleated alternative

**Files:**
- Create: `tests/fixtures/certification/blind_cleated_caddy.spec.yaml`
- Test: YAML parse plus source-tree immutability/hash checks from the shell

**Interfaces:**
- Consumes: the frozen product brief and predictions in `docs/superpowers/specs/2026-07-15-blind-caddy-certification-challenge-design.md`; the proven hidden-cleat geometry at `git show 91120d1:details/armchair_caddy.spec.yaml`
- Produces: immutable fixture bytes at `tests/fixtures/certification/blind_cleated_caddy.spec.yaml` for Task 2

- [ ] **Step 1: Record the untouched shipped-spec hashes**

Run:

```bash
shasum -a 256 details/armchair_caddy.spec.yaml details/armchair_caddy.cert.yaml details/armchair_caddy.design-review.yaml
```

Expected: three SHA-256 lines to compare after the fixture commit; no files change.

- [ ] **Step 2: Create the frozen fixture**

Create `tests/fixtures/certification/blind_cleated_caddy.spec.yaml` with this complete content:

```yaml
# Blind certification fixture: plausible unapproved cleated caddy.
# This file is copied byte-for-byte over the shipped caddy spec only inside
# disposable oracle worktrees. It is not a discovered or shipped detail.

name: armchair caddy
type: armchair_caddy
units: in

params:
  arm_w: 6.0
  arm_l: 10.0
  arm_h: 8.0
  panel_thk: 0.75
  panel_width: 5.5
  side_drop: 7.0
  arm_gap: 0.25
  ease_r: 0.125
  cup_dia: 3.5
  cleat_thk: 0.75
  cleat_drop: 1.5
  cleat_len: 4.0
  screw_dia: 0.19
  screw_len_v: 2.0
  screw_len_h: 1.25
  screw_dy_v: 1.5
  screw_dy_h: 0.6

derived:
  clear: "= cleat_thk + arm_gap"
  inner_span: "= arm_w + 2*clear"
  side_inner_x: "= inner_span / 2"
  side_outer_x: "= side_inner_x + panel_thk"
  top_len: "= 2 * side_outer_x"
  side_bot_z: "= -side_drop"
  top_top_z: "$panel_thk"
  cleat_inner_x: "= side_inner_x - cleat_thk"
  cleat_mid_x: "= side_inner_x - cleat_thk/2"
  cleat_bot_z: "= -cleat_drop"
  sidescrew_z: "= -cleat_drop/2"

components:
  - id: arm
    type: boulder
    name: sofa arm
    reader_name: Sofa arm
    params: {width: "$arm_l", length: "$arm_w", depth: "$arm_h"}

  - id: top
    type: hardwood_panel
    name: top panel
    reader_name: Top panel
    params:
      length: "$top_len"
      width: "$panel_width"
      thickness: "$panel_thk"
      ease_radius: "$ease_r"
    place:
      raw:
        at: ["= -top_len/2", "= -panel_width/2", "0 in"]
    features:
      - bore: {dia: $cup_dia, id: cup_hole, name: "cup hole"}

  - id: side_pos
    type: hardwood_panel
    name: side panel +X
    reader_name: Side panel
    params:
      length: "$side_drop"
      width: "$panel_width"
      thickness: "$panel_thk"
      ease_radius: "$ease_r"
    place:
      raw:
        at: ["$side_inner_x", "= panel_width/2", "$side_bot_z"]
        rotate: [["Y", -90], ["Z", 180]]

  - id: side_neg
    type: hardwood_panel
    name: side panel -X
    reader_name: Side panel
    params:
      length: "$side_drop"
      width: "$panel_width"
      thickness: "$panel_thk"
      ease_radius: "$ease_r"
    place:
      raw:
        at: ["= -side_inner_x", "= -panel_width/2", "$side_bot_z"]
        rotate: [["Y", -90]]

  - id: cleat_pos
    type: hardwood_panel
    name: interior cleat +X
    reader_name: Interior cleat
    params: {length: "$cleat_len", width: "$cleat_thk", thickness: "$cleat_drop"}
    place:
      raw:
        at: ["$side_inner_x", "= -cleat_len/2", "$cleat_bot_z"]
        rotate: [["Z", 90]]

  - id: cleat_neg
    type: hardwood_panel
    name: interior cleat -X
    reader_name: Interior cleat
    params: {length: "$cleat_len", width: "$cleat_thk", thickness: "$cleat_drop"}
    place:
      raw:
        at: ["= -cleat_inner_x", "= -cleat_len/2", "$cleat_bot_z"]
        rotate: [["Z", 90]]

  - id: vscrew_p0
    type: structural_screw
    name: cleat-up screw +X front
    params: {diameter: "$screw_dia", length: "$screw_len_v"}
    place: {raw: {at: ["$cleat_mid_x", "= -screw_dy_v", "$cleat_bot_z"], rotate: [["Y", 180]]}}
  - id: vscrew_p1
    type: structural_screw
    name: cleat-up screw +X back
    params: {diameter: "$screw_dia", length: "$screw_len_v"}
    place: {raw: {at: ["$cleat_mid_x", "$screw_dy_v", "$cleat_bot_z"], rotate: [["Y", 180]]}}
  - id: vscrew_m0
    type: structural_screw
    name: cleat-up screw -X front
    params: {diameter: "$screw_dia", length: "$screw_len_v"}
    place: {raw: {at: ["= -cleat_mid_x", "= -screw_dy_v", "$cleat_bot_z"], rotate: [["Y", 180]]}}
  - id: vscrew_m1
    type: structural_screw
    name: cleat-up screw -X back
    params: {diameter: "$screw_dia", length: "$screw_len_v"}
    place: {raw: {at: ["= -cleat_mid_x", "$screw_dy_v", "$cleat_bot_z"], rotate: [["Y", 180]]}}
  - id: hscrew_p0
    type: structural_screw
    name: cleat-side screw +X front
    params: {diameter: "$screw_dia", length: "$screw_len_h"}
    place: {raw: {at: ["$cleat_inner_x", "= -screw_dy_h", "$sidescrew_z"], rotate: [["Y", -90]]}}
  - id: hscrew_p1
    type: structural_screw
    name: cleat-side screw +X back
    params: {diameter: "$screw_dia", length: "$screw_len_h"}
    place: {raw: {at: ["$cleat_inner_x", "$screw_dy_h", "$sidescrew_z"], rotate: [["Y", -90]]}}
  - id: hscrew_m0
    type: structural_screw
    name: cleat-side screw -X front
    params: {diameter: "$screw_dia", length: "$screw_len_h"}
    place: {raw: {at: ["= -cleat_inner_x", "= -screw_dy_h", "$sidescrew_z"], rotate: [["Y", 90]]}}
  - id: hscrew_m1
    type: structural_screw
    name: cleat-side screw -X back
    params: {diameter: "$screw_dia", length: "$screw_len_h"}
    place: {raw: {at: ["= -cleat_inner_x", "$screw_dy_h", "$sidescrew_z"], rotate: [["Y", 90]]}}

connections:
  - type: cleat_screwed
    label: "cleat +X -> top underside"
    params: {n_screws: 2}
    parts: [cleat_pos, top]
    hardware: [vscrew_p0, vscrew_p1]
    assumptions: ["Screws bite the hardwood top's face grain; withdrawal capacity is not analyzed."]
  - type: cleat_screwed
    label: "cleat +X -> side +X inner face"
    params: {n_screws: 2}
    parts: [cleat_pos, side_pos]
    hardware: [hscrew_p0, hscrew_p1]
    assumptions: ["Screws bite the hardwood side's face grain; withdrawal capacity is not analyzed."]
  - type: cleat_screwed
    label: "cleat -X -> top underside"
    params: {n_screws: 2}
    parts: [cleat_neg, top]
    hardware: [vscrew_m0, vscrew_m1]
    assumptions: ["Screws bite the hardwood top's face grain; withdrawal capacity is not analyzed."]
  - type: cleat_screwed
    label: "cleat -X -> side -X inner face"
    params: {n_screws: 2}
    parts: [cleat_neg, side_neg]
    hardware: [hscrew_m0, hscrew_m1]
    assumptions: ["Screws bite the hardwood side's face grain; withdrawal capacity is not analyzed."]

sequence:
  assembly:
    mode: bench_then_set
    why: >-
      Assemble the hardwood sleeve and hidden cleats on the bench, then lower
      the completed connection-free caddy over the sofa arm. Insertion travel,
      sliding resistance, capacity, and hot-drink stability are not analyzed.

roles:
  arm: {role: existing, grounded_by: site}

validation:
  bearings:
    - {a: top, b: arm, axis: Z, area: 2000}
    - {a: top, b: side_pos, axis: Z, area: 800}
    - {a: top, b: side_neg, axis: Z, area: 800}
  dimensions:
    - name: "top underside rests on the arm top"
      part: top
      measure: zmin
      expected: "0 in"
      tolerance: "0.02 in"
    - name: "top spans both side panels"
      part: top
      measure: xlen
      expected: "$top_len"
      tolerance: "0.02 in"
    - name: "positive side sets the clear opening"
      part: side_pos
      measure: xmin
      expected: "$side_inner_x"
      tolerance: "0.02 in"
    - name: "side retains the seven-inch drop"
      part: side_pos
      measure: zmin
      expected: "$side_bot_z"
      tolerance: "0.02 in"

export: {glb_tolerance: 0.1, glb_angular_tolerance: 0.15}
```

- [ ] **Step 3: Verify only syntax and frozen product topology before committing**

Run:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from hashlib import sha256
import yaml

path = Path("tests/fixtures/certification/blind_cleated_caddy.spec.yaml")
raw = path.read_bytes()
doc = yaml.safe_load(raw)
components = doc["components"]
assert sum(row["type"] == "hardwood_panel" for row in components) == 5
assert sum(row["type"] == "structural_screw" for row in components) == 8
assert sum(row["type"] == "boulder" for row in components) == 1
assert len(doc["connections"]) == 4
assert all(row["type"] == "cleat_screwed" for row in doc["connections"])
assert "design_review" not in doc
print(sha256(raw).hexdigest())
PY
```

Expected: one SHA-256 digest and no assertion failure. Do not compile the alternative and do not execute pytest in this task.

- [ ] **Step 4: Recheck shipped files and commit the frozen fixture**

Run the Step 1 hash command again and verify the three hashes are byte-identical to Step 1. Then run:

```bash
git add tests/fixtures/certification/blind_cleated_caddy.spec.yaml docs/superpowers/plans/2026-07-15-blind-caddy-certification-challenge.md
git commit -m "test: freeze blind cleated caddy challenge"
```

Expected: a commit containing the fixture and implementation plan, with no oracle execution in its history.

---

### Task 2: Add the disposable dual-oracle harness

**Files:**
- Create: `scripts/blind_caddy_certification.py`
- Create: `tests/test_blind_caddy_certification.py`

**Interfaces:**
- Consumes: the committed fixture from Task 1; repository root; legacy ref `5e1498e`; generic ref `HEAD`; source-worktree Python executable
- Produces: `OracleResult` records containing oracle name/ref/commit, fixture SHA-256, collected node IDs, exact gate command, exit code, and combined terminal output; no result files

- [ ] **Step 1: Write the failing orchestration tests**

Create `tests/test_blind_caddy_certification.py` with these three named tests:

- `test_run_challenge_copies_identical_bytes_and_uses_each_worktree_source`: monkeypatch `_run` so each fake `git worktree add` creates the requested worktree's `details/` and `src/` directories; return fixed commit hashes from `rev-parse`, two fixed node IDs from collection, and nonzero expected-rejection results from the gates. Assert both copied specs equal `fixture.read_bytes()` and share its SHA-256; both gate commands equal `(python, "-m", "pytest", "--detail-gate", "armchair_caddy", "-q", "-n", "4")`; legacy uses `5e1498e`; generic uses `HEAD`; each pytest environment starts `PYTHONPATH` with that oracle's own `src`; and both `git worktree remove --force` calls occur.
- `test_run_challenge_removes_the_first_worktree_when_second_setup_fails`: make the fake generic `git worktree add` raise `subprocess.CalledProcessError`; assert the already-added legacy worktree is removed and the same infrastructure exception propagates.
- `test_cli_prints_hash_commands_nodes_and_output_without_writing_results`: replace `run_challenge` with two fixed `OracleResult` values, call `main` with `--repo-root` and `--python`, and assert stdout contains both refs/commits, the shared digest, collect commands/node IDs, gate commands, return codes, and captured output. Assert the temporary directory remains empty because the CLI has no result-output argument and writes no certification artifact.

Use `tmp_path`, `monkeypatch`, and `subprocess.CompletedProcess`. Import the module as `scripts.blind_caddy_certification`.

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_blind_caddy_certification.py -q
```

Expected: FAIL during collection because `scripts.blind_caddy_certification` does not exist.

- [ ] **Step 3: Implement the minimal harness**

Implement these exact public values and interfaces in `scripts/blind_caddy_certification.py` (the bodies implement the numbered behavior immediately below):

```python
LEGACY_REF = "5e1498e"
GENERIC_REF = "HEAD"
FIXTURE = Path("tests/fixtures/certification/blind_cleated_caddy.spec.yaml")
GATE_ARGS = ("-m", "pytest", "--detail-gate", "armchair_caddy", "-q", "-n", "4")
COLLECT_ARGS = ("-m", "pytest", "--detail-gate", "armchair_caddy", "--collect-only", "-q")

@dataclass(frozen=True)
class OracleResult:
    name: str
    ref: str
    commit: str
    fixture_sha256: str
    collect_command: tuple[str, ...]
    node_ids: tuple[str, ...]
    gate_command: tuple[str, ...]
    returncode: int
    output: str

def run_challenge(
    repo_root: Path,
    *,
    python: Path,
    fixture: Path | None = None,
    legacy_ref: str = LEGACY_REF,
    generic_ref: str = GENERIC_REF,
) -> tuple[OracleResult, OracleResult]:

def main(argv: Sequence[str] | None = None) -> int:
```

The implementation must:

1. resolve `repo_root`, `python`, and `fixture` before creating worktrees;
2. read the fixture once and compute `sha256(fixture_bytes).hexdigest()` once;
3. use `TemporaryDirectory(prefix="blind-caddy-certification-")`;
4. add detached worktrees sequentially with `git -C <repo_root> worktree add --detach <path> <ref>`;
5. copy the already-read bytes with `Path.write_bytes` to `<worktree>/details/armchair_caddy.spec.yaml`, then hash the destination and raise if it differs;
6. resolve each detached commit with `git -C <worktree> rev-parse HEAD`;
7. set `PYTHONDONTWRITEBYTECODE=1` and prepend `<worktree>/src` to `PYTHONPATH` for both pytest subprocesses;
8. collect selected node IDs with the exact collect tuple above and require collection return code zero;
9. identify node IDs as stripped collection-output lines containing `::` and beginning with `tests/`;
10. run the exact gate tuple above without `check=True`, because expected rejections return nonzero;
11. combine stdout and stderr in captured text without saving a report file;
12. remove every successfully added worktree in reverse order in `finally` with `git -C <repo_root> worktree remove --force <path>`; and
13. let infrastructure/setup/collection failures propagate after cleanup.

The CLI arguments are `--repo-root` (default: the script's parent repository), `--python` (default: `<repo-root>/.venv/bin/python`), `--legacy-ref`, and `--generic-ref`. Print both results in deterministic legacy-then-generic order, including every `OracleResult` field. Return zero when both oracle processes ran, regardless of their expected rejection return codes.

- [ ] **Step 4: Run focused tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_blind_caddy_certification.py -q
```

Expected: all harness tests pass without creating real worktrees or running either oracle.

- [ ] **Step 5: Commit the harness before the experiment**

Run:

```bash
git add scripts/blind_caddy_certification.py tests/test_blind_caddy_certification.py
git commit -m "test: add blind certification oracle harness"
```

Expected: the harness and unit tests are committed; the frozen fixture commit remains an ancestor and no oracle has run yet.

---

### Task 3: Execute, classify, and record the blind comparison

**Files:**
- Create: `.superpowers/sdd/blind-caddy-certification-comparison.md`
- Modify only if a discovered gap requires a separately specified TDD task: generic certification source and focused regression tests

**Interfaces:**
- Consumes: committed Task 1 fixture, committed Task 2 harness, legacy equivalence ledger `.superpowers/sdd/caddy-generic-certification-equivalence.md`, frozen predictions, both oracle outputs
- Produces: permanent comparison report and a final ordinary approved-caddy gate result

- [ ] **Step 1: Prove the experiment starts from committed bytes**

Run:

```bash
git status --short
git log --oneline -3
shasum -a 256 tests/fixtures/certification/blind_cleated_caddy.spec.yaml
```

Expected: clean status; separate fixture and harness commits visible; one fixture digest.

- [ ] **Step 2: Execute both isolated oracles once**

Run:

```bash
.venv/bin/python scripts/blind_caddy_certification.py
```

Expected: two disposable worktrees are created and removed; both results print the same fixture SHA-256; legacy reports all selected legacy node IDs and current reports the generic node plus eight retained physical probes. Nonzero gate return codes are expected rejection outcomes, not harness failure.

- [ ] **Step 3: Compare empirical results to the frozen predictions**

For each collected legacy node, record PASS/FAIL from the run output. Map every legacy failure to one or more of these exact categories:

```text
meaningful accuracy: compilation, geometry, validation, connections,
fabrication, BOM, governance, declared intent, determinism
retained spatial invariant: physical geometry beyond v1 normalized evidence
shared framework duplicate: independently preserved by a named shared test
approved policy: optional documentation/presentation behavior
```

For the generic oracle, expand the generic certification assertion text into the nine rule IDs (`compile.success`, `geometry.parts_valid`, `validation.clean`, `connections.resolved`, `fabrication.fold`, `bom.source_ids`, `governance.ready`, `intent.matches`, `determinism.evidence`) and record PASS/FAIL plus the eight physical-probe outcomes. Do not treat assertion-count parity as success; category coverage is the comparison unit.

- [ ] **Step 4: Stop for a new TDD correction task if the generic gate misses meaningful accuracy**

If any meaningful legacy rejection category has neither a failing generic rule nor a failing retained physical probe, do not finish this task. Report the exact legacy nodes, evidence, and missing category to the controller. The controller must invoke systematic debugging, write a concrete failing regression test, specify the smallest slug-independent correction as a new plan task, and rerun this task after that correction is committed.

If there is no missed meaningful category, continue without changing certification code.

- [ ] **Step 5: Write the permanent comparison report**

Create `.superpowers/sdd/blind-caddy-certification-comparison.md` with these populated sections and no unresolved placeholders:

```markdown
# Blind caddy certification comparison

## Frozen inputs
## Fixture and oracle identity
## Exact commands
## Frozen predictions versus observed passes
## Legacy node outcomes
## Generic rule and retained-probe outcomes
## Category equivalence mapping
## Approved policy-only differences
## Gaps and corrections
## Ordinary approved-caddy regression
## Conclusion
```

Include the fixture digest, legacy and generic commit hashes, exact commands, every node outcome, the category mapping, discrepancies from frozen pass predictions, any corrections, and an explicit success/regression conclusion. State that disposable worktrees and generated outputs were removed and that no certification result object was reused.

- [ ] **Step 6: Re-run the ordinary approved caddy gate**

Run:

```bash
.venv/bin/python -m pytest --detail-gate armchair_caddy -q -n 4
```

Expected: `9 passed`. Add the exact elapsed result to the report.

- [ ] **Step 7: Run focused permanent-evidence tests and commit**

Run:

```bash
.venv/bin/python -m pytest tests/test_blind_caddy_certification.py tests/test_certification_migrations.py -q
git status --short
```

Expected: all focused tests pass and only the comparison report plus any separately reviewed regression correction are uncommitted. Then run:

```bash
git add .superpowers/sdd/blind-caddy-certification-comparison.md
git commit -m "docs: record blind caddy certification comparison"
```

Expected: committed permanent evidence with the shipped caddy spec and contract still byte-identical to Task 1 Step 1.
