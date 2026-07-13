"""``detailgen.spec`` — DetailSpec: the declarative language and compiler
front-end (roadmap item 7).

A DetailSpec is a serializable, diffable, replayable description of a
construction detail (``params / derived / components / connections /
validation``) that the platform compiles — through the same registries, mate
API, and ``Connection`` machinery a hand-authored detail uses — into geometry,
validation, BOM, and documentation. It is the stable contract between AI
authoring and the framework: Claude emits a spec, not imperative Python, so
authoring is validated, diffable, and replayable.

Public API::

    from detailgen.spec import load_spec_file, compile_spec

    doc = load_spec_file("details/rock_anchor.spec.yaml")  # strict structural load
    detail = compile_spec(doc)                             # -> a Detail
    report = detail.validate()                             # standard sweep
    for fact in detail.derivation_report():                # P4 provenance
        ...

The two-step ``load`` then ``compile`` split is deliberate: loading is pure
structure (no CadQuery, no registries) so a spec's shape can be validated
cheaply; compiling resolves vocabulary + values and builds geometry lazily.
"""

from .compiler import (
    ParamsProxy,
    SpecCompileError,
    SpecDetail,
    compile_spec,
    compile_spec_file,
)
from .loader import load_spec_file, load_spec_text
from .schema import DetailSpecDoc, SpecSchemaError
from .serialize import dump_json, dump_yaml, spec_to_dict
from .values import SpecValueError

__all__ = [
    "load_spec_file",
    "load_spec_text",
    "compile_spec",
    "compile_spec_file",
    "ParamsProxy",
    "spec_to_dict",
    "dump_yaml",
    "dump_json",
    "SpecDetail",
    "DetailSpecDoc",
    "SpecSchemaError",
    "SpecValueError",
    "SpecCompileError",
]
