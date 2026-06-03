-- Create feature_store schema
CREATE SCHEMA IF NOT EXISTS feature_store;

-- 1. Feature Registry (metadata)
CREATE TABLE IF NOT EXISTS feature_store.feature_registry (
  feature_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  feature_name VARCHAR(255) NOT NULL UNIQUE,
  feature_type VARCHAR(50) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  is_active BOOLEAN DEFAULT TRUE
);

-- 2. Feature Values (entity time-series data)
CREATE TABLE IF NOT EXISTS feature_store.feature_values (
  id BIGSERIAL PRIMARY KEY,
  entity_id VARCHAR(255) NOT NULL,
  feature_id UUID NOT NULL REFERENCES feature_store.feature_registry(feature_id),
  value JSONB,
  event_timestamp TIMESTAMPTZ DEFAULT NOW(),
  partition_key VARCHAR(50)
);
CREATE INDEX IF NOT EXISTS idx_entity_feature ON feature_store.feature_values(entity_id, feature_id);
CREATE INDEX IF NOT EXISTS idx_event_ts ON feature_store.feature_values(event_timestamp);

-- 3. Feature Audit (change tracking for Blue/Green)
CREATE TABLE IF NOT EXISTS feature_store.feature_audit (
  audit_id BIGSERIAL PRIMARY KEY,
  operation VARCHAR(20) NOT NULL,
  entity_id VARCHAR(255),
  feature_id UUID,
  changed_at TIMESTAMPTZ DEFAULT NOW(),
  details JSONB,
  deployment_tag VARCHAR(50)
);
CREATE INDEX IF NOT EXISTS idx_deployment_tag ON feature_store.feature_audit(deployment_tag);

-- Enable pg_stat_statements for monitoring (optional)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;