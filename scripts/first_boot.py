#!/usr/bin/env python3
"""Initialize the Strat-OS database (run once on first deployment)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import backend.config as cfg
from backend.database import init_db

if __name__ == "__main__":
    cfg.ensure_dirs()
    init_db()
    print(f"Database initialized at {cfg.DB_PATH}")
    print("Competition rules row seeded (id=1, 220A cap).")
    print("Ready. Start the service with: systemctl start strat-os")
