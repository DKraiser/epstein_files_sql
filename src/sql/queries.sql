-- FTS
-- Without index: 58s

SELECT dc.id
FROM (
    SELECT d.id AS id
        FROM documents as d
        WHERE d.full_text_searchvec @@ plainto_tsquery('english', 'air')
    
    UNION 

    SELECT c.document_id AS id
        FROM chunks as c
        WHERE c.content_searchvec @@ plainto_tsquery('english', 'air')
) AS dc
ORDER BY dc.id ASC;

-- Total creation time: 9 min 1 sec
CREATE INDEX IF NOT EXISTS idx_documents_full_text_searchvec_gin ON documents USING gin(full_text_searchvec);
CREATE INDEX IF NOT EXISTS idx_chunks_content_searchvec_gin ON chunks USING gin(content_searchvec);