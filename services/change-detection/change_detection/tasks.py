import logging
from math import atan2, cos, degrees, radians, sin
from pathlib import Path

import numpy as np
from sqlalchemy import select, text

from helios_common.celery_app import celery_app
from helios_common.config import settings
from helios_common.db import SyncSessionLocal
from helios_common.events import CHANGE_DETECTED, publish_event
from helios_common.models import ChangeEvent, ChangeEventType, Detection, Scene
from helios_common.paths import scene_tiles_dir
from helios_common.triton_client import infer_bit

logger = logging.getLogger(__name__)


def _tile_pairs(t1_dir: Path, t2_dir: Path) -> list[tuple[str, str]]:
    pairs = []
    for t2 in sorted(t2_dir.glob("*.tif")):
        t1 = t1_dir / t2.name
        if t1.exists():
            pairs.append((str(t1), str(t2)))
    return pairs


def _detection_centers(session, scene_id: int) -> list[tuple[int, float, float, str]]:
    rows = session.execute(
        text(
            "SELECT id, lat, lon, class FROM detections WHERE scene_id = :sid"
        ),
        {"sid": scene_id},
    ).fetchall()
    return [(r[0], r[1], r[2], r[3]) for r in rows]


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * __import__("math").asin(__import__("math").sqrt(a))


def _bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1r, lat2r = radians(lat1), radians(lat2)
    dlon = radians(lon2 - lon1)
    x = sin(dlon) * cos(lat2r)
    y = cos(lat1r) * sin(lat2r) - sin(lat1r) * cos(lat2r) * cos(dlon)
    return (degrees(atan2(x, y)) + 360) % 360


def _speed_kmh(distance_m: float, t1: Scene, t2: Scene) -> float | None:
    if not t1.acquisition_timestamp or not t2.acquisition_timestamp:
        return None
    delta_h = (t2.acquisition_timestamp - t1.acquisition_timestamp).total_seconds() / 3600.0
    if delta_h <= 0:
        return None
    return (distance_m / 1000.0) / delta_h


def _match_detections(
    t1_dets: list[tuple[int, float, float, str]],
    t2_dets: list[tuple[int, float, float, str]],
    max_dist_m: float = 50.0,
) -> tuple[list, list, list]:
    matched_t1 = set()
    matched_t2 = set()
    moved = []

    for i, (id2, lat2, lon2, cls2) in enumerate(t2_dets):
        best_j, best_dist = None, max_dist_m
        for j, (id1, lat1, lon1, cls1) in enumerate(t1_dets):
            if j in matched_t1 or cls1 != cls2:
                continue
            dist = _haversine_m(lat1, lon1, lat2, lon2)
            if dist < best_dist:
                best_dist = dist
                best_j = j
        if best_j is not None:
            matched_t1.add(best_j)
            matched_t2.add(i)
            id1, lat1, lon1, _ = t1_dets[best_j]
            if best_dist > 5.0:
                moved.append((id1, id2, best_dist, lat1, lon1, lat2, lon2))

    appeared = [t2_dets[i] for i in range(len(t2_dets)) if i not in matched_t2]
    disappeared = [t1_dets[j] for j in range(len(t1_dets)) if j not in matched_t1]
    return appeared, disappeared, moved


def _publish_change(session, event: ChangeEvent) -> None:
    t1 = session.get(Detection, event.detection_id_t1) if event.detection_id_t1 else None
    t2 = session.get(Detection, event.detection_id_t2) if event.detection_id_t2 else None
    publish_event(
        CHANGE_DETECTED,
        {
            "id": event.id,
            "aoi_id": event.aoi_id,
            "event_type": event.event_type.value,
            "distance_moved_m": event.distance_moved_m,
            "speed_kmh": event.speed_kmh,
            "bearing_degrees": event.bearing_degrees,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "t1": {"lat": t1.lat, "lon": t1.lon, "class": t1.class_} if t1 else None,
            "t2": {"lat": t2.lat, "lon": t2.lon, "class": t2.class_} if t2 else None,
        },
    )


@celery_app.task(name="change_detection.tasks.detect_changes")
def detect_changes(aoi_id: int, t1_scene_id: int, t2_scene_id: int) -> dict:
    """Run BIT change detection between two scenes and write change_events."""
    t1_dir = scene_tiles_dir(t1_scene_id)
    t2_dir = scene_tiles_dir(t2_scene_id)
    pairs = _tile_pairs(t1_dir, t2_dir)
    change_pixels = 0

    for t1_path, t2_path in pairs:
        try:
            mask = infer_bit(t1_path, t2_path)
            change_pixels += int(np.sum(mask >= settings.bit_change_threshold))
        except Exception as exc:
            logger.exception("BIT inference failed %s %s: %s", t1_path, t2_path, exc)

    events_created = 0
    created_events: list[ChangeEvent] = []
    with SyncSessionLocal() as session:
        t1_scene = session.get(Scene, t1_scene_id)
        t2_scene = session.get(Scene, t2_scene_id)
        t1_dets = _detection_centers(session, t1_scene_id)
        t2_dets = _detection_centers(session, t2_scene_id)
        appeared, disappeared, moved = _match_detections(t1_dets, t2_dets)

        for det in appeared:
            ev = ChangeEvent(
                aoi_id=aoi_id,
                event_type=ChangeEventType.APPEARED,
                detection_id_t2=det[0],
            )
            session.add(ev)
            created_events.append(ev)
            events_created += 1
        for det in disappeared:
            ev = ChangeEvent(
                aoi_id=aoi_id,
                event_type=ChangeEventType.DISAPPEARED,
                detection_id_t1=det[0],
            )
            session.add(ev)
            created_events.append(ev)
            events_created += 1
        for id1, id2, dist_m, lat1, lon1, lat2, lon2 in moved:
            bearing = _bearing_degrees(lat1, lon1, lat2, lon2)
            speed = _speed_kmh(dist_m, t1_scene, t2_scene) if t1_scene and t2_scene else None
            ev = ChangeEvent(
                aoi_id=aoi_id,
                event_type=ChangeEventType.MOVED,
                detection_id_t1=id1,
                detection_id_t2=id2,
                distance_moved_m=dist_m,
                bearing_degrees=bearing,
                speed_kmh=speed,
            )
            session.add(ev)
            created_events.append(ev)
            events_created += 1

        session.flush()
        for ev in created_events:
            _publish_change(session, ev)
        session.commit()

    logger.info(
        "Change detection aoi=%s t1=%s t2=%s events=%d change_pixels=%d",
        aoi_id,
        t1_scene_id,
        t2_scene_id,
        events_created,
        change_pixels,
    )
    return {
        "aoi_id": aoi_id,
        "t1_scene_id": t1_scene_id,
        "t2_scene_id": t2_scene_id,
        "events_created": events_created,
        "change_pixels": change_pixels,
        "status": "complete",
    }
