"""
Airflow DAG: S3 Data Pipeline with Transformations
====================================================
This DAG:
1. Extracts raw CSV data from an S3 source bucket
2. Applies multiple data transformations (cleaning, enrichment, aggregation)
3. Loads transformed data back to S3 in Parquet format
4. Sends a summary notification on completion

Requirements:
    pip install apache-airflow apache-airflow-providers-amazon pandas pyarrow

S3 Connection:
    Configure an Airflow connection named 'aws_default' with your AWS credentials,
    or set environment variables AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.
"""

from __future__ import annotations

import io
import json
import logging
from datetime import datetime, timedelta

import pandas as pd
from airflow.decorators import task
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.slack.operators.slack_webhook import \
    SlackWebhookOperator
from airflow.providers.smtp.operators.smtp import EmailOperator
from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.sdk import Variable

from airflow import DAG

# from airflow.providers.papermill.operators.papermill import PapermillOperator

SLACK_WEBHOOK_URL = Variable.get("slack_webhook_url")
SLACK_CHANNEL = Variable.get("slack_channel")

# ---------------------------------------------------------------------------
# Configuration — override via Airflow Variables or environment variables
# ---------------------------------------------------------------------------
SOURCE_BUCKET = Variable.get("s3_source_bucket", default="databricks-v02")
DEST_BUCKET   = Variable.get("s3_dest_bucket",   default="databricks-v02")
SOURCE_PREFIX = ""          # s3://SOURCE_BUCKET/raw/sales/YYYY-MM-DD.csv
DEST_PREFIX   = "transformed/"  # s3://DEST_BUCKET/transformed/sales/YYYY-MM-DD/
AWS_CONN_ID   = "aws_default"

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default DAG arguments
# ---------------------------------------------------------------------------
default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email": ["data-alerts@example.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="s3_data_transformation_pipeline",
    description="Extract from S3, transform with pandas, load back to S3 as Parquet",
    default_args=default_args,
    schedule="0 6 * * *",             # Daily at 06:00 UTC
    catchup=False,
    max_active_runs=1,
    tags=["s3", "etl", "transformations", "sales"],
    doc_md=__doc__,
) as dag:

    # -----------------------------------------------------------------------
    # Task 1: Validate that the source file exists in S3
    # -----------------------------------------------------------------------
    @task(task_id="validate_source")
    def validate_source(**context) -> str:
        """Check that today's source file is present in S3."""
        ds = context["ds"]                           # execution date YYYY-MM-DD
        s3_key = f"{SOURCE_PREFIX}housing.csv"

        hook = S3Hook(aws_conn_id=AWS_CONN_ID)
        exists = hook.check_for_key(key=s3_key, bucket_name=SOURCE_BUCKET)
        if not exists:
            raise FileNotFoundError(
                f"Source file not found: s3://{SOURCE_BUCKET}/{s3_key}"
            )

        log.info("✅ Validated: s3://%s/%s", SOURCE_BUCKET, s3_key)
        return s3_key                                # passed to downstream tasks

    # -----------------------------------------------------------------------
    # Task 2: Extract — download the raw CSV from S3 into memory
    # -----------------------------------------------------------------------
    @task(task_id="extract_from_s3")
    def extract_from_s3(s3_key: str) -> dict:
        """Download raw CSV from S3 and return as a JSON-serialisable dict."""
        hook = S3Hook(aws_conn_id=AWS_CONN_ID)
        obj  = hook.get_key(key=s3_key, bucket_name=SOURCE_BUCKET)
        raw_bytes = obj.get()["Body"].read()

        df = pd.read_csv(io.BytesIO(raw_bytes))
        log.info("📥 Extracted %d rows × %d cols from s3://%s/%s",
                 len(df), len(df.columns), SOURCE_BUCKET, s3_key)

        # Serialise to JSON so XCom can carry it between tasks
        return {"data": df.to_json(orient="split"), "source_key": s3_key}

    # -----------------------------------------------------------------------
    # Task 3a: Clean — handle nulls, types, duplicates
    # -----------------------------------------------------------------------
    @task(task_id="transform_clean")
    def transform_clean(payload: dict) -> dict:
        """
        Cleaning transformations:
        - Drop exact duplicate rows
        - Strip whitespace from string columns
        - Coerce date columns to datetime
        - Fill missing numeric values with column median
        - Drop rows missing critical business keys
        """
        df = pd.read_json(payload["data"], orient="split")

        before = len(df)
        df = df.drop_duplicates()
        log.info("🧹 Removed %d duplicate rows", before - len(df))

        # Strip whitespace from all object columns
        str_cols = df.select_dtypes(include="object").columns
        df[str_cols] = df[str_cols].apply(lambda s: s.str.strip())

        # Coerce date-like columns
        for col in df.columns:
            if "date" in col.lower() or "time" in col.lower():
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # Fill numeric NaN with median
        num_cols = df.select_dtypes(include="number").columns
        df[num_cols] = df[num_cols].fillna(df[num_cols].median())

        # Drop rows missing critical keys (adjust to your schema)
        critical_keys = [c for c in ["order_id", "customer_id"] if c in df.columns]
        if critical_keys:
            df = df.dropna(subset=critical_keys)

        log.info("✅ Cleaned dataset: %d rows remaining", len(df))
        payload["data"] = df.to_json(orient="split")
        return payload

    # -----------------------------------------------------------------------
    # Task 3b: Enrich — add derived / lookup columns
    # -----------------------------------------------------------------------
    @task(task_id="transform_enrich")
    def transform_enrich(payload: dict) -> dict:
        """
        Enrichment transformations:
        - Add year / month / day_of_week columns from a date field
        - Compute revenue = quantity * unit_price (if columns present)
        - Bin customers into value tiers
        - Add a pipeline_timestamp column
        """
        df = pd.read_json(payload["data"], orient="split")

        # Date features
        date_col = next((c for c in df.columns if "date" in c.lower()), None)
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col])
            df["year"]         = df[date_col].dt.year
            df["month"]        = df[date_col].dt.month
            df["day_of_week"]  = df[date_col].dt.day_name()
            df["quarter"]      = df[date_col].dt.quarter
            df["is_weekend"]   = df[date_col].dt.dayofweek.isin([5, 6])

        # Revenue calculation
        if {"quantity", "unit_price"}.issubset(df.columns):
            df["revenue"]         = df["quantity"] * df["unit_price"]
            df["revenue_rounded"] = df["revenue"].round(2)

        # Customer value tiers (based on revenue if available)
        if "revenue" in df.columns:
            df["value_tier"] = pd.cut(
                df["revenue"],
                bins=[0, 100, 500, 2000, float("inf")],
                labels=["low", "medium", "high", "premium"],
                right=True,
            )

        # Audit column
        df["pipeline_timestamp"] = datetime.utcnow().isoformat()

        log.info("✅ Enriched dataset: %d cols", len(df.columns))
        payload["data"] = df.to_json(orient="split")
        return payload

    @task(task_id="transform_enrich_papermill")
    def transform_enrich_papermill(payload: dict) -> dict:
        import json
        import os
        import tempfile

        import papermill as pm

        # 1️⃣ Write payload to a temp file (papermill handles large dicts better this way)
        payload_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(payload, payload_file)
        payload_file.close()

        # 2️⃣ Run the notebook
        output_notebook = tempfile.mktemp(suffix=".ipynb")
        pm.execute_notebook(
            "transform_enrich.ipynb",
            output_notebook,
            parameters={"payload_file": payload_file.name},
            kernel_name="python3",
        )

        # 3️⃣ Read the transformed payload (notebook MUST write this file)
        output_file = payload_file.name.replace(".json", "_output.json")
        if not os.path.exists(output_file):
            raise FileNotFoundError(f"Notebook failed to produce output at {output_file}")

        with open(output_file, "r") as f:
            return json.load(f)

    # -----------------------------------------------------------------------
    # Task 3c: Aggregate — build summary statistics
    # -----------------------------------------------------------------------
    @task(task_id="transform_aggregate")
    def transform_aggregate(payload: dict) -> dict:
        """
        Aggregation transformations:
        - Daily revenue summary by product / region
        - Running total of revenue
        - Z-score normalisation of numeric KPIs
        """
        df = pd.read_json(payload["data"], orient="split")

        agg_tables: dict[str, str] = {}

        # Daily revenue by product
        if {"product_id", "revenue", "year", "month"}.issubset(df.columns):
            daily_rev = (
                df.groupby(["year", "month", "product_id"])["revenue"]
                .agg(total_revenue="sum", order_count="count", avg_revenue="mean")
                .reset_index()
            )
            agg_tables["daily_revenue_by_product"] = daily_rev.to_json(orient="split")
            log.info("📊 Aggregated daily revenue: %d rows", len(daily_rev))

        # Regional breakdown
        if {"region", "revenue"}.issubset(df.columns):
            regional = (
                df.groupby("region")["revenue"]
                .agg(total="sum", orders="count")
                .reset_index()
                .sort_values("total", ascending=False)
            )
            agg_tables["regional_summary"] = regional.to_json(orient="split")

        # Z-score normalisation of numeric columns
        num_cols = df.select_dtypes(include="number").columns.tolist()
        for col in num_cols:
            std = df[col].std()
            if std > 0:
                df[f"{col}_zscore"] = (df[col] - df[col].mean()) / std

        payload["data"] = df.to_json(orient="split")
        payload["agg_tables"] = agg_tables
        return payload

    # -----------------------------------------------------------------------
    # Task 4: Load — write Parquet files back to S3
    # -----------------------------------------------------------------------
    @task(task_id="load_to_s3")
    def load_to_s3(payload: dict, **context) -> dict:
        """
        Upload transformed main table + aggregation tables to S3 as CSV.
        Outputs to:
            s3://DEST_BUCKET/transformed/sales/YYYY-MM-DD/main.csv
            s3://DEST_BUCKET/transformed/sales/YYYY-MM-DD/<agg_name>.csv
        """
        ds   = context["ds"]
        hook = S3Hook(aws_conn_id=AWS_CONN_ID)
        uploaded: list[str] = []

        def _upload_df(df: pd.DataFrame, name: str) -> str:
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            key = f"{DEST_PREFIX}housing/{name}.csv"
            hook.load_string(
                string_data=buf.getvalue(),
                key=key,
                bucket_name=DEST_BUCKET,
                replace=True,
            )
            log.info("⬆️  Uploaded s3://%s/%s (%d rows)", DEST_BUCKET, key, len(df))
            return key

        # Main transformed table
        main_df = pd.read_json(payload["data"], orient="split")
        uploaded.append(_upload_df(main_df, "main"))

        # Aggregation tables
        for table_name, json_str in payload.get("agg_tables", {}).items():
            agg_df = pd.read_json(json_str, orient="split")
            uploaded.append(_upload_df(agg_df, table_name))

        return {
            "uploaded_keys": uploaded,
            "row_count": len(main_df),
            "execution_date": ds,
        }

    # -----------------------------------------------------------------------
    # Task 5: Quality gate — basic row-count / null check
    # -----------------------------------------------------------------------
    @task(task_id="data_quality_check")
    def data_quality_check(load_result: dict) -> None:
        """Fail the DAG if the output looks suspiciously small or empty."""
        row_count = load_result["row_count"]
        min_rows  = int(Variable.get("min_expected_rows", default="1"))

        if row_count < min_rows:
            raise ValueError(
                f"Quality check failed: only {row_count} rows loaded "
                f"(minimum expected: {min_rows})."
            )
        log.info("✅ Quality check passed: %d rows loaded", row_count)

    # -----------------------------------------------------------------------
    # Task 6: Notify — log a summary (replace with SNS/Slack as needed)
    # -----------------------------------------------------------------------
    @task(task_id="notify_success")
    def notify_success(load_result: dict) -> str:
        summary = {
            "status": "SUCCESS",
            "dag": "s3_data_transformation_pipeline",
            "execution_date": load_result["execution_date"],
            "rows_loaded": load_result["row_count"],
            "files_uploaded": load_result["uploaded_keys"],
        }
        log.info("🎉 Pipeline complete:\n%s", json.dumps(summary, indent=2))
        # To send to SNS, swap the log line above for:
        # from airflow.providers.amazon.aws.hooks.sns import SnsHook
        # SnsHook(aws_conn_id=AWS_CONN_ID).publish_to_target(
        #     target_arn=Variable.get("sns_topic_arn"),
        #     message=json.dumps(summary),
        # )
        # Return a string so Slack templating doesn't depend on extra Jinja filters.
        return json.dumps(summary, indent=2)

    # send_email = EmailOperator(
    #     task_id="send_email",
    #     to=Variable.get("email_to"),
    #     subject="S3 Data Transformation Pipeline",
    #     html_content=(
    #         "<p>The S3 Data Transformation Pipeline has completed successfully.</p>"
    #         "<pre>{{ ti.xcom_pull(task_ids='notify_success') | tojson(indent=2) }}</pre>"
    #     ),
    # )

    send_slack = SlackWebhookOperator(
        task_id="send_slack",
        slack_webhook_conn_id="slack_webhook",
        message=(
            "🎉 S3 pipeline succeeded:\n"
            "```{{ ti.xcom_pull(task_ids='notify_success') }}```"
        ),
    )

    # -----------------------------------------------------------------------
    # Bookend operators
    # -----------------------------------------------------------------------
    start = EmptyOperator(task_id="start")
    end   = EmptyOperator(task_id="end")

    # -----------------------------------------------------------------------
    # Wire the DAG - Complete Flow with Papermill
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # Task Dependencies
    # -----------------------------------------------------------------------

    # Extract & Clean
    validated   = validate_source()
    raw_payload = extract_from_s3(validated)
    cleaned     = transform_clean(raw_payload)

    # Papermill Enrichment (simple task, no extra parsing needed)
    enriched    = transform_enrich_papermill(cleaned)

    # Aggregate & Load
    aggregated  = transform_aggregate(enriched)
    load_result = load_to_s3(aggregated)

    # Quality & Notify
    quality_ok  = data_quality_check(load_result)
    summary     = notify_success(load_result)

    # Wire dependencies
    start >> validated >> raw_payload >> cleaned >> enriched >> aggregated >> load_result
    load_result >> quality_ok >> summary >> send_slack >> end