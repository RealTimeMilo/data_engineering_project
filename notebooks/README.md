# Feature-store notebook

`feast_feature_store.ipynb` inspects the Instacart Feast feature store from both
sides and adds a searchable feature index plus EDA.

- **Online store** - Feast RDS Postgres (`sde-airflow-dev-feast-pg`): low-latency
  serving rows (`instacart_user_product_reorder_features`).
- **Offline store** - S3 parquet history
  (`s3://<ml-bucket>/features/instacart/offline/features.parquet`).
- **Feature Marketplace** - the Feast registry indexed into a searchable table
  (entities, feature views, features, data sources, feature services).
- **EDA** - distributions, target balance, correlations and reorder-rate trends.

## How JupyterLab runs

There is no long-running Jupyter server in the cloud. JupyterLab runs **locally
in a Docker container**, and reaches the private RDS through an **SSH tunnel via
the EC2 instance**:

```
JupyterLab container  --(host.docker.internal:15432)-->  ssh tunnel (EC2)
        |                                                      |
        |  S3 / SSM (your ~/.aws creds)                        v
        +-------------------------------------------->  Feast RDS :5432
```

Everything is wired by one Make target:

```bash
make feast-notebook
```

which does three things:

1. **`scripts/feast_tunnel.sh start`** - opens `localhost:15432 -> <feast-rds>:5432`
   over SSH to the EC2 instance (the RDS is private; the EC2 security group is
   allowed on the RDS). Idempotent: reused if already up.
2. **Builds `notebooks/Dockerfile`** into the image `feast-notebook:local`
   (Python 3.11 + `feast[postgres]` + dask/s3fs + pandas + matplotlib/seaborn +
   JupyterLab).
3. **Runs JupyterLab** on port `8888`, mounting the repo at `/work` and your
   `~/.aws` at `/root/.aws`, then open <http://localhost:8888> and the notebook.

Stop the tunnel when finished:

```bash
make feast-tunnel-stop
```

### Container environment

The `make feast-notebook` target injects:

| Variable | Value | Purpose |
|----------|-------|---------|
| `ML_S3_BUCKET` | `terraform output -raw ml_s3_bucket` | offline parquet + SSM |
| `FEAST_DB_HOST` | `host.docker.internal` | reach the host's SSH tunnel |
| `FEAST_DB_PORT` | `15432` | tunnel local port |
| `FEAST_DB_SSLMODE` | `prefer` | tunnel is plaintext |
| `AWS_DEFAULT_REGION` | `us-east-2` | |
| `~/.aws` | mounted read-only | S3 + SSM credentials |

The notebook resolves the DB password itself from SSM
(`/sde-airflow/dev/feast/db-password`, SecureString). It also downloads the
offline parquet to `/tmp/feast_offline/` because Feast's Dask file store resolves
source paths relative to the repo (so it can't read `s3://` directly).

## Running without the container

Prefer a Python **3.11/3.12** virtualenv (not 3.14 - `feast[postgres]` wheels are
unreliable there):

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r notebooks/requirements.txt
python -m ipykernel install --user --name feast --display-name "Feast"
scripts/feast_tunnel.sh start        # keep the tunnel up
```

Then run the notebook and select the `Feast` kernel. The config cell defaults
`FEAST_DB_HOST=localhost`; the container target overrides it to
`host.docker.internal`.

## Troubleshooting

- **`tunnel failed to start`** - a tunnel is already bound to `15432`, or the port
  is held by something else. The script is idempotent (prints "tunnel already
  up"); if you need a clean start, run `make feast-tunnel-stop` first.
- **`Connection refused` on `15432`** - the tunnel is down: `make feast-tunnel`.
- **`platform ... does not match`** - harmless warning; the image is amd64 for
  Fargate parity and runs under emulation on Apple Silicon.
- **`FeastModuleImportError: ... postgres ...`** - `feast` installed without the
  Postgres extra. Use the container, or `pip install "feast[postgres]" psycopg2-binary`.
- **`FileNotFoundError: /app/feature_repo/s3:/...`** - the offline path wasn't
  localized; the notebook's config cell downloads it to `/tmp/feast_offline/`.
