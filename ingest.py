from pathlib import Path

from source import EmbeddingsGenerator, ProcessDocument, VectorStorage


class IngestionPipeline:
    def __init__(self):
        self.vector_store = VectorStorage()
        self.embeddings_pipeline = EmbeddingsGenerator()
        self.document_processor = ProcessDocument()

    def ingest_document(self, path: str | Path):
        """Method to upload a file, split it in chunks and create its embeddings"""
        path = str(path)

        removed = self.vector_store.remove_by_source(path)
        if removed:
            print(f"Replacing {removed} existing chunks for this source")

        # Converting documents to chunks
        chunks = self.document_processor.chunk_document(path)
        # Adding the embeddings to the chunks
        chunks_with_embeddings = self.embeddings_pipeline.add_embeddings_to_chunks(
            chunks
        )
        # Adding the chunks with embeddings to the vector store
        self.vector_store.add_chunks(chunks_with_embeddings)

        # Print statistics of the chunks we have added to the vector DB
        statistics = self.document_processor.chunk_statistics(chunks)
        print("\nIngestion complete!")
        print(f"Total chunks: {statistics['total_chunks']}")
        print(f"Average tokens per chunk: {statistics['avg_tokens_per_chunk']:.1f}")
        print(f"Total documents in store: {self.vector_store.count()}")

    def ingest_directory(self, directory: str):
        """Pipeline to ingest all the files in a given directory using the ingest_document() method"""
        results = {"succeeded": [], "failed": []}
        for path in Path(directory).rglob("*"):
            if path.is_dir():
                continue
            try:
                self.ingest_document(str(path))  # reuses the whole existing pipeline
                results["succeeded"].append(str(path))
            except Exception as e:
                print(f"Skipped {path}: {e}")
                results["failed"].append((str(path), str(e)))
        print(
            f"Successful ingested documents {len(results['succeeded'])}; failed ingested documents: {len(results['failed'])}"
        )
        return results


if __name__ == "__main__":
    ingestion_pipeline = IngestionPipeline()
    ingestion_pipeline.ingest_directory(Path(__file__).parent / "data")
