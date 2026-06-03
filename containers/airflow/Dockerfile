FROM apache/airflow:3.2.1
USER airflow
COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

RUN apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV AIRFLOW__DAG_PROCESSOR__DAG_BUNDLE_CONFIG_LIST='[{"name": "my_git_repo", "classpath": "airflow.providers.git.bundles.git.GitDagBundle", "kwargs": {"git_conn_id": "my_git_connection", "subdir": "dags", "tracking_ref": "main"}}]'
