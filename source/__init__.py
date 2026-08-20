"""Source package for our RAG project.

Re-exports the main classes and CONFIG so modules can do
`from source import CONFIG, EmbeddingsGenerator, ProcessDocument, VectorStorage`.
"""

from source.config import CONFIG
from source.doc_processing import ProcessDocument
from source.embeddings import EmbeddingsGenerator
from source.generate import AnswerGenerator
from source.retrieval import HybridRetriever, reciprocal_rank_fusion
from source.vector_store import VectorStorage

__all__ = [
    "CONFIG",
    "AnswerGenerator",
    "EmbeddingsGenerator",
    "HybridRetriever",
    "ProcessDocument",
    "VectorStorage",
    "reciprocal_rank_fusion",
]
