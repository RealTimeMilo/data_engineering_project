"""
Create a user-level sample of the Instacart CSVs locally before uploading.

    python scripts/sample_instacart.py --fraction 0.1

Reads raw CSVs from --src (default: instacart_data) and writes sampled CSVs to
--out (default: instacart_data/sample). Sampling is by user_id and matches the
sampling logic in containers/ml/ingest.py, so uploading the sample instead of
the full ~700 MB is equivalent (just cheaper).
"""

import argparse
import os

import numpy as np
import pandas as pd

FILES = [
    "orders.csv",
    "products.csv",
    "aisles.csv",
    "departments.csv",
    "order_products__prior.csv",
    "order_products__train.csv",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default="instacart_data")
    parser.add_argument("--out", default="instacart_data/sample")
    parser.add_argument("--fraction", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    orders = pd.read_csv(
        os.path.join(args.src, "orders.csv"),
        dtype={"order_id": "int32", "user_id": "int32", "eval_set": "category"},
    )
    train_users = orders.loc[orders["eval_set"] == "train", "user_id"].unique()
    rng = np.random.default_rng(args.seed)
    n = max(1, int(len(train_users) * args.fraction))
    sample_users = set(rng.choice(train_users, size=n, replace=False).tolist())
    print(f"Keeping {len(sample_users):,} of {len(train_users):,} users")

    orders = orders[orders["user_id"].isin(sample_users)]
    order_ids = set(orders["order_id"].tolist())
    orders.to_csv(os.path.join(args.out, "orders.csv"), index=False)

    # Catalogue tables are small - copy them through unchanged.
    for name in ["products.csv", "aisles.csv", "departments.csv"]:
        pd.read_csv(os.path.join(args.src, name)).to_csv(
            os.path.join(args.out, name), index=False
        )

    for name in ["order_products__prior.csv", "order_products__train.csv"]:
        chunks = []
        for chunk in pd.read_csv(
            os.path.join(args.src, name),
            dtype={"order_id": "int32", "product_id": "int32"},
            chunksize=2_000_000,
        ):
            chunks.append(chunk[chunk["order_id"].isin(order_ids)])
        pd.concat(chunks, ignore_index=True).to_csv(
            os.path.join(args.out, name), index=False
        )
        print(f"Wrote {name}")

    print(f"Sample written to {args.out}")


if __name__ == "__main__":
    main()
