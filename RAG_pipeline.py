from typing import Any

from source import AnswerGenerator, EmbeddingsGenerator, HybridRetriever, VectorStorage


class RAGPipeline:
    def __init__(self):
        self.vector_store = VectorStorage()
        self.embeddings_generator = EmbeddingsGenerator()
        self.hybrid_retriever = HybridRetriever(
            self.vector_store, self.embeddings_generator
        )
        self.answer_generator = AnswerGenerator()

    def search(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        """Retrieval only. Costs one query embedding, no chat call."""
        return self.hybrid_retriever.hybrid_search(query, top_k=top_k)

    def ask(self, query: str, top_k: int | None = None) -> dict[str, Any]:
        """Retrieve, then answer from what was retrieved."""
        chunks = self.search(query, top_k=top_k)
        result = self.answer_generator.generate_answer(chunks, query)
        result["chunks"] = chunks
        return result

    def close(self) -> None:
        self.vector_store.close()
