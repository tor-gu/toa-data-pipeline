# scores-updater

Rescores every result date from `earliest_date` onward and rewrites
`scores/scores.parquet`. Existing scores from that date on are discarded first.

## Input

| Field | Notes |
|---|---|
| `earliest_date` | first date to rescore |
| `rebuild` | optional, defaults to `false`. If `true`, `earliest_date` is ignored and all dates are rescored from an empty starting point. See [Rebuild](../state-machine/README.md#rebuild). |

## Output columns

| Column | Notes |
|---|---|
| `id` | album id |
| `score`, `robustness` | from the score Lambda |
| `date` | the date scored |

Each date is fitted from scratch over every match up to and including it. A match
added at one date therefore changes that date and every later one, which is why the
rescore covers a range rather than just the new dates.

Rankings are expanded into adjacent pairs only — a five-album match yields four
pairwise results, not ten.

The fitting itself is done by the separate score Lambda, one invocation per date,
with `SD` and `UNIT_WIN_PROB` passed through.
