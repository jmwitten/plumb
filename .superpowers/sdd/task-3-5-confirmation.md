# Tasks 3–5 Consolidated-Fix Confirmation

Commit reviewed: `fa4d474` (`2b8626c..fa4d474`)

## Result

- **Confirmation: FAIL**
- **Critical findings remaining: 0**
- **Important findings remaining: 1**

The committed fix closes the prior visible toe/shim defect, compact-banner
layout defect, standalone link-closure regression, front annotation collision,
mobile/print drawing affordances, image-URI injection boundary, and fabrication
ownership wording. The regenerated DB40 plan shows four individual toe members;
the section shows only the front and rear material intervals with a void between
and no invented shim.

## Important

### I1. Placed-geometry invariants remain incomplete on unchecked axes

`installation_drawing_facts()` now validates the cabinet frame and the toe frame
in plan, but it still does not validate several placed dimensions that the
drawings replace with expected-looking declaration geometry:

- Toe parts are checked in X/Y and for nominal height, but their global Z
  origins are never checked. Moving all four toe parts `+100 mm` in Z is
  accepted, while the section still draws them bearing at local Z `0`.
- The anchor strip is checked in X and for size/orientation, but not for its
  placed Y or Z. Moving the strip and both anchors `-10 mm` in Y and `+100 mm`
  in Z is accepted. The returned strip then spans local Z
  `855.65..957.25 mm`, beyond the `876.30 mm` cabinet, and returned embedment
  falls to `21.75 mm`; the projection still returns drawing facts instead of
  rejecting the incoherent cabinet-local placement.
- Studs are checked only by id and X center. Moving `stud_32` `+500 mm` in Y,
  `+100 mm` in Z, and increasing its modeled depth by `50 mm` is accepted. The
  plan/section nevertheless draw the declaration-derived stud position and
  `88.90 mm` depth, not the placed part.

This leaves the core Task 3 promise incomplete: contradictory toe/strip/stud
geometry can still produce a plausible installation drawing. The added negative
tests cover toe X/Y closure, cabinet-side X, strip X/length, duplicate anchors,
and screw params, but not these remaining coordinate-frame axes.

**Required correction:** validate each toe member's base Z; validate the anchor
strip's expected Y/Z in the cabinet/wall frame; and validate each placed stud's
full origin, rotation, and dimensions against the surveyed wall facts. Add one
negative regression for each condition before confirming the fix.

## Verification evidence

No full suite was run. The focused confirmation command completed with:

```text
15 passed, 20 deselected in 9.55s
```

Those probes covered the prior C1/I1/I2/I3/I4 and M1/M2 regressions. Additional
read-only mutation probes reproduced the one remaining Important finding above.

The final landing markup also confirmed:

- 120 visible header words and one retained full policy notice;
- no full policy notice in fabrication or audit;
- all local landing hrefs resolve;
- three full-resolution drawing links, mobile horizontal scrolling, and print
  page breaks;
- viewer/GLB markers only in the landing document.

Direct browser opening of the local `file://` artifact was blocked by browser
policy, so the fix report's recorded desktop/mobile measurements were not
independently rerun. The regenerated PNGs were inspected directly.
