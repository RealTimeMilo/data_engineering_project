
* [Data engineering project template](#data-engineering-project-template)
    * [Run Data Pipeline](#run-data-pipeline)
        * [Run on codespaces](#run-on-codespaces)
        * [Run locally](#run-locally)
    * [Architecture and services in this template](#architecture-and-services-in-this-template)
    * [Using template](#using-template)
    * [Writing pipelines](#writing-pipelines)
    * [(Optional) Advanced cloud setup](#optional-advanced-cloud-setup)
        * [Prerequisites:](#prerequisites)
        * [Tear down infra](#tear-down-infra)


# Data engineering project template

Detailed explanation can be found **[`in this post`](https://www.startdataengineering.com/post/data-engineering-projects-with-free-template/)**

## Run Data Pipeline

Code available at **[data_engineering_project_template](https://github.com/josephmachado/data_engineering_project_template/tree/main?tab=readme-ov-file#data-engineering-project-template)** repository.

### Run on codespaces

You can run this data pipeline using GitHub codespaces. Follow the instructions below.

1. Create codespaces by going to the **[data_engineering_project_template](https://github.com/josephmachado/data_engineering_project_template/tree/main?tab=readme-ov-file#data-engineering-project-template)** repository, cloning it(or click `Use this template` button) and then clicking on `Create codespaces on main` button.
2. Wait for codespaces to start, then in the terminal type `make up`.
3. Wait for `make up` to complete, and then wait for 30s (for Airflow to start).
4. After 30s go to the `ports` tab and click on the link exposing port `8080` to access Airflow UI (username and password is `airflow`).

![codespaces start](./assets/images/cs1.png)
![codespaces make up](./assets/images/cs2.png)
![codespaces open url](./assets/images/cs3.png)

### Run locally

To run locally, you need:

1. [git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
2. [Github account](https://github.com/)
3. [Docker](https://docs.docker.com/engine/install/) with at least 4GB of RAM and [Docker Compose](https://docs.docker.com/compose/install/) v1.27.0 or later

Clone the repo and run the following commands to start the data pipeline:

```bash
git clone https://github.com/josephmachado/data_engineering_project_template.git
cd data_engineering_project_template
make up
sleep 30 # wait for Airflow to start
make ci # run checks and tests
```
Go to [http:localhost:8080](http:localhost:8080) to see the Airflow UI. Username and password are both `airflow`.

## Architecture and services in this template

This data engineering project template, includes the following:

1. **`Airflow`**: To schedule and orchestrate DAGs.
2. **`Postgres`**: To store Airflow's details (which you can see via Airflow UI) and also has a schema to represent upstream databases.
3. **`DuckDB`**: To act as our warehouse
4. **`Quarto with Plotly`**: To convert code in `markdown` format to html files that can be embedded in your app or servered as is.
5. **`cuallee`**: To run data quality checks on the data we extracted from CoinCap API.
6. **`minio`**: To provide an S3 compatible open source storage system.

For simplicity services 1-5 of the above are installed and run in one container defined [here](./containers/airflow/Dockerfile).

![DET](./assets/images/det2.png)

The `coincap_elt` DAG in the [Airflow UI](http://localhost:8080) will look like the below image:

![DAG](./assets/images/dag.png)

You can see the rendered html at [./visualizations/dashboard.html](https://github.com/josephmachado/data_engineering_project_template/blob/main/visualization/dashboard.html).

The file structure of our repo is as shown below:

![File strucutre](./assets/images/fs.png)

## Using template

You can use this repo as a template and create your own, click on the `Use this template` button.

![Template](./assets/images/template.png)

## Writing pipelines

We have a sample pipeline at [coincap_elt.py](./dags/coincap_elt.py) that you can use as a starter to create your own DAGs. The tests are available at [./tests](./tests) folder.

### Dynamic DAG creation

Multiple CoinCap pipelines are generated from **[dags/config/pipelines.yaml](./dags/config/pipelines.yaml)** at scheduler parse time—see **[dags/dynamic_coincap_dags.py](./dags/dynamic_coincap_dags.py)** and **[dags/lib/coincap_factory.py](./dags/lib/coincap_factory.py)**.

To add a DAG, append an entry to `pipelines.yaml` (set `enabled: true`) **or** insert a row into `pipeline_config.pipelines` (see `migrations/001_pipeline_registry.sql`). SQL registry rows override YAML when `id` matches.

| `pipeline_type` | DAG id pattern | Behavior |
|-----------------|----------------|----------|
| `coincap_api` | `coincap_elt_<id>` | Fetch API → CSV → quality → optional dashboard |
| `sql_transform` | `sql_elt_<id>` | Load CSV → run `dags/<sql_file>` → Postgres analytics tables |

Example SQL-only pipeline: `sql_elt_exchanges_summary` (runs after `coincap_elt_exchanges` has written the CSV).

Apply the registry migration on an existing DB:

```bash
make db-migrate
```

Once the `coincap_elt` DAG runs, we can see the dashboard html at [./visualization/dashboard.html](./visualization/dashboard.html) and will look like ![Dashboard](./assets/images/dash.png).

## (Optional) Advanced cloud setup

If you want to run your code on an EC2 instance, with terraform, follow the steps below.

### Prerequisites:

1. [Terraform](https://learn.hashicorp.com/tutorials/terraform/install-cli) 
2. [AWS account](https://aws.amazon.com/) 
3. [AWS CLI installed](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) and [configured](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html)

You can create your GitHub repository based on this template by clicking on the `Use this template button in the **[data_engineering_project_template](https://github.com/josephmachado/data_engineering_project_template)** repository. Clone your repository and replace content in the following files

1. **[CODEOWNERS](https://github.com/josephmachado/data_engineering_project_template/blob/main/.github/CODEOWNERS)**: In this file change the user id from `@josephmachado` to your Github user id.
2. **[cd.yml](https://github.com/josephmachado/data_engineering_project_template/blob/main/.github/workflows/cd.yml)**: In this file change the `data_engineering_project_template` part of the `TARGET` parameter to your repository name.
3. **[variable.tf](https://github.com/josephmachado/data_engineering_project_template/blob/main/terraform/variable.tf)**: In this file change the default values for `alert_email_id` and `repo_url` variables with your email and [github repository url](https://www.theserverside.com/blog/Coffee-Talk-Java-News-Stories-and-Opinions/GitHub-URL-find-use-example) respectively.

Run the following commands in your project directory.

```shell
# Create AWS services with Terraform
make tf-init # Only needed on your first terraform run (or if you add new providers)
make infra-up # type in yes after verifying the changes TF will make

# Wait until the EC2 instance is initialized, you can check this via your AWS UI
# See "Status Check" on the EC2 console, it should be "2/2 checks passed" before proceeding
# Wait another 5 mins, Airflow takes a while to start up

make cloud-airflow # this command will forward Airflow port from EC2 to your machine and opens it in the browser
# the user name and password are both airflow

make cloud-metabase # this command will forward Metabase port from EC2 to your machine and opens it in the browser
# use https://github.com/josephmachado/data_engineering_project_template/blob/main/env file to connect to the warehouse from metabase
```

For the [continuous delivery](https://github.com/josephmachado/data_engineering_project_template/blob/main/.github/workflows/cd.yml) to work, set up the infrastructure with terraform, & defined the following repository secrets. You can set up the repository secrets by going to `Settings > Secrets > Actions > New repository secret`.

1. **`SERVER_SSH_KEY`**: We can get this by running `terraform -chdir=./terraform output -raw private_key` in the project directory and paste the entire content in a new Action secret called SERVER_SSH_KEY.
2. **`REMOTE_HOST`**: Get this by running `terraform -chdir=./terraform output -raw ec2_public_dns` in the project directory.
3. **`REMOTE_USER`**: The value for this is **ubuntu**.

### WorkOS AuthKit SSO (EC2 Airflow)

The EC2 Airflow UI can authenticate users through **WorkOS AuthKit**. It is
opt-in: when the WorkOS variables are unset, the UI keeps the default local DB
login (`airflow` / `airflow`), so this is safe to add to an existing stack.

How it works:

- `containers/airflow/webserver_config.py` is mounted read-only by
  `docker-compose.yml` (the ECS image is left untouched). When WorkOS is
  configured it sets `AUTH_TYPE = AUTH_OAUTH`, registers a `workos` OAuth
  provider against the AuthKit OIDC discovery document, and installs a small
  `FabAirflowSecurityManagerOverride` subclass that maps a WorkOS identity to an
  Airflow user.
- `Authlib` (OAuth client) and `Flask-Mail` (needed for self-registration) are
  added to `containers/airflow/requirements.txt`.

Set up:

1. In the WorkOS Dashboard create an **AuthKit** application and copy its
   **Client ID**, **Client secret**, and **AuthKit domain**
   (for example `https://your-app.authkit.app`).
2. Add the redirect URI to the AuthKit application:
   `<AIRFLOW__API__BASE_URL>/auth/oauth-authorized/workos`.
   On the ALB that is `http://<alb-dns>/auth/oauth-authorized/workos`.
3. Provide the values to the EC2 Airflow environment (repo `.env`, or CI/SSM):

   ```shell
   WORKOS_CLIENT_ID=client_...
   WORKOS_CLIENT_SECRET=sk_...
   WORKOS_AUTHKIT_DOMAIN=https://your-app.authkit.app
   # Public URL of the UI, used to build the OAuth redirect URI
   AIRFLOW__API__BASE_URL=http://<alb-dns>
   # optional
   WORKOS_DEFAULT_ROLE=Viewer
   WORKOS_ADMIN_EMAILS=you@example.com     # comma-separated; granted Admin
   ```
4. Rebuild and restart with `make up` (or let the CD deploy run), then sign in
   with the **WorkOS** button.

Notes:

- New users auto-register with `WORKOS_DEFAULT_ROLE` (`Viewer`); emails listed
  in `WORKOS_ADMIN_EMAILS` are granted `Admin`.
- The REST API still uses HTTP basic auth with the local admin user, so API
  access and CI are unaffected.
- To disable SSO, unset the `WORKOS_*` variables and restart; DB login returns.

### Second Airflow instance on ECS (Fargate)

In addition to the EC2 Airflow, `terraform/ecs_airflow.tf` provisions a second,
independent Airflow that runs on ECS Fargate and is **additive** — it does not
modify the EC2 stack.

- **Control plane**: `api-server`, `scheduler`, `dag-processor`, and `triggerer`
  run as Fargate services in a dedicated ECS cluster (`sde-airflow-dev-ecs`).
- **Task execution**: the scheduler uses Airflow's `AwsEcsExecutor` to launch
  each DAG task as an ephemeral Fargate task (see
  `containers/airflow/ecs_executor_config.sh`).
- **Metadata**: its own `airflow_ecs` Postgres database. A small RDS instance is
  created by default; set `ecs_airflow_postgres_uri` in `terraform.tfvars` to
  reuse an existing Postgres server instead (and set `create_ecs_airflow_rds = false`).
- **Access**: a new listener on the shared ALB at port `8081`. The EC2 Airflow
  keeps the `:80` listener untouched; WAF still covers the shared ALB.

After `make infra-up` (this creates both the EC2 and ECS stacks):

```shell
# 1. Build the Airflow image and push it to the new ECR repo
make ecr-login
make ecs-airflow-push ECS_AIRFLOW_IMAGE_TAG=v1

# 2. Point the services at the pushed tag (or bake it into terraform.tfvars)
#    ecs_airflow_image_tag = "v1"
make infra-up

# 3. Run the one-off DB migration + admin bootstrap task
make ecs-airflow-init

# 4. Create the Airflow Variables the instacart_ml_pipeline DAG needs
make ecs-airflow-vars

# 5. Open the ECS Airflow UI (username/password: airflow / airflow)
terraform -chdir=./terraform output -raw ecs_airflow_url
```

Notes:

- DAGs are baked into the image (`dags/` is copied to `/opt/airflow/dags`) and
  discovered via Airflow's default local DAG bundle, so no Git connection is
  required for them to appear. (Only the EC2 Airflow uses the Git DAG bundle,
  configured in `containers/airflow/ec2_airflow_config.sh`.)
- The control-plane services start before the database is migrated and will
  restart until `make ecs-airflow-init` has run once.
- To use an existing metadata server, set
  `ecs_airflow_postgres_uri = "postgresql+psycopg2://user:pass@host:5432/airflow_ecs"`
  and `create_ecs_airflow_rds = false`.

### Instacart reorder model on ECS (Ray + FastAPI)

`terraform/ml_pipeline.tf` provisions a self-contained ML stack on top of the
existing infrastructure:

- **S3 bucket** for `raw/`, `parquet/`, `features/`, and `models/instacart/`.
- **ECR repos** `…-ml-training` (pipeline image) and `…-ml-inference` (FastAPI).
- **ECS cluster** `sde-airflow-dev-ml` running one-off Fargate tasks and a
  long-lived inference service.
- **Shared ALB** gets a new listener on port `8082` for the inference API.

The pipeline (`containers/ml/`):

| Step | Script | What it does |
|------|--------|--------------|
| ingest | `ingest.py` | Reads raw CSVs from S3, samples a user fraction, writes parquet |
| preprocess | `preprocess.py` | Ray Data group-bys over the prior interactions → user/product features, labels from `order_products__train`, user-based split |
| train | `train.py` | Ray Train + LightGBM binary classifier (`ray.train.lightgbm`) |
| evaluate | `evaluate.py` | ROC-AUC / PR-AUC / accuracy / log-loss on the held-out test split |
| deploy | `deploy.py` | Promotes the run to `models/instacart/latest/` and force-redeploys the inference service |

**Model task:** predict whether a user will *reorder* a product they have bought
before. Candidate set = all (user, product) pairs in the prior orders; label =
presence in the user's `train` order. Split is by `user_id % 10`, so no user
leaks between train/val/test.

Deploy it:

```shell
make infra-up                    # creates S3 + ECR + ECS cluster + inference service
make ml-ecr-login

# (optional) shrink the upload first
make ml-sample SAMPLE_FRACTION=0.1
make ml-upload-data              # uploads *.csv to s3://<bucket>/raw/instacart/

make ml-push ML_IMAGE_TAG=v1     # builds + pushes both images
make infra-up                    # rolls the inference task to tag v1
```

Run the pipeline from Airflow (DAG `instacart_ml_pipeline`, triggered manually):

```shell
# On the ECS Airflow:
terraform -chdir=./terraform output -raw ecs_airflow_url
# Trigger "instacart_ml_pipeline" with a sample_fraction param.
```

Query the inference API:

```shell
URL=$(terraform -chdir=./terraform output -raw ml_inference_url)
curl "$URL/health"
curl -X POST "$URL/predict" -H 'Content-Type: application/json' -d '{
  "instances": [{
    "times_bought": 3, "reorder_rate": 0.66, "avg_add_to_cart": 5,
    "min_add_to_cart": 2, "max_add_to_cart": 9, "user_total_orders": 12,
    "user_avg_days_between_orders": 7.5, "user_reorder_rate": 0.6,
    "times_bought_per_order": 0.25, "days_since_last_purchase": 2,
    "product_reorder_rate": 0.7, "product_order_count": 500,
    "product_avg_add_to_cart": 6, "department_id": 4, "aisle_id": 31
  }]
}'
```

Notes:

- The DAG launches each step as an ECS task via `EcsRunTaskOperator`; it uses
  `ML_AWS_CONN_ID` (default: ambient task role) plus the `ML_TASK_DEF_*`,
  `ML_ECS_CLUSTER`, `ML_SUBNET_IDS` and `ML_SECURITY_GROUP` Airflow Variables.
  `make ecs-airflow-vars` creates the variable values from the Terraform
  outputs; without them the DAG fails with
  `InvalidParameterException: subnets can not be empty`.
- Ray runs as a single-node cluster sized to the task's vCPUs. Object store
  memory is capped (`ML_RAY_OBJECT_STORE_BYTES`) because Fargate's `/dev/shm`
  is small; the pipeline keeps intermediate tables small via sampling.
- The inference service loads `models/instacart/latest/model.txt` from S3 at
  startup, so `deploy` only has to copy the artifact and force a new deployment.

### Feature store (RDS + Feast)

`terraform/feast.tf` provisions a dedicated **RDS Postgres** instance for Feast
and the ECS task that populates it:

- **Online store** = RDS Postgres (`sde-airflow-dev-feast-pg`).
- **Offline store** = the parquet that `preprocess.py` writes to
  `s3://<ml-bucket>/features/instacart/offline/features.parquet`.
- `feast_repo/` holds the entity + feature-view definitions
  (`user`, `product`, `user_product_reorder_features`), a runtime
  `feature_store.yaml` generator, and `apply_materialize.py`.
- The ML DAG runs `feast_materialize` between `preprocess` and `train`,
  launching the `sde-airflow-dev-ml-feast` task (container `feast`).
- The inference service (`containers/ml/serve/app.py`) can serve features
  directly from the online store via `POST /predict_online`.

Build + push the Feast image (from the repo root, alongside the others):

```shell
make ml-push ML_IMAGE_TAG=v1      # builds training, inference, and feast images
```

Run the pipeline (which now includes materialization), or materialize alone:

```shell
ML_START=preprocess bash scripts/run_ml_pipeline.sh   # ingest..preprocess..feast..train..evaluate..deploy
```

Query online features through the model service:

```shell
URL=$(terraform -chdir=./terraform output -raw ml_inference_url)
curl -X POST "$URL/predict_online" -H 'Content-Type: application/json' \
  -d '{"entities": [{"user_id": 1, "product_id": 196}]}'
```

#### Feature-store notebook (online + offline)

`notebooks/feast_feature_store.ipynb` inspects the `user_product_reorder_features`
view from both stores:

- **Online** — the Feast RDS Postgres tables (`instacart_user_product_reorder_features`),
  via the Feast SDK and via raw SQL.
- **Offline** — the S3 parquet history, read directly with pandas and via Feast
  point-in-time (`get_historical_features`).

The RDS is private, so the notebook reaches it through an SSH tunnel via the EC2
instance; S3 is read directly. Run:

```shell
make feast-notebook        # starts the tunnel, builds a Jupyter image, serves http://localhost:8888
# open notebooks/feast_feature_store.ipynb
make feast-tunnel-stop     # when done
```

The DB password is read from SSM (`/sde-airflow/dev/feast/db-password`) and S3
uses your `~/.aws` credentials, both injected into the notebook container.

### Ray Serve inference + Go gRPC gateway

`terraform/rpc_serving.tf` adds a second inference path: a **Network Load
Balancer** (TCP/gRPC) in front of a **Go gRPC gateway**, which forwards to a
**Ray Serve** deployment that runs the reorder model and fetches features from
the Feast online store.

```
gRPC client -> NLB :50051 -> Go gateway (gRPC) -> Ray Serve (HTTP :8000) -> Feast (Postgres) + LightGBM
```

Both containers run in one Fargate task (the gateway reaches Ray Serve on
`localhost`) — no service discovery needed.

- `containers/ray_serve/` — `serve_app.py` (Ray Serve deployment with `/predict`,
  `/predict_online`, `/health`) + Dockerfile.
- `containers/inference_rpc/` — Go gRPC gateway: `proto/inference.proto`,
  `main.go` (server), `client/main.go` (CLI), multi-stage Dockerfile that
  generates the protobuf stubs.

Build, push, deploy:

```shell
make infra-up                     # creates ECR repos + NLB + service (initial)
make ml-ecr-login
make rpc-push ML_IMAGE_TAG=v1     # builds ray_serve + inference_rpc images
make infra-up                     # rolls the RPC service to the pushed images
```

Call it (the NLB endpoint is an output):

```shell
GRPC=$(terraform -chdir=./terraform output -raw rpc_endpoint)
RAY_RPC_ADDR=$GRPC go run ./containers/inference_rpc/client
# or from inside the task: /inference-cli
```

RPC surface (`inference.proto`):

```proto
service Inference {
  rpc Health(HealthRequest)        returns (HealthResponse);
  rpc Predict(PredictRequest)      returns (PredictResponse);   // raw feature rows
  rpc PredictOnline(OnlineRequest) returns (PredictResponse);   // (user_id, product_id) via Feast
}
```

Note: the NLB is TCP pass-through (no TLS). Add a TLS listener / cert if the
endpoint must be encrypted in transit.

### Tear down infra

After you are done, make sure to destroy your cloud infrastructure.

```shell
make down # Stop docker containers on your computer
make infra-down # type in yes after verifying the changes TF will make
```

