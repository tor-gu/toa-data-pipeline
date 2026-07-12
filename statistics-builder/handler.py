import os

import awswrangler as wr
from stats import compute_stats
from toa.logging import Domain, get_logger
from toa.paths import (
    ENRICHED_SCORES_KEY,
    GLOBAL_STATISTICS_KEY,
    RESULTS_CONSOLIDATED_KEY,
)

DATA_BUCKET = os.environ["DATA_BUCKET"]

RESULTS_PATH = f"s3://{DATA_BUCKET}/{RESULTS_CONSOLIDATED_KEY}"
SCORES_PATH = f"s3://{DATA_BUCKET}/{ENRICHED_SCORES_KEY}"
STATISTICS_PATH = f"s3://{DATA_BUCKET}/{GLOBAL_STATISTICS_KEY}"

logger = get_logger(name="statistics-builder", domain=Domain.SCORING_PIPELINE)


def handler(event, _context):
    logger.info("handler started")
    try:
        results = wr.s3.read_parquet(RESULTS_PATH)
        scores = wr.s3.read_parquet(SCORES_PATH)

        stats = compute_stats(results, scores)
        wr.s3.to_parquet(stats, path=STATISTICS_PATH)

        logger.info("statistics build complete", extra=stats.iloc[0].to_dict())
    except Exception:
        logger.exception("handler error")
        raise
