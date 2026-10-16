"""
`feast apply` + `feast materialize` for the Instacart feature store.

Run as an ECS task after preprocess.py has written the offline parquet:
registers the entities/feature view and loads features into the Postgres
online store.

NOTE: Feast's Dask file offline store resolves the source path relative to the
repo directory, so `s3://...` paths are not read as remote URIs. We therefore
download the parquet to a local absolute path before registering the view.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _localize_offline_path() -> None:
    path = os.environ.get("FEAST_OFFLINE_PATH", "")
    if not path.startswith("s3://"):
        return
    import boto3

    parsed = urlparse(path)
    bucket, key = parsed.netloc, parsed.path.lstrip("/")
    local = "/tmp/feast_offline/features.parquet"
    os.makedirs(os.path.dirname(local), exist_ok=True)
    print(f"Downloading {path} -> {local}")
    boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-2")).download_file(
        bucket, key, local
    )
    os.environ["FEAST_OFFLINE_PATH"] = local


# Must run before features.py builds the FileSource.
_localize_offline_path()

import feast_config  # noqa: E402
import features  # noqa: E402
from feast import FeatureStore  # noqa: E402


def main() -> None:
    repo = os.path.dirname(os.path.abspath(__file__))
    feast_config.write_feature_store_yaml(repo)
    store = FeatureStore(repo_path=repo)

    print("Applying feature definitions...")
    store.apply(
        [features.user, features.product, features.user_product_reorder_features]
    )

    start = datetime(2000, 1, 1, tzinfo=timezone.utc)
    end = datetime.now(timezone.utc) + timedelta(days=1)
    print(f"Materializing {features.user_product_reorder_features.name} {start} -> {end}")
    store.materialize(
        start_date=start,
        end_date=end,
        feature_views=[features.user_product_reorder_features.name],
    )
    print("Feast apply + materialize complete")


if __name__ == "__main__":
    main()
