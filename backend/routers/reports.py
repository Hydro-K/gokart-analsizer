"""Reports router: Alltrax program sheet PDF + ML day report PDF."""
from __future__ import annotations
import io
import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.database import get_db
from backend.routers.auth import get_current_user

router = APIRouter(tags=["reports"])

# ── Colour palette matching STRAT-OS dark theme ──────────────────────────────
BG      = "#0a1520"
SURFACE = "#0f2030"
ACCENT  = "#00BFFF"
GREEN   = "#00FF88"
ORANGE  = "#FF8C00"
RED     = "#FF4444"
GOLD    = "#FFD700"
GRAY    = "#6a8090"
WHITE   = "#e0f0ff"
BORDER  = "#1c2e3e"

def _style_fig(fig):
    fig.patch.set_facecolor(BG)

def _style_ax(ax):
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=GRAY, labelsize=8)
    ax.spines[:].set_color(BORDER)
    for spine in ax.spines.values():
        spine.set_linewidth(0.5)

def _title_text(fig, text: str, y=0.97):
    fig.text(0.05, y, text, color=ACCENT, fontsize=14, fontweight="bold",
             fontfamily="monospace", va="top")

def _sub_text(fig, text: str, y=0.93):
    fig.text(0.05, y, text, color=GRAY, fontsize=8, va="top")


# ── Alltrax Program Sheet ─────────────────────────────────────────────────────

@router.get("/alltrax/{kart_id}/program-sheet")
def alltrax_program_sheet(
    kart_id: int,
    db: sqlite3.Connection = Depends(get_db),
    _=Depends(get_current_user),
):
    kart = db.execute("SELECT * FROM karts WHERE id=?", (kart_id,)).fetchone()
    if not kart:
        raise HTTPException(404, "Kart not found")

    try:
        raw = json.loads(kart["settings_json"] or "{}")
    except Exception:
        raw = {}

    maps = raw.get("maps", [
        {"max_current": 180, "accel_rate": 64, "decel_rate": 64,
         "speed_limit": 100, "throttle_deadband": 10, "neutral_braking": 0},
        {"max_current": 150, "accel_rate": 40, "decel_rate": 64,
         "speed_limit": 80,  "throttle_deadband": 10, "neutral_braking": 0},
        {"max_current": 100, "accel_rate": 20, "decel_rate": 128,
         "speed_limit": 60,  "throttle_deadband": 10, "neutral_braking": 0},
    ])
    active_map   = raw.get("active_map", 0)
    lo_v         = raw.get("lo_voltage_cutoff", 42.0)
    hi_v         = raw.get("hi_voltage_cutoff", 58.4)
    peak_amp     = raw.get("peak_amp_mode", True)
    regen        = raw.get("regen_braking", False)
    regen_int    = raw.get("regen_intensity", 40)
    curve        = raw.get("throttle_curve", [0,10,20,30,40,50,60,70,80,90,100])
    tire_psi     = raw.get("tire_psi", {})

    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        # ── Page 1: Map tables + global settings ──────────────────────────────
        fig = plt.figure(figsize=(8.5, 11))
        _style_fig(fig)

        # Header
        fig.text(0.5, 0.97, "STRAT-OS", color=ACCENT, fontsize=20,
                 fontweight="bold", ha="center", fontfamily="monospace")
        fig.text(0.5, 0.94, "Alltrax SR Controller Program Sheet", color=WHITE,
                 fontsize=12, ha="center")
        fig.text(0.5, 0.915, f"Kart: {kart['name']}    |    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}    |    Active Map: Map {active_map + 1}",
                 color=GRAY, fontsize=8, ha="center")

        # Divider
        fig.add_artist(plt.Line2D([0.05, 0.95], [0.905, 0.905],
                                  transform=fig.transFigure, color=BORDER, linewidth=1))

        MAP_LABELS = ["Map 1 — Race", "Map 2 — Practice", "Map 3 — Safe"]
        MAP_COLORS = [ACCENT, GREEN, GOLD]
        param_labels = ["Max Current (A)", "Accel Rate (1–255)", "Decel Rate (1–255)",
                        "Speed Limit (%)", "Throttle Deadband", "Neutral Braking"]
        param_keys   = ["max_current", "accel_rate", "decel_rate",
                        "speed_limit", "throttle_deadband", "neutral_braking"]

        col_w = 0.28
        x_starts = [0.06, 0.37, 0.68]
        y_top = 0.88

        for mi, (m, label, color, xs) in enumerate(zip(maps, MAP_LABELS, MAP_COLORS, x_starts)):
            is_active = mi == active_map
            # Map header box
            ax_hdr = fig.add_axes([xs, y_top - 0.035, col_w, 0.03])
            ax_hdr.set_facecolor(color if is_active else SURFACE)
            ax_hdr.set_xlim(0, 1); ax_hdr.set_ylim(0, 1)
            ax_hdr.axis("off")
            ax_hdr.text(0.5, 0.5, label + (" ★ ACTIVE" if is_active else ""),
                        color=BG if is_active else color, fontsize=9,
                        fontweight="bold", ha="center", va="center",
                        fontfamily="monospace")

            row_h = 0.038
            for pi, (pk, pl) in enumerate(zip(param_keys, param_labels)):
                yy = y_top - 0.035 - (pi + 1) * row_h
                ax_row = fig.add_axes([xs, yy, col_w, row_h - 0.002])
                ax_row.set_facecolor(SURFACE if pi % 2 == 0 else BG)
                ax_row.set_xlim(0, 1); ax_row.set_ylim(0, 1)
                ax_row.axis("off")
                ax_row.text(0.04, 0.5, pl, color=GRAY, fontsize=7.5, va="center")
                val = m.get(pk, "—")
                val_color = ACCENT if is_active else WHITE
                if pk == "max_current" and val > 200:
                    val_color = RED
                ax_row.text(0.96, 0.5, str(val), color=val_color, fontsize=9,
                            fontweight="bold", va="center", ha="right",
                            fontfamily="monospace")

        # Global settings table
        y_global = y_top - 0.035 - len(param_keys) * 0.038 - 0.05
        fig.text(0.06, y_global + 0.025, "GLOBAL CONTROLLER SETTINGS",
                 color=GRAY, fontsize=8, fontweight="bold")

        global_rows = [
            ("Low Voltage Cutoff",  f"{lo_v:.1f} V",     lo_v < 42.0),
            ("High Voltage Cutoff", f"{hi_v:.1f} V",     hi_v > 58.4),
            ("Peak Amp Mode",       "ON" if peak_amp else "OFF", False),
            ("Regen Braking",       "ON" if regen else "OFF",    False),
            ("Regen Intensity",     f"{regen_int}%",     False),
        ]
        for gi, (glabel, gval, warn) in enumerate(global_rows):
            yy = y_global - gi * 0.034
            ax_g = fig.add_axes([0.06, yy, 0.88, 0.03])
            ax_g.set_facecolor(SURFACE if gi % 2 == 0 else BG)
            ax_g.set_xlim(0, 1); ax_g.set_ylim(0, 1); ax_g.axis("off")
            ax_g.text(0.02, 0.5, glabel, color=GRAY, fontsize=8, va="center")
            ax_g.text(0.98, 0.5, gval,
                      color=RED if warn else WHITE,
                      fontsize=9, fontweight="bold", va="center", ha="right",
                      fontfamily="monospace")

        # Tire PSI table
        y_tire = y_global - len(global_rows) * 0.034 - 0.05
        fig.text(0.06, y_tire + 0.025, "TIRE PRESSURE TARGETS (PSI)",
                 color=GRAY, fontsize=8, fontweight="bold")
        tire_corners = [
            ("Front Left (FL)",  "fl"), ("Front Right (FR)", "fr"),
            ("Rear Left (RL)",   "rl"), ("Rear Right (RR)",  "rr"),
        ]
        for ti, (tlabel, tk) in enumerate(tire_corners):
            cold = tire_psi.get(f"{tk}_cold", "—")
            hot  = tire_psi.get(f"{tk}_hot",  "—")
            yy = y_tire - ti * 0.034
            ax_t = fig.add_axes([0.06, yy, 0.88, 0.03])
            ax_t.set_facecolor(SURFACE if ti % 2 == 0 else BG)
            ax_t.set_xlim(0, 1); ax_t.set_ylim(0, 1); ax_t.axis("off")
            ax_t.text(0.02, 0.5, tlabel, color=GRAY, fontsize=8, va="center")
            ax_t.text(0.60, 0.5, f"Cold: {cold} PSI", color=WHITE, fontsize=8,
                      va="center", ha="right")
            ax_t.text(0.98, 0.5, f"Hot target: {hot} PSI", color=ACCENT,
                      fontsize=8, fontweight="bold", va="center", ha="right")

        # Footer
        fig.text(0.5, 0.02,
                 "Program these values exactly into the Alltrax controller using the handheld programmer or Alltrax PC Utility.",
                 color=GRAY, fontsize=7, ha="center", style="italic")

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # ── Page 2: Throttle curve ─────────────────────────────────────────────
        fig2 = plt.figure(figsize=(8.5, 11))
        _style_fig(fig2)
        fig2.text(0.5, 0.97, "Throttle Curve", color=ACCENT, fontsize=14,
                  fontweight="bold", ha="center", fontfamily="monospace")
        fig2.text(0.5, 0.94, f"Kart: {kart['name']}  |  11-point map (0% to 100% throttle input)",
                  color=GRAY, fontsize=8, ha="center")

        ax_c = fig2.add_axes([0.12, 0.45, 0.80, 0.44])
        _style_ax(ax_c)
        x_pts = [i * 10 for i in range(len(curve))]
        ax_c.plot(x_pts, curve, color=ACCENT, linewidth=2.5, marker="o",
                  markersize=7, markerfacecolor=WHITE)
        ax_c.fill_between(x_pts, curve, alpha=0.15, color=ACCENT)
        ax_c.plot([0, 100], [0, 100], color=GRAY, linestyle="--",
                  linewidth=1, alpha=0.5, label="Linear reference")
        ax_c.set_xlim(0, 100); ax_c.set_ylim(0, 100)
        ax_c.set_xlabel("Throttle Input (%)", color=GRAY, fontsize=9)
        ax_c.set_ylabel("Motor Output (%)", color=GRAY, fontsize=9)
        ax_c.set_title("Throttle Curve Map", color=WHITE, fontsize=10, pad=10)
        ax_c.legend(facecolor=SURFACE, edgecolor=BORDER, labelcolor=GRAY, fontsize=8)
        ax_c.grid(True, color=BORDER, linewidth=0.5, alpha=0.7)

        # Table below chart
        col_labels = [f"{i*10}%" for i in range(len(curve))]
        val_labels  = [str(int(v)) for v in curve]
        ax_tbl = fig2.add_axes([0.05, 0.30, 0.90, 0.10])
        ax_tbl.axis("off")
        tbl = ax_tbl.table(
            cellText=[val_labels],
            colLabels=col_labels,
            loc="center",
            cellLoc="center",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)
        for (row, col), cell in tbl.get_celld().items():
            cell.set_facecolor(SURFACE if row == 0 else BG)
            cell.set_text_props(color=ACCENT if row == 1 else GRAY,
                                fontweight="bold" if row == 1 else "normal",
                                fontfamily="monospace")
            cell.set_edgecolor(BORDER)

        fig2.text(0.5, 0.27,
                  "Enter each value above into the Alltrax throttle curve map (points 0–10).",
                  color=GRAY, fontsize=8, ha="center", style="italic")

        pdf.savefig(fig2, bbox_inches="tight")
        plt.close(fig2)

    buf.seek(0)
    kart_name_safe = kart["name"].replace(" ", "_")
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="alltrax_program_{kart_name_safe}.pdf"'},
    )


# ── ML Day Report ─────────────────────────────────────────────────────────────

@router.get("/day/{date}")
def day_report(
    date: str,  # YYYY-MM-DD
    db: sqlite3.Connection = Depends(get_db),
    _=Depends(get_current_user),
):
    """Generate a PDF race-day report for all sessions on `date`."""
    sessions = db.execute(
        """SELECT s.*, d.name as driver_name, k.name as kart_name, t.name as track_name
           FROM sessions s
           LEFT JOIN drivers d ON d.id=s.driver_id
           LEFT JOIN karts   k ON k.id=s.kart_id
           LEFT JOIN tracks  t ON t.id=s.track_id
           WHERE s.date=? ORDER BY s.created_at ASC""",
        (date,),
    ).fetchall()

    if not sessions:
        raise HTTPException(404, f"No sessions found for {date}")

    # Gather laps per session
    sessions_data = []
    for sess in sessions:
        laps = db.execute(
            "SELECT * FROM laps WHERE session_id=? AND is_valid=1 ORDER BY lap_number ASC",
            (sess["id"],),
        ).fetchall()
        tire_logs = db.execute(
            "SELECT * FROM tire_pressure_logs WHERE session_id=? ORDER BY created_at ASC",
            (sess["id"],),
        ).fetchall()
        energy_rows = []
        for lap in laps:
            er = db.execute(
                "SELECT total_kwh, net_kwh, avg_power_kw, peak_power_kw FROM lap_telemetry WHERE lap_id=?",
                (lap["id"],),
            ).fetchone()
            energy_rows.append(dict(er) if er else {})
        sessions_data.append({
            "session": dict(sess),
            "laps": [dict(l) for l in laps],
            "tire_logs": [dict(t) for t in tire_logs],
            "energy": energy_rows,
        })

    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        _build_day_summary_page(pdf, date, sessions_data)
        _build_lap_chart_page(pdf, date, sessions_data)
        if any(sd["tire_logs"] for sd in sessions_data):
            _build_tire_page(pdf, date, sessions_data)
        _build_energy_page(pdf, date, sessions_data)
        _build_suggestions_page(pdf, date, sessions_data)

    buf.seek(0)
    safe_date = date.replace("-", "")
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="day_report_{safe_date}.pdf"'},
    )


def _build_day_summary_page(pdf, date, sessions_data):
    fig = plt.figure(figsize=(8.5, 11))
    _style_fig(fig)

    # Header
    fig.text(0.5, 0.97, "STRAT-OS  ·  Race Day Report", color=ACCENT,
             fontsize=16, fontweight="bold", ha="center", fontfamily="monospace")
    fig.text(0.5, 0.935,
             f"Date: {date}    Sessions: {len(sessions_data)}    "
             f"Total valid laps: {sum(len(sd['laps']) for sd in sessions_data)}",
             color=WHITE, fontsize=10, ha="center")
    fig.add_artist(plt.Line2D([0.05, 0.95], [0.92, 0.92],
                              transform=fig.transFigure, color=BORDER))

    # Sessions table
    fig.text(0.06, 0.90, "SESSION OVERVIEW", color=GRAY,
             fontsize=8, fontweight="bold")

    headers = ["#", "Type", "Driver", "Kart", "Laps", "Best Lap", "Avg Lap", "Δ Best→Avg"]
    col_xs  = [0.06, 0.12, 0.22, 0.36, 0.49, 0.57, 0.70, 0.83]
    row_h   = 0.038

    # Header row
    ax_hdr = fig.add_axes([0.06, 0.86, 0.88, row_h])
    ax_hdr.set_facecolor(ACCENT); ax_hdr.set_xlim(0, 1); ax_hdr.axis("off")
    for h, x in zip(headers, col_xs):
        rel_x = (x - 0.06) / 0.88
        ax_hdr.text(rel_x + 0.01, 0.5, h, color=BG, fontsize=7.5,
                    fontweight="bold", va="center")

    for si, sd in enumerate(sessions_data):
        sess = sd["session"]
        laps = sd["laps"]
        lap_times = [l["lap_time_s"] for l in laps if l.get("lap_time_s")]
        best = min(lap_times) if lap_times else None
        avg  = float(np.mean(lap_times)) if lap_times else None
        delta = avg - best if (best and avg) else None

        row_vals = [
            str(si + 1),
            sess.get("session_type", "—"),
            sess.get("driver_name", "—")[:12],
            sess.get("kart_name", "—")[:10],
            str(len(laps)),
            _fmt_time(best) if best else "—",
            _fmt_time(avg)  if avg  else "—",
            f"+{delta:.3f}s" if delta else "—",
        ]

        yy = 0.86 - (si + 1) * (row_h + 0.002)
        ax_r = fig.add_axes([0.06, yy, 0.88, row_h])
        ax_r.set_facecolor(SURFACE if si % 2 == 0 else BG)
        ax_r.set_xlim(0, 1); ax_r.axis("off")
        for val, x in zip(row_vals, col_xs):
            rel_x = (x - 0.06) / 0.88
            color = ACCENT if val.startswith("1:") or ":" in val else WHITE
            if val.startswith("+"):
                color = GRAY
            ax_r.text(rel_x + 0.01, 0.5, val, color=color,
                      fontsize=7.5, va="center", fontfamily="monospace")

    # Per-driver best summary
    y_drv = 0.86 - (len(sessions_data) + 2) * (row_h + 0.002) - 0.02
    fig.text(0.06, y_drv + 0.025, "BEST LAP PER DRIVER (DAY OVERALL)",
             color=GRAY, fontsize=8, fontweight="bold")

    driver_bests: dict = {}
    for sd in sessions_data:
        drv = sd["session"].get("driver_name", "Unknown")
        for lap in sd["laps"]:
            t = lap.get("lap_time_s")
            if t and (drv not in driver_bests or t < driver_bests[drv]):
                driver_bests[drv] = t

    for di, (drv, best_t) in enumerate(sorted(driver_bests.items(), key=lambda x: x[1])):
        yy = y_drv - di * (row_h + 0.002)
        ax_d = fig.add_axes([0.06, yy, 0.88, row_h])
        ax_d.set_facecolor(SURFACE if di == 0 else BG)
        ax_d.set_xlim(0, 1); ax_d.axis("off")
        badge = "★ FASTEST" if di == 0 else f"#{di+1}"
        ax_d.text(0.02, 0.5, badge, color=GOLD if di == 0 else GRAY,
                  fontsize=8, fontweight="bold", va="center")
        ax_d.text(0.15, 0.5, drv, color=WHITE, fontsize=9, va="center")
        ax_d.text(0.98, 0.5, _fmt_time(best_t), color=ACCENT, fontsize=11,
                  fontweight="bold", va="center", ha="right", fontfamily="monospace")

    fig.text(0.5, 0.02, f"STRAT-OS  ·  Page 1  ·  {date}",
             color=GRAY, fontsize=7, ha="center")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _build_lap_chart_page(pdf, date, sessions_data):
    fig = plt.figure(figsize=(8.5, 11))
    _style_fig(fig)
    fig.text(0.5, 0.97, "Lap Time Progression", color=ACCENT,
             fontsize=14, fontweight="bold", ha="center", fontfamily="monospace")
    fig.text(0.5, 0.94, date, color=GRAY, fontsize=9, ha="center")

    n = len(sessions_data)
    colors_cycle = [ACCENT, GREEN, GOLD, RED, ORANGE, "#AA88FF"]

    # Combined chart across all sessions
    ax = fig.add_axes([0.10, 0.55, 0.85, 0.35])
    _style_ax(ax)

    offset = 0
    xticks, xlabels = [], []
    for si, sd in enumerate(sessions_data):
        laps = sd["laps"]
        times = [l["lap_time_s"] for l in laps if l.get("lap_time_s")]
        if not times:
            continue
        x = list(range(offset + 1, offset + len(times) + 1))
        drv = sd["session"].get("driver_name", "?")
        stype = sd["session"].get("session_type", "Session")
        color = colors_cycle[si % len(colors_cycle)]
        ax.plot(x, times, color=color, linewidth=1.8, marker="o",
                markersize=5, label=f"{stype} — {drv}")
        if times:
            best_idx = int(np.argmin(times))
            ax.annotate(f"  {_fmt_time(times[best_idx])}",
                        (x[best_idx], times[best_idx]),
                        fontsize=6, color=color, va="bottom")
        xticks.append(offset + len(times) // 2 + 1)
        xlabels.append(f"{stype[:4]}\n{drv[:6]}")
        offset += len(times)
        ax.axvline(offset + 0.5, color=BORDER, linewidth=1, linestyle=":")

    ax.set_xlabel("Lap Number", color=GRAY, fontsize=8)
    ax.set_ylabel("Lap Time (s)", color=GRAY, fontsize=8)
    ax.set_title("All Sessions — Lap Times", color=WHITE, fontsize=9, pad=6)
    ax.legend(facecolor=SURFACE, edgecolor=BORDER, labelcolor=WHITE,
              fontsize=7, loc="upper right")
    ax.set_xticks(xticks); ax.set_xticklabels(xlabels, fontsize=7, color=GRAY)
    ax.grid(True, color=BORDER, linewidth=0.5)

    # Per-session mini charts
    valid_sessions = [sd for sd in sessions_data if sd["laps"]]
    cols = min(3, len(valid_sessions))
    if cols > 0:
        rows = (len(valid_sessions) + cols - 1) // cols
        chart_h = 0.10
        chart_w = 0.25
        x_pad   = 0.04
        y_start = 0.48

        for i, sd in enumerate(valid_sessions):
            col = i % cols
            row = i // cols
            ax_s = fig.add_axes([
                0.08 + col * (chart_w + x_pad),
                y_start - row * (chart_h + 0.04),
                chart_w, chart_h,
            ])
            _style_ax(ax_s)
            times = [l["lap_time_s"] for l in sd["laps"] if l.get("lap_time_s")]
            if times:
                color = colors_cycle[i % len(colors_cycle)]
                ax_s.plot(range(1, len(times) + 1), times, color=color,
                          linewidth=1.5, marker="o", markersize=3)
                ax_s.axhline(min(times), color=GREEN, linewidth=0.8,
                             linestyle="--", alpha=0.6)
            stype = sd["session"].get("session_type", "")
            drv   = sd["session"].get("driver_name", "")
            ax_s.set_title(f"{stype} — {drv}", color=WHITE, fontsize=7, pad=3)
            ax_s.tick_params(labelsize=6)

    fig.text(0.5, 0.02, f"STRAT-OS  ·  Page 2  ·  {date}",
             color=GRAY, fontsize=7, ha="center")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _build_tire_page(pdf, date, sessions_data):
    fig = plt.figure(figsize=(8.5, 11))
    _style_fig(fig)
    fig.text(0.5, 0.97, "Tire Pressure Log", color=ACCENT,
             fontsize=14, fontweight="bold", ha="center", fontfamily="monospace")
    fig.text(0.5, 0.94, date, color=GRAY, fontsize=9, ha="center")

    y = 0.90
    for sd in sessions_data:
        logs = sd["tire_logs"]
        if not logs:
            continue
        stype = sd["session"].get("session_type", "Session")
        drv   = sd["session"].get("driver_name", "—")
        fig.text(0.06, y, f"{stype}  —  {drv}", color=WHITE,
                 fontsize=9, fontweight="bold")
        y -= 0.025
        headers = ["Time", "FL", "FR", "RL", "RR", "Notes"]
        col_xs  = [0.06, 0.22, 0.34, 0.46, 0.58, 0.70]
        ax_h = fig.add_axes([0.06, y - 0.030, 0.88, 0.028])
        ax_h.set_facecolor(ACCENT); ax_h.axis("off"); ax_h.set_xlim(0, 1)
        for h, x in zip(headers, col_xs):
            ax_h.text((x - 0.06)/0.88 + 0.01, 0.5, h, color=BG,
                      fontsize=7.5, fontweight="bold", va="center")
        y -= 0.032
        for li, log in enumerate(logs):
            ax_r = fig.add_axes([0.06, y - 0.028, 0.88, 0.026])
            ax_r.set_facecolor(SURFACE if li % 2 == 0 else BG)
            ax_r.axis("off"); ax_r.set_xlim(0, 1)
            vals = [
                log.get("recorded_at", "—"),
                f"{log['fl_psi']:.1f}" if log.get("fl_psi") else "—",
                f"{log['fr_psi']:.1f}" if log.get("fr_psi") else "—",
                f"{log['rl_psi']:.1f}" if log.get("rl_psi") else "—",
                f"{log['rr_psi']:.1f}" if log.get("rr_psi") else "—",
                (log.get("notes") or "")[:28],
            ]
            for val, x in zip(vals, col_xs):
                ax_r.text((x - 0.06)/0.88 + 0.01, 0.5, val, color=WHITE,
                          fontsize=7.5, va="center", fontfamily="monospace")
            y -= 0.030
        y -= 0.020

    fig.text(0.5, 0.02, f"STRAT-OS  ·  Page 3  ·  {date}",
             color=GRAY, fontsize=7, ha="center")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _build_energy_page(pdf, date, sessions_data):
    fig = plt.figure(figsize=(8.5, 11))
    _style_fig(fig)
    fig.text(0.5, 0.97, "Energy & Power Analysis", color=ACCENT,
             fontsize=14, fontweight="bold", ha="center", fontfamily="monospace")
    fig.text(0.5, 0.94, date, color=GRAY, fontsize=9, ha="center")

    # Per-session energy summary
    y = 0.90
    total_kwh_day = 0.0
    for sd in sessions_data:
        energy_list = [e for e in sd["energy"] if e.get("total_kwh")]
        if not energy_list:
            continue
        sess_kwh  = sum(e["total_kwh"] for e in energy_list)
        avg_power = np.mean([e["avg_power_kw"] for e in energy_list if e.get("avg_power_kw")])
        peak_pow  = max((e.get("peak_power_kw", 0) for e in energy_list), default=0)
        total_kwh_day += sess_kwh
        stype = sd["session"].get("session_type", "Session")
        drv   = sd["session"].get("driver_name", "—")

        ax_e = fig.add_axes([0.06, y - 0.06, 0.88, 0.055])
        ax_e.set_facecolor(SURFACE); ax_e.axis("off"); ax_e.set_xlim(0, 1)
        ax_e.text(0.01, 0.75, f"{stype}  —  {drv}", color=WHITE,
                  fontsize=9, fontweight="bold", va="center")
        items = [
            (0.01, "Total Energy",   f"{sess_kwh:.3f} kWh",   ACCENT),
            (0.26, "Avg Power",      f"{avg_power:.1f} kW",    GREEN),
            (0.51, "Peak Power",     f"{peak_pow:.1f} kW",     ORANGE),
            (0.76, "Laps",           str(len(energy_list)),    WHITE),
        ]
        for x, label, val, color in items:
            ax_e.text(x + 0.01, 0.42, label, color=GRAY, fontsize=7, va="center")
            ax_e.text(x + 0.01, 0.12, val,   color=color, fontsize=9,
                      fontweight="bold", va="center", fontfamily="monospace")
        y -= 0.075

    # Battery capacity gauge
    battery_cap_wh = 3072.0  # LiTime 48V 60Ah
    used_pct = (total_kwh_day * 1000 / battery_cap_wh) * 100
    ax_bar = fig.add_axes([0.10, y - 0.08, 0.80, 0.04])
    ax_bar.set_facecolor(SURFACE)
    ax_bar.set_xlim(0, 100); ax_bar.set_ylim(0, 1); ax_bar.axis("off")
    bar_color = RED if used_pct > 80 else ORANGE if used_pct > 60 else GREEN
    ax_bar.barh(0.5, min(used_pct, 100), height=0.8, left=0,
                color=bar_color, alpha=0.8)
    ax_bar.text(50, 0.5, f"{used_pct:.1f}% of {battery_cap_wh:.0f} Wh capacity used today "
                f"({total_kwh_day:.3f} kWh total)",
                color=WHITE, fontsize=9, fontweight="bold",
                ha="center", va="center")
    fig.text(0.10, y - 0.03, "BATTERY USAGE — FULL DAY", color=GRAY,
             fontsize=8, fontweight="bold")

    fig.text(0.5, 0.02, f"STRAT-OS  ·  Page {'3' if True else '4'}  ·  {date}",
             color=GRAY, fontsize=7, ha="center")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _build_suggestions_page(pdf, date, sessions_data):
    fig = plt.figure(figsize=(8.5, 11))
    _style_fig(fig)
    fig.text(0.5, 0.97, "Analysis & Recommendations", color=ACCENT,
             fontsize=14, fontweight="bold", ha="center", fontfamily="monospace")
    fig.text(0.5, 0.94, f"ML-generated insights  ·  {date}",
             color=GRAY, fontsize=9, ha="center")
    fig.add_artist(plt.Line2D([0.05, 0.95], [0.925, 0.925],
                              transform=fig.transFigure, color=BORDER))

    suggestions = _generate_suggestions(sessions_data)

    y = 0.905
    for i, (category, priority, text) in enumerate(suggestions):
        icon_color = RED if priority == "high" else ORANGE if priority == "medium" else GREEN
        icon_char  = "!" if priority == "high" else "→" if priority == "medium" else "✓"

        ax_s = fig.add_axes([0.06, y - 0.055, 0.88, 0.052])
        ax_s.set_facecolor(SURFACE if i % 2 == 0 else BG)
        ax_s.axis("off"); ax_s.set_xlim(0, 1); ax_s.set_ylim(0, 1)

        ax_s.text(0.01, 0.75, f"{icon_char} {category.upper()}",
                  color=icon_color, fontsize=8, fontweight="bold", va="center")
        # Word-wrap text manually
        words = text.split()
        lines, line = [], []
        for w in words:
            line.append(w)
            if len(" ".join(line)) > 80:
                lines.append(" ".join(line[:-1]))
                line = [w]
        if line:
            lines.append(" ".join(line))
        for li, ln in enumerate(lines[:2]):
            ax_s.text(0.02, 0.45 - li * 0.22, ln, color=WHITE,
                      fontsize=7.5, va="center")

        y -= 0.062
        if y < 0.08:
            break

    fig.text(0.5, 0.02, f"STRAT-OS  ·  Last Page  ·  {date}",
             color=GRAY, fontsize=7, ha="center")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _generate_suggestions(sessions_data) -> list[tuple[str, str, str]]:
    """Rule-based insights derived from the day's data."""
    suggestions = []

    all_laps_by_session = [(sd["session"], sd["laps"]) for sd in sessions_data]

    # 1. Consistency check across sessions
    for sess, laps in all_laps_by_session:
        times = [l["lap_time_s"] for l in laps if l.get("lap_time_s")]
        if len(times) < 3:
            continue
        std = float(np.std(times))
        mean = float(np.mean(times))
        cv = std / mean * 100
        stype = sess.get("session_type", "Session")
        drv   = sess.get("driver_name", "Driver")
        if cv > 5:
            suggestions.append((
                "Consistency",
                "high",
                f"{drv} showed {cv:.1f}% lap-time variation in {stype} "
                f"(std={std:.2f}s over {len(times)} laps). "
                f"Target <3%. Review brake points and throttle application — "
                f"focus on consistent corner entry."
            ))
        elif cv < 1.5:
            suggestions.append((
                "Consistency",
                "low",
                f"{drv} was highly consistent in {stype} ({cv:.1f}% variation). "
                f"Good throttle discipline — maintain this approach in the race."
            ))

    # 2. Improvement trend across session types
    session_bests = {}
    for sess, laps in all_laps_by_session:
        times = [l["lap_time_s"] for l in laps if l.get("lap_time_s")]
        if times:
            stype = sess.get("session_type", "")
            drv   = sess.get("driver_name", "")
            key   = (drv, stype)
            if key not in session_bests or min(times) < session_bests[key]:
                session_bests[key] = min(times)

    drivers_seen = {k[0] for k in session_bests}
    for drv in drivers_seen:
        test_best  = session_bests.get((drv, "Testing"))
        sprint_best = session_bests.get((drv, "Sprint"))
        race_best   = session_bests.get((drv, "Race"))
        if test_best and race_best:
            delta = test_best - race_best
            if delta > 0.5:
                suggestions.append((
                    "Pace Improvement",
                    "low",
                    f"{drv} improved {delta:.3f}s from Testing to Race "
                    f"({_fmt_time(test_best)} → {_fmt_time(race_best)}). "
                    f"Confidence and rubber build-up contributed. Keep this trend."
                ))
            elif delta < -0.5:
                suggestions.append((
                    "Pace Decline",
                    "high",
                    f"{drv} was {abs(delta):.3f}s slower in Race vs Testing. "
                    f"Check for tire degradation, battery voltage drop, or driver fatigue. "
                    f"Review braking consistency in the race laps."
                ))

    # 3. Driver comparison
    all_drivers = {}
    for sess, laps in all_laps_by_session:
        drv = sess.get("driver_name", "?")
        times = [l["lap_time_s"] for l in laps if l.get("lap_time_s")]
        if times:
            if drv not in all_drivers:
                all_drivers[drv] = []
            all_drivers[drv].extend(times)

    if len(all_drivers) > 1:
        bests = {d: min(ts) for d, ts in all_drivers.items()}
        sorted_d = sorted(bests.items(), key=lambda x: x[1])
        gap = sorted_d[-1][1] - sorted_d[0][1]
        if gap > 1.0:
            suggestions.append((
                "Driver Gap",
                "medium",
                f"Gap between fastest ({sorted_d[0][0]}, {_fmt_time(sorted_d[0][1])}) "
                f"and slowest ({sorted_d[-1][0]}, {_fmt_time(sorted_d[-1][1])}) "
                f"is {gap:.3f}s. Consider reviewing slower driver's corner entry speeds "
                f"and throttle map — a softer accel curve may help."
            ))

    # 4. Tire pressure checks
    for sd in sessions_data:
        logs = sd["tire_logs"]
        if len(logs) < 2:
            continue
        first = logs[0]; last = logs[-1]
        for corner in ["fl", "fr", "rl", "rr"]:
            p0 = first.get(f"{corner}_psi")
            p1 = last.get(f"{corner}_psi")
            if p0 and p1:
                rise = p1 - p0
                if rise > 5:
                    suggestions.append((
                        "Tire Pressure",
                        "high",
                        f"{corner.upper()} tire rose {rise:.1f} PSI during "
                        f"{sd['session'].get('session_type','session')}. "
                        f"Expected ~3–4 PSI rise. Possible under-inflation cold "
                        f"or heat build-up — lower cold pressure by 1–2 PSI next session."
                    ))

    # 5. Energy
    all_energy = []
    for sd in sessions_data:
        all_energy.extend([e for e in sd["energy"] if e.get("total_kwh")])
    if all_energy:
        avg_kwh = np.mean([e["total_kwh"] for e in all_energy])
        if avg_kwh > 0.05:
            laps_per_charge = 3.072 / avg_kwh
            suggestions.append((
                "Battery Strategy",
                "medium",
                f"Average energy per lap: {avg_kwh:.4f} kWh. "
                f"Estimated {laps_per_charge:.0f} laps per full charge at current usage. "
                f"Plan charge strategy accordingly — allow 15 min buffer before race start."
            ))

    if not suggestions:
        suggestions.append(("Data", "low",
                             "Not enough telemetry data to generate detailed suggestions. "
                             "Upload more laps or check that all CSV channels are wired correctly."))
    return suggestions


def _fmt_time(s: Optional[float]) -> str:
    if s is None:
        return "—"
    m   = int(s // 60)
    sec = s % 60
    return f"{m}:{sec:06.3f}"
