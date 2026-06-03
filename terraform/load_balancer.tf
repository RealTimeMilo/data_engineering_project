# Default VPC — keeps this file self-contained without a separate network module
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_lb" "airflow" {
  name               = "${var.project_name}-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.default.ids

  tags = {
    Name = "${var.project_name}-${var.environment}-alb"
  }
}

resource "aws_lb_target_group" "airflow" {
  name     = "${var.project_name}-${var.environment}-tg"
  port     = var.airflow_port
  protocol = "HTTP"
  vpc_id   = data.aws_vpc.default.id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
    path                = "/api/v2/monitor/health"
    matcher             = "200-399"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-tg"
  }
}

resource "aws_lb_target_group_attachment" "airflow_ec2" {
  target_group_arn = aws_lb_target_group.airflow.arn
  target_id        = aws_instance.sde_ec2.id
  port             = var.airflow_port
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.airflow.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.airflow.arn
  }
}
