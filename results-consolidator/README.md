# results-consolidator

Merges new result JSONs from `results/unprocessed/` into
`results/consolidated/results.parquet`, then moves the originals to
`results/processed/`.

## Input

`results/unprocessed/result_a3f91c02.json`

```json
{
  "date": "2026-07-19",
  "match_id": "a3f91c02",
  "order": [
    "9ff7cc73d40f220a",
    "dc62a2a7130882a4",
    "3fd99875c7b559a0",
    "cbeb8d217579ba22",
    "0243e321081e55b9"
  ]
}
```

`order` is the full ranking for the match, best first.

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
`earliest_date` is returned so that downstream steps know how far back to go when rescoring. (Dates before `earliest_date` do not have to be rescored.) When there is nothing to
process, `earliest_date` is `null` — the key is always present, because the state machine
binds it into a Lambda payload unconditionally.

The pipeline will use `files_processed: 0` as a signal to short-circuit further processing and jump to the end.
