"""
Export manager: saves charts as PNG, recommendations as text,
setup log, and Alltrax settings as JSON.
"""

from __future__ import annotations
import os
from datetime import datetime
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from matplotlib.figure import Figure
    from src.alltrax_settings import AlltraxSettings
    from src.gear_ratio import GearRatioConfig
    from src.recommendations import Recommendation
    from src.setup_log import SetupLog


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def export_figure(fig: "Figure", filepath: str, dpi: int = 150) -> None:
    fig.savefig(filepath, dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())


def export_all(
    output_dir: str,
    figures: dict[str, "Figure"],
    recommendations: List["Recommendation"],
    setup_log: "SetupLog",
    settings: "AlltraxSettings",
    gear: "GearRatioConfig",
    session_name: str = "session",
) -> List[str]:
    """
    Export everything to output_dir.  Returns list of written file paths.
    """
    _ensure_dir(output_dir)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    written = []

    # Charts
    charts_dir = os.path.join(output_dir, "charts")
    _ensure_dir(charts_dir)
    for name, fig in figures.items():
        path = os.path.join(charts_dir, f"{session_name}_{name}_{ts}.png")
        export_figure(fig, path)
        written.append(path)

    # Recommendations
    rec_path = os.path.join(output_dir, f"{session_name}_recommendations_{ts}.txt")
    with open(rec_path, "w") as f:
        f.write("=" * 60 + "\n")
        f.write("EV KART ANALYZER — RECOMMENDATIONS\n")
        f.write(f"Session: {session_name}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")
        if not recommendations:
            f.write("No recommendations generated.\n")
        for i, r in enumerate(recommendations, 1):
            priority_str = {1: "HIGH", 2: "MEDIUM", 3: "LOW"}.get(r.priority, "")
            f.write(f"{i}. [{r.category}] {r.parameter}  [{priority_str}]\n")
            f.write(f"   Current: {r.current_value}\n")
            f.write(f"   Recommended: {r.recommended_value}\n")
            f.write(f"   Reason: {r.reason}\n\n")
    written.append(rec_path)

    # Setup log
    log_path = os.path.join(output_dir, f"{session_name}_setup_log_{ts}.txt")
    setup_log.save_text(log_path)
    written.append(log_path)

    # Alltrax settings JSON
    settings_path = os.path.join(output_dir, f"{session_name}_alltrax_settings_{ts}.json")
    settings.to_json(settings_path)
    written.append(settings_path)

    # Gear ratio JSON
    gear_path = os.path.join(output_dir, f"{session_name}_gear_config_{ts}.json")
    gear.to_json(gear_path)
    written.append(gear_path)

    return written
