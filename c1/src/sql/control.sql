-- GIN index for 'content' `ts_vector`
CREATE INDEX idx_fts_content_gin ON chunks USING GIN(to_tsvector('english', coalesce(chunks."content", '')));
DROP INDEX IF EXISTS idx_fts_content_gin;

-- Explain clause
-- Before creating gin index: 
--   Sort (cost=47.01..47.02 rows=1 width=16) with Sort Key: id
--     ->  Seq Scan on chunks c  (cost=0.00..47.00 rows=1 width=16)
-- After creating: 
--   Sort  (cost=12.83..12.84 rows=1 width=16) with Sort Key: id
--     ->  Bitmap Heap Scan on chunks c  (cost=8.56..12.82 rows=1 width=16)
--         Recheck Cond: (to_tsvector('english'::regconfig, COALESCE(content, ''::text)) @@ '''flight'''::tsquery)
--         ->  Bitmap Index Scan on idx_fts_content_gin  (cost=0.00..8.56 rows=1 width=0)
--             Index Cond: (to_tsvector('english'::regconfig, COALESCE(content, ''::text)) @@ '''flight'''::tsquery)
EXPLAIN
	SELECT c.id, c.document_id 
	FROM chunks c
	WHERE to_tsvector('english', coalesce(c.content, ''))
		@@ plainto_tsquery('english', 'flight')
	ORDER BY c.id;