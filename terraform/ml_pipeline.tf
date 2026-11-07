# =============================================================================
# Instacart reorder-prediction ML pipeline on ECS (Fargate + Ray)
# -----------------------------------------------------------------------------
# Additive to the EC2 Airflow and the ECS Airflow stacks. Provisions:
#   * an S3 bucket for raw/parquet/features/models
#   * ECR repos for the training image and the inference image
#   * an ECS cluster running one-off Ray training tasks and a long-lived
#     FastAPI inference service behind the shared ALB (new listener)
# =============================================================================

data "aws_caller_identity" "current" {}

locals {
  ml_name  = "${var.project_name}-${var.environment}-ml"
  ml_image = var.ml_training_image != "" ? var.ml_training_image : "${aws_ecr_repository.ml.repository_url}:${var.ml_image_tag}"
  ml_serve_image = var.ml_inference_image != "" ? var.ml_inference_image : (
    "${aws_ecr_repository.ml_inference.repository_url}:${var.ml_image_tag}"
  )

  ml_raw_prefix      = "raw/instacart"
  ml_parquet_prefix  = "parquet/instacart"
  ml_features_prefix = "features/instacart"
  ml_models_prefix   = "models/instacart"

  ml_feature_columns = join(",", [
    "times_bought",
    "reorder_rate",
    "avg_add_to_cart",
    "min_add_to_cart",
    "max_add_to_cart",
    "user_total_orders",
    "user_avg_days_between_orders",
    "user_reorder_rate",
    "times_bought_per_order",
    "days_since_last_purchase",
    "product_reorder_rate",
    "product_order_count",
    "product_avg_add_to_cart",
    "department_id",
    "aisle_id",
  ])

  ml_common_environment = [
    { name = "AWS_REGION", value = var.aws_region },
    { name = "ML_S3_BUCKET", value = aws_s3_bucket.ml.bucket },
    { name = "ML_RAW_PREFIX", value = local.ml_raw_prefix },
    { name = "ML_PARQUET_PREFIX", value = local.ml_parquet_prefix },
    { name = "ML_FEATURES_PREFIX", value = local.ml_features_prefix },
    { name = "ML_MODELS_PREFIX", value = local.ml_models_prefix },
    { name = "ML_SAMPLE_FRACTION", value = var.ml_sample_fraction },
    { name = "ML_RUN_ID", value = "manual" },
    { name = "ML_ECS_CLUSTER", value = aws_ecs_cluster.ml.name },
    { name = "ML_ECS_SERVICE", value = aws_ecs_service.ml_inference.name },
    # MLflow (Databricks). The token is injected via `secrets` below.
    { name = "ML_DAG_ID", value = "instacart_ml_pipeline" },
    { name = "MLFLOW_TRACKING_URI", value = var.mlflow_tracking_uri },
    { name = "MLFLOW_EXPERIMENT_NAME", value = var.mlflow_experiment_name },
    # Analytics Postgres (Mode Analytics). Password is a `secrets` entry.
    { name = "ANALYTICS_DB_HOST", value = aws_db_instance.analytics.address },
    { name = "ANALYTICS_DB_PORT", value = "5432" },
    { name = "ANALYTICS_DB_NAME", value = var.analytics_db_name },
    { name = "ANALYTICS_DB_USER", value = var.analytics_writer_username },
    { name = "ANALYTICS_DB_SSLMODE", value = "require" },
  ]

  ml_task_definitions = {
    # ingest reads the full prior CSV when the data was not pre-sampled, so it
    # gets the larger training-sized task.
    ingest     = { command = ["python", "ingest.py"], cpu = var.ml_train_cpu, memory = var.ml_train_memory }
    preprocess = { command = ["python", "preprocess.py"], cpu = var.ml_train_cpu, memory = var.ml_train_memory }
    train      = { command = ["python", "train.py"], cpu = var.ml_train_cpu, memory = var.ml_train_memory }
    evaluate   = { command = ["python", "evaluate.py"], cpu = var.ml_worker_cpu, memory = var.ml_worker_memory }
    deploy     = { command = ["python", "deploy.py"], cpu = var.ml_worker_cpu, memory = var.ml_worker_memory }
  }

  ml_tags = {
    Project     = var.project_name
    Environment = var.environment
    Component   = "instacart-ml"
  }
}

# ---------------------------------------------------------------------------
# S3
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "ml" {
  bucket        = "${local.ml_name}-${data.aws_caller_identity.current.account_id}"
  force_destroy = var.ml_bucket_force_destroy
  tags          = local.ml_tags
}

resource "aws_s3_bucket_versioning" "ml" {
  bucket = aws_s3_bucket.ml.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ml" {
  bucket = aws_s3_bucket.ml.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "ml" {
  bucket                  = aws_s3_bucket.ml.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "ml" {
  bucket = aws_s3_bucket.ml.id

  rule {
    id     = "expire-old-parquet"
    status = "Enabled"
    filter {
      prefix = "${local.ml_parquet_prefix}/"
    }
    expiration {
      days = var.ml_parquet_expiration_days
    }
  }

  rule {
    id     = "expire-old-models"
    status = "Enabled"
    filter {
      prefix = "${local.ml_models_prefix}/"
    }
    expiration {
      days = var.ml_model_expiration_days
    }
  }
}

# ---------------------------------------------------------------------------
# ECR
# ---------------------------------------------------------------------------
resource "aws_ecr_repository" "ml" {
  name                 = "${local.ml_name}-training"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = local.ml_tags
}

resource "aws_ecr_repository" "ml_inference" {
  name                 = "${local.ml_name}-inference"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = local.ml_tags
}

resource "aws_ecr_lifecycle_policy" "ml" {
  for_each = {
    training  = aws_ecr_repository.ml.name
    inference = aws_ecr_repository.ml_inference.name
  }

  repository = each.value
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the last 15 images"
        selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 15 }
        action       = { type = "expire" }
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# ECS cluster
# ---------------------------------------------------------------------------
resource "aws_ecs_cluster" "ml" {
  name = local.ml_name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = local.ml_tags
}

resource "aws_ecs_cluster_capacity_providers" "ml" {
  cluster_name       = aws_ecs_cluster.ml.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
    base              = 1
  }
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "ml" {
  for_each = toset(["ingest", "preprocess", "train", "evaluate", "deploy", "inference"])

  name              = "/${var.project_name}/${var.environment}/ecs-airflow/ml/${each.value}"
  retention_in_days = var.log_retention_days
  tags              = local.ml_tags
}

# ---------------------------------------------------------------------------
# IAM
# ---------------------------------------------------------------------------
resource "aws_iam_role" "ml_execution" {
  name = "${local.ml_name}-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ml_execution" {
  role       = aws_iam_role.ml_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ml_task" {
  name = "${local.ml_name}-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "ml_task" {
  name = "${local.ml_name}-task"
  role = aws_iam_role.ml_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "DataBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = [aws_s3_bucket.ml.arn]
      },
      {
        Sid      = "DataObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = ["${aws_s3_bucket.ml.arn}/*"]
      },
      {
        Sid    = "RedeployInference"
        Effect = "Allow"
        Action = ["ecs:UpdateService", "ecs:DescribeServices"]
        # Built as a string (instead of referencing the service) to avoid a
        # dependency cycle: service -> task definition -> task role -> policy.
        Resource = ["arn:aws:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:service/${aws_ecs_cluster.ml.name}/${local.ml_name}-inference"]
      },
      {
        Sid      = "Logs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
        Resource = ["arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/${var.project_name}/${var.environment}/ecs-airflow/ml/*:*"]
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
resource "aws_security_group" "ml_tasks" {
  name        = "${local.ml_name}-tasks"
  description = "Instacart ML ECS tasks"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "Inference API from the shared ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.ml_tags
}

# ---------------------------------------------------------------------------
# Task definitions
# ---------------------------------------------------------------------------
resource "aws_ecs_task_definition" "ml" {
  for_each = local.ml_task_definitions

  family                   = "${local.ml_name}-${each.key}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = aws_iam_role.ml_execution.arn
  task_role_arn            = aws_iam_role.ml_task.arn

  container_definitions = jsonencode([
    {
      name      = "ml-task"
      image     = local.ml_image
      essential = true
      command   = each.value.command
      environment = concat(
        local.ml_common_environment,
        [
          # Ray object store sized small to be safe on Fargate's /dev/shm.
          { name = "ML_RAY_OBJECT_STORE_BYTES", value = "300000000" },
        ],
      )
      secrets = [
        { name = "MLFLOW_TRACKING_TOKEN", valueFrom = aws_ssm_parameter.mlflow_tracking_token.arn },
        { name = "ANALYTICS_DB_PASSWORD", valueFrom = aws_ssm_parameter.analytics_writer_password.arn },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ml[each.key].name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs/${each.key}"
        }
      }
    }
  ])

  tags = local.ml_tags
}

resource "aws_ecs_task_definition" "ml_inference" {
  family                   = "${local.ml_name}-inference"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ml_inference_cpu
  memory                   = var.ml_inference_memory
  execution_role_arn       = aws_iam_role.ml_execution.arn
  task_role_arn            = aws_iam_role.ml_task.arn

  container_definitions = jsonencode([
    {
      name      = "ml-inference"
      image     = local.ml_serve_image
      essential = true
      portMappings = [{
        containerPort = 8000
        protocol      = "tcp"
      }]
      environment = [
        { name = "AWS_REGION", value = var.aws_region },
        { name = "ML_S3_BUCKET", value = aws_s3_bucket.ml.bucket },
        { name = "ML_MODELS_PREFIX", value = local.ml_models_prefix },
        { name = "ML_FEATURE_COLUMNS", value = local.ml_feature_columns },
        # Feast online store (Postgres) for /predict_online.
        { name = "FEAST_DB_HOST", value = aws_db_instance.feast.address },
        { name = "FEAST_DB_PORT", value = "5432" },
        { name = "FEAST_DB_NAME", value = var.feast_db_name },
        { name = "FEAST_DB_USER", value = var.feast_db_username },
        { name = "FEAST_REGISTRY", value = "/tmp/feast/registry.db" },
        { name = "FEAST_OFFLINE_PATH", value = local.feast_offline_path },
      ]
      secrets = [
        { name = "FEAST_DB_PASSWORD", valueFrom = aws_ssm_parameter.feast_db_password.arn },
      ]
      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 5
        startPeriod = 30
      }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ml["inference"].name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs/inference"
        }
      }
    }
  ])

  tags = local.ml_tags
}

# ---------------------------------------------------------------------------
# Inference service behind the shared ALB
# ---------------------------------------------------------------------------
resource "aws_lb_target_group" "ml_inference" {
  name        = substr("${local.ml_name}-inf-tg", 0, 32)
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
    path                = "/health"
    matcher             = "200"
  }

  tags = local.ml_tags
}

resource "aws_lb_listener" "ml_inference" {
  load_balancer_arn = aws_lb.airflow.arn
  port              = var.ml_inference_port
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ml_inference.arn
  }

  tags = local.ml_tags
}

resource "aws_ecs_service" "ml_inference" {
  name            = "${local.ml_name}-inference"
  cluster         = aws_ecs_cluster.ml.id
  task_definition = aws_ecs_task_definition.ml_inference.arn
  desired_count   = var.ml_inference_desired_count
  launch_type     = "FARGATE"

  health_check_grace_period_seconds = 60

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.ml_tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.ml_inference.arn
    container_name   = "ml-inference"
    container_port   = 8000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener.ml_inference, aws_iam_role_policy.ml_task]

  lifecycle {
    ignore_changes = [desired_count]
  }

  tags = local.ml_tags
}
