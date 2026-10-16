"""
Evaluate the trained booster on the held-out test split and persist metrics.
"""

import os
import tempfile

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    log_loss,
    roc_auc_score,
)

from config import (
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    MODELS_PREFIX,
    RUN_ID,
    S3_BUCKET,
    s3_uri,
)
from utils import configure_logging, download_file, read_parquet, write_json

logger = configure_logging("evaluate")


def _download_model(run_id: str) -> str:
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "model.txt")
    key = f"{MODELS_PREFIX}/{run_id}/model.txt"
    try:
        download_file(S3_BUCKET, key, path)
    except Exception:  # noqa: BLE001 - fall back to latest promoted model
        logger.warning("%s not found; falling back to latest", key)
        download_file(S3_BUCKET, f"{MODELS_PREFIX}/latest/model.txt", path)
    return path


def main() -> None:
    import lightgbm as lgb

    features_uri = s3_uri(os.getenv("ML_FEATURES_PREFIX", "features/instacart"))
    test_df = read_parquet(f"{features_uri}/test")
    logger.info("Evaluating on %s rows", len(test_df))

    model_path = _download_model(RUN_ID)
    booster = lgb.Booster(model_file=model_path)

    X = test_df[FEATURE_COLUMNS]
    y = test_df[LABEL_COLUMN].astype(int)
    proba = booster.predict(X)

    metrics = {
        "run_id": RUN_ID,
        "stage": "evaluate",
        "n_test_rows": int(len(test_df)),
        "positive_rate": float(y.mean()),
        "roc_auc": float(roc_auc_score(y, proba)),
        "pr_auc": float(average_precision_score(y, proba)),
        "accuracy": float(accuracy_score(y, (proba >= 0.5).astype(int))),
        "log_loss": float(log_loss(y, np.clip(proba, 1e-7, 1 - 1e-7))),
    }
    logger.info("Evaluation metrics: %s", metrics)
    write_json(S3_BUCKET, f"{MODELS_PREFIX}/{RUN_ID}/eval_metrics.json", metrics)
    logger.info("Evaluation complete.")


if __name__ == "__main__":
    main()
