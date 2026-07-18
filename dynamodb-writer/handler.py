import os

import awswrangler as wr
import boto3
from boto3.dynamodb.conditions import Key
from toa.columns import NamesCol, ResultsCol, ScoresCol, VizCol
from toa.dynamodb import query_all
from toa.logging import Domain, get_logger
from toa.paths import (
    ENRICHED_SCORES_KEY,
    GLOBAL_STATISTICS_KEY,
    NAMES_CONSOLIDATED_KEY,
    RESULTS_CONSOLIDATED_KEY,
    VIZ_ALBUMS_KEY,
    VIZ_DATES_KEY,
    VIZ_MATCHES_KEY,
)
from transform import (
    VIZ_PK,
    build_scores_lookup,
    ranking_entry,
    score_item,
    stale_viz_keys,
    statistics_items,
    viz_album_item,
    viz_dates_item,
    viz_match_item,
)

DATA_BUCKET = os.environ["DATA_BUCKET"]
SCORES_TABLE = os.environ["SCORES_TABLE"]
MATCHES_TABLE = os.environ["MATCHES_TABLE"]
ALBUM_MATCHES_TABLE = os.environ["ALBUM_MATCHES_TABLE"]
GLOBAL_STATISTICS_TABLE = os.environ["GLOBAL_STATISTICS_TABLE"]
VIZ_TABLE = os.environ["VIZ_TABLE"]

NAMES_PATH = f"s3://{DATA_BUCKET}/{NAMES_CONSOLIDATED_KEY}"
RESULTS_PATH = f"s3://{DATA_BUCKET}/{RESULTS_CONSOLIDATED_KEY}"
SCORES_PATH = f"s3://{DATA_BUCKET}/{ENRICHED_SCORES_KEY}"
STATISTICS_PATH = f"s3://{DATA_BUCKET}/{GLOBAL_STATISTICS_KEY}"
VIZ_DATES_PATH = f"s3://{DATA_BUCKET}/{VIZ_DATES_KEY}"
VIZ_ALBUMS_PATH = f"s3://{DATA_BUCKET}/{VIZ_ALBUMS_KEY}"
VIZ_MATCHES_PATH = f"s3://{DATA_BUCKET}/{VIZ_MATCHES_KEY}"

logger = get_logger(name="dynamodb-writer", domain=Domain.SCORING_PIPELINE)
dynamodb = boto3.resource("dynamodb")


def _build_names(names_df):
    return {
        row[NamesCol.ID]: {
            "artist": row[NamesCol.ARTIST],
            "album": row[NamesCol.ALBUM],
            "short-name": row[NamesCol.SHORT_NAME],
        }
        for _, row in names_df.iterrows()
    }


def _write_scores(table, affected_scores, names, latest_date):
    with table.batch_writer() as batch:
        for _, row in affected_scores.iterrows():
            name = names.get(row[ScoresCol.ID], {})
            batch.put_item(Item=score_item(row, name))
    table.put_item(Item={"id": "METADATA", "date": "latest_date", "value": latest_date})


def _write_matches(
    matches_table, album_matches_table, affected_results, names, scores_lookup
):
    with (
        matches_table.batch_writer() as matches_batch,
        album_matches_table.batch_writer() as album_matches_batch,
    ):
        for _, row in affected_results.iterrows():
            match_id = row[ResultsCol.MATCH_ID]
            date = row[ResultsCol.DATE]
            order = row[ResultsCol.ORDER]

            ranking = [
                ranking_entry(i, album_id, date, names, scores_lookup)
                for i, album_id in enumerate(order)
            ]

            matches_batch.put_item(
                Item={
                    "match_id": match_id,
                    "date": date,
                    "ranking": ranking,
                    "gsi_pk": "MATCH",
                    "date_match_id": f"{date}#{match_id}",
                }
            )

            for album_id in order:
                album_matches_batch.put_item(
                    Item={
                        "album_id": album_id,
                        "match_id": match_id,
                        "date": date,
                        "artist": names.get(album_id, {}).get("artist", ""),
                        "album": names.get(album_id, {}).get("album", ""),
                        "short-name": names.get(album_id, {}).get("short-name", ""),
                    }
                )


# The viz dataset is always fully rewritten (never earliest_date-filtered):
# a new date lengthens every album's score vector, and the identity of the
# largest component can change between runs.
def _write_viz(table, dates_df, albums_df, matches_df, names):
    dates = list(dates_df[VizCol.DATE])
    items = [viz_dates_item(dates, len(albums_df), len(matches_df))]
    for _, row in albums_df.iterrows():
        items.append(viz_album_item(row, names.get(row[VizCol.ID], {})))
    for _, row in matches_df.iterrows():
        items.append(viz_match_item(row))

    existing = query_all(
        table,
        KeyConditionExpression=Key("pk").eq(VIZ_PK),
        ProjectionExpression="sk",
    )
    stale = stale_viz_keys(
        (item["sk"] for item in existing), (item["sk"] for item in items)
    )

    # Write before deleting so concurrent readers never see an empty partition.
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
        for sk in stale:
            batch.delete_item(Key={"pk": VIZ_PK, "sk": sk})

    return len(items), len(stale)


def _write_statistics(table, stats_df):
    with table.batch_writer() as batch:
        for item in statistics_items(stats_df.iloc[0]):
            batch.put_item(Item=item)


def handler(event, _context):
    logger.info("handler started")
    try:
        rebuild = event.get("rebuild", False)
        earliest_date = None if rebuild else event["earliest_date"]

        if rebuild:
            logger.info("rebuild mode: writing all records")

        logger.info("reading names")
        names = _build_names(wr.s3.read_parquet(NAMES_PATH))
        logger.info("names loaded", extra={"count": len(names)})

        logger.info("reading scores", extra={"earliest_date": earliest_date})
        scores_df = wr.s3.read_parquet(SCORES_PATH)
        affected_scores = (
            scores_df
            if rebuild
            else scores_df[scores_df[ScoresCol.DATE] >= earliest_date]
        )
        logger.info(
            "scores loaded",
            extra={"total": len(scores_df), "affected": len(affected_scores)},
        )

        logger.info("reading results")
        results_df = wr.s3.read_parquet(RESULTS_PATH)
        affected_results = (
            results_df
            if rebuild
            else results_df[results_df[ResultsCol.DATE] >= earliest_date]
        )
        logger.info(
            "results loaded",
            extra={"total": len(results_df), "affected": len(affected_results)},
        )

        logger.info("writing scores to dynamodb")
        latest_date = scores_df[ScoresCol.DATE].max()
        _write_scores(dynamodb.Table(SCORES_TABLE), affected_scores, names, latest_date)
        logger.info(
            "scores written",
            extra={"count": len(affected_scores), "latest_date": latest_date},
        )

        logger.info("writing matches to dynamodb")
        scores_lookup = build_scores_lookup(affected_scores)
        _write_matches(
            dynamodb.Table(MATCHES_TABLE),
            dynamodb.Table(ALBUM_MATCHES_TABLE),
            affected_results,
            names,
            scores_lookup,
        )
        logger.info("matches written", extra={"count": len(affected_results)})

        logger.info("writing global statistics to dynamodb")
        stats_df = wr.s3.read_parquet(STATISTICS_PATH)
        _write_statistics(dynamodb.Table(GLOBAL_STATISTICS_TABLE), stats_df)
        logger.info("global statistics written")

        logger.info("writing viz data to dynamodb")
        viz_written, viz_deleted = _write_viz(
            dynamodb.Table(VIZ_TABLE),
            wr.s3.read_parquet(VIZ_DATES_PATH),
            wr.s3.read_parquet(VIZ_ALBUMS_PATH),
            wr.s3.read_parquet(VIZ_MATCHES_PATH),
            names,
        )
        logger.info(
            "viz data written",
            extra={"items_written": viz_written, "stale_deleted": viz_deleted},
        )

        logger.info(
            "update complete",
            extra={
                "scores_written": len(affected_scores),
                "matches_written": len(affected_results),
            },
        )
    except Exception:
        logger.exception("handler error")
        raise
