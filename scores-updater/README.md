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

## Warm starts

Each date is uses the previous datet's scores as an initial value (passed to the
score Lambda as [`initial_strengths`](https://github.com/tor-gu/toa-lambda-score#payload)).

The dates are split into contiguous chunks of `CHUNK_SIZE`, and chaining happens strictly
within a chunk: each chunk's first date starts cold, and every date after it is seeded by
the one before. Only chunks run concurrently, never the dates inside one, since a chained
fit has to wait for the seed it is given.

Changing the initial value can cause the final score to change slightly. The scores are rounded to three decimal places, so the this difference is usually 0.000, but occasionally is 0.001). For this reason, we use a _fixed_ `CHUNK_SIZE` -- this means that the initial values will be identical for each date, even if rescored with a different number of executors.

## Parallelism

By default, the dates are processed sequentially. But if `num_executors` is specified (and > 1), the scoring will be done in parallel.

Currently, the default (AWS) limit is 10, so setting `num_executors` to any value above 10 does not increase performance.

Because chunks are the unit of parallelism, the effective ceiling is also the number of
chunks — `ceil(dates / CHUNK_SIZE)`. Executors beyond that sit idle.
