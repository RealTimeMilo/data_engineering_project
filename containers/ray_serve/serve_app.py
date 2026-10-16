"""
Ray Serve deployment for the Instacart reorder model.

Endpoints (HTTP, consumed by the Go gRPC gateway):
    GET  /health          -> liveness + readiness flags
    GET  /metadata        -> model + feature metadata
    POST /predict         -> raw feature instances
    POST /predict_online  -> (user_id, product_id) pairs; features are fetched
                             from the Feast Postgres online store, then scored.

The deployment starts even if the model or Feast online store is temporarily
unavailable (e.g. the pipeline hasn't produced a model yet); endpoints then
return 503 until they are ready. This keeps the ECS task (and the NLB target)
healthy.

Run locally / in ECS with:  python serve_app.py
"""

import json
import os
import sys
import tempfile
import traceback

import boto3
import lightgbm as lgb
import pandas as pd
import ray
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ray import serve

AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
S3_BUCKET = os.environ["ML_S3_BUCKET"]
MODELS_PREFIX = os.getenv("ML_MODELS_PREFIX", "models/instacart")
FEATURE_COLUMNS = os.environ["ML_FEATURE_COLUMNS"].split(",")
FEAST_REPO = os.getenv("FEAST_REPO", "/app/feature_repo")
FEATURE_VIEW = "user_product_reorder_features"
SERVE_PORT = int(os.getenv("SERVE_PORT", "8000"))
SERVE_REPLICAS = int(os.getenv("SERVE_REPLICAS", "1"))
RAY_OBJECT_STORE_BYTES = int(os.getenv("ML_RAY_OBJECT_STORE_BYTES", "300000000"))

sys.path.insert(0, FEAST_REPO)

app = FastAPI(title="instacart-reorder-rayserve")


class PredictRequest(BaseModel):
    instances: list[dict]


class OnlineRequest(BaseModel):
    entities: list[dict]


class PredictResponse(BaseModel):
    probabilities: list[float]
    model: str


def _load_booster() -> lgb.Booster:
    local = os.path.join(tempfile.mkdtemp(), "model.txt")
    key = f"{MODELS_PREFIX}/latest/model.txt"
    boto3.client("s3", region_name=AWS_REGION).download_file(S3_BUCKET, key, local)
    return lgb.Booster(model_file=local)


@serve.deployment(
    num_replicas=SERVE_REPLICAS,
    ray_actor_options={"num_cpus": float(os.getenv("SERVE_CPUS_PER_REPLICA", "1"))},
)
@serve.ingress(app)
class ReorderService:
    def __init__(self) -> None:
        self.feats = FEATURE_COLUMNS
        self.model_uri = f"s3://{S3_BUCKET}/{MODELS_PREFIX}/latest/model.txt"
        self.booster = None
        self.store = None
        self.model_error = None
        self.feast_error = None
        self._debug: dict = {}

        # The model may not exist yet (pipeline hasn't run) - don't crash.
        try:
            self.booster = _load_booster()
            print(f"loaded model {self.model_uri}")
        except Exception as exc:  # noqa: BLE001
            self.model_error = f"{type(exc).__name__}: {exc}"
            self._debug["model_traceback"] = traceback.format_exc()
            print(f"WARNING: model not loaded yet ({self.model_uri}): {exc}")

        try:
            # Ray Serve runs the replica in a separate worker process where the
            # module-level sys.path tweak does not apply, so add it here.
            if FEAST_REPO not in sys.path:
                sys.path.insert(0, FEAST_REPO)
            import feast_config
            import features
            from feast import FeatureStore

            feast_config.write_feature_store_yaml(FEAST_REPO)
            self.store = FeatureStore(repo_path=FEAST_REPO)
            self.store.apply(
                [features.user, features.product, features.user_product_reorder_features]
            )
            print("Feast online store ready")
        except Exception as exc:  # noqa: BLE001
            self.feast_error = f"{type(exc).__name__}: {exc}"
            self._debug["feast_traceback"] = traceback.format_exc()
            print(f"WARNING: Feast online store not ready: {exc}")

        # Ray does not forward replica stdout to CloudWatch, so publish init
        # diagnostics to S3 where they can be inspected.
        self._dump_init_debug()

    def _dump_init_debug(self) -> None:
        try:
            env_keys = [
                "FEAST_DB_HOST", "FEAST_DB_PORT", "FEAST_DB_NAME", "FEAST_DB_USER",
                "FEAST_REPO", "FEAST_OFFLINE_PATH", "FEAST_REGISTRY", "AWS_REGION",
                "ML_S3_BUCKET",
            ]
            payload = {
                "model_ok": self.booster is not None,
                "model_error": self.model_error,
                "feast_ok": self.store is not None,
                "feast_error": self.feast_error,
                "cwd": os.getcwd(),
                "executable": sys.executable,
                "sys_path_head": sys.path[:6],
                "env": {k: os.environ.get(k) for k in env_keys},
                "env_has_password": bool(os.environ.get("FEAST_DB_PASSWORD")),
                **self._debug,
            }
            boto3.client("s3", region_name=AWS_REGION).put_object(
                Bucket=S3_BUCKET,
                Key=f"{MODELS_PREFIX}/debug/ray-serve-init.json",
                Body=json.dumps(payload, indent=2, default=str).encode(),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: could not write init debug: {exc}")

    def _score(self, frame: pd.DataFrame) -> list[float]:
        if self.booster is None:
            raise HTTPException(status_code=503, detail="Model not loaded yet")
        return self.booster.predict(frame[self.feats]).tolist()

    @app.get("/health")
    def health(self) -> dict:
        return {
            "status": "ok",
            "model_loaded": self.booster is not None,
            "feast_ready": self.store is not None,
            "model_error": self.model_error,
            "feast_error": self.feast_error,
            "model": self.model_uri,
        }

    @app.get("/metadata")
    def metadata(self) -> dict:
        return {
            "model": self.model_uri,
            "feature_view": FEATURE_VIEW,
            "n_features": len(self.feats),
            "features": self.feats,
        }

    @app.post("/predict", response_model=PredictResponse)
    def predict(self, request: PredictRequest) -> PredictResponse:
        if not request.instances:
            raise HTTPException(status_code=400, detail="No instances provided")
        frame = pd.DataFrame(request.instances)
        missing = [c for c in self.feats if c not in frame.columns]
        if missing:
            raise HTTPException(status_code=422, detail=f"Missing features: {missing}")
        return PredictResponse(
            probabilities=self._score(frame[self.feats]), model=self.model_uri
        )

    @app.post("/predict_online", response_model=PredictResponse)
    def predict_online(self, request: OnlineRequest) -> PredictResponse:
        if not request.entities:
            raise HTTPException(status_code=400, detail="No entities provided")
        if self.store is None:
            raise HTTPException(
                status_code=503,
                detail=f"Feast online store unavailable: {self.feast_error}",
            )
        refs = [f"{FEATURE_VIEW}:{c}" for c in self.feats]
        rows = self.store.get_online_features(
            features=refs, entity_rows=request.entities
        ).to_dict()
        frame = pd.DataFrame({c: rows.get(c, []) for c in self.feats})
        if frame.empty or frame.isnull().any(axis=None):
            raise HTTPException(
                status_code=404, detail="No online features for those entities"
            )
        return PredictResponse(
            probabilities=self._score(frame[self.feats]), model=self.model_uri
        )


if __name__ == "__main__":
    ray.init(
        ignore_reinit_error=True,
        object_store_memory=RAY_OBJECT_STORE_BYTES,
        logging_level="WARNING",
        include_dashboard=False,
    )
    # Ray 2.x: the HTTP proxy host/port are set via serve.start (serve.run has no
    # host/port args), and serve.run must block or the process would exit.
    serve.start(http_options={"host": "0.0.0.0", "port": SERVE_PORT})
    serve.run(ReorderService.bind(), blocking=True)
