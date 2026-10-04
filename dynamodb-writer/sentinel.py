"""The full-rewrite sentinel: an S3 object whose presence tells this writer to
rewrite every table. results-consolidator sets it; only this module clears it."""

from botocore.exceptions import ClientError
from toa.paths import DYNAMODB_REWRITE_PENDING_KEY


def read_rewrite_sentinel(s3, bucket):
    """The rewrite sentinel's entity tag, or None when no rewrite is pending."""
    try:
        resp = s3.head_object(Bucket=bucket, Key=DYNAMODB_REWRITE_PENDING_KEY)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return None
        raise
    return resp["ETag"]


def clear_rewrite_sentinel(s3, bucket, etag):
    """Delete the sentinel only if it is still the version this run saw at start.

    The original sentinel is identified by its entity tag.

    We will return false (and not delete) if the tag has changed.
    """
    try:
        s3.delete_object(Bucket=bucket, Key=DYNAMODB_REWRITE_PENDING_KEY, IfMatch=etag)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("PreconditionFailed", "412"):
            return False
        raise
    return True
