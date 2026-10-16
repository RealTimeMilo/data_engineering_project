-- schema.sql
-- Instacart hybrid search starter schema
-- Combines pgvector (semantic) + tsvector (lexical) in one Postgres database,
-- mirroring Instacart's production pattern: normalized tables, single datastore,
-- no separate search cluster.

CREATE EXTENSION IF NOT EXISTS vector;

-- Reference tables -----------------------------------------------------

CREATE TABLE IF NOT EXISTS departments (
    department_id SMALLINT PRIMARY KEY,
    department    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS aisles (
    aisle_id SMALLINT PRIMARY KEY,
    aisle    TEXT NOT NULL
);

-- Products ---------------------------------------------------------------
-- embedding: generated from product_name + aisle + department (see embed_products.py)
-- search_vector: generated column for lexical search, auto-maintained by Postgres

CREATE TABLE IF NOT EXISTS products (
    product_id     INTEGER PRIMARY KEY,
    product_name   TEXT NOT NULL,
    aisle_id       SMALLINT REFERENCES aisles(aisle_id),
    department_id  SMALLINT REFERENCES departments(department_id),
    embedding      VECTOR(384),  -- dim matches all-MiniLM-L6-v2; change if you swap models
    search_vector  TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', product_name)) STORED
);

-- Orders / order_products (optional, only needed if you also want the
-- basket-prediction / recommendation angle from the original Kaggle task) ---

CREATE TABLE IF NOT EXISTS orders (
    order_id                INTEGER PRIMARY KEY,
    user_id                 INTEGER NOT NULL,
    eval_set                TEXT,
    order_number             SMALLINT,
    order_dow                SMALLINT,
    order_hour_of_day        SMALLINT,
    days_since_prior_order   REAL
);

CREATE TABLE IF NOT EXISTS order_products (
    order_id           INTEGER REFERENCES orders(order_id),
    product_id         INTEGER REFERENCES products(product_id),
    add_to_cart_order  SMALLINT,
    reordered          SMALLINT,
    PRIMARY KEY (order_id, product_id)
);

CREATE SCHEMA IF NOT EXISTS feature_store;

-- Create the user-product feature table
CREATE TABLE feature_store.user_product_features (
    user_id                  INT NOT NULL,
    product_id               INT NOT NULL,
    times_bought_total       INT NOT NULL DEFAULT 0,
    times_in_last_5_orders   INT NOT NULL DEFAULT 0,
    reorder_probability      NUMERIC(4, 3) CHECK (reorder_probability >= 0 AND reorder_probability <= 1),
    avg_days_between_orders  NUMERIC(5, 2),
    days_since_last_purchase INT,
    feature_timestamp        TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at               TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Composite primary key covers both entities for unique user-product pairs
    PRIMARY KEY (user_id, product_id)
);

-- Index for reverse lookups (e.g., "Find all users likely to reorder a specific product")
CREATE INDEX idx_user_product_prod_id 
ON feature_store.user_product_features (product_id);

-- Indexes ------------------------------------------------------------------

-- Lexical search index
CREATE INDEX IF NOT EXISTS idx_products_search_vector
    ON products USING GIN (search_vector);

-- Semantic search index (HNSW: better recall/speed than IVFFlat, no need to
-- pre-populate data before building, unlike IVFFlat's "lists" tuning)
-- NOTE: build this AFTER embeddings are populated for best results.
-- CREATE INDEX IF NOT EXISTS idx_products_embedding
--     ON products USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_order_products_product_id
    ON order_products (product_id);
CREATE INDEX IF NOT EXISTS idx_orders_user_id
    ON orders (user_id);
