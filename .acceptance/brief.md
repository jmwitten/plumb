# 36-inch Open 2x2 Cube — Cold Acceptance

Create a complete Plumb package for a low-consequence, nonstructural, open 36 x 36 x 36 inch cube made only from nominal 2x2 lumber and glued square butt joints.

- Project slug: `2x2_cube_36_cold`.
- Closed architecture: four 36 inch vertical posts plus eight 33 inch between-post rails; nominal 2x2 actual section 1.5 x 1.5 inches; sixteen glued square butt joints; no other parts or uses.
- Component mapping: `edge_member` uses public `lumber(nominal, length)`.
- Connection mapping: `rail_to_post` uses public `glued()`.
- Local lumber axis convention: length +X, profile +Y and +Z.
- Posts rotate Y -90 degrees at: p00 [1.5,0,0], p10 [36,0,0], p01 [1.5,34.5,0], p11 [36,34.5,0].
- X rails at: [1.5,0,0], [1.5,0,34.5], [1.5,34.5,0], [1.5,34.5,34.5].
- Y rails rotate Z 90 degrees at: [1.5,1.5,0], [1.5,1.5,34.5], [36,1.5,0], [36,1.5,34.5].
- Use clear reader-facing names and unique labels.
- Front and rear rectangles are cured four-part subassemblies. Stage 1 bonds and cures the four side-rail front ends together. Stage 2 fits the cured rear rectangle and bonds and cures the rear ends together.
- Validate with explicit inch unit strings: envelope 0..36 inches in X, Y, and Z; post length 36 inches; rail length 33 inches; section 1.5 x 1.5 inches.
- Export and documents must state honest nonstructural limits.
- Complete package and review include the assembly manual and all images. Include named subassembly JOIN copy.
- Reader prose must not mention internal workflow or foreign context.
- Run only compiler-published `product_inner` and `product_release` gates.
- Delivery destination: `/Users/joelwitten/Code/JoelBrain/05_Attachments/Organized/2x2 Cube/2026-07-17/36-inch Package`.
