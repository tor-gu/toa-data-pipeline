"""Pure builders that turn pandas rows into DynamoDB items.

Kept free of boto3 and I/O so the item shapes can be unit tested directly;
`handler.py` owns reading from S3 and writing to the tables.
"""

from decimal import Decimal

import pandas as pd
from toa.columns import ScoresCol, StatisticsCol, VizCol

VIZ_PK = "VIZ"


def to_decimal(value):
    """Convert a numeric value to a Decimal. Going via `str` keeps the short
    repr rather than expanding the full binary float.

    Use for required fields. A missing value converts to
    Decimal("NaN"), which would fail on a DynamoDB write."""
    return Decimal(str(value))


def to_optional_decimal(value):
    """Convert a numeric value to a Decimal, mapping missing values to None.

    Use for fields that are legit nullable."""
    return None if pd.isna(value) else to_decimal(value)


def build_scores_lookup(scores_df):
    """Index `is_new` and `score_delta` by (album id, date). Covers only the
    rows present in `scores_df`."""
    return {
        (row[ScoresCol.ID], row[ScoresCol.DATE]): {
            "is_new": bool(row[ScoresCol.IS_NEW]),
            "score_delta": to_optional_decimal(row[ScoresCol.SCORE_DELTA]),
        }
        for _, row in scores_df.iterrows()
    }


def score_item(row, name):
    """Build a `scores` item from a scores row and its name entry. Missing name
    fields default to empty strings."""
    return {
        "id": row[ScoresCol.ID],
        "date": row[ScoresCol.DATE],
        "score": to_decimal(row[ScoresCol.SCORE]),
        "robustness": to_decimal(row[ScoresCol.ROBUSTNESS]),
        "rank": to_decimal(row[ScoresCol.RANK]),
        "artist": name.get("artist", ""),
        "album": name.get("album", ""),
        "short-name": name.get("short-name", ""),
    }


def statistics_items(row):
    """Fan one statistics row out into a key/value item per statistic. The two
    match dates stay strings; the rest become Decimals."""
    return [
        {
            "key": StatisticsCol.EARLIEST_MATCH,
            "value": row[StatisticsCol.EARLIEST_MATCH],
        },
        {"key": StatisticsCol.LATEST_MATCH, "value": row[StatisticsCol.LATEST_MATCH]},
        {
            "key": StatisticsCol.MIN_SCORE,
            "value": to_optional_decimal(row[StatisticsCol.MIN_SCORE]),
        },
        {
            "key": StatisticsCol.MAX_SCORE,
            "value": to_optional_decimal(row[StatisticsCol.MAX_SCORE]),
        },
        {
            "key": StatisticsCol.NUM_ALBUMS,
            "value": to_decimal(row[StatisticsCol.NUM_ALBUMS]),
        },
        {
            "key": StatisticsCol.NUM_MATCHES,
            "value": to_decimal(row[StatisticsCol.NUM_MATCHES]),
        },
    ]


def viz_dates_item(dates, num_albums, num_matches):
    """Build the `DATES` item: the date axis plus the dataset counts."""
    return {
        "pk": VIZ_PK,
        "sk": "DATES",
        "dates": list(dates),
        "num_dates": len(dates),
        "num_albums": num_albums,
        "num_matches": num_matches,
    }


def viz_album_item(row, name):
    """Build an `ALBUM#<id>` item. `scores` carries one entry per date on the
    axis, zero-filled before `debut`."""
    return {
        "pk": VIZ_PK,
        "sk": f"ALBUM#{row[VizCol.ID]}",
        "artist": name.get("artist", ""),
        "album": name.get("album", ""),
        "short-name": name.get("short-name", ""),
        "debut": int(row[VizCol.DEBUT]),
        "scores": [to_decimal(score) for score in row[VizCol.SCORES]],
        "match_ids": list(row[VizCol.MATCH_IDS]),
    }


def viz_match_item(row):
    """Build a `MATCH#<date>#<match_id>` item. Leading the sort key with the
    ISO date makes it order chronologically."""
    return {
        "pk": VIZ_PK,
        "sk": f"MATCH#{row[VizCol.DATE]}#{row[VizCol.MATCH_ID]}",
        "match_id": row[VizCol.MATCH_ID],
        "date": row[VizCol.DATE],
        "ranking": list(row[VizCol.ORDER]),
    }


def stale_viz_keys(existing_sks, new_sks):
    """Sort keys in `existing_sks` that are absent from `new_sks`, sorted for a
    stable delete order."""
    return sorted(set(existing_sks) - set(new_sks))


def ranking_entry(i, album_id, date, names, scores_lookup):
    """Build one entry of a match ranking. `i` is the 0-based position and
    becomes a 1-based rank. `is_new` and `score_delta` are None when
    (`album_id`, `date`) is absent from `scores_lookup`."""
    name = names.get(album_id, {})
    scores = scores_lookup.get((album_id, date), {})
    return {
        "rank": i + 1,
        "id": album_id,
        "artist": name.get("artist", ""),
        "album": name.get("album", ""),
        "short-name": name.get("short-name", ""),
        "is_new": scores.get("is_new"),
        "score_delta": scores.get("score_delta"),
    }
