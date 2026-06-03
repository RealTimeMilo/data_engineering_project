# ---------------------------------------------------------------------------
# CloudWatch Logs
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "airflow_app" {
  name              = "/${var.project_name}/${var.environment}/airflow"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.project_name}-${var.environment}-airflow-logs"
  }
}

resource "aws_cloudwatch_log_group" "ec2_system" {
  name              = "/${var.project_name}/${var.environment}/ec2/system"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "ec2_docker" {
  name              = "/${var.project_name}/${var.environment}/ec2/docker"
  retention_in_days = var.log_retention_days
}

# ---------------------------------------------------------------------------
# IAM — Observability agent (CloudWatch Agent + X-Ray + SSM)
# ---------------------------------------------------------------------------
resource "aws_iam_role" "ec2_observability" {
  name = "${var.project_name}-${var.environment}-ec2-observability"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "cloudwatch_agent" {
  role       = aws_iam_role.ec2_observability.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ec2_observability.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "cloudwatch_logs" {
  name = "${var.project_name}-${var.environment}-logs"
  role = aws_iam_role.ec2_observability.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          "${aws_cloudwatch_log_group.airflow_app.arn}:*",
          "${aws_cloudwatch_log_group.ec2_system.arn}:*",
          "${aws_cloudwatch_log_group.ec2_docker.arn}:*"
        ]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_observability" {
  name = "${var.project_name}-${var.environment}-ec2-profile"
  role = aws_iam_role.ec2_observability.name
}

# ---------------------------------------------------------------------------
# Alarms — ALB + EC2 + WAF
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "alb_unhealthy_hosts" {
  alarm_name          = "${var.project_name}-${var.environment}-alb-unhealthy"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Average"
  threshold           = 0
  alarm_description   = "ALB has unhealthy Airflow targets"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.airflow.arn_suffix
    TargetGroup  = aws_lb_target_group.airflow.arn_suffix
  }
}

resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${var.project_name}-${var.environment}-alb-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Elevated 5xx from Airflow targets"

  dimensions = {
    LoadBalancer = aws_lb.airflow.arn_suffix
    TargetGroup  = aws_lb_target_group.airflow.arn_suffix
  }
}

resource "aws_cloudwatch_metric_alarm" "ec2_cpu" {
  alarm_name          = "${var.project_name}-${var.environment}-ec2-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "EC2 CPU sustained high utilization"

  dimensions = {
    InstanceId = aws_instance.sde_ec2.id
  }
}

resource "aws_cloudwatch_metric_alarm" "waf_blocked" {
  count = var.enable_waf ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-waf-blocked"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BlockedRequests"
  namespace           = "AWS/WAFV2"
  period              = 300
  statistic           = "Sum"
  threshold           = 100
  alarm_description   = "WAF blocked unusual request volume"

  dimensions = {
    WebACL = aws_wafv2_web_acl.alb[0].name
    Region = var.aws_region
  }
}
