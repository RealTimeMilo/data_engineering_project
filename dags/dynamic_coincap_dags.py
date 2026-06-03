"""
Dynamic DAG generation from YAML + SQL registry.

Sources:
  - dags/config/pipelines.yaml
  - pipeline_config.pipelines (Postgres, migrations/001_pipeline_registry.sql)

DAG types:
  - coincap_api    -> coincap_elt_<id>
  - sql_transform  -> sql_elt_<id>
"""

from lib.coincap_factory import create_coincap_dag
from lib.pipeline_loader import load_all_pipelines

for _pipeline in load_all_pipelines():
    _ptype = _pipeline.get("pipeline_type", "coincap_api")
    _pid = _pipeline["id"]

    if _ptype == "sql_transform":
        _dag_id = f"sql_elt_{_pid}"
    else:
        _dag_id = f"coincap_elt_{_pid}"
        globals()[_dag_id] = create_coincap_dag(_pipeline)
