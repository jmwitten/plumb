"""Frame value-type math: composition, inverse, point/direction mapping,
orthonormality, and reproduction of the legacy at/rotate placement transform.
"""

import math

import pytest

from detailgen.core.frame import Frame


def approx_tuple(a, b, tol=1e-9):
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert x == pytest.approx(y, abs=tol), (a, b)


# -- construction & basic mapping -------------------------------------------

def test_identity_maps_points_unchanged():
    f = Frame.identity()
    approx_tuple(f.transform_point((3, -4, 7)), (3, -4, 7))
    approx_tuple(f.origin, (0, 0, 0))
    approx_tuple(f.x_axis, (1, 0, 0))
    approx_tuple(f.y_axis, (0, 1, 0))
    approx_tuple(f.z_axis, (0, 0, 1))


def test_translation_moves_origin_only():
    f = Frame.translation((10, 20, 30))
    approx_tuple(f.origin, (10, 20, 30))
    approx_tuple(f.x_axis, (1, 0, 0))          # orientation unchanged
    approx_tuple(f.transform_point((1, 1, 1)), (11, 21, 31))


def test_rotation_z_90_maps_x_to_y():
    f = Frame.rotation(90, axis=(0, 0, 1))
    approx_tuple(f.transform_point((1, 0, 0)), (0, 1, 0))
    approx_tuple(f.z_axis, (0, 0, 1))
    approx_tuple(f.x_axis, (0, 1, 0))


def test_rotation_about_offset_axis():
    # 180 deg about the line x=0,z arbitrary through (0,0,0) on Z, then a point
    f = Frame.rotation(180, axis=(0, 0, 1), origin=(1, 0, 0))
    # point (2,0,0) reflects through the axis at x=1 -> (0,0,0)
    approx_tuple(f.transform_point((2, 0, 0)), (0, 0, 0))


# -- direction vs point ------------------------------------------------------

def test_transform_direction_ignores_translation():
    f = Frame.translation((100, 0, 0)).compose(Frame.rotation(90, axis=(0, 0, 1)))
    approx_tuple(f.transform_direction((1, 0, 0)), (0, 1, 0))   # pure rotation
    approx_tuple(f.transform_point((1, 0, 0)), (100, 1, 0))     # rotation + shift


# -- compose / inverse -------------------------------------------------------

def test_compose_then_inverse_is_identity():
    f = Frame.translation((5, -3, 8)).compose(
        Frame.rotation(37, axis=(1, 2, 3))).compose(
        Frame.rotation(-19, axis=(0, 1, 0)))
    ident = f.compose(f.inverse())
    for p in [(1, 0, 0), (0, 1, 0), (0, 0, 1), (2, -5, 9)]:
        approx_tuple(ident.transform_point(p), p, tol=1e-8)


def test_compose_applies_right_frame_first():
    # rotate 90 about Z, THEN translate +X by 10 (translate is the outer/left op)
    f = Frame.translation((10, 0, 0)).compose(Frame.rotation(90, axis=(0, 0, 1)))
    approx_tuple(f.transform_point((1, 0, 0)), (10, 1, 0))


# -- from_origin_axes / orthonormality --------------------------------------

def test_from_origin_axes_builds_orthonormal_frame():
    f = Frame.from_origin_axes(origin=(1, 2, 3), x_dir=(0, 0, 1), z_dir=(1, 0, 0))
    approx_tuple(f.origin, (1, 2, 3))
    approx_tuple(f.x_axis, (0, 0, 1))
    approx_tuple(f.z_axis, (1, 0, 0))
    approx_tuple(f.y_axis, (0, -1, 0))   # right-handed: y = z cross x
    assert f.is_orthonormal()


def test_from_origin_axes_orthonormalizes_skew_x():
    # x_dir not perpendicular to z_dir -> projected & normalized, frame stays valid
    f = Frame.from_origin_axes(origin=(0, 0, 0), x_dir=(1, 0, 0.3), z_dir=(0, 0, 1))
    assert f.is_orthonormal()
    approx_tuple(f.z_axis, (0, 0, 1))
    # x projected into the z=0 plane -> (1,0,0)
    approx_tuple(f.x_axis, (1, 0, 0))


def test_all_constructed_frames_are_orthonormal():
    frames = [
        Frame.identity(),
        Frame.translation((3, 4, 5)),
        Frame.rotation(42, axis=(1, 1, 1)),
        Frame.from_origin_axes((0, 0, 0), (1, 0, 0), (0, 1, 0)),
    ]
    for f in frames:
        assert f.is_orthonormal(), f


# -- legacy at/rotate reproduction ------------------------------------------

def test_legacy_frame_matches_hand_transform():
    # local +X -> world +Z (rotate Y -90), then translate; a known rock-anchor spin
    f = Frame.from_at_rotate(at=(2, -0.75, 0.5), rotate=[("Y", -90)])
    # local +X maps to world +Z
    approx_tuple(f.transform_direction((1, 0, 0)), (0, 0, 1))
    # local origin lands at `at`
    approx_tuple(f.transform_point((0, 0, 0)), (2, -0.75, 0.5))


def test_legacy_frame_multi_rotation_order():
    # rotate list applies in order about global axes, then translate
    f = Frame.from_at_rotate(at=(0, 0, 0), rotate=[("X", 90), ("Z", 90)])
    # apply R_X(90) first: (0,1,0)->(0,0,1); then R_Z(90): (0,0,1)->(0,0,1)
    approx_tuple(f.transform_direction((0, 1, 0)), (0, 0, 1))
    # (1,0,0): R_X keeps it, R_Z sends it to (0,1,0)
    approx_tuple(f.transform_direction((1, 0, 0)), (0, 1, 0))
