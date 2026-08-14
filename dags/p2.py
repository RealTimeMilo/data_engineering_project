from datetime import datetime

from airflow.operators.bash import BashOperator

from airflow import DAG

with DAG(
    "current_build",
    description="Print the current build loaded to the worker",
    schedule=None,
    start_date=datetime(2022, 6, 10),
    default_args={
        "owner": "Data Platform Orchestration",
    },
    catchup=True,
) as dag:

    t1 = BashOperator(
        task_id="print_current_build",
        bash_command="ls -la /opt/airflow/",
    )