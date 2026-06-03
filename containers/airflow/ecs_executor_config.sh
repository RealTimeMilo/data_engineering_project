export AIRFLOW__CORE__EXECUTOR='airflow.providers.amazon.aws.executors.ecs.ecs_executor.AwsEcsExecutor'

export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=<postgres-connection-string>

export AIRFLOW__AWS_ECS_EXECUTOR__REGION_NAME=<executor-region>

export AIRFLOW__AWS_ECS_EXECUTOR__CLUSTER=<ecs-cluster-name>

export AIRFLOW__AWS_ECS_EXECUTOR__CONTAINER_NAME=<ecs-container-name>

export AIRFLOW__AWS_ECS_EXECUTOR__TASK_DEFINITION=<task-definition-name>

export AIRFLOW__AWS_ECS_EXECUTOR__LAUNCH_TYPE='FARGATE'

export AIRFLOW__AWS_ECS_EXECUTOR__PLATFORM_VERSION='LATEST'

export AIRFLOW__AWS_ECS_EXECUTOR__ASSIGN_PUBLIC_IP='True'

export AIRFLOW__AWS_ECS_EXECUTOR__SECURITY_GROUPS=<security-group-id-for-rds>

export AIRFLOW__AWS_ECS_EXECUTOR__SUBNETS=<subnet-id-for-rds>