import pandas as pd
from stats import compute_stats
from toa.columns import ResultsCol, ScoresCol, StatisticsCol


def make_results_df(rows):
    return pd.DataFrame(
        rows, columns=[ResultsCol.MATCH_ID, ResultsCol.DATE, ResultsCol.ORDER]
    )


def make_scores_df(rows):
    return pd.DataFrame(rows, columns=[ScoresCol.ID, ScoresCol.SCORE, ScoresCol.DATE])


def test_compute_stats_match_dates_and_count():
    results = make_results_df(
        [
            ("m1", "2024-01-01", ["a", "b"]),
            ("m2", "2024-01-05", ["a", "c"]),
            ("m3", "2024-01-03", ["b", "c"]),
        ]
    )
    scores = make_scores_df([("a", 1.0, "2024-01-05"), ("b", 0.5, "2024-01-05")])

    result = compute_stats(results, scores)

    assert result.iloc[0][StatisticsCol.EARLIEST_MATCH] == "2024-01-01"
    assert result.iloc[0][StatisticsCol.LATEST_MATCH] == "2024-01-05"
    assert result.iloc[0][StatisticsCol.NUM_MATCHES] == 3


def test_compute_stats_score_range_over_all_dates():
    results = make_results_df([("m1", "2024-01-01", ["a", "b"])])
    scores = make_scores_df(
        [
            ("a", 2.0, "2024-01-01"),
            ("b", -1.0, "2024-01-01"),
            ("a", 3.5, "2024-01-02"),
            ("b", -0.5, "2024-01-02"),
        ]
    )

    result = compute_stats(results, scores)

    assert result.iloc[0][StatisticsCol.MIN_SCORE] == -1.0
    assert result.iloc[0][StatisticsCol.MAX_SCORE] == 3.5


def test_compute_stats_num_albums_is_distinct_count():
    results = make_results_df([("m1", "2024-01-01", ["a", "b"])])
    scores = make_scores_df(
        [
            ("a", 1.0, "2024-01-01"),
            ("b", 0.5, "2024-01-01"),
            ("a", 1.2, "2024-01-02"),
            ("b", 0.6, "2024-01-02"),
        ]
    )

    result = compute_stats(results, scores)

    assert result.iloc[0][StatisticsCol.NUM_ALBUMS] == 2
