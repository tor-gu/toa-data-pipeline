import json
import os

import awswrangler as wr
import boto3
import pandas as pd

from toa.logging import Domain, get_logger

DATA_BUCKET = os.environ["DATA_BUCKET"]
UNPROCESSED_PREFIX = "names/unprocessed/"
CONSOLIDATED_PATH = f"s3://{DATA_BUCKET}/names/consolidated/names.parquet"

s3 = boto3.client("s3")

logger = get_logger(name="names-consolidator", domain=Domain.SCORING_PIPELINE)


def handler(event, context):
    logger.info("handler started")
    try:
        response = s3.list_objects_v2(Bucket=DATA_BUCKET, Prefix=UNPROCESSED_PREFIX)
        keys = [obj["Key"] for obj in response.get("Contents", []) if obj["Key"] != UNPROCESSED_PREFIX]

        if not keys:
            logger.info("no name files found")
            return {"names_consolidated": 0}

        names = []
        for key in keys:
            obj = s3.get_object(Bucket=DATA_BUCKET, Key=key)
            names.append(json.loads(obj["Body"].read()))

        df = pd.DataFrame(names)[["id", "artist", "album"]]
        wr.s3.to_parquet(df, path=CONSOLIDATED_PATH)

        logger.info("consolidation complete", extra={"names_consolidated": len(df)})
        return {"names_consolidated": len(df)}
    except Exception:
        logger.exception("handler error")
        raise
