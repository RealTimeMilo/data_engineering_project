# # # create database subnet group
# # resource "aws_db_subnet_group" "database_subnet_group" {
# #   name        = "${var.project_name}-${var.environment}-database-subnets"
# #   subnet_ids  = [aws_subnet.private_data_subnet_az1.id, aws_subnet.private_data_subnet_az2.id]
# #   description = "subnets for database instance"

# #   tags = {
# #     Name = "${var.project_name}-${var.environment}-database-subnets"
# #   }
# # }

# # # create the rds instance
# # resource "aws_db_instance" "database_instance" {
# #   engine                 = "postgres"
# #   engine_version         = "14"
# #   multi_az               = var.multi_az_deployment
# #   identifier             = var.database_instance_identifier
# #   username               = var.db_user
# #   password               = var.db_password
# #   db_name                = var.db_name
# #   instance_class         = var.database_instance_class
# #   allocated_storage      = 200
# #   db_subnet_group_name   = aws_db_subnet_group.database_subnet_group.name
# #   vpc_security_group_ids = [aws_security_group.database_security_group.id]
# #   availability_zone      = data.aws_availability_zones.available_zones.names[0]
# #   skip_final_snapshot    = true
# #   publicly_accessible    = var.publicly_accessible
# # }

# # ============================================================
# # KMS KEY FOR ENCRYPTION (Shared across services)
# # ============================================================

# resource "aws_kms_key" "ml_platform" {
#   description             = "KMS key for ${local.base_name} ML platform encryption"
#   deletion_window_in_days = 7
#   enable_key_rotation     = true
  
#   tags = local.tags
# }

# resource "aws_kms_alias" "ml_platform" {
#   name          = "alias/${local.base_name}-ml-platform-${local.env}"
#   target_key_id = aws_kms_key.ml_platform.key_id
# }

# # ============================================================
# # RDS SUBNET GROUP & PARAMETER GROUP
# # ============================================================

# resource "aws_db_subnet_group" "ml_platform" {
#   name       = "${local.base_name}-ml-platform-${local.env}"
#   subnet_ids = aws_subnet.private[*].id
  
#   tags = merge(local.tags, {
#     Name = "${local.base_name}-ml-platform-${local.env}"
#   })
# }

# resource "aws_db_parameter_group" "airflow_postgres" {
#   name   = "${local.base_name}-airflow-postgres-${local.env}"
#   family = "postgres15"
  
#   parameter {
#     name  = "log_min_duration_statement"
#     value = "1000" # Log queries > 1s
#   }
  
#   parameter {
#     name  = "idle_in_transaction_session_timeout"
#     value = "300000" # 5 minutes
#   }
  
#   tags = local.tags
# }

# # ============================================================
# # RDS INSTANCE: AIRFLOW METADATA DATABASE
# # ============================================================

# resource "aws_db_instance" "airflow_metadata" {
#   identifier = "${local.base_name}-airflow-metadata-${local.env}"
  
#   # Engine
#   engine               = "postgres"
#   engine_version       = "15.4"
#   instance_class       = "db.m6g.large" # Graviton for cost/perf
#   allocated_storage    = 100
#   max_allocated_storage = 500
#   storage_type         = "gp3"
#   storage_encrypted    = true
#   kms_key_id           = aws_kms_key.ml_platform.arn
  
#   # Auth
#   db_name  = "airflow"
#   username = var.airflow_db_username
#   password = var.airflow_db_password # Use secrets manager in prod!
  
#   # Network
#   db_subnet_group_name   = aws_db_subnet_group.ml_platform.name
#   vpc_security_group_ids = [aws_security_group.rds_airflow.id]
#   publicly_accessible    = false
  
#   # High availability (enable for prod)
#   multi_az               = local.env == "prod" ? true : false
#   availability_zone      = local.env == "prod" ? null : data.aws_availability_zones.available.names[0]
  
#   # Performance
#   parameter_group_name = aws_db_parameter_group.airflow_postgres.name
#   backup_retention_period = local.env == "prod" ? 7 : 1
#   backup_window           = "03:00-04:00"
#   maintenance_window      = "sun:04:00-sun:05:00"
  
#   # Monitoring
#   performance_insights_kms_key_id = aws_kms_key.ml_platform.arn
#   monitoring_interval    = 60
#   monitoring_role_arn    = aws_iam_role.rds_enhanced_monitoring.arn
  
#   # Lifecycle
#   skip_final_snapshot = local.env == "prod" ? false : true
#   final_snapshot_identifier = local.env == "prod" ? "${local.base_name}-airflow-final-${local.env}" : null
  
#   tags = local.tags
# }

# # ============================================================
# # RDS INSTANCE: ML FEATURE/METADATA STORE (Optional)
# # ============================================================

# resource "aws_db_instance" "ml_metadata" {
#   identifier = "${local.base_name}-ml-metadata-${local.env}"
  
#   engine               = "postgres"
#   engine_version       = "15.4"
#   instance_class       = "db.m6g.medium"
#   allocated_storage    = 50
#   storage_type         = "gp3"
#   storage_encrypted    = true
#   kms_key_id           = aws_kms_key.ml_platform.arn
  
#   db_name  = "ml_metadata"
#   username = var.ml_metadata_db_username
#   password = var.ml_metadata_db_password
  
#   db_subnet_group_name   = aws_db_subnet_group.ml_platform.name
#   vpc_security_group_ids = [aws_security_group.rds_ml_metadata.id]
#   publicly_accessible    = false
  
#   multi_az = local.env == "prod"
  
#   parameter_group_name   = aws_db_parameter_group.airflow_postgres.name
#   backup_retention_period = local.env == "prod" ? 7 : 1
  
#   skip_final_snapshot = local.env == "prod" ? false : true
  
#   tags = merge(local.tags, {
#     Purpose = "ml-metadata-store"
#   })
# }

# # ============================================================
# # SECURITY GROUPS
# # ============================================================

# # RDS: Airflow metadata DB access
# resource "aws_security_group" "rds_airflow" {
#   name        = "${local.base_name}-rds-airflow-${local.env}"
#   description = "Allow access to Airflow metadata RDS from ECS/Airflow"
#   vpc_id      = aws_vpc.main.id
  
#   ingress {
#     description     = "PostgreSQL from ECS tasks"
#     from_port       = 5432
#     to_port         = 5432
#     protocol        = "tcp"
#     security_groups = [aws_security_group.ecs_tasks.id, aws_security_group.airflow_workers.id]
#   }
  
#   egress {
#     from_port   = 0
#     to_port     = 0
#     protocol    = "-1"
#     cidr_blocks = ["0.0.0.0/0"]
#   }
  
#   tags = local.tags
# }

# # RDS: ML metadata DB access
# resource "aws_security_group" "rds_ml_metadata" {
#   name        = "${local.base_name}-rds-ml-metadata-${local.env}"
#   description = "Allow access to ML metadata RDS from training/inference tasks"
#   vpc_id      = aws_vpc.main.id
  
#   ingress {
#     description     = "PostgreSQL from ML ECS tasks"
#     from_port       = 5432
#     to_port         = 5432
#     protocol        = "tcp"
#     security_groups = [aws_security_group.ecs_tasks.id]
#   }
  
#   egress {
#     from_port   = 0
#     to_port     = 0
#     protocol    = "-1"
#     cidr_blocks = ["0.0.0.0/0"]
#   }
  
#   tags = local.tags
# }

# # ============================================================
# # IAM ROLE: RDS Enhanced Monitoring
# # ============================================================

# resource "aws_iam_role" "rds_enhanced_monitoring" {
#   name = "${local.base_name}-rds-monitoring-${local.env}"
  
#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Action = "sts:AssumeRole"
#         Effect = "Allow"
#         Principal = {
#           Service = "monitoring.rds.amazonaws.com"
#         }
#       }
#     ]
#   })
  
#   tags = local.tags
# }

# resource "aws_iam_role_policy_attachment" "rds_monitoring" {
#   role       = aws_iam_role.rds_enhanced_monitoring.name
#   policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
# }