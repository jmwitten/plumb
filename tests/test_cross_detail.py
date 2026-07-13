"""Cross-detail invariants (TREEFREE): the free-standing platform's beam run and
the tree-clearance detail, loaded into one process and compared on real built
geometry.

Two DECIDED-design relationships:

1. X coverage (BEAMFIX, retained): the platform's continuous beam must physically
   run far enough past the tree centerline to cover the tree detail's beam stub —
   the stub (its ``full_beam_len`` is presentation metadata, ``stub_of``) must fall
   entirely within the platform beam's X envelope, in shared trunk-centered world
   coordinates (both details put the live trunk at the same world X/Y origin).

2. Y growth-clearance (TREEFREE, new): the platform is FREE-STANDING — the beams
   simply CLEAR the trunk in Y by at least the growth allowance (they no longer
   fasten to it). Encoded here as the hand-written cross-detail instance, mirroring
   the in-model check the platform detail now declares against its own beam+trunk
   (``beam inner face clears trunk by growth gap``).

The SITE model makes (1) a single-node identity (``tree/beam_pY`` IS
``platform/beam_pY`` — see tests/test_site_model.py) and (2) an in-model dimension;
these pair-load tests stay while the standalone imperative details ship this phase,
and retire once the details become views.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from detailgen.core import IN
from detailgen.spec.compiler import compile_spec_file

DETAILS_DIR = Path(__file__).resolve().parents[1] / "details"


@pytest.fixture(scope="module")
def platform_detail():
    return compile_spec_file(DETAILS_DIR / "platform.spec.yaml")


@pytest.fixture(scope="module")
def tree_detail():
    return compile_spec_file(DETAILS_DIR / "tree_attachment.spec.yaml")


def test_platform_beam_covers_tree_stub_extent(platform_detail, tree_detail):
    """The platform's beam's actual built X-extent must cover the tree detail's
    beam stub's actual built X-extent, side for side."""
    eps = 1e-3 * IN
    for side in ("+Y", "-Y"):
        beam_bb = platform_detail[f"beam {side}"].world_solid().val().BoundingBox()
        stub_bb = tree_detail[f"beam {side}"].world_solid().val().BoundingBox()
        assert beam_bb.xmin <= stub_bb.xmin + eps, (side, beam_bb.xmin, stub_bb.xmin)
        assert beam_bb.xmax >= stub_bb.xmax - eps, (side, beam_bb.xmax, stub_bb.xmax)


def test_platform_beams_clear_trunk_by_growth_gap(platform_detail, tree_detail):
    """TREEFREE Y-growth-clearance: each platform beam's inner face must stand off
    the trunk (tree detail's trunk radius) by at least growth_gap. Measured on the
    real built solids: the beam inner face is |Y| = beam-inner-face, the trunk
    surface is at its radius, and (inner_face - radius) >= growth_gap each side."""
    P = platform_detail.params
    growth_gap = P.growth_gap * IN
    trunk_bb = tree_detail["trunk"].world_solid().val().BoundingBox()
    trunk_radius = trunk_bb.xlen / 2   # exact cylinder, centered on the origin
    for side, sign in (("+Y", 1), ("-Y", -1)):
        beam_bb = platform_detail[f"beam {side}"].world_solid().val().BoundingBox()
        inner_face = beam_bb.ymin if sign > 0 else -beam_bb.ymax
        clearance = inner_face - trunk_radius
        assert clearance >= growth_gap - 1e-3 * IN, (side, clearance, growth_gap)
