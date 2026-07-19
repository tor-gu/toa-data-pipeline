# results-consolidator

Merges new result JSONs from `results/unprocessed/` into
`results/consolidated/results.parquet`, then moves the originals to
`results/processed/`.

## Output columns

| Column | Notes |
|---|---|
| `match_id` | |
| `date` | match date |
| `order` | album ids, best first |

The merge is an upsert on `match_id`: re-uploading a match replaces its row rather
than duplicating it. Originals are moved only after the Parquet write succeeds, so an
interrupted run leaves its inputs in place and reprocessing them is safe.

Returns `{"files_processed": <count>, "earliest_date": <min date of the new results>}`.
`earliest_date` is returned so that downstream steps know how far back to go when rescoring. (Dates before `earliest_date` do not have to be rescored.)

The pipeline will use `files_processed: 0` as a signal to short-circuit further processing and jump to the end.
