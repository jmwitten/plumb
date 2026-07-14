# DV72 Floating Double-Sink Vanity Design

Date: 2026-07-14

Status: Owner brief approved autonomous implementation; unresolved release facts remain explicit holds.

## Outcome

Implement a 72-inch wall-hung, frameless vanity inspired by
`IMG_7670.HEIC`: warm figured-wood slab fronts, two equal sink bays, two
drawers beneath each sink, dark reveals, half-moon brass pulls, and a pale
stone top. The deliverable is a model-backed coordination package, not a false
fabrication release. It must show useful physical geometry, identify every
remaining responsible-party decision, and generate four concise linked HTML
documents:

1. review and installation;
2. assembly and service;
3. fabrication coordination; and
4. validation and sources.

## Selected architecture

Use the existing opt-in `vanity.double_sink@1` pack and its one-model lowering
to DetailSpec. Do not create a second geometry engine. Retain the pack's
analytic fixture, plumbing, service, drawer, and mounting envelopes, and extend
the output projection so every document reads the same model and findings.

The case is 72 in wide with two nominal 36 in bays, three structural verticals,
two bay bottoms, paired front stretchers, and one continuous rear rail. Each
bay contains an upper U-shaped removable drawer around the sink tailpiece,
trap, shutoffs, and hand/tool service envelope, plus a removable lower drawer
kept forward of the rear service zone. Drawers must be removable without
demolishing the case so both traps, valves, rough-ins, rail, and anchors remain
serviceable.

## Product evidence

The model and documents distinguish verified manufacturer dimensions from
provisional placement and from project-specific unknowns.

- Fixture: Kohler rectangular undermount lavatory. The current design-study
  adapter remains the K-20000 Caxton until the countertop fabricator confirms
  its current template. The K-2882 Verticyl was also checked and has comparable
  503 x 397 x 171 mm gross geometry; changing fixture is a controlled adapter
  revision, not a drawing edit.
- Drain: Kohler K-7124-A clicker drain with overflow, 1-1/4 in connection,
  130 mm nominal body below the flange.
- Trap: Kohler K-8998 cast-brass adjustable P-trap, 1-1/4 x 1-1/4 in, 298 mm
  long x 111 mm high, with slip-joint inlet and cleanout plug. Each sink gets
  its own trap; no shared or double-trap topology is inferred.
- Drawer runner candidate: Blum MOVENTO 763.4570S / current 18-in standard-duty
  family for the upper drawers, full extension with BLUMOTION. Manufacturer
  planning data controls inside-depth, box-width, fixing, locking-device, and
  removal requirements. Lower runner selection remains open if the accepted
  plumbing forces a box shorter than the product's range.
- Mount references: a continuous cabinet rear rail with GRK RSS 5/16 x 4 in
  candidate fasteners represents the case-to-wall path. Rakks EH-1818-LV
  vanity brackets provide a comparative 450 lb evenly distributed static-load
  system and installation pattern, but are not silently combined with the
  rail or treated as project capacity.

Manufacturer CAD/BIM may improve visualization after its source, units,
revision, transform, and redistribution terms are recorded. Manufacturer
specification dimensions and current cutout templates remain controlling.

## Release boundary

Geometry may PASS when it proves only geometry. The package must keep these
facts UNKNOWN until evidence is attached: exact fixture/template revision,
countertop fabrication, final faucet/valve, field survey and rough-ins,
licensed-plumber approval, buildable drawer derivation, dynamic travel/removal
and service sweeps, project-specific wall-mount calculation, and commissioning.

The review/install document leads with the hold and the useful section. The
assembly document explains removability and service order. The fabrication
document exposes model inventory and withheld dimensions without authorizing
cutting. The validation document contains every finding, source, public-model
authority rule, and release gate.

## Verification

- Test document routing, reciprocal links, concise scope, and deterministic
  bytes.
- Test that all nine release findings appear in validation and that the other
  documents summarize rather than duplicate them.
- Test that the section contains fixture, drain/trap, service envelope, both
  drawer levels, counter, rear rail, wall, and candidate anchor information.
- Run the full double-vanity and cabinetry test sets, then the complete suite.
- Obtain an adversarial technical review and a no-context handyman review;
  fix Critical and Important findings before push.

## Time accounting

Record elapsed work in four buckets: reused platform investigation, bespoke
vanity/product work, document implementation, and verification/review. The
final handoff must state which capabilities were reused and which remained
project-specific.
