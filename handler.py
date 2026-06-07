import json
import os

import awswrangler as wr
import boto3
import pandas as pd

DATA_BUCKET = os.environ["DATA_BUCKET"]
UNPROCESSED_PREFIX = "results/unprocessed/"
PROCESSED_PREFIX = "results/processed/"
CONSOLIDATED_PATH = f"s3://{DATA_BUCKET}/results/consolidated/results.parquet"

s3 = boto3.client("s3")


def handler(event, context):
    response = s3.list_objects_v2(Bucket=DATA_BUCKET, Prefix=UNPROCESSED_PREFIX)
    keys = [obj["Key"] for obj in response.get("Contents", []) if obj["Key"] != UNPROCESSED_PREFIX]

    if not keys:
        return {"files_processed": 0}

    new_results = []
    for key in keys:
        obj = s3.get_object(Bucket=DATA_BUCKET, Key=key)
        new_results.append(json.loads(obj["Body"].read()))

    try:
        existing = wr.s3.read_parquet(CONSOLIDATED_PATH)
    except wr.exceptions.NoFilesFound:
        existing = pd.DataFrame(columns=["match_id", "date", "order"])

    new_ids = {r["match_id"] for r in new_results}
    existing = existing[~existing["match_id"].isin(new_ids)]
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

    return {"files_processed": len(keys)}
