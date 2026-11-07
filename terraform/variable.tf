## AWS account level config
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-2"
}

variable "project_name" {
  description = "Prefix for resource names"
  type        = string
  default     = "sde-airflow"
}

variable "environment" {
  description = "Deployment environment (e.g., dev, prod)"
  type        = string
  default     = "dev"
}

## Networking
# variable "vpc_cidr" {
#   description = "VPC CIDR block"
#   type        = string
#   default     = "10.20.0.0/16"
# }

variable "airflow_port" {
  description = "Airflow webserver port behind the ALB"
  type        = number
  default     = 8080
}

## DNS / TLS (leave domain_name empty to skip Route53 + ACM)
variable "domain_name" {
  description = "FQDN for Airflow (e.g. airflow.example.com). Empty disables Route53/HTTPS."
  type        = string
  default     = "data-platform-airflow.ohmilo.com"
}

variable "route53_zone_id" {
  description = "Existing Route53 hosted zone ID. If empty and domain_name is set, a new zone is created."
  type        = string
  default     = ""
}

## Security
variable "key_name" {
  description = "EC2 key pair name prefix"
  type        = string
  default     = "sde-key"
}

variable "admin_cidr_blocks" {
  description = "CIDR blocks allowed for SSH to EC2"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "enable_waf" {
  description = "Attach AWS WAF to the ALB"
  type        = bool
  default     = true
}

variable "waf_rate_limit" {
  description = "WAF rate limit per 5 minutes per IP"
  type        = number
  default     = 2000
}

## Compute
variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium"
}

variable "repo_url" {
  description = "Git repository URL cloned on EC2 bootstrap"
  type        = string
  default     = "https://github.com/RealTimeMilo/data_engineering_project.git"
}

## Observability
variable "log_retention_days" {
  description = "CloudWatch Logs retention"
  type        = number
  default     = 14
}

## Alerts
variable "alert_email_id" {
  description = "Email for budget and alarm notifications"
  type        = string
  default     = "miloxrr@gmail.com"
}

// Database variables
variable "postgres_uri" {
  type        = string
  description = "The postgres uri of your postgres db, if none provided a postgres db in rds is made. Format \"<db_username>:<db_password>@<db_endpoint>:<db_port>/<db_name>\""
  default     = ""
}

variable "rds_allocated_storage" {
  type        = number
  description = "The allocated storage for the rds db in gibibytes"
  default     = 20
}

variable "rds_storage_type" {
  type        = string
  description = <<EOT
  One of `"standard"` (magnetic), `"gp2"` (general purpose SSD), or `"io1"` (provisioned IOPS SSD)
  EOT
  default     = "standard"
}

variable "rds_engine" {
  type        = string
  description = <<EOT
  The database engine to use. For supported values, see the Engine parameter in [API action CreateDBInstance](https://docs.aws.amazon.com/AmazonRDS/latest/APIReference/API_CreateDBInstance.html)
  EOT
  default     = "postgres"
}

variable "rds_username" {
  type        = string
  description = "Username of rds"
  default     = "airflow"
}

variable "rds_password" {
  type        = string
  description = "Password of rds"
  default     = ""
}

variable "rds_instance_class" {
  type        = string
  description = "The class of instance you want to give to your rds db"
  default     = "db.t2.micro"
}

variable "rds_availability_zone" {
  type        = string
  description = "Availability zone for the rds instance"
  default     = "eu-west-1a"
}

variable "rds_skip_final_snapshot" {
  type        = bool
  description = "Whether or not to skip the final snapshot before deleting (mainly for tests)"
  default     = false
}

variable "rds_deletion_protection" {
  type        = bool
  description = "Deletion protection for the rds instance"
  default     = false
}

variable "rds_version" {
  type        = string
  description = "The DB version to use for the RDS instance"
  default     = "12.7"
}

// S3 Bucket
variable "s3_bucket_name" {
  type        = string
  default     = ""
  description = "The S3 bucket name where the DAGs and startup scripts will be stored, leave this blank to let this module create a s3 bucket for you. WARNING: this module will put files into the path \"dags/\" and \"startup/\" of the bucket"
}

variable "service_names" {
  description = "Name of the ECR Respositories"
  type        = set(string)
}

## ECS Airflow (second Airflow instance)
## See terraform/ecs_airflow.tf — additive to the EC2 Airflow defined in main.tf.

variable "create_ecs_airflow_rds" {
  description = "Create a new RDS Postgres instance for the ECS Airflow metadata DB. Ignored when ecs_airflow_postgres_uri is set."
  type        = bool
  default     = true
}

variable "ecs_airflow_postgres_uri" {
  description = "Existing metadata DB connection string (postgresql+psycopg2://user:pass@host:5432/db). When set, no RDS instance is created."
  type        = string
  default     = ""
}

variable "ecs_airflow_image" {
  description = "Full container image URI for the ECS Airflow. Defaults to the ECR repo created by this module."
  type        = string
  default     = ""
}

variable "ecs_airflow_image_tag" {
  description = "Image tag to deploy to the ECS Airflow services"
  type        = string
  default     = "latest"
}

variable "ecs_airflow_cpu" {
  description = "CPU units for a control-plane task (1024 = 1 vCPU)"
  type        = string
  default     = "1024"
}

variable "ecs_airflow_memory" {
  description = "Memory (MiB) for a control-plane task"
  type        = string
  default     = "2048"
}

variable "ecs_airflow_worker_cpu" {
  description = "CPU units for an ephemeral DAG worker task (1024 = 1 vCPU)"
  type        = string
  default     = "512"
}

variable "ecs_airflow_worker_memory" {
  description = "Memory (MiB) for an ephemeral DAG worker task"
  type        = string
  default     = "1024"
}

variable "ecs_airflow_desired_count" {
  description = "Desired task count for each control-plane service"
  type        = number
  default     = 1
}

variable "ecs_airflow_alb_port" {
  description = "ALB listener port dedicated to the ECS Airflow (EC2 Airflow keeps :80)"
  type        = number
  default     = 8081
}

variable "ecs_airflow_db_name" {
  description = "Postgres database name for the ECS Airflow metadata"
  type        = string
  default     = "airflow_ecs"
}

variable "ecs_airflow_db_username" {
  description = "Postgres username for the ECS Airflow metadata database"
  type        = string
  default     = "airflow_ecs"
}

variable "ecs_airflow_rds_instance_class" {
  description = "Instance class for the ECS Airflow metadata RDS"
  type        = string
  default     = "db.t3.micro"
}

variable "ecs_airflow_rds_engine_version" {
  description = "Postgres engine version for the ECS Airflow metadata RDS"
  type        = string
  default     = "16"
}

variable "ecs_airflow_rds_allocated_storage" {
  description = "Allocated storage (GiB) for the ECS Airflow metadata RDS"
  type        = number
  default     = 20
}

variable "ecs_airflow_rds_backup_retention_days" {
  description = "Backup retention (days) for the ECS Airflow metadata RDS"
  type        = number
  default     = 1
}

variable "ecs_airflow_admin_username" {
  description = "Admin username created by the one-off init task"
  type        = string
  default     = "airflow"
}

variable "ecs_airflow_admin_password" {
  description = "Admin password created by the one-off init task"
  type        = string
  default     = "airflow"
  sensitive   = true
}

variable "ecs_airflow_admin_email" {
  description = "Admin email created by the one-off init task"
  type        = string
  default     = "airflow@example.com"
}

## Instacart reorder-model ML pipeline (see terraform/ml_pipeline.tf)

variable "ml_image_tag" {
  description = "Image tag deployed to the ML training and inference tasks"
  type        = string
  default     = "latest"
}

variable "ml_training_image" {
  description = "Override the training image URI. Defaults to the ECR repo created here."
  type        = string
  default     = ""
}

variable "ml_inference_image" {
  description = "Override the inference image URI. Defaults to the ECR repo created here."
  type        = string
  default     = ""
}

variable "ml_train_cpu" {
  description = "CPU units for the Ray preprocess/train tasks (4096 = 4 vCPU)"
  type        = string
  default     = "4096"
}

variable "ml_train_memory" {
  description = "Memory (MiB) for the Ray preprocess/train tasks"
  type        = string
  default     = "16384"
}

variable "ml_worker_cpu" {
  description = "CPU units for the ingest/evaluate/deploy tasks"
  type        = string
  default     = "2048"
}

variable "ml_worker_memory" {
  description = "Memory (MiB) for the ingest/evaluate/deploy tasks"
  type        = string
  default     = "4096"
}

variable "ml_inference_cpu" {
  description = "CPU units for the inference service task"
  type        = string
  default     = "1024"
}

variable "ml_inference_memory" {
  description = "Memory (MiB) for the inference service task"
  type        = string
  default     = "2048"
}

variable "ml_inference_desired_count" {
  description = "Desired task count for the inference service"
  type        = number
  default     = 1
}

variable "ml_inference_port" {
  description = "ALB listener port dedicated to the ML inference API"
  type        = number
  default     = 8082
}

variable "ml_sample_fraction" {
  description = "Default fraction of users the ingest step samples"
  type        = string
  default     = "0.1"
}

variable "ml_bucket_force_destroy" {
  description = "Allow Terraform to delete the ML bucket even if it contains objects"
  type        = bool
  default     = true
}

variable "ml_parquet_expiration_days" {
  description = "Days before intermediate parquet is expired"
  type        = number
  default     = 30
}

variable "ml_model_expiration_days" {
  description = "Days before model artifacts are expired"
  type        = number
  default     = 90
}

## Feast feature store (see terraform/feast.tf)

variable "feast_image" {
  description = "Override the Feast image URI. Defaults to the ECR repo created here."
  type        = string
  default     = ""
}

variable "feast_db_name" {
  description = "Postgres database name for the Feast online store"
  type        = string
  default     = "feast"
}

variable "feast_db_username" {
  description = "Postgres username for the Feast online store"
  type        = string
  default     = "feast"
}

variable "feast_rds_instance_class" {
  description = "Instance class for the Feast RDS"
  type        = string
  default     = "db.t3.micro"
}

variable "feast_rds_engine_version" {
  description = "Postgres engine version for the Feast RDS"
  type        = string
  default     = "16"
}

variable "feast_rds_allocated_storage" {
  description = "Allocated storage (GiB) for the Feast RDS"
  type        = number
  default     = 20
}

## Analytics Postgres for Mode Analytics (see terraform/analytics.tf)

variable "analytics_db_name" {
  description = "Database name for the analytics Postgres"
  type        = string
  default     = "analytics"
}

variable "analytics_admin_username" {
  description = "RDS master username for the analytics Postgres"
  type        = string
  default     = "analytics_admin"
}

variable "analytics_writer_username" {
  description = "Pipeline writer role on the analytics Postgres"
  type        = string
  default     = "ml_writer"
}

variable "analytics_mode_username" {
  description = "Read-only role used by Mode Analytics"
  type        = string
  default     = "mode_readonly"
}

variable "analytics_rds_instance_class" {
  description = "Instance class for the analytics RDS"
  type        = string
  default     = "db.t3.micro"
}

variable "analytics_rds_engine_version" {
  description = "Postgres engine version for the analytics RDS"
  type        = string
  default     = "16"
}

variable "analytics_rds_allocated_storage" {
  description = "Allocated storage (GiB) for the analytics RDS"
  type        = number
  default     = 20
}

## MLflow (Databricks-hosted tracking server)

variable "mlflow_tracking_uri" {
  description = "MLflow tracking URI; empty disables MLflow logging"
  type        = string
  default     = "https://dbc-be947809-b49e.cloud.databricks.com"
}

variable "mlflow_experiment_name" {
  description = "Databricks MLflow experiment path (must be absolute)"
  type        = string
  default     = "/Shared/instacart-reorder"
}

variable "mlflow_tracking_token" {
  description = "Databricks PAT for MLflow. Prefer setting the SSM parameter out-of-band; this is only the initial value."
  type        = string
  default     = "unset"
  sensitive   = true
}

## Ray Serve + Go gRPC inference (see terraform/rpc_serving.tf)


variable "ray_serve_image" {
  description = "Override the Ray Serve image URI. Defaults to the ECR repo created here."
  type        = string
  default     = ""
}

variable "inference_rpc_image" {
  description = "Override the Go gRPC gateway image URI. Defaults to the ECR repo created here."
  type        = string
  default     = ""
}

variable "rpc_cpu" {
  description = "CPU units for the Ray Serve + gRPC Fargate task"
  type        = string
  default     = "2048"
}

variable "rpc_memory" {
  description = "Memory (MiB) for the Ray Serve + gRPC Fargate task"
  type        = string
  default     = "4096"
}

variable "rpc_desired_count" {
  description = "Desired task count for the RPC inference service"
  type        = number
  default     = 1
}

# resource "ecs_cluster" "data_eng" {
#   name = "data-eng"
# }

# resource "datadog_monitor" "airflow_scheduler_heartbeat" {
#   name = "[Data Platform Airflow] Scheduler No Heartbeat"
#   type = "query alert"
#   query = "sum(last_10m):avg:airflow.schedeuler_heartbeat(environment:production,ecs_cluster:data-eng).as_count() <= 0"
#   message = <<-EOT

#   UI
#   https://data-platform-airflow.icprivate.com/home

#   Runbook https://instacart.atlassian.net/wiki/spaces/DATA/pages/34343344/Airflow+monitor+and+runbook
#   @opsgenie-IC-SF-DataEng-Platform-Orchestration-P1
#   EOT

#   tags = ["team:data-eng-platform"]

#   monitor_thresholds {
#     critical = 0
#     critical_recovery = 1
#   }

#   notify_audit = false
#   require_full_window = false
#   notify_no_data = true
#   renotify_interval = 0
#   include_tags = true
#   no_data_timeframe = 10
#   priority = 1
# }

# module "airflow-test" {
#   count = var.environment == "development" ? 1 : 0
#   source = "github.com/instacart/terraform-airflow?ref=v1.20.3"
#   environment = var.environment
#   domain = var.domain
#   tags = module.tags
#   cluster_name = "infra"
#   has_autoscaling = false
#   name = "airflow2-test"
#   app_name = "airflow2-playground"
#   create_db_parameter_group = true
#   pgbouncer_security_group = module.pgbouncer-defaults.security_groups
#   rds_database_name = "airflow2test"
#   target_group_deresgestration_delay = var.target_group_deresgestration_delay
#   webserver_dashed_name = true
#   proxy_webserver = true
#   load_balancer_security_group_ids = {"LoadBalancer Security Group" = data.terraform_remote_state.ecs-clusters.outputs.data_eng_ecs}

#   ecs_cluster_name = {
#     "infra-dev"
#   }
# }
