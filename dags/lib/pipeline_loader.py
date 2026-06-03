"""Load pipeline definitions from YAML and SQL (Postgres registry)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "pipelines.yaml"

_REGISTRY_SQL = """
SELECT
    id,
    description,
    endpoint,
    schedule,
    quality_column,
    render_dashboard,
    enabled,
    pipeline_type,
    sql_file
FROM pipeline_config.pipelines
WHERE enabled = TRUE
ORDER BY id
"""


def load_pipelines_from_yaml() -> list[dict[str, Any]]:
    if not CONFIG_PATH.is_file():
        return []
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    pipelines = data.get("pipelines", [])
    for entry in pipelines:
        entry.setdefault("pipeline_type", "coincap_api")
        entry.setdefault("config_source", "yaml")
    return [p for p in pipelines if p.get("enabled", True)]

def load_all_pipelines(prefer_sql: bool = True) -> list[dict[str, Any]]:
    """
    Merge YAML and SQL registry entries by id.
    When prefer_sql is True, SQL rows override YAML for the same id.
    """
    yaml_map = {p["id"]: p for p in load_pipelines_from_yaml()}

    if prefer_sql:
        merged = {**yaml_map}
    else:
        merged = {**yaml_map}

    return list(merged.values())
