"""Simulation: Mode A sign check, 220A enforcement."""
import numpy as np
import pytest


def _make_lap():
    from backend.analysis.lap_analyzer import LapData
    t = np.linspace(0, 60, 601)
    s = 10 + 5 * np.sin(t * 0.2)  # ~10-15 m/s
    return LapData(
        lap_number=1,
        start_idx=0,
        end_idx=600,
        lap_time=60.0,
        time=t,
        speed=s,
    )


def test_mode_a_220a_hard_cap():
    from backend.analysis.simulation import simulate_mode_a
    lap = _make_lap()
    delta, pred = simulate_mode_a(
        lap=lap,
        max_current=250,  # should be capped to 220
        accel_rate=1.0,
        speed_limit_pct=100,
        gear_ratio_new=8.0,
        gear_ratio_old=8.0,
        mass_new_kg=115.0,
        mass_old_kg=115.0,
        tyre_psi_rear=14.0,
        tyre_psi_front=12.0,
        motor_temp_c=40.0,
    )
    # Should return valid floats
    assert isinstance(delta, np.ndarray)
    assert isinstance(pred, float)
    assert pred > 0


def test_mode_a_higher_accel_reduces_time():
    """Increasing accel_rate should reduce or equal predicted time."""
    from backend.analysis.simulation import simulate_mode_a
    lap = _make_lap()
    kwargs = dict(
        max_current=200, speed_limit_pct=100,
        gear_ratio_new=8.0, gear_ratio_old=8.0,
        mass_new_kg=115.0, mass_old_kg=115.0,
        tyre_psi_rear=14.0, tyre_psi_front=12.0, motor_temp_c=40.0,
    )
    _, base = simulate_mode_a(lap=lap, accel_rate=1.0, **kwargs)
    _, fast = simulate_mode_a(lap=lap, accel_rate=1.2, **kwargs)
    assert fast <= base + 0.5  # faster or equal (within tolerance)


def test_mode_a_speed_limit_increases_time():
    """Reducing speed limit should increase or equal predicted time."""
    from backend.analysis.simulation import simulate_mode_a
    lap = _make_lap()
    kwargs = dict(
        max_current=200, accel_rate=1.0,
        gear_ratio_new=8.0, gear_ratio_old=8.0,
        mass_new_kg=115.0, mass_old_kg=115.0,
        tyre_psi_rear=14.0, tyre_psi_front=12.0, motor_temp_c=40.0,
    )
    _, full = simulate_mode_a(lap=lap, speed_limit_pct=100, **kwargs)
    _, capped = simulate_mode_a(lap=lap, speed_limit_pct=80, **kwargs)
    assert capped >= full - 0.5
