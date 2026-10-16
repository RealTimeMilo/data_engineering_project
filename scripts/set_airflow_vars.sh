#!/usr/bin/env bash
#
# Upsert the Airflow Variables the `instacart_ml_pipeline` DAG needs, taking the
# values from the current Terraform outputs. Without these the DAG launches ECS
# tasks with an empty subnet list and every step fails with
# "InvalidParameterException: subnets can not be empty".
#
# Usage:
#   scripts/set_airflow_vars.sh
#
# Env overrides:
#   ECS_AIRFLOW_URL       (default: terraform output ecs_airflow_url)
#   ECS_AIRFLOW_USER      (default: airflow)
#   ECS_AIRFLOW_PASSWORD  (default: airflow)
set -uo pipefail

TF="terraform -chdir=$(dirname "$0")/../terraform"
URL=${ECS_AIRFLOW_URL:-$($TF output -raw ecs_airflow_url)}
USER=${ECS_AIRFLOW_USER:-airflow}
PASSWORD=${ECS_AIRFLOW_PASSWORD:-airflow}

SUBNETS=${ML_SUBNETS:-$($TF output -json ml_subnets | python3 -c 'import sys,json;print(",".join(json.load(sys.stdin)))')}
SG=${ML_SG:-$($TF output -raw ml_security_group_id)}
CLUSTER=${ML_CLUSTER:-$($TF output -raw ml_ecs_cluster_name)}

TOK=$(curl -fsS -X POST "$URL/auth/token" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$USER\",\"password\":\"$PASSWORD\"}" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])' 2>/dev/null)
if [ -z "$TOK" ]; then
  echo "could not authenticate to $URL (is the API server up and the admin user created?)" >&2
  exit 1
fi

# Create the variable, falling back to PATCH when it already exists (409).
upsert() {
  local key=$1 value=$2 body patch_body code
  body=$(python3 -c 'import json,sys;print(json.dumps({"key":sys.argv[1],"value":sys.argv[2],"description":"set by scripts/set_airflow_vars.sh"}))' "$key" "$value")
  patch_body=$(python3 -c 'import json,sys;print(json.dumps({"key":sys.argv[1],"value":sys.argv[2]}))' "$key" "$value")
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$URL/api/v2/variables" \
    -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d "$body")
  if [ "$code" != "201" ] && [ "$code" != "200" ]; then
    code=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$URL/api/v2/variables/$key" \
      -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d "$patch_body")
  fi
  echo "  $key -> HTTP $code"
}

echo "Setting ML variables on $URL"
upsert ML_SUBNET_IDS "$SUBNETS"
upsert ML_SECURITY_GROUP "$SG"
upsert ML_ECS_CLUSTER "$CLUSTER"
echo "Done."
