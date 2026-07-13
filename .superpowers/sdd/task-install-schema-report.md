# Task INSTALL-SCHEMA report — the FastenerInstallation contract, ConnectionType defaults, spec surface, provenance

Branch `sdd/install-schema` off master d57bf8a. Implements the schema arc of
INSTALL v1 (installability-design.md, APPROVED-WITH-AMENDMENTS): the typed
contract, the ConnectionType default-contract hook on all 8 registered types,
the `install:` spec override surface on both connection-build paths, and
per-field provenance resolution in `Connection.generate_checks`. NO geometric
checks and NO coverage-family/vocabulary edits (the sibling `sdd/install-family`
branch owns coverage.py / RENDERABLE_CHECK_KINDS / EXPECT_CHECKS / evidence
`_IMPERATIVE_DECL`; nothing in this diff touches them).

## Import-path verification (environment)

The venv's PEP-660 editable finder maps `detailgen` to the MAIN checkout and,
being a meta-path finder appended after PathFinder, is beaten by a sys.path
entry that actually contains a `detailgen` package — the ledger's ".shim
symlink pattern" (progress.md:2697). All runs used:

    cd <worktree> && mkdir -p .shim && ln -sfn "$PWD/src" .shim/detailgen
    export PYTHONPATH="$PWD/.shim"
    python -c "import detailgen; print(detailgen.__file__)"
    # -> <worktree>/.shim/detailgen/__init__.py   (verified before every gate)

(`.shim/` is already in .gitignore — the established convention. The brief's
literal `PYTHONPATH=$PWD/src` recipe cannot work here: `src` IS the package
body, so no path entry can offer a `detailgen` name without the shim.)

## Decisions

### Contract field shapes (`src/assemblies/installation.py`, new leaf module)

`FastenerInstallation` — frozen, plain-data, canonical field order
`CONTRACT_FIELDS = (method, entry_face, tool_axis, exit, embedment, head,
tool_envelope, stage)` (installation.py:247-273):

- `method` — OPEN string tag (ProcessStep.kind precedent).
- `entry_face: EntryFace(part, face)` — the member (Placed.id once resolved)
  + a SEMANTIC face descriptor (installation.py:153-176). Descriptor
  vocabulary used by the defaults: `free_face` (through-member face opposite
  the joint interface), `exposed_face` (toe-screw entry), `hanger_face`,
  `drilled_face`. Deliberately an open descriptor set: it is data the axes
  branch maps to geometry per method; an unknown descriptor must degrade to
  honest UNKNOWN, never a guess.
- `tool_axis: ToolAxis(mode: shank|angled, angle_deg, axis_idealized)` —
  `shank` = use the fastener's own `axis` datum (fasteners.py:87-98);
  `angled` = the declared angle off the entry face IS the semantics, and
  `axis_idealized=True` states the drawn solid does not model it (amendment
  #3: a contract-referencing display fact, never a waiver — consumers cap
  verdicts along an idealized axis at REPRESENTED).
- `exit: Exit(condition, faces)` — condition CLOSED
  (`none|concealed_exit|through_exit_required`); `faces` is the declared
  face-set (concealed disclosure, or the REQUIRED far side for a through
  bolt — what makes both bolt ends checkable).
- `embedment` — mm float | literal `"through"` | None (honest "no declared
  minimum", provenance `assumption`).
- `head` — CLOSED (`proud|flush_countersunk|recessed_in_pocket|nut_and_washer`).
- `tool_envelope: ToolEnvelope(length, dia)` mm — ALWAYS resolved; module
  default 6in x 1in (F-6) via `tool_envelope_for(method)`;
  `METHOD_TOOL_ENVELOPES` exists but ships EMPTY (inventing per-method driver
  sizes would be fake manufacturer_data); printable via `.describe()` so
  every verdict names its used value.
- `stage` — v1 knows only `"own_connection"`; real sequencing is axis-3/CPG.

`ResolvedInstallation` (installation.py:318-390) binds a contract to
(connection label, role, driven fastener Placed.ids, non-driven `stack` ids)
with `provenance` as a `(field, source)` tuple in canonical order —
`provenance_map` / `assumption_fields` helpers give reviewers guardrail #7's
"WHICH fields are assumption-grade" directly. `describe()` is the single
deterministic rendering used verbatim as the derivation-log fact
(`field=value [source]; ...`).

Fastener-class identification: component CLASS NAMES
(`LagScrew, StructuralScrew, HexBolt, ThreadedRod` — installation.py:120-128),
the same class-name mechanism as connection.py's positional role guards, so
the leaf module needs no components import. Washers/nuts/epoxy/hangers/post
bases are stack/connector hardware: they ride a fastener's single contract
(`stack`) or carry field fasteners on their own BOM line — never separate
contracts, and never UNKNOWN-flagged.

### Per-type defaults (each honest to its own docstring)

- `toe_screwed` → `toe_screw`, ANGLED 30° (`TOE_SCREW_ANGLE_DEG`, an
  assumption-grade technique value) off the EXPOSED hung-member face,
  `axis_idealized=True` (drawn solids straight today), exit none, head proud.
  Provenance: `tool_axis` and `embedment` = `assumption`. (CAT-B as data.)
- `cleat_screwed` / `rail_cap_screwed` / `butt_screwed` → `driven_straight`
  along the shank, entry on the THROUGH member's `free_face` — through member
  derived from each type's own `_unpack` role layout: the cleat (parts[0]),
  the cap (parts[1]), the face_member (parts[0]) respectively. Exit none,
  head proud.
- `bolted_clamp` → `through_bolt`, entry = head side (plates[0] free face,
  per the documented hardware order: head washer seats on plates[0]), exit
  `through_exit_required` with faces = nut side (plates[-1] free face),
  embedment `"through"`, head `nut_and_washer`, fasteners=(bolt,),
  stack=(washers, nut). Both sides checkable from the contract. (CAT-C.)
- `face_mount_hanger` → TWO role groups (`header_screws`, `hung_screws`),
  both `driven_straight` into `hanger_face` of the respective member; the
  hanger itself rides the header group's `stack`.
- `threaded_rod_epoxy_anchor` → method `epoxy_set` (open tag — an epoxy rod
  is NOT "driven"; representing what is true), entry = the anchor base's
  `drilled_face`, shank axis, exit none, head `nut_and_washer` (the top
  washer/lock/jam stack), embedment None + `assumption` (the minimum is
  adhesive-spec data the type cannot honestly invent; the detail's own
  embedment dimension check carries the authored depth). Rod is the
  fastener; epoxy + 3 nuts + 2 washers are stack.
- `standoff_post_base` → EXPLICIT `()` — no fastener-class hardware by the
  type's own semantics (concrete anchor + post fasteners are field hardware
  on the PostBase BOM line). `()` vs the base `None` is a deliberate
  distinction: "nothing to contract" vs "cannot represent".
- Embedment default for all driven screws: HALF the under-head length of the
  shortest screw in the group (conservative), stamped `assumption` with an
  explanatory note that flows into the DerivedFact assumptions; a component
  with no `length` gets None + note, never a fabricated number.

### Resolution + provenance (`Connection._resolve_install`, connection.py:466-577)

- `Connection.install` — plain dict `{role: {field: value}}`; the `""` key
  targets every group, a named key wins per-field over `""`. Unknown role /
  unknown field are teaching errors (did-you-mean on roles).
- Authored fields overlay type defaults PER FIELD via
  `resolve_role_group`; overridden fields stamp `authored_override`, the
  rest keep the type's stamps (including `assumption`).
- Type with NO default (`install_contract() is None`) + authored `method` ⇒
  `authored_only_contract`: one "authored" group over all fastener-class
  hardware; un-authored fields carry honest None/"" with `assumption`
  (tool_envelope still resolves — printable used-value rule).
- Derivation log: ONE DerivedFact PER CONTRACT, fact =
  `ResolvedInstallation.describe()` (every field with its source — chosen
  over one-fact-per-field as the more readable form; per-field visibility is
  preserved verbatim in the line and structurally on
  `ConnectionChecks.installs`). `subjects` = driven fastener Placed.ids
  (evidence orphan guards satisfied: real placed parts, declared connection).
  Confidence/source_type transpose the :326-345 override-identity pattern to
  field provenance: ALL fields authored ⇒ `official`/`authoritative`; any
  default/assumption content ⇒ `inferred`/`verified_heuristic`.
- Core invariant: fastener-class hardware not covered by any resolved group
  ⇒ ONE blocking `Finding("install_method", "<label>: <names>",
  verdict=UNKNOWN)` with detail beginning `UNKNOWN — NO INSTALLATION METHOD
  REPRESENTED` (connection.py:554-577). Emits NOTHING else; no geometry.
- `ConnectionChecks.installs` (connection.py:189) + aggregation in
  `compile_connections` (connection.py:596) = the stash Detail.validate
  already retains (`_connection_checks`, details/base.py:249).

### Spec surface

- schema.py: `InstallSpec` (:392-437 (schema.py)) beside ExpectSpec — flat, frozen, all
  fields optional; `ConnectionSpec.install` (:458-462 (schema.py)). Exit/head
  vocabularies IMPORTED from the leaf module as
  `INSTALL_EXIT_CONDITIONS`/`INSTALL_HEAD_CONDITIONS` (schema.py:25-33) —
  named module constants without duplication, so spec and contract can't
  drift. Method stays open.
- loader.py `_build_install` (:783-900 (loader.py)): strict `_take` keys
  (method/entry/angle/exit/exit_faces/embedment/head/tool/stage/role),
  teaching errors for: unknown key (did-you-mean), non-numeric or
  out-of-range angle ([0,90); 0 = shank), unknown exit/head value
  (did-you-mean + semantics), `exit_faces` without a matching exit,
  `concealed_exit` without its face-set (the disclosure IS the point),
  empty/role-only block, `tool` missing length or dia, `entry` missing
  part/face. Value-language fields stay RAW.
- compiler.py `build_install_overrides` (:1265-1321 (compiler.py), module function):
  lowers InstallSpec → the Connection.install map; embedment/tool lengths
  through `resolver.resolve_length` (`"through"` passes uninterpreted),
  entry/exit part templates through `_interp` + `_resolve_part` (repeat
  bodies work); angle 0 ⇒ `ToolAxis("shank")`, angle>0 ⇒ angled +
  `axis_idealized=True` (no angled-solid vocabulary yet — the compiler will
  set it False only when it can prove the solid matches). Passed INTO
  `Connection(...)` at `_build_connection` (:770-771 (compiler.py)) — present where
  generate_checks runs, NOT expect-style doc-side re-attachment.
- site.py `_build_site_connection` (:878-881 (site.py)): the second build path lowers
  through the SAME shared helper against `_site_resolver` + `_resolve_qid`.
- serialize.py `_install_to_dict` (:293-322 (serialize.py)): authored fields only
  (omit-defaults); `load(dump(doc)) == doc` and byte-stable re-dump
  test-proven; existing spec round-trip byte-equality untouched (no shipped
  spec authors an install block).

## Consumption surface for the axes branch (task 11/12)

Read `ConnectionChecks.installs` (also retained on
`Detail._connection_checks` after validate()): a list of
`ResolvedInstallation` in declaration order. Per entry: `contract.method`
selects the verdict shape; `entry_face`/`exit` are the semantic locations;
`tool_axis.mode=="shank"` means use the fastener component's `axis`/`tip`/
`head_bearing` datums, `angled` means the declared `angle_deg` off the entry
face with `axis_idealized` capping the rung at REPRESENTED; `embedment` is
mm/"through"/None; `tool_envelope` is always present and printable
(`describe()`); `fasteners` are the driven Placed.ids (geometry lookups),
`stack` the co-covered hardware; `provenance_map`/`assumption_fields` feed
doc disclosures. The full module docstring section "Consumption surface"
(installation.py:55-84) is the normative version of this paragraph.

## Coordination (RESOLVED — family branch merged in)

- `sdd/install-family` merged to master @353224a mid-task; per the clause,
  `git merge master` ran into this branch (clean — no conflicts; the family's
  schema.py/coverage.py/evidence.py touches are disjoint from this branch's
  regions). `install_method` is now MAPPED (KIND_TO_FAMILY → "Fastener
  installability", RENDERABLE_CHECK_KINDS, evidence `_IMPERATIVE_DECL`) and
  deliberately NOT in EXPECT_CHECKS (an installability FAIL is not pinnable).
  The synthetic-unresolved test additionally pins that mapping.
- Combined-tree verification: `regen_baselines.py --check` → "baselines are
  current" (the family branch changed no derivation logs; this branch's
  regenerated counts stand); full suite re-run on the merged tree (numbers
  below).

## Residuals / honest gaps

- Assumption-grade content shipped (visible per field, by design):
  toe-screw angle 30° (technique assumption), screw embedment = half
  under-head length, epoxy-rod embedment None (adhesive-spec data),
  `METHOD_TOOL_ENVELOPES` empty (module default used for every method).
- `axis_idealized` is ALWAYS True for angled axes (type default and authored)
  until angled fastener placement vocabulary (design work order #2) lands.
- The site build path is exercised structurally (shared helper 3-line call +
  the standalone-path tests); no site spec authors an install block yet, so
  no site-level end-to-end install test exists. site.spec.yaml compiles
  unchanged (suite green).
- One `install:` block per connection (the brief's singular surface): two
  role groups needing DIFFERENT overrides on the SAME connection can be
  expressed only via role-targeted single block per role — i.e. not yet;
  first real need should extend ConnectionSpec.install to a tuple.
- `entry_face.face` descriptors are open strings; the axes branch must map
  them per method and honestly UNKNOWN an unmappable one.

## Gates

- Import-path verification: shown above, re-run before each pytest gate.
- New tests: tests/test_install_contract.py (20),
  tests/test_install_spec_surface.py (18) — all green.
- Full suite from the worktree, pre-merge tree: 1060 passed / 3 skipped /
  1 xfailed (master 1020/3/1; +40 = the 38 new tests + 2 new parametrized
  cases of test_scripts_spec_rewire's per-test-file no-imperative-load guard
  over the two new test modules — verified by per-module collection diff
  against a throwaway worktree at d57bf8a).
- Full suite on the COMBINED tree (post `git merge master` @353224a):
  **1060 passed / 3 skipped / 1 xfailed** (the family branch added no net test items; import-path verification printed inline in the same run).
- Baselines: `python scripts/regen_baselines.py` — detail_counts
  derivation_log platform 688→722, rock_anchor 100→104; parts unchanged;
  consolidated_doc.textlayer / slice_accounting / site_divergence
  regenerated byte-identical. `python scripts/refreeze_from_spec.py`
  re-froze platform.json + rock_anchor.json (rock_anchor added to the
  script's EVOLVED set with a documented INSTALL rationale) — reviewed
  field-by-field: findings triples, by_kind, findings_fp, bom, ok all
  UNCHANGED; only counts.derivation_log and content_fp(_spec) moved (the
  content fingerprint hashes derivation facts); geom_fingerprint churn is
  float noise well under the 1e-6 oracle (reviewer-measured: max abs 1.19e-7
  on a 1.44e8 mm³ volume ≈ 8e-16 relative; max relative 1.1e-5 on a near-zero
  bbox coordinate — no real geometry change). tree_attachment /
  trolley_launch deliberately NOT re-frozen (their derivation logs are 0 —
  no justified diff). Platform's `ok: false` is PRE-EXISTING (false→false),
  not introduced here.
- All 9 standalone specs compile + validate with no new findings and no
  blocking change (existing e2e modules pin their findings; suite green is
  the proof), and the no-UNKNOWN property is additionally unit-proven
  per-type in test_install_contract.py.
