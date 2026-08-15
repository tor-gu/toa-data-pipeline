from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import pandas as pd
from toa.columns import ScoresCol

# How many dates are chained together off a single cold start. We use a fixed
# CHUNK_SIZE so that the results don't vary (because of rounding) on the number
# of executors.
CHUNK_SIZE = 20


def select_dates_to_rescore(
    result_dates: list[str], earliest_date: str | None, rebuild: bool
) -> list[str]:
    """The dates that have to be refitted.

    A match added on one date changes the fit for that date and every later
    one, so the rescore runs from `earliest_date` to the end rather than over
    the new dates alone. A rebuild covers every date and ignores
    `earliest_date`.
    """
    if rebuild:
        return list(result_dates)
    return [d for d in result_dates if d >= earliest_date]


def select_scores_to_keep(
    scores: pd.DataFrame, earliest_date: str | None, rebuild: bool
) -> pd.DataFrame:
    """The existing score rows that survive the update.

    Everything from `earliest_date` on is about to be refitted, so only the
    rows before it are kept. A rebuild keeps nothing.
    """
    if rebuild:
        return scores.iloc[0:0]
    return scores[scores[ScoresCol.DATE] < earliest_date]


def chunk_dates(dates: list[str]) -> list[list[str]]:
    """`dates` split into contiguous runs of at most CHUNK_SIZE, in order.

    Each chunk is fitted as one chain, so the split decides which dates get a
    warm start and which pay for a cold one.
    """
    return [dates[i : i + CHUNK_SIZE] for i in range(0, len(dates), CHUNK_SIZE)]


def score_chunk(
    chunk: list[str], score_one: Callable[[str, list[dict] | None], list[dict]]
) -> list[dict]:
    """The fitted rows for one chunk, flattened, in `chunk` order.

    Consecutive dates are fitted over almost the same matches, so each date
    (except the first one) uses the previous date's scores as the initial value.
    """
    rows: list[dict] = []
    seed = None
    for date in chunk:
        scored = score_one(date, seed)
        seed = [
            {ScoresCol.ID: row[ScoresCol.ID], ScoresCol.SCORE: row[ScoresCol.SCORE]}
            for row in scored
        ]
        rows.extend(scored)
    return rows


def score_dates(
    dates: list[str],
    score_one: Callable[[str, list[dict] | None], list[dict]],
    num_executors: int,
) -> list[dict]:
    """The fitted rows for every date, flattened, in `dates` order.

    The work is divided into chunks, and if num_executors is > 1 the chunks will
    be fitted in parallel. Chaining happens strictly within a chunk, so which
    seed a date gets does not depend on how the chunks are scheduled.
    """
    chunks = chunk_dates(dates)
    if num_executors <= 1:
        return [row for chunk in chunks for row in score_chunk(chunk, score_one)]
    with ThreadPoolExecutor(max_workers=num_executors) as pool:
        scored_chunks = pool.map(lambda chunk: score_chunk(chunk, score_one), chunks)
        return [row for scored in scored_chunks for row in scored]


def assemble_updated_scores(
    scores_to_keep: pd.DataFrame, new_rows: list[dict]
) -> pd.DataFrame:
    """The full scores table to write back: the kept rows plus the newly
    fitted ones.
    """
    if not new_rows:
        return scores_to_keep
    new_df = pd.DataFrame(new_rows)
    if scores_to_keep.empty:
        return new_df
    return pd.concat([scores_to_keep, new_df], ignore_index=True)
