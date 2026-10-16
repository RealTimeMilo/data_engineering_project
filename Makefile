####################################################################################################################
# Setup containers to run Airflow

docker-spin-up:
	@rm -rf containers/airflow/dags
	@mkdir -p containers/airflow/dags
	@cp -R dags/. containers/airflow/dags/
	docker compose build && docker compose up airflow-init && docker compose up -d

perms:
	sudo mkdir -p logs plugins temp dags tests migrations data visualization && sudo chmod -R u=rwx,g=rwx,o=rwx logs plugins temp dags tests migrations data visualization

up: perms docker-spin-up 

down:
	docker compose down --volumes --rmi all

restart: down up

sh:
	docker exec -ti webserver bash

####################################################################################################################
# Testing, auto formatting, type checks, & Lint checks

pytest:
	docker exec data_engineering_project_template-airflow-apiserver-1 pytest -p no:warnings -v /opt/airflow/tests

format:
	docker exec data_engineering_project_template-airflow-apiserver-1 python -m black -S --line-length 79 .

isort:
	docker exec data_engineering_project_template-airflow-apiserver-1 isort .

type:
	docker exec data_engineering_project_template-airflow-apiserver-1 mypy --ignore-missing-imports /opt/airflow

lint: 
	docker exec data_engineering_project_template-airflow-apiserver-1 flake8 /opt/airflow/dags

ci: isort format type lint pytest

####################################################################################################################
# Set up cloud infrastructure

tf-init:
	terraform -chdir=./terraform init

infra-up:
	terraform -chdir=./terraform apply

infra-down:
	terraform -chdir=./terraform destroy

infra-config:
	terraform -chdir=./terraform output

####################################################################################################################
# Port forwarding to local machine

cloud-metaflow:
	terraform -chdir=./terraform output -raw private_key > private_key.pem && chmod 600 private_key.pem && ssh -o "IdentitiesOnly yes" -i private_key.pem ubuntu@$$(terraform -chdir=./terraform output -raw ec2_public_dns) -N -f -L 3001:$$(terraform -chdir=./terraform output -raw ec2_public_dns):3000 && open http://localhost:3001 && rm private_key.pem

cloud-airflow:
	terraform -chdir=./terraform output -raw private_key > private_key.pem && chmod 600 private_key.pem && ssh -o "IdentitiesOnly yes" -i private_key.pem ubuntu@$$(terraform -chdir=./terraform output -raw ec2_public_dns) -N -f -L 8081:$$(terraform -chdir=./terraform output -raw ec2_public_dns):8080 && open http://localhost:8081 && rm private_key.pem

####################################################################################################################
# ECS Airflow (second instance)

# Must match `aws_region` in terraform/variable.tf (override on the CLI if needed).
ECS_AWS_REGION ?= us-east-2
ECS_AIRFLOW_IMAGE_TAG ?= latest

ecr-login:
	aws ecr get-login-password --region $(ECS_AWS_REGION) | docker login --username AWS --password-stdin $$(terraform -chdir=./terraform output -raw ecs_airflow_ecr_repository_url | cut -d/ -f1)

# Stage the repo's dags/ into the image build context, then bake them into
# /opt/airflow/dags so they show up under Airflow's default local DAG bundle.
ecs-airflow-build:
	@rm -rf containers/airflow/dags
	@mkdir -p containers/airflow/dags
	@rsync -a --exclude '__pycache__' --exclude '*.pyc' --exclude '.DS_Store' dags/ containers/airflow/dags/
	docker build --platform linux/amd64 -t $$(terraform -chdir=./terraform output -raw ecs_airflow_ecr_repository_url):$(ECS_AIRFLOW_IMAGE_TAG) ./containers/airflow

ecs-airflow-push: ecs-airflow-build
	docker push $$(terraform -chdir=./terraform output -raw ecs_airflow_ecr_repository_url):$(ECS_AIRFLOW_IMAGE_TAG)

# Run the one-off DB migration + admin bootstrap task (run AFTER `make infra-up`).
ecs-airflow-init:
	aws ecs run-task \
		--region $(ECS_AWS_REGION) \
		--cluster $$(terraform -chdir=./terraform output -raw ecs_airflow_cluster_name) \
		--task-definition $$(terraform -chdir=./terraform output -raw ecs_airflow_init_task_definition_family) \
		--launch-type FARGATE \
		--network-configuration "awsvpcConfiguration={subnets=[$$(terraform -chdir=./terraform output -json ecs_airflow_subnets | jq -r 'join(",")')],securityGroups=[$$(terraform -chdir=./terraform output -raw ecs_airflow_security_group_id)],assignPublicIp=ENABLED}"

# Point the instacart_ml_pipeline DAG at the ML subnets/security group (values
# come from the Terraform outputs). Run once the API server is up; rerun after
# any change that rotates the subnets/SG. Without this the DAG fails with
# "InvalidParameterException: subnets can not be empty".
ecs-airflow-vars:
	bash scripts/set_airflow_vars.sh

####################################################################################################################
# Instacart ML pipeline (train + serve on ECS with Ray)

ML_AWS_REGION ?= us-east-2
ML_IMAGE_TAG ?= latest
SAMPLE_FRACTION ?= 0.1

# 1. (optional) create a local user-level sample to keep uploads small
ml-sample:
	python scripts/sample_instacart.py --fraction $(SAMPLE_FRACTION)

# 2. upload raw CSVs (or instacart_data/sample if it exists) to the ML bucket
ml-upload-data:
	@src=instacart_data; \
	if [ -d instacart_data/sample ]; then src=instacart_data/sample; fi; \
	echo "Uploading $$src -> s3://$$(terraform -chdir=./terraform output -raw ml_s3_bucket)/raw/instacart"; \
	aws s3 sync $$src s3://$$(terraform -chdir=./terraform output -raw ml_s3_bucket)/raw/instacart --exclude '*' --include '*.csv'

ml-ecr-login:
	aws ecr get-login-password --region $(ML_AWS_REGION) | docker login --username AWS --password-stdin $$(terraform -chdir=./terraform output -raw ml_ecr_repository_url | cut -d/ -f1)

# Training + inference images build from the repo root so they can include
# feast_repo/ (the serving image needs the Feast feature definitions).
ml-build:
	docker build --platform linux/amd64 -f containers/ml/Dockerfile -t $$(terraform -chdir=./terraform output -raw ml_ecr_repository_url):$(ML_IMAGE_TAG) containers/ml
	docker build --platform linux/amd64 -f containers/ml/serve/Dockerfile -t $$(terraform -chdir=./terraform output -raw ml_inference_ecr_repository_url):$(ML_IMAGE_TAG) .
	docker build --platform linux/amd64 -f containers/feast/Dockerfile -t $$(terraform -chdir=./terraform output -raw feast_image_repository_url):$(ML_IMAGE_TAG) .

ml-push: ml-build
	docker push $$(terraform -chdir=./terraform output -raw ml_ecr_repository_url):$(ML_IMAGE_TAG)
	docker push $$(terraform -chdir=./terraform output -raw ml_inference_ecr_repository_url):$(ML_IMAGE_TAG)
	docker push $$(terraform -chdir=./terraform output -raw feast_image_repository_url):$(ML_IMAGE_TAG)

# Ray Serve inference + Go gRPC gateway (terraform/rpc_serving.tf)
rpc-build:
	docker build --platform linux/amd64 -f containers/ray_serve/Dockerfile -t $$(terraform -chdir=./terraform output -raw ray_serve_ecr_repository_url):$(ML_IMAGE_TAG) .
	docker build --platform linux/amd64 -f containers/inference_rpc/Dockerfile -t $$(terraform -chdir=./terraform output -raw inference_rpc_ecr_repository_url):$(ML_IMAGE_TAG) .

rpc-push: rpc-build
	docker push $$(terraform -chdir=./terraform output -raw ray_serve_ecr_repository_url):$(ML_IMAGE_TAG)
	docker push $$(terraform -chdir=./terraform output -raw inference_rpc_ecr_repository_url):$(ML_IMAGE_TAG)

####################################################################################################################
# Feast feature-store notebook (online RDS + offline S3)

feast-tunnel:
	bash scripts/feast_tunnel.sh start

feast-tunnel-stop:
	bash scripts/feast_tunnel.sh stop

# Opens JupyterLab at http://localhost:8888 with the notebook in notebooks/.
# Reaches the private RDS through the SSH tunnel and uses your ~/.aws creds.
feast-notebook: feast-tunnel
	docker build --platform linux/amd64 -f notebooks/Dockerfile -t feast-notebook:local .
	docker run --rm -it -p 8888:8888 \
	  -e AWS_DEFAULT_REGION=$(ML_AWS_REGION) \
	  -e ML_S3_BUCKET=$$(terraform -chdir=./terraform output -raw ml_s3_bucket) \
	  -e FEAST_DB_HOST=host.docker.internal -e FEAST_DB_PORT=15432 -e FEAST_DB_SSLMODE=prefer \
	  -v $$HOME/.aws:/root/.aws:ro \
	  -v $$(pwd):/work -w /work \
	  feast-notebook:local

####################################################################################################################
# Helpers

ssh-ec2:
	terraform -chdir=./terraform output -raw private_key > private_key.pem && chmod 600 private_key.pem && ssh -o StrictHostKeyChecking=no -o IdentitiesOnly=yes -i private_key.pem ubuntu@$$(terraform -chdir=./terraform output -raw ec2_public_dns) && rm private_key.pem
