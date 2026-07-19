# viz-builder

Reads the consolidated results and the enriched scores and writes the score-history dataset the viz page animates.

## Outputs

| File | Content |
|---|---|
| `viz/dates.parquet` | the date axis |
| `viz/albums.parquet` | `id`, `debut`, `scores`, `match_ids` per album |
| `viz/matches.parquet` | `match_id`, `date`, `order` |

The data covers only the largest connected component of the match graph, which is the first thing this lambda needs to compute.

This dataset is shaped exactly for the viz component to consume. Some peculiarities of this set to note:
- The date axis starts with a synthetic pre-season date, the day before the first real one, so that playback can begin before the first match.
- Each album's `scores` covers every date on the axis, zero-filled before its `debut`. A zero before the debut means unrated, not a score of zero.
- Albums are pre-sorted by debut (and then by id within debut date, for deterministic results)

