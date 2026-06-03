-- Pipeline registry: SQL-driven dynamic DAG definitions (loaded at scheduler parse time)
CREATE SCHEMA IF NOT EXISTS pipeline_config;

CREATE TABLE IF NOT EXISTS pipeline_config.pipelines (
    id              VARCHAR(64) PRIMARY KEY,
    description     TEXT,
    endpoint        VARCHAR(128),
    schedule        VARCHAR(32) NOT NULL DEFAULT '0 6 * * *',
    quality_column  VARCHAR(64) NOT NULL DEFAULT 'name',
    render_dashboard BOOLEAN NOT NULL DEFAULT FALSE,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    pipeline_type   VARCHAR(32) NOT NULL DEFAULT 'coincap_api',
    sql_file        VARCHAR(256),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO pipeline_config.pipelines (
    id, description, endpoint, schedule, quality_column,
    render_dashboard, enabled, pipeline_type, sql_file
) VALUES
    (
        'exchanges',
        'CoinCap exchanges API (SQL registry)',
        'exchanges',
        '0 6 * * *',
        'name',
        TRUE,
        TRUE,
        'coincap_api',
        NULL
    ),
    (
        'assets',
        'CoinCap assets API (SQL registry)',
        'assets',
        '0 7 * * *',
        'name',
        FALSE,
        TRUE,
        'coincap_api',
        NULL
    ),
    (
        'markets',
        'CoinCap markets API (SQL registry)',
        'markets',
        '0 8 * * *',
        'exchangeId',
        FALSE,
        TRUE,
        'coincap_api',
        NULL
    ),
    (
        'exchanges_summary',
        'Transform raw exchanges CSV into Postgres summary table',
        NULL,
        '30 6 * * *',
        'name',
        FALSE,
        TRUE,
        'sql_transform',
        'sql/transform_exchanges_summary.sql'
    )
ON CONFLICT (id) DO UPDATE SET
    description      = EXCLUDED.description,
    endpoint         = EXCLUDED.endpoint,
    schedule         = EXCLUDED.schedule,
    quality_column   = EXCLUDED.quality_column,
    render_dashboard = EXCLUDED.render_dashboard,
    enabled          = EXCLUDED.enabled,
    pipeline_type    = EXCLUDED.pipeline_type,
    sql_file         = EXCLUDED.sql_file,
    updated_at       = NOW();
