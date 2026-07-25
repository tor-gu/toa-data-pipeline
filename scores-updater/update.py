import pandas as pd
from toa.columns import ScoresCol


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
