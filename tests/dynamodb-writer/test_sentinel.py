import pytest
from botocore.exceptions import ClientError
from sentinel import clear_rewrite_sentinel, read_rewrite_sentinel
from toa.paths import DYNAMODB_REWRITE_PENDING_KEY

BUCKET = "data"


def _error(code):
    return ClientError({"Error": {"Code": code}}, "op")


class FakeS3:
    """Stands in for a boto3 S3 client. `head_error` / `delete_error`, when set,
    are raised by the matching call; every delete's kwargs are recorded."""

    def __init__(self, etag='"e1"', head_error=None, delete_error=None):
        self.etag = etag
        self.head_error = head_error
        self.delete_error = delete_error
        self.deletes = []

    def head_object(self, Bucket, Key):  # noqa: N803 — boto3's spelling
        if self.head_error:
            raise self.head_error
        return {"ETag": self.etag}

    def delete_object(self, **kwargs):
        self.deletes.append(kwargs)
        if self.delete_error:
            raise self.delete_error


# ── read_rewrite_sentinel ───────────────────────────────────────────────────


def test_read_returns_etag_when_present():
    assert read_rewrite_sentinel(FakeS3(etag='"e1"'), BUCKET) == '"e1"'


@pytest.mark.parametrize("code", ["404", "NoSuchKey", "NotFound"])
def test_read_returns_none_when_missing(code):
    assert read_rewrite_sentinel(FakeS3(head_error=_error(code)), BUCKET) is None


def test_read_reraises_other_errors():
    # A 403 must fail the run: treating it as "no sentinel" would skip a rewrite.
    with pytest.raises(ClientError):
        read_rewrite_sentinel(FakeS3(head_error=_error("403")), BUCKET)


# ── clear_rewrite_sentinel ──────────────────────────────────────────────────


def test_clear_is_conditional_on_the_etag():
    s3 = FakeS3()
    assert clear_rewrite_sentinel(s3, BUCKET, '"e1"') is True
    assert s3.deletes == [
        {"Bucket": BUCKET, "Key": DYNAMODB_REWRITE_PENDING_KEY, "IfMatch": '"e1"'}
    ]


@pytest.mark.parametrize("code", ["PreconditionFailed", "412"])
def test_clear_refused_when_sentinel_changed(code):
    s3 = FakeS3(delete_error=_error(code))
    assert clear_rewrite_sentinel(s3, BUCKET, '"e1"') is False


def test_clear_reraises_other_errors():
    with pytest.raises(ClientError):
        clear_rewrite_sentinel(FakeS3(delete_error=_error("403")), BUCKET, '"e1"')
