-- Text search indexes for Q1 and Q2
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

-- Q4
-- GiST over temporary table existing inside the transaction.
CREATE INDEX IF NOT EXISTS idx_temp_cardholder_gist
    ON q4_index_items USING gist
        (lower(cardholder) gist_trgm_ops(siglen=32));

-- Partial covering B-tree.
CREATE INDEX IF NOT EXISTS idx_financial_transactions_cardholder
    ON financial_transactions USING btree (cardholder)
    INCLUDE (amount)
    WHERE cardholder IS NOT NULL;

-- Q5: composite covering B-tree. Both columns are index keys.
CREATE INDEX IF NOT EXISTS idx_provenance_files_processed_id_btree
    ON provenance_files USING btree (processed_at_parsed, id)
    WHERE processed_at_parsed IS NOT NULL;

-- Q6: B-tree over email_fields_status. 
CREATE INDEX IF NOT EXISTS idx_documents_email_fields_status_btree
    ON documents USING btree (email_fields_status);

-- Extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;
DROP EXTENSION IF EXISTS pg_trgm;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
DROP EXTENSION IF EXISTS pgcrypto;