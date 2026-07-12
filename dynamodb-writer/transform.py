from decimal import Decimal

import pandas as pd
from toa.columns import ScoresCol, StatisticsCol


def to_decimal(value):
    return None if pd.isna(value) else Decimal(str(value))


def build_scores_lookup(scores_df):
    return {
        (row[ScoresCol.ID], row[ScoresCol.DATE]): {
            "is_new": bool(row[ScoresCol.IS_NEW]),
            "score_delta": to_decimal(row[ScoresCol.SCORE_DELTA]),
        }
        for _, row in scores_df.iterrows()
    }


def score_item(row, name):
    return {
        "id": row[ScoresCol.ID],
        "date": row[ScoresCol.DATE],
        "score": Decimal(str(row[ScoresCol.SCORE])),
        "robustness": Decimal(str(row[ScoresCol.ROBUSTNESS])),
        "rank": Decimal(str(row[ScoresCol.RANK])),
        "artist": name.get("artist", ""),
        "album": name.get("album", ""),
        "short-name": name.get("short-name", ""),
    }


def statistics_items(row):
    return [
        {
            "key": StatisticsCol.EARLIEST_MATCH,
            "value": row[StatisticsCol.EARLIEST_MATCH],
        },
        {"key": StatisticsCol.LATEST_MATCH, "value": row[StatisticsCol.LATEST_MATCH]},
        {
            "key": StatisticsCol.MIN_SCORE,
            "value": to_decimal(row[StatisticsCol.MIN_SCORE]),
        },
        {
            "key": StatisticsCol.MAX_SCORE,
            "value": to_decimal(row[StatisticsCol.MAX_SCORE]),
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


def ranking_entry(i, album_id, date, names, scores_lookup):
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
