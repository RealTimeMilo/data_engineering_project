"""
Feature engineering for reorder ("buy again") prediction using Ray Data.

Heavy aggregations over the prior interactions (the largest table) run as Ray
Dataset group-bys, which are parallelized across the Fargate task's vCPUs.
The aggregated candidate table is small enough to finish in pandas, where we
join user / product / catalogue features and the train-derived label.

Candidate = every (user, product) pair the user bought before.
Label      = 1 if that product is present in the user's `train` order.

Only the first ML_MAX_ROWS prior interactions are read (0 disables the cap), so
runs stay small and cheap; the resulting candidate/feature table is therefore
also bounded by ML_MAX_ROWS rows.

Outputs train/validation/test parquet under ML_FEATURES_PREFIX. Splits are by
user (user_id % 10) so no user leaks across splits.
"""

import pandas as pd
import ray

try:  # standard public location
    from ray.data.aggregate import Count, Max, Mean, Min
except ImportError:  # Ray 2.40 keeps the concrete aggs under _internal
    from ray.data._internal.aggregate import Count, Max, Mean, Min

from config import (
    FEATURE_COLUMNS,
    FEATURES_PREFIX,
    LABEL_COLUMN,
    MAX_ROWS,
    PARQUET_PREFIX,
    RAY_OBJECT_STORE_BYTES,
    TEST_BUCKETS,
    VAL_BUCKETS,
    s3_uri,
)
from utils import configure_logging, read_parquet, write_parquet

logger = configure_logging("preprocess")


def _init_ray() -> None:
    ray.init(
        ignore_reinit_error=True,
        object_store_memory=RAY_OBJECT_STORE_BYTES,
        logging_level="WARNING",
        include_dashboard=False,
    )
    logger.info("Ray initialized with resources: %s", ray.cluster_resources())


# Default column names produced by Ray's aggregators when alias_name is not
# honored. Used as a fallback so downstream column names are stable.
_CANDIDATE_RENAME = {
    "mean(reordered)": "reorder_rate",
    "mean(add_to_cart_order)": "avg_add_to_cart",
    "min(add_to_cart_order)": "min_add_to_cart",
    "max(add_to_cart_order)": "max_add_to_cart",
    "max(order_number)": "pair_max_order_number",
}
_USER_RENAME = {"mean(reordered)": "user_reorder_rate", "max(order_number)": "user_max_order_number"}
_PRODUCT_RENAME = {
    "mean(reordered)": "product_reorder_rate",
    "mean(add_to_cart_order)": "product_avg_add_to_cart",
}


def _finalize(frame, mapping: dict, count_name: str):
    """Apply fallback renames and normalize the Count() output column."""
    frame = frame.rename(columns=mapping)
    for col in list(frame.columns):
        key = str(col).strip().lower()
        if key not in ("user_id", "product_id") and key.startswith("count"):
            frame = frame.rename(columns={col: count_name})
    return frame


def _candidate_features(prior_path: str) -> tuple:
    ds = ray.data.read_parquet(prior_path)
    if MAX_ROWS > 0:
        ds = ds.limit(MAX_ROWS)
    ds = ds.repartition(16)

    candidates = ds.groupby(["user_id", "product_id"]).aggregate(
        Count(),
        Mean("reordered", alias_name="reorder_rate"),
        Mean("add_to_cart_order", alias_name="avg_add_to_cart"),
        Min("add_to_cart_order", alias_name="min_add_to_cart"),
        Max("add_to_cart_order", alias_name="max_add_to_cart"),
        Max("order_number", alias_name="pair_max_order_number"),
    )
    user_aggs = ds.groupby("user_id").aggregate(
        Mean("reordered", alias_name="user_reorder_rate"),
        Max("order_number", alias_name="user_max_order_number"),
    )
    product_aggs = ds.groupby("product_id").aggregate(
        Count(),
        Mean("reordered", alias_name="product_reorder_rate"),
        Mean("add_to_cart_order", alias_name="product_avg_add_to_cart"),
    )

    candidates = _finalize(candidates.to_pandas(), _CANDIDATE_RENAME, "times_bought")
    user_aggs = _finalize(user_aggs.to_pandas(), _USER_RENAME, "user_count")
    product_aggs = _finalize(product_aggs.to_pandas(), _PRODUCT_RENAME, "product_order_count")
    return candidates, user_aggs, product_aggs


def main() -> None:
    parquet = s3_uri(PARQUET_PREFIX)
    features_uri = s3_uri(FEATURES_PREFIX)

    _init_ray()

    candidates, user_aggs, product_aggs = _candidate_features(
        f"{parquet}/prior.parquet"
    )
    logger.info("Candidate rows: %s", len(candidates))

    orders = read_parquet(f"{parquet}/orders.parquet")
    prior_orders = orders[orders["eval_set"] == "prior"]
    total_orders = (
        prior_orders.groupby("user_id")["order_id"].nunique().rename("user_total_orders")
    )
    avg_days = (
        prior_orders.groupby("user_id")["days_since_prior_order"]
        .mean()
        .rename("user_avg_days_between_orders")
    )

    products = read_parquet(f"{parquet}/products.parquet")[
        ["product_id", "aisle_id", "department_id"]
    ]

    train = read_parquet(f"{parquet}/train.parquet")
    labels = (
        train.groupby(["user_id", "product_id"])
        .size()
        .rename(LABEL_COLUMN)
        .reset_index()
    )
    labels[LABEL_COLUMN] = 1

    df = candidates.merge(user_aggs, on="user_id", how="left")
    df = df.merge(product_aggs, on="product_id", how="left")
    df = df.merge(products, on="product_id", how="left")
    df = df.merge(total_orders, on="user_id", how="left")
    df = df.merge(avg_days, on="user_id", how="left")
    df = df.merge(labels, on=["user_id", "product_id"], how="left")
    df[LABEL_COLUMN] = df[LABEL_COLUMN].fillna(0).astype("int8")

    # --- derived features --------------------------------------------------
    df["times_bought_per_order"] = (
        df["times_bought"] / df["user_total_orders"].clip(lower=1)
    )
    df["days_since_last_purchase"] = (
        df["user_max_order_number"] - df["pair_max_order_number"]
    )

    df = df.dropna(subset=["user_total_orders"])
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            raise ValueError(f"Missing expected feature column: {col}")
        df[col] = df[col].astype("float32")

    logger.info("Final feature matrix: %s", df.shape)
    logger.info("Positive rate: %.4f", df[LABEL_COLUMN].mean())

    # --- user-based split --------------------------------------------------
    bucket = df["user_id"] % 10
    train_df = df[~bucket.isin(VAL_BUCKETS | TEST_BUCKETS)]
    val_df = df[bucket.isin(VAL_BUCKETS)]
    test_df = df[bucket.isin(TEST_BUCKETS)]

    keep = FEATURE_COLUMNS + [LABEL_COLUMN, "user_id", "product_id"]
    write_parquet(train_df[keep], f"{features_uri}/train")
    write_parquet(val_df[keep], f"{features_uri}/val")
    write_parquet(test_df[keep], f"{features_uri}/test")
    logger.info(
        "Split sizes -> train=%s val=%s test=%s",
        len(train_df),
        len(val_df),
        len(test_df),
    )

    # --- Feast offline store ----------------------------------------------
    # Single parquet with an event timestamp so Feast can materialize it into
    # the Postgres online store.
    df["event_timestamp"] = pd.Timestamp.utcnow()
    offline_cols = ["user_id", "product_id", "event_timestamp"] + FEATURE_COLUMNS + [LABEL_COLUMN]
    write_parquet(df[offline_cols], f"{features_uri}/offline/features.parquet")

    ray.shutdown()
    logger.info("Preprocess complete.")


if __name__ == "__main__":
    main()
