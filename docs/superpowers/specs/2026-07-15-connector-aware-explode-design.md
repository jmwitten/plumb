# Connector-Aware Exploded Viewer Design

**Date:** 2026-07-15
**Status:** Approved approach; pending written-spec review
**Decision owner:** Joel Witten

## Objective

Make the reusable interactive viewer expose small embedded connectors clearly when a reader uses the Explode control. The armchair caddy is the proving example, but the behavior must derive from general assembly, datum, and instruction metadata. It must not contain caddy-specific part names, component types, or key-placement rules.

The successful result is:

- the viewer initially shows the completed assembly rather than only its first fabrication cohort;
- moving Explode away from zero reveals every modeled part, even if the Assembly control is currently on an earlier step;
- an embedded connector with a declared physical axis pulls along that axis, so its motion reads as removal from the joint;
- returning Explode to zero restores the selected Assembly step's visibility;
- existing authored explode vectors and contact-derived directions retain precedence.

## Root Cause

The current caddy payload places the three panels on Assembly Panel 1 and the four corner keys on Panel 2. The viewer initializes the Assembly control to Panel 1, so every key node begins with `visible=false`.

`applyExplode()` only translates visible nodes. When a node is hidden, it resets that node to its original position and leaves it hidden. A reader who opens the viewer and drags Explode therefore cannot reveal any key.

There is a second, independent legibility problem. The explode-vector derivation understands bearing contacts and fastener through-holes. A glued dowel key has neither, so it falls back to a radial vector from the assembly centroid. The four caddy vectors are only about 37 percent aligned with their actual dowel axes. Even after a reader advances to Panel 2, the motion reads as generic fanning rather than a pin withdrawing from a bore.

## Considered Approaches

### Chosen: completed default, explode visibility override, and datum-axis fallback

Open instruction-aware viewers on the final Assembly panel. While Explode is greater than zero, show every scheduled part and apply its explode vector. When Explode returns to zero, restore the currently selected Assembly panel. Extend automatic vector derivation so a part with no contact-derived direction may use its existing named `axis` datum before falling back to a radial direction.

This fixes both causes with existing semantic inputs. `WoodDowel` already declares an `axis` datum whose local +Z follows the physical dowel axis. Headed fasteners also declare an axis, so the same platform rule can support other embedded connectors without knowing their classes.

### Rejected: final Assembly panel only

Opening on the completed assembly would make the keys present, and the existing radial explode would move them. It would not make their removal direction legible, and selecting an earlier Assembly panel would recreate the hidden-part failure. This addresses the default state but not the platform interaction.

### Rejected: full connection-graph disassembly solver

A solver could derive ordered disassembly paths for every part from the construction graph. That is substantially broader than this defect and would need rules for multi-axis joints, flexible parts, inaccessible paths, and competing connection constraints. The current platform already has contact directions and named axes; using them first is sufficient and testable.

## Viewer State Behavior

The Assembly and Explode controls remain independent inputs with one explicit visibility rule.

At Explode zero:

```text
visible(part) = part.first_panel <= selected_assembly_panel
```

At Explode greater than zero:

```text
visible(part) = true
```

This override is temporary. Explode does not mutate the selected Assembly value. Returning the slider to zero reapplies the selected panel and hides future parts again. If the reader changes the Assembly slider while exploded, the selected value and label update, but every part remains visible until Explode returns to zero.

When instruction-panel metadata exists, the Assembly slider initializes to its maximum value and the current-panel label identifies the final step. A viewer without instruction-panel metadata is unchanged.

The viewer hint will state that Explode reveals all parts. No automatic camera movement, color override, or tooltip pinning is added in this increment.

## Explode Direction Precedence

Automatic explode derivation uses this precedence for each built part:

1. A detail-level authored explode vector continues to win for the entire payload, unchanged from current behavior.
2. A non-cancelled direction derived from declared bearings or fastener through-holes wins for that part.
3. If no contact direction exists and the component declares an `axis` datum, transform that datum's local +Z direction into world space and use it as the candidate removal axis.
4. If neither semantic source yields a direction, use the existing radial direction from the assembly centroid.
5. If the radial direction also collapses, retain the existing +Z fallback.

For a datum-axis direction, choose the sign that points most outward from the assembly centroid. If the dot product with the radial vector is effectively zero, preserve the datum's authored positive direction as the deterministic tie-break. The existing magnitude formula remains unchanged; only the direction source changes.

Existing/context bodies remain pinned at zero. Contact-derived platform, tree, trolley, and rock-anchor vectors remain unchanged because their higher-precedence sources still win. The caddy's dowels have no contact normal, so their existing `axis` datums become the automatic fallback and pull them along their bores.

Malformed, zero-length, or non-finite axis directions fail soft to the radial fallback. Explode presentation must never make an otherwise valid model undeliverable.

## Data Flow

```text
DetailSpec + component datums + validation contacts
                    |
                    v
        derive_explode_vectors()
                    |
                    v
     viewer payload per-part vectors
                    |
       +------------+-------------+
       |                          |
instruction first_panel     Explode slider value
       |                          |
       +------------+-------------+
                    v
       visibility + translated pose
```

No new caddy configuration is introduced. The generated caddy documents receive the improvement by recompiling the same governed spec through the shared viewer path.

## Implementation Boundaries

The implementation is limited to:

- the shared explode derivation in `src/rendering/web_viewer/explode.py`;
- the shared interactive state logic in `src/rendering/web_viewer/viewer.js`;
- focused viewer and caddy regression tests;
- regenerated certified caddy documents and any tracked developer-facing report affected by deterministic output.

The caddy geometry, design-review selection, model fingerprint, assembly instructions, and delivery confirmation do not change. This is a presentation-platform correction, not a production-model redesign.

## Test Strategy

Tests must prove behavior rather than source-string presence alone.

1. A reusable explode-vector unit test places an axial connector without bearing or through-hole contacts and proves its vector is parallel to its world-space `axis` datum and points outward.
2. The caddy payload test proves all four corner-key vectors are axis-aligned while the sofa arm remains pinned and the panel vectors remain contact/radial derived.
3. Existing tests continue to prove authored vectors win, existing bodies remain fixed, and platform contact-derived directions remain unchanged.
4. Viewer-state tests prove instruction-aware viewers initialize to the final panel, Explode greater than zero reveals parts scheduled for later panels, and returning to zero restores the selected Assembly panel.
5. A no-instruction viewer test proves the existing visibility behavior is unchanged.
6. Regenerated caddy documents are checked for four keys in the payload, axis-aligned nonzero vectors, and no preview marking in the certified outputs.
7. Targeted viewer/caddy tests and the full repository suite run before commit and push.

## Non-Goals

- No caddy-specific explode vectors or part-name checks.
- No new key geometry, material, color, or size.
- No change to the construction or customer instructions.
- No camera animation or automatic zoom-to-connector behavior.
- No full disassembly-path or collision-free motion solver.
- No change to authored explode blocks.
- No merge to `main` as part of this increment.
