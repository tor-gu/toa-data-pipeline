from toa.logging import Domain, get_logger

logger = get_logger(name="pipeline-finalizer", domain=Domain.SCORING_PIPELINE)


def handler(event, _context):
    logger.info("handler started")
    status = event.get("status", "unknown")
    if status == "success":
        logger.info("pipeline completed successfully")
    else:
        logger.warning("pipeline failed", extra={"error": event.get("error")})
