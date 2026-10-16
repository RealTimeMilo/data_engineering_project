"""
Train the reorder ("buy again") classifier.

Ray Data is used to read/assemble the feature tables in parallel, then a single
LightGBM booster is trained on the driver. For the sampled dataset produced by
preprocess.py this is faster and far more robust on a single Fargate task than
distributed LightGBM (which hangs on Ray's equal row split here).

Writes the booster + metrics to s3://<bucket>/<models_prefix>/<run_id>/.
"""

import os
import tempfile

import lightgbm as lgb
import ray

from config import (
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    LEARNING_RATE,
    MODELS_PREFIX,
    NUM_ITERATIONS,
    RAY_OBJECT_STORE_BYTES,
    RUN_ID,
    S3_BUCKET,
    s3_uri,
)
from utils import configure_logging, upload_file, write_json

logger = configure_logging("train")


def main() -> None:
    ray.init(
        ignore_reinit_error=True,
        object_store_memory=RAY_OBJECT_STORE_BYTES,
        logging_level="WARNING",
        include_dashboard=False,
    )

    features_uri = s3_uri(os.getenv("ML_FEATURES_PREFIX", "features/instacart"))
    keep = FEATURE_COLUMNS + [LABEL_COLUMN]
    logger.info("Loading feature tables with Ray Data...")
    train_pd = (
        ray.data.read_parquet(f"{features_uri}/train").select_columns(keep).to_pandas()
    )
    valid_pd = (
        ray.data.read_parquet(f"{features_uri}/val").select_columns(keep).to_pandas()
    )
    logger.info("train rows=%s valid rows=%s", len(train_pd), len(valid_pd))

    params = {
        "objective": "binary",
        "metric": ["auc", "average_precision"],
        "learning_rate": LEARNING_RATE,
        "num_leaves": 63,
        "min_data_in_leaf": 100,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.8,
        "bagging_freq": 1,
        "max_depth": -1,
        "verbosity": -1,
    }

    dtrain = lgb.Dataset(train_pd[FEATURE_COLUMNS], label=train_pd[LABEL_COLUMN])
    dvalid = lgb.Dataset(
        valid_pd[FEATURE_COLUMNS],
        label=valid_pd[LABEL_COLUMN],
        reference=dtrain,
    )

    logger.info("Training LightGBM for up to %s rounds...", NUM_ITERATIONS)
    booster = lgb.train(
        params,
        dtrain,
        num_boost_round=NUM_ITERATIONS,
        valid_sets=[dvalid],
        valid_names=["valid"],
        callbacks=[lgb.log_evaluation(50), lgb.early_stopping(50)],
    )
    best = {
        metric: float(value)
        for metric, value in (booster.best_score.get("valid", {}) or {}).items()
    }
    logger.info("Best iteration=%s metrics=%s", booster.best_iteration, best)

    run_dir = f"{MODELS_PREFIX}/{RUN_ID}"
    with tempfile.TemporaryDirectory() as tmp:
        model_path = os.path.join(tmp, "model.txt")
        booster.save_model(model_path)
        upload_file(model_path, S3_BUCKET, f"{run_dir}/model.txt")

        importance = booster.feature_importance(importance_type="gain")
        write_json(
            S3_BUCKET,
            f"{run_dir}/metrics.json",
            {
                "run_id": RUN_ID,
                "stage": "train",
                "num_iterations": NUM_ITERATIONS,
                "best_iteration": booster.best_iteration,
                "learning_rate": LEARNING_RATE,
                "train_rows": int(len(train_pd)),
                "valid_rows": int(len(valid_pd)),
                "best_metrics": best,
                "feature_importance": dict(
                    sorted(
                        zip(FEATURE_COLUMNS, importance.tolist()),
                        key=lambda kv: kv[1],
                        reverse=True,
                    )
                ),
            },
        )

    ray.shutdown()
    logger.info("Training complete. Artifacts: s3://%s/%s", S3_BUCKET, run_dir)


if __name__ == "__main__":
    main()
