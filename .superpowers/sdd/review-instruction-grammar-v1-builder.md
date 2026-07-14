# No-context builder review — DB40 consumer manual (instruction-grammar v1)

Reviewer: fresh-context builder agent, 2026-07-14, against the printed
11-page manual, the West Elm 2x2 bed frame manual (PDF), and knowledge of
Blum/IKEA drawer-cabinet manuals (the Blum MOVENTO PDF exceeded the
reviewer's fetch limit; stated explicitly).

**Overall verdict: PASS — conditional.** "A careful builder can finish it:
captions are accurate, sequence is disciplined, hardware accounting is
exact. But it passes on words, not pictures." Does not yet meet the West
Elm/Blum illustration standard.

## The five acceptance questions

1. **Identify parts and hardware before each step?** MIXED — hardware PASS
   (letter chips reconcile exactly: A 18 = 6+4×3; B 50 = 8+5+13+8×3;
   E 42 = 10×3+4×3; etc. — "better bookkeeping than most big-box
   manuals"); parts FAIL-lean (no per-part picture key; identification
   rides on the fabrication labels per the kit gate).
2. **Understand the operation primarily from the illustration?** FAIL —
   single-state scenes; no exploded views/motion arrows; steps 8–10 and
   11/12/14 read visually similar; captions carry the load.
3. **Orientation/quantity/sequence/tightening unambiguous?** MIXED —
   sequence PASS (1–14 + full-page STOP); quantity PASS-ish; tightening
   clear in words only; handed-part orientation depends on physical labels.
4. **Any unnecessary prose?** MIXED — step captions all necessary; the
   cover meta-line and the signed record read as commissioning overhead to
   a DIY builder. (Both are required surfaces for this stud-anchored
   built-in; retained by design.)
5. **Lost an action-changing fact?** PASS — groove warning, STOP page,
   countertop hold, "never glue alone", "into — not through —", "never
   substitute drywall anchors" all survived. Caveat: the drywall-anchor
   line was body text, not a ⚠ warning.

Also: STOP page unmissable; layout clean, no collisions; grayscale fine for
text, dark renders hide internal features (grooves/notches).

## Findings and disposition

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | Critical | Illustrations don't convey the action (no exploded/arrow/detail views; late steps visually similar) | **Accepted as v1 scope limit** — motion/exploded states are not modeled facts; the spec forbids inventing directions and this branch may not change geometry. Documented as the headline +presentation follow-up (typed operation diagrams exist on the technical surface and can be projected into frames next). |
| 2 | Critical | Handed/mirror parts recoverable only via physical labels | **Mitigated** — the prepared-kit gate now states the label dependency explicitly and instructs to stop and re-label before assembling any unlabeled part. Full fix (per-part orientation views) is future work. |
| 3 | Critical | "Never substitute drywall anchors" not marked as a warning | **Fixed** — moved to the anchor frame's ⚠ warning box ("Never substitute drywall anchors or rely on gypsum board; the screws must reach the verified studs."). |
| 4 | Important | Parts not picture-keyed | Accepted for v1 (per-frame picture keys name focus parts; per-part thumbnails are follow-up). |
| 5 | Important | Stabilizer sync components keyed to nothing | **Fixed** — steps 6/7 captions now attribute pinion housings/racks/rod/adapters/clips to stabilizer set letter (C). |
| 6 | Important | Adjustment step is prose, should be a diagram | Accepted for v1 (adjustment directions are manufacturer-controlled; a typed diagram projection is follow-up). |
| 7 | Important | No visual tightening cue | Accepted for v1 (tightening states are typed text; halfway/final glyphs are follow-up). |
| 8 | Minor | No page numbers | **Fixed** — every sheet now carries "Page N of M". |
| 9 | Minor | Repeat-badge scope not visually bracketed | Accepted (badge reads "3× per drawer" adjacent to the chips). |
| 10 | Minor | Cover meta-line + signed record are overhead for DIY | Retained by design (release/hold contract for a stud-anchored built-in). |
| 11 | Minor | Tools listed as text without icons | Accepted for v1. |

After fixes: regenerated manual is 11 pages / 640 visible instructional
words; all structural and mutation tests green.
