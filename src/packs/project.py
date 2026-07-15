"""Strict project loader and opt-in pack compilation entry point."""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import yaml

from .registry import PackRegistry, default_pack_registry

_META_KEYS = frozenset({"name", "units", "packs"})
_UNITS = frozenset({"mm", "in", "ft"})
_PACK_REF = re.compile(r"^(?P<id>[A-Za-z][A-Za-z0-9_.-]*)@(?P<major>0|[1-9][0-9]*)$")


class ProjectSchemaError(ValueError):
    """A packed project is structurally invalid or requests unknown vocabulary."""


def _json_native(value):
    """Return only JSON-native containers, preserving deterministic order."""

    if isinstance(value, dict):
        return {str(key): _json_native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_native(item) for item in value]
    return value


@dataclass(frozen=True)
class PackRef:
    pack_id: str
    major_version: int

    @property
    def key(self) -> str:
        return f"{self.pack_id}@{self.major_version}"


@dataclass(frozen=True)
class ProjectDoc:
    name: str
    units: str
    packs: tuple[PackRef, ...]
    sections: dict[str, dict] = field(default_factory=dict)


class ProjectReleaseError(RuntimeError):
    """A packed project cannot cross its fabrication/installation gate."""


@dataclass
class PackedProject:
    """A pack result wrapped around the unchanged compiled base detail."""

    project_doc: ProjectDoc
    model: object
    lowered_doc: object
    detail: object
    report: object
    artifacts: object
    pack_id: str
    pack_version: str
    expanded_project_doc: ProjectDoc | None = None
    required_base_coverage: tuple[str, ...] = ()
    _base_report: object = field(default=None, init=False, repr=False, compare=False)

    def build(self):
        return self.detail.build()

    def _typed_fabrication_contract(self):
        contract = getattr(self.model, "fabrication_release_contract", None)
        return contract() if callable(contract) else None

    def validate(self):
        typed_contract = self._typed_fabrication_contract()
        if typed_contract is not None:
            model_ready, contract_name = typed_contract
            audit_matches = getattr(
                self.model, "fabrication_audit_matches", None,
            )
            if (
                self.artifacts.fabrication_ready != model_ready
                or self.artifacts.release_contract != contract_name
                or (
                    callable(audit_matches)
                    and not audit_matches(self.artifacts.fabrication_audit)
                )
            ):
                raise ProjectSchemaError(
                    "typed fabrication model and artifact authority disagree"
                )
        self._base_report = self.detail.validate()
        # Domain packs can activate an existing base coverage family when they
        # have run a real, named check that the generic compiler cannot infer
        # from its vocabulary alone.  Capacity remains separate and UNKNOWN
        # unless a capacity checker actually runs.
        from ..validation.checks import Finding, UNKNOWN_VERDICT

        for finding in self.report.findings:
            check = getattr(finding, "base_check", "")
            if not check:
                continue
            verdict = UNKNOWN_VERDICT if finding.verdict == "UNKNOWN" else ""
            self._base_report.add(Finding(
                check=check,
                subject=finding.rule,
                passed=finding.verdict == "PASS",
                detail=finding.message,
                verdict=verdict,
            ))
        split_release = bool(
            typed_contract is not None
            or getattr(self.report, "installation_use_blocking_rules", ())
        )
        installation_use_ready = self.installation_use_ready
        fabrication_ready = self.fabrication_ready
        installation_steps = self.artifacts.installation_steps
        policy = getattr(self.report, "installation_use_policy", None)
        if policy is not None:
            installation_steps = tuple(
                replace(
                    step,
                    instruction=policy.release_gate_instruction(
                        released=installation_use_ready
                    ),
                ) if step.step_id == "install.release_gate" else step
                for step in installation_steps
            )
        self.artifacts = replace(
            self.artifacts,
            release_ready=installation_use_ready,
            fabrication_ready=fabrication_ready,
            installation_use_ready=installation_use_ready,
            release_scope=(
                "full" if split_release and installation_use_ready
                else "fabrication_only" if split_release and fabrication_ready
                else "none" if split_release
                else "unified"
            ),
            release_contract=(
                typed_contract[1] if typed_contract is not None
                else "split" if split_release else "unified"
            ),
            installation_steps=installation_steps,
        )
        return self._base_report

    def _required_coverage_ok(self) -> bool:
        if self._base_report is None:
            return False
        rows = {
            row.family: row.verdict for row in self._base_report.coverage_matrix()
        }
        return all(rows.get(family) == "PASS"
                   for family in self.required_base_coverage)

    @property
    def base_report(self):
        return self._base_report

    @property
    def fabrication_ready(self) -> bool:
        # Pack checks alone are not the release gate: until the unchanged base
        # geometry sweep has actually run, readiness is unknown and therefore
        # false. ``require_fabrication_release``/``validate`` supplies evidence.
        typed_contract = self._typed_fabrication_contract()
        report_ready = (
            typed_contract[0] if typed_contract is not None
            else getattr(self.report, "fabrication_ready", self.report.release_ready)
        )
        return bool(
            report_ready
            and self._base_report is not None
            and self._base_report.ok
            and self._required_coverage_ok()
        )

    @property
    def installation_use_ready(self) -> bool:
        return bool(
            self.fabrication_ready
            and getattr(
                self.report, "installation_use_ready", self.report.release_ready
            )
        )

    @property
    def release_ready(self) -> bool:
        """Conservative compatibility alias for installation/use readiness."""

        return self.installation_use_ready

    def require_fabrication_release(self):
        typed_contract = self._typed_fabrication_contract()
        report_ready = (
            typed_contract[0] if typed_contract is not None
            else getattr(
                self.report, "fabrication_ready", self.report.release_ready
            )
        )
        if not report_ready:
            lines = "\n".join(
                f"[{finding.verdict}] {finding.rule}: {finding.message}"
                for finding in self.report.blocking
            )
            raise ProjectReleaseError(
                f"{self.project_doc.name}: cabinet release blocked:\n{lines}"
            )
        base = self.validate()
        if not base.ok:
            lines = "\n".join(str(finding) for finding in base.blocking)
            raise ProjectReleaseError(
                f"{self.project_doc.name}: base-language validation blocked "
                f"release:\n{lines}"
            )
        if not self._required_coverage_ok():
            rows = {
                row.family: row.verdict for row in base.coverage_matrix()
            }
            missing = [
                f"{family}: {rows.get(family, 'missing')}"
                for family in self.required_base_coverage
                if rows.get(family) != "PASS"
            ]
            raise ProjectReleaseError(
                f"{self.project_doc.name}: required base coverage blocked "
                f"release:\n" + "\n".join(missing)
            )
        return self

    def require_release(self):
        self.require_fabrication_release()
        if not getattr(
            self.report, "installation_use_ready", self.report.release_ready
        ):
            blockers = getattr(self.report, "installation_use_blocking", ())
            lines = "\n".join(
                f"[{finding.verdict}] {finding.rule}: {finding.message}"
                for finding in blockers
            )
            raise ProjectReleaseError(
                f"{self.project_doc.name}: installation/use release blocked:\n"
                f"{lines}"
            )
        return self

    def bom_table(self):
        return self.detail.bom_table()

    def manifest(self) -> dict:
        model = self.model
        catalog_manifest = getattr(model, "catalog_manifest", None)
        catalogs = (
            catalog_manifest()
            if callable(catalog_manifest)
            else {
                "hinge": model.hinge.product_id,
                "wall_anchor": model.wall_anchor.product_id,
            }
        )
        expanded = self.expanded_project_doc or self.project_doc
        expanded_payload = {
            "name": expanded.name,
            "units": expanded.units,
            "packs": [ref.key for ref in expanded.packs],
            **expanded.sections,
        }
        payload = {
            "schema": "detailgen/packed-project/v1",
            "project": self.project_doc.name,
            "mode": model.mode,
            "packs": {self.pack_id: self.pack_version},
            "profile": model.profile.profile_id,
            "catalogs": catalogs,
            "release_ready": self.release_ready,
            "base_validation": (
                "not_run" if self._base_report is None
                else ("pass" if self._base_report.ok else "blocked")
            ),
            "base_coverage": (
                "not_run" if self._base_report is None
                else self._base_report.coverage_payload()
            ),
            "expanded_project": expanded_payload,
            "physical_tests": "not_performed",
            "archetypes": sorted({
                provenance.archetype_id
                for provenance in model.source_map.values()
                if getattr(provenance, "archetype_id", "")
            }),
            "components": [part.part_id for part in model.parts],
            "source_map": {
                part_id: asdict(provenance)
                for part_id, provenance in sorted(model.source_map.items())
            },
            "findings": [asdict(finding) for finding in self.report.findings],
            "evidence": [asdict(item) for item in self.report.evidence],
            "artifacts": self.artifacts.to_dict(),
        }
        if (
            self._typed_fabrication_contract() is not None
            or getattr(self.report, "installation_use_blocking_rules", ())
        ):
            typed_contract = self._typed_fabrication_contract()
            payload.update({
                "fabrication_ready": self.fabrication_ready,
                "installation_use_ready": self.installation_use_ready,
                "release_contract": (
                    typed_contract[1] if typed_contract is not None else "split"
                ),
                "release_scope": (
                    "full" if self.installation_use_ready else
                    "fabrication_only" if self.fabrication_ready else
                    "none"
                ),
            })
            policy = getattr(self.report, "installation_use_policy", None)
            if policy is not None:
                payload["installation_use_policy"] = asdict(policy)
        catalog_source_manifest = getattr(model, "catalog_source_manifest", None)
        catalog_sources = (
            catalog_source_manifest() if callable(catalog_source_manifest) else {}
        )
        if catalog_sources:
            payload["catalog_sources"] = catalog_sources
        sizing_policy_manifest = getattr(model, "sizing_policy_manifest", None)
        sizing_policies = (
            sizing_policy_manifest() if callable(sizing_policy_manifest) else ()
        )
        if sizing_policies:
            payload["sizing_policies"] = sorted(sizing_policies)
        derived_fact_manifest = getattr(model, "derived_fact_manifest", None)
        if callable(derived_fact_manifest):
            derived_facts = derived_fact_manifest()
            if derived_facts:
                payload["derived_facts"] = derived_facts
        catalog_asset_manifest = getattr(model, "catalog_asset_manifest", None)
        if callable(catalog_asset_manifest):
            catalog_assets = catalog_asset_manifest()
            if catalog_assets:
                payload["catalog_assets"] = catalog_assets
        return _json_native(payload)

    def manifest_json(self) -> str:
        return json.dumps(
            self.manifest(), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False,
        )

    def __getattr__(self, name: str):
        # Preserve the ordinary Detail surface (render, assembly, evidence graph,
        # etc.) without subclassing or changing the base compiler lifecycle.
        return getattr(self.detail, name)


def _parse_pack_ref(value, index: int) -> PackRef:
    if not isinstance(value, str):
        raise ProjectSchemaError(
            f"packs[{index}]: use '<pack-id>@<major-version>', got {value!r}"
        )
    match = _PACK_REF.fullmatch(value.strip())
    if match is None:
        raise ProjectSchemaError(
            f"packs[{index}]: use '<pack-id>@<major-version>' with an explicit "
            f"integer major version, got {value!r}"
        )
    return PackRef(match.group("id"), int(match.group("major")))


def load_project_text(text: str, *, fmt: str = "yaml") -> ProjectDoc:
    """Parse a packed project without importing or activating any pack."""

    raw = json.loads(text) if fmt == "json" else yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ProjectSchemaError(
            f"a packed project must be a mapping, got {type(raw).__name__}"
        )

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ProjectSchemaError("project 'name' is required and must be non-empty")

    units = raw.get("units")
    if units not in _UNITS:
        raise ProjectSchemaError(
            f"project units must be one of {sorted(_UNITS)}, got {units!r}"
        )

    pack_values = raw.get("packs")
    if not isinstance(pack_values, list) or not pack_values:
        raise ProjectSchemaError(
            "project 'packs' must be a non-empty list of '<pack-id>@<major-version>'"
        )
    packs = tuple(_parse_pack_ref(value, i) for i, value in enumerate(pack_values))
    seen: set[str] = set()
    for ref in packs:
        if ref.pack_id in seen:
            raise ProjectSchemaError(
                f"duplicate pack activation for {ref.pack_id!r}; activate a pack once"
            )
        seen.add(ref.pack_id)

    sections: dict[str, dict] = {}
    for key, value in raw.items():
        if key in _META_KEYS:
            continue
        if not isinstance(value, dict):
            raise ProjectSchemaError(
                f"project section {key!r} must be a mapping, got "
                f"{type(value).__name__}"
            )
        sections[str(key)] = dict(value)
    return ProjectDoc(name=name.strip(), units=units, packs=packs, sections=sections)


def load_project_file(path: str | Path) -> ProjectDoc:
    path = Path(path)
    fmt = "json" if path.suffix.lower() == ".json" else "yaml"
    return load_project_text(path.read_text(), fmt=fmt)


def compile_project(doc: ProjectDoc, *, registry: PackRegistry | None = None):
    """Resolve explicitly activated packs and compile one packed project.

    V1 intentionally supports one active domain front end. The document uses a
    list so the syntax does not need to change when multi-pack composition gains
    a designed result-merging contract.
    """

    registry = default_pack_registry() if registry is None else registry
    active = [registry.resolve(ref) for ref in doc.packs]
    if len(active) != 1:
        raise ProjectSchemaError(
            f"packed-project v1 activates exactly one domain pack; got "
            f"{[ref.key for ref in doc.packs]}"
        )

    claimed = {
        str(section)
        for pack in active
        for section in getattr(pack, "section_keys", ())
    }
    for key in doc.sections:
        if key in claimed:
            continue
        suggestion = difflib.get_close_matches(key, sorted(claimed), n=1)
        hint = f"; did you mean {suggestion[0]!r}?" if suggestion else ""
        raise ProjectSchemaError(
            f"unclaimed project section {key!r}; active pack sections: "
            f"{sorted(claimed)}{hint}"
        )
    return active[0].compile(doc)


def compile_project_file(path: str | Path):
    return compile_project(load_project_file(path))
