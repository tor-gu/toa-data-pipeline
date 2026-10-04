"""Pure builders that turn pandas rows into DynamoDB items.

Kept free of boto3 and I/O so the item shapes can be unit tested directly;
`handler.py` owns reading from S3 and writing to the tables.
"""

from decimal import Decimal

import pandas as pd
from toa.columns import NamesCol, ScoresCol, StatisticsCol, VizCol

VIZ_PK = "VIZ"

# Every match row carries this constant partition key on the recent-index GSI, so
# the index is one partition that orders matches by date.
MATCHES_PK = "MATCH"


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


def build_names(names_df):
    """Index display names by album id: `{id: {artist, album, short-name}}`."""
    return {
        row[NamesCol.ID]: {
            "artist": row[NamesCol.ARTIST],
            "album": row[NamesCol.ALBUM],
            "short-name": row[NamesCol.SHORT_NAME],
        }
        for _, row in names_df.iterrows()
    }


def select_since(df, date_col, earliest_date):
    """Rows of `df` dated on or after `earliest_date`, or all of `df` when it is
    None (a full rewrite)."""
    if earliest_date is None:
        return df
    return df[df[date_col] >= earliest_date]


def build_scores_lookup(scores_df):
    """Index the album's standing as of a date — `new_score`, `new_rank`,
    `is_new`, `score_delta` and `rank_delta` — by (album id, date). Covers only
    the rows present in `scores_df`.

    Note that `score_delta` and `rank_delta` will be null on an album's first
    appearance."""
    return {
        (row[ScoresCol.ID], row[ScoresCol.DATE]): {
            "new_score": to_decimal(row[ScoresCol.SCORE]),
            "new_rank": to_decimal(row[ScoresCol.RANK]),
            "is_new": bool(row[ScoresCol.IS_NEW]),
            "score_delta": to_optional_decimal(row[ScoresCol.SCORE_DELTA]),
            "rank_delta": to_optional_decimal(row[ScoresCol.RANK_DELTA]),
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


def match_item(match_id, date, ranking):
    """Build a `matches` item. `gsi_pk` puts every match in the one partition of
    the recent-index GSI, and `date_match_id` orders them by date there."""
    return {
        "match_id": match_id,
        "date": date,
        "ranking": ranking,
        "gsi_pk": MATCHES_PK,
        "date_match_id": f"{date}#{match_id}",
    }


def album_match_item(album_id, match_id, date, name):
    """Build an `album_matches` item from its keys and the album's name entry.
    Missing name fields default to empty strings."""
    return {
        "album_id": album_id,
        "match_id": match_id,
        "date": date,
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


def ranking_entry(i, album_id, date, names, scores_lookup):
    """Build one entry of a match ranking. `i` is the 0-based position and
    becomes a 1-based rank.

    Two different ranks live in this entry. `rank` is the album's position
    *within this match*, running 1..N over the result order. `new_rank` is its
    standing among *all* albums as of `date`, and `rank_delta` is the movement
    of that standing — not of `rank`. The pair mirrors `new_score` and
    `score_delta`.

    Everything drawn from the lookup is None when (`album_id`, `date`) is absent
    from `scores_lookup`."""
    name = names.get(album_id, {})
    scores = scores_lookup.get((album_id, date), {})
    return {
        "rank": i + 1,
        "id": album_id,
        "artist": name.get("artist", ""),
        "album": name.get("album", ""),
        "short-name": name.get("short-name", ""),
        "new_score": scores.get("new_score"),
        "new_rank": scores.get("new_rank"),
        "is_new": scores.get("is_new"),
        "score_delta": scores.get("score_delta"),
        "rank_delta": scores.get("rank_delta"),
    }
