from decimal import Decimal

import pandas as pd
from toa.columns import ScoresCol, StatisticsCol, VizCol
from transform import (
    VIZ_PK,
    build_scores_lookup,
    ranking_entry,
    score_item,
    stale_viz_keys,
    statistics_items,
    to_decimal,
    viz_album_item,
    viz_dates_item,
    viz_match_item,
)

# ── to_decimal ──────────────────────────────────────────────────────────────


def test_to_decimal_numeric():
    assert to_decimal(1.5) == Decimal("1.5")


def test_to_decimal_nan():
    assert to_decimal(float("nan")) is None


def test_to_decimal_none():
    assert to_decimal(None) is None


# ── build_scores_lookup ──────────────────────────────────────────────────────


def make_scores_df(rows):
    return pd.DataFrame(
        rows,
        columns=[
            ScoresCol.ID,
            ScoresCol.SCORE,
            ScoresCol.DATE,
            ScoresCol.ROBUSTNESS,
            ScoresCol.RANK,
            ScoresCol.IS_NEW,
            ScoresCol.SCORE_DELTA,
        ],
    )


def test_build_scores_lookup_keys_and_types():
    df = make_scores_df(
        [
            ("a", 1.0, "2024-01-01", 1.0, 1.0, True, float("nan")),
            ("b", 0.5, "2024-01-01", 1.0, 2.0, False, -0.3),
        ]
    )
    lookup = build_scores_lookup(df)

    assert lookup[("a", "2024-01-01")]["is_new"] is True
    assert lookup[("a", "2024-01-01")]["score_delta"] is None

    assert lookup[("b", "2024-01-01")]["is_new"] is False
    assert lookup[("b", "2024-01-01")]["score_delta"] == Decimal("-0.3")


def test_build_scores_lookup_is_new_is_native_bool():
    df = make_scores_df([("a", 1.0, "2024-01-01", 1.0, 1.0, True, float("nan"))])
    lookup = build_scores_lookup(df)
    assert type(lookup[("a", "2024-01-01")]["is_new"]) is bool


# ── score_item ────────────────────────────────────────────────────────────────


def test_score_item_includes_rank():
    row = pd.Series(
        {
            ScoresCol.ID: "a",
            ScoresCol.DATE: "2024-01-01",
            ScoresCol.SCORE: 0.5,
            ScoresCol.ROBUSTNESS: 1.2,
            ScoresCol.RANK: 1.5,
        }
    )
    item = score_item(
        row, {"artist": "Artist", "album": "Album", "short-name": "Short"}
    )
    assert item["rank"] == Decimal("1.5")
    assert item["artist"] == "Artist"


def test_score_item_missing_name_defaults_to_empty_strings():
    row = pd.Series(
        {
            ScoresCol.ID: "a",
            ScoresCol.DATE: "2024-01-01",
            ScoresCol.SCORE: 0.5,
            ScoresCol.ROBUSTNESS: 1.2,
            ScoresCol.RANK: 1.0,
        }
    )
    item = score_item(row, {})
    assert item["artist"] == ""
    assert item["album"] == ""
    assert item["short-name"] == ""


# ── ranking_entry ────────────────────────────────────────────────────────────


def test_ranking_entry_includes_is_new_and_score_delta():
    names = {"a": {"artist": "Artist", "album": "Album", "short-name": "Short"}}
    scores_lookup = {
        ("a", "2024-01-01"): {"is_new": False, "score_delta": Decimal("0.2")}
    }

    entry = ranking_entry(0, "a", "2024-01-01", names, scores_lookup)

    assert entry == {
        "rank": 1,
        "id": "a",
        "artist": "Artist",
        "album": "Album",
        "short-name": "Short",
        "is_new": False,
        "score_delta": Decimal("0.2"),
    }


def test_ranking_entry_missing_score_defaults_to_none():
    entry = ranking_entry(2, "z", "2024-01-01", {}, {})
    assert entry["rank"] == 3
    assert entry["is_new"] is None
    assert entry["score_delta"] is None


# ── statistics_items ────────────────────────────────────────────────────────────


def test_statistics_items_shape_and_values():
    row = pd.Series(
        {
            StatisticsCol.EARLIEST_MATCH: "2024-01-01",
            StatisticsCol.LATEST_MATCH: "2024-06-01",
            StatisticsCol.MIN_SCORE: -1.5,
            StatisticsCol.MAX_SCORE: 3.25,
            StatisticsCol.NUM_ALBUMS: 42,
            StatisticsCol.NUM_MATCHES: 100,
        }
    )

    items = statistics_items(row)

    by_key = {item["key"]: item["value"] for item in items}
    assert by_key[StatisticsCol.EARLIEST_MATCH] == "2024-01-01"
    assert by_key[StatisticsCol.LATEST_MATCH] == "2024-06-01"
    assert by_key[StatisticsCol.MIN_SCORE] == Decimal("-1.5")
    assert by_key[StatisticsCol.MAX_SCORE] == Decimal("3.25")
    assert by_key[StatisticsCol.NUM_ALBUMS] == Decimal("42")
    assert by_key[StatisticsCol.NUM_MATCHES] == Decimal("100")
    assert len(items) == 6


# ── viz items ────────────────────────────────────────────────────────────────


def test_viz_dates_item_shape():
    item = viz_dates_item(["2024-01-01", "2024-01-02"], 3, 5)
    assert item == {
        "pk": VIZ_PK,
        "sk": "DATES",
        "dates": ["2024-01-01", "2024-01-02"],
        "num_dates": 2,
        "num_albums": 3,
        "num_matches": 5,
    }


def test_viz_album_item_decimal_scores_and_sk():
    row = pd.Series(
        {
            VizCol.ID: "abc123",
            VizCol.DEBUT: 1,
            VizCol.SCORES: [0.0, 0.1235],
            VizCol.MATCH_IDS: ["m1", "m2"],
        }
    )
    item = viz_album_item(
        row, {"artist": "Artist", "album": "Album", "short-name": "Short"}
    )
    assert item["pk"] == VIZ_PK
    assert item["sk"] == "ALBUM#abc123"
    assert item["debut"] == 1
    assert item["scores"] == [Decimal("0.0"), Decimal("0.1235")]
    assert item["match_ids"] == ["m1", "m2"]
    assert item["artist"] == "Artist"


def test_viz_album_item_missing_name_defaults_to_empty_strings():
    row = pd.Series(
        {
            VizCol.ID: "abc123",
            VizCol.DEBUT: 0,
            VizCol.SCORES: [0.5],
            VizCol.MATCH_IDS: ["m1"],
        }
    )
    item = viz_album_item(row, {})
    assert item["artist"] == ""
    assert item["album"] == ""
    assert item["short-name"] == ""


def test_viz_match_item_sk_sorts_chronologically():
    row = pd.Series(
        {
            VizCol.MATCH_ID: "m1",
            VizCol.DATE: "2024-01-01",
            VizCol.ORDER: ["a", "b", "c"],
        }
    )
    item = viz_match_item(row)
    assert item == {
        "pk": VIZ_PK,
        "sk": "MATCH#2024-01-01#m1",
        "match_id": "m1",
        "date": "2024-01-01",
        "ranking": ["a", "b", "c"],
    }


def test_stale_viz_keys_diff():
    existing = ["DATES", "ALBUM#a", "ALBUM#b", "MATCH#2024-01-01#m1"]
    new = ["DATES", "ALBUM#a", "MATCH#2024-01-01#m1"]
    assert stale_viz_keys(existing, new) == ["ALBUM#b"]


def test_stale_viz_keys_empty_when_no_change():
    assert stale_viz_keys(["DATES"], ["DATES"]) == []
