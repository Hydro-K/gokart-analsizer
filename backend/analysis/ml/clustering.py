"""
Driver style ML pipeline.

Bootstrap (N < 20): MiniBatchKMeans → map centroids to style labels.
Incremental (N >= 20): SGDClassifier.partial_fit → persistent classifier.
Labels: aggressive, smooth, balanced, inconsistent
"""
from __future__ import annotations
import logging
import sqlite3
from typing import List

import numpy as np

log = logging.getLogger(__name__)

_STYLE_LABELS = ["aggressive", "smooth", "balanced", "inconsistent"]
_FEATURE_KEYS = [
    "throttle_variance",
    "braking_intensity",
    "corner_entry_speed_avg",
    "accel_consistency",
    "smoothness_score",
]


def _load_feature_matrix(db: sqlite3.Connection):
    rows = db.execute(
        "SELECT lap_id, driver_id, throttle_variance, braking_intensity, "
        "corner_entry_speed_avg, accel_consistency, smoothness_score "
        "FROM feature_vectors WHERE throttle_variance IS NOT NULL"
    ).fetchall()
    if not rows:
        return np.array([]), [], []
    X = np.array([[row[k] for k in _FEATURE_KEYS] for row in rows], dtype=float)
    lap_ids    = [row["lap_id"]    for row in rows]
    driver_ids = [row["driver_id"] for row in rows]
    return X, lap_ids, driver_ids


def _map_clusters_to_labels(km, scaler, X: np.ndarray) -> dict:
    """Map KMeans cluster indices to style labels by centroid inspection."""
    centers = scaler.inverse_transform(km.cluster_centers_)
    # Features: [throttle_var, braking_intensity, corner_entry_speed, accel_consistency, smoothness]
    # aggressive: high braking_intensity + low accel_consistency + high throttle_var
    # smooth:     high smoothness + high accel_consistency + low throttle_var
    # balanced:   medium everything
    # inconsistent: low smoothness + high throttle_var + low accel_consistency

    scores = []
    for c in centers:
        throttle_var, braking_int, corner_speed, accel_cons, smoothness = c
        # Compute style score vector
        aggressive_score  = braking_int * 0.4 + throttle_var * 0.3 + (100 - accel_cons) * 0.3
        smooth_score      = smoothness * 0.4 + accel_cons * 0.3 + (100 - throttle_var) * 0.3
        inconsistent_score = throttle_var * 0.4 + (100 - accel_cons) * 0.4 + (100 - smoothness) * 0.2
        balanced_score    = 100 - max(aggressive_score, smooth_score, inconsistent_score) * 0.5
        scores.append([aggressive_score, smooth_score, balanced_score, inconsistent_score])

    scores = np.array(scores)
    cluster_to_label = {}
    used_labels = set()
    # Assign greedily: each cluster gets the label it scores highest on
    for _ in range(len(centers)):
        best_cluster, best_label = -1, -1
        best_val = -np.inf
        for ci in range(len(centers)):
            if ci in cluster_to_label:
                continue
            for li, label in enumerate(_STYLE_LABELS):
                if label in used_labels:
                    continue
                if scores[ci, li] > best_val:
                    best_val = scores[ci, li]
                    best_cluster = ci
                    best_label = li
        if best_cluster >= 0:
            cluster_to_label[best_cluster] = _STYLE_LABELS[best_label]
            used_labels.add(_STYLE_LABELS[best_label])

    # Fallback
    for ci in range(len(centers)):
        if ci not in cluster_to_label:
            cluster_to_label[ci] = "balanced"
    return cluster_to_label


def run_ml_training(db: sqlite3.Connection) -> dict:
    """Main ML training job. Updates feature_vectors.style_label and driver_styles."""
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.linear_model import SGDClassifier
    from backend.analysis.ml.model_store import save_model, load_model, save_meta

    X, lap_ids, driver_ids = _load_feature_matrix(db)
    n = len(lap_ids)
    if n < 5:
        return {"error": f"Need at least 5 laps (have {n})"}

    # Fit or load scaler
    scaler = load_model("scaler")
    if scaler is None:
        scaler = StandardScaler()
        scaler.fit(X)
    X_scaled = scaler.transform(X)
    save_model("scaler", scaler)

    if n < 20:
        # Bootstrap: KMeans
        km = MiniBatchKMeans(n_clusters=min(4, n), random_state=42, n_init=3)
        raw_labels = km.fit_predict(X_scaled)
        save_model("kmeans", km)
        cluster_map = _map_clusters_to_labels(km, scaler, X_scaled)
        labels = [cluster_map.get(int(l), "balanced") for l in raw_labels]
    else:
        # Incremental SGD classifier
        clf = load_model("classifier")
        if clf is None:
            # Bootstrap first, then train classifier
            km = load_model("kmeans")
            if km is None:
                km = MiniBatchKMeans(n_clusters=4, random_state=42, n_init=3)
                km.fit(X_scaled[:min(n, 50)])
                save_model("kmeans", km)
            cluster_map = _map_clusters_to_labels(km, scaler, X_scaled)
            bootstrap_labels = [cluster_map.get(int(l), "balanced") for l in km.predict(X_scaled)]
            clf = SGDClassifier(loss="log_loss", random_state=42, max_iter=1)
            clf.partial_fit(X_scaled, bootstrap_labels, classes=_STYLE_LABELS)
        else:
            # Re-fit on all data with existing labels as pseudo-labels
            existing = db.execute(
                "SELECT lap_id, style_label FROM feature_vectors WHERE style_label IS NOT NULL"
            ).fetchall()
            label_map = {r["lap_id"]: r["style_label"] for r in existing}
            # Partial fit on laps that have labels
            labeled_X = [X_scaled[i] for i, lid in enumerate(lap_ids) if lid in label_map]
            labeled_y = [label_map[lid] for lid in lap_ids if lid in label_map]
            if len(labeled_X) >= 4:
                clf.partial_fit(np.array(labeled_X), labeled_y, classes=_STYLE_LABELS)
        save_model("classifier", clf)
        labels = clf.predict(X_scaled).tolist()

    # Update DB
    label_updates = list(zip(labels, lap_ids))
    db.executemany(
        "UPDATE feature_vectors SET style_label=? WHERE lap_id=?", label_updates
    )

    # Aggregate driver style (majority vote, weighted by recency)
    from collections import Counter
    driver_lap_labels: dict[int, list] = {}
    for lid, did, label in zip(lap_ids, driver_ids, labels):
        driver_lap_labels.setdefault(did, []).append(label)

    for driver_id, driver_labels in driver_lap_labels.items():
        # Recent laps weighted 2×
        n_d = len(driver_labels)
        recent = driver_labels[max(0, n_d - n_d//3):]
        weighted = driver_labels + recent
        counts = Counter(weighted)
        top_label = counts.most_common(1)[0][0]
        confidence = counts[top_label] / len(weighted) * 100
        n_sessions = db.execute(
            "SELECT COUNT(DISTINCT session_id) FROM laps WHERE driver_id=?", (driver_id,)
        ).fetchone()[0]
        db.execute(
            "INSERT INTO driver_styles(driver_id, style_label, confidence, sessions_analyzed) "
            "VALUES(?,?,?,?) ON CONFLICT(driver_id) DO UPDATE SET "
            "style_label=excluded.style_label, confidence=excluded.confidence, "
            "sessions_analyzed=excluded.sessions_analyzed, "
            "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')",
            (driver_id, top_label, round(confidence, 1), n_sessions),
        )

    save_meta(n)
    return {"laps_trained": n, "drivers_updated": len(driver_lap_labels)}
