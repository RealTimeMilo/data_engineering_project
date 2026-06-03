FROM apache/airflow:3.2.1
USER airflow
COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

COPY quarto.sh /
RUN cd / && bash /quarto.sh
RUN bash /tmp/quarto.sh \
    && rm -f ~/quarto-*.tar.gz /tmp/quarto.sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV AIRFLOW__DAG_PROCESSOR__DAG_BUNDLE_CONFIG_LIST='[    {
      "name": "my_git_repo",
      "classpath": "airflow.providers.git.bundles.git.GitDagBundle",
      "kwargs": {
        "tracking_ref": "main",
        "repo_url": "https://github.com/RealTimeMilo/data_engineering_project.git",
        "repo_path": "data_engineering_project/dags",
        "git_username": "RealTimeMilo",
        "git_password": "ghp_xWd1234567890xWd1234567890xWd1234567890xWd1234567890",
        "git_branch": "main",
        "git_conn_id": "my_git_conn_id"}
    },
    {
      "name": "dags-folder",
      "classpath": "airflow.dag_processing.bundles.local.LocalDagBundle",
      "kwargs": {}
    }]'
