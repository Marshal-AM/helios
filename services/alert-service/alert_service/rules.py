"""Alert firing rules for Phase 4."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from math import atan2, cos, degrees, radians, sin

from sklearn.cluster import DBSCAN
from sqlalchemy import select, text

from helios_common.config import settings
from helios_common.db import SyncSessionLocal
from helios_common.events import ALERT_FIRED, publish_event
from helios_common.models import Alert, AlertSeverity, Aoi, AoiPriority, ChangeEvent, Scene

logger = logging.getLogger(__name__)

CRITICAL_CLASSES = {"tank", "2s1", "t62", "aircraft", "plane"}
HIGH_CLASSES = {"vehicle", "large-vehicle", "small-vehicle", "brdm_2", "btr_60"}
MEDIUM_CLASSES = {"ship", "harbor"}


def severity_for_class(class_name: str) -> AlertSeverity:
    c = class_name.lower()
    if c in CRITICAL_CLASSES:
        return AlertSeverity.CRITICAL
    if c in HIGH_CLASSES:
        return AlertSeverity.HIGH
    if c in MEDIUM_CLASSES:
        return AlertSeverity.MEDIUM
    return AlertSeverity.MEDIUM


def _revisit_minutes(priority: AoiPriority) -> int:
    if priority == AoiPriority.HIGH:
        return settings.revisit_interval_high_minutes
    if priority == AoiPriority.LOW:
        return settings.revisit_interval_low_minutes
    return settings.revisit_interval_medium_minutes


def _recent_duplicate(session, aoi_id: int, alert_type: str) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.alert_dedup_hours)
    row = session.execute(
        text(
            """
            SELECT 1 FROM alerts
            WHERE aoi_id = :aoi_id AND alert_type = :alert_type AND timestamp >= :cutoff
            LIMIT 1
            """
        ),
        {"aoi_id": aoi_id, "alert_type": alert_type, "cutoff": cutoff},
    ).first()
    return row is not None


def fire_alert(
    session,
    *,
    aoi_id: int,
    alert_type: str,
    severity: AlertSeverity,
    lat: float,
    lon: float,
    description: str,
    change_event_id: int | None = None,
) -> Alert | None:
    if _recent_duplicate(session, aoi_id, alert_type):
        return None

    alert = Alert(
        aoi_id=aoi_id,
        change_event_id=change_event_id,
        alert_type=alert_type,
        severity=severity,
        lat=lat,
        lon=lon,
        description=description,
    )
    session.add(alert)
    session.flush()

    if change_event_id:
        ce = session.get(ChangeEvent, change_event_id)
        if ce:
            ce.alert_fired = True

    publish_event(
        ALERT_FIRED,
        {
            "id": alert.id,
            "aoi_id": aoi_id,
            "alert_type": alert_type,
            "severity": severity.value,
            "lat": lat,
            "lon": lon,
            "description": description,
            "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
        },
    )
    return alert


def _scene_classes(session, scene_id: int) -> set[str]:
    rows = session.execute(
        text("SELECT DISTINCT class FROM detections WHERE scene_id = :sid"),
        {"sid": scene_id},
    ).fetchall()
    return {r[0].lower() for r in rows}


def _recent_scenes(session, aoi_id: int, limit: int) -> list[Scene]:
    stmt = (
        select(Scene)
        .where(Scene.aoi_id == aoi_id, Scene.processed.is_(True))
        .order_by(Scene.acquisition_timestamp.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def check_new_object(session, aoi: Aoi) -> int:
    scenes = _recent_scenes(session, aoi.id, 4)
    if len(scenes) < 2:
        return 0
    latest = _scene_classes(session, scenes[0].id)
    prior_sets = [_scene_classes(session, s.id) for s in scenes[1:4]]
    fired = 0
    for cls in latest:
        if cls and all(cls not in ps for ps in prior_sets):
            det = session.execute(
                text(
                    """
                    SELECT lat, lon FROM detections
                    WHERE scene_id = :sid AND lower(class) = :cls
                    LIMIT 1
                    """
                ),
                {"sid": scenes[0].id, "cls": cls},
            ).first()
            if det and fire_alert(
                session,
                aoi_id=aoi.id,
                alert_type="new_object",
                severity=severity_for_class(cls),
                lat=det[0],
                lon=det[1],
                description=f"New class '{cls}' appeared in AOI {aoi.name}",
            ):
                fired += 1
    return fired


def check_disappearance(session, aoi: Aoi) -> int:
    scenes = _recent_scenes(session, aoi.id, 6)
    if len(scenes) < 5:
        return 0
    fired = 0
    present_in_first_3: set[str] = set()
    for s in scenes[2:5]:
        present_in_first_3 |= _scene_classes(session, s.id)
    absent_two = present_in_first_3.copy()
    for s in scenes[:2]:
        absent_two -= _scene_classes(session, s.id)
    for cls in absent_two:
        det = session.execute(
            text(
                """
                SELECT lat, lon FROM detections d
                JOIN scenes s ON s.id = d.scene_id
                WHERE d.aoi_id = :aoi AND lower(d.class) = :cls
                ORDER BY s.acquisition_timestamp DESC LIMIT 1
                """
            ),
            {"aoi": aoi.id, "cls": cls},
        ).first()
        if det and fire_alert(
            session,
            aoi_id=aoi.id,
            alert_type="disappearance",
            severity=severity_for_class(cls),
            lat=det[0],
            lon=det[1],
            description=f"Class '{cls}' absent for 2 passes after prior presence in AOI {aoi.name}",
        ):
            fired += 1
    return fired


def _cluster_count(session, scene_id: int) -> int:
    rows = session.execute(
        text("SELECT lat, lon FROM detections WHERE scene_id = :sid"),
        {"sid": scene_id},
    ).fetchall()
    if len(rows) < 2:
        return len(rows)
    import numpy as np

    coords = np.radians([[r[0], r[1]] for r in rows])
    # eps ~0.5km in radians
    eps = 0.5 / 6371.0
    labels = DBSCAN(eps=eps, min_samples=2, metric="haversine").fit(coords).labels_
    return len(set(labels)) - (1 if -1 in labels else 0)


def check_formation_change(session, aoi: Aoi) -> int:
    scenes = _recent_scenes(session, aoi.id, 2)
    if len(scenes) < 2:
        return 0
    c1 = _cluster_count(session, scenes[1].id)
    c2 = _cluster_count(session, scenes[0].id)
    if c1 == 0:
        return 0
    change = abs(c2 - c1) / c1
    if change <= settings.formation_change_pct:
        return 0
    center = session.execute(
        text("SELECT lat, lon FROM detections WHERE aoi_id = :aoi LIMIT 1"),
        {"aoi": aoi.id},
    ).first()
    if not center:
        return 0
    if fire_alert(
        session,
        aoi_id=aoi.id,
        alert_type="formation_change",
        severity=AlertSeverity.HIGH,
        lat=center[0],
        lon=center[1],
        description=(
            f"Formation change in {aoi.name}: clusters {c1} -> {c2} "
            f"({change * 100:.0f}% change)"
        ),
    ):
        return 1
    return 0


def check_movement_threshold(session, aoi: Aoi) -> int:
    rows = session.execute(
        text(
            """
            SELECT id, distance_moved_m, bearing_degrees, detection_id_t2
            FROM change_events
            WHERE aoi_id = :aoi AND event_type = 'moved'
              AND distance_moved_m >= :thresh AND alert_fired = false
            """
        ),
        {"aoi": aoi.id, "thresh": settings.movement_alert_threshold_m},
    ).fetchall()
    fired = 0
    for row in rows:
        det = session.execute(
            text("SELECT lat, lon FROM detections WHERE id = :id"),
            {"id": row[3]},
        ).first()
        if not det:
            continue
        bearing = row[2] or 0
        dist = row[1] or 0
        if fire_alert(
            session,
            aoi_id=aoi.id,
            alert_type="movement_threshold",
            severity=AlertSeverity.HIGH,
            lat=det[0],
            lon=det[1],
            description=(
                f"Movement {dist:.0f}m at bearing {bearing:.0f}° in AOI {aoi.name}"
            ),
            change_event_id=row[0],
        ):
            fired += 1
    return fired


def check_density_surge(session, aoi: Aoi) -> int:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    total = session.execute(
        text(
            "SELECT COUNT(*) FROM detections WHERE aoi_id = :aoi AND timestamp >= :cutoff"
        ),
        {"aoi": aoi.id, "cutoff": cutoff},
    ).scalar_one()
    avg_per_day = total / 30.0 if total else 0
    latest_scene = _recent_scenes(session, aoi.id, 1)
    if not latest_scene:
        return 0
    latest_count = session.execute(
        text("SELECT COUNT(*) FROM detections WHERE scene_id = :sid"),
        {"sid": latest_scene[0].id},
    ).scalar_one()
    if avg_per_day <= 0 or latest_count < avg_per_day * settings.density_surge_multiplier:
        return 0
    center = session.execute(
        text("SELECT lat, lon FROM detections WHERE scene_id = :sid LIMIT 1"),
        {"sid": latest_scene[0].id},
    ).first()
    if not center:
        return 0
    if fire_alert(
        session,
        aoi_id=aoi.id,
        alert_type="density_surge",
        severity=AlertSeverity.HIGH,
        lat=center[0],
        lon=center[1],
        description=(
            f"Density surge in {aoi.name}: {latest_count} detections vs "
            f"{avg_per_day:.1f}/day 30d average"
        ),
    ):
        return 1
    return 0


def check_no_coverage(session, aoi: Aoi) -> int:
    if not aoi.last_pass_at:
        return 0
    revisit = _revisit_minutes(aoi.priority) * 1.5
    elapsed = (datetime.now(timezone.utc) - aoi.last_pass_at).total_seconds() / 60.0
    if elapsed <= revisit:
        return 0
    # centroid of AOI for alert location
    center = session.execute(
        text(
            """
            SELECT ST_Y(ST_Centroid(polygon)), ST_X(ST_Centroid(polygon))
            FROM aois WHERE id = :id
            """
        ),
        {"id": aoi.id},
    ).first()
    if not center:
        return 0
    if fire_alert(
        session,
        aoi_id=aoi.id,
        alert_type="no_coverage",
        severity=AlertSeverity.MEDIUM,
        lat=center[0],
        lon=center[1],
        description=(
            f"No coverage for {aoi.name}: last pass {elapsed:.0f}min ago "
            f"(threshold {revisit:.0f}min)"
        ),
    ):
        return 1
    return 0


def scan_all_alerts() -> dict:
    total = 0
    with SyncSessionLocal() as session:
        aois = session.scalars(select(Aoi).where(Aoi.monitoring_active.is_(True))).all()
        for aoi in aois:
            total += check_new_object(session, aoi)
            total += check_disappearance(session, aoi)
            total += check_formation_change(session, aoi)
            total += check_movement_threshold(session, aoi)
            total += check_density_surge(session, aoi)
            total += check_no_coverage(session, aoi)
        session.commit()
    return {"alerts_fired": total, "status": "complete"}
