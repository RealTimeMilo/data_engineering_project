terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    datadog = {
      source = "DataDog/datadog"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
    postgresql = {
      source  = "cyrilgdn/postgresql"
      version = "~> 1.22"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.9"
    }
  }

  required_version = ">= 1.2.0"
}

# # Configure the GitHub Provider
# provider "github" {}

# # Add a user to the organization
# resource "github_membership" "membership_for_user_x" {
#   # ...
# }

# Configure the Datadog provider
# provider "datadog" {
#   api_key = var.datadog_api_key
#   app_key = var.datadog_app_key
# }

provider "aws" {
  region  = var.aws_region
  profile = "default"
}

# Create Launch Template Resource Block
# resource "aws_launch_template" "template" {
#   name_prefix     = "airflow-auto-scaling"
#   image_id        = data.aws_ami.ubuntu.id
#   instance_type   = "m4.large"
#   tags = {
#     Name: "airflow-auto-scaling"
#   }
# }

# resource "aws_autoscaling_group" "autoscale" {
#   name                  = "airflow-autoscaling-group"  
#   desired_capacity      = 1
#   max_size              = 3
#   min_size              = 1
#   health_check_type     = "EC2"

#   launch_template {
#     id      = aws_launch_template.template.id
#     version = "$Latest"
#   }
# }

# # Scale UP when CPU > 70%
# resource "aws_autoscaling_policy" "scale_up" {
#   name                   = "scale-up"
#   autoscaling_group_name = aws_autoscaling_group.autoscale.name
#   adjustment_type        = "ChangeInCapacity"
#   scaling_adjustment     = 1  # Add 1 instance
#   cooldown               = 300  # Wait 5 minutes before scaling again
# }

# # Scale DOWN when CPU < 30%
# resource "aws_autoscaling_policy" "scale_down" {
#   name                   = "scale-down"
#   autoscaling_group_name = aws_autoscaling_group.autoscale.name
#   adjustment_type        = "ChangeInCapacity"
#   scaling_adjustment     = -1  # Remove 1 instance
#   cooldown               = 300
# }

# # CloudWatch alarms to trigger the policies
# resource "aws_cloudwatch_metric_alarm" "high_cpu" {
#   alarm_name          = "high-cpu"
#   comparison_operator = "GreaterThanThreshold"
#   evaluation_periods  = 2
#   metric_name         = "CPUUtilization"
#   namespace           = "AWS/EC2"
#   period              = 120
#   statistic           = "Average"
#   threshold           = 70
#   alarm_actions       = [aws_autoscaling_policy.scale_up.arn]
  
#   dimensions = {
#     AutoScalingGroupName = aws_autoscaling_group.autoscale.name
#   }
# }

# resource "aws_cloudwatch_metric_alarm" "low_cpu" {
#   alarm_name          = "low-cpu"
#   comparison_operator = "LessThanThreshold"
#   evaluation_periods  = 2
#   metric_name         = "CPUUtilization"
#   namespace           = "AWS/EC2"
#   period              = 120
#   statistic           = "Average"
#   threshold           = 30
#   alarm_actions       = [aws_autoscaling_policy.scale_down.arn]
  
#   dimensions = {
#     AutoScalingGroupName = aws_autoscaling_group.autoscale.name
#   }
# }

# Create security group for access to EC2 from your Anywhere
resource "aws_security_group" "sde_security_group" {
  name        = "sde_security_group"
  description = "Security group to allow inbound SCP & outbound 8080 (Airflow) connections"

  ingress {
    description = "Inbound SCP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    # cidr_blocks = ["0.0.0.0/0"]
    cidr_blocks = var.admin_cidr_blocks
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Inbound Airflow"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    # cidr_blocks = ["0.0.0.0/0"]
    security_groups = [aws_security_group.alb.id]
  }

    ingress {
    description = "Inbound HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  tags = {
    Name = "sde_security_group"
  }
}

# output "ec2_public_ip" {
#   description = "Public IP of EC2 instance"
#   value       = aws_instance.sde_ec2.public_ip
# }

# output "airflow_url" {
#     description = "Airflow Web UI URL"
#     value       = "http://${aws_instance.sde_ec2.public_ip}:8080"
# }

# Create EC2 with IAM role to allow EMR, Redshift, & S3 access and security group 
resource "tls_private_key" "custom_key" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "generated_key" {
  key_name_prefix = var.key_name
  public_key      = tls_private_key.custom_key.public_key_openssh
}

data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
  owners = ["099720109477"] # Canonical
}

# resource "aws_iam_role" "ecs_task_execution_role" {
#   name = "airflow-ecs-task-execution-role"
  
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Action = "sts:AssumeRole"
#         Effect = "Allow"
#         Principal = {
#           Service = "ecs-tasks.amazonaws.com"
#         }
#       }
#     ]
#   })
# }

# resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
#   role       = aws_iam_role.ecs_task_execution_role.name
#   policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
# }

# resource "aws_iam_role" "ecs_task_role" {
#   name = "airflow-ecs-task-role"
  
#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Action = "sts:AssumeRole"
#         Effect = "Allow"
#         Principal = {
#           Service = "ecs-tasks.amazonaws.com"
#         }
#       }
#     ]
#   })
# }

# resource "aws_ecs_task_definition" "airflow_webserver" {
#   family                   = "airflow-webserver"
#   network_mode             = "awsvpc"
#   requires_compatibilities = ["FARGATE"]
#   cpu                      = "512"   # 0.5 vCPU
#   memory                   = "1024"  # 1 GB
#   execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
#   task_role_arn            = aws_iam_role.ecs_task_role.arn
  
#   container_definitions = jsonencode([
#     {
#       name  = "airflow-webserver"
#       image = "apache/airflow:2.7.1"
      
#       portMappings = [
#         {
#           containerPort = 8080
#           protocol      = "tcp"
#         }
#       ]
      
#       command = ["webserver"]
      
#       logConfiguration = {
#         logDriver = "awslogs"
#         options = {
#           "awslogs-group"         = "/ecs/airflow-webserver"
#           "awslogs-region"        = var.aws_region
#           "awslogs-stream-prefix" = "ecs"
#         }
#       }
#     }
#   ])
# }

# # Similar task definitions for scheduler and worker
# resource "aws_ecs_task_definition" "airflow_scheduler" {
#   family                   = "airflow-scheduler"
#   network_mode             = "awsvpc"
#   requires_compatibilities = ["FARGATE"]
#   cpu                      = "512"
#   memory                   = "1024"
#   execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
#   task_role_arn            = aws_iam_role.ecs_task_role.arn
  
#   container_definitions = jsonencode([
#     {
#       name    = "airflow-scheduler"
#       image   = "apache/airflow:2.7.1"
#       command = ["scheduler"]
      
#       environment = [
#         # Same as webserver
#       ]
      
#       logConfiguration = {
#         logDriver = "awslogs"
#         options = {
#           "awslogs-group"         = "/ecs/airflow-scheduler"
#           "awslogs-region"        = var.aws_region
#           "awslogs-stream-prefix" = "ecs"
#         }
#       }
#     }
#   ])
# }

# resource "aws_ecs_service" "airflow_webserver" {
#   name            = "airflow-webserver"
#   cluster         = aws_ecs_cluster.airflow_cluster.id
#   task_definition = aws_ecs_task_definition.airflow_webserver.arn
#   desired_count   = 1
#   launch_type     = "FARGATE"
  
#   network_configuration {
#     subnets          = [aws_subnet.public_subnet_1.id, aws_subnet.public_subnet_2.id]
#     security_groups  = [aws_security_group.airflow_sg.id]
#     assign_public_ip = true
#   }
  
#   load_balancer {
#     target_group_arn = aws_lb_target_group.airflow_tg.arn
#     container_name   = "airflow-webserver"
#     container_port   = 8080
#   }
  
#   depends_on = [aws_lb_listener.airflow_listener]
# }

# resource "aws_ecs_service" "airflow_scheduler" {
#   name            = "airflow-scheduler"
#   cluster         = aws_ecs_cluster.airflow_cluster.id
#   task_definition = aws_ecs_task_definition.airflow_scheduler.arn
#   desired_count   = 1
#   launch_type     = "FARGATE"
  
#   network_configuration {
#     subnets          = [aws_subnet.public_subnet_1.id, aws_subnet.public_subnet_2.id]
#     security_groups  = [aws_security_group.airflow_sg.id]
#     assign_public_ip = true
#   }
# }

resource "aws_instance" "sde_ec2" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type

  key_name        = aws_key_pair.generated_key.key_name
  security_groups = [aws_security_group.sde_security_group.name]

  root_block_device {
    volume_size           = 30  # GB
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  monitoring = true

  depends_on = [
    aws_lb_target_group.airflow
  ]

  tags = {
    Name = "airflow_ec2.0"
    Environment = var.environment
  }

  user_data = <<EOF
#!/bin/bash

echo "-------------------------START SETUP---------------------------"
sudo apt-get -y update

sudo apt-get -y install \
ca-certificates \
curl \
gnupg \
lsb-release

sudo apt -y install unzip

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get -y update
sudo apt-get -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo chmod 666 /var/run/docker.sock

sudo apt install make

# Create SSH key for git (if using private repo)
# sudo -u ubuntu ssh-keygen -t ed25519 -f /home/ubuntu/.ssh/id_ed25519 -N ""
# sudo -u ubuntu bash -c 'echo "Host github.com
#   StrictHostKeyChecking no
#   UserKnownHostsFile=/dev/null" > /home/ubuntu/.ssh/config'

# echo "SSH public key for GitHub deploy key:"
# cat /home/ubuntu/.ssh/id_ed25519.pub

echo 'Clone git repo to EC2'
cd /home/ubuntu && git clone ${var.repo_url}

echo 'CD to data_engineering_project directory'
cd data_engineering_project

echo 'Start containers & Run db migrations'
make up

echo "-------------------------END SETUP---------------------------"

EOF

}

# EC2 budget constraint
# resource "aws_budgets_budget" "ec2" {
#   name              = "budget-ec2-monthly"
#   budget_type       = "COST"
#   limit_amount      = "5"
#   limit_unit        = "USD"
#   time_period_end   = "2087-06-15_00:00"
#   time_period_start = "2022-10-22_00:00"
#   time_unit         = "MONTHLY"

#   notification {
#     comparison_operator        = "GREATER_THAN"
#     threshold                  = 100
#     threshold_type             = "PERCENTAGE"
#     notification_type          = "FORECASTED"
#     subscriber_email_addresses = [var.alert_email_id]
#   }
# }
