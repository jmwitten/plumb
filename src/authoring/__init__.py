"""Compact public vocabulary manifest for DetailSpec authoring."""

from .manifest import (
    authoring_manifest_json,
    build_authoring_grammar,
    build_authoring_manifest,
)
from .workflow import build_workflow_contract
from .component_extension import (
    CHANGE_CLASSES,
    COMPONENT_FAMILIES,
    ComponentExtensionContract,
    ComponentExtensionError,
    build_component_context_route,
    build_component_extension_guide,
    load_component_extension_contract,
    verify_component_extension,
)
from .scaffold import (
    ScaffoldComponent,
    ScaffoldConnection,
    ScaffoldDocuments,
    ScaffoldError,
    ScaffoldRequest,
    ScaffoldResult,
    build_scaffold,
    write_scaffold,
)

__all__ = [
    "authoring_manifest_json",
    "build_authoring_grammar",
    "build_authoring_manifest",
    "build_workflow_contract",
    "CHANGE_CLASSES",
    "COMPONENT_FAMILIES",
    "ComponentExtensionContract",
    "ComponentExtensionError",
    "build_component_context_route",
    "build_component_extension_guide",
    "load_component_extension_contract",
    "verify_component_extension",
    "ScaffoldComponent",
    "ScaffoldConnection",
    "ScaffoldDocuments",
    "ScaffoldError",
    "ScaffoldRequest",
    "ScaffoldResult",
    "build_scaffold",
    "write_scaffold",
]
