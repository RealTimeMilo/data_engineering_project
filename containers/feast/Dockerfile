FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY containers/feast/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Build context is the repository root (see Makefile).
COPY feast_repo /app/feature_repo

CMD ["python", "feature_repo/apply_materialize.py"]
