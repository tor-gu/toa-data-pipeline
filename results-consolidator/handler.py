import json
import os

import awswrangler as wr
import boto3
from results_consolidate import (
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
from toa.logging import Domain, get_logger
from toa.paths import (
    REDACTIONS_CONSOLIDATED_KEY,
    REDACTIONS_PROCESSED_PREFIX,
    REDACTIONS_UNPROCESSED_PREFIX,
    RESULTS_CONSOLIDATED_KEY,
    RESULTS_PROCESSED_PREFIX,
    RESULTS_UNPROCESSED_PREFIX,
    RESULTS_UNREDACTED_KEY,
)

DATA_BUCKET = os.environ["DATA_BUCKET"]
UNPROCESSED_PREFIX = RESULTS_UNPROCESSED_PREFIX
PROCESSED_PREFIX = RESULTS_PROCESSED_PREFIX
CONSOLIDATED_PATH = f"s3://{DATA_BUCKET}/{RESULTS_CONSOLIDATED_KEY}"
UNREDACTED_PATH = f"s3://{DATA_BUCKET}/{RESULTS_UNREDACTED_KEY}"
REDACTIONS_PATH = f"s3://{DATA_BUCKET}/{REDACTIONS_CONSOLIDATED_KEY}"

s3 = boto3.client("s3")

logger = get_logger(name="results-consolidator", domain=Domain.SCORING_PIPELINE)


def _list_unprocessed(prefix):
    paginator = s3.get_paginator("list_objects_v2")
    return [
        obj["Key"]
        for page in paginator.paginate(Bucket=DATA_BUCKET, Prefix=prefix)
        for obj in page.get("Contents", [])
        if obj["Key"] != prefix
    ]


def _load_json(keys):
    records = []
    for key in keys:
        obj = s3.get_object(Bucket=DATA_BUCKET, Key=key)
        records.append(json.loads(obj["Body"].read()))
    return records


def _read_parquet(path, empty):
    try:
        return wr.s3.read_parquet(path)
    except wr.exceptions.NoFilesFound:
        return empty


def _move_to_processed(keys, processed_prefix):
    for key in keys:
        filename = key.split("/")[-1]
        s3.copy_object(
            Bucket=DATA_BUCKET,
            CopySource={"Bucket": DATA_BUCKET, "Key": key},
            Key=f"{processed_prefix}{filename}",
        )
        s3.delete_object(Bucket=DATA_BUCKET, Key=key)


def handler(event, context):
    logger.info("handler started")
    try:
        result_keys = _list_unprocessed(UNPROCESSED_PREFIX)
        redaction_keys = _list_unprocessed(REDACTIONS_UNPROCESSED_PREFIX)

        if not result_keys and not redaction_keys:
            logger.info("no unprocessed files found")
            return {
                "files_processed": 0,
                "redaction_files_processed": 0,
                "redactions_processed": 0,
                "earliest_date": None,
            }

        new_results = _load_json(result_keys)
        new_redactions = _load_json(redaction_keys)

        unredacted = _read_parquet(UNREDACTED_PATH, empty_results_df())
        redactions = _read_parquet(REDACTIONS_PATH, empty_redactions_df())

        if new_results:
            unredacted = merge_results(unredacted, new_results)
            wr.s3.to_parquet(unredacted, path=UNREDACTED_PATH)

        # Calculate net-new redactions ids. (Don't count re-uploaded redactions)
        new_redacted_ids = {r[RedactionsCol.ID] for r in new_redactions} - set(
            redactions[RedactionsCol.ID]
        )
        redaction_date = earliest_redacted_date(unredacted, new_redacted_ids)
        redactions_removed = count_redacted_occurrences(unredacted, new_redacted_ids)

        if new_redactions:
            redactions = merge_redactions(redactions, new_redactions)
            wr.s3.to_parquet(redactions, path=REDACTIONS_PATH)

        # Rebuilt in full from every accumulated redaction, not just the new ones.
        redacted_ids = set(redactions[RedactionsCol.ID])
        results = apply_redactions(unredacted, redacted_ids)
        wr.s3.to_parquet(results, path=CONSOLIDATED_PATH)

        # After the writes, so an interrupted run leaves its inputs in place and
        # reprocesses them next time -- every step above is idempotent.
        _move_to_processed(result_keys, PROCESSED_PREFIX)
        _move_to_processed(redaction_keys, REDACTIONS_PROCESSED_PREFIX)

        results_date = (
            min(r[ResultsCol.DATE] for r in new_results) if new_results else None
        )
        earliest_date = combine_earliest(results_date, redaction_date)

        logger.info(
            "consolidation complete",
            extra={
                "files_processed": len(result_keys),
                "redaction_files_processed": len(redaction_keys),
                "redactions_processed": redactions_removed,
                "unredacted_records": len(unredacted),
                "total_records": len(results),
                "redactions_total": len(redactions),
                "earliest_date": earliest_date,
            },
        )
        return {
            "files_processed": len(result_keys),
            "redactions_processed": redactions_removed,
            "earliest_date": earliest_date,
        }
    except Exception:
        logger.exception("handler error")
        raise
