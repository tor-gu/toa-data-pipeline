from decimal import Decimal

import pandas as pd
from toa.columns import ScoresCol
from transform import build_scores_lookup, ranking_entry, score_item, to_decimal

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
