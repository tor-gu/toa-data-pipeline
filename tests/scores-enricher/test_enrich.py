import math

import pandas as pd
import pytest
from enrich import (
    _assign_ranks,
    add_is_new,
    add_rank_delta,
    add_ranks,
    add_score_delta,
    enrich,
)
from toa.columns import ScoresCol

TOLERANCE = 0.000005


# ── _assign_ranks ──────────────────────────────────────────────────────────────


def test_assign_ranks_no_ties():
    assert _assign_ranks([3.0, 2.0, 1.0], TOLERANCE) == [1.0, 2.0, 3.0]


def test_assign_ranks_two_way_tie_at_top():
    assert _assign_ranks([2.0, 2.0, 1.0], TOLERANCE) == [1.5, 1.5, 3.0]


def test_assign_ranks_three_way_tie():
    assert _assign_ranks([1.0, 1.0, 1.0], TOLERANCE) == [2.0, 2.0, 2.0]


def test_assign_ranks_two_way_tie_at_bottom():
    assert _assign_ranks([3.0, 1.0, 1.0], TOLERANCE) == [1.0, 2.5, 2.5]


def test_assign_ranks_tie_within_tolerance():
    # differ by half tolerance — should be grouped
    scores = [1.0, 1.0 - TOLERANCE / 2]
    result = _assign_ranks(scores, TOLERANCE)
    assert result == [1.5, 1.5]


def test_assign_ranks_just_outside_tolerance():
    scores = [1.0, 1.0 - TOLERANCE * 10]
    result = _assign_ranks(scores, TOLERANCE)
    assert result == [1.0, 2.0]


# ── add_ranks ──────────────────────────────────────────────────────────────────


def make_scores_df(rows):
    return pd.DataFrame(
        rows,
        columns=[ScoresCol.ID, ScoresCol.SCORE, ScoresCol.DATE, ScoresCol.ROBUSTNESS],
    )


def test_add_ranks_basic():
    df = make_scores_df(
        [
            ("a", 2.0, "2024-01-01", 1.0),
            ("b", 1.0, "2024-01-01", 1.0),
        ]
    )
    result = add_ranks(df, TOLERANCE)
    ranks = dict(zip(result[ScoresCol.ID], result[ScoresCol.RANK]))
    assert ranks["a"] == 1.0
    assert ranks["b"] == 2.0


def test_add_ranks_tie():
    df = make_scores_df(
        [
            ("a", 2.0, "2024-01-01", 1.0),
            ("b", 2.0, "2024-01-01", 1.0),
            ("c", 1.0, "2024-01-01", 1.0),
        ]
    )
    result = add_ranks(df, TOLERANCE)
    ranks = dict(zip(result[ScoresCol.ID], result[ScoresCol.RANK]))
    assert ranks["a"] == 1.5
    assert ranks["b"] == 1.5
    assert ranks["c"] == 3.0


def test_add_ranks_per_date():
    df = make_scores_df(
        [
            ("a", 2.0, "2024-01-01", 1.0),
            ("b", 1.0, "2024-01-01", 1.0),
            ("a", 1.0, "2024-01-02", 1.0),
            ("b", 2.0, "2024-01-02", 1.0),
        ]
    )
    result = add_ranks(df, TOLERANCE)
    for _, row in result.iterrows():
        if row[ScoresCol.DATE] == "2024-01-01":
            assert row[ScoresCol.RANK] == (1.0 if row[ScoresCol.ID] == "a" else 2.0)
        else:
            assert row[ScoresCol.RANK] == (2.0 if row[ScoresCol.ID] == "a" else 1.0)


# ── add_is_new ─────────────────────────────────────────────────────────────────


def make_history_df(rows):
    return pd.DataFrame(
        rows,
        columns=[ScoresCol.ID, ScoresCol.SCORE, ScoresCol.DATE, ScoresCol.ROBUSTNESS],
    )


def test_add_is_new_single_album():
    df = make_history_df(
        [
            ("a", 1.0, "2024-01-01", 1.0),
            ("a", 1.5, "2024-01-02", 1.0),
            ("a", 2.0, "2024-01-03", 1.0),
        ]
    )
    result = add_is_new(df)
    is_new = dict(zip(result[ScoresCol.DATE], result[ScoresCol.IS_NEW]))
    assert is_new["2024-01-01"]
    assert not is_new["2024-01-02"]
    assert not is_new["2024-01-03"]


def test_add_is_new_multiple_albums():
    df = make_history_df(
        [
            ("a", 1.0, "2024-01-01", 1.0),
            ("b", 1.0, "2024-01-02", 1.0),
            ("a", 1.5, "2024-01-02", 1.0),
        ]
    )
    result = add_is_new(df)
    result = result.set_index([ScoresCol.ID, ScoresCol.DATE])
    assert result.loc[("a", "2024-01-01"), ScoresCol.IS_NEW]
    assert not result.loc[("a", "2024-01-02"), ScoresCol.IS_NEW]
    assert result.loc[("b", "2024-01-02"), ScoresCol.IS_NEW]


# ── add_score_delta ────────────────────────────────────────────────────────────


def make_enriched_df(rows):
    df = pd.DataFrame(
        rows,
        columns=[
            ScoresCol.ID,
            ScoresCol.SCORE,
            ScoresCol.DATE,
            ScoresCol.ROBUSTNESS,
            ScoresCol.IS_NEW,
        ],
    )
    return df


def test_add_score_delta_null_on_first():
    df = make_enriched_df(
        [
            ("a", 1.0, "2024-01-01", 1.0, True),
            ("a", 1.5, "2024-01-02", 1.0, False),
        ]
    )
    result = add_score_delta(df)
    result = result.set_index([ScoresCol.ID, ScoresCol.DATE])
    assert math.isnan(result.loc[("a", "2024-01-01"), ScoresCol.SCORE_DELTA])
    assert result.loc[("a", "2024-01-02"), ScoresCol.SCORE_DELTA] == pytest.approx(0.5)


def test_add_score_delta_three_dates():
    df = make_enriched_df(
        [
            ("a", 1.0, "2024-01-01", 1.0, True),
            ("a", 1.5, "2024-01-02", 1.0, False),
            ("a", 1.2, "2024-01-03", 1.0, False),
        ]
    )
    result = add_score_delta(df)
    result = result.set_index([ScoresCol.ID, ScoresCol.DATE])
    assert math.isnan(result.loc[("a", "2024-01-01"), ScoresCol.SCORE_DELTA])
    assert result.loc[("a", "2024-01-02"), ScoresCol.SCORE_DELTA] == pytest.approx(0.5)
    assert result.loc[("a", "2024-01-03"), ScoresCol.SCORE_DELTA] == pytest.approx(-0.3)


def test_add_score_delta_no_cross_album_contamination():
    df = make_enriched_df(
        [
            ("a", 1.0, "2024-01-01", 1.0, True),
            ("b", 5.0, "2024-01-01", 1.0, True),
            ("a", 1.5, "2024-01-02", 1.0, False),
            ("b", 5.5, "2024-01-02", 1.0, False),
        ]
    )
    result = add_score_delta(df)
    result = result.set_index([ScoresCol.ID, ScoresCol.DATE])
    assert result.loc[("a", "2024-01-02"), ScoresCol.SCORE_DELTA] == pytest.approx(0.5)
    assert result.loc[("b", "2024-01-02"), ScoresCol.SCORE_DELTA] == pytest.approx(0.5)


# ── add_rank_delta ─────────────────────────────────────────────────────────────


def make_ranked_df(rows):
    """Like `make_enriched_df`, plus the `rank` column that `add_rank_delta`
    reads."""
    return pd.DataFrame(
        rows,
        columns=[
            ScoresCol.ID,
            ScoresCol.SCORE,
            ScoresCol.DATE,
            ScoresCol.ROBUSTNESS,
            ScoresCol.IS_NEW,
            ScoresCol.RANK,
        ],
    )


def test_add_rank_delta_null_on_first():
    df = make_ranked_df(
        [
            ("a", 1.0, "2024-01-01", 1.0, True, 3.0),
            ("a", 1.5, "2024-01-02", 1.0, False, 2.0),
        ]
    )
    result = add_rank_delta(df).set_index([ScoresCol.ID, ScoresCol.DATE])
    assert math.isnan(result.loc[("a", "2024-01-01"), ScoresCol.RANK_DELTA])


def test_add_rank_delta_moving_up_is_positive():
    df = make_ranked_df(
        [
            ("a", 1.0, "2024-01-01", 1.0, True, 8.0),
            ("a", 1.5, "2024-01-02", 1.0, False, 3.0),
        ]
    )
    result = add_rank_delta(df).set_index([ScoresCol.ID, ScoresCol.DATE])
    assert result.loc[("a", "2024-01-02"), ScoresCol.RANK_DELTA] == pytest.approx(5.0)


def test_add_rank_delta_moving_down_is_negative():
    df = make_ranked_df(
        [
            ("a", 1.5, "2024-01-01", 1.0, True, 3.0),
            ("a", 1.0, "2024-01-02", 1.0, False, 8.0),
        ]
    )
    result = add_rank_delta(df).set_index([ScoresCol.ID, ScoresCol.DATE])
    assert result.loc[("a", "2024-01-02"), ScoresCol.RANK_DELTA] == pytest.approx(-5.0)


def test_add_rank_delta_unchanged_rank_is_positive_zero():
    df = make_ranked_df(
        [
            ("a", 1.0, "2024-01-01", 1.0, True, 2.0),
            ("a", 1.1, "2024-01-02", 1.0, False, 2.0),
        ]
    )
    result = add_rank_delta(df).set_index([ScoresCol.ID, ScoresCol.DATE])
    delta = result.loc[("a", "2024-01-02"), ScoresCol.RANK_DELTA]
    assert delta == 0.0
    # Not -0.0: consumers format the sign, and "-0" would read as a drop.
    assert math.copysign(1.0, delta) == 1.0


def test_add_rank_delta_fractional_ranks():
    # A tie resolving into a clean ordering moves the album half a place.
    df = make_ranked_df(
        [
            ("a", 1.0, "2024-01-01", 1.0, True, 1.5),
            ("a", 1.2, "2024-01-02", 1.0, False, 1.0),
        ]
    )
    result = add_rank_delta(df).set_index([ScoresCol.ID, ScoresCol.DATE])
    assert result.loc[("a", "2024-01-02"), ScoresCol.RANK_DELTA] == pytest.approx(0.5)


def test_add_rank_delta_no_cross_album_contamination():
    df = make_ranked_df(
        [
            ("a", 1.0, "2024-01-01", 1.0, True, 2.0),
            ("b", 5.0, "2024-01-01", 1.0, True, 1.0),
            ("a", 6.0, "2024-01-02", 1.0, False, 1.0),
            ("b", 5.5, "2024-01-02", 1.0, False, 2.0),
        ]
    )
    result = add_rank_delta(df).set_index([ScoresCol.ID, ScoresCol.DATE])
    assert result.loc[("a", "2024-01-02"), ScoresCol.RANK_DELTA] == pytest.approx(1.0)
    assert result.loc[("b", "2024-01-02"), ScoresCol.RANK_DELTA] == pytest.approx(-1.0)


# ── enrich ─────────────────────────────────────────────────────────────────────


def test_enrich_adds_every_column():
    df = make_scores_df(
        [
            ("a", 2.0, "2024-01-01", 1.0),
            ("b", 1.0, "2024-01-01", 1.0),
            ("a", 1.0, "2024-01-02", 1.0),
            ("b", 2.0, "2024-01-02", 1.0),
        ]
    )
    result = enrich(df, TOLERANCE)
    for column in (
        ScoresCol.RANK,
        ScoresCol.IS_NEW,
        ScoresCol.SCORE_DELTA,
        ScoresCol.RANK_DELTA,
    ):
        assert column in result.columns
    assert len(result) == len(df)


def test_enrich_tracks_a_swap_end_to_end():
    # "a" starts on top and "b" overtakes it on the second date.
    df = make_scores_df(
        [
            ("a", 2.0, "2024-01-01", 1.0),
            ("b", 1.0, "2024-01-01", 1.0),
            ("a", 1.0, "2024-01-02", 1.0),
            ("b", 2.0, "2024-01-02", 1.0),
        ]
    )
    result = enrich(df, TOLERANCE).set_index([ScoresCol.ID, ScoresCol.DATE])

    # The debut date has nothing to move from.
    assert math.isnan(result.loc[("a", "2024-01-01"), ScoresCol.RANK_DELTA])
    assert math.isnan(result.loc[("b", "2024-01-01"), ScoresCol.RANK_DELTA])

    # The match itself: "b" gained a place, "a" lost one.
    assert result.loc[("b", "2024-01-02"), ScoresCol.RANK_DELTA] == pytest.approx(1.0)
    assert result.loc[("a", "2024-01-02"), ScoresCol.RANK_DELTA] == pytest.approx(-1.0)
