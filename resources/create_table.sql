CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS endpoint_embeddings (
    id SERIAL PRIMARY KEY,
    http_method VARCHAR(10) NOT NULL,
    path TEXT NOT NULL,
    gcp_service VARCHAR(100) NOT NULL,
    natural_text TEXT NOT NULL,
    embedding vector(1024), -- Size for model mxbai-embed-large
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);