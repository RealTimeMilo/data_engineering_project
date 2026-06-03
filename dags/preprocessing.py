from datetime import datetime

from airflow.providers.amazon.aws.operators.ecs import ECSOperator

from airflow import DAG

# Configuration constants
AWS_REGION = "us-east-2"
CLUSTER_NAME = "my-preprocessing-cluster"
TASK_DEFINITION = "my-preprocessing-task:1"
CONTAINER_NAME = "preprocessing-container"

default_args = {
    "owner": "data_engineering",
    "start_date": datetime(2026, 1, 1),
    "retries": 1,
}

with DAG(
    dag_id="preprocessing_ecs_job",
    default_args=default_args,
    schedule_interval="0 3 * * *",  # Runs daily at 3 AM
    catchup=False,
    tags=["preprocessing", "ecs", "aws"],
) as dag:

    run_preprocessing = ECSOperator(
        task_id="run_preprocessing_task",
        aws_conn_id="aws_default",
        region=AWS_REGION,
        cluster=CLUSTER_NAME,
        task=TASK_DEFINITION,
        launch_type="FARGATE",
        network_configuration={
            "awsvpcConfiguration": {
                "subnets": ["subnet-abcdef123456"],
                "securityGroups": ["sg-12345678"],
                "assignPublicIp": "ENABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": CONTAINER_NAME,
                    "command": ["python", "process_data.py", "--date", "{{ ds }}"],
                    "environment": [
                        {"name": "ENVIRONMENT", "value": "production"},
                        {"name": "S3_BUCKET", "value": "my-data-bucket"},
                    ],
                }
            ]
        },
        # Waits for task completion, updating logs and status to the Airflow UI
        wait_for_completion=True,
        max_active_tasks=1,
    )

    run_preprocessing
