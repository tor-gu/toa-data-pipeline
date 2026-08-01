# scores-updater

Rescores every result date from `earliest_date` onward and rewrites
`scores/scores.parquet`. Existing scores from that date on are discarded first.

## Input

| Field | Notes |
|---|---|
| `earliest_date` | first date to rescore |
| `rebuild` | optional, defaults to `false`. If `true`, `earliest_date` is ignored and all dates are rescored from an empty starting point. See [Rebuild](../state-machine/README.md#rebuild). |
| `num_executors` | optional, defaults to `1`. How many score Lambda invocations to keep in flight at once. |

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

## Parallelism

By default, the dates are processed sequentially. But if `num_executors` is specified (and > 1), the scoring will be done in parallel.

Currently, the default (AWS) limit is 10, so setting `num_executors` to any value above 10 does not increase performance.
