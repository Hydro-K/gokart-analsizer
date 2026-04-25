"""GPS reconstruction: synthetic lat/lon → local_xy in 0-1000 range."""
import numpy as np
import pytest


def test_reconstruct_track_basic():
    from backend.analysis.gps_reconstruction import reconstruct_track

    # Circular track
    angles = np.linspace(0, 2 * np.pi, 200)
    lat = 51.5 + 0.005 * np.sin(angles)
    lon = -0.1 + 0.008 * np.cos(angles)

    tm = reconstruct_track(lat, lon, smooth_sigma=3.0)

    assert tm.local_xy is not None
    assert len(tm.local_xy) >= 10

    xs = [p[0] for p in tm.local_xy]
    ys = [p[1] for p in tm.local_xy]

    assert min(xs) >= 0
    assert max(xs) <= 1000
    assert min(ys) >= 0
    assert max(ys) <= 1000
    assert tm.length_m > 100  # at least 100m track


def test_reconstruct_needs_10_points():
    from backend.analysis.gps_reconstruction import reconstruct_track
    with pytest.raises(ValueError, match="10"):
        reconstruct_track(np.array([51.5] * 5), np.array([-0.1] * 5))


def test_haversine_known_distance():
    from backend.analysis.gps_reconstruction import _haversine_m
    # London to Paris approx 340 km
    d = _haversine_m(51.5, -0.12, 48.85, 2.35)
    assert 330_000 < d < 350_000
