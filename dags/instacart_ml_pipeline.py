"""
Instacart reorder-model pipeline (ingest -> preprocess -> train -> evaluate -> deploy).

Every step runs as a one-off ECS Fargate task using the `instacart-ml` image
(and `instacart-inference` for serving). The tasks are created by
terraform/ml_pipeline.tf; this DAG just launches them with per-run overrides.

Required Airflow Variables (sensible defaults are baked in):
    ML_AWS_CONN_ID          Airflow AWS connection (aws_default or None for task role)
    ML_ECS_CLUSTER          ECS cluster name
    ML_TASK_DEF_INGEST      task definition family[:revision]
    ML_TASK_DEF_PREPROCESS
    ML_TASK_DEF_TRAIN
    ML_TASK_DEF_EVALUATE
    ML_TASK_DEF_DEPLOY
    ML_CONTAINER_NAME       container name inside the task definition
    ML_SUBNET_IDS           comma-separated subnet IDs
    ML_SECURITY_GROUP       security group ID
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator

# None => use the ambient AWS credentials (ECS task role / EC2 instance role).
# Set the ML_AWS_CONN_ID Variable to use an Airflow connection instead.
AWS_CONN_ID = Variable.get("ML_AWS_CONN_ID", default_var=None)
CLUSTER = Variable.get("ML_ECS_CLUSTER", default_var="sde-airflow-dev-ml")
CONTAINER_NAME = Variable.get("ML_CONTAINER_NAME", default_var="ml-task")
SUBNETS = Variable.get("ML_SUBNET_IDS", default_var="").split(",")
SECURITY_GROUP = Variable.get("ML_SECURITY_GROUP", default_var="")
AWS_REGION = Variable.get("ML_AWS_REGION", default_var="us-east-2")

TASK_DEFS = {
    "ingest": Variable.get("ML_TASK_DEF_INGEST", default_var="sde-airflow-dev-ml-ingest"),
    "preprocess": Variable.get("ML_TASK_DEF_PREPROCESS", default_var="sde-airflow-dev-ml-preprocess"),
    "feast": Variable.get("ML_TASK_DEF_FEAST", default_var="sde-airflow-dev-ml-feast"),
    "train": Variable.get("ML_TASK_DEF_TRAIN", default_var="sde-airflow-dev-ml-train"),
    "evaluate": Variable.get("ML_TASK_DEF_EVALUATE", default_var="sde-airflow-dev-ml-evaluate"),
    "deploy": Variable.get("ML_TASK_DEF_DEPLOY", default_var="sde-airflow-dev-ml-deploy"),
}

# Container name per step (the Feast task def uses a different container name).
CONTAINERS = {"feast": Variable.get("ML_FEAST_CONTAINER_NAME", default_var="feast")}

NETWORK_CONFIGURATION = {
    "awsvpcConfiguration": {
        "subnets": [s for s in SUBNETS if s],
        "securityGroups": [SECURITY_GROUP] if SECURITY_GROUP else [],
        "assignPublicIp": "ENABLED",
    }
}

default_args = {
    "owner": "ml-platform-team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def ml_task(task_id: str, step: str, command: str, extra_env: list[dict]) -> EcsRunTaskOperator:
    """Launch one pipeline step as an ECS task with Airflow-templated overrides."""
    container = CONTAINERS.get(step, CONTAINER_NAME)
    return EcsRunTaskOperator(
        task_id=task_id,
        aws_conn_id=AWS_CONN_ID,
        region=AWS_REGION,
        cluster=CLUSTER,
        task_definition=TASK_DEFS[step],
        launch_type="FARGATE",
        # The CloudWatch stream is <task-def prefix>/<container>/<task-id>. Pass
        # the container name explicitly and include it in the prefix: Airflow's
        # log-stream builder skips appending the container when the prefix
        # already ends with "/<container>". Otherwise the feast step (container
        # named "feast") derives "ecs/feast/<id>" instead of
        # "ecs/feast/feast/<id>", and the task fails on GetLogEvents even though
        # the ECS task succeeded.
        container_name=container,
        awslogs_stream_prefix=f"ecs/{step}/{container}",
        overrides={
            "containerOverrides": [
                {
                    "name": container,
                    "command": command,
                    "environment": [
                        # run_id is always defined (unlike ts_nodash, which needs
                        # a logical_date and is undefined for manual runs in
                        # Airflow 3). Sanitised so it is safe as an S3 key.
                        {
                            "name": "ML_RUN_ID",
                            "value": "{{ dag_run.run_id | replace(':', '-') | replace('+', '-') | replace('.', '-') }}",
                        },
                        *extra_env,
                    ],
                }
            ]
        },
        network_configuration=NETWORK_CONFIGURATION,
        awslogs_group=f"/sde-airflow/dev/ecs-airflow/ml/{step}",
        awslogs_region=AWS_REGION,
        awslogs_fetch_interval=timedelta(seconds=10),
        deferrable=False,
        reattach=True,
    )


with DAG(
    dag_id="instacart_ml_pipeline",
    description="Train + deploy the Instacart reorder model on ECS with Ray",
    default_args=default_args,
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["ml", "instacart", "ecs", "ray"],
    params={"sample_fraction": 0.1},
) as dag:

    t_ingest = ml_task(
        "ingest",
        "ingest",
        ["python", "ingest.py"],
        [{"name": "ML_SAMPLE_FRACTION", "value": "{{ params.sample_fraction }}"}],
    )

    t_preprocess = ml_task("preprocess", "preprocess", ["python", "preprocess.py"], [])
    t_feast = ml_task(
        "feast_materialize",
        "feast",
        ["python", "feature_repo/apply_materialize.py"],
        [],
    )
    t_train = ml_task("train", "train", ["python", "train.py"], [])
    t_evaluate = ml_task("evaluate", "evaluate", ["python", "evaluate.py"], [])
    t_deploy = ml_task("deploy", "deploy", ["python", "deploy.py"], [])

    t_ingest >> t_preprocess >> t_feast >> t_train >> t_evaluate >> t_deploy
