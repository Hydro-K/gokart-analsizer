"""Joblib-based model persistence for Strat-OS ML system."""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import json

import joblib

import backend.config as cfg

_META_FILE = cfg.MODEL_DIR / "model_meta.json"


def save_model(name: str, obj) -> None:
    cfg.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(obj, cfg.MODEL_DIR / f"{name}.joblib")


def load_model(name: str):
    p = cfg.MODEL_DIR / f"{name}.joblib"
    return joblib.load(str(p)) if p.exists() else None


def model_exists() -> bool:
    return (cfg.MODEL_DIR / "classifier.joblib").exists()


def last_trained() -> Optional[str]:
    if _META_FILE.exists():
        try:
            return json.loads(_META_FILE.read_text()).get("last_trained")
        except Exception:
            pass
    return None


def save_meta(n_samples: int) -> None:
    from datetime import datetime, timezone
    cfg.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    _META_FILE.write_text(json.dumps({
        "last_trained": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_samples": n_samples,
    }))
