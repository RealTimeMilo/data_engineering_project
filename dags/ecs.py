"""
preprocessing_dag.py – Airflow DAG for data preprocessing using ECSOperator.

Pipeline:
    extract  →  clean  →  transform  →  load

Each task runs preprocessing.py inside a Docker container on AWS ECS Fargate.
Place this file in your Airflow DAGs folder (e.g. $AIRFLOW_HOME/dags/).

Required Airflow connections:
  - aws_default  : AWS credentials with ECS + CloudWatch permissions

Required Airflow Variables (or replace inline):
  - ECS_CLUSTER         : name of your ECS cluster
  - ECS_TASK_DEFINITION : task definition family:revision  (e.g. preprocessing:3)
  - ECS_CONTAINER_NAME  : container name inside the task definition
  - ECS_SUBNET_IDS      : comma-separated private subnet IDs
  - ECS_SECURITY_GROUP  : security group ID for the tasks
  - ECR_IMAGE           : full ECR image URI  (e.g. 123456789.dkr.ecr.us-east-1.amazonaws.com/preprocessing:latest)
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator

# ── Config – pull from Airflow Variables so nothing is hard-coded ─────────────
CLUSTER          = Variable.get("ECS_CLUSTER",         default_var="honorable-dolphin-o1o354")
TASK_DEFINITION  = Variable.get("ECS_TASK_DEFINITION", default_var="preprocessing-1")
CONTAINER_NAME   = Variable.get("ECS_CONTAINER_NAME",  default_var="preprocessing-container")
SUBNETS          = Variable.get("ECS_SUBNET_IDS",       default_var="subnet-xxxxxxxx").split(",")
SECURITY_GROUP   = Variable.get("ECS_SECURITY_GROUP",  default_var="sg-xxxxxxxx")
ECR_IMAGE        = Variable.get("ECR_IMAGE",            default_var="559540498216.dkr.ecr.us-east-2.amazonaws.com/local/docker-airflow:latest")

# ── Default args ──────────────────────────────────────────────────────────────
default_args = {
    "owner": "data-team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# ── Shared ECS / Fargate config reused by every task ─────────────────────────
NETWORK_CONFIG = {
    "awsvpcConfiguration": {
        "subnets": SUBNETS,
        "securityGroups": [SECURITY_GROUP],
        "assignPublicIp": "DISABLED",   # use ENABLED if subnets are public
    }
}

def ecs_task(task_id: str, step: str) -> EcsRunTaskOperator:
    """
    Factory that returns an EcsRunTaskOperator for a given preprocessing step.

    The container's CMD is overridden so that each ECS task runs only one step:
        python preprocessing.py --step <step>
    """
    return EcsRunTaskOperator(
        task_id=task_id,
        aws_conn_id="aws_default",
        cluster=CLUSTER,
        task_definition=TASK_DEFINITION,
        launch_type="FARGATE",
        overrides={
            "containerOverrides": [
                {
                    "name": CONTAINER_NAME,
                    "image": ECR_IMAGE,
                    "command": ["python", "preprocessing.py", "--step", step],
                    "environment": [
                        # Inject any runtime env vars your script needs
                        {"name": "STEP", "value": step},
                        {"name": "ENV",  "value": "production"},
                    ],
                }
            ]
        },
        network_configuration=NETWORK_CONFIG,
        awslogs_group="/ecs/preprocessing",
        awslogs_stream_prefix=f"ecs/preprocessing/{step}",
        awslogs_region="us-east-1",          # change to your region
        awslogs_fetch_interval=timedelta(seconds=5),
        # Airflow polls ECS until the task reaches STOPPED
        deferrable=False,
        reattach=True,                        # re-attach if the Airflow worker restarts
    )


# ── DAG ───────────────────────────────────────────────────────────────────────
with DAG(
    dag_id="preprocessing_ecs_pipeline",
    description="ECS Fargate preprocessing pipeline – extract, clean, transform, load",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["preprocessing", "ecs", "etl"],
) as dag:

    t_extract   = ecs_task("extract",   "extract")
    t_clean     = ecs_task("clean",     "clean")
    t_transform = ecs_task("transform", "transform")
    t_load      = ecs_task("load",      "load")

    # ── Dependency chain ──────────────────────────────────────────────────────
    t_extract >> t_clean >> t_transform >> t_load