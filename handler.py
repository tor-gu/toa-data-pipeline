import json
import os

import awswrangler as wr
import boto3
import pandas as pd

DATA_BUCKET = os.environ["DATA_BUCKET"]
SCORE_FUNCTION_NAME = os.environ["SCORE_FUNCTION_NAME"]
SD = float(os.environ["SD"])
UNIT_WIN_PROB = float(os.environ["UNIT_WIN_PROB"])

CONSOLIDATED_PATH = f"s3://{DATA_BUCKET}/results/consolidated/results.parquet"
SCORES_PATH = f"s3://{DATA_BUCKET}/scores/scores.parquet"

lambda_client = boto3.client("lambda")


def expand_pairs(match_id, order):
    return [
        {"winner": order[i], "loser": order[i + 1], "match_id": match_id}
        for i in range(len(order) - 1)
    ]


def invoke_score_lambda(pairs):
    response = lambda_client.invoke(
        FunctionName=SCORE_FUNCTION_NAME,
        Payload=json.dumps({"results": pairs, "sd": SD, "unit_win_prob": UNIT_WIN_PROB}),
    )
    payload = json.loads(response["Payload"].read())
    if response.get("FunctionError"):
        raise RuntimeError(f"Score Lambda error: {payload}")
    if payload.get("statusCode", 200) != 200:
        raise RuntimeError(f"Score Lambda returned {payload['statusCode']}: {payload.get('body')}")
    return json.loads(payload["body"])["scores"]


def handler(_event, context):
    consolidated = wr.s3.read_parquet(CONSOLIDATED_PATH)

    try:
        scores = wr.s3.read_parquet(SCORES_PATH)
    except wr.exceptions.NoFilesFound:
        scores = pd.DataFrame(columns=["id", "score", "robustness", "date"])

    result_dates = sorted(consolidated["date"].unique())
    scored_dates = set(scores["date"].unique()) if not scores.empty else set()
    most_recent = result_dates[-1]

    dates_to_process = sorted((set(result_dates) - scored_dates) | {most_recent})

    scores = scores[scores["date"] != most_recent]

    new_rows = []
    for date in dates_to_process:
        subset = consolidated[consolidated["date"] <= date]
        pairs = []
        for match_id, order in zip(subset["match_id"], subset["order"]):
            pairs.extend(expand_pairs(match_id, order))

        scored = invoke_score_lambda(pairs)
        for row in scored:
            row["date"] = date
        new_rows.extend(scored)

    if new_rows:
        updated = pd.concat([scores, pd.DataFrame(new_rows)], ignore_index=True)
        wr.s3.to_parquet(updated, path=SCORES_PATH)
