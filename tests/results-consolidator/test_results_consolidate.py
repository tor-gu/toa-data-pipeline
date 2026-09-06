import numpy as np
import pandas as pd
from results_consolidate import (
    REDACTIONS_COLUMNS,
    RESULTS_COLUMNS,
    apply_redactions,
    combine_earliest,
    count_redacted_occurrences,
    earliest_redacted_date,
    empty_redactions_df,
    empty_results_df,
    merge_redactions,
    merge_results,
)
from toa.columns import RedactionsCol, ResultsCol


def result(match_id, date, order):
    return {
        ResultsCol.MATCH_ID: match_id,
        ResultsCol.DATE: date,
        ResultsCol.ORDER: order,
    }


def redaction(id_, artist="An Artist", album="An Album"):
    return {
        RedactionsCol.ID: id_,
        RedactionsCol.ARTIST: artist,
        RedactionsCol.ALBUM: album,
    }


def make_results_df(rows):
    return pd.DataFrame(rows, columns=RESULTS_COLUMNS)


def make_redactions_df(rows):
    return pd.DataFrame(rows, columns=REDACTIONS_COLUMNS)


def match_ids(df):
    return list(df[ResultsCol.MATCH_ID])


def order_for(df, match_id):
    return list(df[df[ResultsCol.MATCH_ID] == match_id].iloc[0][ResultsCol.ORDER])


# ── empty frames ──────────────────────────────────────────────────────────────


def test_empty_results_df_has_the_results_columns():
    assert list(empty_results_df().columns) == RESULTS_COLUMNS
    assert empty_results_df().empty


def test_empty_redactions_df_has_the_redactions_columns():
    assert list(empty_redactions_df().columns) == REDACTIONS_COLUMNS
    assert empty_redactions_df().empty


def test_merging_into_an_empty_results_df_keeps_only_the_new_rows():
    merged = merge_results(empty_results_df(), [result("m1", "2026-01-01", ["a", "b"])])

    assert match_ids(merged) == ["m1"]
    assert list(merged.columns) == RESULTS_COLUMNS


def test_merging_into_an_empty_redactions_df_keeps_only_the_new_rows():
    merged = merge_redactions(empty_redactions_df(), [redaction("a")])

    assert list(merged[RedactionsCol.ID]) == ["a"]
    assert list(merged.columns) == REDACTIONS_COLUMNS


# ── merge_results ─────────────────────────────────────────────────────────────


def test_merge_results_appends_a_new_match():
    existing = make_results_df([result("m1", "2026-01-01", ["a", "b"])])

    merged = merge_results(existing, [result("m2", "2026-01-02", ["c", "d"])])

    assert match_ids(merged) == ["m1", "m2"]


def test_merge_results_upserts_on_match_id():
    existing = make_results_df([result("m1", "2026-01-01", ["a", "b"])])

    merged = merge_results(existing, [result("m1", "2026-01-05", ["b", "a"])])

    assert match_ids(merged) == ["m1"]
    assert order_for(merged, "m1") == ["b", "a"]
    assert merged.iloc[0][ResultsCol.DATE] == "2026-01-05"


def test_merge_results_projects_away_extra_keys():
    merged = merge_results(
        empty_results_df(),
        [{**result("m1", "2026-01-01", ["a", "b"]), "unexpected": "ignored"}],
    )

    assert list(merged.columns) == RESULTS_COLUMNS


# ── merge_redactions ──────────────────────────────────────────────────────────


def test_merge_redactions_appends_a_new_album():
    existing = make_redactions_df([redaction("a")])

    merged = merge_redactions(existing, [redaction("b")])

    assert list(merged[RedactionsCol.ID]) == ["a", "b"]


def test_merge_redactions_upserts_on_id():
    existing = make_redactions_df([redaction("a", artist="Old", album="Old Album")])

    merged = merge_redactions(
        existing, [redaction("a", artist="New", album="New Album")]
    )

    assert list(merged[RedactionsCol.ID]) == ["a"]
    assert merged.iloc[0][RedactionsCol.ARTIST] == "New"


# ── apply_redactions ──────────────────────────────────────────────────────────


def test_apply_redactions_with_no_redactions_returns_the_input():
    unredacted = make_results_df(
        [
            result("m1", "2026-01-01", ["a", "b", "c"]),
            result("m2", "2026-01-02", ["c", "d"]),
        ]
    )

    redacted = apply_redactions(unredacted, set())

    assert match_ids(redacted) == ["m1", "m2"]
    assert order_for(redacted, "m1") == ["a", "b", "c"]


def test_apply_redactions_strips_the_album_and_keeps_the_rest_in_order():
    unredacted = make_results_df([result("m1", "2026-01-01", ["a", "b", "r", "c"])])

    redacted = apply_redactions(unredacted, {"r"})

    assert order_for(redacted, "m1") == ["a", "b", "c"]


def test_apply_redactions_strips_several_albums_at_once():
    unredacted = make_results_df(
        [result("m1", "2026-01-01", ["a", "r", "b", "s", "c"])]
    )

    redacted = apply_redactions(unredacted, {"r", "s"})

    assert order_for(redacted, "m1") == ["a", "b", "c"]


def test_apply_redactions_drops_a_match_reduced_to_one_album():
    unredacted = make_results_df(
        [
            result("m1", "2026-01-01", ["a", "b", "c"]),
            result("m2", "2026-01-02", ["r", "d"]),
        ]
    )

    redacted = apply_redactions(unredacted, {"r"})

    assert match_ids(redacted) == ["m1"]


def test_apply_redactions_drops_a_match_reduced_to_nothing():
    unredacted = make_results_df([result("m1", "2026-01-01", ["r", "s"])])

    redacted = apply_redactions(unredacted, {"r", "s"})

    assert redacted.empty
    assert list(redacted.columns) == RESULTS_COLUMNS


def test_apply_redactions_keeps_a_match_reduced_to_exactly_two_albums():
    unredacted = make_results_df([result("m1", "2026-01-01", ["a", "r", "b"])])

    redacted = apply_redactions(unredacted, {"r"})

    assert order_for(redacted, "m1") == ["a", "b"]


def test_apply_redactions_ignores_an_album_that_never_played():
    unredacted = make_results_df([result("m1", "2026-01-01", ["a", "b", "c"])])

    redacted = apply_redactions(unredacted, {"never"})

    assert match_ids(redacted) == ["m1"]
    assert order_for(redacted, "m1") == ["a", "b", "c"]


def test_apply_redactions_handles_orders_stored_as_numpy_arrays():
    # This is the shape `order` comes back in after a Parquet round trip.
    unredacted = make_results_df(
        [result("m1", "2026-01-01", np.array(["a", "r", "b"], dtype=object))]
    )

    redacted = apply_redactions(unredacted, {"r"})

    assert order_for(redacted, "m1") == ["a", "b"]


def test_apply_redactions_leaves_the_unredacted_frame_untouched():
    unredacted = make_results_df([result("m1", "2026-01-01", ["a", "r", "b"])])

    apply_redactions(unredacted, {"r"})

    assert order_for(unredacted, "m1") == ["a", "r", "b"]


def test_apply_redactions_renumbers_the_index():
    unredacted = make_results_df(
        [
            result("m1", "2026-01-01", ["r", "a"]),
            result("m2", "2026-01-02", ["b", "c"]),
        ]
    )

    redacted = apply_redactions(unredacted, {"r"})

    assert list(redacted.index) == [0]


def test_apply_redactions_on_an_empty_frame_stays_empty():
    redacted = apply_redactions(empty_results_df(), {"r"})

    assert redacted.empty
    assert list(redacted.columns) == RESULTS_COLUMNS


# ── count_redacted_occurrences ────────────────────────────────────────────────


def test_count_redacted_occurrences_counts_one_per_match():
    unredacted = make_results_df(
        [
            result("m1", "2026-01-01", ["a", "r", "b"]),
            result("m2", "2026-01-02", ["r", "c"]),
            result("m3", "2026-01-03", ["a", "b", "r"]),
        ]
    )

    assert count_redacted_occurrences(unredacted, {"r"}) == 3


def test_count_redacted_occurrences_sums_across_several_albums():
    unredacted = make_results_df(
        [
            result("m1", "2026-01-01", ["a", "r", "s"]),
            result("m2", "2026-01-02", ["s", "c"]),
        ]
    )

    assert count_redacted_occurrences(unredacted, {"r", "s"}) == 3


def test_count_redacted_occurrences_is_zero_for_an_album_that_never_played():
    unredacted = make_results_df([result("m1", "2026-01-01", ["a", "b", "c"])])

    assert count_redacted_occurrences(unredacted, {"never"}) == 0


def test_count_redacted_occurrences_is_zero_without_redactions():
    unredacted = make_results_df([result("m1", "2026-01-01", ["a", "b"])])

    assert count_redacted_occurrences(unredacted, set()) == 0


def test_count_redacted_occurrences_is_zero_on_an_empty_frame():
    assert count_redacted_occurrences(empty_results_df(), {"r"}) == 0


def test_count_redacted_occurrences_counts_dropped_matches_too():
    # m2 falls below MIN_MATCH_SIZE and disappears, but its slot was still removed.
    unredacted = make_results_df(
        [
            result("m1", "2026-01-01", ["a", "r", "b"]),
            result("m2", "2026-01-02", ["r", "c"]),
        ]
    )

    assert count_redacted_occurrences(unredacted, {"r"}) == 2
    assert match_ids(apply_redactions(unredacted, {"r"})) == ["m1"]


def test_count_redacted_occurrences_returns_a_plain_int():
    unredacted = make_results_df([result("m1", "2026-01-01", ["a", "r"])])

    # The state machine compares this numerically; a numpy int64 would not
    # survive the Lambda's JSON response.
    assert type(count_redacted_occurrences(unredacted, {"r"})) is int


def test_count_redacted_occurrences_handles_orders_stored_as_numpy_arrays():
    unredacted = make_results_df(
        [result("m1", "2026-01-01", np.array(["a", "r", "b"], dtype=object))]
    )

    assert count_redacted_occurrences(unredacted, {"r"}) == 1


# ── earliest_redacted_date ────────────────────────────────────────────────────


def test_earliest_redacted_date_finds_the_first_appearance():
    unredacted = make_results_df(
        [
            result("m1", "2026-03-01", ["a", "b"]),
            result("m2", "2026-01-15", ["r", "c"]),
            result("m3", "2026-02-01", ["r", "d"]),
        ]
    )

    assert earliest_redacted_date(unredacted, {"r"}) == "2026-01-15"


def test_earliest_redacted_date_spans_several_redacted_albums():
    unredacted = make_results_df(
        [
            result("m1", "2026-03-01", ["r", "a"]),
            result("m2", "2026-01-15", ["s", "b"]),
        ]
    )

    assert earliest_redacted_date(unredacted, {"r", "s"}) == "2026-01-15"


def test_earliest_redacted_date_is_none_when_the_album_never_played():
    unredacted = make_results_df([result("m1", "2026-03-01", ["a", "b"])])

    assert earliest_redacted_date(unredacted, {"r"}) is None


def test_earliest_redacted_date_is_none_without_redactions():
    unredacted = make_results_df([result("m1", "2026-03-01", ["a", "b"])])

    assert earliest_redacted_date(unredacted, set()) is None


def test_earliest_redacted_date_is_none_on_an_empty_frame():
    assert earliest_redacted_date(empty_results_df(), {"r"}) is None


# ── combine_earliest ──────────────────────────────────────────────────────────


def test_combine_earliest_picks_the_earlier_date():
    assert combine_earliest("2026-09-01", "2024-03-02") == "2024-03-02"


def test_combine_earliest_ignores_none():
    assert combine_earliest(None, "2026-09-01") == "2026-09-01"
    assert combine_earliest("2026-09-01", None) == "2026-09-01"


def test_combine_earliest_is_none_when_everything_is_none():
    assert combine_earliest(None, None) is None
