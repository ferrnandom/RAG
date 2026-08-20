CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    content TEXT NOT NULL,
    metadata JSONB,
    embedding vector(1536),
    fts TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS documents_embedding_idx ON documents USING hnsw (embedding vector_ip_ops);
CREATE INDEX IF NOT EXISTS documents_fts_idx ON documents USING GIN (fts);
CREATE INDEX IF NOT EXISTS documents_metadata_idx ON documents USING GIN (metadata);