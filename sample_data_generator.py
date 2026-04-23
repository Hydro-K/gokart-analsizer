"""
Generates a synthetic AiM Solo 2-style CSV for testing the app.
Simulates a realistic EV kart speed trace at Purdue Grand Prix.
"""

from __future__ import annotations
import csv
import math
import random
import sys
from pathlib import Path


def _smooth_step(x: float) -> float:
    return x * x * (3 - 2 * x)


def _build_track_profile() -> list[tuple[str, float, float]]:
    """
    Returns a list of (segment_type, duration_s, target_speed_kmh).
    Models a ~75-second lap on a tight university kart track.
    """
    # (type, duration, target_speed)
    # Straight: full acceleration up to target
    # Corner: slow down to target speed
    return [
        ("straight",  2.0, 20.0),   # start/finish straight, accelerating from low speed
        ("straight",  4.0, 52.0),   # back straight
        ("corner",    2.5, 22.0),   # Turn 1 — tight
        ("straight",  3.0, 46.0),
        ("corner",    2.0, 30.0),   # Turn 2 — medium
        ("straight",  2.5, 48.0),
        ("corner",    3.0, 18.0),   # Turn 3 — very tight hairpin
        ("straight",  5.0, 52.0),   # long back straight
        ("corner",    2.5, 25.0),   # Turn 4
        ("straight",  3.5, 50.0),
        ("corner",    2.0, 28.0),   # Turn 5
        ("straight",  2.5, 46.0),
        ("corner",    2.5, 20.0),   # Turn 6 — tight
        ("straight",  3.0, 48.0),
        ("corner",    2.0, 32.0),   # Turn 7
        ("straight",  4.0, 52.0),   # main straight into S/F
        ("corner",    1.5, 15.0),   # chicane before S/F
        ("straight",  2.0, 35.0),   # acceleration out of chicane
    ]


def _simulate_speed(profile, sample_rate=25.0, noise=0.8) -> list[float]:
    """Simulate speed trace following the track profile."""
    speeds = []
    current_speed = 0.0
    dt = 1.0 / sample_rate
    max_accel_ms2 = 5.5     # m/s²  (EV kart with Alltrax SR-72400)
    max_decel_ms2 = 8.0     # m/s²  (braking)

    for seg_type, duration, target_kmh in profile:
        target_ms = target_kmh / 3.6
        n_samples = int(duration * sample_rate)
        for i in range(n_samples):
            if current_speed < target_ms:
                # Accelerate
                gap = target_ms - current_speed
                a = min(max_accel_ms2, gap / dt * 0.4)
                current_speed = min(current_speed + a * dt, target_ms)
            else:
                # Brake
                gap = current_speed - target_ms
                a = min(max_decel_ms2, gap / dt * 0.5)
                current_speed = max(current_speed - a * dt, target_ms)

            noise_val = random.gauss(0, noise) / 3.6
            speeds.append(max(0.0, current_speed + noise_val) * 3.6)  # back to km/h

    return speeds


def generate(filepath: str, num_laps: int = 4, noise: float = 0.8) -> None:
    """Write a multi-lap AiM Solo 2 CSV to filepath."""
    sample_rate = 25.0
    profile = _build_track_profile()
    lap_duration_approx = sum(d for _, d, _ in profile)

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)

        # AiM-style header
        writer.writerow(["Format", "AiM Data"])
        writer.writerow(["Firmware", "1.5.0"])
        writer.writerow(["Date", "2025-04-23"])
        writer.writerow(["Vehicle", "Purdue EV Kart"])
        writer.writerow(["Racer", "Test Driver"])
        writer.writerow(["Venue", "Purdue Grand Prix Track"])
        writer.writerow(["Championship", "Purdue Grand Prix"])
        writer.writerow(["Comment", "Generated sample data"])
        writer.writerow([])

        # Column headers
        writer.writerow(["Time", "GPS Speed", "GPS Lat", "GPS Lon", "GPS Alt", "Beacon"])
        # Units
        writer.writerow(["s", "km/h", "deg", "deg", "m", ""])

        t = 0.0
        dt = 1.0 / sample_rate
        lat_base = 40.4259
        lon_base = -86.9081

        for lap_num in range(num_laps):
            # Slightly vary each lap
            lap_noise = noise * (1.0 + (lap_num % 2) * 0.3)
            speeds = _simulate_speed(profile, sample_rate, noise=lap_noise)

            for i, speed_kmh in enumerate(speeds):
                # Fake circular GPS track
                frac = i / len(speeds)
                angle = frac * 2 * math.pi
                lat = lat_base + 0.002 * math.cos(angle)
                lon = lon_base + 0.003 * math.sin(angle)
                alt = 184.0 + 2.0 * math.sin(angle * 2)

                # Beacon pulse at start of each lap (first 3 samples)
                beacon = 1 if i < 3 else 0

                writer.writerow([
                    f"{t:.4f}",
                    f"{speed_kmh:.2f}",
                    f"{lat:.6f}",
                    f"{lon:.6f}",
                    f"{alt:.1f}",
                    beacon,
                ])
                t += dt

    print(f"Sample data written: {filepath}")
    print(f"  {num_laps} laps × ~{lap_duration_approx:.0f}s each")
    print(f"  Sample rate: {sample_rate:.0f} Hz")
    print(f"  Total rows: {int(num_laps * len(_simulate_speed(profile, sample_rate, 0.0)))}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "sample_lap.csv"
    laps = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    generate(out, laps)
