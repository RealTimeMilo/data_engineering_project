
"""
    While executing it on ECS you can specify granule controls as to how much CPU to give it and how much memory to give it.

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
