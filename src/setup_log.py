"""
Setup change log: tracks every parameter change with timestamp and optional notes.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List


@dataclass
class ChangeEntry:
    timestamp: str
    parameter: str
    old_value: str
    new_value: str
    notes: str = ""


@dataclass
class SetupLog:
    entries: List[ChangeEntry] = field(default_factory=list)
    session_notes: str = ""

    def record(
        self,
        parameter: str,
        old_value,
        new_value,
        notes: str = "",
    ) -> None:
        if str(old_value) == str(new_value):
            return
        self.entries.append(
            ChangeEntry(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                parameter=parameter,
                old_value=str(old_value),
                new_value=str(new_value),
                notes=notes,
            )
        )

    def clear(self) -> None:
        self.entries.clear()
        self.session_notes = ""

    def to_text(self) -> str:
        lines = ["=" * 60, "SETUP LOG", "=" * 60, ""]
        if self.session_notes:
            lines += ["SESSION NOTES:", self.session_notes, ""]
        lines += ["CHANGES:", ""]
        if not self.entries:
            lines.append("  (no changes recorded)")
        for e in self.entries:
            lines.append(f"  [{e.timestamp}]  {e.parameter}")
            lines.append(f"    {e.old_value}  →  {e.new_value}")
            if e.notes:
                lines.append(f"    Note: {e.notes}")
            lines.append("")
        return "\n".join(lines)

    def to_json(self, filepath: str) -> None:
        with open(filepath, "w") as f:
            json.dump(
                {
                    "session_notes": self.session_notes,
                    "entries": [asdict(e) for e in self.entries],
                },
                f,
                indent=2,
            )

    def save_text(self, filepath: str) -> None:
        with open(filepath, "w") as f:
            f.write(self.to_text())
