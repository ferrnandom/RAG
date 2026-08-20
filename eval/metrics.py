"""Retrieval metrics implemented by hand"""

import math


def hit_rate_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """scores 1.0 if any of the retrieved chunks is in the top k"""
    return 1.0 if set(retrieved[:k]) & relevant else 0.0


def racall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """fraction of all relevant chunks that appear in the top k"""
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str]) -> float:
    """Reciprocal Rank of the first relevant chunk"""
    for rank, key in enumerate(retrieved, start=1):
        if key in relevant:
            return 1.0 / rank
    return 0.0


def _dcg(gains: list[float]) -> float:
    return sum(g / math.log2(rank + 1) for rank, g in enumerate(gains, start=1))


def ndcg_at_k(retrieved: list[str], grades: dict[str, int], k: int) -> float:
    """Graded relevance, position-discounted.

    Uses gain = 2^rel - 1, the TREC convention that pytrec_eval implements, so
    hand-computed values match the reported ones. The other common variant uses
    gain = rel and produces different numbers -- this is exactly why you should
    not invent your own nDCG for anything you publish.
    """
    gains = [2 ** grades.get(key, 0) - 1 for key in retrieved[:k]]
    ideal = [2**g - 1 for g in sorted(grades.values(), reverse=True)[:k]]
    idcg = _dcg(ideal)
    return _dcg(gains) / idcg if idcg else 0.0
