-- | Table name | Size from 'z1_import' (bytes) | Size from 'z1_import_optimized' (bytes) | Delta (original size - optimized size, bytes) | Became smaller (boolean) |
-- | --- | --- | --- | --- |
-- | 3227140096 |	3227140096 |	0 |	false |
-- | 5767168 |	5693440 |	73728 |	true |
-- | 1114112 |	1114112 |	0 |	false |
-- | 2488287232 |	2478579712 |	9707520 |	true |
-- | 1113907200 |	1113907200 |	0 |	false |
-- | 581632 |	581632 |	0 |	false |
-- | 1974272 |	1916928 |	57344 |	true |
-- | 14016512 |	13557760 |	458752 |	true |
-- | 245760 |	245760 |	0 |	false |
-- | 811008 |	827392 |	-16384 |	false |
-- | 458752 |	458752 |	0 |	false |
-- | 1004388352 |	981499904 |	22888448 |	true |
-- | 90112 |	90112 |	0 |	false |

WITH tables(table_name) AS (
    VALUES
        ('chunks'),
        ('curated_docs'),
        ('derived_events'),
        ('documents'),
        ('entities'),
        ('event_participants'),
        ('event_sources'),
        ('financial_transactions'),
        ('kg_entities'),
        ('kg_relationships'),
        ('persons'),
        ('provenance_files'),
        ('provenance_runs')
),
sizes AS (
    SELECT
        table_name,
        pg_total_relation_size(
            to_regclass(format('%I.%I', 'z1_import', table_name))
        ) AS original_size,
        pg_total_relation_size(
            to_regclass(format('%I.%I', 'z1_import_optimized', table_name))
        ) AS optimized_size
    FROM tables
)
SELECT
    table_name AS "Table name",
    original_size AS "Size from 'z1_import' (bytes)",
    optimized_size AS "Size from 'z1_import_optimized' (bytes)",
    original_size - optimized_size
        AS "Delta (original size - optimized size, bytes)",
    optimized_size < original_size AS "Became smaller (boolean)"
FROM sizes
ORDER BY table_name;