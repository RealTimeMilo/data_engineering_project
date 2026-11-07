# MLflow (Databricks) → ECS ML pipeline

The Instacart pipeline logs to a Databricks-hosted MLflow tracking server. The
integration is optional at runtime: if `MLFLOW_TRACKING_URI` is empty (or the
server is unreachable and `MLFLOW_REQUIRED=false`), the ECS task logs a warning
and continues — S3 artifacts are still written.

## What gets logged

One **parent run** per Airflow run (named after the Airflow `dag_run.run_id`),
with one **child run per stage**, linked via the reserved `mlflow.parentRunId`
tag so the MLflow UI renders them as nested:

| Stage | Params | Metrics | Artifacts |
|---|---|---|---|
| `ingest` | sample fraction, seed, prefixes | user/order/interaction counts | — |
| `preprocess` | max rows, feature list | candidate/split sizes, positive rate | — |
| `train` | full LightGBM param set, row counts | best iteration, `valid.auc`, `valid.average_precision`, gain importances | `model/`, `booster/model.txt`, `metrics.json` |
| `evaluate` | — | ROC-AUC, PR-AUC, accuracy, log loss, mean prediction | `eval_metrics.json` |
| `deploy` | — | copied objects, redeployed flag | — |

Runs are grouped by the `ml_run_id` tag (= the sanitized Airflow run id).

## Configuration

Terraform (`terraform/analytics.tf`, `terraform/ml_pipeline.tf`):

| Variable / resource | Value |
|---|---|
| `mlflow_tracking_uri` | `https://dbc-be947809-b49e.cloud.databricks.com` |
| `mlflow_experiment_name` | `/Shared/instacart-reorder` |
| SSM `/sde-airflow/dev/mlflow/tracking-token` | Databricks PAT (`SecureString`) |

The PAT is **not stored in git or Terraform state**. The SSM parameter is created
with a placeholder (`unset`) and `ignore_changes`, then set out-of-band:

```bash
aws ssm put-parameter \
  --region us-east-2 \
  --name /sde-airflow/dev/mlflow/tracking-token \
  --type SecureString \
  --value "$DATABRICKS_TOKEN" \
  --overwrite
```

It is injected into every ML ECS task as the `MLFLOW_TRACKING_TOKEN` secret. The
task definition also carries:

```
MLFLOW_TRACKING_URI=https://dbc-be947809-b49e.cloud.databricks.com
MLFLOW_EXPERIMENT_NAME=/Shared/instacart-reorder
ML_DAG_ID=instacart_ml_pipeline
```

The DAG additionally sets `MLFLOW_RUN_NAME={{ dag_run.run_id }}` on every task and
lets you override the experiment with the `MLFLOW_EXPERIMENT_NAME` Airflow
Variable (no redeploy needed).

## Verifying

```bash
# 1. Experiment exists (API)
curl -s -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  "https://dbc-be947809-b49e.cloud.databricks.com/api/2.0/mlflow/experiments/search?max_results=20" \
  | jq -r '.experiments[] | "\(.experiment_id)  \(.name)"'

# 2. Run a stage task and read its logs
aws logs tail /sde-airflow/dev/ecs-airflow/ml/train --follow --region us-east-2
# look for: "MLflow tracking URI=... experiment=..." and "MLflow pipeline run ..."

# 3. Open the experiment
#    https://dbc-be947809-b49e.cloud.databricks.com/#/experiments/1957572061168153
```

## Rotating the token

Create a new PAT in Databricks (**Settings → Developer → Access tokens**), then
re-run the `put-parameter --overwrite` command above. Running tasks pick it up on
their next start; no image rebuild or Terraform apply is needed.

## Failure behaviour

| Situation | Result |
|---|---|
| `MLFLOW_TRACKING_URI` empty | all calls are no-ops |
| Server unreachable, `MLFLOW_REQUIRED=false` (default) | warning in CloudWatch, pipeline continues |
| Server unreachable, `MLFLOW_REQUIRED=true` | stage fails (useful for CI) |
| Artifact upload blocked (e.g. workspace policy) | warning; metrics/params still logged |
