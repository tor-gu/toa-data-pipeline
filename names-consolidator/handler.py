import json
import os

import awswrangler as wr
import boto3
import pandas as pd
from short_name import generate_short_name
from toa.columns import NamesCol
from toa.logging import Domain, get_logger
from toa.paths import NAMES_CONSOLIDATED_KEY, NAMES_UNPROCESSED_PREFIX

DATA_BUCKET = os.environ["DATA_BUCKET"]
MIN_SHORT_NAME = int(os.environ["SHORT_NAME_MIN_LEN"])
MAX_SHORT_NAME = int(os.environ["SHORT_NAME_MAX_LEN"])
UNPROCESSED_PREFIX = NAMES_UNPROCESSED_PREFIX
CONSOLIDATED_PATH = f"s3://{DATA_BUCKET}/{NAMES_CONSOLIDATED_KEY}"

s3 = boto3.client("s3")

logger = get_logger(name="names-consolidator", domain=Domain.SCORING_PIPELINE)


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
            logger.info("no name files found")
            return {"names_consolidated": 0}

        names = []
        for key in keys:
            obj = s3.get_object(Bucket=DATA_BUCKET, Key=key)
            name = json.loads(obj["Body"].read())
            if not name.get(NamesCol.SHORT_NAME):
                name[NamesCol.SHORT_NAME] = generate_short_name(
                    name[NamesCol.ALBUM], MIN_SHORT_NAME, MAX_SHORT_NAME
                )
            names.append(name)

        df = pd.DataFrame(names)[
            [NamesCol.ID, NamesCol.ARTIST, NamesCol.ALBUM, NamesCol.SHORT_NAME]
        ]
        wr.s3.to_parquet(df, path=CONSOLIDATED_PATH)

        logger.info("consolidation complete", extra={"names_consolidated": len(df)})
        return {"names_consolidated": len(df)}
    except Exception:
        logger.exception("handler error")
        raise
