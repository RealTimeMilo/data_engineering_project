"""
FastAPI inference service for the Instacart reorder model.

Endpoints:
  GET  /health          -> liveness/readiness for the ALB
  GET  /metadata        -> model + feature metadata
  POST /predict         -> raw feature instances
  POST /predict_online  -> (user_id, product_id) pairs; features are fetched
                           from the Feast Postgres online store, then scored.
"""

import os
import tempfile
from contextlib import asynccontextmanager

import boto3
import lightgbm as lgb
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
S3_BUCKET = os.environ["ML_S3_BUCKET"]
MODELS_PREFIX = os.getenv("ML_MODELS_PREFIX", "models/instacart")
FEATURE_COLUMNS = os.environ["ML_FEATURE_COLUMNS"].split(",")

FEAST_REPO = os.getenv("FEAST_REPO", "/app/feature_repo")
FEATURE_VIEW = "user_product_reorder_features"

if FEAST_REPO not in os.sys.path:
    os.sys.path.insert(0, FEAST_REPO)

_state: dict = {"model": None, "loaded_from": None, "feast": None}


# --- model -----------------------------------------------------------------
def _download_model() -> str:
    key = f"{MODELS_PREFIX}/latest/model.txt"
    local = os.path.join(tempfile.mkdtemp(), "model.txt")
    boto3.client("s3", region_name=AWS_REGION).download_file(S3_BUCKET, key, local)
    return local


def _load_model() -> None:
    path = _download_model()
    _state["model"] = lgb.Booster(model_file=path)
    _state["loaded_from"] = f"s3://{S3_BUCKET}/{MODELS_PREFIX}/latest/model.txt"
    print(f"Loaded model from {_state['loaded_from']}")


# --- feast online store ----------------------------------------------------
def _init_feast() -> None:
    try:
        import feast_config  # noqa: WPS433 (runtime import)
        import features  # noqa: WPS433
        from feast import FeatureStore  # noqa: WPS433

        feast_config.write_feature_store_yaml(FEAST_REPO)
        store = FeatureStore(repo_path=FEAST_REPO)
        store.apply(
            [features.user, features.product, features.user_product_reorder_features]
        )
        _state["feast"] = store
        print("Feast online store ready")
    except Exception as exc:  # noqa: BLE001
        # Serving can still answer /predict with raw features.
        print(f"WARNING: Feast init failed: {exc}")
        _state["feast"] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_model()
    _init_feast()
    yield


app = FastAPI(title="instacart-reorder-inference", lifespan=lifespan)


class PredictRequest(BaseModel):
    instances: list[dict]


class PredictResponse(BaseModel):
    probabilities: list[float]
    model: str


class OnlineRequest(BaseModel):
    entities: list[dict]  # [{"user_id": 1, "product_id": 2}, ...]


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model_loaded": _state["model"] is not None,
        "feast_ready": _state["feast"] is not None,
    }


@app.get("/metadata")
def metadata() -> dict:
    return {
        "model": _state["loaded_from"],
        "n_features": len(FEATURE_COLUMNS),
        "features": FEATURE_COLUMNS,
        "feature_view": FEATURE_VIEW,
    }


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    if _state["model"] is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if not request.instances:
        raise HTTPException(status_code=400, detail="No instances provided")

    frame = pd.DataFrame(request.instances)
    missing = [c for c in FEATURE_COLUMNS if c not in frame.columns]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing feature columns: {missing}")

    proba = _state["model"].predict(frame[FEATURE_COLUMNS]).tolist()
    return PredictResponse(probabilities=proba, model=_state["loaded_from"])


@app.post("/predict_online", response_model=PredictResponse)
def predict_online(request: OnlineRequest) -> PredictResponse:
    if _state["model"] is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    if _state["feast"] is None:
        raise HTTPException(status_code=503, detail="Feast online store unavailable")
    if not request.entities:
        raise HTTPException(status_code=400, detail="No entities provided")

    feature_refs = [f"{FEATURE_VIEW}:{c}" for c in FEATURE_COLUMNS]
    rows = _state["feast"].get_online_features(
        features=feature_refs, entity_rows=request.entities
    ).to_dict()

    frame = pd.DataFrame({col: rows.get(col, []) for col in FEATURE_COLUMNS})
    if frame.empty or frame.isnull().any(axis=None):
        raise HTTPException(status_code=404, detail="No online features for those entities")

    proba = _state["model"].predict(frame[FEATURE_COLUMNS]).tolist()
    return PredictResponse(probabilities=proba, model=_state["loaded_from"])
