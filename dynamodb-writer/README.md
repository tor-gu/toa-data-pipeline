# dynamodb-writer

Reads the pipeline's Parquet outputs from S3 and writes them to the five DynamoDB
tables. It runs in one of two modes.

## Modules

`handler.py` is the main function. It decides the mode, reads the inputs, writes, deletes stale rows, clears the sentinel, and logs each step. The work is done in the following modules:

| Module | Holds | I/O |
|---|---|---|
| `transform.py` | item builders (`score_item`, `match_item`, …), `build_names`, `select_since` | none |
| `rewrite.py` | full-rewrite decisions: `rewrite_mode`, the empty-input guard, `stale_keys` | none |
| `inputs.py` | `read_inputs`: the seven Parquet files as one `Inputs` | S3 (awswrangler) |
| `tables.py` | `write_all` and `delete_all_stale`, plus the per-table writes they call | DynamoDB |
| `sentinel.py` | `read_rewrite_sentinel` and the conditional `clear_rewrite_sentinel` | S3 |

The I/O modules take `Table` objects and an S3 client as arguments and don't log, so the
tests drive them with fakes (`tests/dynamodb-writer/test_tables.py`, `test_sentinel.py`).

## Modes

| Mode | When | What it does |
|---|---|---|
| incremental | default | Upserts `scores` and `matches`/`album_matches` rows with `date >= earliest_date`. Never deletes |
| full | `rebuild: true`, **or** the rewrite sentinel is set | Upserts every row, then deletes every row it did not write |

`global_statistics` and `viz` are snapshots and are rewritten in full in both modes.

Incremental writes are upserts, so they do not support things like
redactions.

Full rewrites write every row, and then delete stale rows.

When there is a redaction, the upstream process leave a [rewrite sentinel](#the-rewrite-sentinel) in S3, which triggers a full rewrite.

Deleting comes last so readers never see a gap. `scores` keeps its `METADATA` item because the writer rewrites it.

### Empty-input guard

A full rewrite deletes whatever the inputs lack, so it refuses to start if
`results.parquet` or `enriched_scores.parquet` is empty. A lost Parquet file then fails the run instead of wiping the tables.

## The rewrite sentinel

`flags/dynamodb_rewrite_pending.json` in the data bucket. 

Currently, this is used in only one case: when `results-consolidator` has processed redactions.

The `dyanamodb-writer` reads the sentinel `HEAD` and saves the entity tag
before reading any Parquet file.  

After a full-rewrite, the sentinel is removed -- but only if the entity tag matches. (This guards against a second in-flight redaction processed while we were busy.)

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
| `ranking` | ordered list of `{rank, id, artist, album, short-name, new_score, new_rank, is_new, score_delta, rank_delta}`|
| `gsi_pk` | constant `"MATCH"` |
| `date_match_id` | `"<date>#<match_id>"` — GSI sort key for recency queries |

Note: `rank` is the rank within the match. `new_rank` and `rank_delta` refer to global
rank among all albums.

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

