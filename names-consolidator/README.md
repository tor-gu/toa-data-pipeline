# names-consolidator

Reads every `name_<id>.json` under `names/unprocessed/`, fills in a `short-name`
where the uploaded file doesn't supply one, merges the result into
`names/consolidated/names.parquet`, and moves the originals to `names/processed/`.

The merge is an upsert on `id`: a re-uploaded name replaces its existing row
rather than duplicating it. The move happens after the Parquet write, so an
interrupted run leaves its inputs in `names/unprocessed/` and re-merges them on
the next run.

## Input

`names/unprocessed/name_dc62a2a7130882a4.json`

```json
{
  "id": "dc62a2a7130882a4",
  "artist": "The Cure",
  "album": "Disintegration"
}
```

A `short-name` field may be included to override the generated one.

## Output columns

| Column | Notes |
|---|---|
| `id` | album id |
| `artist`, `album` | display names |
| `short-name` | from the JSON, or generated |

## Short names

Only generated when the JSON has no `short-name` (an empty string counts as
absent). An album title that already fits within `SHORT_NAME_MAX_LEN` is used
as-is; otherwise it is cut at the last word boundary falling in
`SHORT_NAME_MIN_LEN`–`SHORT_NAME_MAX_LEN`, or hard-truncated to the max if there
is no boundary in that range. Both lengths are environment variables.

Because names are merged rather than rebuilt, a short name is fixed once it
lands in the Parquet — changing `SHORT_NAME_MIN_LEN`/`SHORT_NAME_MAX_LEN` only
affects names consolidated after the change. To re-derive them all, copy
`names/processed/` back to `names/unprocessed/` and run the pipeline.

Returns `{"files_processed": <files read this run>, "names_consolidated": <total
rows in the Parquet>}`.
