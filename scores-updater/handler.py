import json
import os

import awswrangler as wr
import boto3
import pandas as pd
from toa.columns import ResultsCol, ScoresCol
from toa.logging import Domain, get_logger
from toa.paths import RESULTS_CONSOLIDATED_KEY, SCORES_KEY
from update import (
    assemble_updated_scores,
    score_dates,
    select_dates_to_rescore,
    select_scores_to_keep,
)

DATA_BUCKET = os.environ["DATA_BUCKET"]
SCORE_FUNCTION_NAME = os.environ["SCORE_FUNCTION_NAME"]
SD = float(os.environ["SD"])
UNIT_WIN_PROB = float(os.environ["UNIT_WIN_PROB"])

CONSOLIDATED_PATH = f"s3://{DATA_BUCKET}/{RESULTS_CONSOLIDATED_KEY}"
SCORES_PATH = f"s3://{DATA_BUCKET}/{SCORES_KEY}"

lambda_client = boto3.client("lambda")

logger = get_logger(name="scores-updater", domain=Domain.SCORING_PIPELINE)


def expand_pairs(match_id, order):
    return [
        {"winner": order[i], "loser": order[i + 1], "match_id": match_id}
        for i in range(len(order) - 1)
    ]


def invoke_score_lambda(pairs):
    response = lambda_client.invoke(
        FunctionName=SCORE_FUNCTION_NAME,
        Payload=json.dumps(
            {"results": pairs, "sd": SD, "unit_win_prob": UNIT_WIN_PROB}
        ),
    )
    payload = json.loads(response["Payload"].read())
    if response.get("FunctionError"):
        raise RuntimeError(f"Score Lambda error: {payload}")
    if payload.get("statusCode", 200) != 200:
        raise RuntimeError(
            f"Score Lambda returned {payload['statusCode']}: {payload.get('body')}"
        )
    return json.loads(payload["body"])["scores"]


def score_date(consolidated, date):
    """Fit one date over every match up to and including it.

    Reads `consolidated` but never mutates it, so several of these can run at
    once against the same DataFrame.
    """
    subset = consolidated[consolidated[ResultsCol.DATE] <= date]
    pairs = []
    for match_id, order in zip(subset[ResultsCol.MATCH_ID], subset[ResultsCol.ORDER]):
        pairs.extend(expand_pairs(match_id, order))

    scored = invoke_score_lambda(pairs)
    for row in scored:
        row[ScoresCol.DATE] = date
    logger.info("scored date", extra={"date": date, "num_scores": len(scored)})
    return scored


def handler(event, _context):
    logger.info("handler started")
    try:
        rebuild = event.get("rebuild", False)
        num_executors = event.get("num_executors", 1)
        earliest_date = None if rebuild else event["earliest_date"]

        if rebuild:
            logger.info("rebuild mode: rescoring all dates")
        if num_executors > 1:
            logger.info("scoring in parallel", extra={"num_executors": num_executors})

        consolidated = wr.s3.read_parquet(CONSOLIDATED_PATH)

        try:
            scores = wr.s3.read_parquet(SCORES_PATH)
        except wr.exceptions.NoFilesFound:
            scores = pd.DataFrame(
                columns=[
                    ScoresCol.ID,
                    ScoresCol.SCORE,
                    ScoresCol.ROBUSTNESS,
                    ScoresCol.DATE,
                ]
            )

        result_dates = sorted(consolidated[ResultsCol.DATE].unique())
        dates_to_process = select_dates_to_rescore(result_dates, earliest_date, rebuild)
        scores_to_keep = select_scores_to_keep(scores, earliest_date, rebuild)

        new_rows = score_dates(
            dates_to_process,
            lambda date: score_date(consolidated, date),
            num_executors,
        )

        if new_rows:
            updated = assemble_updated_scores(scores_to_keep, new_rows)
            wr.s3.to_parquet(updated, path=SCORES_PATH)

        logger.info(
            "scoring complete",
            extra={
                "dates_processed": len(dates_to_process),
                "num_executors": num_executors,
            },
        )
    except Exception:
        logger.exception("handler error")
        raise
