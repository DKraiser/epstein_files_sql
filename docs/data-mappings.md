
# Data mapping 

## `documents`

| Dataset field         | Dataset type | Postgres type  | Remarks                           |
| --------------------- | ------------ | ----------     | --------------------------------- |
| `id`                  |  Int64       | BIGSERIAL      |                                   |
| `created_at`          |  String      | TIMESTAMP      |                                   |
| `char_count`          |  String      | INTEGER        |                                   |
| `dataset`             |  String      | SMALLINT       | FK to `datasets` enum table       |
| `document_type`       |  String      | SMALLINT       | FK to `document_types` enum table |
| `ocr_source`          |  String      | SMALLINT       | FK to `ocr_sources` enum table    |
| `is_photo`            |  Boolean     | BOOLEAN        |                                   |
| `has_stamps`          |  Boolean     | BOOLEAN        |                                   |
| `has_handwriting`     |  Boolean     | BOOLEAN        |                                   |
| `file_key`            |  String      | TEXT           |                                   |
| `full_text`           |  String      | TEXT           |                                   |
| `date`                |  String      | TEXT           |                                   |
| `additional_notes`    |  String      | TEXT           |                                   |
| `page_number`         |  Int32       | TEXT           |                                   |
| `document_number`     |  String      | TEXT           |                                   |
| `email_fields`        |  String      | JSONB          |                                   |

## `chunks`

| Dataset field | Dataset type  | Postgres type | Remarks                      |
| ------------- | ------------- | ---------     | ---------------------------- |
| `id`          | Int64         | BIGSERIAL     |                              |
| `document_id` | Int64         | BIGINT        | FK to `documents` enum table |
| `chunk_index` | Int32         | INTEGER       |                              |
| `token_count` | Int32         | INTEGER       |                              |
| `char_start`  | Int32         | INTEGER       |                              |
| `char_end`    | Int32         | INTEGER       |                              |
| `content`     | String        | TEXT          |                              |