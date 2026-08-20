"""
In this file first I will create a logic for loading and chunking one doc
at a time. then in the RAG system logic I will extrapolate this approach to load several files at a time
"""

from typing import Any

import tiktoken
from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer

from source import CONFIG


class ProcessDocument:
    def __init__(self):
        self.converter = DocumentConverter()
        tiktoken_encoder = tiktoken.encoding_for_model(CONFIG.embedding_model)
        self.tokenizer = OpenAITokenizer(
            tokenizer=tiktoken_encoder, max_tokens=CONFIG.chunk_max_tokens
        )
        self.chunker = HybridChunker(tokenizer=self.tokenizer)

    def chunk_document(self, source: str) -> list[dict[str, Any]]:
        """Given a source, we load the file, chunk and create meta data for later referencing"""

        # First we create a docling object
        print(f"Extracting document from: {source}")
        doc = self.converter.convert(source).document  # docling object

        # Second we create the chunks
        chunks = list(self.chunker.chunk(dl_doc=doc))  # list of DocMetaChunk objects

        # example of docling object
        """
        DocMetaChunk(
        text="Our total revenue reached $14.2M, representing a substantial year-over-year increase.",
        meta=ChunkMeta(
            headings=["Company Annual Report 2025", "Financial Performance"],
            doc_items=[
                TextElement(
                    self_ref="#/texts/12", 
                    label="paragraph", 
                    text="Our total revenue reached $14.2M, representing a substantial year-over-year increase.", 
                    prov=[ProvenanceItem(page_no=2, bbox=BoundingBox(...))]
                )
            ]
        )
    )
]"""
        # Addding context for later referencing to our chunks
        processed_chunks = []
        for i, chunk in enumerate(chunks):
            # We get the contextualized text including heading/context
            contextualized_text = self.chunker.contextualize(chunk=chunk)

            # set of unique page numbers
            page_numbers = set()
            for item in chunk.meta.doc_items:
                for prov in item.prov:
                    if hasattr(prov, "page_no"):
                        page_numbers.add(prov.page_no)
            page_numbers = sorted(page_numbers)

            # Extracting headers from the files
            headings = []
            if hasattr(chunk.meta, "headings"):
                headings = chunk.meta.headings

            metadata = {
                "chunk_index": i,
                "total_chunks": len(chunks),
                "source": source,
                "page_numbers": page_numbers,
                "headings": headings,
            }

            processed_chunks.append(
                {"content": contextualized_text, "metadata": metadata}
            )

        print(f"In total {len(chunks)} were created")
        return processed_chunks

        """ 
Visual example of what a chunk would look like: 

{
    "content": "Company Annual Report 2025\nFinancial Performance\nOur total revenue reached $14.2M, representing a substantial year-over-year increase.",
    "metadata": {
        "chunk_index": 12,
        "total_chunks": 47,
        "source": "data/Company_Annual_Report_2025.pdf",
        "page_numbers": [2],
        "headings": ["Company Annual Report 2025", "Financial Performance"],
    },
}

"""

    def chunk_statistics(self, chunks: list[dict[str, any]]) -> list[dict[str, any]]:
        """Generate statistics about the generated chunks"""
        total_tokens = 0

        for chunk in chunks:
            tokens = self.tokenizer.tokenizer.encode(chunk["content"])
            total_tokens += len(tokens)

        return {
            "total_chunks": len(chunks),
            "total_tokens": total_tokens,
            "avg_tokens_per_chunk": total_tokens / len(chunks) if chunks else 0,
        }
