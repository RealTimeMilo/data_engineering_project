#!/usr/bin/env bash
#
# Run the Instacart reorder pipeline end-to-end as one-off ECS Fargate tasks:
#   ingest -> preprocess -> train -> evaluate -> deploy
#
# Usage:
#   scripts/run_ml_pipeline.sh [run_id]
#
# Env overrides:
#   AWS_REGION, ML_CLUSTER, ML_SAMPLE_FRACTION, ML_CONTAINER_NAME
set -uo pipefail

REGION=${AWS_REGION:-us-east-2}
CLUSTER=${ML_CLUSTER:-sde-airflow-dev-ml}
CONTAINER=${ML_CONTAINER_NAME:-ml-task}
SAMPLE=${ML_SAMPLE_FRACTION:-0.1}
RUN_ID=${1:-run-$(date +%Y%m%d-%H%M%S)}
TF="terraform -chdir=$(dirname "$0")/../terraform"

SUBNETS=${ML_SUBNETS:-$($TF output -json ml_subnets | python3 -c 'import sys,json;print(",".join(json.load(sys.stdin)))')}
SG=${ML_SG:-$($TF output -raw ml_security_group_id)}
NET="awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG],assignPublicIp=ENABLED}"

echo "Run id: $RUN_ID"
echo "Cluster: $CLUSTER  Subnets: $SUBNETS  SG: $SG"

run_step() {
  local step=$1
  # The Feast task definition uses a different container name.
  local container="$CONTAINER"
  [ "$step" = "feast" ] && container="feast"
  local overrides
  overrides=$(python3 - "$container" "$RUN_ID" "$SAMPLE" <<'PY'
import json, sys
name, run_id, sample = sys.argv[1:4]
print(json.dumps({"containerOverrides": [{
    "name": name,
    "environment": [
        {"name": "ML_RUN_ID", "value": run_id},
        {"name": "ML_SAMPLE_FRACTION", "value": sample},
    ],
}]}))
PY
)
  echo "=== [$step] launching sde-airflow-dev-ml-$step ==="
  local task
  task=$(aws ecs run-task --region "$REGION" --cluster "$CLUSTER" \
    --task-definition "sde-airflow-dev-ml-$step" --launch-type FARGATE \
    --network-configuration "$NET" --overrides "$overrides" \
    --query 'tasks[0].taskArn' --output text)
  if [ -z "$task" ] || [ "$task" = "None" ]; then
    echo "  failed to launch"
    return 1
  fi
  local tid=${task##*/}
  echo "  task=$tid"

  local status
  while true; do
    status=$(aws ecs describe-tasks --region "$REGION" --cluster "$CLUSTER" --tasks "$task" \
      --query 'tasks[0].lastStatus' --output text 2>/dev/null)
    [ "$status" = "STOPPED" ] && break
    sleep 15
  done

  local exit_code
  exit_code=$(aws ecs describe-tasks --region "$REGION" --cluster "$CLUSTER" --tasks "$task" \
    --query 'tasks[0].containers[0].exitCode' --output text 2>/dev/null)
  if [ "$exit_code" != "0" ]; then
    echo "  !! [$step] failed with exit=$exit_code. Last logs:"
    aws logs get-log-events --region "$REGION" \
      --log-group-name "/sde-airflow/dev/ecs-airflow/ml/$step" \
      --log-stream-name "ecs/$step/$container/$tid" --limit 60 \
      --query 'events[].message' --output text 2>&1 | tail -40
    return 1
  fi
  echo "  [$step] OK"
}

START=${ML_START:-ingest}
started=0
for step in ingest preprocess feast train evaluate deploy; do
  if [ "$step" = "$START" ]; then started=1; fi
  [ "$started" = 1 ] || continue
  if ! run_step "$step"; then
    echo "PIPELINE FAILED at step: $step"
    exit 1
  fi
done

BUCKET=$($TF output -raw ml_s3_bucket)
echo "PIPELINE COMPLETE. Model at s3://$BUCKET/models/instacart/$RUN_ID and .../latest/"
