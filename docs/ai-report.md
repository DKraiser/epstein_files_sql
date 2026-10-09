| Date | Model | Goal of using | Statement | Risk or hypothesis | Test or primary source | Observed result | Approved, fixed or refused |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 09.18.26 | GPT-5.6 Luna | Designing an efficient PostgreSQL schema for documents and chunks. Optimizing data types for PostgreSQL storage and querying. | A hybrid PostgreSQL schema featuring inline text columns and enum tables is simple and efficient option. | Hypothesis: correct schema and datatypes will save memory and provide integrity along the database. Risk: messy or unparseable source strings could cause type-casting failures during direct import. | Sources: README.md and PROVENANCE.md | Generated and fixed `schema.sql` for `documents` and `chunks`, described in `data-mappings.md` | Approved, fixed (column order, datatypes) |
| 09.27.26 | GPT-5.6 Luna | Designing an efficient PostgreSQL schema for the rest of the dataset. Optimizing data types for PostgreSQL storage and querying. | A schema featuring inline text columns, enum tables, advanced postgres datatypes is simple and efficient option. | Hypothesis: correct schema and datatypes will save memory and provide integrity along the database. Risk: messy or unparseable source strings could cause type-casting failures during direct import. Also dataset may contain invalid references, duplicates, that should be handled gracefully. | Sources: README.md and PROVENANCE.md, dataset contents | Generated `schema.sql` for the rest of the database, `data-mapping.md`, `data-profile.md` | Approved, fixed (column order, datatypes, naming) |
| 10.02.26 | GPT-6.1 Sol | Implementing an importer. | Use explicit layer transformations, lookup dictionaries, and separate transactions. | Incorrect parsing, unresolved references, or silently discarded records can be permitted by invalid importer. | [tests.py](/home/oles/Documents/FIIT/Current/DBS2/Task1/src/python/importer/tests.py).| Importer module that makes mistakes in unambigous parsing. `importer-report.md` | Approved, fixed | 
| 10.04.26 | GPT-6.1 Sol | Ensuring repeatability and interruption recovery. | Preserve committed layers, roll back the active layer, recognize existing identical rows as duplicates and quarantine ones with existing id and unique payload. | Earlier checks counted only new rows; repeated imports failed, reimports caused errors. | `DatasetIntegrationTests` and `DatabaseComponentTests`. | Counts corrected to include existing rows/links. Repeated fixture imports preserved table contents; interruption retry passed. | Approved |
| 10.08.26 | GPT-6.1 Sol | Finding bottlenecks and designing indexes. | Broad traversal of small graphs in Q3, fuzzy comparison of cardholder names in Q4, scanning in Q5 and Q6 can be optimized. | Irrelevant and redundant indexes consume server memory and can even lead to a query execution speed decline. | [`ai_confirmation.py`](../ai_confirmation.py): one warm-up and three measured `EXPLAIN ANALYZE` runs per variant; [results](ai_confirmation.md) | Q3 indexes slowed execution. GiST accelerated Q4's temporary-table search; the Q5 composite B-tree and Q6 status B-tree also improved execution. | Approved, fixed (Q4 uses GiST with bidirectional edges and similarity threshold 0.5) |

## Detailed AI statement analysis

Selected AI claim to confirm: Finding bottlenecks and designing indexes.

AI claim: according to the plans provided by postgres, the following operations consume most part of time and can be optimized with indexes: 

| Query | Bottleneck | Possible solution |
| - | - | - |
| Q3 | Repeated joins and existence checks on `kg_relationships.source_id` and `target_id`.	| Composite B-tree on `(source_id, target_id) INCLUDE (id, relationship_type_id)` and a separate B-tree on `(target_id)`. |
| Q4 | Pairwise fuzzy comparisons between aggregated cardholders; scanning transactions for aggregation. | GiST on `lower(cardholder) gist_trgm_ops(siglen=32)` on a temporary table containing the aggregated cardholders, with the join rewritten to use %. Additionally, a covering B-tree on `(cardholder) INCLUDE (amount) WHERE cardholder IS NOT NULL` can accelerate the initial aggregation. |
| Q5 | Reading almost all rows of the wide `provenance_files` table to obtain timestamps and join IDs. | Composite covering B-tree on `(processed_at_parsed, id) WHERE processed_at_parsed IS NOT NULL`. Sorting and aggregation remain additional costs. | 
| Q6 | Scanning the entire `documents` table despite a highly selective email status condition. | B-tree on `(email_fields_status)`. Alternatively, a partial B-tree on `(id)` whose predicate matches the complete Q6 filtering condition. |

Performing a benchmark with different indexes demonstrated following results: 

| Query | No index median time | Execution plan | Index median time | Execution plan |
| --- | --- | --- | --- | --- |
| Q3 | 31.795 ms | Sort; Hash Join; Seq Scan on `kg_relationships`; Hash; Seq Scan on `kg_entities`; Seq Scan on `enum_kg_entity_types`; Seq Scan on `enum_relationship_types` | 36.632 ms | Sort; Hash Join; Nested Loop; Seq Scan on `kg_relationships`; Hash; Index Only Scan on `kg_relationships` using `idx_kg_relationships_target_btree`; Seq Scan on `kg_entities`; Index Only Scan on `kg_relationships` using` idx_kg_relationships_source_target_btree`; Memoize; Seq Scan on `enum_kg_entity_types`; Seq Scan on `enum_relationship_types` |
| Q4 | 209.128 ms | Sort; Recursive Union; Seq Scan on `q4_index_items`; Hash Join; WorkTable Scan; Hash; Nested Loop; Materialize; Aggregate; Subquery Scan; CTE Scan | 18.445 ms | Sort; Recursive Union; Seq Scan on `q4_index_items`; Hash Join; WorkTable Scan; Hash; Nested Loop; Index Scan on `q4_index_items` using `idx_q4_cardholder_gist`; Aggregate; Subquery Scan; CTE Scan |
| Q5 | 1511.826 ms | Aggregate; Gather Merge; Sort; Hash Join; Parallel Hash Join; Parallel Seq Scan on `provenance_file_models`; Parallel Hash; Parallel Seq Scan on `provenance_files`; Hash; Seq Scan on `enum_models` | 1507.417 ms | Aggregate; Gather Merge; Sort; Hash Join; Parallel Hash Join; Parallel Seq Scan on `provenance_file_models`; Parallel Hash; Parallel Index Only Scan on `provenance_files` using `idx_provenance_files_processed_id_btree`; Hash; Seq Scan on `enum_models` |
| Q6 | 476.501 ms | Gather; Nested Loop; Parallel Seq Scan on `documents`; Materialize; Index Only Scan on `enum_parse_statuses` using `enum_parse_statuses_pkey` | 4.385 ms | Nested Loop; Index Only Scan on `enum_parse_statuses` using `enum_parse_statuses_pkey`; Index Scan on `documents` using `idx_documents_email_fields_status_btree` |

The confirmation benchmark for Q3 without secondary indexes demonstrated better results in comparison to the one using proposed graph indexes, so all the proposed indexes were refused. For Q4, GiST reduced the median temporary-table search time by approx. 10 times; aggregation setup (51.420 ms) and index creation (5.581 ms) are excluded. The Q5 composite B-tree reduced the median time by approx. 5-10%, and the Q6 status B-tree reduced it from hundreds of milliseconds to milliseconds. Medians exclude one warm-up and use three measured runs.

| query | insertion table | no index median insert time | index median insert time | 
| --- | --- | ---: | ---: |
| Q3 | `kg_relationships` | 0.868 ms | 0.495 ms |
| Q4 | `q4_index_items` | 0.030 ms | 0.126 ms |
| Q5 | `provenance_files` | 1.043 ms | 0.539 ms |
| Q6 | `documents` | 1.649 ms | 2.147 ms |

Medians exclude one warm-up and use three measured runs.