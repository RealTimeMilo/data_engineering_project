"""
Promote a trained model to `latest` and roll the inference ECS service.

Steps:
  1. Copy s3://<bucket>/<models_prefix>/<run_id>/* -> .../latest/
  2. Force a new deployment of the inference ECS service so it reloads the
     model on startup.
  3. Close out the MLflow pipeline run and the analytics `pipeline_runs` row.
"""

import boto3

import analytics
from config import (
    AWS_REGION,
    ECS_CLUSTER,
    ECS_SERVICE,
    MODELS_PREFIX,
    RUN_ID,
    S3_BUCKET,
)
from mlflow_utils import finish_pipeline, run_url, stage as mlflow_stage
from utils import configure_logging, copy_prefix

logger = configure_logging("deploy")


def main() -> None:
    copied = copy_prefix(
        S3_BUCKET,
        f"{MODELS_PREFIX}/{RUN_ID}",
        f"{MODELS_PREFIX}/latest",
    )
    if copied == 0:
        raise RuntimeError(
            f"No model artifacts found at {MODELS_PREFIX}/{RUN_ID} - did training run?"
        )

    redeployed = False
    if not ECS_CLUSTER or not ECS_SERVICE:
        logger.warning(
            "ML_ECS_CLUSTER / ML_ECS_SERVICE not set; skipped ECS redeploy."
        )
    else:
        ecs = boto3.client("ecs", region_name=AWS_REGION)
        ecs.update_service(
            cluster=ECS_CLUSTER,
            service=ECS_SERVICE,
            forceNewDeployment=True,
        )
        redeployed = True
        logger.info(
            "Forced new deployment of %s on cluster %s", ECS_SERVICE, ECS_CLUSTER
        )

    with mlflow_stage("deploy", tags={"model_run": RUN_ID}) as ml:
        ml.set_tags(
            {"deployed": str(redeployed).lower(), "ecs_service": ECS_SERVICE or ""}
        )
        ml.log_metrics({"copied_objects": copied, "redeployed": int(redeployed)})

    analytics.finish_run(
        RUN_ID,
        status="succeeded",
        extra_metrics={"copied_objects": float(copied)},
    )
    finish_pipeline("FINISHED")

    url = run_url()
    if url:
        logger.info("MLflow run: %s", url)


if __name__ == "__main__":
    main()
