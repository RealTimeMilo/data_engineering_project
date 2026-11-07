"""
Publish pipeline telemetry to the analytics Postgres that Mode Analytics reads.

Tables (schema ``ml_analytics``, created by ``bootstrap_analytics.py``):
    pipeline_runs      one row per Airflow run, with status + params
    model_metrics      one row per (run, stage, metric)
    model_predictions  one row per scored test (user, product) pair

All writes are best-effort: a database outage logs a warning and leaves the ML
artifacts in S3 untouched. Set ``ANALYTICS_REQUIRED=true`` to make it fatal.

Environment
-----------
ANALYTICS_DB_HOST / PORT / NAME / USER / PASSWORD / SSLMODE
ANALYTICS_REQUIRED   "true" to raise instead of warning
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Iterable

logger = logging.getLogger("analytics")

HOST = os.getenv("ANALYTICS_DB_HOST", "").strip()
PORT = int(os.getenv("ANALYTICS_DB_PORT", "5432"))
NAME = os.getenv("ANALYTICS_DB_NAME", "analytics")
USER = os.getenv("ANALYTICS_DB_USER", "ml_writer")
PASSWORD = os.getenv("ANALYTICS_DB_PASSWORD", "")
SSLMODE = os.getenv("ANALYTICS_DB_SSLMODE", "require")
REQUIRED = os.getenv("ANALYTICS_REQUIRED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
DAG_ID = os.getenv("ML_DAG_ID", "")

SCHEMA = "ml_analytics"


def enabled() -> bool:
    return bool(HOST)


def _warn(exc: Exception) -> None:
    if REQUIRED:
        raise exc
    logger.warning("Analytics write skipped: %s", exc)


def connect():
    """Open a psycopg2 connection to the analytics database."""
    import psycopg2

    return psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname=NAME,
        user=USER,
        password=PASSWORD,
        sslmode=SSLMODE,
        connect_timeout=10,
        application_name="instacart-ml",
    )


def _ensure_run(cur, run_id: str, params: dict[str, Any] | None = None) -> None:
    cur.execute(
        f"""
        INSERT INTO {SCHEMA}.pipeline_runs (run_id, dag_id, status, params)
        VALUES (%s, %s, 'running', %s::jsonb)
        ON CONFLICT (run_id) DO UPDATE
          SET dag_id = COALESCE(EXCLUDED.dag_id, {SCHEMA}.pipeline_runs.dag_id),
              params = {SCHEMA}.pipeline_runs.params || EXCLUDED.params
        """,
        (run_id, DAG_ID or None, json.dumps(params or {}, default=str)),
    )


def start_run(run_id: str, params: dict[str, Any] | None = None) -> None:
    if not enabled():
        return
    try:
        with connect() as conn, conn.cursor() as cur:
            _ensure_run(cur, run_id, params)
    except Exception as exc:  # noqa: BLE001
        _warn(exc)


def record_metrics(run_id: str, stage: str, metrics: dict[str, Any]) -> None:
    """Upsert numeric metrics for one stage."""
    if not enabled() or not metrics:
        return
    rows = [
        (run_id, stage, str(key), float(value))
        for key, value in metrics.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    if not rows:
        return
    try:
        from psycopg2.extras import execute_values

        with connect() as conn, conn.cursor() as cur:
            _ensure_run(cur, run_id)
            execute_values(
                cur,
                f"""
                INSERT INTO {SCHEMA}.model_metrics (run_id, stage, metric, value)
                VALUES %s
                ON CONFLICT (run_id, stage, metric) DO UPDATE
                  SET value = EXCLUDED.value, recorded_at = now()
                """,
                rows,
            )
    except Exception as exc:  # noqa: BLE001
        _warn(exc)


def record_predictions(
    run_id: str,
    user_ids: Iterable[Any],
    product_ids: Iterable[Any],
    labels: Iterable[Any],
    probabilities: Iterable[Any],
    chunk_size: int = 1000,
) -> None:
    """Upsert scored test-set pairs (idempotent per run)."""
    if not enabled():
        return
    rows = [
        (run_id, int(u), int(p), int(l) if l is not None else None, float(prob))
        for u, p, l, prob in zip(user_ids, product_ids, labels, probabilities)
    ]
    if not rows:
        return
    try:
        from psycopg2.extras import execute_values

        with connect() as conn, conn.cursor() as cur:
            _ensure_run(cur, run_id)
            for start in range(0, len(rows), chunk_size):
                execute_values(
                    cur,
                    f"""
                    INSERT INTO {SCHEMA}.model_predictions
                      (run_id, user_id, product_id, label, reorder_probability)
                    VALUES %s
                    ON CONFLICT (run_id, user_id, product_id) DO UPDATE
                      SET label = EXCLUDED.label,
                          reorder_probability = EXCLUDED.reorder_probability,
                          scored_at = now()
                    """,
                    rows[start : start + chunk_size],
                )
    except Exception as exc:  # noqa: BLE001
        _warn(exc)


def finish_run(
    run_id: str,
    status: str = "succeeded",
    extra_metrics: dict[str, Any] | None = None,
    mlflow_run_id: str | None = None,
) -> None:
    if not enabled():
        return
    if extra_metrics:
        record_metrics(run_id, "deploy", extra_metrics)
    try:
        with connect() as conn, conn.cursor() as cur:
            _ensure_run(cur, run_id)
            cur.execute(
                f"""
                UPDATE {SCHEMA}.pipeline_runs
                   SET status = %s,
                       finished_at = now(),
                       mlflow_run_id = COALESCE(%s, mlflow_run_id)
                 WHERE run_id = %s
                """,
                (status, mlflow_run_id, run_id),
            )
    except Exception as exc:  # noqa: BLE001
        _warn(exc)
