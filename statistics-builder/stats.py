import pandas as pd
from toa.columns import ResultsCol, ScoresCol, StatisticsCol


def compute_stats(results_df: pd.DataFrame, scores_df: pd.DataFrame) -> pd.DataFrame:
    """Compute global summary statistics over the full match/score history."""
    return pd.DataFrame(
        [
            {
                StatisticsCol.EARLIEST_MATCH: results_df[ResultsCol.DATE].min(),
                StatisticsCol.LATEST_MATCH: results_df[ResultsCol.DATE].max(),
                StatisticsCol.MIN_SCORE: scores_df[ScoresCol.SCORE].min(),
                StatisticsCol.MAX_SCORE: scores_df[ScoresCol.SCORE].max(),
                StatisticsCol.NUM_ALBUMS: scores_df[ScoresCol.ID].nunique(),
                StatisticsCol.NUM_MATCHES: results_df[ResultsCol.MATCH_ID].nunique(),
            }
        ]
    )
