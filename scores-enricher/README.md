# scores-enricher

Reads `scores/scores.parquet` and writes `scores/enriched_scores.parquet` with four
added columns. The raw scores file is left untouched.

## Added columns

| Column | Notes |
|---|---|
| `rank` | position within the date, best first |
| `is_new` | true on the first date the album was scored |
| `score_delta` | change since the album's previous scored date; null when `is_new` |
| `rank_delta` | places gained since the album's previous scored date; null when `is_new` |

## Sign convention

Numerically lower ranks are 'higher', so `rank_delta` is `old_rank - new_rank`.

## Ties

Consecutive scores within `TIE_TOLERANCE` of each other are treated as tied and share
the average of the positions they span, so ranks — and therefore rank deltas — can be
fractional. Two albums tied at the top are both rank 1.5.
