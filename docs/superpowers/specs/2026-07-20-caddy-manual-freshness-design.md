# Caddy Manual Freshness and Progressive Assembly Design

Date: 2026-07-20

## Problem

The wooden diaper caddy was compiled from `codex/plumb-fast-lane`, a clean but
stale worktree that diverged from `main` before the birdhouse manual improvements
landed. Plumb preflight checked repository presence, dependencies, workflow
compatibility, and worktree cleanliness, but did not compare the selected commit
with `origin/main`. The old compiler then grouped thirteen fastening operations
and thirty-two picture callouts into one panel. Review incorrectly treated that
as advisory even though a builder could not follow the operation without
guessing.

## Selected design

Use two independent, fail-closed controls.

### Source-freshness control

The maintained Plumb plugin preflight will inspect the selected compiler
checkout against a configurable authoritative ref, defaulting to
`origin/main`. A release-capable preflight passes only when the authoritative
ref is present and is an ancestor of `HEAD`. A checkout that is behind or has
diverged fails with a required `source-freshness` check containing the selected
HEAD, authoritative ref, authoritative commit, and ahead/behind counts.

`PLUMB_ALLOW_STALE_SOURCE=1` is the sole escape hatch. It makes an intentional
historical or offline build explicit in the preflight evidence; it never occurs
silently. `PLUMB_BASE_REF` may select a different authoritative ref for a
deliberate branch-based workflow. Preflight remains non-mutating: it will not
fetch, merge, rebase, or alter a worktree.

This is preferred to a warning because warnings were already overlooked, and
preferred to automatic synchronization because Plumb worktrees may contain
concurrent user work.

### Instruction-scope control

The caddy specification will declare a progressive bench sequence with one
physical goal per stage:

1. Attach the near long wall to the bottom.
2. Attach the far long wall to the bottom.
3. Attach the left raised end to the bottom and both long walls.
4. Attach the right raised end to the bottom and both long walls.
5. Install the center divider against the bottom and both long walls.
6. Fit, glue, and screw the handle between the raised ends.
7. Hold the handle bonds through the selected adhesive label's full cure.
8. Inspect the completed caddy.

The generic process graph remains authoritative for dependencies. The stages
declare presentation and build strategy; they do not invent structural proof.
Identical screws appear as a hardware family with quantities and unnumbered
location targets, while numbered callouts identify only arriving workpieces.

The caddy release test will enforce the reader outcome rather than a global
panel count: eight panels, no fastening panel with more than three connection
instructions, no picture key containing fastener components, and no panel with
more than four numbered workpiece callouts. This product-specific gate prevents
the exact regression without imposing an unsuitable universal limit on all
projects.

## Review classification

The original crowded overview is reclassified as a product-blocking instruction
usability defect. Repair occurs in authoritative plugin/spec/test sources,
followed by one complete regeneration and a fresh review. Generated HTML is not
edited.

## Verification and delivery

The plugin change must demonstrate a red/green regression using a temporary Git
repository whose selected branch is behind its authoritative ref. The product
change must demonstrate a red/green release regression against the unstaged
caddy spec. Verification then includes the plugin suite, Plumb platform
integration tier, caddy inner and release gates, package hash closure, and a
visual inspection of every assembly panel. The approved package replaces the
existing JoelBrain artifact atomically, with updated review evidence and project
note. All modified repositories are committed and pushed where a remote exists.
