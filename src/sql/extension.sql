-- MV creation.
EXPLAIN ANALYZE
CREATE MATERIALIZED VIEW IF NOT EXISTS q5_mt_view AS (
	SELECT 
		pf.processed_at_parsed::date AS processing_date,
		ARRAY_AGG(DISTINCT em.model_name),
		count(*)	
	FROM provenance_files pf 
		JOIN provenance_file_models pfm ON pfm.file_id = pf.id
		JOIN enum_models em ON em.model_id = pfm.model_id
	WHERE pf.processed_at_parsed IS NOT NULL
	GROUP BY
		pf.processed_at_parsed::date
	ORDER BY processing_date
);
-- MV drop.
DROP MATERIALIZED VIEW IF EXISTS q5_mt_view;

-- Comparison of selection from mv and from original query
-- using index q5 from `indexes_and_extensions.sql`.
EXPLAIN ANALYZE
SELECT *
FROM q5_mt_view;

EXPLAIN ANALYZE
SELECT 
	pf.processed_at_parsed::date AS processing_date,
	ARRAY_AGG(DISTINCT em.model_name),
	count(*)	
FROM provenance_files pf 
	JOIN provenance_file_models pfm ON pfm.file_id = pf.id
	JOIN enum_models em ON em.model_id = pfm.model_id
WHERE pf.processed_at_parsed IS NOT NULL
GROUP BY
	pf.processed_at_parsed::date
ORDER BY processing_date;

-- Assessment of refresh time of materialized view after update.
BEGIN;

INSERT INTO provenance_files (
	id, source_row, attempts,
	pdf_sha256_status, file_status, output_sha256_status,
	first_seen_at_status, processed_at_status, document_match_status, model_used_status,
	source_file, file_key, output_name, pdf_path,
	first_seen_at_raw, processed_at_raw, first_seen_at_parsed, processed_at_parsed,
	model_used_raw
) VALUES
	(10000000, 0, 1, 3, 1, 3, 1, 1, 2, 1,
	 'refresh_batch_10.jsonl', 'refresh_batch_10000000', 'refresh_batch_10000000.json', 'refresh_batch_10000000.pdf',
	 '2026-10-10T09:00:00Z', '2026-10-10T09:01:00Z', '2026-10-10T09:00:00Z', '2026-10-10T09:01:00Z',
	 'gemini-2.5-flash,gemini-3-flash-preview,gpt-5-nano'),
	(10000001, 1, 1, 3, 1, 3, 1, 1, 2, 1,
	 'refresh_batch_10.jsonl', 'refresh_batch_10000001', 'refresh_batch_10000001.json', 'refresh_batch_10000001.pdf',
	 '2026-10-10T09:00:00Z', '2026-10-10T09:02:00Z', '2026-10-10T09:00:00Z', '2026-10-10T09:02:00Z',
	 'gemini-2.5-flash-lite'),
	(10000002, 2, 1, 3, 1, 3, 1, 1, 2, 1,
	 'refresh_batch_10.jsonl', 'refresh_batch_10000002', 'refresh_batch_10000002.json', 'refresh_batch_10000002.pdf',
	 '2026-10-10T09:00:00Z', '2026-10-10T09:03:00Z', '2026-10-10T09:00:00Z', '2026-10-10T09:03:00Z',
	 'gemini-3-flash-preview,gpt-4o-mini'),
	(10000003, 3, 1, 3, 1, 3, 1, 1, 2, 1,
	 'refresh_batch_10.jsonl', 'refresh_batch_10000003', 'refresh_batch_10000003.json', 'refresh_batch_10000003.pdf',
	 '2026-10-10T09:00:00Z', '2026-10-10T09:04:00Z', '2026-10-10T09:00:00Z', '2026-10-10T09:04:00Z',
	 'gpt-4o-mini,gpt-5-nano,grok-2-vision-latest'),
	(10000004, 4, 1, 3, 1, 3, 1, 1, 2, 1,
	 'refresh_batch_10.jsonl', 'refresh_batch_10000004', 'refresh_batch_10000004.json', 'refresh_batch_10000004.pdf',
	 '2026-10-10T09:00:00Z', '2026-10-10T09:05:00Z', '2026-10-10T09:00:00Z', '2026-10-10T09:05:00Z',
	 'tesseract-community'),
	(10000005, 5, 1, 3, 1, 3, 1, 1, 2, 1,
	 'refresh_batch_10.jsonl', 'refresh_batch_10000005', 'refresh_batch_10000005.json', 'refresh_batch_10000005.pdf',
	 '2026-10-10T09:00:00Z', '2026-10-10T09:06:00Z', '2026-10-10T09:00:00Z', '2026-10-10T09:06:00Z',
	 'gemini-2.5-flash,gpt-4o-mini'),
	(10000006, 6, 1, 3, 1, 3, 1, 1, 2, 1,
	 'refresh_batch_10.jsonl', 'refresh_batch_10000006', 'refresh_batch_10000006.json', 'refresh_batch_10000006.pdf',
	 '2026-10-10T09:00:00Z', '2026-10-10T09:07:00Z', '2026-10-10T09:00:00Z', '2026-10-10T09:07:00Z',
	 'gemini-2.5-flash-lite,gpt-5-nano,tesseract-community'),
	(10000007, 7, 1, 3, 1, 3, 1, 1, 2, 1,
	 'refresh_batch_10.jsonl', 'refresh_batch_10000007', 'refresh_batch_10000007.json', 'refresh_batch_10000007.pdf',
	 '2026-10-10T09:00:00Z', '2026-10-10T09:08:00Z', '2026-10-10T09:00:00Z', '2026-10-10T09:08:00Z',
	 'grok-2-vision-latest'),
	(10000008, 8, 1, 3, 1, 3, 1, 1, 2, 1,
	 'refresh_batch_10.jsonl', 'refresh_batch_10000008', 'refresh_batch_10000008.json', 'refresh_batch_10000008.pdf',
	 '2026-10-10T09:00:00Z', '2026-10-10T09:09:00Z', '2026-10-10T09:00:00Z', '2026-10-10T09:09:00Z',
	 'gemini-3-flash-preview,tesseract-community'),
	(10000009, 9, 1, 3, 1, 3, 1, 1, 2, 1,
	 'refresh_batch_10.jsonl', 'refresh_batch_10000009', 'refresh_batch_10000009.json', 'refresh_batch_10000009.pdf',
	 '2026-10-10T09:00:00Z', '2026-10-10T09:10:00Z', '2026-10-10T09:00:00Z', '2026-10-10T09:10:00Z',
	 'gemini-2.5-flash,gemini-2.5-flash-lite,gpt-4o-mini');

INSERT INTO provenance_file_models (file_id, model_id) VALUES
	(10000000, 1),
	(10000000, 3),
	(10000000, 6),
	(10000001, 2),
	(10000002, 3),
	(10000002, 5),
	(10000003, 5),
	(10000003, 6),
	(10000003, 7),
	(10000004, 8),
	(10000005, 1),
	(10000005, 5),
	(10000006, 2),
	(10000006, 6),
	(10000006, 8),
	(10000007, 7),
	(10000008, 3),
	(10000008, 8),
	(10000009, 1),
	(10000009, 2),
	(10000009, 5);

REFRESH MATERIALIZED VIEW q5_mt_view;

ROLLBACK;
