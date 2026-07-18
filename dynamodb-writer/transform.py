from decimal import Decimal

import pandas as pd
from toa.columns import ScoresCol, StatisticsCol, VizCol

VIZ_PK = "VIZ"


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


def viz_dates_item(dates, num_albums, num_matches):
    return {
        "pk": VIZ_PK,
        "sk": "DATES",
        "dates": list(dates),
        "num_dates": len(dates),
        "num_albums": num_albums,
        "num_matches": num_matches,
    }


def viz_album_item(row, name):
    return {
        "pk": VIZ_PK,
        "sk": f"ALBUM#{row[VizCol.ID]}",
        "artist": name.get("artist", ""),
        "album": name.get("album", ""),
        "short-name": name.get("short-name", ""),
        "debut": int(row[VizCol.DEBUT]),
        "scores": [Decimal(str(score)) for score in row[VizCol.SCORES]],
        "match_ids": list(row[VizCol.MATCH_IDS]),
    }


def viz_match_item(row):
    return {
        "pk": VIZ_PK,
        "sk": f"MATCH#{row[VizCol.DATE]}#{row[VizCol.MATCH_ID]}",
        "match_id": row[VizCol.MATCH_ID],
        "date": row[VizCol.DATE],
        "ranking": list(row[VizCol.ORDER]),
    }


def stale_viz_keys(existing_sks, new_sks):
    return sorted(set(existing_sks) - set(new_sks))


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
