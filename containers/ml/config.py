"""
Shared configuration for the Instacart reorder-prediction pipeline.

All values are environment driven so the same image can run every ECS task
(ingest / preprocess / train / evaluate / deploy) with different overrides.
"""

import os


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Set ML_S3_BUCKET (and friends) on the ECS task definition."
        )
    return value


# --- AWS / storage ---------------------------------------------------------
AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
S3_BUCKET = _require("ML_S3_BUCKET")

RAW_PREFIX = os.getenv("ML_RAW_PREFIX", "raw/instacart")
PARQUET_PREFIX = os.getenv("ML_PARQUET_PREFIX", "parquet/instacart")
FEATURES_PREFIX = os.getenv("ML_FEATURES_PREFIX", "features/instacart")
MODELS_PREFIX = os.getenv("ML_MODELS_PREFIX", "models/instacart")

# --- Run knobs -------------------------------------------------------------
RUN_ID = os.getenv("ML_RUN_ID", "local")
# Fraction of *users* to keep. 1.0 = use everything that was uploaded.
SAMPLE_FRACTION = float(os.getenv("ML_SAMPLE_FRACTION", "0.1"))
RANDOM_SEED = int(os.getenv("ML_RANDOM_SEED", "42"))
# Hard cap on the number of prior interaction rows preprocess reads (0 = no
# cap). Bounds the candidate/feature table so runs stay small and cheap.
MAX_ROWS = int(os.getenv("ML_MAX_ROWS", "100000"))

# Train/val/test split by user bucket (user_id % 10).
VAL_BUCKETS = {8}
TEST_BUCKETS = {9}

# --- Training --------------------------------------------------------------
NUM_ITERATIONS = int(os.getenv("ML_NUM_ITERATIONS", "400"))
LEARNING_RATE = float(os.getenv("ML_LEARNING_RATE", "0.05"))
RAY_NUM_WORKERS = int(os.getenv("ML_RAY_NUM_WORKERS", "0"))  # 0 => auto
RAY_OBJECT_STORE_BYTES = int(
    os.getenv("ML_RAY_OBJECT_STORE_BYTES", "300000000")
)

# --- Serving ---------------------------------------------------------------
ECS_CLUSTER = os.getenv("ML_ECS_CLUSTER", "")
ECS_SERVICE = os.getenv("ML_ECS_SERVICE", "")

# Every numeric column the model consumes. Keep in sync with preprocess.py.
FEATURE_COLUMNS = [
    "times_bought",
    "reorder_rate",
    "avg_add_to_cart",
    "min_add_to_cart",
    "max_add_to_cart",
    "user_total_orders",
    "user_avg_days_between_orders",
    "user_reorder_rate",
    "times_bought_per_order",
    "days_since_last_purchase",
    "product_reorder_rate",
    "product_order_count",
    "product_avg_add_to_cart",
    "department_id",
    "aisle_id",
]
LABEL_COLUMN = "label"


def s3_uri(prefix: str) -> str:
    """Join the bucket with a prefix into an s3:// URI."""
    return f"s3://{S3_BUCKET}/{prefix.strip('/')}"
