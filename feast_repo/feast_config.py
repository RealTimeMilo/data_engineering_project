"""
Runtime Feast configuration.

feature_store.yaml is generated from environment variables so secrets
(the Postgres password) never live in the image or the repo.
"""

import os
import pathlib

import yaml

# Must stay in sync with containers/ml/config.py::FEATURE_COLUMNS
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

PROJECT = os.getenv("FEAST_PROJECT", "instacart")


def write_feature_store_yaml(repo_dir: str) -> str:
    """Write feature_store.yaml into repo_dir and return its path."""
    config = {
        "project": PROJECT,
        "provider": "local",
        "registry": os.getenv("FEAST_REGISTRY", "/tmp/feast/registry.db"),
        "offline_store": {"type": "file"},
        "online_store": {
            "type": "postgres",
            "host": os.environ["FEAST_DB_HOST"],
            "port": int(os.getenv("FEAST_DB_PORT", "5432")),
            "database": os.getenv("FEAST_DB_NAME", "feast"),
            "db_schema": os.getenv("FEAST_DB_SCHEMA", "public"),
            "user": os.getenv("FEAST_DB_USER", "feast"),
            "password": os.environ["FEAST_DB_PASSWORD"],
            "sslmode": os.getenv("FEAST_DB_SSLMODE", "require"),
        },
        "entity_key_serialization_version": 3,
    }
    registry = config["registry"]
    if registry.startswith("/"):
        pathlib.Path(registry).parent.mkdir(parents=True, exist_ok=True)
    path = pathlib.Path(repo_dir) / "feature_store.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    return str(path)
