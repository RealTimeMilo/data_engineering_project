FROM python:3.11-slim

# libgomp is required by LightGBM
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py utils.py ingest.py preprocess.py train.py evaluate.py deploy.py ./

# Each ECS task overrides the command (e.g. ["python", "preprocess.py"]).
CMD ["python", "-c", "print('Override the command with python <script>.py')"]
