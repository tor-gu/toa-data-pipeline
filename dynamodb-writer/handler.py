import os

import boto3
from inputs import read_inputs
from rewrite import check_full_rewrite_inputs, rewrite_mode
from sentinel import clear_rewrite_sentinel, read_rewrite_sentinel
from tables import Tables, delete_all_stale, write_all
from toa.columns import ResultsCol, ScoresCol
from toa.logging import Domain, get_logger
from transform import select_since

DATA_BUCKET = os.environ["DATA_BUCKET"]
SCORES_TABLE = os.environ["SCORES_TABLE"]
MATCHES_TABLE = os.environ["MATCHES_TABLE"]
ALBUM_MATCHES_TABLE = os.environ["ALBUM_MATCHES_TABLE"]
GLOBAL_STATISTICS_TABLE = os.environ["GLOBAL_STATISTICS_TABLE"]
VIZ_TABLE = os.environ["VIZ_TABLE"]

logger = get_logger(name="dynamodb-writer", domain=Domain.SCORING_PIPELINE)
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")


def _tables():
    return Tables(
        scores=dynamodb.Table(SCORES_TABLE),
        matches=dynamodb.Table(MATCHES_TABLE),
        album_matches=dynamodb.Table(ALBUM_MATCHES_TABLE),
        global_statistics=dynamodb.Table(GLOBAL_STATISTICS_TABLE),
        viz=dynamodb.Table(VIZ_TABLE),
    )


def handler(event, _context):
    logger.info("handler started")
    try:
        # Read the sentinel before any parquet: a sentinel seen here is one whose
        # redaction is already in the inputs this run is about to read.
        sentinel_etag = read_rewrite_sentinel(s3, DATA_BUCKET)
        reason = rewrite_mode(event.get("rebuild", False), sentinel_etag is not None)
        full = reason is not None
        mode = "full" if full else "incremental"
        earliest_date = None if full else event["earliest_date"]
        logger.info(
            "write mode",
            extra={
                "mode": mode,
                "reason": reason,
                "sentinel_present": sentinel_etag is not None,
                "earliest_date": earliest_date,
            },
        )

        inputs = read_inputs(DATA_BUCKET)
        affected_scores = select_since(inputs.scores, ScoresCol.DATE, earliest_date)
        affected_results = select_since(inputs.results, ResultsCol.DATE, earliest_date)
        logger.info(
            "inputs loaded",
            extra={
                "names": len(inputs.names),
                "scores_total": len(inputs.scores),
                "scores_affected": len(affected_scores),
                "results_total": len(inputs.results),
                "results_affected": len(affected_results),
            },
        )
        if full:
            check_full_rewrite_inputs(len(inputs.results), len(inputs.scores))

        tables = _tables()
        written = write_all(tables, inputs, affected_scores, affected_results)
        logger.info(
            "tables written",
            extra={
                "scores": len(affected_scores),
                "matches": len(affected_results),
                "viz_items": written.viz_items,
                "viz_stale_deleted": written.viz_stale_deleted,
            },
        )

        stale_deleted = {}
        if full:
            stale_deleted = delete_all_stale(tables, written)
            logger.info("stale rows deleted", extra=stale_deleted)

        # Only a sentinel seen before the reads may be cleared; one that appeared
        # mid-run belongs to a redaction this run may not have read.
        sentinel_cleared = False
        if sentinel_etag is not None:
            sentinel_cleared = clear_rewrite_sentinel(s3, DATA_BUCKET, sentinel_etag)
            if not sentinel_cleared:
                logger.warning(
                    "rewrite sentinel changed during the run; leaving it set"
                )
        elif full:
            logger.info("no rewrite sentinel was pending; nothing to clear")

        logger.info(
            "update complete",
            extra={
                "mode": mode,
                "reason": reason,
                "scores_written": len(affected_scores),
                "matches_written": len(affected_results),
                "stale_deleted": stale_deleted,
                "sentinel_cleared": sentinel_cleared,
            },
        )
    except Exception:
        logger.exception("handler error")
        raise
