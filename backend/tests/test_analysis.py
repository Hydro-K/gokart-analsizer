"""Analysis: sector splits, energy estimate, theoretical best."""
import numpy as np
import pytest


def test_estimate_energy():
    from backend.analysis.deep_analysis import estimate_energy
    t = np.linspace(0, 60, 601)
    s = np.ones(601) * 15.0  # constant 15 m/s
    energy = estimate_energy(t, s)
    assert energy > 0
    assert energy < 5.0  # sanity: < 5 kWh for 1 lap


def test_driver_smoothness_score():
    from backend.analysis.deep_analysis import driver_smoothness_score
    t = np.linspace(0, 60, 601)
    smooth_s = np.ones(601) * 15.0
    jerky_s = 15.0 + 3.0 * np.random.RandomState(0).randn(601)
    smooth_score = driver_smoothness_score(t, smooth_s)
    jerky_score = driver_smoothness_score(t, jerky_s)
    assert smooth_score > jerky_score
    assert 0 <= smooth_score <= 100
    assert 0 <= jerky_score <= 100


def test_sector_splits():
    from backend.analysis.deep_analysis import sector_splits
    t = np.linspace(0, 60, 601)
    s = 15.0 + 5 * np.sin(t * 0.1)
    result = sector_splits(t, s, n_sectors=3)
    assert len(result) == 3
    total_time = sum(r.time_s for r in result)
    assert abs(total_time - 60.0) < 1.0


def test_theoretical_best_lap():
    from backend.analysis.deep_analysis import theoretical_best_lap
    from backend.analysis.lap_analyzer import LapData

    laps = []
    for i in range(5):
        t = np.linspace(0, 60 + i, 601)
        s = 15.0 + i * 0.5 * np.sin(t * 0.1)
        laps.append(LapData(
            lap_number=i+1, start_idx=0, end_idx=600,
            lap_time=60.0 + i, time=t, speed=s,
        ))

    best = theoretical_best_lap(laps)
    assert best < laps[0].lap_time  # theoretical best < best lap
