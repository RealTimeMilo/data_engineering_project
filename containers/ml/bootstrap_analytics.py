"""
Bootstrap the analytics Postgres used by Mode Analytics.

Idempotent: creates the ``ml_analytics`` schema and tables plus three roles
(``ml_writer`` for the pipeline, ``mode_readonly`` for Mode, and the RDS master
``analytics_admin`` which only this script uses). Run it once as an ECS task
after Terraform creates the instance:

    python bootstrap_analytics.py

Environment (injected by terraform/analytics.tf):
    ANALYTICS_DB_HOST / PORT / NAME / SSLMODE
    ANALYTICS_DB_ADMIN_USER / ANALYTICS_DB_ADMIN_PASSWORD
    ANALYTICS_DB_WRITER_USER / ANALYTICS_DB_WRITER_PASSWORD
    ANALYTICS_MODE_USER / ANALYTICS_MODE_PASSWORD
"""

from __future__ import annotations

import os

import psycopg2
from psycopg2 import sql

HOST = os.environ["ANALYTICS_DB_HOST"]
PORT = int(os.getenv("ANALYTICS_DB_PORT", "5432"))
NAME = os.getenv("ANALYTICS_DB_NAME", "analytics")
SSLMODE = os.getenv("ANALYTICS_DB_SSLMODE", "require")

ADMIN_USER = os.getenv("ANALYTICS_DB_ADMIN_USER", "analytics_admin")
ADMIN_PASSWORD = os.environ["ANALYTICS_DB_ADMIN_PASSWORD"]
WRITER_USER = os.getenv("ANALYTICS_DB_WRITER_USER", "ml_writer")
WRITER_PASSWORD = os.environ["ANALYTICS_DB_WRITER_PASSWORD"]
MODE_USER = os.getenv("ANALYTICS_MODE_USER", "mode_readonly")
MODE_PASSWORD = os.environ["ANALYTICS_MODE_PASSWORD"]

SCHEMA = "ml_analytics"

DDL = [
    f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}",
    f"""
    CREATE TABLE IF NOT EXISTS {SCHEMA}.pipeline_runs (
        run_id        text PRIMARY KEY,
        dag_id        text,
        status        text NOT NULL DEFAULT 'running',
        params        jsonb NOT NULL DEFAULT '{{}}'::jsonb,
        mlflow_run_id text,
        started_at    timestamptz NOT NULL DEFAULT now(),
        finished_at   timestamptz
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {SCHEMA}.model_metrics (
        id           bigserial PRIMARY KEY,
        run_id       text NOT NULL
                     REFERENCES {SCHEMA}.pipeline_runs(run_id) ON DELETE CASCADE,
        stage        text NOT NULL,
        metric       text NOT NULL,
        value        double precision NOT NULL,
        recorded_at  timestamptz NOT NULL DEFAULT now(),
        UNIQUE (run_id, stage, metric)
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {SCHEMA}.model_predictions (
        id                  bigserial PRIMARY KEY,
        run_id              text NOT NULL
                            REFERENCES {SCHEMA}.pipeline_runs(run_id) ON DELETE CASCADE,
        user_id             bigint NOT NULL,
        product_id          bigint NOT NULL,
        label               smallint,
        reorder_probability double precision NOT NULL,
        scored_at           timestamptz NOT NULL DEFAULT now(),
        UNIQUE (run_id, user_id, product_id)
    )
    """,
    f"CREATE INDEX IF NOT EXISTS model_metrics_run_idx "
    f"ON {SCHEMA}.model_metrics (run_id, stage)",
    f"CREATE INDEX IF NOT EXISTS model_predictions_user_idx "
    f"ON {SCHEMA}.model_predictions (user_id)",
    f"CREATE INDEX IF NOT EXISTS model_predictions_product_idx "
    f"ON {SCHEMA}.model_predictions (product_id)",
]


def _ensure_role(cur, role: str, password: str) -> None:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
    if cur.fetchone():
        cur.execute(
            sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
        print(f"role {role}: updated password")
    else:
        cur.execute(
            sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
        print(f"role {role}: created")


def _grants(cur) -> None:
    statements = [
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}").format(
            sql.Identifier(NAME),
            sql.Identifier(WRITER_USER),
            sql.Identifier(MODE_USER),
        ),
        sql.SQL("GRANT USAGE ON SCHEMA {} TO {}, {}").format(
            sql.Identifier(SCHEMA),
            sql.Identifier(WRITER_USER),
            sql.Identifier(MODE_USER),
        ),
        sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(
            sql.Identifier(SCHEMA), sql.Identifier(MODE_USER)
        ),
        sql.SQL(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}"
        ).format(sql.Identifier(SCHEMA), sql.Identifier(WRITER_USER)),
        sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
            sql.Identifier(SCHEMA), sql.Identifier(WRITER_USER)
        ),
        # Tables created later (by migrations) inherit the same grants.
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} "
            "GRANT SELECT ON TABLES TO {}"
        ).format(
            sql.Identifier(ADMIN_USER),
            sql.Identifier(SCHEMA),
            sql.Identifier(MODE_USER),
        ),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
        ).format(
            sql.Identifier(ADMIN_USER),
            sql.Identifier(SCHEMA),
            sql.Identifier(WRITER_USER),
        ),
        sql.SQL(
            "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} "
            "GRANT USAGE, SELECT ON SEQUENCES TO {}"
        ).format(
            sql.Identifier(ADMIN_USER),
            sql.Identifier(SCHEMA),
            sql.Identifier(WRITER_USER),
        ),
        # Defense in depth: Mode can never write, even by accident.
        sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(
            sql.Identifier(MODE_USER)
        ),
        sql.SQL("ALTER ROLE {} SET statement_timeout = '120s'").format(
            sql.Identifier(MODE_USER)
        ),
    ]
    for statement in statements:
        cur.execute(statement)


def main() -> None:
    print(f"Connecting to {NAME} at {HOST}:{PORT} as {ADMIN_USER} (sslmode={SSLMODE})")
    with psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname=NAME,
        user=ADMIN_USER,
        password=ADMIN_PASSWORD,
        sslmode=SSLMODE,
        connect_timeout=15,
    ) as conn, conn.cursor() as cur:
        for statement in DDL:
            cur.execute(statement)
        print(f"schema {SCHEMA}: tables ensured")

        _ensure_role(cur, WRITER_USER, WRITER_PASSWORD)
        _ensure_role(cur, MODE_USER, MODE_PASSWORD)
        _grants(cur)
        print("grants applied")

        cur.execute(
            f"""
            SELECT table_name
              FROM information_schema.tables
             WHERE table_schema = %s
             ORDER BY table_name
            """,
            (SCHEMA,),
        )
        tables = [row[0] for row in cur.fetchall()]

        cur.execute(f"SELECT count(*) FROM {SCHEMA}.pipeline_runs")
        runs = cur.fetchone()[0]
        cur.execute(f"SELECT count(*) FROM {SCHEMA}.model_predictions")
        predictions = cur.fetchone()[0]

    print(f"tables: {', '.join(tables)}")
    print(f"rows: pipeline_runs={runs} model_predictions={predictions}")
    print("Analytics bootstrap complete.")


if __name__ == "__main__":
    main()
