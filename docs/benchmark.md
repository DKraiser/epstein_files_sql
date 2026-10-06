# Full-text search index benchmark

Measured on 2026-10-06T21:35:10.893926+00:00 in schema `public`.

Query: English lexeme search for `air` across documents and chunks, with `UNION` removing duplicate document IDs and ascending ID order.

| Variant | Run 1 (ms) | Run 2 (ms) | Run 3 (ms) | Mean (ms) | Median (ms) | Speedup vs no index |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| No FTS index | 39,290.749 | 38,488.249 | 41,078.384 | 39,619.127 | 39,290.749 | 1.00x |
| GIN | 3,383.209 | 193.734 | 188.306 | 1,255.083 | 193.734 | 31.57x |
| GiST | 44,553.897 | 43,844.164 | 44,140.689 | 44,179.583 | 44,140.689 | 0.90x |

**GIN had the lowest mean execution time in this run.** Every run returned 36,057 document IDs.

## Plans

The complete first-run `EXPLAIN ANALYZE` plan for each variant is saved in `observations/benchmark.json`. Selected scan nodes:

- **No FTS index:** Seq Scan on `documents`; Seq Scan on `chunks`.
- **GIN:** Bitmap Heap Scan on `documents`; Bitmap Index Scan on `idx_documents_full_text_searchvec_gin`; Bitmap Heap Scan on `chunks`; Bitmap Index Scan on `idx_chunks_content_searchvec_gin`.
- **GiST:** Bitmap Heap Scan on `documents`; Bitmap Index Scan on `idx_documents_full_text_searchvec_gist`; Bitmap Heap Scan on `chunks`; Bitmap Index Scan on `idx_chunks_content_searchvec_gist`.

In GiST's first run, heap rechecks rejected 507,449 rows and the bitmap contained 67,941 lossy heap blocks. Signature false positives and bitmap lossiness both increase recheck work. This helps explain why GiST performed poorly for this query and dataset.

GIN's first run took 3,383.209 ms, compared with a 193.734 ms median. This is consistent with cache warming; the experiment does not isolate its effect.

## Why the indexes differ

Without an FTS index, PostgreSQL scans the search vectors and checks the predicate for each row. GIN maps lexemes to matching rows, making it well suited to this unweighted lexeme query. GiST uses lossy signatures: collisions can produce candidate rows that require a heap recheck and are then rejected. Both indexes return exact query results; GiST's lossiness affects work performed, not correctness. GIN bitmap scans can also require rechecks when their bitmap becomes lossy.

## Measurement limits and rerun

Each variant ran exactly three times, with no extra warmup and no cache reset. Variants ran in order: no index, GIN, GiST. Index builds and earlier scans affect cache state, so these results are not controlled cold-cache comparisons. Three samples of one term do not establish performance for every workload.

Times are server execution times from `EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, FORMAT JSON)`. Planning, client transfer, and index creation are excluded; EXPLAIN instrumentation still adds overhead.=

The script analyzes both tables once and retains primary-key and unrelated indexes. It temporarily removes indexes involving the search columns and restores the original indexes using transaction rollback, including on failure. It holds exclusive table locks during the benchmark; run it on an idle database.

From the project root, using the existing `.env` and dependencies:

```bash
src/.venv/bin/python src/python/benchmark.py
```
