"""Escape-hatch **cross-check** callables referenced by specs (task 4B-2).

A ``cross_check:`` block names a dotted path here (``f(detail) -> dict``),
resolved and called exactly like a component's ``imperative`` hook — an authored
escape from the declarative language for an INDEPENDENT constraint solve that
verifies (never replaces) the computed placement. It is logged loudly in the
derivation report. These are deliberately NOT a DSL: the constraint-solver pass
is arbitrary geometry code, so it stays Python, reached only through the marked
reference.

Each callable takes the compiled :class:`~detailgen.spec.compiler.SpecDetail`
(``detail["part name"]`` resolves a placed part; ``detail.params.<field>`` reads
a param), so the same solve runs identically whether authored imperatively or
compiled from a spec.
"""

from __future__ import annotations

from ..core import IN


def rock_anchor_solver(detail) -> dict:
    """Independent constraint solve on the +Y rod hardware stack, compared to the
    canonical computed placement (the rock anchor's ``cross_check``). Never
    mutates the model; the axial nut position is an intended free DOF, so only
    the RADIAL (X, Y) position is compared."""
    import cadquery as cq

    P = detail.params
    ROD_EMBED, ROD_Y = P.rod_embed, P.rod_sp / 2
    LEV_NUT_Z, NUT_H = P.lev_nut_z, P.nut_h
    out = {"canonical": "computed placement", "solver": "skipped",
           "max_deviation_in": None, "agrees": None}
    try:
        asm = cq.Assembly()
        # cq constraint queries ("tag@kind@sel") can't contain spaces, so the
        # verification assembly uses underscore aliases for the same solids.
        chain = {"rod": (detail["rod 0"], -ROD_EMBED),
                 "levnut": (detail["leveling nut 0"], LEV_NUT_Z),
                 "washer": (detail["fender washer lo 0"], LEV_NUT_Z + NUT_H)}
        for alias, (part, z) in chain.items():
            asm.add(part.world_solid(), name=alias,
                    loc=cq.Location((0, ROD_Y * IN, z * IN)))
        asm.constrain("rod", "Fixed")
        asm.constrain("rod@faces@%CYLINDER", "levnut@faces@%CYLINDER", "Axis", param=0)
        asm.constrain("levnut@faces@>Z", "washer@faces@<Z", "Plane")
        asm.solve()
        placed = dict(asm.traverse())
        # Compare RADIAL (X,Y) position only. The nut's axial (Z) position is a
        # genuine free degree of freedom — a leveling nut is threaded to a set
        # height, which is a design choice, not a mating constraint. The solver
        # cannot (and should not) reproduce it; this is precisely why computed
        # placement is canonical.
        radial = 0.0
        for alias, (part, z) in chain.items():
            gx, gy, _ = placed[alias].loc.toTuple()[0]
            radial = max(radial, abs(gx - 0), abs(gy - ROD_Y * IN))
        out.update(solver="ran", max_radial_deviation_in=round(radial / IN, 6),
                   agrees=bool(radial / IN <= 2e-3),
                   note="axial nut position is an intended free DOF (leveling); "
                        "computed placement is authoritative")
    except Exception as e:
        out.update(solver=f"error: {type(e).__name__}: {e}", agrees=False)
    return out
