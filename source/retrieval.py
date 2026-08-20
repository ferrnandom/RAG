"""Hybrid retrieval: we combine dense search (pgvector) + sparse (Postgres FTS). Then we combine using RRF"""

from collections import defaultdict
from typing import Any

from source.config import CONFIG
from source.embeddings import EmbeddingsGenerator
from source.vector_store import VectorStorage


def reciprocal_rank_fusion(
    rankings: list[list[int]], k: int | None = None
) -> list[tuple[int, float]]:
    """This function receives the top k results from dense and sparse search. Then takes both results and
    returns the best top k results from both lists. To do so, it considers the position in the original list

    score(doc) = sum over each ranking of 1 / (k + rank)
    """
    k = k or CONFIG.rrf_k
    scores: dict[int, float] = defaultdict(float)

    # creating the rrf score
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] += (
                1.0 / (k + rank)
            )  # we accumulate the results in case they appear in both search results (sparse and dense)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))


class HybridRetriever:
    def __init__(self, store: VectorStorage, embedder: EmbeddingsGenerator):
        self.store = store
        self.embedder = embedder

    def dense_search(self, query: str, k: int) -> list[dict[int, Any]]:
        embedded_query = self.embedder.embed_query(query)
        return self.store.similarity_search(embedded_query, k)

    def sparse_search(self, query: str, k: int) -> list[tuple[int, Any]]:
        return self.store.keyword_search(query, k)

    def hybrid_search(
        self, query: str, top_k: int | None = None, candidate_k: int | None = None
    ) -> list[dict[int, Any]]:
        top_k = top_k or CONFIG.top_k
        candidate_k = candidate_k or CONFIG.candidate_k

        # IDs of the dense and sparse search
        dense_ids = [row["id"] for row in self.dense_search(query, candidate_k)]
        sparse_ids = [doc_id for doc_id, _ in self.sparse_search(query, candidate_k)]

        fused_results = reciprocal_rank_fusion([dense_ids, sparse_ids])[:top_k]

        # now we get the chunks from the vector db
        get_ids_from_db = []
        for doc_id, score in fused_results:
            get_ids_from_db.append(doc_id)
        rows = self.store.get_by_ids(get_ids_from_db)

        results = []
        for rank, (doc_id, score) in enumerate(fused_results, start=1):
            row = rows.get(doc_id)
            if row is None:
                continue
            results.append({**row, "rank": rank, "rrf_score": score})
        return results
