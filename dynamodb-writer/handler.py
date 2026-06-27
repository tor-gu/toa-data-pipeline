import os
from decimal import Decimal

import awswrangler as wr
import boto3
from toa.columns import NamesCol, ResultsCol, ScoresCol
from toa.logging import Domain, get_logger
from toa.paths import NAMES_CONSOLIDATED_KEY, RESULTS_CONSOLIDATED_KEY, SCORES_KEY

DATA_BUCKET = os.environ["DATA_BUCKET"]
SCORES_TABLE = os.environ["SCORES_TABLE"]
MATCHES_TABLE = os.environ["MATCHES_TABLE"]
ALBUM_MATCHES_TABLE = os.environ["ALBUM_MATCHES_TABLE"]

NAMES_PATH = f"s3://{DATA_BUCKET}/{NAMES_CONSOLIDATED_KEY}"
RESULTS_PATH = f"s3://{DATA_BUCKET}/{RESULTS_CONSOLIDATED_KEY}"
SCORES_PATH = f"s3://{DATA_BUCKET}/{SCORES_KEY}"

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
            batch.put_item(
                Item={
                    "id": row[ScoresCol.ID],
                    "date": row[ScoresCol.DATE],
                    "score": Decimal(str(row[ScoresCol.SCORE])),
                    "robustness": Decimal(str(row[ScoresCol.ROBUSTNESS])),
                    "artist": name.get("artist", ""),
                    "album": name.get("album", ""),
                    "short-name": name.get("short-name", ""),
                }
            )
    table.put_item(Item={"id": "METADATA", "date": "latest_date", "value": latest_date})


def _write_matches(matches_table, album_matches_table, affected_results, names):
    with (
        matches_table.batch_writer() as matches_batch,
        album_matches_table.batch_writer() as album_matches_batch,
    ):
        for _, row in affected_results.iterrows():
            match_id = row[ResultsCol.MATCH_ID]
            date = row[ResultsCol.DATE]
            order = row[ResultsCol.ORDER]

            ranking = [
                {
                    "rank": i + 1,
                    "id": album_id,
                    "artist": names.get(album_id, {}).get("artist", ""),
                    "album": names.get(album_id, {}).get("album", ""),
                    "short-name": names.get(album_id, {}).get("short-name", ""),
                }
                for i, album_id in enumerate(order)
            ]

            matches_batch.put_item(
                Item={"match_id": match_id, "date": date, "ranking": ranking}
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
        affected_scores = scores_df if rebuild else scores_df[scores_df[ScoresCol.DATE] >= earliest_date]
        logger.info(
            "scores loaded",
            extra={"total": len(scores_df), "affected": len(affected_scores)},
        )

        logger.info("reading results")
        results_df = wr.s3.read_parquet(RESULTS_PATH)
        affected_results = results_df if rebuild else results_df[results_df[ResultsCol.DATE] >= earliest_date]
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
        _write_matches(
            dynamodb.Table(MATCHES_TABLE),
            dynamodb.Table(ALBUM_MATCHES_TABLE),
            affected_results,
            names,
        )
        logger.info("matches written", extra={"count": len(affected_results)})

        logger.info(
            "sync complete",
            extra={
                "scores_written": len(affected_scores),
                "matches_written": len(affected_results),
            },
        )
    except Exception:
        logger.exception("handler error")
        raise
