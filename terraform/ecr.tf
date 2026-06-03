# resource "aws_ecr_repository" "repo" {
#     name = "ml-platform-airflow-infra"
#     image_tag_mutability = "MUTABLE"
#     force_delete         = true
    
#     image_scanning_configuration {
#         scan_on_push = true
#   }
# }

# # Keep only the last 15 images to save space/money
# resource "aws_ecr_lifecycle_policy" "repo_policy" {
#   repository = aws_ecr_repository.app_repo.name

#   policy = <<EOF
# {
#     "rules": [
#         {
#             "rulePriority": 1,
#             "description": "Keep last 15 images",
#             "selection": {
#                 "tagStatus": "any",
#                 "countType": "imageCountMoreThan",
#                 "countNumber": 15
#             },
#             "action": {
#                 "type": "expire"
#             }
#         }
#     ]
# }
# EOF
# }

# # ============================================================
# # ECR REPOSITORIES FOR ML PIPELINE CONTAINERS
# # ============================================================

# # Base ML training container (PyTorch/TensorFlow/Scikit-learn)
# resource "aws_ecr_repository" "ml_training_base" {
#   name                 = "${local.base_name}/ml-training-base"
#   image_tag_mutability = "IMMUTABLE"
  
#   image_scanning_configuration {
#     scan_on_push = true
#   }
  
#   encryption_configuration {
#     encryption_type = "AES256"
#   }
  
#   tags = local.tags
# }

# # Feature engineering container
# resource "aws_ecr_repository" "ml_feature_engineering" {
#   name                 = "${local.base_name}/ml-feature-engineering"
#   image_tag_mutability = "IMMUTABLE"
  
#   image_scanning_configuration {
#     scan_on_push = true
#   }
  
#   encryption_configuration {
#     encryption_type = "AES256"
#   }
  
#   tags = local.tags
# }

# # Model inference/serving container
# resource "aws_ecr_repository" "ml_inference" {
#   name                 = "${local.base_name}/ml-inference"
#   image_tag_mutability = "IMMUTABLE"
  
#   image_scanning_configuration {
#     scan_on_push = true
#   }
  
#   encryption_configuration {
#     encryption_type = "AES256"
#   }
  
#   tags = local.tags
# }

# # Airflow worker executor container (customized with ML deps)
# resource "aws_ecr_repository" "airflow_worker" {
#   name                 = "${local.base_name}/airflow-worker"
#   image_tag_mutability = "IMMUTABLE"
  
#   image_scanning_configuration {
#     scan_on_push = true
#   }
  
#   encryption_configuration {
#     encryption_type = "AES256"
#   }
  
#   tags = local.tags
# }

# # Batch prediction job container
# resource "aws_ecr_repository" "ml_batch_predictor" {
#   name                 = "${local.base_name}/ml-batch-predictor"
#   image_tag_mutability = "IMMUTABLE"
  
#   image_scanning_configuration {
#     scan_on_push = true
#   }
  
#   encryption_configuration {
#     encryption_type = "AES256"
#   }
  
#   tags = local.tags
# }

# # Lifecycle policies to manage image retention
# resource "aws_ecr_lifecycle_policy" "ml_training_base" {
#   repository = aws_ecr_repository.ml_training_base.name
#   policy = jsonencode({
#     rules = [
#       {
#         rulePriority = 1
#         description  = "Keep last 10 production images"
#         selection = {
#           tagStatus   = "tagged"
#           tagPrefixList = ["prod", "v"]
#           countType   = "imageCountMoreThan"
#           countNumber = 10
#         }
#         action = {
#           type = "expire"
#         }
#       },
#       {
#         rulePriority = 2
#         description  = "Delete untagged images after 7 days"
#         selection = {
#           tagStatus   = "untagged"
#           countType   = "sinceImagePushed"
#           countUnit   = "days"
#           countNumber = 7
#         }
#         action = {
#           type = "expire"
#         }
#       }
#     ]
#   })
# }

# # ECR pull-through cache for Docker Hub (optional, reduces external pulls)
# resource "aws_ecr_pull_through_cache_rule" "docker_hub" {
#   ecr_repository_prefix = "docker-hub"
#   upstream_registry_url = "registry-1.docker.io"
# }
