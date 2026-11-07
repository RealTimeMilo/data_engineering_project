output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "ec2_instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.sde_ec2.id
}

output "ec2_public_ip" {
  description = "EC2 public IP (SSH only; Airflow via ALB)"
  value       = aws_instance.sde_ec2.public_ip
}

output "ec2_public_dns" {
  description = "EC2 public DNS"
  value       = aws_instance.sde_ec2.public_dns
}

output "alb_dns_name" {
  description = "ALB DNS name"
  value       = aws_lb.airflow.dns_name
}

output "alb_arn" {
  description = "ALB ARN"
  value       = aws_lb.airflow.arn
}

output "airflow_url" {
  description = "Airflow URL (ALB or Route53)"
  value       = var.domain_name != "" ? "https://${var.domain_name}" : "http://${aws_lb.airflow.dns_name}"
}

output "waf_web_acl_arn" {
  description = "WAF Web ACL ARN"
  value       = var.enable_waf ? aws_wafv2_web_acl.alb[0].arn : null
}

output "cloudwatch_log_groups" {
  description = "CloudWatch log groups for observability"
  value = {
    airflow = aws_cloudwatch_log_group.airflow_app.name
    system  = aws_cloudwatch_log_group.ec2_system.name
    docker  = aws_cloudwatch_log_group.ec2_docker.name
    waf     = var.enable_waf ? aws_cloudwatch_log_group.waf[0].name : null
  }
}

output "private_key" {
  description = "EC2 private key (sensitive)"
  value       = tls_private_key.custom_key.private_key_pem
  sensitive   = true
}

output "public_key" {
  description = "EC2 public key"
  value       = tls_private_key.custom_key.public_key_openssh
}

# ---------------------------------------------------------------------------
# ECS Airflow (second instance)
# ---------------------------------------------------------------------------
output "ecs_airflow_ecr_repository_url" {
  description = "ECR repository URL for the ECS Airflow image"
  value       = aws_ecr_repository.ecs_airflow.repository_url
}

output "ecs_airflow_cluster_name" {
  description = "ECS cluster running the second Airflow"
  value       = aws_ecs_cluster.ecs_airflow.name
}

output "ecs_airflow_worker_task_definition_family" {
  description = "Task definition family used by the AwsEcsExecutor"
  value       = aws_ecs_task_definition.ecs_airflow_worker.family
}

output "ecs_airflow_init_task_definition_family" {
  description = "Task definition family for the one-off DB migration/admin task"
  value       = aws_ecs_task_definition.ecs_airflow_init.family
}

output "ecs_airflow_security_group_id" {
  description = "Security group attached to the ECS Airflow tasks"
  value       = aws_security_group.ecs_airflow_tasks.id
}

output "ecs_airflow_subnets" {
  description = "Subnets used by the ECS Airflow tasks (default VPC)"
  value       = data.aws_subnets.default.ids
}

output "ecs_airflow_url" {
  description = "ECS Airflow UI URL (shared ALB, dedicated listener)"
  value       = "http://${aws_lb.airflow.dns_name}:${var.ecs_airflow_alb_port}"
}

# ---------------------------------------------------------------------------
# Instacart ML pipeline
# ---------------------------------------------------------------------------
output "ml_s3_bucket" {
  description = "S3 bucket holding Instacart raw/parquet/features/models"
  value       = aws_s3_bucket.ml.bucket
}

output "ml_ecr_repository_url" {
  description = "ECR repository URL for the training image"
  value       = aws_ecr_repository.ml.repository_url
}

output "ml_inference_ecr_repository_url" {
  description = "ECR repository URL for the inference image"
  value       = aws_ecr_repository.ml_inference.repository_url
}

output "ml_ecs_cluster_name" {
  description = "ECS cluster running the ML tasks and inference service"
  value       = aws_ecs_cluster.ml.name
}

output "ml_task_definition_families" {
  description = "Task definition families for each pipeline step"
  value = {
    for k, v in aws_ecs_task_definition.ml : k => v.family
  }
}

output "ml_inference_service_name" {
  description = "ECS service name for the inference API"
  value       = aws_ecs_service.ml_inference.name
}

output "ml_inference_task_definition_family" {
  description = "Task definition family for the inference API"
  value       = aws_ecs_task_definition.ml_inference.family
}

output "ml_security_group_id" {
  description = "Security group attached to ML tasks"
  value       = aws_security_group.ml_tasks.id
}

output "ml_subnets" {
  description = "Subnets used by the ML tasks (default VPC)"
  value       = data.aws_subnets.default.ids
}

output "ml_inference_url" {
  description = "Instacart reorder-model inference API base URL"
  value       = "http://${aws_lb.airflow.dns_name}:${var.ml_inference_port}"
}

# ---------------------------------------------------------------------------
# Feast feature store
# ---------------------------------------------------------------------------
output "feast_db_endpoint" {
  description = "Feast online-store RDS endpoint"
  value       = aws_db_instance.feast.address
}

output "feast_db_name" {
  description = "Feast database name"
  value       = aws_db_instance.feast.db_name
}

output "feast_image_repository_url" {
  description = "ECR repository URL for the Feast image"
  value       = aws_ecr_repository.feast.repository_url
}

output "feast_task_definition_family" {
  description = "ECS task definition family that runs feast apply + materialize"
  value       = aws_ecs_task_definition.feast.family
}

output "feast_offline_path" {
  description = "S3 parquet path used as the Feast offline store"
  value       = local.feast_offline_path
}

# ---------------------------------------------------------------------------
# Ray Serve + Go gRPC inference
# ---------------------------------------------------------------------------
output "ray_serve_ecr_repository_url" {
  description = "ECR repository URL for the Ray Serve image"
  value       = aws_ecr_repository.ray_serve.repository_url
}

output "inference_rpc_ecr_repository_url" {
  description = "ECR repository URL for the Go gRPC gateway image"
  value       = aws_ecr_repository.inference_rpc.repository_url
}

output "rpc_nlb_dns_name" {
  description = "NLB DNS name for the gRPC inference endpoint"
  value       = aws_lb.rpc.dns_name
}

output "rpc_endpoint" {
  description = "gRPC endpoint (host:port) for the inference gateway"
  value       = "${aws_lb.rpc.dns_name}:50051"
}

output "rpc_task_definition_family" {
  description = "Task definition family for the Ray Serve + gRPC task"
  value       = aws_ecs_task_definition.rpc.family
}

# ---------------------------------------------------------------------------
# MLflow (Databricks-hosted tracking server)
# ---------------------------------------------------------------------------
output "mlflow_tracking_uri" {
  description = "MLflow tracking URI used by the ECS ML tasks"
  value       = var.mlflow_tracking_uri
}

output "mlflow_experiment_name" {
  description = "MLflow experiment the pipeline logs to"
  value       = var.mlflow_experiment_name
}

output "mlflow_tracking_token_parameter" {
  description = "SSM parameter holding the Databricks PAT (set out-of-band)"
  value       = aws_ssm_parameter.mlflow_tracking_token.name
}

# ---------------------------------------------------------------------------
# Analytics Postgres (Mode Analytics)
# ---------------------------------------------------------------------------
output "analytics_db_endpoint" {
  description = "Public DNS endpoint of the analytics Postgres"
  value       = aws_db_instance.analytics.address
}

output "analytics_db_port" {
  description = "Analytics Postgres port"
  value       = aws_db_instance.analytics.port
}

output "analytics_db_name" {
  description = "Analytics database name"
  value       = var.analytics_db_name
}

output "analytics_mode_user" {
  description = "Read-only username for Mode Analytics"
  value       = var.analytics_mode_username
}

output "analytics_mode_password" {
  description = "Read-only password for Mode Analytics"
  value       = random_password.analytics_mode.result
  sensitive   = true
}

output "analytics_connection_url" {
  description = "Postgres URL for Mode Analytics (read-only role)"
  value = format(
    "postgresql://%s:%s@%s:%s/%s?sslmode=require",
    var.analytics_mode_username,
    random_password.analytics_mode.result,
    aws_db_instance.analytics.address,
    aws_db_instance.analytics.port,
    var.analytics_db_name,
  )
  sensitive = true
}

output "analytics_bootstrap_task_definition_family" {
  description = "Task definition that creates the analytics schema + roles"
  value       = aws_ecs_task_definition.analytics_bootstrap.family
}
