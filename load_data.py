"""
load_data.py

Loads the public Instacart Market Basket Analysis CSVs into Postgres.
Download the dataset first from:
  https://www.kaggle.com/competitions/instacart-market-basket-analysis
and unzip it into a local `data/` folder so you have:
  data/departments.csv
  data/aisles.csv
  data/products.csv
  data/orders.csv
  data/order_products__prior.csv   (optional, large — only needed for the
                                     basket-prediction / recommendation angle)

Usage:
  python load_data.py --dsn "postgresql://user:pass@localhost:5432/instacart" --data-dir ./data
"""

import argparse
import csv
import io
import psycopg2


TABLES = [
    # (csv filename, table name, columns in file order)
    ("departments.csv", "departments", ["department_id", "department"]),
    ("aisles.csv", "aisles", ["aisle_id", "aisle"]),
    ("products.csv", "products",
     ["product_id", "product_name", "aisle_id", "department_id"]),
    ("orders.csv", "orders",
     ["order_id", "user_id", "eval_set", "order_number", "order_dow",
      "order_hour_of_day", "days_since_prior_order"]),
    # order_products is large (~30M rows for the "prior" file) — comment out
    # if you only want product-level hybrid search and not basket data.
    ("order_products__prior.csv", "order_products",
     ["order_id", "product_id", "add_to_cart_order", "reordered"]),
]


def copy_csv(conn, csv_path: str, table: str, columns: list[str]) -> None:
    """Fast bulk load using Postgres COPY instead of row-by-row INSERT."""
    with open(csv_path, "r", encoding="utf-8") as f:
        with conn.cursor() as cur:
            cols = ", ".join(columns)
            cur.copy_expert(
                f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv, HEADER true)",
                f,
            )
    conn.commit()
    print(f"  loaded {table} from {csv_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True, help="Postgres connection string")
    parser.add_argument("--data-dir", default="./data", help="Folder with Instacart CSVs")
    parser.add_argument("--schema", default="schema.sql", help="Path to schema.sql")
    parser.add_argument("--skip-order-products", action="store_true",
                         help="Skip the large order_products__prior.csv load")
    args = parser.parse_args()

    conn = psycopg2.connect(args.dsn)

    print("Applying schema...")
    with open(args.schema, "r") as f:
        with conn.cursor() as cur:
            cur.execute(f.read())
    conn.commit()

    print("Loading tables...")
    for filename, table, columns in TABLES:
        if args.skip_order_products and table == "order_products":
            print(f"  skipping {table} (--skip-order-products)")
            continue
        path = f"{args.data_dir.rstrip('/')}/{filename}"
        copy_csv(conn, path, table, columns)

    conn.close()
    print("Done. Next: run embed_products.py to populate the embedding column.")


if __name__ == "__main__":
    main()
