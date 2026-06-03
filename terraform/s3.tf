# locals {
#   base_name = "your-org-ml"
#   env       = "prod"
#   tags = {
#     Environment = local.env
#     ManagedBy   = "terraform"
#     Project     = "ml-pipelines"
#   }
# }

# # ============================================================
# # AIRFLOW-SPECIFIC BUCKETS
# # ============================================================

# # Store DAG files, plugins, and requirements for Airflow workers
# resource "aws_s3_bucket" "airflow_dags" {
#   bucket = "${local.base_name}-airflow-dags-${local.env}"
#   tags   = local.tags
# }

# resource "aws_s3_bucket_versioning" "airflow_dags" {
#   bucket = aws_s3_bucket.airflow_dags.id
#   versioning_configuration {
#     status = "Enabled"
#   }
# }

# # Centralized Airflow task execution logs
# resource "aws_s3_bucket" "airflow_logs" {
#   bucket = "${local.base_name}-airflow-logs-${local.env}"
#   tags   = local.tags
# }

# resource "aws_s3_bucket_lifecycle_configuration" "airflow_logs" {
#   bucket = aws_s3_bucket.airflow_logs.id
#   rule {
#     id     = "expire-old-logs"
#     status = "Enabled"
#     expiration {
#       days = 90
#     }
#   }
# }

# # ============================================================
# # ECS & DOCKER ARTIFACTS
# # ============================================================

# # Docker build context, Dockerfiles, and build logs
# resource "aws_s3_bucket" "ecs_docker_artifacts" {
#   bucket = "${local.base_name}-ecs-docker-artifacts-${local.env}"
#   tags   = local.tags
# }

# # ECS task definition JSON templates and overrides
# resource "aws_s3_bucket" "ecs_task_definitions" {
#   bucket = "${local.base_name}-ecs-task-definitions-${local.env}"
#   tags   = local.tags
# }

# # ECS task execution logs (stdout/stderr from containers)
# resource "aws_s3_bucket" "ecs_task_logs" {
#   bucket = "${local.base_name}-ecs-task-logs-${local.env}"
#   tags   = local.tags
# }

# resource "aws_s3_bucket_lifecycle_configuration" "ecs_task_logs" {
#   bucket = aws_s3_bucket.ecs_task_logs.id
#   rule {
#     id     = "archive-logs"
#     status = "Enabled"
#     transition {
#       days          = 30
#       storage_class = "STANDARD_IA"
#     }
#     expiration {
#       days = 365
#     }
#   }
# }

# # ============================================================
# # ML PIPELINE DATA FLOW
# # ============================================================

# # Raw data landing zone (immutable, append-only)
# resource "aws_s3_bucket" "raw_data_lake" {
#   bucket = "${local.base_name}-raw-data-lake-${local.env}"
#   tags   = local.tags
# }

# # Curated training datasets (post-validation)
# resource "aws_s3_bucket" "training_datasets" {
#   bucket = "${local.base_name}-training-datasets-${local.env}"
#   tags   = local.tags
# }

# # Feature store outputs (pre-computed features for training/inference)
# resource "aws_s3_bucket" "feature_store" {
#   bucket = "${local.base_name}-feature-store-${local.env}"
#   tags   = local.tags
# }

# # Pipeline intermediate results & checkpoints (Airflow XComs, partial outputs)
# resource "aws_s3_bucket" "pipeline_checkpoints" {
#   bucket = "${local.base_name}-pipeline-checkpoints-${local.env}"
#   tags   = local.tags
# }

# # Async inference request/response payloads
# resource "aws_s3_bucket" "inference_jobs" {
#   bucket = "${local.base_name}-inference-jobs-${local.env}"
#   tags   = local.tags
# }

# # ============================================================
# # CONFIGURATION & GOVERNANCE
# # ============================================================

# # Pipeline configuration files, parameters, and environment overrides
# resource "aws_s3_bucket" "pipeline_configs" {
#   bucket = "${local.base_name}-pipeline-configs-${local.env}"
#   tags   = local.tags
# }

# # Audit trail: access logs, pipeline execution metadata, compliance
# resource "aws_s3_bucket" "ml_audit_logs" {
#   bucket = "${local.base_name}-ml-audit-logs-${local.env}"
#   tags   = local.tags
# }

# resource "aws_s3_bucket_server_side_encryption_configuration" "ml_audit_logs" {
#   bucket = aws_s3_bucket.ml_audit_logs.id
#   rule {
#     apply_server_side_encryption_by_default {
#       sse_algorithm = "AES256"
#     }
#   }
# }

# # ============================================================
# # EXISTING BUCKETS (CORRECTED NAMING)
# # ============================================================

# resource "aws_s3_bucket" "predictions" {
#   bucket = "${local.base_name}-predictions-${local.env}"
#   tags   = local.tags
# }

# resource "aws_s3_bucket" "model_artifacts" {
#   bucket = "${local.base_name}-model-artifacts-${local.env}" # Fixed: no spaces
#   tags   = local.tags
# }

# resource "aws_s3_bucket" "ml_metrics_evaluation" {
#   bucket = "${local.base_name}-ml-metrics-evaluation-${local.env}" # Fixed: no & or _
#   tags   = local.tags
# }

# resource "aws_s3_bucket" "ecs_ml_logs" {
#   bucket = "${local.base_name}-ecs-ml-logs-${local.env}" # Fixed: no slashes
#   tags   = local.tags
# }

# resource "aws_s3_bucket" "processed_feature_data" {
#   bucket = "${local.base_name}-processed-feature-data-${local.env}" # Fixed: no slashes
#   tags   = local.tags
# }

# resource "aws_s3_bucket" "ml_models" {
#   bucket = "${local.base_name}-models-${local.env}"
#   tags   = local.tags
# }

# resource "aws_s3_bucket_versioning" "ml_models" {
#   bucket = aws_s3_bucket.ml_models.id
#   versioning_configuration {
#     status = "Enabled"
#   }
# }