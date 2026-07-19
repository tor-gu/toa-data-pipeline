# names-consolidator

Reads every `name_<id>.json` under `names/unprocessed/`, fills in a `short-name`
where the uploaded file doesn't supply one, and writes
`names/consolidated/names.parquet`.

Input files are never moved, so `names/unprocessed/` accumulates and is re-read in
full on every run — the Parquet is rebuilt from scratch rather than merged into.

## Output columns

| Column | Notes |
|---|---|
| `id` | album id |
| `artist`, `album` | display names |
| `short-name` | from the JSON, or generated |

## Short names

Only generated when the JSON has no `short-name`. An album title that already fits
within `SHORT_NAME_MAX_LEN` is used as-is; otherwise it is cut at the last word
boundary falling in `SHORT_NAME_MIN_LEN`–`SHORT_NAME_MAX_LEN`, or hard-truncated to
the max if there is no boundary in that range. Both lengths are environment variables.

Returns `{"names_consolidated": <count>}`.
