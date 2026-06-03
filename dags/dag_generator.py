import os
from datetime import datetime

import yaml
from airflow.providers.amazon.aws.operators.ecs import EcsOperator

from airflow import DAG


def create_dag_from_yaml(yaml_path: str) -> DAG:
    """Dynamically parses a YAML config and returns an Airflow DAG."""
    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)

    dag_id = f"ml_launcher_{config['job_name']}"
    
    default_args = {
        'owner': 'ml-platform-team',
        'start_date': datetime(2026, 1, 1),
    }

    dag = DAG(
        dag_id=dag_id,
        default_args=default_args,
        schedule_interval=config['schedule'],
        catchup=False,
    )

    with dag:
        # Dynamically inject the YAML environment variables into the ECS Task Overrides
        env_overrides = [
            {"name": k, "value": str(v)} for k, v in config['environment'].items()
        ]

        run_ecs_task = EcsRunTaskOperator(
            task_id=f"run_{config['job_name']}_task",
            cluster=config['cluster'],
            task_definition=config['task_definition'],
            launch_type=config['compute']['launch_type'],
            overrides={
                "containerOverrides": [
                    {
                        "name": "ml-worker-container", # Name of your container in ECS
                        "environment": env_overrides,
                        "resourceRequirements": [
                            {"type": "VCPU", "value": config['compute']['cpu']},
                            {"type": "MEMORY", "value": config['compute']['memory']}
                        ]
                    }
                ]
            },
            aws_conn_id='aws_default',
        )

    return dag

# Assuming the YAML is loaded from a shared repository or mapped volume
config_path = os.path.join(os.path.dirname(__file__), "ml_job_config.yaml")
globals()[f"ml_launcher_{yaml.safe_load(open(config_path))['job_name']}"] = create_dag_from_yaml(config_path)
