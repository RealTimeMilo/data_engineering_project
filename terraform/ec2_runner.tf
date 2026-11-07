# =============================================================================
# EC2 wrapper instance role for the docker-compose Airflow
# -----------------------------------------------------------------------------
# The EC2 Airflow launches one-off ECS Fargate tasks with EcsRunTaskOperator.
# The operator uses the ambient credential chain, which on the instance is this
# role. Without it, task runs fail with NoCredentialsError.
#
# Scope: run/describe/stop ECS tasks, pass the ML task + execution roles, and
# read the ML log groups. Nothing account-wide beyond that.
# =============================================================================

import {
  to = aws_iam_role.ec2_ecs_runner
  id = "${var.project_name}-${var.environment}-ec2-ecs"
}

import {
  to = aws_iam_role_policy.ec2_ecs_runner
  id = "${var.project_name}-${var.environment}-ec2-ecs:ecs-run-ml-tasks"
}

import {
  to = aws_iam_instance_profile.ec2_ecs_runner
  id = "${var.project_name}-${var.environment}-ec2-ecs"
}

resource "aws_iam_role" "ec2_ecs_runner" {
  name = "${var.project_name}-${var.environment}-ec2-ecs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })

  tags = local.ml_tags
}

resource "aws_iam_role_policy" "ec2_ecs_runner" {
  name = "ecs-run-ml-tasks"
  role = aws_iam_role.ec2_ecs_runner.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask",
          "ecs:StartTask",
          "ecs:StopTask",
          "ecs:DescribeTasks",
          "ecs:DescribeTaskDefinition",
          "ecs:ListTasks",
          "ecs:TagResource",
          "ecs:ListServices",
          "ecs:DescribeServices",
          "ecs:ListClusters",
          "ecs:DescribeClusters",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = "iam:PassRole"
        Resource = [
          aws_iam_role.ml_task.arn,
          aws_iam_role.ml_execution.arn,
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:GetLogEvents",
          "logs:FilterLogEvents",
        ]
        Resource = [
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/${var.project_name}/${var.environment}/ecs-airflow/ml/*",
        ]
      },
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_ecs_runner" {
  name = "${var.project_name}-${var.environment}-ec2-ecs"
  role = aws_iam_role.ec2_ecs_runner.name

  tags = local.ml_tags
}
