"""
Connectivity self-test for the two external integrations.

Run as a one-off ECS task using any ML task definition (it needs the MLflow
token secret and the analytics writer credentials):

    aws ecs run-task ... --overrides '{"containerOverrides":[{
      "name":"ml-task","command":["python","check_connections.py"],
      "environment":[{"name":"ML_RUN_ID","value":"connectivity-check"}]}]}'

Exits non-zero if either integration is configured but unusable.
"""

from __future__ import annotations

import sys

import analytics
import mlflow_utils
from config import RUN_ID
from mlflow_utils import finish_pipeline, stage as mlflow_stage


def main() -> int:
    ok = True

    print(f"MLflow enabled={mlflow_utils.enabled()} uri={mlflow_utils.TRACKING_URI}")
    if mlflow_utils.enabled():
        with mlflow_stage(
            "connectivity",
            params={"source": "check_connections.py", "run_id": RUN_ID},
        ) as ml:
            ml.log_metrics({"connectivity.mlflow_ok": 1})
            if not ml.active:
                print("MLflow stage did not open a run (see warnings above)")
                ok = False
            else:
                print("MLflow: run created and metric logged")
        finish_pipeline("FINISHED")
    else:
        print("MLflow disabled: MLFLOW_TRACKING_URI is empty")
        ok = False

    print(f"Analytics enabled={analytics.enabled()} host={analytics.HOST or '(unset)'}")
    if analytics.enabled():
        try:
            with analytics.connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT current_user, current_database(), version()")
                user, database, version = cur.fetchone()
                print(f"Analytics: connected as {user} to {database} ({version[:40]}...)")
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = %s ORDER BY table_name",
                    (analytics.SCHEMA,),
                )
                tables = [row[0] for row in cur.fetchall()]
                print(f"Analytics: {analytics.SCHEMA} tables={tables}")
            analytics.record_metrics(
                RUN_ID, "connectivity", {"connectivity.analytics_ok": 1}
            )
            print("Analytics: metric upserted")
        except Exception as exc:  # noqa: BLE001
            print(f"Analytics: FAILED - {exc}")
            ok = False
    else:
        print("Analytics disabled: ANALYTICS_DB_HOST is empty")
        ok = False

    print("ALL CHECKS PASSED" if ok else "CHECKS INCOMPLETE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
