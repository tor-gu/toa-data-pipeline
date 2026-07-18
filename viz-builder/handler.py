import os

import awswrangler as wr
import pandas as pd
from toa.columns import VizCol
from toa.logging import Domain, get_logger
from toa.paths import (
    ENRICHED_SCORES_KEY,
    RESULTS_CONSOLIDATED_KEY,
    VIZ_ALBUMS_KEY,
    VIZ_DATES_KEY,
    VIZ_MATCHES_KEY,
)
from viz import build_album_vectors, build_dates, component_matches, largest_component

DATA_BUCKET = os.environ["DATA_BUCKET"]

RESULTS_PATH = f"s3://{DATA_BUCKET}/{RESULTS_CONSOLIDATED_KEY}"
SCORES_PATH = f"s3://{DATA_BUCKET}/{ENRICHED_SCORES_KEY}"
VIZ_DATES_PATH = f"s3://{DATA_BUCKET}/{VIZ_DATES_KEY}"
VIZ_ALBUMS_PATH = f"s3://{DATA_BUCKET}/{VIZ_ALBUMS_KEY}"
VIZ_MATCHES_PATH = f"s3://{DATA_BUCKET}/{VIZ_MATCHES_KEY}"

logger = get_logger(name="viz-builder", domain=Domain.SCORING_PIPELINE)


def handler(event, _context):
    logger.info("handler started")
    try:
        results = wr.s3.read_parquet(RESULTS_PATH)
        scores = wr.s3.read_parquet(SCORES_PATH)

        component = largest_component(results)
        matches = component_matches(results, component)
        dates = build_dates(scores, matches)
        albums = build_album_vectors(scores, component, dates, matches)

        wr.s3.to_parquet(pd.DataFrame({VizCol.DATE: dates}), path=VIZ_DATES_PATH)
        wr.s3.to_parquet(albums, path=VIZ_ALBUMS_PATH)
        wr.s3.to_parquet(matches, path=VIZ_MATCHES_PATH)

        logger.info(
            "viz build complete",
            extra={
                "num_dates": len(dates),
                "num_albums": len(albums),
                "num_matches": len(matches),
            },
        )
    except Exception:
        logger.exception("handler error")
        raise
