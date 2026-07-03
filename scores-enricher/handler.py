import os

import awswrangler as wr
from enrich import enrich
from toa.logging import Domain, get_logger
from toa.paths import ENRICHED_SCORES_KEY, SCORES_KEY

DATA_BUCKET = os.environ["DATA_BUCKET"]
TIE_TOLERANCE = float(os.environ.get("TIE_TOLERANCE", "0.000005"))

SCORES_PATH = f"s3://{DATA_BUCKET}/{SCORES_KEY}"
ENRICHED_SCORES_PATH = f"s3://{DATA_BUCKET}/{ENRICHED_SCORES_KEY}"

logger = get_logger(name="scores-enricher", domain=Domain.SCORING_PIPELINE)


def handler(event, _context):
    logger.info("handler started")
    try:
        scores = wr.s3.read_parquet(SCORES_PATH)
        enriched = enrich(scores, TIE_TOLERANCE)
        wr.s3.to_parquet(enriched, path=ENRICHED_SCORES_PATH)
        logger.info("enrichment complete", extra={"rows": len(enriched)})
    except Exception:
        logger.exception("handler error")
        raise
