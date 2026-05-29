"""Loop closer — orchestrates the feedback loop.

Called periodically (every 500 requests) to:
1. Read real training data from request_store
2. Train the ML routing model
3. Persist health state to SQLite
4. Trigger eval gate promotions
"""

from __future__ import annotations

import logging
import time

_log = logging.getLogger(__name__)


def close_loop() -> dict:
    """Execute one cycle of the feedback loop. Returns diagnostics."""
    t0 = time.time()
    result = {
        "timestamp": t0,
        "training": False,
        "training_samples": 0,
        "training_loss": 0.0,
        "health_persisted": False,
        "store_count": 0,
    }

    # 1. Get request store stats
    try:
        from routing_loop.request_store import get_request_store
        store = get_request_store()
        result["store_count"] = store.count()
    except Exception as exc:
        _log.debug("close_loop: request_store unavailable: %s", exc)
        return result

    # 2. Train ML model with real data
    try:
        result["training"], result["training_samples"], result["training_loss"] = (
            _train_ml_model(store)
        )
    except Exception as exc:
        _log.debug("close_loop: ML training failed: %s", exc)

    # 3. Persist health state
    try:
        _persist_health_state()
        result["health_persisted"] = True
    except Exception as exc:
        _log.debug("close_loop: health persist failed: %s", exc)

    # 4. Trigger eval gate
    try:
        _trigger_eval_gate()
    except Exception as exc:
        _log.debug("close_loop: eval gate failed: %s", exc)

    duration_ms = (time.time() - t0) * 1000
    _log.info(
        "loop_closer: store=%d training=%s samples=%d loss=%.4f duration=%.0fms",
        result["store_count"], result["training"],
        result["training_samples"], result["training_loss"], duration_ms,
    )
    return result


def _train_ml_model(store) -> tuple[bool, int, float]:
    """Train the ML model using real request data from the store."""
    records = store.get_recent_features(n=500)
    if len(records) < 10:
        return False, 0, 0.0

    # Get unique backends from recent data
    backends = list(set(r.backend for r in records if r.backend))
    if len(backends) < 2:
        return False, 0, 0.0

    # Load or create model
    from routing_ml.routing_model import create_model, train_step
    from routing_ml.routing_trainer import get_model, MODEL_PATH

    model = get_model()
    if model is None or set(model.backend_names) != set(backends):
        model = create_model(backends)

    # Build training samples from real features
    backend_idx = {b: i for i, b in enumerate(model.backend_names)}
    losses = []
    import random
    for _ in range(3):  # 3 epochs
        random.shuffle(records)
        for rec in records[:200]:
            if not rec.feature_vector or rec.backend not in backend_idx:
                continue
            target = [0.0] * len(model.backend_names)
            target[backend_idx[rec.backend]] = 1.0 if rec.success else 0.3
            loss = train_step(model, rec.feature_vector, target, lr=0.0005)
            losses.append(loss)

    # Save model
    model.save(MODEL_PATH)
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    return True, len(records), avg_loss


def _persist_health_state() -> None:
    """Persist in-memory health state to SQLite for restart recovery."""
    try:
        from health_tracker import get_health_map, get_scores, get_latency_map
        import sqlite3, os

        db_path = os.path.join(
            os.environ.get("LIMA_DATA_DIR", "data"), "request_log.db"
        )
        conn = sqlite3.connect(db_path, timeout=5)
        conn.execute("""CREATE TABLE IF NOT EXISTS backend_health (
            backend TEXT PRIMARY KEY,
            state TEXT,
            score REAL,
            latency_ms REAL,
            last_updated REAL
        )""")
        conn.execute("DELETE FROM backend_health")

        health_map = get_health_map()
        scores = get_scores()
        latency_map = get_latency_map()

        for backend, state in health_map.items():
            conn.execute(
                "INSERT INTO backend_health VALUES (?, ?, ?, ?, ?)",
                (backend, state, scores.get(backend, 50),
                 latency_map.get(backend, 1500), time.time()),
            )
        conn.commit()
        conn.close()
    except Exception as exc:
        _log.debug("_persist_health_state: %s", exc)


def _trigger_eval_gate() -> None:
    """Try to auto-approve eval candidates that meet thresholds."""
    try:
        from session_memory.eval_gate import eval_candidates_from_memory, approve_candidate
        candidates = eval_candidates_from_memory()
        for c in candidates[:3]:
            if c.get("pass_rate", 0) >= 0.8 and c.get("total_tasks", 0) >= 3:
                approve_candidate(c.get("pattern_id", ""))
                _log.info("eval_gate: auto-approved pattern %s", c.get("pattern_id"))
    except Exception:
        pass
