# Generic Package Output Improvements

**Date:** 2026-07-16
**Scope:** Reusable Plumb package generation; no project-specific renderer or 2x4-specific platform rule.

## Goal

Make the generic package easier to open and use by preserving complete package-relative image paths, putting the existing interactive exploded viewer at the top of the assembly manual, resolving selected screws from a small provenance-backed catalog, and omitting the low-level installation HTML from new default packages without deleting that capability.

## Decisions

### Complete package-relative paths

HTML image references will use paths relative to the document root, such as `views/iso.png`, rather than discarding directories and emitting `iso.png`. Absolute workstation paths are rejected as a delivery format because they break when the package is moved. The projection contract will preserve the supplied document-relative path; the package builder is responsible for deriving it from the package root.

### Reuse the existing viewer

The assembly manual will reuse `build_viewer_payload`, the exported GLB, and the vendored offline viewer assets. A screen-only “Explore the build in 3D” section will appear after the manual header and safety notice, before the parts overview and instruction panels. The initial image uses the complete package-relative `views/iso.png` path. The GLB remains embedded as deterministic gzip/base64 so activation works from a local `file:` URL. Print output hides the interactive section.

### Small screw catalog

A JSON catalog snapshot will contain three Home Depot structural-screw listings. Each record carries a stable internal reference, normalized reader size, modeled diameter and length, head/drive terminology, retailer identifiers, source URL, and retrieval date. The user-facing documents do not need to name the manufacturer; provenance remains available through the BOM source and catalog record.

`StructuralScrew` will support either:

- explicit `diameter` and `length` (backward compatible), or
- one `catalog_ref` (new preferred procurement-backed path).

Supplying both fails loudly. Catalog resolution sets geometry, reader terminology, grouping identity, and purchase source from the same record. The manual prefers a component's catalog display size over recomputing an unusual fraction from modeled diameter.

The catalog is a proof of concept, not an engineering approval database. Retailer listings establish product terminology and procurement provenance; they do not establish capacity, code compliance, or installation requirements.

### Assembly-only default document surface

The installation projection and renderer remain available for an explicit future caller. The generic package writer makes installation optional, and the default builder stops requesting it. New packages therefore contain technical, fabrication, and assembly HTML but no `installation.html`. Existing delivered packages are not modified or deleted.

## Alternatives considered

- **Absolute host image paths:** fixes one machine only and makes archives non-portable; rejected.
- **A second assembly-specific viewer:** duplicates a proven viewer and creates drift; rejected.
- **Copy catalog terms into each project spec:** leaves two sources for the same fastener; rejected.
- **Delete the installation renderer:** removes a potentially useful explicit audit surface and violates the request to retain it; rejected.

## Acceptance checks

1. `technical.html` references `views/<name>.png`, and every referenced local file exists.
2. `assembly.html` contains the existing viewer payload, Explode control, and embedded GLB before the first instruction panel.
3. A spec can instantiate `structural_screw` with only `catalog_ref`; geometry, BOM wording, source, and manual size come from the catalog.
4. A default new package does not contain or manifest `installation.html`; the standalone installation renderer still passes its unit contract.
5. The prior July 16 package remains unchanged, while a newly generated comparison package demonstrates all four differences.
