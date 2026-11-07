"""
MLflow logging for the Instacart pipeline.

Targets a Databricks-hosted MLflow tracking server (or any MLflow server) and is
fully optional: when ``MLFLOW_TRACKING_URI`` is empty every call becomes a no-op,
and a tracking-server outage is only fatal when ``MLFLOW_REQUIRED=true``.

Grouping model
--------------
One *parent* run per pipeline run (named after ``ML_RUN_ID``) carries the
``ml_run_id`` tag. Each stage logs to its own run linked with the reserved
``mlflow.parentRunId`` tag, so the MLflow UI shows ingest / preprocess / train /
evaluate / deploy nested under the pipeline run.

Environment
-----------
MLFLOW_TRACKING_URI       e.g. https://dbc-xxxx.cloud.databricks.com or "databricks"
MLFLOW_TRACKING_TOKEN     Databricks PAT (injected as an ECS secret from SSM)
MLFLOW_EXPERIMENT_NAME    default "/Shared/instacart-reorder"
MLFLOW_MODEL_NAME         registered-model name (only used when MLFLOW_LOG_MODEL=true)
MLFLOW_PARENT_RUN_ID      resume/attach to an existing parent run
MLFLOW_REQUIRED           "true" to fail the task when logging fails
MLFLOW_LOG_MODEL          "true" to log a pyfunc model instead of the raw booster
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager
from typing import Any, Iterator

from config import RUN_ID

logger = logging.getLogger("mlflow")

TRACKING_URI = (os.getenv("MLFLOW_TRACKING_URI") or "").strip()
TRACKING_TOKEN = (os.getenv("MLFLOW_TRACKING_TOKEN") or "").strip()
EXPERIMENT_NAME = (
    os.getenv("MLFLOW_EXPERIMENT_NAME") or "/Shared/instacart-reorder"
).strip()
MODEL_NAME = os.getenv("MLFLOW_MODEL_NAME", "instacart-reorder")
RUN_NAME = (os.getenv("MLFLOW_RUN_NAME") or RUN_ID).strip()
DAG_ID = os.getenv("ML_DAG_ID", "")
REQUIRED = os.getenv("MLFLOW_REQUIRED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
LOG_MODEL = os.getenv("MLFLOW_LOG_MODEL", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_PARENT_RUN_ID = (os.getenv("MLFLOW_PARENT_RUN_ID") or "").strip() or None
_EXPERIMENT_ID = ""
_CONFIGURED = False

# MLflow rejects a handful of characters in metric/param keys.
_BAD_KEY = re.compile(r"[^A-Za-z0-9_.\-]")


def enabled() -> bool:
    return bool(TRACKING_URI)


def _warn(exc: Exception) -> None:
    if REQUIRED:
        raise exc
    logger.warning("MLflow logging skipped: %s", exc)


def _configure():
    """Import and configure MLflow once. Raises on import/config failure."""
    global _CONFIGURED
    import mlflow  # imported lazily so the cost is only paid when enabled

    if _CONFIGURED:
        return mlflow

    # Keep a Databricks outage from hanging a Fargate task indefinitely.
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "30")
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "2")

    if TRACKING_TOKEN:
        os.environ.setdefault("MLFLOW_TRACKING_TOKEN", TRACKING_TOKEN)
        os.environ.setdefault("DATABRICKS_TOKEN", TRACKING_TOKEN)

    uri = TRACKING_URI.rstrip("/")
    if uri == "databricks":
        host = os.getenv("MLFLOW_DATABRICKS_HOST") or os.getenv("DATABRICKS_HOST", "")
        if host:
            os.environ.setdefault("DATABRICKS_HOST", host)
    elif "databricks.com" in uri:
        # Artifact uploads (dbfs:/...) resolve credentials through the
        # DATABRICKS_* variables even when the tracking URI is the workspace URL.
        os.environ.setdefault("DATABRICKS_HOST", uri)

    mlflow.set_tracking_uri(uri)

    if os.getenv("MLFLOW_TRACKING_USERNAME") and os.getenv("MLFLOW_TRACKING_PASSWORD"):
        # Basic auth servers: MLflow reads these from the environment directly.
        pass

    global _EXPERIMENT_ID
    experiment = mlflow.set_experiment(EXPERIMENT_NAME)
    _EXPERIMENT_ID = str(getattr(experiment, "experiment_id", "") or "")
    _CONFIGURED = True
    logger.info("MLflow tracking URI=%s experiment=%s", uri, EXPERIMENT_NAME)
    return mlflow


def _metric_key(key: str) -> str:
    return _BAD_KEY.sub("_", str(key))[:250]


def _flatten(payload: dict[str, Any], prefix: str = "") -> dict[str, float]:
    """Flatten a nested dict to numeric {metric: value} pairs."""
    out: dict[str, float] = {}
    for key, value in payload.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(_flatten(value, f"{name}."))
        elif isinstance(value, bool):
            out[_metric_key(name)] = 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            out[_metric_key(name)] = float(value)
    return out


def _scalar_params(payload: dict[str, Any]) -> dict[str, Any]:
    """MLflow params must be scalars; stringify everything else."""
    out: dict[str, Any] = {}
    for key, value in payload.items():
        name = _metric_key(key)
        if isinstance(value, (str, int, float, bool)):
            out[name] = value
        else:
            out[name] = str(value)
    return out


def _parent_tags() -> dict[str, str]:
    tags = {"ml_run_id": RUN_ID, "stage": "pipeline", "source": "airflow-ecs"}
    if DAG_ID:
        tags["dag_id"] = DAG_ID
    return tags


def ensure_pipeline_run() -> str:
    """Return the parent run id, creating (or re-finding) the pipeline run."""
    global _PARENT_RUN_ID
    if _PARENT_RUN_ID:
        return _PARENT_RUN_ID

    mlflow = _configure()
    experiment = mlflow.set_experiment(EXPERIMENT_NAME)
    experiment_id = getattr(experiment, "experiment_id", None)
    if not experiment_id:
        raise RuntimeError(f"MLflow experiment not found: {EXPERIMENT_NAME}")

    client = mlflow.tracking.MlflowClient()
    try:
        found = client.search_runs(
            [experiment_id],
            filter_string=(
                f"tags.ml_run_id = '{RUN_ID}' and tags.stage = 'pipeline'"
            ),
            max_results=1,
            order_by=["attributes.start_time DESC"],
        )
        if found:
            _PARENT_RUN_ID = found[0].info.run_id
            logger.info("Reusing MLflow pipeline run %s", _PARENT_RUN_ID)
            return _PARENT_RUN_ID
    except Exception as exc:  # noqa: BLE001 - search is best-effort
        logger.debug("MLflow run search failed: %s", exc)

    run = client.create_run(
        experiment_id,
        run_name=RUN_NAME,
        tags=_parent_tags(),
    )
    _PARENT_RUN_ID = run.info.run_id
    logger.info("Created MLflow pipeline run %s (%s)", _PARENT_RUN_ID, RUN_NAME)
    return _PARENT_RUN_ID


class Recorder:
    """Thin, failure-tolerant wrapper around an active MLflow run."""

    def __init__(self, mlflow=None) -> None:
        self._mlflow = mlflow

    @property
    def active(self) -> bool:
        return self._mlflow is not None

    def log_params(self, params: dict[str, Any]) -> None:
        if not self._mlflow or not params:
            return
        try:
            self._mlflow.log_params(_scalar_params(params))
        except Exception as exc:  # noqa: BLE001
            _warn(exc)

    def log_metrics(self, metrics: dict[str, Any], prefix: str = "") -> None:
        if not self._mlflow or not metrics:
            return
        flat = _flatten(metrics, prefix)
        items = list(flat.items())
        try:
            for start in range(0, len(items), 100):
                self._mlflow.log_metrics(dict(items[start : start + 100]))
        except Exception as exc:  # noqa: BLE001
            _warn(exc)

    def set_tags(self, tags: dict[str, Any]) -> None:
        if not self._mlflow or not tags:
            return
        try:
            self._mlflow.set_tags({str(k): str(v) for k, v in tags.items()})
        except Exception as exc:  # noqa: BLE001
            _warn(exc)

    def log_artifact(self, local_path: str, artifact_path: str | None = None) -> None:
        if not self._mlflow:
            return
        try:
            self._mlflow.log_artifact(local_path, artifact_path=artifact_path)
        except Exception as exc:  # noqa: BLE001
            _warn(exc)

    def log_dict(self, payload: dict[str, Any], artifact_file: str) -> None:
        if not self._mlflow:
            return
        try:
            self._mlflow.log_dict(payload, artifact_file)
        except Exception as exc:  # noqa: BLE001
            _warn(exc)

    def log_text(self, text: str, artifact_file: str) -> None:
        if not self._mlflow:
            return
        try:
            self._mlflow.log_text(text, artifact_file)
        except Exception as exc:  # noqa: BLE001
            _warn(exc)

    def log_model(self, booster, model_path: str, artifact_path: str = "model") -> None:
        """Log the LightGBM booster, falling back to a plain artifact."""
        if not self._mlflow:
            return
        try:
            if LOG_MODEL:
                self._mlflow.lightgbm.log_model(booster, artifact_path=artifact_path)
            else:
                # A plain artifact works against every tracking server (including
                # Databricks) without requiring model-registry permissions.
                self._mlflow.log_artifact(model_path, artifact_path=artifact_path)
        except Exception as exc:  # noqa: BLE001
            _warn(exc)


_NULL = Recorder(None)


@contextmanager
def stage(
    name: str,
    params: dict[str, Any] | None = None,
    tags: dict[str, Any] | None = None,
) -> Iterator[Recorder]:
    """Open an MLflow child run for one pipeline stage."""
    if not enabled():
        yield _NULL
        return

    try:
        mlflow = _configure()
        parent_id = ensure_pipeline_run()
        run_tags = {
            "ml_run_id": RUN_ID,
            "stage": name,
            "mlflow.parentRunId": parent_id,
        }
        if DAG_ID:
            run_tags["dag_id"] = DAG_ID
        for key, value in (tags or {}).items():
            run_tags[str(key)] = str(value)
        mlflow.start_run(run_name=name, tags=run_tags)
    except Exception as exc:  # noqa: BLE001 - setup failure
        _warn(exc)
        yield _NULL
        return

    recorder = Recorder(mlflow)
    try:
        if params:
            recorder.log_params(params)
        yield recorder
    finally:
        try:
            mlflow.end_run()
        except Exception as exc:  # noqa: BLE001
            _warn(exc)


def finish_pipeline(status: str = "FINISHED") -> None:
    """Terminate the parent pipeline run (call from the last stage)."""
    if not enabled():
        return
    try:
        mlflow = _configure()
        parent_id = ensure_pipeline_run()
        mlflow.tracking.MlflowClient().set_terminated(parent_id, status=status)
        logger.info("MLflow pipeline run %s -> %s", parent_id, status)
    except Exception as exc:  # noqa: BLE001
        _warn(exc)


def run_url() -> str:
    """Best-effort URL for the pipeline run (printed at the end of a stage)."""
    if not enabled() or not _PARENT_RUN_ID:
        return ""
    base = TRACKING_URI.rstrip("/")
    if base == "databricks":
        return ""
    experiment = _EXPERIMENT_ID or EXPERIMENT_NAME.strip("/")
    return f"{base}/#/experiments/{experiment}/runs/{_PARENT_RUN_ID}"
