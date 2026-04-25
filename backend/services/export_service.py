"""Headless matplotlib chart generation + session report bundle."""
from __future__ import annotations
import json
import logging
import sqlite3
import zipfile
from pathlib import Path
from datetime import datetime, timezone

import numpy as np

import backend.config as cfg

log = logging.getLogger(__name__)

CHART_BG   = "#0d1b2a"
GRID_COLOR = "#1a2a3a"
LINE_COLOR = "#00BFFF"
ACCENT     = "#FF8800"


def export_session(session_id: int, db: sqlite3.Connection) -> dict:
    """Generate full session report bundle: charts + JSON + TXT + zip."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sess = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not sess:
        raise ValueError(f"Session {session_id} not found")

    d = db.execute("SELECT name FROM drivers WHERE id=?", (sess["driver_id"],)).fetchone()
    k = db.execute("SELECT name FROM karts WHERE id=?",   (sess["kart_id"],)).fetchone()
    t = db.execute("SELECT name FROM tracks WHERE id=?",  (sess["track_id"],)).fetchone()
    driver_name = d["name"] if d else "Unknown"
    kart_name   = k["name"] if k else "Unknown"
    track_name  = t["name"] if t else "Unknown"

    out_dir = cfg.EXPORT_DIR / str(session_id)
    charts_dir = out_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    lap_rows = db.execute(
        "SELECT l.*, t.time_json, t.speed_json, t.lat_json, t.lon_json, t.phase_json "
        "FROM laps l LEFT JOIN lap_telemetry t ON t.lap_id=l.id "
        "WHERE l.session_id=? ORDER BY l.lap_number",
        (session_id,),
    ).fetchall()

    laps_data = [dict(r) for r in lap_rows]
    valid_laps = [l for l in laps_data if l["is_valid"]]
    best_lap = min(valid_laps, key=lambda x: x["lap_time_s"]) if valid_laps else None

    # ── Speed trace chart (best lap) ──────────────────────────────────────────
    if best_lap and best_lap.get("time_json"):
        try:
            time_arr  = np.array(json.loads(best_lap["time_json"]))
            speed_arr = np.array(json.loads(best_lap["speed_json"])) * 3.6
            phase_arr = json.loads(best_lap["phase_json"] or "[]")

            fig, ax = plt.subplots(figsize=(12, 5), facecolor=CHART_BG)
            ax.set_facecolor(CHART_BG)

            if phase_arr and len(phase_arr) == len(time_arr):
                phase_colors = {"accelerating": "#00FF88", "braking": "#FF4444",
                                "cornering": "#FFD700", "straight": "#4488FF"}
                from matplotlib.collections import LineCollection
                points = np.array([time_arr, speed_arr]).T.reshape(-1, 1, 2)
                segments = np.concatenate([points[:-1], points[1:]], axis=1)
                colors = [phase_colors.get(str(p), LINE_COLOR) for p in phase_arr[:-1]]
                lc = LineCollection(segments, colors=colors, linewidth=2)
                ax.add_collection(lc)
                ax.set_xlim(time_arr[0], time_arr[-1])
                ax.set_ylim(0, max(speed_arr) * 1.1)
            else:
                ax.plot(time_arr, speed_arr, color=LINE_COLOR, linewidth=2)

            ax.set_xlabel("Time (s)", color="white")
            ax.set_ylabel("Speed (km/h)", color="white")
            ax.set_title(f"Best Lap Speed Trace — {driver_name} (Lap {best_lap['lap_number']})", color="white")
            ax.tick_params(colors="white")
            for spine in ax.spines.values():
                spine.set_edgecolor(GRID_COLOR)
            ax.grid(True, color=GRID_COLOR, alpha=0.5)
            fig.savefig(str(charts_dir / "speed_trace_best.png"), dpi=150, bbox_inches="tight",
                        facecolor=CHART_BG)
            plt.close(fig)
        except Exception as e:
            log.warning("Speed trace chart failed: %s", e)

    # ── Lap times bar chart ───────────────────────────────────────────────────
    if valid_laps:
        try:
            fig, ax = plt.subplots(figsize=(10, 4), facecolor=CHART_BG)
            ax.set_facecolor(CHART_BG)
            lap_nums  = [l["lap_number"] for l in valid_laps]
            lap_times = [l["lap_time_s"] for l in valid_laps]
            colors = [ACCENT if lt == min(lap_times) else LINE_COLOR for lt in lap_times]
            ax.bar(lap_nums, lap_times, color=colors)
            ax.set_xlabel("Lap", color="white")
            ax.set_ylabel("Lap Time (s)", color="white")
            ax.set_title("Lap Times", color="white")
            ax.tick_params(colors="white")
            ax.grid(True, axis="y", color=GRID_COLOR, alpha=0.5)
            fig.savefig(str(charts_dir / "lap_times.png"), dpi=150, bbox_inches="tight",
                        facecolor=CHART_BG)
            plt.close(fig)
        except Exception as e:
            log.warning("Lap times chart failed: %s", e)

    # ── GPS track map ─────────────────────────────────────────────────────────
    track_row = db.execute("SELECT local_xy FROM tracks WHERE id=?", (sess["track_id"],)).fetchone()
    if track_row and track_row["local_xy"]:
        try:
            xy = np.array(json.loads(track_row["local_xy"]))
            fig, ax = plt.subplots(figsize=(6, 6), facecolor=CHART_BG)
            ax.set_facecolor(CHART_BG)
            ax.plot(xy[:, 0], xy[:, 1], color=LINE_COLOR, linewidth=2)
            ax.set_aspect("equal")
            ax.axis("off")
            ax.set_title(f"Track Map — {track_name}", color="white")
            fig.savefig(str(charts_dir / "track_map.png"), dpi=150, bbox_inches="tight",
                        facecolor=CHART_BG)
            plt.close(fig)
        except Exception as e:
            log.warning("Track map chart failed: %s", e)

    # ── Build report.json ─────────────────────────────────────────────────────
    best_ever = db.execute(
        "SELECT best_ever_s, theoretical_best_s FROM benchmarks "
        "WHERE track_id=? AND driver_id=? AND kart_id=?",
        (sess["track_id"], sess["driver_id"], sess["kart_id"]),
    ).fetchone()

    post = db.execute("SELECT * FROM post_session_readings WHERE session_id=?", (session_id,)).fetchone()

    report_json = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session": {
            "id": session_id,
            "driver": driver_name,
            "kart": kart_name,
            "track": track_name,
            "date": sess["date"],
            "session_type": sess["session_type"],
        },
        "laps": [{"lap_number": l["lap_number"], "lap_time_s": l["lap_time_s"],
                  "is_valid": bool(l["is_valid"])} for l in laps_data],
        "best_lap": {"lap_number": best_lap["lap_number"], "lap_time_s": best_lap["lap_time_s"]} if best_lap else None,
        "benchmarks": dict(best_ever) if best_ever else {},
        "post_session": dict(post) if post else {},
    }

    (out_dir / "report.json").write_text(json.dumps(report_json, indent=2))

    # ── Build report.txt ──────────────────────────────────────────────────────
    _write_text_report(out_dir / "report.txt", report_json, valid_laps)

    # ── Zip everything ────────────────────────────────────────────────────────
    zip_path = cfg.EXPORT_DIR / f"{session_id}.zip"
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for f in out_dir.rglob("*"):
            if f.is_file():
                zf.write(str(f), f.relative_to(out_dir))

    return {"session_id": session_id, "zip_path": str(zip_path), "charts": len(list(charts_dir.glob("*.png")))}


def _write_text_report(path: Path, data: dict, valid_laps: list) -> None:
    sep = "=" * 80
    thin = "-" * 80
    lines = [
        sep,
        "STRAT-OS SESSION REPORT",
        f"Session: {data['session']['session_type']} — {data['session']['date']}",
        f"Driver:  {data['session']['driver']}  |  Kart: {data['session']['kart']}  |  Track: {data['session']['track']}",
        thin,
        "LAP TIMES",
    ]
    best_time = data["best_lap"]["lap_time_s"] if data.get("best_lap") else None
    for lap in valid_laps:
        lt = lap["lap_time_s"]
        m, s = divmod(lt, 60)
        marker = " ★ best" if best_time and abs(lt - best_time) < 0.001 else ""
        lines.append(f"  Lap {lap['lap_number']:>2}:  {int(m)}:{s:06.3f}{marker}")
    if best_time:
        m, s = divmod(best_time, 60)
        lines.append(thin)
        lines.append(f"BEST LAP:  {int(m)}:{s:06.3f}")
        bm = data.get("benchmarks", {})
        theo = bm.get("theoretical_best_s")
        if theo:
            tm, ts = divmod(theo, 60)
            lines.append(f"THEORETICAL BEST: {int(tm)}:{ts:06.3f}  (gap: +{best_time - theo:.3f}s)")
    lines.append(sep)
    path.write_text("\n".join(lines))
