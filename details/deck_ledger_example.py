"""EXAMPLE DETAIL — deck ledger connection.

This is the annotated walkthrough of the whole pipeline; new details should
copy this file's shape. It models a classic detail: a pressure-treated 2x8
ledger lagged to the house rim board, carrying one deck joist in a face-mount
hanger.

Run it from the project root:

    python details/deck_ledger_example.py

It will:
1. build components (parameters only — geometry is lazy),
2. place them in a DetailAssembly (world frame: Z up, ledger face at Y=0),
3. validate (pairwise interference sweep + bearing contacts + a dimension
   check), refusing to export if anything fails,
4. export outputs/deck_ledger_example.{step,stl} and PNG previews.

World frame used here
---------------------
- Z is up. The ledger's outside face is the Y=0 plane.
- House side is -Y (rim board behind the ledger), deck side is +Y
  (joist runs away from the house).
- X runs along the ledger.
"""

from detailgen.core import IN, FT
from detailgen.components import Lumber, LagScrew, Washer, JoistHanger
from detailgen.assemblies import DetailAssembly
from detailgen.validation import validate_assembly, check_dimension
from detailgen.rendering import export_all


def build() -> DetailAssembly:
    # -- 1. components: parameters only, local frames documented per class ----
    ledger = Lumber("2x8", length=2 * FT, name="ledger", treated=True)
    rim = Lumber("2x10", length=2 * FT, name="house rim")
    joist = Lumber("2x8", length=2 * FT, name="joist", treated=True)

    # Hanger wraps the joist's actual dimensions.
    hanger = JoistHanger(joist.thickness, joist.depth, name="joist hanger")

    # Two 1/2" x 3" lags: through 1.5" ledger, 1.5" embedment into the rim.
    lags = [LagScrew(0.5 * IN, 3 * IN, name=f"lag {i + 1}") for i in range(2)]
    washers = [Washer(9 / 16 * IN, name=f"washer {i + 1}") for i in range(2)]

    # -- 2. placement: the assembly owns ALL positioning ----------------------
    detail = DetailAssembly("deck ledger example")

    # Lumber's local frame is length +X, thickness +Y, depth +Z — so a member
    # is already "on edge"; ledger just shifts back so its face is at Y=0.
    detail.add(ledger, at=(0, -ledger.thickness, 0))

    # Rim board directly behind, tops flush with the ledger.
    detail.add(
        rim,
        at=(0, -ledger.thickness - rim.thickness, ledger.depth - rim.depth),
    )

    # Joist runs +Y (away from the house). Rotating +90 about Z maps the
    # member's length axis (+X) onto +Y. It starts one hanger-gauge off the
    # ledger face, where the hanger's back plane sits.
    joist_center_x = 12 * IN
    detail.add(
        joist,
        at=(joist_center_x + joist.thickness / 2, hanger.GAUGE, 0),
        rotate=[("Z", 90)],
    )

    # Hanger: local frame is back-plane-at-X=0, joist along +X; same +90 spin
    # puts its stirrup along +Y. Placed at the joist centerline.
    detail.add(hanger, at=(joist_center_x, hanger.GAUGE, 0), rotate=[("Z", 90)])

    # Lags: fastener local frame is head-at-origin, shank down -Z. Rotating
    # -90 about X points the shank in -Y (into the house). Each head bears on
    # a washer, so the head plane sits one washer-thickness off the face.
    for i, (x, z) in enumerate([(4 * IN, 65), (18 * IN, 120)]):
        detail.add(washers[i], at=(x, 0, z), rotate=[("X", -90)])
        detail.add(lags[i], at=(x, washers[i].thickness, z), rotate=[("X", -90)])

    return detail


def main() -> None:
    detail = build()

    # -- 3. validate: broken geometry must never reach outputs/ ---------------
    report = validate_assembly(
        detail,
        # Lags are *supposed* to penetrate the wood — allowlist those pairs.
        expected_overlaps={
            ("lag 1", "ledger"), ("lag 1", "house rim"),
            ("lag 2", "ledger"), ("lag 2", "house rim"),
        },
        # Parts that must bear on each other.
        contacts=[
            ("ledger", "house rim"),
            ("joist hanger", "ledger"),
            ("joist", "joist hanger"),
        ],
    )

    # Design-intent dimension check: joist top flush with ledger top.
    by_name = {p.name: p for p in detail.parts}
    report.add(check_dimension(
        "joist top flush with ledger top",
        actual=by_name["joist"].world_solid().val().BoundingBox().zmax,
        expected=by_name["ledger"].world_solid().val().BoundingBox().zmax,
        part=[by_name["joist"].name, by_name["ledger"].name],
    ))

    print(report)
    report.require_clean()

    # -- 4. export -------------------------------------------------------------
    print("\nBOM:")
    for row in detail.bom():
        print(f"  {row['name']:<14} {row['type']:<12} {row['material']}")

    # The fasteners and hanger face +Y (deck side), so render from there.
    written = export_all(detail, views=("iso_back", "back"))
    print("\nWrote:")
    for path in written:
        print(f"  {path}")


if __name__ == "__main__":
    main()
