# Vendored: three.js r147 (0.147.0)

Vendored for the interactive build-document viewer (`detailgen.rendering.web_viewer`).
r147 is the last three.js release shipping non-module `examples/js` builds
(`GLTFLoader.js`, `OrbitControls.js` as plain scripts assigning to the global
`THREE`), which lets the viewer run with zero build tooling from `file://` and
under a strict Content-Security-Policy (no `<script type="module">`, no CDN).

## Files

| File | Acquired from | SHA-256 |
| --- | --- | --- |
| `three.min.js` | `https://unpkg.com/three@0.147.0/build/three.min.js` | `f34446bf875b5fb0dcd93819ffe1d9e182d46634ee855f5d904c6c4ac7cdbc95` |
| `GLTFLoader.js` | `https://unpkg.com/three@0.147.0/examples/js/loaders/GLTFLoader.js` | `b2edda923572c73e6b30b139756d182c87e2c34d022845c6e067a9a0a9544e01` |
| `OrbitControls.js` | `https://unpkg.com/three@0.147.0/examples/js/controls/OrbitControls.js` | `b4c6e53f98538535b11fd6655627d47fb5877b3ad972568bff0a7026c4b6d5c4` |
| `LICENSE.three-upstream` | `https://unpkg.com/three@0.147.0/LICENSE` | `fbf3943930dacbf56aabb8dc5d816440bd16aa6f4cc78ddbdf12106ee1807832` |

Acquisition date: 2026-07-06.

## License

MIT (Three.js Authors, 2010-2022). See `LICENSE.three-upstream` for the full
upstream text, embedded here unmodified as required by the license. The
`@license` MIT header is also present at the top of `three.min.js` itself.

## Why vendored (not CDN)

The build document is a single self-contained HTML file consumed from
`file://` (Obsidian vault) and potentially under a strict artifact CSP that
blocks all outbound network requests — a CDN `<script src>` would silently
fail in both contexts. Vendoring + inlining is the only option that works
everywhere the document is opened.
