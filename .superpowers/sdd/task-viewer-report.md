# Task #20 — viewer: platform explode + interactive Panel E + fab-note tooltips

BASE: master @7e07f1d. Worktree `wt-viewer`, branch `sdd/viewer`. No `src/spec/`
touched (CL-1 runs there in parallel); no model/validation change. Surfaces
edited: `src/rendering/web_viewer/` (payload + new `explode.py` + viewer.js/css),
`src/core/process_graph.py` (fab-note single source), `scripts/consolidated_report.py`
(Panel E + fab-note delegate), one regenerated text-layer golden, one new test.

## Finding 1 — platform explode slider was a no-op
`platform.spec.yaml` authors zero `explode:` vectors (by design — see its own
note), so `explode_vectors()` returned `{}` and the slider froze the whole
platform and the composed site.

Fix: `build_viewer_payload` now falls back to DERIVED vectors when a detail
authors none (`web_viewer/explode.py::derive_explode_vectors`). A detail that
DOES author explode (rock anchor / tree / trolley) keeps its vectors verbatim —
their goldens are untouched.

**Derivation rule (deterministic — pure function of the compiled geometry + the
module's fixed constants; parts iterated in sorted-name order, every tie broken
by name):** for each part P, collect an OUTWARD unit normal from every declared
contact that involves P —
- a bearing `(P bears on Q along axis)`: the axis, signed away from Q
  (`sign(center(P)[axis] - center(Q)[axis])`); the reciprocal is added to Q;
- a through-hole where P is the fastener: the hole axis, signed away from the
  plates' mean center (the bolt backs out the way its head faces).
A contact whose two centers coincide on the axis (< EPS) contributes nothing (no
honest sign). Sum the normals into N. If |N| > EPS the direction is N
normalized — every summand points away from a neighbor, so the sum can never
point INTO the assembly. Otherwise fall back to the radial direction
`center(P) - center(assembly)` (also outward), or +Z if that is ~0. Magnitude =
`BASE_STEP + GAIN * |radial displacement projected onto the direction|`.

The contacts are read from the model post-compile via the PUBLIC
`SpecDetail.validation_spec()` (resolved `(a,b,axis,area)` bearings +
through-holes) — no `src/spec/` edit, no re-authoring. Centers are the local
bounding-box midpoint mapped through each part's `world_frame` (cheap; no
world-solid tessellation).

Honesty of the result, spot-checked on the real platform: deck boards lift +Z
off their joists; pier blocks drop −Z out from under their legs; bolts pull out
along their hole axis; an interior joist clamped between BOTH beams sees its two
opposed Y bearings CANCEL to ~0 net Y (it is not driven into a beam) and falls
back to radial. Every BUILT part gets a nonzero vector, so nothing freezes;
existing/context bodies are pinned at zero (see the fix round below).

## Finding 2 — Panel E was static PNGs
Added a scoped interactive 3D viewer over the pier-foundation hero still
(additive — the two stills remain), reusing the existing web_viewer machinery:
a `viewer-slot data-detail="pier_foundation"` + "Explore in 3D" button, a scoped
coarse web GLB of the three placed pier parts (leg + precast block + standoff
post base), and a payload that REUSES the platform part rows (item/dims/fab) so
there is no second tooltip derivation. Explode is overridden to a clean VERTICAL
pull-apart via `derive_vertical_stack_explode` (the three coaxial parts share an
X/Y footprint and differ only in height, so Z is the unambiguous axis): block
−95 mm, base 0, leg +95 mm. GLB nodes join the payload keys 1:1 (verified).

Text-layer golden change: exactly ONE line — the pier hero `<img>` now wrapped
in the viewer-slot + button. Everything else byte-identical. Additive-view-only,
regenerated and diff-reviewed.

## Finding 3 — tooltip built from pre-FAB component params (notch invisible)
Hovering a notched deck board read only "48 in" (the overall length) with no
mention of the trunk notch. Fixed at the SINGLE source: the fab-note derivation
moved to `ProcessRecord.fab_note()` (core); `consolidated_report._cutlist_fab_note`
now delegates to it, and `build_viewer_payload` reads the SAME method off each
part's `fabrication_record()`. The tooltip gains a `fab` field rendered beside
dims (viewer.js `.v-tip-fab`). The overall "48 in" stays; the notch note rides
with it. Applies to every viewer (zipline + caddy — both go through
`build_viewer_payload` and the shared viewer.js). Cut plan output is byte-
identical (same source), so the cut-list golden is unchanged.

Sample tooltip (platform `deck 3`, and the caddy top board): dims `... 48.0" ...`
+ fab `notch: 12" R full-cylinder clearance pocket around the trunk at the
tree-face end, cut through the thickness`.

## Fix round (gate RED → GREEN)
The binding gate found 2 red in `tests/test_scripts_spec_rewire.py`
(`test_vault_copy_off_by_default`, `test_vault_copy_flag_opts_in`): those tests
stub `load_details` to `{}` and run the REAL `main()`, and my Panel E wiring
hard-indexed `payloads["platform"]` → `KeyError` on that empty subset (retro R33
class — the real-main() path). Fix: `main()` computes
`has_pier = "platform" in details and "platform" in payloads` and builds the pier
payload/GLB only when true; a subset that omits the platform skips Panel E's
viewer entirely (stills-only fallback). `render_viewer_assets` and the slot guard
already tolerated the absence. Added `test_main_skips_panel_e_when_platform_absent`
(stubbed real-main path asserts no `KeyError` and the pier slug is omitted).

Also fixed a PRE-EXISTING VIEWER_FULL red I surfaced by running the full gate:
`test_other_details_join_glb_full[platform]` called `require_clean()` on the
deliberately-dirty platform (3 blocking foundation_capacity UNKNOWNs) — the
GLB↔payload join it checks needs only `validate()`, so it now validates instead
of gating. (Not in the default gate; only appears under `VIEWER_FULL=1`.)
**Pre-existing-test modification justified:** the platform is honestly blocked by
design post-FAB-3 (the foundation-capacity UNKNOWNs are meant to stay open), so
`require_clean()` can never pass for it; the GLB↔payload join is a DOCUMENTATION
surface, not a certified export — same rationale as `render_documentation`
(draw + surface the honest verdict, never refuse) — so validating without gating
is the correct verb, and cleanliness stays guarded by the coverage tests.

Review addition (review-viewer.md, non-blocking): PIN EXISTING/CONTEXT BODIES in
the derived path. The trunk and boulder were deriving a ~450 mm radial explode —
but a context body is the FIXED frame the built parts pull away from, so a tree
flying apart is nonsense. `derive_explode_vectors` now pins any part whose
component is existing/context (the SAME `_existing` predicate the tooltip EXISTING
badge uses) at (0,0,0). Authored vectors still win verbatim (they never reach the
derivation). Tests: trunk + boulder pinned in the platform payload, sofa arm
pinned in the caddy's, every BUILT part still moves. The beams-outvoted
mid-slider overlap stays the filed follow-up (not chased this round).

Base note: master advanced to e3088f3 (CL-1 merged in `src/spec/`); no overlap
with my surfaces (viewer + core fab-note + report script).

## Tests (controller gates)
`tests/test_viewer_explode_and_fab.py` (15 tests, ~4 s): fab-note tooltip
contract (notch present beside dims; plain part empty; tooltip == cut-plan single
source), explode-derivation determinism + every-part-moves + honest directions
(deck +Z / block −Z / clamped-joist ~0 net Y) + authored-wins-over-derivation,
existing/context bodies pinned (platform trunk + boulder, caddy sofa arm),
Panel E presence (viewer-slot + button; vertical stack; payload reuse; scripts
emitted only when present) + main() skips Panel E gracefully on a platform-less
subset. Scoped run GREEN: `test_scripts_spec_rewire.py` + this file = 98 passed;
`test_viewer_data.py` full sweep (`VIEWER_FULL=1`) = 3 passed;
`test_armchair_caddy_e2e.py` = 15 passed; `test_fab2_cutlist.py` +
`test_spec_presentation_loading.py` = 24 passed; text-layer golden passes.

## Docs rebuilt + previews re-staged
Both build documents regenerated; previews overwritten at their existing paths:
- `…/scratchpad/PREVIEW - Zipline Build Document.html`
- `…/scratchpad/PREVIEW - Armchair Caddy Build Document.html`
