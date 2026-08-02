from initialize import normalize, unknown_fields
from toa.logging import Domain, get_logger

logger = get_logger(name="pipeline-initializer", domain=Domain.SCORING_PIPELINE)


def handler(event, _context):
    logger.info("handler started")
    try:
        normalized = normalize(event)
        unknown = unknown_fields(event)
        if unknown:
            logger.warning("ignoring unknown input fields", extra={"fields": unknown})
        logger.info("input normalized", extra=normalized)
        return normalized
    except Exception:
        logger.exception("handler error")
        raise
