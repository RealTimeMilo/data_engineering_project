"""Small I/O + logging helpers shared across the ML containers."""

import io
import json
import logging
import os
import sys

import boto3
import pandas as pd

from config import AWS_REGION

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s | %(message)s"


def configure_logging(name: str = "instacart-ml") -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT, stream=sys.stdout)
    return logging.getLogger(name)


logger = configure_logging()


def read_parquet(uri: str, **kwargs) -> pd.DataFrame:
    """Read a parquet file/prefix from S3 (s3fs) or local disk."""
    logger.info("Reading parquet: %s", uri)
    return pd.read_parquet(uri, **kwargs)


def write_parquet(df: pd.DataFrame, uri: str) -> None:
    """Write a DataFrame to parquet on S3 or local disk."""
    logger.info("Writing %s rows -> %s", len(df), uri)
    df.to_parquet(uri, index=False)

def read_csv(uri: str, **kwargs) -> pd.DataFrame:
    logger.info("Reading csv: %s", uri)
    return pd.read_csv(uri, **kwargs)


def s3_client():
    return boto3.client("s3", region_name=AWS_REGION)


def upload_file(local_path: str, bucket: str, key: str) -> None:
    logger.info("Uploading %s -> s3://%s/%s", local_path, bucket, key)
    s3_client().upload_file(local_path, bucket, key)


def download_file(bucket: str, key: str, local_path: str) -> None:
    logger.info("Downloading s3://%s/%s -> %s", bucket, key, local_path)
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
    s3_client().download_file(bucket, key, local_path)


def write_json(bucket: str, key: str, payload: dict) -> None:
    body = json.dumps(payload, indent=2, default=str).encode("utf-8")
    logger.info("Writing json -> s3://%s/%s", bucket, key)
    s3_client().put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")


def read_json(bucket: str, key: str) -> dict:
    obj = s3_client().get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read().decode("utf-8"))


def copy_prefix(bucket: str, src_prefix: str, dst_prefix: str) -> int:
    """Copy every object under src_prefix to dst_prefix. Returns object count."""
    client = s3_client()
    src_prefix = src_prefix.rstrip("/") + "/"
    dst_prefix = dst_prefix.rstrip("/") + "/"
    paginator = client.get_paginator("list_objects_v2")
    copied = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=src_prefix):
        for obj in page.get("Contents", []):
            src_key = obj["Key"]
            rel = src_key[len(src_prefix):]
            dst_key = dst_prefix + rel
            client.copy_object(
                Bucket=bucket,
                CopySource={"Bucket": bucket, "Key": src_key},
                Key=dst_key,
            )
            copied += 1
    logger.info("Copied %s objects %s -> %s", copied, src_prefix, dst_prefix)
    return copied
