from datetime import datetime

from airflow.providers.amazon.aws.operators.ecs import ECSOperator

from airflow import DAG

with DAG(
    dag_id="simple_ecs_dag",
    start_date=datetime(2026, 1, 1),
    schedule_interval=None,  # This means you trigger it by hand
    catchup=False,
) as dag:

    run_ecs = ECSOperator(
        task_id="run_ecs_task",
        cluster="my-cluster",
        task_definition="my-task-definition",
        launch_type="FARGATE",
        network_configuration={
            "awsvpcConfiguration": {
                "subnets": ["subnet-12345"],
            }
        },
    )
