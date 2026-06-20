import json
import os

import awswrangler as wr
import boto3
import pandas as pd

from toa.columns import NamesCol
from toa.logging import Domain, get_logger
from toa.paths import NAMES_CONSOLIDATED_KEY, NAMES_UNPROCESSED_PREFIX

DATA_BUCKET = os.environ["DATA_BUCKET"]
UNPROCESSED_PREFIX = NAMES_UNPROCESSED_PREFIX
CONSOLIDATED_PATH = f"s3://{DATA_BUCKET}/{NAMES_CONSOLIDATED_KEY}"

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

        df = pd.DataFrame(names)[[NamesCol.ID, NamesCol.ARTIST, NamesCol.ALBUM]]
        wr.s3.to_parquet(df, path=CONSOLIDATED_PATH)

        logger.info("consolidation complete", extra={"names_consolidated": len(df)})
        return {"names_consolidated": len(df)}
    except Exception:
        logger.exception("handler error")
        raise
