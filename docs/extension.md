## Chosen Extension

For this task, the R2 extension was selected. A materialized view was created for query Q5, which calculates the daily number of document-processing operations, grouped by the models used.

## Theory

**View** — A view is a named SQL query stored in the database as a database object. It does not persist the query results; instead, the underlying query is executed whenever the view is referenced in a query. Views are useful for encapsulating complex SQL logic and reusing queries without duplicating their definitions.

**Materialized view** — A materialized view is a database object that stores the results of a query. Unlike a regular view, it persists the query results, requiring additional storage space. The stored data is not automatically updated when the underlying tables change. To update the results, the `REFRESH MATERIALIZED VIEW` command must be executed.

## Tests

For all tests presented below, the median execution time was calculated from three warm runs, excluding one initial warm-up run.

### Materialized View Creation and Refresh

| Operation | Median execution time (ms) |
|---|---:|
| Creation | 1826.344 |
| Refresh | 1801.140 |

### Query Execution Performance

The following table compares the execution time of Q5 when executed directly against the underlying tables and when retrieving the results from the materialized view.

| Execution method | Median execution time (ms) |
|---|---:|
| Direct query execution | 1697.245 |
| Materialized view | 0.531 |

### Results and Analysis

The initial creation of the materialized view took 1826.344 ms, approximately 7.61% longer than the direct execution of Q5, which took 1697.245 ms. This additional time can be attributed to the execution of the defining query and the storage of its results in the materialized view.

Refreshing the materialized view took 1801.140 ms. This operation requires re-executing the defining query and updating the stored results, which introduces additional processing and storage overhead.

In contrast, retrieving the results from the materialized view took only 0.531 ms, compared with 1697.245 ms for direct query execution. This represents a substantial reduction in query execution time, as the results are already computed and stored in the database.

Overall, the results demonstrate that a materialized view can significantly improve read performance for queries that are executed frequently and do not require immediately up-to-date results. However, this improvement comes at the cost of additional storage space and the processing time required to refresh the materialized view.