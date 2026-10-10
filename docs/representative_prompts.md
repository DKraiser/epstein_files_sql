Using the `schema.sql` and `queries.sql`, find me bottlenecks in query (you can use `EXPLAIN ANALYZE`) and propose me indexes to fix these bottlenecks. Consider only queries 3-6 as 1 and 2 use gin and gin_trgm.

---

# Importer attempt 2

The previous version of your importer seems bad to me, so I want you to try again. I have added some more clarifications and explanations. 

## Steps

Importer works with the following pipeline:

1. Collect datasets and populate the following lookup tables: 
    - `enum_datasets` 
    - `enum_document_types` 
    - `enum_ocr_sources` 
    - `enum_entity_types` 
    - `enum_person_categories` 
    - `enum_kg_entity_types` 
    - `enum_relationship_types` 
    - `enum_event_tracks` 
    - `enum_event_types` 
    - `enum_event_confidences` 
    - `enum_participant_roles`
    - `enum_curated_subjects` 

2. Populate tables referencing only lookup tables;

3. Import the rest of the dataset;

For each imported table:

1. Text, date and json values to parse preserve in `[column_name]_raw`, parsed value in `[column_name]_parsed`, and parsing status in `[column_name]_status`;

2. If column should reference another table, use [import enums](src/python/importer/enums_and_literals.py) where possible or perform the lookup through the dataset. For `document_id` and `file_key` build and use in-memory dictionary in order to fasten the lookup;

## Important clarifications

1. For `provenance/runs.model`, `provenance/files.model_used`, perform parsing through comma-separated values and use linking tables `provenance_run_models` and `provenance_file_models`;

2. To populate `enum_document_types` and match with `documents.document_type` use capitalized values;

3. To parse dates, use [`importer/dates` module](src/python/importer/dates.py) `parse()` function;

4. Do not use `args` lib and cli args at all;

5. Use defined constants from [`shared` module](src/python/shared/)

## Secondary

Importer must:
- Import each layer in a separate transaction;
- Log matching errors, parsing errors etc;
- Not silently discard data;
- Verify `N_read = N_accepted + N_quarantined + N_duplicate` for each layer;
- Provide an idempotency (Demonstrate safe repeatability: an idempotent import or a documented rebuild of your own working schema. Also explain the procedure in case of interruption);
- Verify the integrity with the source, all the foreign keys and counts;

## Rights and restrictions

You are allowed to:
- Create, read and update files inside `src/python/importer`;
- Only create new files in `src/python/shared` or read existing ones;
- Connect to postgres and execute `src/sql/schema.sql` and `src/sql/seed.sql`;
You are forbidden to:
- Modify any other files, inlcuding `src/sql/schema.sql`, `src/sql/seed.sql`, existing files in `src/python/shared` etc;
Module usage
This module should be a package called with `python -m python.importer`. Do not provide extra capability features unless you are not requested to.

## Code quality
Generated code should be well commented, separated into files in a sensible way. 

## Reporting
After implementing the importer and testing it, write a `.md` report based on your decisions and tests into `observations/importer_report.md`

---

# Schema investigation and optimization

Hello, now you can see the `schema.sql` file. 

## Task

For each layer of the dataset:
- Check current table schema and comments in `schema.sql`;
- Investigate original data corresponding to this table (values in columns, their format, size etc);
- Find possible optimizations in datatypes (foreign keys to a new enum, normalizations where it is appropriate etc);
- Edit the `schema.sql`;
- Enter all your findings into `data-profile.md` according to chapter 5 of `docs/task/task_en.md`
- Enter data mapping into `data-mapping.md`

## Remarks

I have started to process `documents` layer manually and `chunks` do not need any further analysis.
