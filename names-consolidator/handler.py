import json
import os

import awswrangler as wr
import boto3
from consolidate import empty_names_df, fill_short_names, merge_names
from toa.logging import Domain, get_logger
from toa.paths import (
    NAMES_CONSOLIDATED_KEY,
    NAMES_PROCESSED_PREFIX,
    NAMES_UNPROCESSED_PREFIX,
)

DATA_BUCKET = os.environ["DATA_BUCKET"]
MIN_SHORT_NAME = int(os.environ["SHORT_NAME_MIN_LEN"])
MAX_SHORT_NAME = int(os.environ["SHORT_NAME_MAX_LEN"])
UNPROCESSED_PREFIX = NAMES_UNPROCESSED_PREFIX
PROCESSED_PREFIX = NAMES_PROCESSED_PREFIX
CONSOLIDATED_PATH = f"s3://{DATA_BUCKET}/{NAMES_CONSOLIDATED_KEY}"

s3 = boto3.client("s3")

logger = get_logger(name="names-consolidator", domain=Domain.SCORING_PIPELINE)


def handler(event, context):
    logger.info("handler started")
    try:
        paginator = s3.get_paginator("list_objects_v2")
        keys = [
            obj["Key"]
            for page in paginator.paginate(
                Bucket=DATA_BUCKET, Prefix=UNPROCESSED_PREFIX
            )
            for obj in page.get("Contents", [])
            if obj["Key"] != UNPROCESSED_PREFIX
        ]

        if not keys:
            logger.info("no unprocessed name files found")
            return {"files_processed": 0, "names_consolidated": 0}

        new_names = []
        for key in keys:
            obj = s3.get_object(Bucket=DATA_BUCKET, Key=key)
            new_names.append(json.loads(obj["Body"].read()))
        new_names = fill_short_names(new_names, MIN_SHORT_NAME, MAX_SHORT_NAME)

        try:
            existing = wr.s3.read_parquet(CONSOLIDATED_PATH)
        except wr.exceptions.NoFilesFound:
            existing = empty_names_df()

        combined = merge_names(existing, new_names)

        wr.s3.to_parquet(combined, path=CONSOLIDATED_PATH)

        # After the write, so an interrupted run leaves its inputs in place and
        # re-merges them next time -- the merge is idempotent by id.
        for key in keys:
            filename = key.split("/")[-1]
            s3.copy_object(
                Bucket=DATA_BUCKET,
                CopySource={"Bucket": DATA_BUCKET, "Key": key},
                Key=f"{PROCESSED_PREFIX}{filename}",
            )
            s3.delete_object(Bucket=DATA_BUCKET, Key=key)

        logger.info(
            "consolidation complete",
            extra={
                "files_processed": len(keys),
                "names_consolidated": len(combined),
            },
        )
        return {"files_processed": len(keys), "names_consolidated": len(combined)}
    except Exception:
        logger.exception("handler error")
        raise
