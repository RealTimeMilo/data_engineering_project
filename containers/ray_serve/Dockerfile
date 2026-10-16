FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build context is the repository root (see Makefile).
COPY containers/ray_serve/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY containers/ray_serve/serve_app.py /app/serve_app.py
COPY feast_repo /app/feature_repo

EXPOSE 8000
CMD ["python", "serve_app.py"]
