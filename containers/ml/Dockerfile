FROM python:3.11-slim

# libgomp is required by LightGBM
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# MLflow inspects the git repo for source tags; there is no git in the image.
ENV GIT_PYTHON_REFRESH=quiet

COPY config.py utils.py mlflow_utils.py analytics.py bootstrap_analytics.py check_connections.py ingest.py preprocess.py train.py evaluate.py deploy.py ./

# Each ECS task overrides the command (e.g. ["python", "preprocess.py"]).
CMD ["python", "-c", "print('Override the command with python <script>.py')"]
