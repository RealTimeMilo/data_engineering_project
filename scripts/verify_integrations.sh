#!/usr/bin/env bash
#
# Verify the two external integrations from inside the VPC:
#   1. create the analytics schema/roles (bootstrap task)
#   2. open an MLflow run + write an analytics row (connectivity task)
#
# Both run as one-off Fargate tasks using the current task definitions.
#
# Usage: scripts/verify_integrations.sh [bootstrap|check|all]
set -uo pipefail

TF="terraform -chdir=$(dirname "$0")/../terraform"
REGION=${AWS_REGION:-us-east-2}

CLUSTER=$($TF output -raw ml_ecs_cluster_name)
SUBNETS=$($TF output -json ml_subnets | python3 -c 'import sys,json;print(",".join(json.load(sys.stdin)))')
SG=$($TF output -raw ml_security_group_id)

run_task() {
  local family=$1
  shift
  local overrides=${1:-}
  local args=(
    ecs run-task
    --region "$REGION"
    --cluster "$CLUSTER"
    --task-definition "$family"
    --launch-type FARGATE
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG],assignPublicIp=ENABLED}"
    --query 'tasks[0].taskArn' --output text
  )
  if [ -n "$overrides" ]; then
    args+=(--overrides "$overrides")
  fi
  aws "${args[@]}"
}

wait_and_report() {
  local arn=$1 label=$2
  if [ -z "$arn" ] || [ "$arn" = "None" ]; then
    echo "$label failed to start (no task ARN)"
    return 1
  fi
  echo "waiting for $label task: $arn"
  aws ecs wait tasks-stopped --region "$REGION" --cluster "$CLUSTER" --tasks "$arn"
  local exit_code
  exit_code=$(aws ecs describe-tasks --region "$REGION" --cluster "$CLUSTER" --tasks "$arn" \
    --query 'tasks[0].containers[0].exitCode' --output text)
  if [ -z "$exit_code" ] || [ "$exit_code" = "None" ]; then
    exit_code=1
  fi
  echo "$label exit code: $exit_code"
  echo "--- last log lines ---"
  aws logs tail "$(aws ecs describe-tasks --region "$REGION" --cluster "$CLUSTER" --tasks "$arn" \
    --query 'tasks[0].containers[0].logConfiguration.options.["awslogs-group"]' --output text)" \
    --region "$REGION" --since 15m 2>/dev/null | tail -25
  return "$exit_code"
}

mode=${1:-all}
rc=0

if [ "$mode" = "bootstrap" ] || [ "$mode" = "all" ]; then
  FAMILY=$($TF output -raw analytics_bootstrap_task_definition_family)
  ARN=$(run_task "$FAMILY")
  wait_and_report "$ARN" "analytics-bootstrap" || rc=$?
fi

if [ "$mode" = "check" ] || [ "$mode" = "all" ]; then
  FAMILY=$($TF output -json ml_task_definition_families | python3 -c 'import sys,json;print(json.load(sys.stdin)["evaluate"])')
  OVERRIDES='{"containerOverrides":[{"name":"ml-task","command":["python","check_connections.py"],"environment":[{"name":"ML_RUN_ID","value":"connectivity-check"}]}]}'
  ARN=$(run_task "$FAMILY" "$OVERRIDES")
  wait_and_report "$ARN" "connectivity-check" || rc=$?
fi

exit "$rc"
