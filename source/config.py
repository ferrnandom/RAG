# This file contains the object CONFIG
import os
from dataclasses import dataclass

from dotenv import load_dotenv

# loading environmental variables
load_dotenv()


@dataclass
class Config:
    # Embeddings config
    embedding_model = "text-embedding-3-small"  # check that this embedding model is the appropiate based on my LLM
    embedding_dimension = 1536
    chunk_max_tokens = 512

    # OpenAI API key
    openai_key = os.getenv("OPENAI_API_KEY")

    # VectorDB config
    db_host = "localhost"
    db_port = 5555
    db_name = "postgres"
    db_user = "postgres"
    db_password = "postgres"

    # Retrieval
    candidate_k = 50
    top_k = 10
    rrf_k = 60

    # Postgress FTS
    fts_language = "english"
    fts_normalization = 1

    # Generation
    chat_model = "gpt-5.4-nano"
    chat_temperature = 0
    max_answer_tokens = 800


CONFIG = Config()
