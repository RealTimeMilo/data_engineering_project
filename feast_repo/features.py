"""Feast entity + feature-view definitions for the Instacart reorder model."""

import os
from datetime import timedelta

from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float32, Int64
from feast.value_type import ValueType

from feast_config import FEATURE_COLUMNS

user = Entity(
    name="user",
    join_keys=["user_id"],
    value_type=ValueType.INT64,
    description="Instacart user",
)

product = Entity(
    name="product",
    join_keys=["product_id"],
    value_type=ValueType.INT64,
    description="Instacart product",
)

# Offline store: the parquet written by containers/ml/preprocess.py
offline_source = FileSource(
    name="instacart_offline",
    path=os.getenv(
        "FEAST_OFFLINE_PATH",
        "s3://sde-airflow-dev-ml-559540498216/features/instacart/offline/features.parquet",
    ),
    timestamp_field="event_timestamp",
)

user_product_reorder_features = FeatureView(
    name="user_product_reorder_features",
    entities=[user, product],
    ttl=timedelta(days=3650),
    schema=[Field(name=column, dtype=Float32) for column in FEATURE_COLUMNS],
    source=offline_source,
    online=True,
)
