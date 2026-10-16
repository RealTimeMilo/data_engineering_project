FROM apache/airflow:3.2.2
USER root
RUN apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /
USER airflow
RUN pip install --no-cache-dir -r /requirements.txt

COPY ec2_airflow_config.sh /
RUN cd / && bash /ec2_airflow_config.sh

# Airflow 3 reads DAGs from its default local bundle folder. The `dags/` build
# context is staged here by `make ecs-airflow-build` so the DAGs ship in the
# image and appear in the ECS Airflow UI without a Git connection.
COPY --chown=airflow:0 dags/ /opt/airflow/dags/