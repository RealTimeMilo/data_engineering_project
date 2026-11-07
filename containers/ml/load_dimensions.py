"""
Load the Instacart dimension tables into the analytics Postgres.

`model_predictions` stores ids only; these small tables let Mode group by
product / aisle / department names.

Source (default): s3://<ML_S3_BUCKET>/raw/instacart/{products,aisles,departments}.csv
Local override:   DIMENSIONS_DIR=/path/to/instacart_data

Run as a one-off ECS task with the evaluate task definition, or locally:

    DIMENSIONS_DIR=./instacart_data ANALYTICS_DB_... python load_dimensions.py
"""

from __future__ import annotations

import io
import os

import pandas as pd

import analytics

PRODUCT_COLUMNS = ["product_id", "product_name", "aisle_id", "department_id"]
AISLE_COLUMNS = ["aisle_id", "aisle"]
DEPARTMENT_COLUMNS = ["department_id", "department"]

PRODUCT_DTYPES = {
    "product_id": "int64",
    "product_name": "str",
    "aisle_id": "int64",
    "department_id": "int64",
}
AISLE_DTYPES = {"aisle_id": "int64", "aisle": "str"}
DEPARTMENT_DTYPES = {"department_id": "int64", "department": "str"}


def _read(name: str, dtype: dict) -> pd.DataFrame:
    local = os.getenv("DIMENSIONS_DIR", "").strip()
    if local:
        path = os.path.join(local, f"{name}.csv")
        print(f"Reading {path}")
        return pd.read_csv(path, dtype=dtype)

    import boto3

    from config import AWS_REGION, S3_BUCKET

    key = f"raw/instacart/{name}.csv"
    print(f"Reading s3://{S3_BUCKET}/{key}")
    obj = boto3.client("s3", region_name=AWS_REGION).get_object(
        Bucket=S3_BUCKET, Key=key
    )
    return pd.read_csv(io.BytesIO(obj["Body"].read()), dtype=dtype)


def _upsert(cur, table: str, columns: list[str], frame: pd.DataFrame) -> int:
    from psycopg2.extras import execute_values

    rows = list(frame[columns].itertuples(index=False, name=None))
    updates = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in columns[1:]
    )
    statement = (
        f"INSERT INTO {analytics.SCHEMA}.{table} ({', '.join(columns)}) "
        f"VALUES %s ON CONFLICT ({columns[0]}) DO UPDATE SET {updates}"
    )
    execute_values(cur, statement, rows)
    return len(rows)


def main() -> None:
    products = _read("products", PRODUCT_DTYPES)
    aisles = _read("aisles", AISLE_DTYPES)
    departments = _read("departments", DEPARTMENT_DTYPES)

    with analytics.connect() as conn, conn.cursor() as cur:
        n_products = _upsert(cur, "dim_products", PRODUCT_COLUMNS, products)
        n_aisles = _upsert(cur, "dim_aisles", AISLE_COLUMNS, aisles)
        n_departments = _upsert(
            cur, "dim_departments", DEPARTMENT_COLUMNS, departments
        )

    print(
        f"Loaded dim_products={n_products} dim_aisles={n_aisles} "
        f"dim_departments={n_departments}"
    )


if __name__ == "__main__":
    main()
