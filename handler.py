import os

import boto3

STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]

sfn = boto3.client("stepfunctions")


def handler(event, context):
    sfn.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        input="{}",
    )
