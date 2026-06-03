from airflow.models import DagBag

from lib.coincap_factory import CONFIG_PATH, load_pipelines
from lib.pipeline_loader import load_all_pipelines, load_pipelines_from_yaml


def test_pipeline_config_exists():
    assert CONFIG_PATH.is_file()


def test_load_pipelines_returns_enabled_only():
    pipelines = load_pipelines_from_yaml()
    assert len(pipelines) >= 1
    assert all(p.get("enabled", True) for p in pipelines)


def test_load_all_pipelines_includes_coincap_type():
    pipelines = load_all_pipelines()
    coincap = [p for p in pipelines if p.get("pipeline_type", "coincap_api") == "coincap_api"]
    assert len(coincap) >= 1


def test_dynamic_dags_registered():
    dag_bag = DagBag(dag_folder="/opt/airflow/dags", include_examples=False)
    assert not dag_bag.import_errors, dag_bag.import_errors

    for pipeline in load_all_pipelines():
        ptype = pipeline.get("pipeline_type", "coincap_api")
        pid = pipeline["id"]
        expected = f"sql_elt_{pid}" if ptype == "sql_transform" else f"coincap_elt_{pid}"
        assert expected in dag_bag.dags, f"Missing DAG: {expected}"
