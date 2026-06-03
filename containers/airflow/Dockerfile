FROM apache/airflow:3.2.1
USER root
RUN apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /
USER airflow
RUN pip install --no-cache-dir -r /requirements.txt

ENV DAG_BUNDLE_CONFIG_LIST='[{"name": "git_dags", "classpath": "airflow.providers.git.bundles.git.GitDagBundle", "kwargs": {"git_conn_id": "my_git_connection", "tracking_ref": "main", "subdir": "dags", "refresh_interval": 300}}]'