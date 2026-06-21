import os

import boto3

from toa.logging import Domain, get_logger

STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]

sfn = boto3.client("stepfunctions")

logger = get_logger(name="results-watcher", domain=Domain.SCORING_PIPELINE)


def handler(event, context):
    logger.info("handler started")
    try:
        sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input="{}",
        )
        logger.info("execution started", extra={"state_machine_arn": STATE_MACHINE_ARN})
    except Exception:
        logger.exception("handler error")
        raise
