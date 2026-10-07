# Full-text search index comparison

## Setup and query

The expectation is that an FTS index avoids scanning every search vector, with GIN particularly suitable for lexeme lookup. This searches English lexemes, rather than literal substrings.

Environment: PostgreSQL 18.6 on x86-64 Linux in the project's Docker setup; psycopg client (project pin: 3.3.5). `pgcrypto` supplies `digest`; its extension version was not recorded. Basic settings: `shared_buffers = 128MB`, `work_mem = 4MB`, `maintenance_work_mem = 64MB`, two parallel workers per gather, JIT enabled.

Exact measured SQL and parameters:

```sql
WITH selected_ids AS (
    WITH params AS (
        SELECT plainto_tsquery('english', 'air') AS query
    )
    SELECT DISTINCT dc.id
    FROM params AS p
    CROSS JOIN LATERAL (
        SELECT d.id AS id
        FROM documents AS d
        WHERE d.full_text_searchvec @@ p.query
        UNION ALL
        SELECT c.document_id AS id
        FROM chunks AS c
        WHERE c.content_searchvec @@ p.query
    ) AS dc
    ORDER BY dc.id ASC
)
SELECT
    digest(string_agg(si.id::TEXT, ', ' ORDER BY si.id), 'sha256')::TEXT AS hash,
    count(*) AS count
FROM selected_ids AS si;
```

Tested index definitions, using the default `tsvector_ops` operator class:

```sql
CREATE INDEX idx_documents_full_text_searchvec_gin ON public.documents USING gin (full_text_searchvec);
CREATE INDEX idx_chunks_content_searchvec_gin ON public.chunks USING gin (content_searchvec);

CREATE INDEX idx_documents_full_text_searchvec_gist ON public.documents USING gist (full_text_searchvec);
CREATE INDEX idx_chunks_content_searchvec_gist ON public.chunks USING gist (content_searchvec);
```

## Method and results

Each variant has one warm-up and three timed repetitions, using the same SQL, data, parameters, and client. `perf_counter` measures submission through retrieval of the hash/count row, including the client round trip, without rendering or exporting results. Index creation is excluded. Variants run in order: no index, GIN, GiST, without clearing caches.

Both tables are locked throughout, preventing concurrent import into them. PK, UNIQUE, and FK constraints remain active. The planner is not forced, and index changes roll back after each variant.

| Variant | Run 1 (ms) | Run 2 (ms) | Run 3 (ms) | Mean (ms) | Median (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| No FTS index | 39,604.780 | 39,474.226 | 39,463.446 | 39,514.151 | 39,474.226 |
| GIN | 193.690 | 183.205 | 184.770 | 187.222 | 184.770 |
| GiST | 24,829.655 | 24,615.453 | 25,330.413 | 24,925.174 | 24,829.655 |

Every warm-up and measured run returned **36,057 distinct document IDs** and the same SHA-256 digest:

`fe5e91e946573a5d901af37cc28744b38816cc47644ef50741a771c80691b5c9`

## Plans, space, and interpretation

The JSON saves `EXPLAIN (FORMAT JSON)` for every variant. These are estimated plans, without execution statistics.

| Variant | Access method | Deduplication and ordering |
| --- | --- | --- |
| No FTS index | Parallel sequential scans of both tables, filtering with `@@` | Sort, Unique, Gather Merge |
| GIN | Bitmap Index Scan on each GIN index, then parallel Bitmap Heap Scan | Hash aggregation, Sort, Gather Merge, Unique |
| GiST | Bitmap Index Scan on each GiST index, then parallel Bitmap Heap Scan | Hash aggregation, Sort, Gather Merge, Unique |

Sizes cover only the tested FTS indexes (`pg_relation_size`), excluding PK and UNIQUE indexes. One MiB is 1,048,576 bytes.

| Variant | Documents index (bytes) | Chunks index (bytes) | Total (MiB) |
| --- | ---: | ---: | ---: |
| No FTS index | 0 | 0 | 0.00 |
| GIN | 967,983,104 | 1,311,326,208 | 2,173.72 |
| GiST | 517,971,968 | 754,761,728 | 1,213.77 |

GIN's median is **213.64 times faster** than the baseline; GiST's is **1.59 times faster**. GIN maps lexemes to matching rows. GiST uses lossy signatures, which can produce false candidates requiring heap rechecks. This offers a plausible explanation for GiST's slower result, but the estimated plans do not measure rejected candidates. Both index types preserve exact query results.
GIN is the better search choice for this query and dataset, using approximately 960 MiB more space than GiST. Both types also require index maintenance on inserts and updates.

## Insertion cost

The exact insertion in the saved evidence uses `chunks.id = 100000000`:

```sql
INSERT INTO chunks (
    id, document_id, chunk_index, token_count, char_start, char_end,
    content, content_searchvec
) VALUES (
    100000000, 1, 1000000, 0, 0, 0,
    'Some text chunk', to_tsvector('english', 'Some text chunk')
);
```

Each variant has one warm-up and three timed insertions. Each attempt rolls back; preparation, rollback, and commit cost are excluded. The saved insertion plans show `Insert on chunks` over a `Result` node.

| Variant | Run 1 (ms) | Run 2 (ms) | Run 3 (ms) | Mean (ms) | Median (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| No FTS index | 0.326 | 1.307 | 0.458 | 0.697 | 0.458 |
| GIN | 0.309 | 0.222 | 0.335 | 0.288 | 0.309 |
| GiST | 0.339 | 0.448 | 0.246 | 0.344 | 0.339 |

