# results-consolidator

Maintains three Parquet files, and moves the JSONs it consumed into their
`processed/` prefixes:

| File | Notes |
|---|---|
| `results/consolidated/unredacted_results.parquet` | Built incrementally |
| `redactions/consolidated/redactions.parquet` | Built incrementally |
| `results/consolidated/results.parquet` | Full rebuild from `unredacted_results` and `redactions` |

`results.parquet` keeps the name and key it always had, so downstream steps are
unchanged — they read the redacted view without knowing redactions exist.

## Inputs

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

`redactions/unprocessed/redaction_9ff7cc73d40f220a.json`, is a copy of the album's name record:

```json
{
  "id": "9ff7cc73d40f220a",
  "artist": "The Cranberries",
  "album": "Everybody Else Is Doing It"
}
```

## Output columns

`results.parquet` and `unredacted_results.parquet`:

| Column | Notes |
|---|---|
| `match_id` | |
| `date` | match date |
| `order` | album ids, best first |

`redactions.parquet`: `id`, `artist`, `album`.

## The redaction rule

Redacted album ids are stripped out of each `order` list. A match keeps the
comparisons among its surviving albums, so redacting one album out of five
leaves a four-album match. A match left with fewer than two albums is dropped
entirely.

Because `results.parquet` is rebuilt from scratch against redactions, the 
rule is applied uniformly on every run.

## Return value

```json
{
  "files_processed": 2,
  "redactions_processed": 3,
  "earliest_date": "2024-03-02"
}
```

`redactions_processed` counts album slots actually removed from the results (e.g. an album that played in three matches contributes 3)

`earliest_date` tells downstream steps how far back to rescore, and is the earlier of two things:

- the minimum date among the newly uploaded results, and
- the earliest date on which a newly redacted album appeared in the unredacted
  results

It is `null` when nothing was processed.

## Ordering and idempotence

All three Parquet writes happen before any original is moved, so an interrupted run leaves its inputs in `unprocessed/` and reprocessing them is safe.
