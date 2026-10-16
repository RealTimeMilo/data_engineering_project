"""
Ingest Instacart CSVs from S3 into parquet, optionally sampling.

The order_products files are read in chunks and filtered to the sampled orders
so the job never has to hold the full ~550 MB prior table in memory.

Outputs (under ML_PARQUET_PREFIX):
    orders.parquet      -- orders filtered to the sampled users (with eval_set)
    prior.parquet       -- order_products__prior enriched with user_id/order_number
    train.parquet       -- order_products__train enriched with user_id
    products.parquet / aisles.parquet / departments.parquet

Sampling is at the *user* level so feature/label pairs stay consistent.
"""

import numpy as np
import pandas as pd

from config import (
    PARQUET_PREFIX,
    RANDOM_SEED,
    RAW_PREFIX,
    SAMPLE_FRACTION,
    s3_uri,
)
from utils import configure_logging, read_csv, write_parquet

logger = configure_logging("ingest")

ORDERS_DTYPES = {
    "order_id": "int32",
    "user_id": "int32",
    "eval_set": "category",
    "order_number": "int8",
    "order_dow": "int8",
    "order_hour_of_day": "int8",
    "days_since_prior_order": "float32",
}
OP_DTYPES = {
    "order_id": "int32",
    "product_id": "int32",
    "add_to_cart_order": "int16",
    "reordered": "int8",
}
PRODUCTS_DTYPES = {
    "product_id": "int32",
    "product_name": "str",
    "aisle_id": "int16",
    "department_id": "int8",
}
AISLES_DTYPES = {"aisle_id": "int16", "aisle": "str"}
DEPARTMENTS_DTYPES = {"department_id": "int8", "department": "str"}


def _read_filtered(name: str, dtype: dict, order_ids: set) -> pd.DataFrame:
    """Read an order_products CSV in chunks, keeping only sampled order ids."""
    path = f"{s3_uri(RAW_PREFIX)}/{name}.csv"
    chunks = []
    reader = pd.read_csv(path, dtype=dtype, chunksize=2_000_000)
    for chunk in reader:
        kept = chunk[chunk["order_id"].isin(order_ids)]
        if not kept.empty:
            chunks.append(kept)
    return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(columns=dtype)


def main() -> None:
    raw = s3_uri(RAW_PREFIX)
    out = s3_uri(PARQUET_PREFIX)
    logger.info("Ingesting from %s -> %s (sample_fraction=%s)", raw, out, SAMPLE_FRACTION)

    orders = read_csv(f"{raw}/orders.csv", dtype=ORDERS_DTYPES)
    products = read_csv(f"{raw}/products.csv", dtype=PRODUCTS_DTYPES)
    aisles = read_csv(f"{raw}/aisles.csv", dtype=AISLES_DTYPES)
    departments = read_csv(f"{raw}/departments.csv", dtype=DEPARTMENTS_DTYPES)

    train_users = orders.loc[orders["eval_set"] == "train", "user_id"].unique()
    if SAMPLE_FRACTION < 1.0:
        rng = np.random.default_rng(RANDOM_SEED)
        n = max(1, int(len(train_users) * SAMPLE_FRACTION))
        sample_users = rng.choice(train_users, size=n, replace=False)
        logger.info(
            "Sampling %s of %s users (fraction=%s)",
            len(sample_users), len(train_users), SAMPLE_FRACTION,
        )
    else:
        sample_users = train_users

    orders = orders[orders["user_id"].isin(sample_users)].copy()
    prior_order_ids = set(orders.loc[orders["eval_set"] == "prior", "order_id"].tolist())
    train_order_ids = set(orders.loc[orders["eval_set"] == "train", "order_id"].tolist())
    logger.info("Sampled prior orders=%s train orders=%s", len(prior_order_ids), len(train_order_ids))

    user_to_order = orders[["order_id", "user_id", "order_number"]]
    train_users_map = orders.loc[orders["eval_set"] == "train", ["order_id", "user_id"]]

    prior = _read_filtered("order_products__prior", OP_DTYPES, prior_order_ids)
    prior = prior.merge(user_to_order, on="order_id", how="inner")
    logger.info("prior interactions kept: %s", len(prior))

    train = _read_filtered("order_products__train", OP_DTYPES, train_order_ids)
    train = train.merge(train_users_map, on="order_id", how="inner")
    logger.info("train interactions kept: %s", len(train))

    write_parquet(orders, f"{out}/orders.parquet")
    write_parquet(prior, f"{out}/prior.parquet")
    write_parquet(train, f"{out}/train.parquet")
    write_parquet(products, f"{out}/products.parquet")
    write_parquet(aisles, f"{out}/aisles.parquet")
    write_parquet(departments, f"{out}/departments.parquet")

    logger.info("Ingest complete.")


if __name__ == "__main__":
    main()
