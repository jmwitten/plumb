# Generic Build Certification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Certify standalone construction builds through one generic engine and a declarative `<slug>.cert.yaml`, prove the architecture on the armchair caddy, and remove at least 80 percent of its bespoke gate tests without weakening accuracy coverage.

**Architecture:** A strict contract loader and standalone adapter produce immutable evidence for a slug-independent rule engine. A thin CLI and one automatically parametrized pytest module consume the same engine; the existing detail-gate collection hook selects the generic row plus a small justified bespoke geometry set.

**Tech Stack:** Python 3.12, dataclasses, `typing.Protocol`, PyYAML, pytest 9, pytest-xdist, existing CadQuery/compiler/validation/fabrication/design-review APIs.

## Global Constraints

- No certification-engine or generic-test code may contain `armchair_caddy` or caddy geometry knowledge.
- Previous-run geometry, validation, render, and certification results are ineligible; preserve the existing fresh per-test cache fixture.
- Documentation and presentation are optional unless named in `deliverables`.
- Recorded decisions may classify applicability or permit an honest unknown; they may not suppress contradictory evidence or an observed failure.
- Contract YAML is closed-schema data. Unknown keys, arbitrary Python, and general expression evaluation fail closed.
- The first adapter supports standalone `*.spec.yaml`; later site and cabinet support must require only new adapters.
- A temporary unrelated spec and contract must certify through discovery without a registry edit or a new Python test.
- At least 45 of the current 53 caddy gate nodes must cease to require bespoke caddy Python tests.
- The slower of two clean-process caddy gate runs must remain below 645.17 seconds.
- Shared certification code changes require the full `pytest -q -n 4` regression before completion.

---

## File map

- `src/certification/model.py` — result states, immutable evidence, findings, decisions, and result formatting.
- `src/certification/contract.py` — strict YAML schema, path safety, typed intent selectors, and discovery.
- `src/certification/adapters.py` — adapter protocol and standalone-spec production adapter.
- `src/certification/rules.py` — stable generic rule catalog and typed selector evaluation.
- `src/certification/engine.py` — adapter dispatch, evidence collection, rule execution, and public API.
- `src/certification/__init__.py` — supported public imports.
- `src/certification/__main__.py` — human/JSON CLI and stable exit codes.
- `pyproject.toml` — ship `detailgen.certification`.
- `tests/test_certification_contract.py` — schema/discovery/path tests without CadQuery.
- `tests/test_certification_engine.py` — fake-evidence rule, severity, decision, and generality tests.
- `tests/test_certification_standalone.py` — real standalone adapter and mutation integration tests.
- `tests/test_certified_builds.py` — one automatically discovered generic pytest node per contract.
- `tests/conftest.py` — gate contracts updated for generic accuracy certification.
- `details/armchair_caddy.cert.yaml` — caddy intent and approved unknowns.
- `tests/test_caddy_reinforced_miter.py` — retained physical invariants only.
- `tests/test_install_sweep.py` — remove caddy cases and the unrelated-corpus cost from the caddy gate.
- `tests/test_armchair_caddy_e2e.py` — delete after equivalence proof.
- `tests/test_caddy_design_review.py` — delete after governance rule/mutation proof.
- `tests/test_caddy_instruction_manual.py` — delete because documentation is not a caddy certification deliverable.
- `.superpowers/sdd/caddy-generic-certification-equivalence.md` — disposition of all 53 old nodes.
- `.superpowers/sdd/caddy-test-performance-report.md` — final counts, mutations, timing, and regression evidence.
- `README.md` — contract authoring and certification workflow.

---

### Task 1: Certification domain model and strict contract loader

**Files:**
- Create: `src/certification/__init__.py`
- Create: `src/certification/model.py`
- Create: `src/certification/contract.py`
- Modify: `pyproject.toml`
- Test: `tests/test_certification_contract.py`

**Interfaces:**
- Produces: `FindingState`, `CertificationFinding`, `DecisionRecord`, `IntentSelector`, `CountIntent`, `FabricationIntent`, `BomIntent`, `CertificationContract`, `CertificationResult`.
- Produces: `load_contract(path: Path, *, repo_root: Path) -> CertificationContract` and `discover_contracts(details_dir: Path, *, repo_root: Path) -> tuple[CertificationContract, ...]`.

- [ ] **Step 1: Write strict contract-loader tests**

```python
def test_loads_minimal_closed_contract(tmp_path):
    source = tmp_path / "toy.spec.yaml"
    source.write_text("name: toy\nunits: in\nparams: {}\ncomponents: []\n")
    contract_path = tmp_path / "toy.cert.yaml"
    contract_path.write_text(
        "schema_version: 1\n"
        "subject:\n  kind: standalone_detail\n  source: toy.spec.yaml\n"
        "intent: {}\ndeliverables: []\ndecisions: []\n"
    )
    contract = load_contract(contract_path, repo_root=tmp_path)
    assert contract.slug == "toy"
    assert contract.subject.source == source.resolve()


@pytest.mark.parametrize("unknown", ["mystery", "python", "expression"])
def test_unknown_top_level_key_fails_closed(tmp_path, unknown):
    path = _minimal_contract(tmp_path)
    raw = yaml.safe_load(path.read_text())
    raw[unknown] = "ignored if loader is lax"
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    with pytest.raises(ContractError, match=rf"{unknown}.*unknown"):
        load_contract(path, repo_root=tmp_path)


def test_source_cannot_escape_repository_root(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    path = _minimal_contract(repo, source="../outside.spec.yaml")
    with pytest.raises(ContractError, match="escapes repository root"):
        load_contract(path, repo_root=repo)


def test_discovery_rejects_duplicate_slug(tmp_path):
    _minimal_contract(tmp_path / "a", slug="toy")
    _minimal_contract(tmp_path / "b", slug="toy")
    with pytest.raises(ContractError, match="duplicate certification slug 'toy'"):
        discover_contracts(tmp_path, repo_root=tmp_path)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_certification_contract.py -q`

Expected: collection fails because `detailgen.certification` does not exist.

- [ ] **Step 3: Implement immutable model types**

```python
class FindingState(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    NEEDS_DECISION = "NEEDS_DECISION"


@dataclass(frozen=True)
class CertificationFinding:
    rule_id: str
    state: FindingState
    subject: str
    detail: str
    evidence_fingerprint: str = ""


@dataclass(frozen=True)
class CertificationResult:
    slug: str
    findings: tuple[CertificationFinding, ...]
    applied_decisions: tuple[DecisionRecord, ...] = ()

    @property
    def failed(self) -> bool:
        return any(row.state is FindingState.FAIL for row in self.findings)

    @property
    def needs_decision(self) -> bool:
        return any(
            row.state is FindingState.NEEDS_DECISION for row in self.findings
        )

    @property
    def releasable(self) -> bool:
        return not self.failed and not self.needs_decision
```

Define frozen subject, selector, count, fabrication, BOM, decision, and contract dataclasses beside these values. Keep selector fields closed to `component`, `material`, `role`, `name`, `name_contains`, and connection `kind`.

- [ ] **Step 4: Implement a strict YAML loader and discovery**

Use a `_require_keys(mapping, *, required, optional, path)` helper that raises `ContractError` for missing or unknown fields. Resolve the subject relative to the contract, call `Path.resolve()`, and require `source.is_relative_to(repo_root.resolve())`. Derive the slug by removing `.cert.yaml`, validate it against `^[a-z][a-z0-9_]*$`, and sort discovery by slug.

- [ ] **Step 5: Export the public model and ship the package**

Add `"detailgen.certification"` to `[tool.setuptools].packages` and export only the stable contract/result/loader interfaces from `src/certification/__init__.py`.

- [ ] **Step 6: Run contract tests and the existing default-collection audit**

Run:

```bash
.venv/bin/python -m pytest tests/test_certification_contract.py tests/test_scripts_spec_rewire.py -q
```

Expected: all tests pass; the repository audit recognizes the new test file.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/certification tests/test_certification_contract.py
git commit -m "feat: add strict build certification contracts"
```

---

### Task 2: Standalone adapter and typed evidence collection

**Files:**
- Create: `src/certification/adapters.py`
- Extend: `src/certification/model.py`
- Test: `tests/test_certification_standalone.py`

**Interfaces:**
- Consumes: `CertificationContract` from Task 1.
- Produces: `BuildAdapter` protocol, `StandaloneSpecAdapter`, `PartEvidence`, `ConnectionEvidence`, `FabricationEvidence`, `BomEvidence`, `GovernanceEvidence`, `EvidenceSnapshot`.
- Produces: `StandaloneSpecAdapter.collect(contract: CertificationContract) -> EvidenceSnapshot`.

- [ ] **Step 1: Write a real unrelated-fixture adapter test**

Create a minimal valid standalone fixture through the existing spec vocabulary in `tests/fixtures/certification/toy_panel.spec.yaml`. The test must compile it through `compile_spec_file`, not mock the compiler.

```python
def test_standalone_adapter_collects_authoritative_evidence(repo_root):
    contract = load_contract(
        repo_root / "tests/fixtures/certification/toy_panel.cert.yaml",
        repo_root=repo_root,
    )
    snapshot = StandaloneSpecAdapter().collect(contract)
    assert snapshot.slug == "toy_panel"
    assert snapshot.validation.ok
    assert [part.component for part in snapshot.parts] == ["HardwoodPanel"]
    assert snapshot.bom[0].source_ids == (snapshot.parts[0].id,)
```

- [ ] **Step 2: Write fabrication, governance, and compile-failure tests**

```python
def test_adapter_calls_authoritative_fabrication_verifier(monkeypatch, contract):
    calls = []
    monkeypatch.setattr(
        "detailgen.certification.adapters.verify_assembly_fabrication",
        lambda assembly: calls.append(assembly.name),
    )
    StandaloneSpecAdapter().collect(contract)
    assert calls == ["toy panel"]


def test_compile_exception_becomes_snapshot_failure(monkeypatch, contract):
    monkeypatch.setattr(
        "detailgen.certification.adapters.compile_spec_file",
        lambda path: (_ for _ in ()).throw(ValueError("bad spec")),
    )
    snapshot = StandaloneSpecAdapter().collect(contract)
    assert snapshot.compile_error == "ValueError: bad spec"
    assert snapshot.parts == ()
```

- [ ] **Step 3: Run adapter tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_certification_standalone.py -q`

Expected: import failures for the adapter/evidence types.

- [ ] **Step 4: Implement the adapter protocol and standalone collector**

```python
class BuildAdapter(Protocol):
    kind: str

    def collect(self, contract: CertificationContract) -> EvidenceSnapshot:
        ...


class StandaloneSpecAdapter:
    kind = "standalone_detail"

    def collect(self, contract):
        try:
            detail = compile_spec_file(contract.subject.source)
            report = detail.validate()
            verify_assembly_fabrication(detail.assembly)
        except Exception as exc:
            return EvidenceSnapshot.compile_failure(
                contract.slug, contract.subject, exc
            )
        return EvidenceSnapshot(
            slug=contract.slug,
            subject=contract.subject,
            validation=_validation_evidence(report),
            parts=tuple(_part_evidence(part) for part in detail.assembly.parts),
            connections=tuple(_edge_evidence(e) for e in detail.connection_edges),
            fabrication=tuple(_fabrication_evidence(p) for p in detail.assembly.parts),
            bom=tuple(_bom_evidence(row) for row in detail.bom_table()),
            governance=_governance_evidence(detail),
            source_fingerprint=_sha256(contract.subject.source.read_bytes()),
            compile_error="",
        )
```

Catch compilation/build/validation exceptions into a compile-failure snapshot, but let collector-programming errors identify their stage in `collector_error`; rules will fail them loudly.

- [ ] **Step 5: Normalize evidence deterministically**

Sort parts by stable ID, connections by `(kind, a, b, connection)`, fabrication by part ID, findings by their original authoritative index plus stable fields, and BOM rows by `(item, dimensions, source_ids)`. Preserve numerical values as floats; formatting belongs only in renderers.

- [ ] **Step 6: Run adapter and focused existing lifecycle tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_certification_standalone.py tests/test_armchair_caddy_e2e.py::test_fabrication_fold_invariant_holds tests/test_caddy_design_review.py::test_caddy_spec_opts_in_and_delivery_is_confirmed -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/certification tests/fixtures/certification tests/test_certification_standalone.py
git commit -m "feat: collect standalone certification evidence"
```

---

### Task 3: Generic rules, contract intent, decisions, and engine

**Files:**
- Create: `src/certification/rules.py`
- Create: `src/certification/engine.py`
- Extend: `src/certification/model.py`
- Test: `tests/test_certification_engine.py`

**Interfaces:**
- Consumes: `EvidenceSnapshot`, `CertificationContract`, `BuildAdapter`.
- Produces: `CertificationContext(primary, repeat, contract)`,
  `CertificationRule`, `DEFAULT_RULES`, `evaluate_selector`, and
  `certify_contract(contract, *, adapters=None, rules=DEFAULT_RULES) -> CertificationResult`.

- [ ] **Step 1: Write fake-snapshot rule tests**

```python
def test_clean_snapshot_passes_every_mandatory_rule(clean_snapshot, contract):
    result = certify_contract(
        contract,
        adapters={"standalone_detail": FakeAdapter(clean_snapshot)},
    )
    assert result.releasable
    assert {f.rule_id for f in result.findings} >= {
        "compile.success", "validation.clean", "geometry.parts_valid",
        "connections.resolved", "fabrication.fold", "bom.source_ids",
        "governance.ready", "intent.matches",
    }


def test_validation_failure_cannot_be_suppressed_by_decision(
    dirty_snapshot, contract_with_matching_decision
):
    result = certify_contract(
        contract_with_matching_decision,
        adapters={"standalone_detail": FakeAdapter(dirty_snapshot)},
    )
    finding = next(f for f in result.findings if f.rule_id == "validation.clean")
    assert finding.state is FindingState.FAIL
    assert result.failed


def test_unknown_critical_claim_requires_decision(unknown_snapshot, contract):
    result = certify_contract(
        contract,
        adapters={"standalone_detail": FakeAdapter(unknown_snapshot)},
    )
    assert any(f.state is FindingState.NEEDS_DECISION for f in result.findings)
```

- [ ] **Step 2: Write typed selector and intent tests**

```python
def test_count_intent_matches_component_selector(clean_snapshot):
    intent = CountIntent(
        selector=IntentSelector(component="HardwoodPanel"), exactly=3
    )
    assert count_matches(clean_snapshot.parts, intent).passed


def test_bom_source_ids_must_partition_billable_parts(
    snapshot_with_duplicate_id, contract
):
    context = CertificationContext(
        snapshot_with_duplicate_id, snapshot_with_duplicate_id, contract
    )
    finding = BomSourceIdsRule().evaluate(context)
    assert finding.state is FindingState.FAIL
    assert "appears in more than one BOM row" in finding.detail


def test_optional_documents_are_not_in_default_rule_catalog():
    assert not any(rule.id.startswith("documents.") for rule in DEFAULT_RULES)
```

- [ ] **Step 3: Run engine tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_certification_engine.py -q`

Expected: imports fail for rules and engine.

- [ ] **Step 4: Implement stable rules and selector evaluation**

Implement one focused class/function per rule. Each rule evaluates a
`CertificationContext`; ordinary rules read `context.primary`, while the
determinism rule compares canonical normalized payloads from `primary` and
`repeat`. Selectors use exact normalized fields except `name_contains`, which
performs literal case-insensitive substring matching. Empty selectors and
selectors matching zero rows fail intent evaluation loudly.

```python
DEFAULT_RULES = (
    CompileSuccessRule(),
    ValidationCleanRule(),
    GeometryPartsValidRule(),
    ConnectionReferencesRule(),
    FabricationFoldRule(),
    BomSourceIdsRule(),
    GovernanceReadyRule(),
    IntentRule(),
    DeterministicEvidenceRule(),
)
```

Geometry validity uses authoritative solid counts, positive volume, finite
bounds, and the existing validation findings; it does not implement new
collision math. Governance is `PASS` for an ungoverned subject and requires
both modeling and delivery readiness when governance exists.

- [ ] **Step 5: Implement decisions and dependency fingerprints**

Only findings in `NEEDS_DECISION` are eligible. Hash canonical JSON containing the rule ID and that finding's normalized evidence payload. Apply a decision only when rule ID and fingerprint match. Keep the finding's unknown wording and include the decision in `applied_decisions`; use `WARN`, never `PASS`, for an allowed unknown.

- [ ] **Step 6: Implement adapter dispatch and exception policy**

```python
DEFAULT_ADAPTERS = {"standalone_detail": StandaloneSpecAdapter()}


def certify_contract(contract, *, adapters=None, rules=DEFAULT_RULES):
    registry = DEFAULT_ADAPTERS if adapters is None else adapters
    try:
        adapter = registry[contract.subject.kind]
    except KeyError:
        raise CertificationUsageError(
            f"unsupported certification adapter {contract.subject.kind!r}"
        ) from None
    primary = adapter.collect(contract)
    repeat = adapter.collect(contract)
    context = CertificationContext(primary, repeat, contract)
    findings = tuple(rule.evaluate(context) for rule in rules)
    return apply_decisions(contract, CertificationResult(contract.slug, findings))
```

Both collections use the same contract but fresh detail instances. They may
share only the current test's isolated production cache; no saved baseline or
prior-process certification result participates. A repeat compile failure or
normalized evidence mismatch fails `determinism.evidence`.

- [ ] **Step 7: Run engine/contract/adapter tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_certification_contract.py tests/test_certification_engine.py tests/test_certification_standalone.py -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/certification tests/test_certification_engine.py
git commit -m "feat: certify builds with generic accuracy rules"
```

---

### Task 4: CLI, automatic pytest discovery, and generic detail gates

**Files:**
- Create: `src/certification/__main__.py`
- Create: `tests/test_certification_cli.py`
- Create: `tests/test_certified_builds.py`
- Modify: `tests/conftest.py`
- Modify: `pyproject.toml`
- Test: `tests/test_detail_gate_selection.py`

**Interfaces:**
- Produces: `main(argv: Sequence[str] | None = None) -> int`.
- Preserves: `pytest --detail-gate <slug>` and ordinary unfiltered pytest.

- [ ] **Step 1: Write CLI exit-code and JSON tests**

```python
@pytest.mark.parametrize(
    ("state", "exit_code"),
    [("pass", 0), ("warn", 0), ("fail", 1), ("decision", 2), ("usage", 4)],
)
def test_cli_exit_codes(monkeypatch, capsys, state, exit_code):
    monkeypatch.setattr(cli, "_load_and_certify", lambda path: _result(state))
    assert cli.main(["details/toy.cert.yaml", "--json"]) == exit_code
    payload = json.loads(capsys.readouterr().out)
    assert payload["slug"] == "toy"
```

- [ ] **Step 2: Write automatic contract discovery test**

```python
def test_unrelated_contract_becomes_a_pytest_parameter_without_registry_edit(
    tmp_path,
):
    details = tmp_path / "details"
    details.mkdir()
    _write_toy_spec_and_contract(details, slug="garden_shelf")
    params = certification_params(details, repo_root=tmp_path)
    assert [param.id for param in params] == ["garden_shelf"]
    marks = [mark for mark in params[0].marks if mark.name == "detail_gate"]
    assert marks[0].args == ("garden_shelf",)
```

- [ ] **Step 3: Run CLI/discovery tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_certification_cli.py tests/test_certified_builds.py tests/test_detail_gate_selection.py -q
```

Expected: missing CLI and discovery helpers.

- [ ] **Step 4: Implement deterministic CLI renderers**

Human output lists `[STATE] rule_id: subject — detail` in rule order, followed by applied decisions. JSON uses sorted keys and arrays in rule order. `main()` catches `ContractError` and `CertificationUsageError`, writes `ERROR: ...` to stderr, and returns four.

- [ ] **Step 5: Generate generic pytest parameters**

```python
CORE_CONTRACTS = (
    "compile", "geometry", "validation", "connections",
    "fabrication", "bom", "governance", "intent", "determinism",
)


def certification_params(details_dir=DETAILS, repo_root=ROOT):
    return [
        pytest.param(
            contract.source_path,
            id=contract.slug,
            marks=pytest.mark.detail_gate(
                contract.slug, contracts=CORE_CONTRACTS
            ),
        )
        for contract in discover_contracts(details_dir, repo_root=repo_root)
    ]


@pytest.mark.parametrize("contract_path", certification_params())
def test_certified_build(contract_path):
    contract = load_contract(contract_path, repo_root=ROOT)
    result = certify_contract(contract)
    assert result.releasable, result.format_text()
```

- [ ] **Step 6: Update gate completeness vocabulary**

Replace `documents` with `connections`, `bom`, and `intent` in `REQUIRED_DETAIL_CONTRACTS`. Keep strict malformed-marker validation. Update its unit tests to use the new frozenset instead of hard-coded old values.

- [ ] **Step 7: Run default and filtered collection tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_certification_cli.py tests/test_certified_builds.py tests/test_detail_gate_selection.py -q
.venv/bin/python -m pytest --collect-only -q > /tmp/certification-collection.txt
```

Expected: focused tests pass; default collection includes every preexisting node until the deliberate migration task.

- [ ] **Step 8: Commit**

```bash
git add src/certification/__main__.py tests/test_certification_cli.py tests/test_certified_builds.py tests/conftest.py tests/test_detail_gate_selection.py pyproject.toml
git commit -m "feat: discover generic certification gates"
```

---

### Task 5: Caddy contract, accuracy mutations, and equivalence map

**Files:**
- Create: `details/armchair_caddy.cert.yaml`
- Extend: `tests/test_certification_standalone.py`
- Create: `.superpowers/sdd/caddy-generic-certification-equivalence.md`

**Interfaces:**
- Consumes: generic engine and discovery from Tasks 1–4.
- Produces: caddy contract and auditable disposition for all 53 old nodes.

- [ ] **Step 1: Author the caddy contract from approved design intent**

Declare three `HardwoodPanel` parts, four `WoodDowel` parts, no names containing `screw` or `bracket`, two `bonded_to` and two `keyed_by` edges, top/side fabrication sequences, BOM quantities/length ranges, clean validation, governed selected concept `reinforced_miter`, and delivery readiness. Leave `deliverables: []`.

- [ ] **Step 2: Run the generic caddy node and verify its first failure**

Run: `.venv/bin/python -m pytest tests/test_certified_builds.py -k armchair_caddy -q`

Expected: fail on any contract/evidence mismatch. Correct the schema or collector only when the observed production evidence proves the generic representation wrong; correct the contract when the declared intent was encoded incorrectly.

- [ ] **Step 3: Add generic mutation tests**

Cover these independent failure classes with the unrelated toy subject or fake
evidence. None of these tests may name the caddy:

```python
@pytest.mark.parametrize(
    ("mutation", "rule_id"),
    [
        ("malformed_spec", "compile.success"),
        ("validation_failure", "validation.clean"),
        ("fabrication_drift", "fabrication.fold"),
        ("duplicate_bom_source_id", "bom.source_ids"),
        ("wrong_component_count_intent", "intent.matches"),
        ("stale_governance", "governance.ready"),
    ],
)
def test_mutations_fail_named_generic_rule(
    toy_contract, mutation, rule_id
):
    result = certify_contract(
        toy_contract,
        adapters={"standalone_detail": FakeAdapter(_mutated_evidence(mutation))},
    )
    assert any(
        row.rule_id == rule_id and row.state is FindingState.FAIL
        for row in result.findings
    )
```

The two caddy-specific physical mutations—extra keyed-miter hardware and
oversized corner keys—remain as justified bespoke tests in the reinforced-miter
module because they probe actual product geometry and joint semantics.

- [ ] **Step 4: Write all 53 equivalence rows before deleting tests**

Generate the old node list with:

```bash
.venv/bin/python -m pytest --detail-gate armchair_caddy --collect-only -q \
  | rg '^tests/' > /tmp/caddy-old-nodes.txt
```

For each node, record one named disposition. Retain exactly the six
reinforced-miter geometry tests plus the two physical negative probes for extra
hardware and oversized keys. The map must contain exactly 53 old node IDs and
no generic prose such as "covered by certification."

- [ ] **Step 5: Verify old and generic gates together**

Run:

```bash
.venv/bin/python -m pytest --detail-gate armchair_caddy -q -n 4
.venv/bin/python -m pytest tests/test_certification_standalone.py -q
```

Expected: old marked tests plus the generic caddy node pass; all mutation cases pass.

- [ ] **Step 6: Commit**

```bash
git add details/armchair_caddy.cert.yaml tests/test_certification_standalone.py .superpowers/sdd/caddy-generic-certification-equivalence.md
git commit -m "test: certify the caddy through generic rules"
```

---

### Task 6: Remove redundant caddy suites and retain only physical invariants

**Files:**
- Delete: `tests/test_armchair_caddy_e2e.py`
- Delete: `tests/test_caddy_design_review.py`
- Delete: `tests/test_caddy_instruction_manual.py`
- Modify: `tests/test_install_sweep.py`
- Modify: `tests/test_caddy_reinforced_miter.py`
- Modify: `.superpowers/sdd/caddy-generic-certification-equivalence.md`

**Interfaces:**
- Preserves: one generic certification node plus exactly eight justified bespoke caddy nodes.
- Removes: whole-corpus `swept` fixture from caddy gate execution.

- [ ] **Step 1: Confirm the equivalence map is structurally complete**

Add a lightweight audit test that parses the Markdown table and asserts the baseline node set equals the 53 recorded IDs, every disposition names a rule/contract/retained node, and at least 43 rows are not retained bespoke tests.

- [ ] **Step 2: Delete the three redundant dedicated suites**

Delete the E2E, design-review, and instruction-manual files only after Task 5's combined gate is green. Their generic accuracy coverage stays in the certification node; document output behavior remains owned by shared renderer/manual framework tests.

- [ ] **Step 3: Remove five caddy cases from the mixed install sweep**

Delete the caddy section from `tests/test_install_sweep.py`. Move the extra
hardware and oversized-key mutations into `tests/test_caddy_reinforced_miter.py`
with direct caddy-only helpers; never retain the whole-corpus `swept`
dependency.

- [ ] **Step 4: Keep and justify the physical-invariant module**

Keep its module marker for `armchair_caddy` with `contracts=("geometry",)`. The six current tests remain because closed 45-degree miter fit, diagonal dowel axes/stations, and cup-bore placement are richer geometric claims than v1 generic selectors. Add a module docstring naming that boundary.

- [ ] **Step 5: Run the reduced gate and audit**

Run:

```bash
.venv/bin/python -m pytest --detail-gate armchair_caddy --collect-only -q
.venv/bin/python -m pytest --detail-gate armchair_caddy -q -n 4
.venv/bin/python -m pytest tests/test_certification_standalone.py tests/test_caddy_reinforced_miter.py -q
```

Expected: one generic certification node plus exactly eight bespoke physical
nodes; all pass; no unrelated standalone build compiles.

- [ ] **Step 6: Commit**

```bash
git add -A tests .superpowers/sdd/caddy-generic-certification-equivalence.md
git commit -m "test: replace bespoke caddy suites with certification"
```

---

### Task 7: Generality proof, documentation, and clean-process benchmarks

**Files:**
- Extend: `tests/test_certification_engine.py`
- Modify: `README.md`
- Modify: `.superpowers/sdd/caddy-test-performance-report.md`
- Modify: `.superpowers/sdd/progress.md`

**Interfaces:**
- Proves: unrelated future builds need only source + contract.
- Documents: authoring, decisions, optional deliverables, and full-suite policy.

- [ ] **Step 1: Add the release-blocking unrelated-build proof**

Create `garden_shelf.spec.yaml` and `garden_shelf.cert.yaml` only inside
`tmp_path`, call `discover_contracts`, load the discovered contract, and certify
it through `StandaloneSpecAdapter`. Assert no production registry mutation and
no product-specific test callback.

- [ ] **Step 2: Add engine source audit**

```python
def test_generic_certification_source_contains_no_caddy_special_case(repo_root):
    text = "\n".join(
        path.read_text()
        for path in sorted((repo_root / "src/certification").glob("*.py"))
    )
    assert "armchair_caddy" not in text
    assert "corner key" not in text.lower()
```

- [ ] **Step 3: Document the future-build workflow**

README must show:

```bash
python -m detailgen.certification details/my_build.cert.yaml
pytest --detail-gate my_build -q -n 4
```

Explain that authors add a source and strict contract, generic checks are
automatic, high-severity uncertainty returns exit two for an agent/CLI decision,
documents are optional, and shared framework changes still require the full
suite.

- [ ] **Step 4: Benchmark twice with fresh processes**

Run twice:

```bash
/usr/bin/time -p .venv/bin/python -m pytest --detail-gate armchair_caddy -q -n 4
```

Record pytest and process wall time from both runs, use the slower result, and
verify each test receives a new temporary cache root.

- [ ] **Step 5: Record coverage and performance evidence**

Update the reports with old/new node counts, replacement percentage, retained
invariants, mutation matrix, unrelated-build proof, no-unrelated-compile proof,
and timing comparison against 1,290.34 and 645.17 seconds.

- [ ] **Step 6: Run focused verification**

Run:

```bash
.venv/bin/python -m pytest tests/test_certification_contract.py tests/test_certification_engine.py tests/test_certification_standalone.py tests/test_certification_cli.py tests/test_certified_builds.py tests/test_detail_gate_selection.py tests/test_caddy_reinforced_miter.py -q -n 4
git diff --check
```

Expected: all pass and no whitespace errors.

- [ ] **Step 7: Commit**

```bash
git add README.md tests/test_certification_engine.py .superpowers/sdd
git commit -m "docs: prove generic caddy certification"
```

---

### Task 8: Full regression, review, and delivery

**Files:**
- Modify only files required by verified review findings.

**Interfaces:**
- Produces: clean pushed branch with full evidence.

- [ ] **Step 1: Review the complete diff against the design**

Run:

```bash
git diff --check origin/codex/caddy-test-performance...HEAD
git diff --stat origin/codex/caddy-test-performance...HEAD
git diff origin/codex/caddy-test-performance...HEAD -- src/certification tests details/armchair_caddy.cert.yaml README.md .superpowers/sdd
```

Check contract strictness, slug independence, decision non-suppression, rule
exception behavior, deleted-test equivalence, and absence of unrelated fixture
compilation.

- [ ] **Step 2: Run the full repository regression**

Run:

```bash
/usr/bin/time -p .venv/bin/python -m pytest -q -n 4
```

Expected: all collected tests pass, with only the repository's documented skips
and xfail.

- [ ] **Step 3: Correct review or regression findings test-first**

For every issue, add or identify the failing focused test, reproduce the failure,
make the minimum correction, rerun the focused test, then rerun the affected
certification gate. Do not restore deleted bespoke tests as a shortcut.

- [ ] **Step 4: Record final regression evidence and commit**

Update `.superpowers/sdd/caddy-test-performance-report.md` with the exact full
count and wall time, then:

```bash
git add -A
git commit -m "docs: record generic certification regression"
```

- [ ] **Step 5: Verify branch integrity and push**

Run:

```bash
git status --short --branch
git diff --check origin/codex/caddy-test-performance...HEAD
git push
git rev-parse HEAD
git rev-parse @{upstream}
```

Expected: clean branch, successful push, identical local/upstream SHAs.
