"""
Promote a trained model to `latest` and roll the inference ECS service.

Steps:
  1. Copy s3://<bucket>/<models_prefix>/<run_id>/* -> .../latest/
  2. Force a new deployment of the inference ECS service so it reloads the
     model on startup.
"""

import boto3

from config import (
    AWS_REGION,
    ECS_CLUSTER,
    ECS_SERVICE,
    MODELS_PREFIX,
    RUN_ID,
    S3_BUCKET,
)
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

    if not ECS_CLUSTER or not ECS_SERVICE:
        logger.warning(
            "ML_ECS_CLUSTER / ML_ECS_SERVICE not set; skipped ECS redeploy."
        )
        return

    ecs = boto3.client("ecs", region_name=AWS_REGION)
    ecs.update_service(
        cluster=ECS_CLUSTER,
        service=ECS_SERVICE,
        forceNewDeployment=True,
    )
    logger.info(
        "Forced new deployment of %s on cluster %s", ECS_SERVICE, ECS_CLUSTER
    )


if __name__ == "__main__":
    main()
