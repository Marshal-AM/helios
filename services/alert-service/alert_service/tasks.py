import logging

from alert_service.rules import scan_all_alerts
from helios_common.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="alert_service.tasks.scan_alerts")
def scan_alerts() -> dict:
    """Scan PostGIS for alert conditions every 5 minutes."""
    result = scan_all_alerts()
    logger.info("Alert scan complete: %s", result)
    return result
