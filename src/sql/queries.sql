-- Q1: Full TS - gin
WITH params AS (
    SELECT plainto_tsquery('english', 'air') AS query
)
SELECT DISTINCT dc.id
FROM params as p
    CROSS JOIN LATERAL (
        SELECT d.id AS id
            FROM documents as d
            WHERE d.full_text_searchvec @@ p.query
        UNION ALL
        SELECT c.document_id AS id
            FROM chunks as c
            WHERE c.content_searchvec @@ p.query
    ) AS dc
ORDER BY dc.id ASC;



-- Q2: Fuzzy TS - gin_trgm
WITH params AS (
    SELECT 
        current_setting('pg_trgm.word_similarity_threshold')::REAL AS similarity_threshold,
        'fliht'::TEXT AS searched
),
selected_ids AS (
	SELECT
	    candidate_rows.id AS document_id,
	    MAX(candidate_rows.score) AS score
	FROM params AS p
	    CROSS JOIN LATERAL (
	        SELECT 
	        	d.id AS id,
	        	word_similarity(p.searched, d.full_text) AS score 
	        FROM documents AS d
			WHERE p.searched <% d.full_text
			UNION ALL
			SELECT 
	        	c.document_id AS id,
	        	word_similarity(p.searched, c.content) AS score 
	        FROM chunks AS c
			WHERE p.searched <<% c."content"
	    ) AS candidate_rows 
	GROUP BY 
		candidate_rows.id
)
SELECT 
	si.document_id,
	si.score,
	d.full_text,
	p.similarity_threshold,
	p.searched,
	'pg_trgm.word_similarity'::TEXT AS "method"
FROM selected_ids si
	JOIN documents d ON d.id = si.document_id
	CROSS JOIN params p
ORDER BY 
	si.score DESC, 
	si.document_id ASC;



-- Q3: Relational 2-hop - seq scans
WITH graph_starts_and_intermediates AS (
	SELECT 
		ke_starts.id AS start_node_id,
		kr.id AS start_to_intermediate_edge_id,
		kr.target_id AS intermediate_node_id
	FROM kg_entities ke_starts
		JOIN kg_relationships kr ON kr.source_id = ke_starts.id
	WHERE NOT EXISTS (
		SELECT 1
		FROM kg_relationships kr2 
		WHERE kr2.target_id = ke_starts.id
	)
),
graph_second_edges_and_possible_ends AS (
	SELECT 
		gs.*,
		kr.id AS intermediate_to_possible_end_edge_id,
		kr.target_id AS possible_end_node_id
	FROM graph_starts_and_intermediates gs
		JOIN kg_relationships kr ON kr.source_id = gs.intermediate_node_id	 
)
SELECT 
	gsepe.*
FROM graph_second_edges_and_possible_ends gsepe
WHERE NOT EXISTS (
	SELECT 1
	FROM kg_relationships kr 
	WHERE kr.source_id = gsepe.possible_end_node_id 
)
ORDER BY
	gsepe.start_node_id ASC,
	gsepe.intermediate_node_id ASC,
	gsepe.possible_end_node_id ASC
	
	
	
-- Q4: Financial trasactions aggregation
-- Selected groups of similar cardholders
-- All cardholders treated as one entity are aggregated to an array
-- Selected cardholders with total income > 0
BEGIN;

SET LOCAL pg_trgm.similarity_threshold = '0.5';

CREATE TEMP TABLE q4_index_items ON COMMIT DROP AS
SELECT
    ROW_NUMBER() OVER (ORDER BY cardholder) AS id,
    cardholder,
    SUM(amount) AS total_income,
    COUNT(*) AS transactions_count
FROM financial_transactions
WHERE cardholder IS NOT NULL
GROUP BY cardholder
HAVING SUM(amount) > 0;

WITH RECURSIVE edges AS (
    SELECT a.id AS source, b.id AS target
    FROM q4_index_items a
    JOIN q4_index_items b
      ON a.id <> b.id
     AND lower(b.cardholder) % lower(a.cardholder)
),
connections AS (
    SELECT id AS node, id AS group_id
    FROM q4_index_items
    UNION
    SELECT e.target, c.group_id
    FROM connections c
    JOIN edges e ON e.source = c.node
),
groups AS (
    SELECT node, MIN(group_id) AS group_id
    FROM connections
    GROUP BY node
)
SELECT
    ARRAY_AGG(i.cardholder ORDER BY i.cardholder) AS cardholders,
    SUM(i.total_income) AS total_income,
    SUM(i.transactions_count) AS transactions_count
FROM groups g
JOIN q4_index_items i ON i.id = g.node
GROUP BY g.group_id
ORDER BY total_income DESC;

ROLLBACK;



-- Q5: What models were used for parsing files each day
SELECT 
	pf.processed_at_parsed::date AS processing_date,
	ARRAY_AGG(DISTINCT em.model_name),
	count(DISTINCT pf.id)	
FROM provenance_files pf 
	JOIN provenance_file_models pfm ON pfm.file_id = pf.id
	JOIN enum_models em ON em.model_id = pfm.model_id
WHERE pf.processed_at_parsed IS NOT NULL
GROUP BY
	pf.processed_at_parsed::date
ORDER BY processing_date;


-- Q6: All emails where subject, sender and recipients are known
SELECT 
	d.id,
	d.full_text 
FROM documents d 
	JOIN enum_parse_statuses eps ON d.email_fields_status = eps.status_id
WHERE 
	eps.status_id = 1
	AND d.email_fields_parsed ->> 'subject' NOT ILIKE ALL (ARRAY['%REDACTED%', '%\_\_\_\_%']) 
	AND d.email_fields_parsed ->> 'from_field' NOT ILIKE ALL (ARRAY['%REDACTED%', '%\_\_\_\_%']) 
	AND d.email_fields_parsed ->> 'to_field' NOT ILIKE ALL (ARRAY['%REDACTED%', '%\_\_\_\_%']) 
