"""Redis pub/sub events for WebSocket fan-out."""

from __future__ import annotations

import json
import logging
from typing import Any

import redis

from helios_common.config import settings

logger = logging.getLogger(__name__)

CHANNEL = "helios:events"

DETECTION_CREATED = "detection_created"
CHANGE_DETECTED = "change_detected"
ALERT_FIRED = "alert_fired"
SCENE_PROCESSING = "scene_processing"
SCENE_PROCESSING_COMPLETE = "scene_processing_complete"


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def publish_event(event_type: str, payload: dict[str, Any]) -> None:
    """Publish an event for FastAPI WebSocket subscribers."""
    message = json.dumps({"type": event_type, "payload": payload})
    try:
        client = _redis_client()
        client.publish(CHANNEL, message)
    except Exception as exc:
        logger.warning("Failed to publish event %s: %s", event_type, exc)


def subscribe_events():
    """Blocking Redis pubsub iterator (used in background thread)."""
    client = _redis_client()
    pubsub = client.pubsub()
    pubsub.subscribe(CHANNEL)
    return pubsub
