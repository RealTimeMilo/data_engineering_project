from datetime import datetime
from airflow.providers.amazon.aws.operators.rds import RdsCreateDbInstanceOperator
from airflow import DAG
from airflow.sdk import Param

with DAG(
    dag_id="trigger_rds_from_form",
    description="Trigger new rds",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    params={
        "db_identifier": Param("my_dynamic_db", type="string", description="RDS instance identifier"),
        "db_instance_class": Param("db.t4g.micro", type="string", description="Instance class"),
        "allocated_storage": Param(20, type="integer", description="Storage size"),
        "db_engine": Param("postgres", type="string", description="DB engine"),
        "db_username": Param("dbuser", type="string", description="Instance class"),
        "db_password": Param("ChangeMe123", type="string", description="Instance class"),
    },
) as dag:

    create_db = RdsCreateDbInstanceOperator(
        task_id="dynamic_create_rds",
        db_instance_identifier="{{ params.db_identifier }}",
        db_instance_class="{{ params.db_instance_class }}",
        # allocated_storage="{{ params.allocated_storage }}",
        engine="{{ params.db_engine }}",
        # db_username="{{ params.db_username }}",
        # db_password="{{ params.db_password }}",
    )