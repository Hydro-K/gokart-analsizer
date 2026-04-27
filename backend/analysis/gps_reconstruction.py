"""
Offline GPS track reconstruction.
No external APIs. No map tiles.
Converts lat/lon → local XY (meters) → normalized 0-1000 canvas units.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List

import numpy as np
from scipy.ndimage import gaussian_filter1d

_EARTH_RADIUS_M = 6_371_000.0


@dataclass
class TrackMap:
    local_xy: List[List[float]]   # [[x, y], ...] normalized 0-1000
    lat_center: float
    lon_center: float
    length_m: float


def reconstruct_track_multi_lap(
    lap_gps: List[tuple],
    smooth_sigma: float = 8.0,
) -> TrackMap:
    """
    Build a track map by averaging GPS paths from multiple laps.

    lap_gps: list of (lat_array, lon_array) tuples — one per lap.
    Each lap is resampled to 500 evenly-spaced arc-length points in local XY,
    then all paths are averaged point-by-point before smoothing.
    This cancels GPS noise and gives a much more accurate track outline.
    """
    if not lap_gps:
        raise ValueError("No GPS laps provided")
    if len(lap_gps) == 1:
        return reconstruct_track(lap_gps[0][0], lap_gps[0][1], smooth_sigma)

    N_POINTS = 500

    # Use first lap's centroid as the shared origin
    lat0 = np.concatenate([lat for lat, _ in lap_gps])
    lon0 = np.concatenate([lon for _, lon in lap_gps])
    lat_c = float(np.mean(lat0))
    lon_c = float(np.mean(lon0))

    def _lap_to_xy_resampled(lat_arr, lon_arr):
        """Filter outliers, project, resample to N_POINTS uniform arc-length."""
        x, y = _equirect(np.asarray(lat_arr), np.asarray(lon_arr), lat_c, lon_c)
        # Filter GPS outliers
        keep = np.ones(len(x), dtype=bool)
        for i in range(1, len(x)):
            d = np.sqrt((x[i] - x[i-1])**2 + (y[i] - y[i-1])**2)
            if d > 50.0:
                keep[i] = False
        x, y = x[keep], y[keep]
        if len(x) < 10:
            return None, None
        # Arc-length parameterization
        ds = np.sqrt(np.diff(x)**2 + np.diff(y)**2)
        s = np.concatenate([[0.0], np.cumsum(ds)])
        s_uniform = np.linspace(0, s[-1], N_POINTS)
        x_r = np.interp(s_uniform, s, x)
        y_r = np.interp(s_uniform, s, y)
        return x_r, y_r

    xs, ys = [], []
    for lat_arr, lon_arr in lap_gps:
        xr, yr = _lap_to_xy_resampled(lat_arr, lon_arr)
        if xr is not None:
            xs.append(xr)
            ys.append(yr)

    if not xs:
        raise ValueError("No valid GPS laps after filtering")

    # Average paths
    x_avg = np.mean(xs, axis=0)
    y_avg = np.mean(ys, axis=0)

    # Smooth the averaged path
    x_smooth = gaussian_filter1d(x_avg, sigma=smooth_sigma)
    y_smooth = gaussian_filter1d(y_avg, sigma=smooth_sigma)

    # Track length
    dx, dy = np.diff(x_smooth), np.diff(y_smooth)
    length_m = float(np.sum(np.sqrt(dx**2 + dy**2)))

    # Normalize to 0-1000 canvas
    x_min, x_max = x_smooth.min(), x_smooth.max()
    y_min, y_max = y_smooth.min(), y_smooth.max()
    scale = 900.0 / max(x_max - x_min, y_max - y_min, 1.0)
    x_norm = (x_smooth - x_min) * scale + 50.0
    y_norm = 950.0 - (y_smooth - y_min) * scale

    xy = [[round(float(xi), 2), round(float(yi), 2)] for xi, yi in zip(x_norm, y_norm)]
    return TrackMap(local_xy=xy, lat_center=round(lat_c, 6), lon_center=round(lon_c, 6),
                    length_m=round(length_m, 1))


def reconstruct_track(lat: np.ndarray, lon: np.ndarray, smooth_sigma: float = 15.0) -> TrackMap:
    """
    Reconstruct a track map from GPS lat/lon arrays.

    Steps:
    1. Filter GPS outliers (neighbor distance > 50 m)
    2. Remove duplicates (< 0.5 m apart)
    3. Equirectangular projection → local XY meters
    4. Gaussian smooth to remove GPS jitter
    5. Normalize to 0-1000 canvas units (preserve aspect ratio)
    6. Compute track length
    """
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)

    if len(lat) < 10:
        raise ValueError("Need at least 10 GPS points to reconstruct track")

    # 1. Filter outliers — drop points > 50 m from previous
    keep = np.ones(len(lat), dtype=bool)
    for i in range(1, len(lat)):
        d = _haversine_m(lat[i-1], lon[i-1], lat[i], lon[i])
        if d > 50.0:
            keep[i] = False
    lat, lon = lat[keep], lon[keep]

    # 2. Remove duplicates
    lat_c = float(np.mean(lat))
    lon_c = float(np.mean(lon))
    x_raw, y_raw = _equirect(lat, lon, lat_c, lon_c)
    dist_step = np.sqrt(np.diff(x_raw)**2 + np.diff(y_raw)**2)
    keep2 = np.concatenate([[True], dist_step >= 0.5])
    x_raw, y_raw = x_raw[keep2], y_raw[keep2]

    if len(x_raw) < 5:
        raise ValueError("Too few unique GPS points after filtering")

    # 3. Smooth
    x_smooth = gaussian_filter1d(x_raw, sigma=smooth_sigma)
    y_smooth = gaussian_filter1d(y_raw, sigma=smooth_sigma)

    # 4. Track length
    dx = np.diff(x_smooth)
    dy = np.diff(y_smooth)
    length_m = float(np.sum(np.sqrt(dx**2 + dy**2)))

    # 5. Normalize to 0-1000 canvas (preserve aspect ratio)
    x_min, x_max = x_smooth.min(), x_smooth.max()
    y_min, y_max = y_smooth.min(), y_smooth.max()
    x_range = max(x_max - x_min, 1.0)
    y_range = max(y_max - y_min, 1.0)
    scale = 900.0 / max(x_range, y_range)   # 900 leaves 50px margin each side

    x_norm = (x_smooth - x_min) * scale + 50.0
    y_norm = 950.0 - (y_smooth - y_min) * scale  # flip Y so north=up

    xy = [[round(float(xi), 2), round(float(yi), 2)] for xi, yi in zip(x_norm, y_norm)]

    return TrackMap(
        local_xy=xy,
        lat_center=round(lat_c, 6),
        lon_center=round(lon_c, 6),
        length_m=round(length_m, 1),
    )


def _equirect(lat: np.ndarray, lon: np.ndarray, lat_c: float, lon_c: float):
    """Equirectangular projection to local XY meters."""
    x = _EARTH_RADIUS_M * np.radians(lon - lon_c) * np.cos(np.radians(lat_c))
    y = _EARTH_RADIUS_M * np.radians(lat - lat_c)
    return x, y


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    R = _EARTH_RADIUS_M
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
    return R * 2 * np.arcsin(np.sqrt(a))
