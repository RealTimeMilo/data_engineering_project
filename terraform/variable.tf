## AWS account level config
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
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
variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.20.0.0/16"
}

variable "airflow_port" {
  description = "Airflow webserver port behind the ALB"
  type        = number
  default     = 8080
}

## DNS / TLS (leave domain_name empty to skip Route53 + ACM)
variable "domain_name" {
  description = "FQDN for Airflow (e.g. airflow.example.com). Empty disables Route53/HTTPS."
  type        = string
  default     = "data-platform-airflow"
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
  type = set(string)
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
