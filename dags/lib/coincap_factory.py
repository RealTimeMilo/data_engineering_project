"""Build CoinCap ELT DAGs from pipeline config (dynamic DAG generation)."""

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl
import requests
from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator
from cuallee import Check, CheckLevel
from lib.pipeline_loader import CONFIG_PATH, load_all_pipelines

COINCAP_BASE_URL = "https://api.coincap.io/v2"


def load_pipelines() -> list[dict[str, Any]]:
    """CoinCap API pipelines only (YAML + SQL registry)."""
    return [
        p
        for p in load_all_pipelines()
        if p.get("pipeline_type", "coincap_api") == "coincap_api"
    ]


def create_coincap_dag(pipeline: dict[str, Any]):
    """Return a DAG instance for one pipeline config entry."""
    pipeline_id = pipeline["id"]
    endpoint = pipeline["endpoint"]
    dag_id = f"coincap_elt_{pipeline_id}"
    file_path = (
        f'{os.getenv("AIRFLOW_HOME", "/opt/airflow")}/data/coincap_{pipeline_id}.csv'
    )
    url = f"{COINCAP_BASE_URL}/{endpoint}"
    quality_column = pipeline.get("quality_column", "name")
    render_dashboard = pipeline.get("render_dashboard", False)

    @dag(
        dag_id=dag_id,
        description=pipeline.get(
            "description", f"Dynamic CoinCap ELT for {endpoint}"
        ),
        schedule=pipeline.get("schedule", "0 6 * * *"),
        start_date=datetime(2023, 1, 1),
        catchup=False,
        tags=["coincap", "dynamic", pipeline_id],
    )
    def coincap_elt_pipeline():
        @task
        def fetch_coincap_data(api_url: str, output_path: str) -> str:
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            rows = response.json().get("data", [])
            if not rows:
                raise ValueError(f"No data returned from {api_url}")
            keys = rows[0].keys()
            with open(output_path, "w", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=keys)
                writer.writeheader()
                writer.writerows(rows)
            return output_path

        @task
        def run_quality_check(output_path: str, column_name: str) -> list[str]:
            check = Check(CheckLevel.ERROR, "Completeness")
            pl_df = pl.read_csv(output_path)
            validation_results_df = check.is_complete(column_name).validate(pl_df)
            return validation_results_df["status"].to_list()

        @task.branch
        def check_data_quality(
            validation_results: list[str],
            include_dashboard: bool,
        ) -> str:
            if "FAIL" in validation_results:
                return "stop_pipeline"
            if include_dashboard:
                return "generate_dashboard"
            return "pipeline_success"

        stop_pipeline = DummyOperator(task_id="stop_pipeline")
        pipeline_success = DummyOperator(task_id="pipeline_success")

        fetched_path = fetch_coincap_data(url, file_path)
        validation = run_quality_check(fetched_path, quality_column)
        branch = check_data_quality(validation, render_dashboard)

        fetched_path >> validation >> branch
        branch >> [pipeline_success, stop_pipeline]

        if render_dashboard:
            markdown_path = (
                f'{os.getenv("AIRFLOW_HOME", "/opt/airflow")}/visualization/'
            )
            render_cmd = (
                f"cd {markdown_path} && "
                f"quarto render {markdown_path}/dashboard.qmd"
            )
            gen_dashboard = BashOperator(
                task_id="generate_dashboard",
                bash_command=render_cmd,
            )
            branch >> gen_dashboard

    return coincap_elt_pipeline()
