import json
import os

import awswrangler as wr
import boto3
import pandas as pd
from toa.columns import ResultsCol
from toa.logging import Domain, get_logger
from toa.paths import (
    RESULTS_CONSOLIDATED_KEY,
    RESULTS_PROCESSED_PREFIX,
    RESULTS_UNPROCESSED_PREFIX,
)

DATA_BUCKET = os.environ["DATA_BUCKET"]
UNPROCESSED_PREFIX = RESULTS_UNPROCESSED_PREFIX
PROCESSED_PREFIX = RESULTS_PROCESSED_PREFIX
CONSOLIDATED_PATH = f"s3://{DATA_BUCKET}/{RESULTS_CONSOLIDATED_KEY}"

s3 = boto3.client("s3")

logger = get_logger(name="results-consolidator", domain=Domain.SCORING_PIPELINE)


def handler(event, context):
    logger.info("handler started")
    try:
        response = s3.list_objects_v2(Bucket=DATA_BUCKET, Prefix=UNPROCESSED_PREFIX)
        keys = [
            obj["Key"]
            for obj in response.get("Contents", [])
            if obj["Key"] != UNPROCESSED_PREFIX
        ]

        if not keys:
            logger.info("no unprocessed files found")
            return {"files_processed": 0, "earliest_date": None}

        new_results = []
        for key in keys:
            obj = s3.get_object(Bucket=DATA_BUCKET, Key=key)
            new_results.append(json.loads(obj["Body"].read()))

        try:
            existing = wr.s3.read_parquet(CONSOLIDATED_PATH)
        except wr.exceptions.NoFilesFound:
            existing = pd.DataFrame(
                columns=[ResultsCol.MATCH_ID, ResultsCol.DATE, ResultsCol.ORDER]
            )

        new_ids = {r[ResultsCol.MATCH_ID] for r in new_results}
        existing = existing[~existing[ResultsCol.MATCH_ID].isin(new_ids)]
        combined = pd.concat([existing, pd.DataFrame(new_results)], ignore_index=True)

        wr.s3.to_parquet(combined, path=CONSOLIDATED_PATH)

        for key in keys:
            filename = key.split("/")[-1]
            s3.copy_object(
                Bucket=DATA_BUCKET,
                CopySource={"Bucket": DATA_BUCKET, "Key": key},
                Key=f"{PROCESSED_PREFIX}{filename}",
            )
            s3.delete_object(Bucket=DATA_BUCKET, Key=key)

        earliest_date = min(r[ResultsCol.DATE] for r in new_results)
        logger.info(
            "consolidation complete",
            extra={
                "files_processed": len(keys),
                "total_records": len(combined),
                "earliest_date": earliest_date,
            },
        )
        return {"files_processed": len(keys), "earliest_date": earliest_date}
    except Exception:
        logger.exception("handler error")
        raise
