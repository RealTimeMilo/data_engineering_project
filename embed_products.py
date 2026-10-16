"""
embed_products.py

Generates an embedding for each product (from product_name + aisle + department)
and writes it into the `embedding` VECTOR(384) column in Postgres.

Uses a local, free sentence-transformers model (no API key, no cost) so this
runs end-to-end offline. Swap in OpenAI/Cohere embeddings if you want higher
quality — just update EMBED_DIM in schema.sql to match (1536 for OpenAI
text-embedding-3-small, etc).

Usage:
  pip install sentence-transformers psycopg2-binary pgvector tqdm
  python embed_products.py --dsn "postgresql://user:pass@localhost:5432/instacart"
"""

import argparse

import psycopg2
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

MODEL_NAME = "all-MiniLM-L6-v2"  # 384-dim, fast, good enough for a starter project
BATCH_SIZE = 256


def fetch_products(conn):
    """Pull product_id + a composite text field (name + aisle + department)."""
    query = """
        SELECT p.product_id,
               p.product_name || ' ' || a.aisle || ' ' || d.department AS text
        FROM products p
        JOIN aisles a ON p.aisle_id = a.aisle_id
        JOIN departments d ON p.department_id = d.department_id
        WHERE p.embedding IS NULL
    """
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def update_embeddings(conn, model, rows):
    with conn.cursor() as cur:
        for i in tqdm(range(0, len(rows), BATCH_SIZE), desc="Embedding batches"):
            batch = rows[i:i + BATCH_SIZE]
            ids = [r[0] for r in batch]
            texts = [r[1] for r in batch]

            embeddings = model.encode(texts, show_progress_bar=False)

            for product_id, embedding in zip(ids, embeddings):
                cur.execute(
                    "UPDATE products SET embedding = %s WHERE product_id = %s",
                    (embedding.tolist(), product_id),
                )
            conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True, help="Postgres connection string")
    args = parser.parse_args()

    conn = psycopg2.connect(args.dsn)
    register_vector(conn)

    print(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    print("Fetching products missing embeddings...")
    rows = fetch_products(conn)
    print(f"  {len(rows)} products to embed")

    if rows:
        update_embeddings(conn, model, rows)

    print("Building HNSW index (run once, after embeddings are populated)...")
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_products_embedding
            ON products USING hnsw (embedding vector_cosine_ops)
            """
        )
    conn.commit()

    conn.close()
    print("Done. Next: run hybrid_search.py to query.")


if __name__ == "__main__":
    main()
