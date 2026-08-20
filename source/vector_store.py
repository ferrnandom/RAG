"""Vector storage implementation using PG Admin"""

import json
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from source import CONFIG


class VectorStorage:
    def __init__(self):
        self.conn = psycopg.connect(
            f"host={CONFIG.db_host} port={CONFIG.db_port} "
            f"dbname={CONFIG.db_name} user={CONFIG.db_user} "
            f"password={CONFIG.db_password}",
            autocommit=True,
        )
        register_vector(
            self.conn
        )  # Translates between python list[float] to Postgres vector types

    def add_chunks(self, chunks: list[dict[str, Any]]) -> int:
        """Adding chunks to the vectorDB"""
        with self.conn.transaction():
            with self.conn.cursor() as cur:
                for chunk in chunks:
                    cur.execute(
                        "INSERT INTO documents (content, metadata, embedding) VALUES (%s, %s, %s)",
                        (
                            chunk["content"],
                            json.dumps(chunk.get("metadata", {})),
                            chunk["embedding"],
                        ),
                    )

            return len(chunks)

    def similarity_search(
        self, query_embedding: list[float], k: int = 5
    ) -> list[dict[str, Any]]:
        """Return the K chuncks closest to the query"""

        with self.conn.cursor(row_factory=dict_row) as cur:
            result = cur.execute(
                """
                SELECT id, content, metadata,
                -(embedding <#> %s::vector) AS similarity
                FROM documents
                ORDER BY embedding <#> %s::vector
                LIMIT %s
                """,
                (query_embedding, query_embedding, k),
            )
            return result.fetchall()

    def keyword_search(self, query: str, k: int = 5) -> list[tuple[int, float]]:
        """Returns the chunk ID and relevance score for a keyword search.

        Converts the search query into clean word roots (lexemes), removes
        common stopwords, and joins the terms with OR to find matching chunks.
        """
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(  # CTE to preprocess the search query the same way chunks were processed
                """    
                WITH q AS ( 
                    SELECT array_to_string(
                        tsvector_to_array(to_tsvector(%s::regconfig, %s)), ' | '
                    ) ::tsquery AS query
                )
                SELECT d.id, ts_rank_cd(d.fts, q.query, %s) AS score
                FROM documents d, q
                WHERE d.fts @@ q.query
                ORDER BY score DESC, d.id
                LIMIT %s
                """,
                (CONFIG.fts_language, query, CONFIG.fts_normalization, k),
            )
            result_list = []
            for row in cur.fetchall():
                result_list.append((row["id"], float(row["score"])))
            return result_list

    def get_by_ids(self, ids: list[int]) -> dict[int, dict[str, Any]]:
        """Function that will look for documents based on their ID"""
        if not ids:
            return {}
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                " SELECT id, content, metadata FROM documents WHERE ID = any(%s)",
                (ids,),
            )
            result_dict = {}
            for row in cur.fetchall():
                result_dict[row["id"]] = row
            return result_dict

    def remove_by_source(self, source: str) -> int:
        """Removes a document's chunks to avoid duplicating when re-ingesting"""
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM documents WHERE metadata ->>  'source' = %s",
                (source,),
            )
            return cur.rowcount

    def count(self) -> int:
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents")
            return cur.fetchone()[0]

    def clear(self):
        with self.conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE documents RESTART IDENTITY")
            self.conn.commit()

    def all_chunks(self) -> list[dict[str, Any]]:
        """Gets all the chunks sorted by id"""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id, content, metadata FROM documents ORDER BY id")
            return cur.fetchall()

    def close(self):
        self.conn.close()
