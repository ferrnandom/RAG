"""Script to create embeddings"""

from typing import Any

from openai import OpenAI
from tqdm import tqdm

from source import CONFIG


class EmbeddingsGenerator:
    def __init__(self):
        self.client = OpenAI()
        self.model = CONFIG.embedding_model
        self.dimensions = CONFIG.embedding_dimension

    def create_embeddings(
        self, texts: list[str], batch_size: int = 100
    ) -> list[list[float]]:
        """Method to create embeddings for several texts in batches"""

        all_embeddings = []

        for i in tqdm(range(0, len(texts), batch_size), desc="Creating embeddings"):
            batch = texts[i : i + batch_size]

            response = self.client.embeddings.create(
                model=self.model, input=batch, dimensions=self.dimensions
            )

            embeddings = []
            for item in response.data:
                embeddings.append(item.embedding)

            all_embeddings.extend(embeddings)

        return all_embeddings

    def add_embeddings_to_chunks(
        self, chunks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """creating a dictionary with the chunk's text, metadata and embeddings"""
        # Extracting the text from each chunk
        texts = []
        for chunk in chunks:
            texts.append(chunk["content"])

        # Create emabeddings
        embeddings = self.create_embeddings(texts)

        # Adding embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding

        return chunks

    def embed_query(self, query: str) -> list[float]:
        """Method to create an embedding from the search query. No batching, no progress bar."""
        response = self.client.embeddings.create(
            model=self.model, input=[query], dimensions=self.dimensions
        )
        return response.data[0].embedding
