FROM apache/airflow:3.2.1
USER root
RUN apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /
USER airflow
RUN pip install --no-cache-dir -r /requirements.txt

ENV AIRFLOW__DAG_PROCESSOR__DAG_BUNDLE_CONFIG_LIST='[{"name": "production-marketing-dags", "classpath": "airflow.providers.git.bundles.git.GitDagBundle", "kwargs": {"git_conn_id": "my_git_connection", "tracking_ref": "main", "subdir": "dags", "refresh_interval": 300}}]'