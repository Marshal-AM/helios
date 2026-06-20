"""WebSocket payload builders."""

from __future__ import annotations

from helios_common.geojson import detection_feature
from helios_common.models import Detection, Scene


def detection_event_payload(detection: Detection, scene: Scene) -> dict:
    feature = detection_feature(
        detection_id=detection.id,
        lat=detection.lat,
        lon=detection.lon,
        class_name=detection.class_,
        confidence=detection.confidence,
        timestamp=detection.timestamp,
        subclass=detection.subclass,
        heading_degrees=detection.heading_degrees,
        scene_id=detection.scene_id,
        aoi_id=detection.aoi_id,
        satellite_source=scene.satellite_source,
    )
    return {"feature": feature}
