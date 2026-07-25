import pandas as pd
from toa.columns import ScoresCol
from update import (
    assemble_updated_scores,
    select_dates_to_rescore,
    select_scores_to_keep,
)

DATES = ["2024-01-01", "2024-02-01", "2024-03-01"]


def make_scores_df(rows):
    return pd.DataFrame(
        rows,
        columns=[ScoresCol.ID, ScoresCol.SCORE, ScoresCol.ROBUSTNESS, ScoresCol.DATE],
    )


def empty_scores_df():
    return make_scores_df([])


# ── select_dates_to_rescore ────────────────────────────────────────────────────


def test_select_dates_from_the_middle():
    assert select_dates_to_rescore(DATES, "2024-02-01", False) == DATES[1:]


def test_select_dates_includes_earliest_date_itself():
    # the date a match was added is refitted too, not just the ones after it
    assert "2024-02-01" in select_dates_to_rescore(DATES, "2024-02-01", False)


def test_select_dates_earliest_before_all_dates():
    assert select_dates_to_rescore(DATES, "2023-01-01", False) == DATES


def test_select_dates_earliest_after_all_dates():
    assert select_dates_to_rescore(DATES, "2025-01-01", False) == []


def test_select_dates_earliest_between_dates():
    assert select_dates_to_rescore(DATES, "2024-01-15", False) == DATES[1:]


def test_select_dates_no_result_dates():
    assert select_dates_to_rescore([], "2024-01-01", False) == []


def test_select_dates_rebuild_covers_everything():
    assert select_dates_to_rescore(DATES, "2024-03-01", True) == DATES


def test_select_dates_rebuild_ignores_null_earliest_date():
    assert select_dates_to_rescore(DATES, None, True) == DATES


def test_select_dates_rebuild_with_no_result_dates():
    assert select_dates_to_rescore([], None, True) == []


def test_select_dates_rebuild_does_not_alias_input():
    result_dates = list(DATES)
    selected = select_dates_to_rescore(result_dates, None, True)
    selected.append("2024-04-01")
    assert result_dates == DATES


# ── select_scores_to_keep ──────────────────────────────────────────────────────


def test_select_scores_keeps_only_earlier_dates():
    scores = make_scores_df(
        [
            ("a", 1.0, 0.5, "2024-01-01"),
            ("b", 2.0, 0.5, "2024-02-01"),
            ("c", 3.0, 0.5, "2024-03-01"),
        ]
    )
    kept = select_scores_to_keep(scores, "2024-02-01", False)
    assert kept[ScoresCol.DATE].tolist() == ["2024-01-01"]


def test_select_scores_keeps_nothing_when_earliest_is_first_date():
    scores = make_scores_df([("a", 1.0, 0.5, "2024-01-01")])
    assert select_scores_to_keep(scores, "2024-01-01", False).empty


def test_select_scores_keeps_everything_when_earliest_is_later():
    scores = make_scores_df(
        [
            ("a", 1.0, 0.5, "2024-01-01"),
            ("b", 2.0, 0.5, "2024-02-01"),
        ]
    )
    kept = select_scores_to_keep(scores, "2024-03-01", False)
    assert len(kept) == 2


def test_select_scores_on_empty_frame():
    kept = select_scores_to_keep(empty_scores_df(), "2024-01-01", False)
    assert kept.empty
    assert list(kept.columns) == [
        ScoresCol.ID,
        ScoresCol.SCORE,
        ScoresCol.ROBUSTNESS,
        ScoresCol.DATE,
    ]


def test_select_scores_rebuild_keeps_nothing():
    scores = make_scores_df(
        [
            ("a", 1.0, 0.5, "2024-01-01"),
            ("b", 2.0, 0.5, "2024-02-01"),
        ]
    )
    kept = select_scores_to_keep(scores, "2024-03-01", True)
    assert kept.empty


def test_select_scores_rebuild_preserves_columns():
    scores = make_scores_df([("a", 1.0, 0.5, "2024-01-01")])
    kept = select_scores_to_keep(scores, None, True)
    assert list(kept.columns) == list(scores.columns)


def test_select_scores_does_not_mutate_input():
    scores = make_scores_df(
        [
            ("a", 1.0, 0.5, "2024-01-01"),
            ("b", 2.0, 0.5, "2024-02-01"),
        ]
    )
    select_scores_to_keep(scores, "2024-02-01", False)
    select_scores_to_keep(scores, None, True)
    assert len(scores) == 2


# ── assemble_updated_scores ────────────────────────────────────────────────────


NEW_ROWS = [
    {
        ScoresCol.ID: "b",
        ScoresCol.SCORE: 2.0,
        ScoresCol.ROBUSTNESS: 0.5,
        ScoresCol.DATE: "2024-02-01",
    },
    {
        ScoresCol.ID: "c",
        ScoresCol.SCORE: 3.0,
        ScoresCol.ROBUSTNESS: 0.5,
        ScoresCol.DATE: "2024-02-01",
    },
]


def test_assemble_concatenates_kept_and_new():
    kept = make_scores_df([("a", 1.0, 0.5, "2024-01-01")])
    updated = assemble_updated_scores(kept, NEW_ROWS)
    assert len(updated) == 3
    assert updated[ScoresCol.ID].tolist() == ["a", "b", "c"]
    assert updated[ScoresCol.DATE].tolist() == [
        "2024-01-01",
        "2024-02-01",
        "2024-02-01",
    ]


def test_assemble_reindexes():
    kept = make_scores_df(
        [
            ("a", 1.0, 0.5, "2024-01-01"),
            ("b", 2.0, 0.5, "2024-01-01"),
        ]
    ).iloc[1:]
    updated = assemble_updated_scores(kept, NEW_ROWS)
    assert updated.index.tolist() == [0, 1, 2]


def test_assemble_with_nothing_kept():
    # the rebuild / cold-start path -- the result is just the new rows
    updated = assemble_updated_scores(empty_scores_df(), NEW_ROWS)
    assert len(updated) == 2
    assert updated[ScoresCol.ID].tolist() == ["b", "c"]


def test_assemble_with_nothing_kept_has_no_null_rows():
    updated = assemble_updated_scores(empty_scores_df(), NEW_ROWS)
    assert not updated.isna().any().any()


def test_assemble_with_no_new_rows_returns_kept():
    kept = make_scores_df([("a", 1.0, 0.5, "2024-01-01")])
    updated = assemble_updated_scores(kept, [])
    assert updated[ScoresCol.ID].tolist() == ["a"]


def test_assemble_with_nothing_at_all():
    assert assemble_updated_scores(empty_scores_df(), []).empty


def test_assemble_does_not_mutate_kept():
    kept = make_scores_df([("a", 1.0, 0.5, "2024-01-01")])
    assemble_updated_scores(kept, NEW_ROWS)
    assert len(kept) == 1
