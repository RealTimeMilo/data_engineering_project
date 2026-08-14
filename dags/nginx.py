from datetime import datetime

from airflow import DAG
from airflow.models import Variable
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator

CLUSTER = Variable.get("ECS_CLUSTER", default_var="mlops-cluster")
TASK_DEFINITION = Variable.get("ECS_TASK_DEFINITION", default_var="nginx")
CONTAINER_NAME = Variable.get("ECS_CONTAINER_NAME", default_var="nginx")
# SUBNETS = Variable.get("ECS_SUBNET_IDS", default_var="subnet-xxxxxxxx").split(",")
# SECURITY_GROUP = Variable.get("ECS_SECURITY_GROUP", default_var="sg-xxxxxxxx")
AWS_REGION = Variable.get("AWS_REGION", default_var="us-east-2")

NETWORK_CONFIG = {
    "awsvpcConfiguration": {
        # "subnets": SUBNETS,
        # "securityGroups": [SECURITY_GROUP],
        "assignPublicIp": "ENABLED",
    }
}

with DAG(
    dag_id="ecs_nginx_dag",
    description="Run nginx on ECS Fargate",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    tags=["ecs", "nginx"],
) as dag:

    run_nginx = EcsRunTaskOperator(
        task_id="nginx",
        aws_conn_id="aws_default",
        region_name=AWS_REGION,
        cluster=CLUSTER,
        task_definition=TASK_DEFINITION,
        launch_type="FARGATE",
        network_configuration=NETWORK_CONFIG,
        overrides={
            "containerOverrides": [
                {
                    "name": CONTAINER_NAME,
                    # Validates nginx config and exits; use the task definition CMD to run nginx normally.
                    "command": ["nginx", "-t"],
                },
            ],
        },
    )
