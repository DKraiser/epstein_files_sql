-- FTS search of lexem 'flight'
SELECT c.id, c.document_id 
FROM chunks c
WHERE to_tsvector('english', coalesce(c.content, ''))
	@@ plainto_tsquery('english', 'flight')
ORDER BY c.id;

-- Search of substring 'flight' 
SELECT c.id, c.document_id 
FROM chunks c
WHERE c.content LIKE '%flight%'
ORDER BY c.id;