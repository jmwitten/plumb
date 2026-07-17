# General DetailSpec Scaffolder Design

## Problem

The live authoring manifest exposes registry keys, constructor signatures, and
top-level DetailSpec keys, but not the nested shapes needed to author a valid
component, placement, connection, validation check, or certification contract.
In a fresh-context benchmark, that gap caused an agent to invent a different
schema and retry package generation repeatedly. The manifest also leaves two
important conventions implicit: dimension measures are world-axis bounding-box
values, and lumber miter angles are measured in degrees off square.

## Decision

Add a registry-backed `scaffold` subcommand to `python -m detailgen.authoring`.
The command accepts a slug, explicit component selections, constructor values,
optional explicit placements, connection selections, and connection constructor
values. It emits `<slug>.spec.yaml` and `<slug>.cert.yaml` only after loading and
compiling the spec and loading the certification contract.

The scaffolder never guesses physical dimensions, placements, nominal sizes,
connection participants, or validation claims. Missing required constructor
parameters and unsupported keys fail closed with a diagnostic that names the
valid vocabulary and the exact missing fields. A component with an omitted
placement retains DetailSpec's documented identity placement; that is
structurally and compiler valid but may be physically unresolved when combined
with other members. The command reports that distinction rather than treating a
preview package or review as part of scaffolding.

## CLI

```text
python -m detailgen.authoring scaffold \
  --slug garden-frame \
  --out details \
  --component post:lumber \
  --set post.nominal=2x4 \
  --set post.length=36 \
  --place 'post={raw: {at: [0, 0, 0]}}'
```

- `--component ID:TYPE` is repeatable.
- `--set ID.PARAM=YAML_VALUE` is repeatable and supplies component parameters.
- `--place ID=YAML_MAPPING` is repeatable and supplies an exact DetailSpec
  placement block.
- `--connection TYPE:PART[,PART...]` is repeatable.
- `--connection-set INDEX.PARAM=YAML_VALUE` is repeatable, where `INDEX` is the
  zero-based connection occurrence.
- `--out` is a directory. Existing outputs are not overwritten without
  `--force`.

Connection parts must name declared component ids. Registry signatures provide
the required parameter set for both components and connections. The generated
certification contract uses `standalone_detail` and points to the generated
spec beside it.

## Compact Grammar

The authoring manifest advances to v3 and adds an `authoring_grammar` object.
It documents exact nested field shapes for top-level metadata, components,
placements (`mate`, `raw`, and `mount`), connections, validation dimensions,
and the minimal certification contract. This object is deliberately compact:
it is a grammar and convention index, not a copy of every schema dataclass.

The dimension section explicitly states that `xmin` through `zlen` are measured
from the placed solid's world-axis bounding box. No rotation-invariant member
length measure currently exists, so the scaffolder emits no dimension check by
default and directs authors to refuse an intrinsic-length claim rather than use
`xlen` on a rotated member.

The lumber section explicitly states that `miter_angle_degrees` is the angle
off square, not the acute angle between joined members. It documents the exact
`end_cuts` mapping and the required
`length_semantics: long_point_to_long_point` pairing.

## Boundaries and Failure Handling

`detailgen.authoring.scaffold` owns parsing, validation against live registry
signatures, document assembly, atomic-ish output checks, and post-write
load/compile/contract verification. It reuses the DetailSpec loader/compiler and
certification contract loader as the authority. It does not reproduce geometry
rules, infer datums, run product gates, generate a package, or certify physical
adequacy.

Input errors use one `ScaffoldError` family and produce CLI exit code 2 with a
single actionable message. Unexpected compiler or contract errors retain their
native diagnostics. Output collision is checked before either file is written;
post-write verification failure removes both newly-created outputs.

## Tests

Focused tests cover:

- deterministic v3 grammar and the two convention warnings;
- a generic one-component scaffold that loads, compiles, and whose certification
  contract resolves;
- explicit raw placement and a generic connection with registry parameters;
- unknown component/connection keys, undeclared connection participants,
  missing required constructor parameters, unknown parameter names, malformed
  YAML values, duplicate ids, and output overwrite protection;
- CLI compatibility: no subcommand still prints the manifest.

No test or implementation uses the triangle product as a precedent.
