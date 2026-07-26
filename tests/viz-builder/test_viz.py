import pandas as pd
import pytest
from toa.columns import ResultsCol, ScoresCol, VizCol
from viz import build_album_vectors, build_dates, component_matches, largest_component


def make_results_df(rows):
    return pd.DataFrame(
        rows, columns=[ResultsCol.MATCH_ID, ResultsCol.DATE, ResultsCol.ORDER]
    )


def make_scores_df(rows):
    return pd.DataFrame(rows, columns=[ScoresCol.ID, ScoresCol.DATE, ScoresCol.SCORE])


def make_matches_df(rows):
    return pd.DataFrame(
        rows, columns=[ResultsCol.MATCH_ID, ResultsCol.DATE, ResultsCol.ORDER]
    )


def test_largest_component_picks_bigger_clique():
    results = make_results_df(
        [
            ("m1", "2024-01-01", ["a", "b", "c"]),
            ("m2", "2024-01-02", ["x", "y"]),
        ]
    )
    assert largest_component(results) == {"a", "b", "c"}


def test_largest_component_merges_via_bridging_match():
    results = make_results_df(
        [
            ("m1", "2024-01-01", ["a", "b"]),
            ("m2", "2024-01-02", ["c", "d"]),
            ("m3", "2024-01-03", ["b", "c"]),
            ("m4", "2024-01-04", ["x", "y", "z"]),
        ]
    )
    assert largest_component(results) == {"a", "b", "c", "d"}


def test_largest_component_handles_mixed_match_sizes():
    results = make_results_df(
        [
            ("m1", "2024-01-01", ["a", "b", "c", "d", "e"]),
            ("m2", "2024-01-02", ["e", "f"]),
            ("m3", "2024-01-03", ["x", "y", "z"]),
        ]
    )
    assert largest_component(results) == {"a", "b", "c", "d", "e", "f"}


def test_largest_component_tie_breaks_deterministically():
    results = make_results_df(
        [
            ("m1", "2024-01-01", ["p", "q"]),
            ("m2", "2024-01-02", ["a", "b"]),
        ]
    )
    assert largest_component(results) == {"p", "q"}


def test_largest_component_empty_results():
    results = make_results_df([])
    assert largest_component(results) == set()


def test_component_matches_is_all_or_nothing():
    results = make_results_df(
        [
            ("m2", "2024-01-02", ["b", "c"]),
            ("m1", "2024-01-01", ["a", "b", "c"]),
            ("m3", "2024-01-03", ["x", "y"]),
        ]
    )
    matches = component_matches(results, {"a", "b", "c"})
    assert list(matches[ResultsCol.MATCH_ID]) == ["m1", "m2"]


def test_component_matches_sorted_by_date_then_match_id():
    results = make_results_df(
        [
            ("m2", "2024-01-01", ["a", "b"]),
            ("m1", "2024-01-01", ["b", "c"]),
        ]
    )
    matches = component_matches(results, {"a", "b", "c"})
    assert list(matches[ResultsCol.MATCH_ID]) == ["m1", "m2"]


def test_build_dates_sorted_unique_with_preseason():
    scores = make_scores_df(
        [
            ("a", "2024-01-05", 0.1),
            ("b", "2024-01-01", 0.2),
            ("a", "2024-01-01", 0.3),
        ]
    )
    matches = make_results_df([("m1", "2024-01-01", ["a", "b"])])
    assert build_dates(scores, matches) == [
        "2023-12-31",
        "2024-01-01",
        "2024-01-05",
    ]


def test_build_dates_preseason_is_day_before_first_real_date():
    scores = make_scores_df([("a", "2024-03-01", 0.1)])
    matches = make_results_df([("m1", "2024-03-01", ["a", "b"])])
    assert build_dates(scores, matches)[0] == "2024-02-29"


def test_build_dates_empty_has_no_preseason():
    scores = make_scores_df([])
    matches = make_results_df([])
    assert build_dates(scores, matches) == []


def test_build_dates_rejects_match_date_missing_from_scores():
    scores = make_scores_df([("a", "2024-01-01", 0.1)])
    matches = make_results_df([("m1", "2024-01-02", ["a", "b"])])
    with pytest.raises(ValueError, match="match dates missing"):
        build_dates(scores, matches)


def test_build_album_vectors_zero_fills_before_debut():
    dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
    scores = make_scores_df(
        [
            ("a", "2024-01-01", 0.5),
            ("a", "2024-01-02", 0.6),
            ("a", "2024-01-03", 0.7),
            ("b", "2024-01-02", -0.25),
            ("b", "2024-01-03", -0.35),
        ]
    )
    albums = build_album_vectors(scores, {"a", "b"}, dates, make_matches_df([]))

    a = albums[albums[VizCol.ID] == "a"].iloc[0]
    b = albums[albums[VizCol.ID] == "b"].iloc[0]
    assert a[VizCol.DEBUT] == 0
    assert a[VizCol.SCORES] == [0.5, 0.6, 0.7]
    assert b[VizCol.DEBUT] == 1
    assert b[VizCol.SCORES] == [0.0, -0.25, -0.35]


def test_build_album_vectors_rounds_scores():
    dates = ["2024-01-01"]
    scores = make_scores_df([("a", "2024-01-01", 0.123456789)])
    albums = build_album_vectors(scores, {"a"}, dates, make_matches_df([]))
    assert albums.iloc[0][VizCol.SCORES] == [0.1235]


def test_build_album_vectors_excludes_non_component_albums():
    dates = ["2024-01-01"]
    scores = make_scores_df([("a", "2024-01-01", 0.1), ("x", "2024-01-01", 0.2)])
    albums = build_album_vectors(scores, {"a"}, dates, make_matches_df([]))
    assert list(albums[VizCol.ID]) == ["a"]


def test_build_album_vectors_rejects_gaps():
    dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
    scores = make_scores_df(
        [
            ("a", "2024-01-01", 0.1),
            ("a", "2024-01-03", 0.2),
        ]
    )
    with pytest.raises(ValueError, match="gaps"):
        build_album_vectors(scores, {"a"}, dates, make_matches_df([]))


def test_build_album_vectors_rejects_unscored_component_albums():
    dates = ["2024-01-01"]
    scores = make_scores_df([("a", "2024-01-01", 0.1)])
    with pytest.raises(ValueError, match="missing from scores"):
        build_album_vectors(scores, {"a", "ghost"}, dates, make_matches_df([]))


def test_build_album_vectors_collects_match_ids_in_date_order():
    dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
    scores = make_scores_df(
        [
            ("a", "2024-01-01", 0.1),
            ("a", "2024-01-02", 0.2),
            ("a", "2024-01-03", 0.3),
            ("b", "2024-01-01", -0.1),
            ("b", "2024-01-02", -0.2),
            ("b", "2024-01-03", -0.3),
        ]
    )
    # As emitted by component_matches: sorted by (date, match_id).
    matches = make_matches_df(
        [
            ("m1", "2024-01-01", ["a", "b"]),
            ("m2", "2024-01-02", ["a", "b"]),
            ("m3", "2024-01-03", ["b", "a"]),
        ]
    )
    albums = build_album_vectors(scores, {"a", "b"}, dates, matches)

    a = albums[albums[VizCol.ID] == "a"].iloc[0]
    b = albums[albums[VizCol.ID] == "b"].iloc[0]
    assert a[VizCol.MATCH_IDS] == ["m1", "m2", "m3"]
    assert b[VizCol.MATCH_IDS] == ["m1", "m2", "m3"]
