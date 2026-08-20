"""Script to generate answer based on the top global k best chunks"""

from pathlib import Path
from typing import Any

from openai import OpenAI

from source.config import CONFIG

SYSTEM_PROMPT = """You are a helpful assistant that answers questions using ONLY the \
provided context documents. Follow these rules strictly:

1. Answer using only information found in the CONTEXT section below.
2. If the answer is not in the context, say "I don't have enough information in the \
provided documents to answer that" — do not use outside knowledge.
3. Cite the passages you used with bracketed numbers, like [1] or [2][3].
4. Be concise and direct. Do not pad the answer with generic caveats beyond what's stated above.
"""


class AnswerGenerator:
    def __init__(self):
        self.client = OpenAI()
        self.model = CONFIG.chat_model

    # First method to retrieve context
    def _format_context(self, chunks: list[dict[str, Any]]) -> str:
        """We will give the LLM the chunks with their source, page and headings"""
        blocks = []
        for i, chunk in enumerate(chunks, start=1):
            metadata = chunk.get("metadata") or {}
            label = f"[{i}] {Path(metadata.get('source', 'unknown')).name}"

            pages = metadata.get("page_numbers", [])
            if pages:
                label += f" - {', '.join(str(p) for p in pages)}"

            headings = metadata.get("headings") or []
            if headings:
                label += f" - {'>'.join(str(h) for h in headings)}"

            blocks.append(f"{label}\n{chunk['content']}")
        return "\n\n".join(blocks)

    # Middle method to cite sources properly
    def _source(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Method we will use to obatain the metadata for referencing"""
        referencing = []
        for i, chunk in enumerate(chunks, start=1):
            metadata = chunk.get("metadata") or {}
            referencing.append(
                {
                    "citation": i,
                    "id": chunk.get("id"),
                    "page_numbers": metadata.get("page_numbers") or [],
                    "headings": metadata.get("headings") or [],
                    "source": Path(metadata.get("source", "unknown")).name,
                }
            )
        return referencing

    # Final method to generate answer based on retrieved context
    def generate_answer(
        self, chunks: list[dict[str, Any]], query: str
    ) -> dict[str, Any]:
        """Answers user question based on the retrieved chunks"""
        if not chunks:
            return {
                "answer": "I found nothing relevant in the indexed documents for that question.",
                "sources": [],
                "model": self.model,
            }
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Context: {self._format_context(chunks)}\n\nQuestion: {query}"
                    ),
                },
            ],
            max_completion_tokens=CONFIG.max_answer_tokens,
            temperature=CONFIG.chat_temperature,
        )

        return {
            "answer": response.choices[0].message.content,
            "sources": self._source(chunks),
            "model": self.model,
        }
