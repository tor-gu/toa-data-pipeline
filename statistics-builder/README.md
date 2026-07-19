# statistics-builder

Reads the consolidated results and the enriched scores and writes a single-row
`statistics/global_statistics.parquet`.

## Statistics

| Field | Notes |
|---|---|
| `earliest_match`, `latest_match` | first and last match dates |
| `min_score`, `max_score` | score range across every album on every date |
| `num_albums` | distinct albums ever scored |
| `num_matches` | distinct matches |

