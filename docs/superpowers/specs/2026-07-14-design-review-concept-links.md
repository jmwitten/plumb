# Design-Review Concept Example Links

## Goal

Make the existing precedent sources visibly accessible from each concept in the
developer design report. A reviewer should not have to infer that source titles
in the earlier provenance table are clickable or manually match feature
reference ids back to that table.

## Approaches considered

1. **Derive concept links from feature precedent references — selected.** Build
   each concept's example list from the union of its features'
   `precedent_refs`, preserving source order and removing duplicates. This keeps
   URLs, titles, publishers, and access dates single-sourced in `precedents`.
2. Add a separate `examples` list to every concept. This would allow editorial
   curation but duplicate provenance and permit links to drift from the feature
   evidence.
3. Embed remote thumbnails or screenshots. This would be visually richer but
   adds copyright, availability, layout, and caching concerns that are not
   necessary to answer the reviewer's immediate question.

## Report behavior

Each concept gains an **Examples** subsection immediately after its summary and
before its architecture signature.

- Every unique referenced precedent renders as an explicit external link using
  its human title, followed by publisher and source kind.
- Link order follows the canonical `precedents` order, not incidental feature
  order, so report output remains deterministic.
- A concept with no precedent-backed features renders **No direct precedent
  identified; review the novelty/deviation basis below.** It must not silently
  omit the subsection or invent a related example.
- A concept with both supported and unsupported features shows its real example
  links; the existing feature inventory and deviation section continue to expose
  which specific feature lacks support.
- Links open normally in the current browser context. The report does not embed
  third-party content, images, tracking scripts, or remote styles.

## Architecture and data flow

`render_design_review_html()` builds an id-to-`Precedent` map from the loaded
document, collects each concept's referenced ids, then renders only matching
sources. Validation already rejects unknown precedent references, so the report
does not need a second reference-validity policy. Escaping continues through the
existing `_e()` helper.

No schema, loader, fingerprint, gate, or caddy-review YAML changes are required.
The generated report changes presentation only; its selection fingerprint and
approval state remain unchanged.

## Verification

- Generic report tests assert a concept-level example heading, linked source
  title, escaped URL, publisher, and deterministic output.
- A report test mutates a concept to remove all feature precedent references and
  asserts the explicit no-direct-precedent message.
- The caddy test asserts the reinforced-miter section contains links to the Love
  & Renovations and Woodworker's Journal examples, while the current rail
  feature remains visibly represented by its deviation rather than a fabricated
  precedent.
- Regenerate `outputs/design-reviews/armchair_caddy.html`, visually inspect it,
  and rerun the focused report and caddy suites before committing the
  implementation.

## Scope boundary

This change improves the developer review report only. It does not alter the
customer build manual, source research, selected concept, caddy geometry, or any
lifecycle approval. The reinforced-miter production redesign remains a separate
governed increment.
