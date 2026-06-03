# resource "aws_ecs_cluster" "airflow_cluster" {
#     name = "airflow-cluster"

#     setting {
#         name  = "containerInsights"
#         value = "enabled"
#         }
  
#   tags = {
#     Name = "airflow-cluster"
#   }
# }

# data "aws_iam_role" "airflow-role" {
#   name = "test.workflow"
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
# }

# resource "aws_ecs_task_definition" "service" {
#   family                   = "airflow_webserver"
#   requires_compatibilities = ["FARGATE"]
#   container_definitions    = jsonencode([
#     {
#       name         = "app"
#       image        = "local/airflow:3.2.1"
#       cpu          = 10
#       memory       = 512
#       essential    = true
#       portMappings = [
#         {
#           containerPort = 8080
#           hostPort      = 8080
#           protocol      = "tcp"
#         }
#       ]
#     },
#   ])
# }