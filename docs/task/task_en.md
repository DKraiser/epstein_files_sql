# **Z1: From Hugging Face to Your Own PostgreSQL Database** 
|**Condition**|**Rule**|
|---|---|
|Format|Individual solution and brief individual presentation.|
|Grading|15 points: 12 points for the core and 3 points for one required extension.|
|Z1 Deadline|By the end of the 4th week of classes, before Lecture 5. The exact date and time are listed in the assignment on <br>Teams.|
|Midterm Check C1|After Exercise 2, before Lecture 3; 2 points separately, not counted toward the 15 points for Z1.|
|AI|Allowed. You are responsible for the correctness of your solution and its explanation.|



## **1. What You Need to Do**

Download the specified dataset from Hugging Face on your own, explore it, design your own relational schema, and program the transformation and import into PostgreSQL. Implement search and analytical queries on the imported data, select indexes, and verify their impact on query performance. Finally, complete one extension as described in Chapter 9.

The result is not just a database containing rows. You will submit a reproducible procedure and evidence clearly demonstrating why you modeled and processed the data in this particular way.

**You must create the schema and the importer yourself.** Restoring the school dump, running the importer from the instructor’s solution, or copying a classmate’s database does not meet this requirement. You may use libraries, documentation, and the cited examples. Using different table names for no good reason will not be evaluated; you do not need to forcefully change the source structure.

Do not implement OCR, new entity recognition, web scraping, or geocoding. Do not create a frontend. The prepared geodata will be used only in the next assignment.



## **2. Data: Fixed Source and Scope**

Use the kabasshouse/epstein-data dataset and exclusively this revision:

`133ef9f0a539fafc270cde8fa8638dc38d89968d`
The list of files for this fixed revision is the starting point for downloading. Do not use the dynamic `main` or `latest` branches.

For the final Z1, download and process all `*-of-*.parquet` files in the following layers:

|**Directory in the repository**|**Files**|**Source lines**|
|---|---|---|
|`data/documents/`|15|1,424,673|
|`data/chunks/`|11|2,193,090|
|`data/entities/`|18|10,629,198|
|`data/persons/`|1|1,614|
|`data/kg_entities/`|1|467|
|`data/kg_relationships/`|1|2,198|
|`data/derived_events/`|1|3,038|
|`data/event_participants/`|1|5,751|
|`data/event_sources/`|1|21,910|
|`data/financial_transactions/`|1|49,770|
|`data/curated_docs/`|1|5,766|
|`data/provenance/runs/`|1|123|
|`data/provenance/files/`|3|1,387,775|

In total, there are **56 Parquet files, approximately 1.45 GB of compressed input**. The database, indexes, decompressed text, and working files take up additional space. The download size is not the same as the database size, and you do not need to artificially inflate it to 20 GB.

The source also contains parallel exports without `-of-`, such as `persons-00000.parquet`. Do not add these to Z1. Uncontrolled loading of all `*.parquet` files may result in duplicate data. Embeddings, the audit log, and other layers not listed are not required inputs. Also include the source `README.md`, `LICENSE`, and `PROVENANCE.md` files from the same revision.

Automate and document the download process. You can use, for example, `huggingface_hub` or `hf download`; the official guide explains how to select the revision and files. After downloading, the import must be able to run offline. If a specific revision is not available, contact the instructor; do not modify the dataset arbitrarily.

### **Data Meaning and Uncertainty**

A document, a text chunk, an extracted mention, and a verified identity are different objects. The `entities` layer contains extracted mentions, not automatically verified individuals. The same name does not necessarily refer to the same person. An occurrence in a document or a shared document does not prove a personal relationship, a meeting, or unlawful conduct.

Keep the source files unaltered. The dataset may contain sensitive or disturbing content; for technical verification, use IDs, metadata, and aggregates whenever possible. Do not upload full documents, the dataset, passwords, or tokens to a public Git repository or public AI services. Share only the necessary small pieces of evidence within the scope of the course.



## **3. Procedure During the Semester**

|**When**|**What You Need to Do**|
|---|---|
|Exercise 1|Start PostgreSQL, connect, explore the two source files, and, depending on the time, run the <br>importer. A completed import is not required.|
|Exercise 2|Complete a small custom import, checks, one FTS query, and a GIN query. After the exercise, submit C1<br>according to Chapter 4.|
|Week 3|This exercise focuses on PostGIS. In Z1, independently extend the import to cover the entire input and prepare your own<br>queries.|
|Week 4|Complete the checks, indexes, one basic comparison, and an extension; submit Z1 by the end of the week<br>. The exercise continues to cover PostGIS and C2.|
|Exercises 5–6|Using the database you have already submitted, learn detailed planning and optimization for the performance section of <br>Z2. Z1 is not submitted a second time.|

Each exercise follows the lecture with the same number. C1 and Z1 are milestones of the same solution, not two independent projects. Continue to develop the scripts and the diagram.



## **4. Checkpoint C1: Small Import, FTS, and One GIN**

**This chapter is due only after Exercise 2. It is not a list of tasks to be completed by the end of the first exercise.** The maximum score is 2 points; the exact submission deadline is in Teams.

### **Shared Sample**

For C1, these two files from the revision specified in Chapter 2 are sufficient; together they are approximately 75 MB:

- `data/documents/documents-00000-of-00015.parquet`
- `data/chunks/chunks-00000-of-00011.parquet`

Use your own script to create the `c1-sample-v1` sample:

1. Select 1,000 rows with the lowest numeric `id` from the document file listed above; use an explicit sort.

2. From the chunk file provided, select all chunks whose `document_id` belongs to these documents.

3. Import them into your own document/chunk model. We expect 1,000 documents and 160 chunks that refer to 157 different documents. The source document IDs range from 1 to 1,000.

This does not include all chunks of these documents in the entire source. A document without a chunk in this sample does not necessarily mean the document has no text. Do not select 1,000 random chunks, and do not use the sample to draw conclusions about the performance of a large dataset.

For documents, preserve the source ID, `file_key`, dataset, and type. For chunks, preserve the source ID, document reference, order, and text. Table names are up to you. Create PK/UNIQUE and validated FK for chunks and documents. Verify counts, duplicates, and orphaned references. Repeated runs must not unintentionally duplicate data; a clean rebuild of your own schema is also permitted.

### **Search**

Implement this predicate on the imported chunks, adapted to the names in your schema:

```sql
to_tsvector(‘english’, coalesce(content, ‘’)) 
    @@ plainto_tsquery(‘english’, air’)
```

The output consists of `(chunk_id, document_id)` tuples, sorted by `chunk_id`, without `LIMIT` and without merging multiple chunks of a single document.

1. Run the query without an auxiliary FTS index and save the entire small result set.

2. Create a single GIN index compatible with the query on the physical table.

3. Repeat the query and compare all result tuples, their count, and their order.

4. Save the basic `EXPLAIN` before/after, the index definition, and the index size. Simply name the scan and any sorting, without analyzing cost, loops, or BUFFERS.

5. For the separate literals `air`, `airs`, and `airport`, compare the FTS with `ILIKE ‘%air%’` and explain the difference in meaning.

A zero result on the sample may be correct; the literals will check both the positive and negative cases. A sequential scan is permissible. You do not need to achieve a speedup; do not force the use of an index, and do not add artificial copies of rows. PK/UNIQUE/FK remain active.

### **Explanation and Submission for C1**

In `C1/run.md`, describe the procedure, provide a brief mapping of IDs and fields, and include four query lines: an exact lookup by `file_key`, a substring query, a JSONB containment query, and a time range query in an append-only log. For each, specify the operator, the appropriate index (or “no index”), and one risk. Do not implement the other four indexes or the log table.

Include a manifest of two files with the repository/revision, paths, and SHA-256 hashes; your own DDL/importer; test and query SQL; small results; and basic plans. In `run.md`, briefly verify one AI claim; if you do not use AI, the instructor will provide a claim for verification. A comprehensive report, a complete ER diagram, ten runs, or p50/p95 metrics are not required for C1.

During your defense, explain your own solution and one related mechanism from the first lecture. A separate benchmark for JOINs or TOAST is not required.

|**Area C1**|**Points**|
|---|---|
|Custom import, ID mapping, and integrity|0.5|
|Correct FTS and distinction from substring|0.5|
|Compatible GIN, consistent result, and basic overview of the approach|0.5|
|Operator/index, internal mechanism, and trade-offs|0.5|



## **5. Final Core: Environment, Profiling, and Import**

The following sections belong to the final Z1. Remove the small C1 filter during a full import; do not include the sample a second time.

### **Reproducibility**

Use PostgreSQL in a container or an equally reproducible environment. Specify the versions of the server, extensions, and libraries. Include the configuration or exact installation procedure. The download, transformation, import, and validation must be reproducible using commands or scripts starting from an empty working database, even offline using the provided input.

In `source-manifest.json`, record the repo ID, full commit SHA, download time, and version of the download tool. For each of the 56 files, specify the path, byte count, SHA-256 calculated from the content, and number of lines. Verify the completeness of the shards and their consistency with the manifest before importing.

### **Profiling**

In `data-profile.md`, document the source schema, counts, NULL/empty values, candidate keys, duplicates, and invalid references for at least documents, entities, event_sources, financial_transactions, and provenance/files. Determine the results using your own scripts. You can use DuckDB, Polars, or PyArrow to work with Parquet; the target remains PostgreSQL.

### **Import and Errors**

- Use batch processing or streaming; if necessary, justify a different memory management approach. The entire text corpus does not need to be in RAM at once.

- Maintain traceability: source layer/file and original ID or row position.

- Log incorrect dates, JSON, sums, or references in the error log or quarantine. Do not confuse an error with a missing value, and do not silently discard data.

- For each layer, verify that `N_read = N_accepted + N_quarantined + N_duplicate`. The categories do not overlap, and duplicates must be justified. Report the number of target rows after normalization separately.

- Demonstrate safe repeatability: an idempotent import or a documented rebuild of your own working schema. Also explain the procedure in case of interruption.

- At the end, automatically verify keys, foreign keys, counts, and consistency with the source. The script running to completion without exceptions is not sufficient proof.

- Log your own import runs separately from the upstream `provenance/runs`; these are distinct processes.



## **6. Final Core: Custom Schema and Integrity**

The model must cover the meaning of all 13 layers from Chapter 2. You choose the names and number of target tables. Justify the table boundaries, normalization or denormalization, data types, keys, and the use of JSONB. A single generic JSONB column without a relational model is not sufficient. However, splitting a suitable table solely for the sake of differentiation is not required.

Submit an ER diagram or an equally readable description of the model and `data-mapping.md`:

```
source layer/field | target table/field | conversion and type
NULL/error | key/relationship | reason for decision
```

Describe each field used; list unused fields and explain why. Mandatory queries must not lose necessary data just to simplify the import. The original files remain intact.

You must resolve and explain the following:

1. Original ID and its namespace versus custom surrogate ID. Maintain a one-to-one mapping during renumbering; import order is not a stable identifier.

2. Preserve the source `entities.document_id` as `raw_document_id` or its equivalent. Define nullable foreign keys to documents separately; the same column name does not imply the same namespace.

3. For dates, distinguish between missing data, conversion errors, and unspecified precision. Do not invent a specific day or time zone.

4. For `documents.email_fields`, distinguish between the original notation, JSONB, SQL NULL, JSON null, a missing key, and invalid JSON. Automatic casting without error handling is insufficient.

5. For amounts, preserve the available precision, sign, and currency. An unknown amount is not zero; do not add different currencies without a rule.

6. Preserve the original text of the entry. Label your own normalization with a rule/version; a normalized string is not a verified identity.

### **Foreign Keys Are Mandatory**

Foreign keys must be explicitly declared using `FOREIGN KEY` / `REFERENCES`, active, and validated against the final data. A name like `*_id`, a line in a diagram, or a check performed only within the application is not sufficient.

At a minimum, ensure the following logical relationships in your schema names:

- a chunk to a document;

- both the source and target entities of a KG relationship to a KG entity;

- an event participant to an event;

- an event source to an event.

Also add FKs for other actual references, including mapping tables. For each relationship, justify whether it is required or optional and describe its behavior when the parent is modified or deleted.

**Invalid inputs are not a reason to remove the FK from the entire model.** For an unresolved relationship, retain the original value and the explicit status; the target ID may be NULL, but a non-null value must have an FK. Explain specifically why `event_sources.file_key` does not have to be a valid reference to a document and why a participant’s name cannot automatically be considered a `person_id`.

### **Matching Confidence**

When matching, we recommend logging `match_method`, `match_status`, source/target, justification, and `match_confidence`. Confidence is associated with a specific match; if you store it, use `CHECK` for the range 0–1 and NULL for unspecified confidence. A similarity score of 0.95 does not automatically imply a 95% probability of correct identity. The FK verifies the existence of the target, not the factual correctness of the match. Neither an advanced resolver nor a numerical confidence score is an additional requirement of the core; the resolver can be set to R1.

### **Minimum Automated Tests**

Using separate synthetic examples, verify an invalid date, invalid JSON versus a missing value, a nonexistent document reference, and duplicate record processing. Also verify that the database rejects an invalid non-zero FK. Do not insert test data into the frozen corpus. The instructor must be able to trace the target and the transformation from the source ID.



## **7. Final Core: Queries and Indexes**

Implement at least six queries. For each one, specify the query, tables, parameters, output columns, sorting/duplicate handling rule, and the reason for sensitivity to the model or index. Choose your own parameters based on the data, record them, and do not change them between the compared variants.

|**Query**|**Desired Result**|
|---|---|
|Q1: Full-text|Search for documents or chunks. You may extend the C1 query `flight` to the entire input.<br>The result must include the source ID.|
|Q2: Fuzzy search|Find similar names or identifiers; provide the input, similarity threshold/method,<br>score, and ID. Do not present similarity as confirmation of identity.|
|Q3: Relational 2-hop|In a relationally stored graph layer, find paths consisting of exactly two edges. Return the start,<br>intermediate node, end, and identities of both edges. Determine the direction and repetition rule for edges/nodes;<br>do not confuse paths with unique ends. Neither SQL/PGQ nor Neo4j is required in Z1.|
|Q4: Financial Analysis|Implement aggregation of financial records, for example, by currency and merchant<br>or period. Also return the number of records and distinguish between missing and invalid amounts.|
|Q5: Provenance|Determine a specific processing characteristic, such as repeated file processing<br>or run success rates. Specify the unit of measurement; do not pass off an upstream run as<br>your own import.|
|Q6: Custom Question|Choose another meaningful analytical question and justify it. For document<br>metadata, you can use a JSONB filter and explain its significance.|

You must be able to demonstrate the JSONB processing from Chapter 6 using a query, such as a filter in Q1 or Q6; it does not have to be the seventh independent query. A small KG is suitable for proving the correctness of Q3, but not necessarily for demonstrating the performance of a large graph.

Design and implement indexes that meet the following requirements: B-tree, composite index, GIN for FTS or trigrams, and an index of your choice. For each, provide the DDL, query and operator, key/opclass order, size, and the cost of insertion or import. If a single index satisfies multiple listed properties, explicitly justify this choice; What is important is a justified set of indexes for the workload, not the unnecessary duplication of indexes.



## **8. Final Core: One Basic Index Comparison**

Select **one of the queries Q1–Q6** and compare its performance before and after creating a single justified auxiliary index. Use the full prescribed input for the relevant layers, not the small sample C1. The other queries must be functional but do not need to have their own benchmark.

1. Record your expectations, the exact query and parameters, the index DDL, PostgreSQL versions/extensions, row counts, and basic environment parameters.

2. Use the same data, SQL, and parameters in both variants. Change only the auxiliary index under investigation. Keep PK, UNIQUE, and FK constraints active; do not force the execution plan and do not create artificial copies of the data.

3. Verify the consistency of the entire result, including row identities and the number of occurrences, not just `count(*)`. Use a sorted export or a deterministic hash with the specified format. When using LIMIT or ranking, also specify the order in case of tied scores.

4. For each variant, perform one warm-up run and **three timed repetitions**. Using the same client, measure the time from submission to the retrieval of the last row, without rendering or writing the export. Do not run an import concurrently. Report all times and the median.

5. Save the basic pre- and post-`EXPLAIN`, the index definition, and the index size. Simply describe the method of data access and any sorting; a detailed analysis of metrics is not required.

6. Briefly explain the observed difference, the benefit of the index for the selected operator, and its write and space costs. Do not draw general conclusions about production performance based on three repetitions.

This is a simple warm comparison. Do not clear the OS cache, and there is no need to restart the database. Correct non-acceleration or a Seq Scan are not automatically considered errors; the order of notebooks based on speed is not evaluated. The results should be included in `benchmark.md` and in the sections for queries and indexes.

**A detailed analysis of execution plans is not required for Z1.** The three performance experiments, ten runs, p95, and the mandatory `EXPLAIN (ANALYZE, BUFFERS, SETTINGS)` do not belong in Z1. We will cover cardinality estimates, loops, buffers, and optimization in lectures/sections 5–6 and verify them in the performance section of Z2. The submitted Z1 archive remains unchanged, but you will continue to use the database and your own scripts. There is no second submission or additional graded section for Z1.



## **9. One Required Extension Worth 3 Points**

Choose **one** option. Describe the implementation, demonstration, verification, and decisions in `extension.md`. Do not include all options just to cover a wide range of technologies.

### **R1: Unresolved Link Resolver**

Implement a solution for at least one of the following scenarios: a participant linked to a person, an event source linked to a document, or a report of unresolved links. Store the input, candidates/accepted match, method, and status; distinguish between automatic and manual confirmation. In the tests, demonstrate success, failure, and ambiguity, and explain the risk of an incorrect link.

### **R2: Materialized View or Reporting Layer**

Implement a derived model for a specific analytical query, such as a timeline or the aggregation of documents or transactions. Compare the direct calculation with the derived result, demonstrate refresh capabilities, and explain the cost of updates and stale data. Distinguish between a regular VIEW and a materialized result.

### **R3: Search as an Application Feature**

Create an SQL interface or endpoint that combines full-text search, fuzzy matching, ranking, and filtering by type, dataset, or date. Demonstrate the ranking order and relevant edge cases. Justify the ranking and explain how it differs from a substring search. If the query has the same meaning, changing the index alone must not alter the correct result; a different dictionary, phrase, or ranking rule may change the query, and this must be acknowledged. A frontend is not required.

### **R4: Operational Provenance Analytics**

Expand the analysis of requests and files to include, for example, success rates, repetitions, or validation errors. Demonstrate how to trace a specific issue. Evaluate costs/latency only where the source provides them; otherwise, identify the missing metrics. Explain the granularity of the record and why a repeated `file_key` may not be a duplicate to be removed.

### **R5: Preparation for the Spatial Layer**

Implement a table of locations and a relationship model prepared for the later import of geodata. Each relationship has exactly one entity and a separate, optional source document as its provenance. Create the appropriate foreign keys and integrity checks. Justify the future spatial type, CRS, and index as opposed to plain text or a lat/lon pair. You do not need custom geocoding or the entire geo package; label the test data and separate it from the source.



## **10. AI Report and Defense**

In `ai-report.md`, specify the tool/model, date, and purpose of use; provide representative prompts and relevant claims; and list the parts that were adopted or corrected, along with your own decisions. You do not need to submit every chat, but it must be clear how you verified important recommendations.

#### Use a short table:

```
claim | risk/assumption | test or primary source
observed result | accepted, corrected, or rejected
```

Refute or substantially clarify at least one technical claim. If you do not use AI, state so and verify the claim provided by the instructor. Whether or not you use AI does not, in itself, affect your score.

In your brief presentation, you will demonstrate the origin and transformation of the selected record, explain the model and indexes, describe the basic method of accessing the data, and respond to a change in a parameter. The question may intentionally contain an incorrect assumption; your task is not to agree with it.



## **11. What to Submit to Teams**

Submit a single ZIP file containing the source project and the author’s identification. If you are working in Git, include the commit for the submitted version in the README; a link to the repository alone does not constitute a valid submission. Archive name: `Z1_last_name_first_name.zip`.

|**Artifact**|**Contents**|
|---|---|
|`README.md`|Author, versions, configuration, sequence of commands from download to benchmark, offline<br>replay.|
|Download and manifest|Custom download step and `source-manifest.json` for the entire scope.|
|`data-profile.md`|Findings from the source and scripts to reproduce them.|
|`data-mapping.md` and model|Source-to-target mapping, types, rules, and ER diagram or equivalent.|
|DDL and importer|`schema.sql` or migrations, custom transformation, and record of import requirements.|
|Tests and `import-report.md`|Integrity checks, row counting, errors, and proof of reproducibility.|
|`queries.sql`|Q1–Q6, selected parameters, and explanation of their significance.|
|`benchmark.md` and evidence|One query before/after indexing, basic EXPLAIN, three times and the median for each variant, <br>result verification, and conclusion.|
|`ai-report.md`|AI claims, their verification, and custom decisions.|
|`extension.md` and <br>implementation|Selected R1–R5, working demo, testing, and limitations.|

You may adapt the names of the helper scripts to your language, but be sure to explain their purpose. Do not include the dataset, dump, `.env` file with passwords, virtual environment, dependencies, or cache in the ZIP file. Include small sample outputs and plans; your script must be able to generate large result exports without you having to submit them in their entirety.

Submit C1 as a separate item in Teams as `C1_lastname_firstname.zip`, containing a small C1 directory and the necessary scripts for the current version of the same project. Its scope is defined by Chapter 4, not the entire list of final Z1 artifacts.



## **12. Z1 Scoring**

|**Area**|**Points**|**What You Demonstrate**|
|---|---|---|
|Data Acquisition, Environment, and ETL|3|0.5 download/manifest, 0.5 reproducibility/offline, 2 custom ETL,<br>row accounting, validation, and secure repetition. |
|Model, mapping, and integrity|4|2 schema, types, and mapping; 1 validated foreign key and integrity tests; 1 data origin<br>and uncertainty documentation.|
|Queries and indexes|3|1 correct queries; 1 justified indexes and costs; 1 basic <br>before/after comparison with preserved results.|
|AI Audit and Justification|2|Verification of recommendations and independent understanding of the solution.|
|One Mandatory Extension|3|1 technical correctness, 1 demonstrated benefit, 1 justification of the decision and<br>limits.|
|Total Z1|15|C1 is evaluated separately, with a maximum of 2 points.|

Partial points are awarded for areas where you have demonstrated understanding. An error in one area does not automatically nullify the others; during the defense, points are adjusted for the areas being evaluated. A functional output alone, without an understanding of the underlying concepts, is not enough to earn full points. The number of lines of code, the aesthetics of the SQL, or whether your laptop was the fastest are not evaluated.