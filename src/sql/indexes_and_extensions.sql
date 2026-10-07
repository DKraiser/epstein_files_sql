-- Create indexes
-- GIN on tsvectors
CREATE INDEX IF NOT EXISTS idx_documents_full_text_searchvec_gin ON documents USING gin(full_text_searchvec);
CREATE INDEX IF NOT EXISTS idx_chunks_content_searchvec_gin ON chunks USING gin(content_searchvec);

-- GIN trigram on original texts
CREATE INDEX IF NOT EXISTS idx_documents_full_text_gin_trgm ON documents USING gin(full_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_chunks_content_gin_trgm ON chunks USING gin("content" gin_trgm_ops);

--GiST
CREATE INDEX IF NOT EXISTS idx_documents_full_text_searchvec_gist ON documents USING gist(full_text_searchvec);
CREATE INDEX IF NOT EXISTS idx_chunks_content_searchvec_gist ON chunks USING gist(content_searchvec);

--Drop indexes
-- GIN
DROP INDEX IF EXISTS idx_documents_full_text_searchvec_gin;
DROP INDEX IF EXISTS idx_chunks_content_searchvec_gin;

-- GIN trigram
DROP INDEX IF EXISTS idx_documents_full_text_gin_trgm;
DROP INDEX IF EXISTS idx_chunks_content_gin_trgm;

-- GiST
DROP INDEX IF EXISTS idx_documents_full_text_searchvec_gist;
DROP INDEX IF EXISTS idx_chunks_content_searchvec_gist;


-- Extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;
DROP EXTENSION IF EXISTS pg_trgm;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
DROP EXTENSION IF EXISTS pgcrypto;