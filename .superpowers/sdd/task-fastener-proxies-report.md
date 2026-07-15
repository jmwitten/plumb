# Task report — schematic fastener proxies in the DB40 explode view

**Option A implemented:** labelled schematic fastener proxy bodies, positioned
exactly at the typed machining stations, added to the PRESENTATION scene only
(the interactive viewer's GLB + hover payload) behind an opt-in flag.

## What ships

- New module `src/packs/cabinetry/fastener_proxies.py`:
  - `_FastenerProxy(Component)` — a cheap cylinder-and-head body (no thread),
    sized from the typed catalog product, disclosing itself as schematic.
  - `proxy_stations(project, assembly)` — pure derivation of one
    `ProxyStation` per individual scheduled fastener in a covered class.
  - `append_fastener_proxies(project, assembly)` — appends the proxy bodies to
    a throwaway product-view assembly and returns the viewer payload rows.
- `scripts/cabinetry_project_report.py`: `render_shared_product_assets(...,
  include_fastener_proxies=False)`. Default off ⇒ the accepted technical
  document pipeline is byte-identical. The static views render from the base
  scene first, so only the interactive viewer (GLB + payload) gains proxies;
  the isometric PNG is unchanged.
- `scripts/cabinetry_consumer_manual.py`: passes `include_fastener_proxies=True`
  (only edit to that script).
- Tests: `tests/test_cabinetry_fastener_proxies.py` (9 tests).

## How positions are derived (no invented locations)

Each proxy comes from ONE `MachiningFeature` row and nothing else. The station's
world position is derived from the typed row plus the machined part's own placed
geometry:

- Fastener axis = the machined panel's thickness axis (the face normal, read off
  the part's world frame).
- Head plane = the part's world bounding-box extreme on that axis, on the side
  the row's `face` names (`outside`/`inside` resolved against the cabinet
  centre, `top` up, `front` toward the room).
- In-face position maps the row's `+X`/`+Y` PHYSICAL direction words (`up`,
  `toward wall`, `rearward`, `right`, …) onto world axes. This was essential:
  the face datums use different origin corners and axis handedness than the
  panel's solid frame, so a naïve "face coords = solid-local coords" mapping
  produced MIRRORED positions (caught during validation). Reading the physical
  words lands on the true corner every time.
- Drive axis = into the part (−outward normal); for the receiving-based classes
  this was independently checked to point toward the receiving part. Explode =
  head-backing-out (+outward normal), matching the through-hole convention in
  `rendering/web_viewer/explode.py`.

All 98 stations were verified on-face, in-footprint, and (where a receiving part
is named) drive-toward-receiving, before writing the module.

## Classes COVERED (98 proxies) — count cross-checked against the hardware schedule

| Machining kind | Proxies | Reader name | Hardware line (qty) | Product |
|---|---|---|---|---|
| `confirmat_step_drill` | 26 | Confirmat screw | `carcass_confirmat_system` (26) | Häfele Confirmat 7×50 |
| `drawer_box_confirmat_step_drill` | 24 | Confirmat screw | `drawer_box_joinery_fastener` (8×3) | Häfele Confirmat 7×50 |
| `toe_attachment_station` | 6 | Cabinet screw | `toe_base_attachment_system` (6) | GRK #8×1‑1/4 |
| `applied_front_attachment` | 12 | Front-attachment screw | `applied_front_fastener_system` (4×3) | GRK #8×1‑1/4 |
| `runner_fixing_station` | 30 | Runner mounting screw | `drawer_runner_installation_screw` (10×3) | Blum 606N (from runner record) |

(Confirmat carcass + drawer-box share one physical product, so both read
"Confirmat screw" and are instance-numbered together, 1…50.)

## Classes SKIPPED (disclosed, not guessed)

- `locking_device_bore` — `location_mm` is empty (an angled 75° template at the
  drawer-front corner); no honest position to derive.
- `pull_bore` — the drawer pull is a handle, not a fastener, and the mounting
  screw's insertion side is not fixed by the typed row. (Left for a possible
  future non-fastener "pull" proxy.)
- `stabilizer_gear_rack_cut`, `stabilizer_linkage_rod_cut` — hardware-stock cut
  lengths on a non-placed hardware id; no scene position.
- `captured_back_groove`, `drawer_bottom_groove`, `runner_rear_notch`,
  `runner_hook_bore` — material-removal features (grooves/notches/bores), not
  connector bodies.
- Wall anchors are already modelled as real 3D bodies; not proxied.

`SKIPPED_KINDS` in the module and a test assert that every machining kind the
model emits is either covered or explicitly skipped — nothing falls through
silently.

## Test evidence

- `tests/test_cabinetry_fastener_proxies.py` — **9 passed**. Covers: covered/
  skipped partition of every emitted kind; per-class count == hardware schedule;
  proxy total == covered rows expanded by count; every proxy on its typed
  station (on the machined face, in footprint); explode along the drive axis;
  catalog-sized dims; append preserves the base scene and adds only proxies;
  flag OFF ⇒ payload + scene unproxied and payload equals today's baseline; flag
  ON ⇒ proxies in the GLB, model rows untouched, every proxy row carries the
  schematic disclosure.
- Affected existing suites stay green: `test_cabinetry_project_report.py`,
  `test_cabinetry_instruction_manual.py`,
  `test_cabinetry_consumer_manual.py -k "not PrintBreaks"`,
  `test_viewer_instruction_panels.py` — **98 passed, 1 deselected**.
- Also green: `test_viewer_explode_and_fab.py`, `test_inspector_payload.py`.
- End-to-end: `scripts/cabinetry_consumer_manual.py` renders the full document;
  its embedded viewer payload carries all 98 proxy rows (Confirmat 50, Runner
  30, Front-attachment 12, Cabinet 6) with catalog specs, `[-120,0,0]`-style
  explode vectors, and the schematic disclosure.

## GLB cost

The 98 proxies share only ~3 distinct geometries (Häfele confirmat, GRK cabinet
screw, Blum runner screw) by `cache_key`, so `isolated_world_solids` tessellates
each once. Coarse geometry (plain cylinders), consistent with the shared GLB's
tolerance 0.4.
