"""
hybrid_search.py

Runs a hybrid (lexical + semantic) product search against Postgres, combining
ts_rank (keyword match) and pgvector cosine similarity (semantic match) in a
single SQL query — the same pattern Instacart uses in production, just at a
much smaller scale.

Usage:
  python hybrid_search.py --dsn "postgresql://user:pass@localhost:5432/instacart" \
      --query "organic banana" --limit 10
"""

import argparse

import psycopg2
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"

# Weights for combining the two scores. Tune based on what matters more for
# your use case: exact attribute matches (lexical) vs. conceptual similarity
# (semantic, e.g. "breakfast cereal" matching "granola").
LEXICAL_WEIGHT = 0.4
SEMANTIC_WEIGHT = 0.6

SQL = """
SELECT
    product_id,
    product_name,
    ts_rank(search_vector, plainto_tsquery('english', %(query_text)s)) AS lexical_score,
    1 - (embedding <=> %(query_embedding)s) AS semantic_score,
    (%(lex_w)s * ts_rank(search_vector, plainto_tsquery('english', %(query_text)s))
     + %(sem_w)s * (1 - (embedding <=> %(query_embedding)s))) AS combined_score
FROM products
WHERE embedding IS NOT NULL
ORDER BY combined_score DESC
LIMIT %(limit)s;
"""


def search(conn, model, query_text: str, limit: int):
    query_embedding = model.encode(query_text).tolist()

    with conn.cursor() as cur:
        cur.execute(
            SQL,
            {
                "query_text": query_text,
                "query_embedding": query_embedding,
                "lex_w": LEXICAL_WEIGHT,
                "sem_w": SEMANTIC_WEIGHT,
                "limit": limit,
            },
        )
        return cur.fetchall()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True, help="Postgres connection string")
    parser.add_argument("--query", required=True, help="Search text, e.g. 'organic banana'")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    conn = psycopg2.connect(args.dsn)
    register_vector(conn)

    model = SentenceTransformer(MODEL_NAME)

    results = search(conn, model, args.query, args.limit)

    print(f"\nResults for: {args.query!r}\n")
    print(f"{'product_id':<12}{'lexical':<10}{'semantic':<10}{'combined':<10}product_name")
    print("-" * 90)
    for product_id, name, lex, sem, combined in results:
        print(f"{product_id:<12}{lex:<10.4f}{sem:<10.4f}{combined:<10.4f}{name}")

    conn.close()


if __name__ == "__main__":
    main()
