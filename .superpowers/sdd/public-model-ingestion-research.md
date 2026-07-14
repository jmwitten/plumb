# Public model ingestion research

**Research date:** 2026-07-14  
**Scope:** official/public CAD, BIM, and technical resources that can accelerate the photo-inspired double-sink, four-drawer floating vanity and later catalog-backed projects.  
**Decision:** use manufacturer assets as pinned visual/configuration references; keep compact analytic geometry and explicit engineering contracts as the validation truth.

This is an engineering and repository policy, not legal advice. Terms change, and every accepted asset must carry the terms URL and the date on which it was reviewed.

## Executive conclusion

The platform can gain meaningful speed without becoming a warehouse of opaque models:

1. Add a metadata-only `CatalogAssetRef` contract first. A project may name an official asset, its product/SKU/revision, source URL, format, digest, units, coordinate transform, terms, and permitted use without committing the binary.
2. When the applicable terms permit local download/use, store manufacturer downloads in a user-local, content-addressed cache outside Git. Public availability is not permission to redistribute a file in the public `plumb` repository; a source whose terms do not permit the cache stays metadata/link-only.
3. Give every asset a narrow role: `visual_reference`, `cutout_template`, `collision_hint`, or `analytic_seed`. An imported mesh or BIM family is never silently promoted to structural, plumbing, machining, or code authority.
4. Keep the engine's validation geometry analytic: basin and drain envelopes, faucet centerlines, trap/service zones, drawer motion and service envelopes, mounting rails, fastener axes, embedment, and backing. These are small, inspectable, testable, and can be generated even when a vendor portal is unavailable.
5. A manufacturer cutout template can be authoritative for that cutting operation when its SKU/revision/digest are pinned and the license permits local use. It still must not be inferred from the external model's bounding box.

For the vanity, the highest-leverage near-term inputs are the Kohler fixture specification/template and a Blum sink-drawer configuration. A detailed GRK screw model would add almost no value; the mounting calculation needs fastener and substrate properties, spacing, edge/end distance, embedment, and load-path facts, not photorealistic threads.

## Selected vanity components

| Component | Official resources found | Best platform use | Repository policy |
|---|---|---|---|
| Kohler Caxton K-20000 sink | Product page exposes at least DXF cutout and Revit modules; Kohler also publishes a current two-page specification and identifies required template `1281904-7` | Visual sink body plus a separately pinned cutout; analytic basin, drain, clamp, countertop, drawer-avoidance, and service envelopes | URL/metadata in Git; downloaded CAD/template only in local cache unless Kohler grants redistribution |
| Kohler Purist K-T14414-4 wall faucet trim + K-410-K valve | Product page exposes at least DXF/Revit resources; specification gives the valve dependency, wall-to-drain centerline, reach, bores, and spout-to-rim range | Visual trim; analytic rough-in, handle/spout bores, valve/service space, supply lines, and water target | URL/metadata in Git; model local-only under the currently found terms |
| Blum sink drawer using MOVENTO/LEGRABOX/MERIVOBOX/TANDEMBOX | Product Database supplies individual-product CAD; Product Configurator supplies application CAD, checked parts lists, and planning output; official sink-cabinet page describes a U-shaped drawer and wood drawer + MOVENTO option | Configure the chosen 36-inch bay in metric, capture exact SKU/parts-list output, and seed the U-shaped drawer solution; keep runner drilling, clearances, motion, and plumbing avoidance analytic | Configuration metadata/output facts in project data; do not redistribute Blum CAD until the accepted E-SERVICES terms explicitly allow it |
| GRK RSS 5/16 x 4 in structural screw candidate | Product page, product information, technical drawing, and ICC-ES ESR-2442; no official 3D file was found in the reviewed GRK resources | Analytic fastener axis/head/shank plus code-report-backed connection facts after a real wall/backing calculation | Link and factual SKU metadata only; GRK terms prohibit redistribution/modification of site content without consent |

### Kohler Caxton K-20000

The [official K-20000 product page](https://la.kohler.com/en/product-detail/20000?skuid=K-20000-0) exposes a DXF cutout resource and a Revit BIM module on the currently visible regional surface. Kohler's [cutout-template guidance](https://assist.kohler.com/en/other-products/Cutout-Templates) says its library contains 2D and 3D CAD and directs users to the product page for the appropriate CAD/template.

The [current US/Canada specification](https://resources.kohler.com/webassets/kpna/catalog/pdf/en/K-20000_spec_US-CA_Kohler_en.pdf) is the stronger design input. It identifies basin clamps `1193643`, a 1-3/4 in drain hole, 1-1/4 in OD tailpiece, and required undermount template `1281904-7`. It expressly tells the countertop fabricator to use the supplied or current Kohler template and warns against incorrect-template cutout errors. That makes the split unambiguous:

- imported 3D fixture: visual reference and gross collision check;
- current `1281904-7` template: local cutout reference;
- explicit analytic model: bowl/drain/tailpiece/clamp/countertop/service/drawer envelopes.

Do not calculate the countertop cutout from the 3D model silhouette or nominal product bounding box. The same specification labels product dimensions nominal, and its named product size, overall page dimensions, bowl dimensions, and actual cutout serve different purposes.

### Kohler Purist K-T14414-4 and K-410-K

The [official K-T14414-4 product page](https://la.kohler.com/en/product-detail/T14414-4) exposes DXF and Revit resources on its current regional surface. The [official specification](https://resources.kohler.com/webassets/kpna/catalog/pdf/en/K-T14414-4_spec.pdf) says the trim requires K-410-K, places the spout 9 in from the finished wall to the drain centerline, gives a 9-1/2 in maximum reach, requires three 1-1/2 in bores, and constrains the bottom-of-spout to fixture-rim distance to 1-1/2–6 in.

The faucet asset therefore helps the render but does not replace a `WallFaucetAdapter` containing:

- finished-wall datum and drain target centerline;
- K-410-K concealed-valve rough-in/service envelope;
- hot/cold supply routes and shutoff/service assumptions;
- the three wall bores and trim coverage;
- spout trajectory, water target, rim clearance, and handle operating envelopes.

These analytic facts are what must interact with the sink, wall construction, mirror/backsplash, and drawer/plumbing design.

### Blum sink-drawer resources

Blum's [Product Database](https://www.blum.com/us/en/services/e-services/productdatabase/) provides technical attributes, drawings, and individual-product CAD in “all common formats” after free E-SERVICES registration. Its [Product Configurator](https://www.blum.com/us/en/services/e-services/onlineproductconfigurator/) provides 2D/3D application CAD, planning information, and a checked parts list. The US configurator currently accepts metric input, says its data is automatically kept current, and allows results to be exported as PDF/Excel.

The official [Blum sink-cabinet application](https://www.blum.com/us/en/products/cabinet-applications/sinkunit/overview/) validates the core design pattern: a U-shaped drawer uses storage to the left and right of plumbing; the application can use standard LEGRABOX, MERIVOBOX, or TANDEMBOX components, and Blum explicitly shows that a wood drawer with MOVENTO runners is also possible.

For this vanity, configure one representative 36 in (914.4 mm) sink bay after the sink, drain, trap, service chase, panel thicknesses, and front layout are fixed. Preserve:

- configuration/project identifier and export date;
- every selected Blum part/SKU and quantity;
- nominal length, load class, motion technology, locking device, and adjustment options;
- cabinet and drawer inputs in millimetres;
- output document/file digests;
- exact CAD format chosen, because “common formats” is not a stable format contract.

The configuration is a manufacturer-backed selection and parts-list oracle. The engine still needs its own analytic runner datum, drilling schedule, permissible drawer dimensions, motion envelope, U-notch geometry, and service/removal envelope so a model update cannot silently alter construction truth.

### GRK RSS wall fastener candidate

The [official RSS product page](https://www.grkfasteners.com/grk-products/structural-framing-screws/rss-rugged-structural-screw) lists 5/16 x 4 in variants and links the product information, technical drawing, and ESR-2442. The [current ESR-2442](https://www.grkfasteners.com/getmedia/5f4f72a8-8d1f-479b-8ae0-5fc043e2943d/ESR-2442.pdf?ext=.pdf) is the relevant evaluated-report source. No official GRK 3D CAD/BIM asset was found in the product and technical libraries reviewed; this is an observation as of the research date, not a guarantee that none exists.

A helical thread mesh would not answer whether the vanity is safe. Represent the candidate analytically and keep the wall mount unresolved until the model knows:

- wall framing/backing species, grade, size, condition, and exact position;
- rail/back dimensions and material;
- fastener diameter, length, head, thread/point geometry, and corrosion class;
- count, spacing, edge/end distances, member thicknesses, and achieved embedment;
- vanity dead load, countertop/fixtures, contents, construction tolerances, and design load combinations;
- connection demand/capacity calculation and governing code/report conditions.

The 5/16 x 4 in screw is a candidate catalog selection, not a generic “supports the vanity” fact.

## Licensing and redistribution findings

Public download buttons do not make files open source.

| Source | What the reviewed terms allow or say | Conservative platform decision |
|---|---|---|
| Kohler regional product site | Kohler's [Legal Statement](https://la.kohler.com/en/legal-statement) permits downloads for non-commercial personal use while retaining notices, and prohibits distributing, modifying, transmitting, reusing, or public/commercial use without written permission | Do not commit Kohler CAD, Revit, OBJ, imagery, or cutout files to the public repo; keep a local cache and commit only factual metadata, source links, digests, and independently authored analytic adapters |
| Blum US | Public pages invite use of CAD in design software, but the public [US T&C page](https://www.blum.com/us/en/terms-conditions/) publishes seller/delivery terms rather than a clear CAD redistribution license; account-level E-SERVICES terms may add conditions | Treat Blum downloads as local/project-use only until the exact accepted E-SERVICES agreement is recorded and permits redistribution; never infer a license from “free account” or “download” |
| GRK | [Terms of Use](https://www.grkfasteners.com/terms-of-use) grant personal, non-commercial display/use and prohibit reproduction, derivatives, retransmission, distribution, publication, and caching without consent | Default to metadata/link-only: no persistent GRK cache, PDFs, drawings, or site assets in Git; author analytic geometry/data with cited provenance |
| BIMobject/Bim.com | [User terms](https://business.bimobject.com/terms-of-service-eula) allow building professionals to include objects/content in project drawings and documents, but the right is non-exclusive, non-sublicensable, and non-transferable; content remains owned by BIMobject/manufacturers and is provided as-is | Accept as a project-reference source, not a source for a redistributable platform asset library; retain the manufacturer identity and license snapshot for each object |
| SketchUp 3D Warehouse | The [General Model License](https://3dwarehouse.sketchup.com/tos) permits models in a Combined Work with substantial added content but prohibits standalone sale/distribution and aggregation into another repository/service | Community models can accelerate visual mockups only; do not aggregate them into the pack or treat them as dimensional/engineering evidence |

For future structural products, Simpson Strong-Tie's manufacturer library is a useful example of a better-maintained source: its [Drawing Finder overview](https://seblog.strongtie.com/2020/11/specifying-simpson-strong-tie-products-in-your-designs-just-got-easier/) describes DWG, DXF, RFA, PDF, IFC, SAT, and STL content and explicit work on scale, insertion points, layers, and clash cylinders. Availability still does not remove the need to record the applicable license and engineering report.

## Proposed `CatalogAssetRef` contract

Store a small, serializable record in the project/release manifest. The raw file remains external unless `redistribution = permitted` is backed by a specific recorded grant.

```yaml
catalog_asset:
  id: kohler.caxton.k-20000.visual
  manufacturer: Kohler
  product_family: Caxton
  sku: K-20000
  variant: "0 white"
  asset_role: visual_reference  # visual_reference | cutout_template | collision_hint | analytic_seed
  authority: reference_only     # reference_only | manufacturer_template

  source_url: https://...
  source_page_url: https://...
  specification_url: https://...
  retrieved_at: 2026-07-14T00:00:00Z
  source_revision: "6-10-2024 20:30 - US"
  etag: null
  last_modified: null

  format: rfa
  media_type: application/octet-stream
  source_filename: ...
  byte_length: 0
  sha256_raw: ...

  terms_url: https://...
  terms_checked_at: 2026-07-14
  license_class: local_project_use_only
  redistribution: prohibited
  required_attribution: ...

  source_units: mm
  unit_evidence: manufacturer_dimension_anchor
  source_frame:
    handedness: right
    up_axis: z
    front_axis: negative_y
    origin_note: manufacturer-defined
  transform_to_project_mm: [16 explicit row-major numbers]
  anchors:
    - id: drain_center
      expected_mm: [x, y, z]
      tolerance_mm: project-declared
      evidence: current manufacturer specification

  converter:
    name: ...
    version: ...
    arguments: [...]
  normalized_sha256: ...
  analytic_adapter: kohler_k20000_v1
```

Required invariants:

- `manufacturer + sku + variant + source_revision` identify the product. A marketing name alone is insufficient.
- Raw SHA-256 identifies the exact downloaded bytes; normalized SHA-256 identifies a deterministic converted representation. Neither substitutes for a product revision.
- Source units, axis orientation, handedness, origin, and the full transform to the engine's millimetre frame are explicit. Never rely on an importer default.
- At least two independent dimension/centerline anchors verify scale and orientation; three are preferable for non-symmetric assets. Symmetric geometry must not be allowed to hide a mirrored transform.
- The declared role and authority control consumers. A renderer may consume `visual_reference`; a cut-list, structural check, plumbing check, or machining generator may not.
- A source digest change is quarantined for review. It never silently replaces the accepted asset or updates dimensions.

## Safe ingestion pipeline

1. **Resolve.** Start from an allowlisted official product page. Record manufacturer, exact SKU/variant, product page, specification, asset URL, retrieval timestamp, and terms URL.
2. **License gate.** Classify `redistribution` as `permitted`, `local_only`, `prohibited`, or `unknown`. `unknown` behaves as `prohibited` for Git and generated self-contained documents.
3. **Fetch to quarantine only when licensed.** Download into a user-local cache outside the repository only when the license gate permits local storage. Record response URL after redirects, content type, byte count, ETag/Last-Modified when available, and SHA-256. Enforce size, archive-depth, and file-count limits. Otherwise retain only the source URL and metadata.
4. **Parse offline.** Disable external references, scripts, macros, remote textures, and automatic network resolution. Reject executable content, path traversal, archive bombs, and a file whose magic/type conflicts with its declared format.
5. **Normalize deterministically.** Convert using a pinned tool/version and arguments. Retain the raw bytes immutably in the local content-addressed cache; never overwrite them in place.
6. **Calibrate units.** Read native units when reliable, then cross-check against manufacturer dimension anchors. If units are absent or conflicting, require a declared scale supported by at least two non-collinear anchors. Ambiguity is a blocking import error.
7. **Normalize coordinates.** Record handedness, up/front axes, origin, and a single explicit transform to project millimetres. Verify named connection/drain/mounting points, not just the bounding box.
8. **Sanity-check geometry.** Record bounding box, body/mesh count, triangle/face count, open/non-manifold state, duplicate bodies, missing references, and unexpected distant geometry. Apply render-complexity budgets.
9. **Attach an analytic adapter.** The adapter supplies separately sourced clearance, load, machining, installation, motion, and service envelopes. Imported surfaces may be compared with them but may not manufacture them implicitly.
10. **Publish metadata, not binaries.** A release may include source links, revision, digests, attribution, and independently rendered views when permitted. It must not embed a source asset whose redistribution grant is absent.
11. **Monitor without auto-upgrading.** Periodically recheck source and terms URLs. A changed file, spec revision, SKU state, or license creates an explicit review item and leaves the accepted release reproducible.

## Analytic truth versus visual reference

Use this decision table in every adapter:

| Question | Analytic engine contract | Imported asset |
|---|---|---|
| Does the sink fit the top and clear the drawers? | Basin/cutout/clamp/drain/service envelopes derived from current spec/template | Visual confirmation and secondary gross-clash probe |
| Where is the countertop cut? | Current, SKU-specific manufacturer template with pinned digest | Never inferred from body mesh or nominal bounding box |
| Does water land in the bowl and can the faucet be serviced? | Wall datum, spout/drain centerline, reach, rim gap, valve and handle envelopes | Visual trim and presentation |
| Can the upper drawer move around plumbing? | Explicit U-notch, tailpiece/trap/supply/service/motion envelopes | Visual interference clue only |
| Are runners selected and drilled correctly? | SKU-specific catalog facts, accepted configuration output, drilling/motion rules | Optional detailed hardware render |
| Is the vanity safely wall-mounted? | Connection model, load path, substrate/backing, spacing/edge/embedment, code/evaluation data | Fastener/rail visuals only |

When the visual asset and analytic adapter disagree, the system must report a blocking mismatch naming both sources and revisions. It must not rescale, shift, or “fix” the model silently.

## Recommended implementation order

1. **Metadata-only catalog references.** Implement `CatalogAssetRef` and release-manifest serialization with license/digest/unit/frame fields. This is useful immediately even with no geometry importer.
2. **Kohler fixture adapter.** Encode K-20000 basin, drain, cutout-template reference, clamp/service, and drawer-avoidance envelopes; encode K-T14414-4/K-410-K wall rough-in and operating/service envelopes. Produce a simple analytic display body until a local visual asset is deliberately selected.
3. **Blum configuration reference.** Add a `HardwareConfigurationRef` that records a metric Product Configurator input/output, exact parts list, and digest. Implement the wood U-shaped upper drawer + MOVENTO path analytically for the two 36 in bays.
4. **Wall-mount connection adapter.** Treat GRK RSS as a candidate SKU and implement the connection facts/calculation gates before choosing screw count/spacing. Use generated simple screw/rail geometry.
5. **Optional visual import.** Only after the first three adapters are tested, add a sandboxed importer/cache for one format with a real need. Prefer a geometry-preserving, well-supported format and a single deterministic conversion path; do not implement six importers because a vendor page lists six formats.
6. **Catalog-source expansion.** Add official manufacturer portals first, manufacturer-identified BIMobject/CADENAS entries second, and community libraries only as `visual_reference` with no validation authority.

This order gives most of the speed benefit—faster fixture selection, fewer retyped dimensions, reusable plumbing/drawer/mounting contracts, and better renders—without coupling build correctness to proprietary or unstable geometry files.

## Acceptance tests for a later ingestion increment

- A catalog reference missing SKU, source URL, raw digest, source units, transform, terms URL/date, license class, or asset role is rejected.
- `unknown`, `local_only`, and `prohibited` assets cannot be copied into Git-tracked output or a self-contained HTML document.
- A unitless or conflicting file cannot pass by bounding-box guess alone.
- A mirrored/upside-down asset with a plausible bounding box fails named-anchor checks.
- A digest change never alters an accepted release without an explicit review/update action.
- A visual asset cannot be read by cut-list, machining, structural, plumbing, or code validators.
- A current manufacturer cutout template can be used locally only when SKU/revision/digest match the selected fixture.
- The vanity compiles and validates using analytic adapters with the external asset cache empty.
- External assets are optional enhancement: removing the cache degrades rendering explicitly but never changes dimensions, findings, procurement, machining, sequence, or release truth.
