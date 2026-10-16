FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 libgomp1 git openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

# Build context is the repository root (see Makefile).
COPY notebooks/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

EXPOSE 8888
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--ServerApp.token=", "--ServerApp.password="]
