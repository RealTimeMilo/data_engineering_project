from airflow.providers.amazon.aws.operators.ecs import EcsRunTaskOperator

nginx_task = EcsRunTaskOperator(
    task_id="nginx_task",
    cluster="mlops-cluster",
    task_definition="nginx",
    launch_type="FARGATE",
    overrides={
        "containerOverrides": [
            {
                "name": "nginx",
                "command": ["python", "nginx.py"],
            },
        ],
    },
    # network_configuration={
    #     "awsvpcConfiguration": {
    #         "subnets": test_context[SUBNETS_KEY],
    #         "securityGroups": test_context[SECURITY_GROUPS_KEY],
    #         "assignPublicIp": "ENABLED",
    #     },
    # },
)