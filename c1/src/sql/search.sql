-- FTS search of lexem 'air'
-- Results: (993, 990)
SELECT c.id, c.document_id 
FROM chunks c
WHERE to_tsvector('english', coalesce(c.content, ''))
	@@ plainto_tsquery('english', 'air')
ORDER BY c.id;

-- Search of substring 'air' 
-- Results: (473, 473),
--			(474, 473),
--			(776, 773),
-- 			(993, 990)
SELECT c.id, c.document_id 
FROM chunks c
WHERE c.content ILIKE '%air%'
ORDER BY c.id;