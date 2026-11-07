# =============================================================================
# Analytics Postgres for Mode Analytics
# -----------------------------------------------------------------------------
# A dedicated, publicly reachable (IP-allowlisted) Postgres that holds the
# `ml_analytics` schema:
#   * pipeline_runs      -- one row per Airflow/MLflow run
#   * model_metrics      -- one row per (run, stage, metric)
#   * model_predictions  -- one row per scored (user, product) pair
#
# Access model
#   * ml_writer       -- the ECS pipeline (insert/update, no DDL)
#   * mode_readonly   -- Mode Analytics (SELECT only, read-only transactions)
#   * analytics_admin -- RDS master, used only by the bootstrap task
#
# The instance is public because Mode's Direct Connect cannot tunnel; its
# security group only admits Mode's published egress IPs (plus the ML/Airflow
# security groups for in-VPC writes).
# =============================================================================

locals {
  analytics_name = "${var.project_name}-${var.environment}-analytics"

  # Mode Analytics Direct Connect egress addresses (eight /32s).
  # https://mode.com/help/articles/connecting-mode-to-your-database/
  analytics_mode_cidrs = [
    "54.68.30.98/32",
    "54.68.45.3/32",
    "34.209.23.118/32",
    "54.188.241.100/32",
    "52.43.195.103/32",
    "3.224.146.111/32",
    "54.221.238.89/32",
    "52.20.173.236/32",
  ]
}

# ---------------------------------------------------------------------------
# Credentials (generated; never in git or Terraform output in plaintext)
# ---------------------------------------------------------------------------
resource "random_password" "analytics_admin" {
  length  = 32
  special = false
}

resource "random_password" "analytics_writer" {
  length  = 32
  special = false
}

resource "random_password" "analytics_mode" {
  length  = 32
  special = false
}

resource "aws_ssm_parameter" "analytics_admin_password" {
  name  = "/${var.project_name}/${var.environment}/analytics/admin-password"
  type  = "SecureString"
  value = random_password.analytics_admin.result
  tags  = local.ml_tags
}

resource "aws_ssm_parameter" "analytics_writer_password" {
  name  = "/${var.project_name}/${var.environment}/analytics/writer-password"
  type  = "SecureString"
  value = random_password.analytics_writer.result
  tags  = local.ml_tags
}

resource "aws_ssm_parameter" "analytics_mode_password" {
  name  = "/${var.project_name}/${var.environment}/analytics/mode-password"
  type  = "SecureString"
  value = random_password.analytics_mode.result
  tags  = local.ml_tags
}

# The Databricks PAT is set out-of-band (aws ssm put-parameter) so it never
# lands in Terraform state. `ignore_changes` keeps later applies from reverting it.
resource "aws_ssm_parameter" "mlflow_tracking_token" {
  name  = "/${var.project_name}/${var.environment}/mlflow/tracking-token"
  type  = "SecureString"
  value = var.mlflow_tracking_token
  tags  = local.ml_tags

  lifecycle {
    ignore_changes = [value]
  }
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
resource "aws_security_group" "analytics_rds" {
  name        = "${local.analytics_name}-rds"
  description = "Analytics Postgres: Mode Analytics + in-VPC writers"
  vpc_id      = data.aws_vpc.default.id

  dynamic "ingress" {
    for_each = toset(local.analytics_mode_cidrs)
    content {
      description = "Mode Analytics Direct Connect"
      from_port   = 5432
      to_port     = 5432
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  ingress {
    description = "PostgreSQL from ECS ML + Airflow tasks and the EC2 bastion"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    security_groups = [
      aws_security_group.ml_tasks.id,
      aws_security_group.ecs_airflow_tasks.id,
      aws_security_group.sde_security_group.id,
    ]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.ml_tags
}

resource "aws_db_subnet_group" "analytics" {
  name       = "${local.analytics_name}-db-subnets"
  subnet_ids = data.aws_subnets.default.ids

  tags = local.ml_tags
}

resource "aws_db_parameter_group" "analytics" {
  name   = "${local.analytics_name}-pg16"
  family = "postgres16"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  tags = local.ml_tags
}

# ---------------------------------------------------------------------------
# Instance
# ---------------------------------------------------------------------------
resource "aws_db_instance" "analytics" {
  identifier              = "${local.analytics_name}-pg"
  engine                  = "postgres"
  engine_version          = var.analytics_rds_engine_version
  instance_class          = var.analytics_rds_instance_class
  allocated_storage       = var.analytics_rds_allocated_storage
  storage_type            = "gp3"
  storage_encrypted       = true
  db_name                 = var.analytics_db_name
  username                = var.analytics_admin_username
  password                = random_password.analytics_admin.result
  db_subnet_group_name    = aws_db_subnet_group.analytics.name
  vpc_security_group_ids  = [aws_security_group.analytics_rds.id]
  parameter_group_name    = aws_db_parameter_group.analytics.name
  publicly_accessible     = true
  multi_az                = false
  backup_retention_period = 1
  skip_final_snapshot     = true
  deletion_protection     = false
  apply_immediately       = true

  tags = merge(local.ml_tags, { Component = "analytics-postgres" })
}

# ---------------------------------------------------------------------------
# Bootstrap task (schema + roles), run once per stack
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "analytics_bootstrap" {
  name              = "/${var.project_name}/${var.environment}/ecs-airflow/ml/analytics-bootstrap"
  retention_in_days = var.log_retention_days
  tags              = local.ml_tags
}

resource "aws_iam_role_policy" "ml_execution_analytics_secrets" {
  name = "${local.ml_name}-execution-analytics"
  role = aws_iam_role.ml_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["ssm:GetParameters", "ssm:GetParameter"]
        Resource = [
          aws_ssm_parameter.analytics_admin_password.arn,
          aws_ssm_parameter.analytics_writer_password.arn,
          aws_ssm_parameter.analytics_mode_password.arn,
          aws_ssm_parameter.mlflow_tracking_token.arn,
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = ["*"]
      },
    ]
  })
}

resource "aws_ecs_task_definition" "analytics_bootstrap" {
  family                   = "${local.ml_name}-analytics-bootstrap"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ml_worker_cpu
  memory                   = var.ml_worker_memory
  execution_role_arn       = aws_iam_role.ml_execution.arn
  task_role_arn            = aws_iam_role.ml_task.arn

  container_definitions = jsonencode([
    {
      name      = "analytics-bootstrap"
      image     = local.ml_image
      essential = true
      command   = ["python", "bootstrap_analytics.py"]
      environment = [
        { name = "AWS_REGION", value = var.aws_region },
        { name = "ML_S3_BUCKET", value = aws_s3_bucket.ml.bucket },
        { name = "ANALYTICS_DB_HOST", value = aws_db_instance.analytics.address },
        { name = "ANALYTICS_DB_PORT", value = "5432" },
        { name = "ANALYTICS_DB_NAME", value = var.analytics_db_name },
        { name = "ANALYTICS_DB_SSLMODE", value = "require" },
        { name = "ANALYTICS_DB_ADMIN_USER", value = var.analytics_admin_username },
        { name = "ANALYTICS_DB_WRITER_USER", value = var.analytics_writer_username },
        { name = "ANALYTICS_MODE_USER", value = var.analytics_mode_username },
      ]
      secrets = [
        { name = "ANALYTICS_DB_ADMIN_PASSWORD", valueFrom = aws_ssm_parameter.analytics_admin_password.arn },
        { name = "ANALYTICS_DB_WRITER_PASSWORD", valueFrom = aws_ssm_parameter.analytics_writer_password.arn },
        { name = "ANALYTICS_MODE_PASSWORD", valueFrom = aws_ssm_parameter.analytics_mode_password.arn },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.analytics_bootstrap.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs/analytics-bootstrap"
        }
      }
    }
  ])

  tags = local.ml_tags
}
