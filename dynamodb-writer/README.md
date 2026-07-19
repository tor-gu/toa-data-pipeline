# dynamodb-writer

Reads the pipeline's Parquet outputs from S3 and writes them to the five DynamoDB
tables. Takes `earliest_date` to write only new/updated records, or `rebuild: true`
to rewrite everything.

## Tables

### `scores` — `id` (hash) + `date` (range), GSI `date-index` on `date`

| Attribute | Notes |
|---|---|
| `id` | album id |
| `date` | scoring date |
| `score`, `robustness`, `rank` | numbers |
| `artist`, `album`, `short-name` | denormalised from names |

Plus a metadata item: `id="METADATA"`, `date="latest_date"`, `value=<latest date>`.

### `matches` — `match_id` (hash), GSI `recent-index` on `gsi_pk` + `date_match_id`

| Attribute | Notes |
|---|---|
| `match_id`, `date` | |
| `ranking` | ordered list of `{rank, id, artist, album, short-name, is_new, score_delta}` |
| `gsi_pk` | constant `"MATCH"` |
| `date_match_id` | `"<date>#<match_id>"` — GSI sort key for recency queries |

### `album_matches` — `album_id` (hash) + `match_id` (range)

| Attribute | Notes |
|---|---|
| `album_id`, `match_id` | keys — index from album → every match it appeared in |
| `date` | match date |
| `artist`, `album`, `short-name` | denormalised from names |

### `global_statistics` — `key` (hash)

One item per statistic.

| Attribute | Notes |
|---|---|
| `key` | one of `earliest_match`, `latest_match`, `min_score`, `max_score`, `num_albums`, `num_matches` |
| `value` | the statistic — string for the match dates, number for the rest |

Always fully rewritten.

### `viz` — `pk` (hash, constant `"VIZ"`) + `sk` (range)

Score-history dataset for the largest connected component. Always fully
rewritten (write-then-delete-stale), never date-filtered.

| `sk` | Attributes |
|---|---|
| `DATES` | `dates` (the date axis), `num_dates`, `num_albums`, `num_matches` |
| `ALBUM#<id>` | `artist`, `album`, `short-name`, `debut` (index of first real score), `scores` (one per date, zero-filled before debut), `match_ids` |
| `MATCH#<date>#<match_id>` | `match_id`, `date`, `ranking` (ordered album ids) |

