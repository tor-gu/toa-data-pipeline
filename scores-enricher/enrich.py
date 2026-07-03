import pandas as pd
from toa.columns import ScoresCol


def _assign_ranks(scores_desc: list[float], tolerance: float) -> list[float]:
    """Assign average ranks to a sorted (descending) list of scores.

    Consecutive scores within `tolerance` of each other form a tied group and
    receive the average of the 1-indexed positions they would have occupied
    individually. E.g. two scores tied at the top → [1.5, 1.5].
    """
    ranks = []
    i = 0
    while i < len(scores_desc):
        j = i + 1
        while j < len(scores_desc) and abs(scores_desc[j] - scores_desc[j - 1]) <= tolerance:
            j += 1
        group_size = j - i
        avg_rank = (i + 1) + (group_size - 1) / 2
        ranks.extend([avg_rank] * group_size)
        i = j
    return ranks


def add_ranks(df: pd.DataFrame, tolerance: float) -> pd.DataFrame:
    """Add a `rank` column. Ranks are computed per date, 1-indexed, with the
    highest score receiving rank 1. Tied groups (adjacent scores within
    `tolerance`) share the average of their individual ranks.
    """
    groups = []
    for _, group in df.groupby(ScoresCol.DATE):
        group = group.sort_values(ScoresCol.SCORE, ascending=False).copy()
        group[ScoresCol.RANK] = _assign_ranks(group[ScoresCol.SCORE].tolist(), tolerance)
        groups.append(group)
    return pd.concat(groups)


def add_is_new(df: pd.DataFrame) -> pd.DataFrame:
    """Add an `is_new` boolean column. True on the first date an album id
    appears in the scores history, False on all subsequent dates.
    """
    df = df.sort_values([ScoresCol.ID, ScoresCol.DATE], ignore_index=True)
    df[ScoresCol.IS_NEW] = ~df.duplicated(subset=[ScoresCol.ID], keep="first")
    return df


def add_score_delta(df: pd.DataFrame) -> pd.DataFrame:
    """Add a `score_delta` column. For each album, the difference between its
    current score and its score on the previous date it was scored. Null for
    albums where `is_new` is True.
    """
    df = df.sort_values([ScoresCol.ID, ScoresCol.DATE], ignore_index=True)
    df[ScoresCol.SCORE_DELTA] = df.groupby(ScoresCol.ID)[ScoresCol.SCORE].diff()
    df.loc[df[ScoresCol.IS_NEW], ScoresCol.SCORE_DELTA] = None
    return df


def enrich(df: pd.DataFrame, tolerance: float) -> pd.DataFrame:
    """Apply all enrichments to a scores DataFrame, adding `rank`, `is_new`,
    and `score_delta` columns.
    """
    df = add_ranks(df, tolerance)
    df = add_is_new(df)
    df = add_score_delta(df)
    return df
