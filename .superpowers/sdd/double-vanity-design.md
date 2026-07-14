# DV72 floating double-sink vanity — design contract

**Status:** implementation contract for a design-study increment  
**Date:** 2026-07-14  
**Reference image:** `/Users/joelwitten/Downloads/IMG_7670.HEIC`

## Outcome

Add an opt-in `vanity.double_sink@1` pack that lowers to the unchanged base
DetailSpec language. Its first archetype is
`floating_double_sink_four_drawer@1`: a photo-inspired, nominal 72 in-wide
floating vanity with two undermount sinks and four drawer fronts arranged as
two independent 36 in service bays.

The first delivered document is a **design study, not a released build
document**. It must be useful for layout and coordination while loudly naming
the site, fixture, countertop, plumbing, drawer, and structural facts that
remain unresolved. No project can cross the release gate by selecting this
archetype alone.

## Reference-image interpretation

The photograph controls the visual intent only:

- floating rectangular body with no toe kick;
- two equal-width sink bays;
- two slab drawer fronts per bay;
- book-matched or sequence-matched warm figured wood where practical;
- thin dark shadow gaps at the center and horizontal reveal;
- half-moon brass pulls centered on each front; and
- a light, thick-looking stone top with two broad rectangular basins.

The photograph supplies no scale, joinery, material thickness, fixture SKU,
plumbing route, wall construction, load capacity, or code evidence. Those
facts must come from authored project data, selected catalog adapters, and site
survey evidence.

## First archetype defaults

Defaults exist to make a coherent study quickly; every release-sensitive
default remains explicit in the expanded project and carries provenance.

| Item | Study value | Authority |
|---|---:|---|
| Vanity width | 1828.8 mm / 72 in | owner-directed nominal |
| Cabinet body depth | 533.4 mm / 21 in | study default |
| Countertop depth | 558.8 mm / 22 in | unresolved layout default |
| Cabinet body height | 508 mm / 20 in | photo-inspired study default |
| Countertop thickness | 38.1 mm / 1.5 in | unresolved fabricator default |
| Bottom elevation | 254 mm / 10 in | study default |
| Bay width | 914.4 mm / 36 in | derived from equal split |
| Sink centers | x = 457.2, 1371.6 mm | derived equal-bay centers |
| Sink | Kohler Caxton K-20000 | selected analytic adapter |
| Faucet study candidate | Kohler K-T14414-4 + K-410-K | unresolved candidate |
| Drawer motion | Blum MOVENTO soft-close, full extension | catalog-backed family |
| Upper drawer | U-shaped/notched service drawer | derived geometry |
| Lower drawer | shortened box ahead of rear chase | derived geometry |
| Pulls | half-moon brass, catalog selection unresolved | visual requirement |

## Pack boundary

The new pack owns vanity-domain authoring and derived vocabulary:

- fixture and faucet selection;
- jurisdiction/version selection;
- plumbing paths and service envelopes;
- sink-bay and drawer-avoidance strategies;
- countertop/template coordination;
- wall-mount assembly and release evidence;
- manufacturer asset references; and
- vanity-specific drawings, findings, procurement, and installation steps.

It must lower all physical parts, contacts, overlaps, connections, sequence,
and validation expectations into existing DetailSpec constructs. It must not
add process-global component kinds or mutate base registries on import.

## Typed analytic model

### `CatalogAssetRef`

Metadata-only manufacturer reference. Required fields:

- manufacturer, exact SKU/variant, source and specification URLs;
- source revision and retrieval time;
- asset role and authority;
- format/media type, byte length, raw SHA-256 when downloaded;
- source units, axes, handedness, origin note, and explicit transform;
- named calibration anchors;
- terms URL/date, license class, and redistribution status; and
- analytic adapter id.

`unknown`, `local_only`, and `prohibited` assets may never be embedded in Git
or a self-contained release document. Renderers may consume a
`visual_reference`; cut-list, machining, structural, plumbing, and code checks
may not. The vanity must compile with the external asset cache absent.

### `SinkFixtureAdapter`

For K-20000, preserve separately:

- 514 x 398 x 186 mm gross fixture envelope;
- 448 x 334 x 135 mm bowl envelope;
- 44 mm drain and 31.75 mm tailpiece facts;
- drain center and overflow;
- named current cutout template `1281904-7` as a reference, never a cutout
  inferred from nominal bounds;
- clamp/rim/countertop zones; and
- installation, connection, and service envelopes.

### `WallFaucetAdapter`

For K-T14414-4 with K-410-K, preserve nominal and range facts independently:

- nominal 229 mm wall-to-drain center;
- published reach envelope;
- spout-to-rim range;
- wall bores, valve bodies, supply routes, handle operation, and service
  space; and
- finished-wall thickness datum.

The top depth, sink position, wall build-up, faucet reach, stone web, basin
clamps, and water target are one coupled coordination check.

### `PlumbingPath`

Model two independent sink systems. Each owns a drain, tailpiece, trap,
trap-to-wall arm, supply routes, shutoffs, connection arcs, and hand/tool
service envelope. The study can use honest analytic P-trap-shaped envelopes;
the fitting family and exact dimensions remain unresolved until selected by
the plumber.

Jurisdiction values come from a versioned profile. The initial profiles pin
NYC 2022 and IPC 2024 separately, including the different outlet-to-trap-weir
vertical maxima. No number may be presented as universal.

### `SinkBay`

Each 36 in bay is independently serviceable and contains:

- one upper U-shaped drawer with storage wings beside the basin/plumbing;
- one lower shortened drawer in front of a continuous rear chase;
- full-extension soft-close runners selected for each drawer's real length;
- a removable service path that exposes all concealed slip joints; and
- no fixed shelf/stretcher crossing the required service opening.

The U void, lower-box depth, rear chase, runner stations, and front attachment
patterns are derived from the selected fixture/plumbing/service geometry.
They are never copied from a catalog illustration as constants.

### `WallMountAssembly`

Model the continuous structural rail/back, verified studs/backing, fastener
axes, achieved embedment, edge/end distances, and complete load path. The GRK
RSS 5/16 x 4 in is a candidate SKU only. Capacity remains UNKNOWN until a
project-specific calculation/review covers substrate, geometry, dead and
service loads, contents, and installation tolerances.

## Geometry and motion checks

For each sink bay, the validator must keep these envelopes distinct:

1. fixture body;
2. template/countertop/clamp zone;
3. drain and trap physical path;
4. supply and shutoff path;
5. plumbing assembly/removal sweep;
6. hand/tool service envelope;
7. upper U-drawer closed and full-travel envelopes;
8. lower drawer closed and full-travel envelopes;
9. drawer removal path;
10. wall faucet rough-in and service envelope; and
11. structural rail/anchor keepouts.

Passing static closed-position clearance is insufficient. Release needs the
full movement, assembly, removal, and service paths to clear.

## Required release gates

The first study must emit all of these as required UNKNOWN findings and block
release until evidence is supplied:

1. **Fixture/template:** current K-20000 SKU/revision and template digest.
2. **Countertop/fabricator:** material, thickness, edge/web rules, cutout,
   reveal, clamps, reinforcement, sealant, and approved sink placement.
3. **Faucet:** final trim/valve, wall build-up, bores, reach, water target,
   rim gap, and service path.
4. **Site survey:** wall/floor datums, available span, front clearance,
   obstruction clearances, studs/backing, rough-ins, and shutoff locations.
5. **Plumbing approval:** LMP-selected traps/fittings and confirmed waste,
   vent, supply, access, slope, and jurisdiction/version compliance.
6. **Drawer derivation:** actual plumbing/service envelopes produce buildable
   U voids, lower depths, runner selections, and clearances.
7. **Dynamic access:** both drawers can operate and be removed; every required
   joint and valve can be assembled, inspected, and serviced.
8. **Wall mount:** project-specific load-path and connection calculation,
   reviewed substrate and fastener installation.
9. **Field commissioning:** fixture/leak tests, drawer operation under design
   contents, anchor inspection, and final service-access confirmation.

Honest FAIL or UNKNOWN always wins over a presentationally complete document.

## Reader outputs

The design-study document must include:

- reference-image intent and an explicit non-dimensional disclaimer;
- overall elevation, plan, and section;
- sink/faucet/top coordination section;
- per-bay plumbing and drawer-interaction diagrams;
- closed, open, removal, and service states;
- model-derived part/hardware inventory and unresolved procurement;
- wall-mount/load-path diagram;
- jurisdiction profile and code checkpoints;
- release-gate table; and
- installation sequence only to the level supported by evidence.

It must not call itself a build document or present fabrication dimensions for
unresolved countertop cutouts, plumbing fittings, drawer notches, or anchors.

## Acceptance

1. The old `vanity.frameless@1` V36 two-door fixture compiles byte-identically.
2. `vanity.double_sink@1` is opt-in and does not alter base registries.
3. DV72 has exactly two sink bays, two fixtures, two independent traps, four
   drawer fronts, four removable drawer boxes, and no toe-kick parts.
4. Sink centers satisfy the selected jurisdiction's side/obstruction and
   center-to-center checks; site front clearance remains independently gated.
5. Each upper drawer derives a U void from its own selected envelopes; each
   lower drawer stops ahead of the rear service chase.
6. Closed, full-extension, removal, plumbing-assembly, and service envelopes
   are checked independently for both bays.
7. Removing either bay's drawers exposes a measured service opening; a prose
   claim alone cannot pass.
8. Both plumbing systems remain independent and no S-trap/double-trap topology
   is emitted.
9. The wall mount is physically represented but capacity remains UNKNOWN
   without project evidence.
10. The study cannot pass `require_release()` with any of the required gates
    unresolved.
11. With no external CAD cache, analytic geometry, findings, artifacts, and
    document hashes remain deterministic.
12. Catalog asset metadata cannot cross from visual-reference consumers into
    fabrication or validation truth.

